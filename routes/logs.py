# routes/logs.py
from flask import Blueprint, render_template, request, session, jsonify
from db.conexion import get_connection
# login_requerido aplicado inline para evitar circular import
from functools import wraps
from flask import redirect, url_for

bp_logs = Blueprint('logs', __name__)


# ─────────────────────────────────────────────────────────────────
# HELPER — llamar desde cualquier ruta para registrar acción
# ─────────────────────────────────────────────────────────────────

def registrar(accion, modulo, descripcion, entidad_id=None):
    """
    Registra una acción en logs_sistema.
    Uso: from routes.logger import registrar
         registrar('crear', 'solicitudes', f'Solicitud {codigo} creada', nuevo_id)
    """
    try:
        conn = get_connection(); cur = conn.cursor()
        cur.execute("""
            INSERT INTO logs_sistema (usuario_id, usuario_dni, accion, modulo, descripcion, entidad_id, ip)
            VALUES (%s, %s, %s, %s, %s, %s, %s)
        """, (
            session.get('usuario_id'),
            session.get('usuario_dni', '—'),
            accion,
            modulo,
            descripcion[:500],
            entidad_id,
            request.remote_addr
        ))
        conn.commit()
    except Exception:
        pass   # Los logs nunca deben romper el flujo principal
    finally:
        try: cur.close(); conn.close()
        except: pass


# ─────────────────────────────────────────────────────────────────
# VISTA — Historial de acciones
# ─────────────────────────────────────────────────────────────────

@bp_logs.route('/historial')
def historial():
    if not session.get('usuario_id'):
        return redirect(url_for('auth.login'))
    modulo  = request.args.get('modulo', '')
    accion  = request.args.get('accion', '')
    usuario = request.args.get('usuario', '')
    limit   = int(request.args.get('limit', 100))

    conn = get_connection(); cur = conn.cursor(dictionary=True)

    # Si es usuario normal, solo ve sus propios logs
    es_admin = session.get('usuario_rol') == 'admin'
    filtros, params = [], []

    if not es_admin:
        filtros.append("l.usuario_id = %s")
        params.append(session.get('usuario_id'))

    if modulo:
        filtros.append("l.modulo = %s")
        params.append(modulo)
    if accion:
        filtros.append("l.accion = %s")
        params.append(accion)
    if usuario and es_admin:
        filtros.append("l.usuario_dni LIKE %s")
        params.append(f'%{usuario}%')

    where = ('WHERE ' + ' AND '.join(filtros)) if filtros else ''

    cur.execute(f"""
        SELECT l.*, u.nombre_completo
        FROM logs_sistema l
        LEFT JOIN usuarios u ON l.usuario_id = u.id
        {where}
        ORDER BY l.fecha DESC
        LIMIT %s
    """, params + [limit])
    logs = cur.fetchall()

    # Totales por módulo (para stats)
    cur.execute(f"""
        SELECT modulo, COUNT(*) AS total
        FROM logs_sistema l
        {where}
        GROUP BY modulo ORDER BY total DESC
    """, params)
    por_modulo = cur.fetchall()

    # Totales por acción
    cur.execute(f"""
        SELECT accion, COUNT(*) AS total
        FROM logs_sistema l
        {where}
        GROUP BY accion
    """, params)
    por_accion = {r['accion']: r['total'] for r in cur.fetchall()}

    cur.close(); conn.close()

    return render_template('logs/historial.html',
                           logs=logs,
                           por_modulo=por_modulo,
                           por_accion=por_accion,
                           es_admin=es_admin,
                           filtro_modulo=modulo,
                           filtro_accion=accion,
                           filtro_usuario=usuario,
                           limit=limit)


@bp_logs.route('/api/recientes')
def api_recientes():
    if not session.get('usuario_id'):
        return redirect(url_for('auth.login'))
    """API: últimas 10 acciones del usuario actual (para dashboard)"""
    conn = get_connection(); cur = conn.cursor(dictionary=True)
    cur.execute("""
        SELECT accion, modulo, descripcion, fecha
        FROM logs_sistema
        WHERE usuario_id = %s
        ORDER BY fecha DESC LIMIT 10
    """, (session.get('usuario_id'),))
    logs = cur.fetchall()
    cur.close(); conn.close()
    # Convert datetime to string for JSON
    for l in logs:
        l['fecha'] = l['fecha'].strftime('%d/%m/%Y %H:%M') if l['fecha'] else ''
    return jsonify(logs)