# routes/reportes.py
from flask import Blueprint, render_template, request, jsonify, session, send_file, Response, stream_with_context
from db.conexion import get_connection
from db.cache import preview_cache
from routes.auth import login_requerido
from routes.generar_word import generar_preview_images, generar_pdf
import io
import zipfile
import json

bp_rep = Blueprint('reportes', __name__)

MESES_ES = {
    1: 'Enero', 2: 'Febrero', 3: 'Marzo', 4: 'Abril',
    5: 'Mayo', 6: 'Junio', 7: 'Julio', 8: 'Agosto',
    9: 'Septiembre', 10: 'Octubre', 11: 'Noviembre', 12: 'Diciembre'
}

GRUPOS_DISPONIBLES = {
    'facultad': 'Facultad',
    'programa': 'Programa de estudios',
    'turno': 'Turno',
    'modalidad_estudios': 'Modalidad estudios',
    'modalidad_admision': 'Modalidad admisión',
    'estado_solicitud': 'Estado solicitud',
    'carrera': 'Carrera',
    'semestre': 'Semestre académico',
    'ies_origen': 'Institución origen',
    'asesora': 'Asesora',
    'mes': 'Mes de emisión',
}


def _get_opciones_agrupacion():
    return GRUPOS_DISPONIBLES


@bp_rep.route('/')
@login_requerido
def index():
    opciones_grupo = _get_opciones_agrupacion()
    return render_template('reportes/index.html', 
                         opciones_grupo=opciones_grupo,
                         grupos_disponibles=list(GRUPOS_DISPONIBLES.keys()))


@bp_rep.route('/buscar')
@login_requerido
def buscar():
    """
    Busca solicitudes con optimización N+1 eliminada.
    Usa subquery para obtener datos de cursos en una sola consulta.
    """
    try:
        grupo_por = request.args.get('grupo_por', '')
        buscar_txt = request.args.get('buscar', '').strip()

        conn = get_connection()
        cur = conn.cursor(dictionary=True)

        # Subquery optimizada para datos de cursos (elimina N+1 queries)
        cursos_subquery = """
            (SELECT
                sc.solicitud_id,
                COALESCE(SUM(cp.creditos), 0) AS total_creditos_conv,
                COUNT(CASE WHEN sc.estado = 'examen_suficiencia' THEN 1 END) AS total_examenes
            FROM solicitud_cursos sc
            LEFT JOIN cursos_plan cp ON sc.curso_local_id = cp.id
            GROUP BY sc.solicitud_id)
        """

        sql = f"""
            SELECT
                s.id AS solicitud_id,
                s.codigo AS solicitud_codigo,
                s.estado AS solicitud_estado,
                s.fecha_emision,
                s.fecha_registro,
                COALESCE(p.id, 0) AS postulante_id,
                COALESCE(p.codigo, '') AS postulante_codigo,
                COALESCE(p.apellidos_nombres, 'Sin nombre') AS nombre,
                COALESCE(p.dni, '') AS dni,
                COALESCE(p.programa, 'No especificado') AS programa,
                COALESCE(p.modalidad_estudios, 'No especificado') AS modalidad_estudios,
                COALESCE(p.turno, 'No especificado') AS turno,
                COALESCE(p.semestre_academico, 'No especificado') AS semestre,
                COALESCE(p.asesora, 'No especificado') AS asesora,
                COALESCE(f.nombre, p.facultad, 'No especificado') AS facultad,
                COALESCE(p.modalidad_admision, 'No especificado') AS modalidad_admision,
                COALESCE(pe.nombre_plan, 'No especificada') AS ies_origen,
                s.costo_credito,
                s.costo_examen,
                COALESCE(cs.total_creditos_conv, 0) AS total_creditos_conv,
                COALESCE(cs.total_examenes, 0) AS total_examenes
            FROM solicitudes s
            LEFT JOIN postulantes p ON s.postulante_id = p.id
            LEFT JOIN planes_estudio pe ON s.plan_externo_id = pe.id
            LEFT JOIN carreras c ON s.carrera_id = c.id
            LEFT JOIN facultades f ON c.facultad_id = f.id
            LEFT JOIN {cursos_subquery} cs ON s.id = cs.solicitud_id
            WHERE 1=1
        """

        params = []

        if buscar_txt:
            sql += """ AND (
                p.codigo LIKE %s OR p.dni LIKE %s OR p.apellidos_nombres LIKE %s
                OR p.programa LIKE %s OR p.facultad LIKE %s OR s.codigo LIKE %s
            )"""
            like = f'%{buscar_txt}%'
            params.extend([like, like, like, like, like, like])

        sql += " ORDER BY s.fecha_registro DESC"

        cur.execute(sql, params)
        resultados = cur.fetchall()

        # Calcular costo total (ya no requiere queries adicionales)
        for r in resultados:
            total_cred = float(r['total_creditos_conv'] or 0)
            total_exam = int(r['total_examenes'] or 0)
            costo_cred = float(r['costo_credito'] or 0)
            costo_exam = float(r['costo_examen'] or 0)
            r['total_costo'] = (total_cred * costo_cred) + (total_exam * costo_exam)
        
        if grupo_por and grupo_por in GRUPOS_DISPONIBLES:
            grupos = {}
            for r in resultados:
                if grupo_por == 'mes':
                    if r['fecha_emision']:
                        fecha = r['fecha_emision']
                        mes_nombre = MESES_ES.get(fecha.month, fecha.strftime('%B'))
                        clave = f"{fecha.year}-{fecha.month:02d}: {mes_nombre}"
                    else:
                        clave = 'Sin fecha'
                elif grupo_por == 'estado_solicitud':
                    clave = r.get('solicitud_estado', 'No especificado')
                elif grupo_por == 'carrera':
                    clave = r.get('programa', 'No especificado')
                else:
                    clave = r.get(grupo_por, 'No especificado') or 'No especificado'
                if clave not in grupos:
                    grupos[clave] = []
                grupos[clave].append(r)
        else:
            grupos = {'Todos': resultados}
        
        cur.close()
        conn.close()
        
        return jsonify({
            'ok': True,
            'total': len(resultados),
            'grupos': {k: len(v) for k, v in grupos.items()},
            'resultados': grupos,
            'grupo_por': grupo_por,
            'grupo_nombre': GRUPOS_DISPONIBLES.get(grupo_por, 'Sin agrupar')
        })
    except Exception as e:
        try:
            cur.close()
            conn.close()
        except:
            pass
        return jsonify({
            'ok': False,
            'error': str(e)
        }), 500


@bp_rep.route('/descargar-uno', methods=['POST'])
@login_requerido
def descargar_uno():
    """Descarga un solo PDF usando la función existente."""
    try:
        data = request.get_json()
        sol_id = data.get('solicitud_id')
        
        if not sol_id:
            return jsonify({'ok': False, 'error': 'ID requerido'}), 400
        
        buffer_pdf, _ = generar_pdf(int(sol_id))
        buffer_pdf.seek(0)
        
        conn = get_connection()
        cur = conn.cursor(dictionary=True)
        cur.execute("""
            SELECT s.codigo AS solicitud_codigo, p.apellidos_nombres, p.dni, p.programa
            FROM solicitudes s
            LEFT JOIN postulantes p ON s.postulante_id = p.id
            WHERE s.id = %s
        """, (sol_id,))
        row = cur.fetchone()
        cur.close()
        conn.close()
        
        if row:
            nombre = (row['apellidos_nombres'] or 'SinNombre').replace(' ', '_')
            dni = row['dni'] or ''
            codigo = (row['solicitud_codigo'] or str(sol_id)).replace(' ', '_')
            prog = (row['programa'] or 'SinPrograma')[:30].replace(' ', '_').replace('/', '-')
            nombre_archivo = f"CONV_{nombre}_{dni}_{codigo}_{prog}.pdf"
        else:
            nombre_archivo = f"CONVALIDACION_{sol_id}.pdf"
        
        return send_file(
            buffer_pdf,
            mimetype='application/pdf',
            as_attachment=True,
            download_name=nombre_archivo
        )
    except Exception as e:
        return jsonify({'ok': False, 'error': str(e)}), 500


@bp_rep.route('/preview-generar/<int:id>')
def preview_generar(id):
    """Genera preview usando la función existente con cache."""
    def generar():
        try:
            paginas = generar_preview_images(id)
            yield f"data: {json.dumps({'pct': 100, 'msg': 'PDF listo', 'paginas': len(paginas)})}\n\n"
        except Exception as e:
            yield f"data: {json.dumps({'error': str(e)})}\n\n"
    
    return Response(stream_with_context(generar()), mimetype='text/event-stream',
                   headers={'Cache-Control': 'no-cache', 'X-Accel-Buffering': 'no'})


@bp_rep.route('/preview-pagina/<int:id>/<int:pagina>')
def preview_pagina(id, pagina):
    """Retorna página del cache o genera imagen."""
    cached = preview_cache.get(id)
    if cached is None:
        generar_preview_images(id)
        cached = preview_cache.get(id)
        if cached is None:
            return Response('Cache vacío', status=404)
    
    paginas = cached
    if pagina < 0 or pagina >= len(paginas):
        return Response('Página no encontrada', status=404)
    
    return Response(paginas[pagina], mimetype='image/png')


@bp_rep.route('/descargar', methods=['POST'])
@login_requerido
def descargar():
    """Descarga múltiples PDFs en ZIP usando la función existente."""
    try:
        data = request.get_json()
        solicitudes = data.get('solicitudes', [])
        nombre_grupo = str(data.get('nombre_grupo', 'Reporte'))[:40].replace(' ', '_')
        
        if not solicitudes:
            return jsonify({'ok': False, 'error': 'No hay solicitudes'}), 400
        
        buffer_zip = io.BytesIO()
        descargados = 0
        
        with zipfile.ZipFile(buffer_zip, 'w', zipfile.ZIP_DEFLATED) as zf:
            for item in solicitudes:
                if isinstance(item, dict):
                    sol_id = item.get('solicitud_id')
                    nombre = item.get('nombre', '')
                    dni = item.get('dni', '')
                    codigo = item.get('solicitud_codigo', '')
                    prog = (item.get('programa', '') or 'SinProg')[:20].replace(' ', '_').replace('/', '-')
                else:
                    sol_id = item
                    nombre, dni, codigo, prog = '', '', '', 'SOL'
                
                if not sol_id:
                    continue
                    
                try:
                    buffer_pdf, _ = generar_pdf(int(sol_id))
                    buffer_pdf.seek(0)
                    
                    if nombre and dni and codigo:
                        nom_limpio = nombre.replace(' ', '_')
                        nombre_archivo = f"CONV_{nom_limpio}_{dni}_{codigo}_{prog}.pdf"
                    else:
                        nombre_archivo = f"SOL-{sol_id:04d}.pdf"
                    
                    zf.writestr(nombre_archivo, buffer_pdf.read())
                    descargados += 1
                except:
                    pass
            
            if descargados == 0:
                return jsonify({'ok': False, 'error': 'No se pudieron generar PDFs'}), 400
        
        buffer_zip.seek(0)
        
        return send_file(
            buffer_zip,
            mimetype='application/zip',
            as_attachment=True,
            download_name=f'{nombre_grupo}_{descargados}docs.zip'
        )
    except Exception as e:
        return jsonify({'ok': False, 'error': str(e)}), 500


@bp_rep.route('/descargar-todos', methods=['POST'])
@login_requerido
def descargar_todos():
    """Descarga todos los grupos en un solo ZIP."""
    try:
        data = request.get_json()
        grupos_data = data.get('grupos', {})
        
        if not grupos_data:
            return jsonify({'ok': False, 'error': 'No hay grupos'}), 400
        
        buffer_zip = io.BytesIO()
        total_docs = 0
        
        with zipfile.ZipFile(buffer_zip, 'w', zipfile.ZIP_DEFLATED) as zf:
            for grupo_nombre, solicitudes in grupos_data.items():
                if not solicitudes:
                    continue
                
                sol_ids = [s['solicitud_id'] for s in solicitudes if s.get('solicitud_id')]
                cant = len(sol_ids)
                
                if cant == 0:
                    continue
                
                prefijo = str(grupo_nombre)[:30].replace(' ', '_').replace('/', '-').replace('\\', '-').replace(':', '-')
                
                for sol_id in sol_ids:
                    try:
                        buffer_pdf, _ = generar_pdf(int(sol_id))
                        buffer_pdf.seek(0)
                        nombre_archivo = f"{prefijo}/SOL-{sol_id:04d}.pdf"
                        zf.writestr(nombre_archivo, buffer_pdf.read())
                        total_docs += 1
                    except:
                        pass
            
            if total_docs == 0:
                return jsonify({'ok': False, 'error': 'No se pudieron generar PDFs'}), 400
        
        buffer_zip.seek(0)
        
        return send_file(
            buffer_zip,
            mimetype='application/zip',
            as_attachment=True,
            download_name='Reportes_Convalidados.zip'
        )
    except Exception as e:
        return jsonify({'ok': False, 'error': str(e)}), 500
