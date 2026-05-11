# services/solicitud_service.py
"""
Servicios de lógica de negocio para solicitudes.
Separa la lógica de las rutas para mejor mantenibilidad.
"""
from flask import current_app
from db.conexion import Database, fetch_one, fetch_all, execute
from db.cache import pdf_cache, preview_cache

def get_cache():
    return current_app.extensions.get('cache')

ORDEN_CICLOS = ['I','II','III','IV','V','VI','VII','VIII','IX','X']
CICLOS = {'I','II','III','IV','V','VI','VII','VIII','IX','X'}
_ORDEN_CICLO = "CASE cp_l.ciclo WHEN 'I' THEN 1 WHEN 'II' THEN 2 WHEN 'III' THEN 3 WHEN 'IV' THEN 4 WHEN 'V' THEN 5 WHEN 'VI' THEN 6 WHEN 'VII' THEN 7 WHEN 'VIII' THEN 8 WHEN 'IX' THEN 9 WHEN 'X' THEN 10 END"
_ORDEN_CICLO_PLAN = "CASE ciclo WHEN 'I' THEN 1 WHEN 'II' THEN 2 WHEN 'III' THEN 3 WHEN 'IV' THEN 4 WHEN 'V' THEN 5 WHEN 'VI' THEN 6 WHEN 'VII' THEN 7 WHEN 'VIII' THEN 8 WHEN 'IX' THEN 9 WHEN 'X' THEN 10 END"

def get_solicitud_completa(solicitud_id):
    with Database(dictionary=True) as db:
        db.cur.execute("""
            SELECT s.*,
                   COALESCE(p.apellidos_nombres, '') AS nombre,
                   COALESCE(p.dni, '') AS dni,
                   COALESCE(p.programa, '') AS programa,
                   COALESCE(p.modalidad_estudios, '') AS modalidad,
                   COALESCE(p.semestre_academico,'') AS semestre_academico,
                   CASE WHEN p.sexo IN ('F','FEMENINO','MUJER') THEN 'F' ELSE 'M' END AS genero,
                   p.codigo AS codigo_postulante,
                   p.institucion_procedencia,
                   COALESCE(p.correo,'') AS correo,
                   COALESCE(p.celular,'') AS celular,
                   COALESCE(NULLIF(p.institucion_procedencia,''), pe.nombre_plan, '') AS ies_origen
            FROM solicitudes s
            LEFT JOIN postulantes p ON s.postulante_id = p.id
            LEFT JOIN planes_estudio pe ON s.plan_externo_id = pe.id
            WHERE s.id=%s
        """, (solicitud_id,))
        s = db.cur.fetchone()

        if not s:
            return None

        s['tratamiento'] = 'el interesado' if s.get('genero') == 'M' else 'la interesada'

        db.cur.execute(f"""
            SELECT sc.*,
                   cp_l.ciclo, cp_l.nombre_curso, cp_l.creditos,
                   cp_l.codigo AS codigo_local, cp_l.prerrequisito,
                   cp_e.nombre_curso AS nombre_externo,
                   cp_e.codigo AS codigo_externo
            FROM solicitud_cursos sc
            JOIN cursos_plan cp_l ON sc.curso_local_id = cp_l.id
            LEFT JOIN cursos_plan cp_e ON sc.curso_externo_id = cp_e.id
            WHERE sc.solicitud_id = %s
            ORDER BY {_ORDEN_CICLO}
        """, (solicitud_id,))
        todos = db.cur.fetchall()

        s['convalidados']    = [c for c in todos if c['estado'] == 'convalidado']
        s['examenes']        = [c for c in todos if c['estado'] == 'examen_suficiencia']
        s['no_convalidados'] = [c for c in todos if c['estado'] == 'pendiente']

        s['total_creditos_conv'] = sum(c['creditos'] for c in s['convalidados'])
        s['total_creditos_exam'] = sum(c['creditos'] for c in s['examenes'])
        s['total_creditos_no']   = sum(c['creditos'] for c in s['no_convalidados'])
        s['costo_credito'] = s['costo_credito'] if s['costo_credito'] is not None else 60
        s['costo_examen']  = s['costo_examen']  if s['costo_examen']  is not None else 130
        costo_cred = float(s['costo_credito'])
        costo_exam = float(s['costo_examen'])
        s['subtotal_conv']       = s['total_creditos_conv'] * costo_cred
        s['subtotal_exam']       = len(s['examenes']) * costo_exam
        s['total_costo']         = s['subtotal_conv'] + s['subtotal_exam']

        return s

def get_planes_por_tipo():
    cache = get_cache()
    if cache:
        data = cache.get('planes_por_tipo')
        if data:
            return data
    planes = fetch_all("""
        SELECT p.id, p.nombre_plan, p.tipo_plan, p.periodo_academico,
               COUNT(c.id) AS total_cursos, COALESCE(SUM(c.creditos),0) AS total_creditos
        FROM planes_estudio p
        LEFT JOIN cursos_plan c ON c.plan_id = p.id
        GROUP BY p.id ORDER BY p.nombre_plan, p.periodo_academico
    """)
    
    grupos = {}
    for p in planes:
        n = p['nombre_plan']
        if n not in grupos:
            grupos[n] = {'nombre': n, 'tipo': p['tipo_plan'], 'periodos': []}
        grupos[n]['periodos'].append({
            'id': p['id'], 'periodo': p['periodo_academico'],
            'total_cursos': p['total_cursos'], 'total_creditos': p['total_creditos']
        })
    
    data = {
        'locales': [g for g in grupos.values() if g['tipo'] == 'local'],
        'externos': [g for g in grupos.values() if g['tipo'] == 'externo']
    }
    if cache:
        cache.set('planes_por_tipo', data, timeout=900)
    return data

def get_cursos_plan(plan_id):
    cache = get_cache()
    key = f'cursos_plan_{plan_id}'
    if cache:
        data = cache.get(key)
        if data:
            return data
    data = fetch_all(f"""
        SELECT id, ciclo, codigo, nombre_curso, creditos, prerrequisito
        FROM cursos_plan WHERE plan_id=%s
        ORDER BY {_ORDEN_CICLO_PLAN}, nombre_curso
    """, (plan_id,))
    if cache:
        cache.set(key, data, timeout=900)
    return data

def verificar_duplicado(postulante_id, excluir_id=None):
    sql = "SELECT s.id, s.codigo FROM solicitudes s WHERE s.postulante_id=%s"
    params = [postulante_id]
    if excluir_id:
        sql += " AND s.id != %s"
        params.append(excluir_id)
    return fetch_one(sql, params)

def buscar_postulante(query):
    if len(query) < 2:
        return []
    like = f'%{query}%'
    return fetch_all("""
        SELECT id, codigo, apellidos_nombres, dni, programa, sexo,
               modalidad_estudios, modalidad_admision, semestre_academico,
               turno, asesora, correo, celular, institucion_procedencia
        FROM postulantes
        WHERE apellidos_nombres LIKE %s OR dni LIKE %s OR codigo LIKE %s OR programa LIKE %s
        LIMIT 10
    """, (like, like, like, like))
