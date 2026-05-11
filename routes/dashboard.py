# routes/dashboard.py
from flask import Blueprint, render_template, request, jsonify, session, redirect, url_for
from db.conexion import get_connection
from routes.auth import login_requerido, _cargar_modulos

bp_dash = Blueprint('dashboard', __name__)


def _get_metricas(mes=None, anio=None):
    conn = get_connection(); cur = conn.cursor(dictionary=True)

    filtro_sql = ""
    params = []
    if anio:
        filtro_sql += " AND EXTRACT(YEAR FROM s.fecha_registro) = %s"
        params.append(int(anio))
    if mes:
        filtro_sql += " AND EXTRACT(MONTH FROM s.fecha_registro) = %s"
        params.append(int(mes))

    # Totales emitidas y borradores en una sola consulta
    cur.execute(f"""
        SELECT estado, COUNT(*) AS total
        FROM solicitudes s WHERE 1=1{filtro_sql}
        GROUP BY estado
    """, params)
    estados = {r['estado']: r['total'] for r in cur.fetchall()}
    total_emitidas = estados.get('emitido', 0)
    total_borradores = estados.get('borrador', 0)
    total_solicitudes = total_emitidas + total_borradores

    # Total postulantes
    cur.execute("SELECT COUNT(*) AS total FROM postulantes")
    total_postulantes = cur.fetchone()['total']

    # Postulantes sin convalidación (usando LEFT JOIN + IS NULL, más eficiente)
    cur.execute("""
        SELECT COUNT(*) AS total FROM postulantes p
        LEFT JOIN solicitudes s ON s.postulante_id = p.id
        WHERE s.id IS NULL
    """)
    sin_convalidacion = cur.fetchone()['total']

    # Porcentaje avance
    pct_avance = round((total_solicitudes / total_postulantes * 100), 1) if total_postulantes else 0

    # Costo acumulado optimizado (usando subconsultas más simples)
    cur.execute(f"""
        SELECT COALESCE(SUM(
            COALESCE(sc_conv.total_cred, 0) * s.costo_credito
            + COALESCE(sc_exam.cantidad, 0) * s.costo_examen
        ), 0) AS total_costo
        FROM solicitudes s
        LEFT JOIN (
            SELECT solicitud_id, SUM(cp.creditos) AS total_cred
            FROM solicitud_cursos sc
            JOIN cursos_plan cp ON sc.curso_local_id = cp.id
            WHERE sc.estado = 'convalidado'
            GROUP BY solicitud_id
        ) sc_conv ON sc_conv.solicitud_id = s.id
        LEFT JOIN (
            SELECT solicitud_id, COUNT(*) AS cantidad
            FROM solicitud_cursos
            WHERE estado = 'examen_suficiencia'
            GROUP BY solicitud_id
        ) sc_exam ON sc_exam.solicitud_id = s.id
        WHERE s.estado = 'emitido'{filtro_sql}
    """, params)
    total_costo = float(cur.fetchone()['total_costo'])

    # Ultimas solicitudes (5)
    cur.execute("""
        SELECT s.id, s.codigo, s.estado, s.fecha_registro,
               COALESCE(p.apellidos_nombres,'—') AS nombre,
               COALESCE(p.programa,'—') AS programa
        FROM solicitudes s
        LEFT JOIN postulantes p ON s.postulante_id=p.id
        ORDER BY s.fecha_registro DESC LIMIT 6
    """)
    ultimas = cur.fetchall()

    # Por estado (para gráfico)
    cur.execute(f"""
        SELECT estado, COUNT(*) AS total
        FROM solicitudes s WHERE 1=1{filtro_sql}
        GROUP BY estado
    """, params)
    por_estado = {r['estado']: r['total'] for r in cur.fetchall()}
    por_estado['pendiente'] = sin_convalidacion

    # Solicitudes por mes (últimos 6 meses) para gráfico
    cur.execute("""
        SELECT TO_CHAR(fecha_registro,'YYYY-MM') AS mes, COUNT(*) AS total
        FROM solicitudes
        WHERE fecha_registro >= NOW() - INTERVAL '6 MONTHS'
        GROUP BY mes ORDER BY mes
    """)
    por_mes = cur.fetchall()

    cur.close(); conn.close()

    return {
        'total_emitidas':    total_emitidas,
        'total_borradores':  total_borradores,
        'total_solicitudes': total_solicitudes,
        'sin_convalidacion': sin_convalidacion,
        'total_postulantes': total_postulantes,
        'pct_avance':        pct_avance,
        'total_costo':       total_costo,
        'ultimas':           ultimas,
        'por_estado':        por_estado,
        'por_mes':           por_mes,
    }


@bp_dash.route('/')
@login_requerido
def index():
    mes  = request.args.get('mes')
    anio = request.args.get('anio')
    metricas = _get_metricas(mes, anio)
    from datetime import datetime
    anio_actual = datetime.now().year
    return render_template('dashboard/index.html',
                           metricas=metricas, mes=mes, anio=anio,
                           anio_actual=anio_actual)


@bp_dash.route('/api/metricas')
@login_requerido
def api_metricas():
    mes  = request.args.get('mes')
    anio = request.args.get('anio')
    return jsonify(_get_metricas(mes, anio))


@bp_dash.route('/seleccionar-facultad')
@login_requerido
def seleccionar_facultad():
    conn = get_connection(); cur = conn.cursor(dictionary=True)
    cur.execute("""
        SELECT f.*, COUNT(c.id) AS total_carreras
        FROM facultades f
        LEFT JOIN carreras c ON c.facultad_id=f.id AND c.estado='activo'
        WHERE f.estado='activo'
        GROUP BY f.id ORDER BY f.nombre
    """)
    facultades = cur.fetchall()
    cur.close(); conn.close()
    return render_template('dashboard/seleccionar_facultad.html', facultades=facultades)


@bp_dash.route('/seleccionar-carrera/<int:facultad_id>')
@login_requerido
def seleccionar_carrera(facultad_id):
    conn = get_connection(); cur = conn.cursor(dictionary=True)
    cur.execute("SELECT * FROM facultades WHERE id=%s AND estado='activo'", (facultad_id,))
    facultad = cur.fetchone()
    if not facultad:
        return redirect(url_for('dashboard.seleccionar_facultad'))
    cur.execute("""
        SELECT c.*, f.nombre AS facultad_nombre
        FROM carreras c
        JOIN facultades f ON c.facultad_id = f.id
        WHERE c.facultad_id=%s AND c.estado='activo'
        ORDER BY c.nombre, c.periodo
    """, (facultad_id,))
    carreras = cur.fetchall()
    cur.close(); conn.close()
    from collections import OrderedDict
    grupos = OrderedDict()
    for c in carreras:
        nom = c['nombre']
        if nom not in grupos:
            grupos[nom] = {
                'nombre': nom,
                'periodos': [],
                'facultad_nombre': c.get('facultad_nombre','')
            }
        grupos[nom]['periodos'].append({
            'id': c['id'],
            'periodo': c.get('periodo',''),
            'codigo': c.get('codigo',''),
            'costo_convalidacion': float(c['costo_convalidacion']),
            'costo_examen': float(c['costo_examen'])
        })
    return render_template('dashboard/seleccionar_carrera.html',
                           facultad=facultad, carreras=list(grupos.values()))


@bp_dash.route('/iniciar-convalidacion/<int:carrera_id>')
@login_requerido
def iniciar_convalidacion(carrera_id):
    conn = get_connection(); cur = conn.cursor(dictionary=True)
    cur.execute("""
        SELECT c.*, f.nombre AS facultad_nombre
        FROM carreras c
        JOIN facultades f ON c.facultad_id = f.id
        WHERE c.id=%s
    """, (carrera_id,))
    carrera = cur.fetchone()
    cur.close(); conn.close()
    if carrera:
        session['carrera_id']          = carrera['id']
        session['carrera_nombre']      = carrera['nombre']
        session['facultad_nombre']     = carrera['facultad_nombre']
        session['costo_credito_carrera'] = float(carrera['costo_convalidacion'])
        session['costo_examen_carrera']  = float(carrera['costo_examen'])
    return redirect(url_for('solicitudes.nueva'))


@bp_dash.route('/recargar-modulos', methods=['POST'])
@login_requerido
def recargar_modulos():
    """Recarga los módulos del usuario desde la BD ( útil tras cambios en admin)."""
    usuario_id = session.get('usuario_id')
    rol = session.get('usuario_rol')
    if usuario_id:
        _cargar_modulos(usuario_id, rol)
        return jsonify({'ok': True, 'modulos': session.get('modulos', [])})
    return jsonify({'ok': False, 'error': 'No hay sesión'}), 401