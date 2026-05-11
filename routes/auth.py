# routes/auth.py
from flask import Blueprint, render_template, request, redirect, url_for, flash, session
from db.conexion import get_connection
from routes.logger import registrar
import bcrypt

bp_auth = Blueprint('auth', __name__)

def hash_password(password: str) -> str:
    return bcrypt.hashpw(password.encode('utf-8'), bcrypt.gensalt()).decode('utf-8')

def verify_password(password: str, hashed: str) -> bool:
    if hashed.startswith('$2'):
        return bcrypt.checkpw(password.encode('utf-8'), hashed.encode('utf-8'))
    return False

def _cargar_modulos(usuario_id, rol):
    """Carga los módulos del usuario en sesión. Admin tiene todos."""
    if rol == 'admin':
        session['modulos'] = '__all__'
        return
    conn = get_connection(); cur = conn.cursor(dictionary=True)
    cur.execute("""
        SELECT m.clave FROM usuario_modulos um
        JOIN modulos m ON um.modulo_id = m.id
        WHERE um.usuario_id = %s AND m.activo
    """, (usuario_id,))
    session['modulos'] = [r['clave'] for r in cur.fetchall()]
    cur.close(); conn.close()


def tiene_modulo(clave):
    """Verifica si el usuario actual tiene acceso al módulo. Admin siempre sí."""
    if session.get('usuario_rol') == 'admin':
        return True
    modulos = session.get('modulos', [])
    return modulos == '__all__' or clave in modulos


def login_requerido(f):
    from functools import wraps
    @wraps(f)
    def decorated(*args, **kwargs):
        if not session.get('usuario_id'):
            return redirect(url_for('auth.login'))
        return f(*args, **kwargs)
    return decorated


def modulo_requerido(clave):
    """
    Decorador que verifica acceso a un módulo específico.
    Admin siempre pasa. Usuario estándar necesita tener el módulo asignado.
    Uso: @modulo_requerido('postulantes')
    """
    def decorator(f):
        from functools import wraps
        @wraps(f)
        def decorated(*args, **kwargs):
            if not session.get('usuario_id'):
                return redirect(url_for('auth.login'))
            if not tiene_modulo(clave):
                flash(f'No tienes acceso al módulo «{clave}».', 'danger')
                return redirect(url_for('dashboard.index'))
            return f(*args, **kwargs)
        return decorated
    return decorator


def admin_requerido(f):
    from functools import wraps
    @wraps(f)
    def decorated(*args, **kwargs):
        if not session.get('usuario_id'):
            return redirect(url_for('auth.login'))
        if session.get('usuario_rol') != 'admin':
            flash('Acceso restringido a administradores.', 'danger')
            return redirect(url_for('dashboard.index'))
        return f(*args, **kwargs)
    return decorated


@bp_auth.route('/login', methods=['GET', 'POST'])
def login():
    if session.get('usuario_id'):
        return redirect(url_for('dashboard.index'))

    if request.method == 'POST':
        dni  = request.form.get('dni', '').strip()
        pwd  = request.form.get('contrasena', '').strip()

        if not dni or not pwd:
            flash('Ingresa usuario y contraseña.', 'warning')
            return render_template('auth/login.html')

        conn = get_connection(); cur = conn.cursor(dictionary=True)
        cur.execute("SELECT * FROM usuarios WHERE dni=%s AND estado='activo'", (dni,))
        usuario = cur.fetchone()
        cur.close(); conn.close()

        if not usuario or not verify_password(pwd, usuario['contrasena']):
            flash('Credenciales incorrectas.', 'danger')
            return render_template('auth/login.html')

        # Guardar sesión
        session['usuario_id']     = usuario['id']
        session['usuario_dni']    = usuario['dni']
        session['usuario_nombre'] = usuario['nombre_completo'] or usuario['dni']
        session['usuario_rol']    = usuario['rol']
        session['primer_acceso']  = bool(usuario['primer_acceso'])
        _cargar_modulos(usuario['id'], usuario['rol'])

        registrar('login', 'auth', f'Login exitoso: {usuario["dni"]}')
        if usuario['primer_acceso']:
            return redirect(url_for('auth.cambiar_contrasena'))

        if usuario['rol'] == 'admin':
            return redirect(url_for('dashboard.index'))
        else:
            return redirect(url_for('dashboard.seleccionar_facultad'))

    return render_template('auth/login.html')


@bp_auth.route('/cambiar-contrasena', methods=['GET', 'POST'])
def cambiar_contrasena():
    if not session.get('usuario_id'):
        return redirect(url_for('auth.login'))

    if request.method == 'POST':
        nueva  = request.form.get('nueva', '').strip()
        confirma = request.form.get('confirma', '').strip()

        if len(nueva) < 4:
            flash('La contraseña debe tener al menos 4 caracteres.', 'warning')
            return render_template('auth/cambiar_contrasena.html')
        if nueva != confirma:
            flash('Las contraseñas no coinciden.', 'danger')
            return render_template('auth/cambiar_contrasena.html')

        conn = get_connection(); cur = conn.cursor()
        cur.execute("""
            UPDATE usuarios SET contrasena=%s, primer_acceso=FALSE
            WHERE id=%s
        """, (hash_password(nueva), session['usuario_id']))
        conn.commit(); cur.close(); conn.close()

        session['primer_acceso'] = False
        flash('Contraseña actualizada correctamente.', 'success')

        if session.get('usuario_rol') == 'admin':
            return redirect(url_for('dashboard.index'))
        return redirect(url_for('dashboard.seleccionar_facultad'))

    return render_template('auth/cambiar_contrasena.html')


@bp_auth.route('/logout')
def logout():
    registrar('logout', 'auth', f'Logout: {session.get("usuario_dni","—")}')
    session.clear()
    return redirect(url_for('auth.login'))


@bp_auth.route('/ping', methods=['POST'])
def ping():
    """Extiende el tiempo de sesión."""
    if session.get('usuario_id'):
        session.modified = True
        return {'ok': True}
    return {'ok': False}, 401