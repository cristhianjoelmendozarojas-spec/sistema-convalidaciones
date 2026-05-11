# app.py
import os
import sys

# Add current directory to path
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

import logging
from dotenv import load_dotenv
from flask import Flask, redirect, url_for, session, send_from_directory, render_template, jsonify, request, flash
from config import Config

load_dotenv()

app = Flask(__name__)
app.config.from_object(Config)

# ============================================================
# CACHE CONFIGURATION
# ============================================================
app.config['CACHE_TYPE'] = 'SimpleCache'
app.config['CACHE_DEFAULT_TIMEOUT'] = 300
from flask_caching import Cache
cache = Cache(app)

# ============================================================
# LOGGING CONFIGURATION
# ============================================================
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s [%(levelname)s] %(module)s: %(message)s',
    handlers=[
        logging.StreamHandler(),
        logging.FileHandler('app.log', encoding='utf-8')
    ]
)
logger = logging.getLogger(__name__)

# ============================================================
# UPLOAD CONFIGURATION
# ============================================================
UPLOAD_FOLDER = os.path.join(app.root_path, 'static', 'uploads')
os.makedirs(UPLOAD_FOLDER, exist_ok=True)
app.config['UPLOAD_FOLDER'] = UPLOAD_FOLDER
app.config['MAX_CONTENT_LENGTH'] = 500 * 1024 * 1024  # 500MB max

# Allowed extensions for uploads
ALLOWED_EXTENSIONS = {'pdf', 'png', 'jpg', 'jpeg', 'doc', 'docx', 'xls', 'xlsx'}

def allowed_file(filename):
    return '.' in filename and filename.rsplit('.', 1)[1].lower() in ALLOWED_EXTENSIONS

@app.route('/uploads/<path:filename>')
def uploaded_file(filename):
    return send_from_directory(app.config['UPLOAD_FOLDER'], filename)

# ============================================================
# GLOBAL ERROR HANDLERS
# ============================================================
@app.errorhandler(404)
def not_found_error(error):
    """Maneja errores 404 - Página no encontrada"""
    logger.warning(f'404 error: {request.url if request else "unknown"}')
    if request.path.startswith('/api/') or request.headers.get('X-Requested-With') == 'XMLHttpRequest':
        return jsonify({'error': 'Recurso no encontrado', 'ok': False}), 404
    return render_template('errors/404.html'), 404

@app.errorhandler(500)
def internal_error(error):
    """Maneja errores 500 - Error interno del servidor"""
    logger.error(f'500 error: {error}', exc_info=True)
    if request.path.startswith('/api/') or request.headers.get('X-Requested-With') == 'XMLHttpRequest':
        return jsonify({'error': 'Error interno del servidor', 'ok': False}), 500
    return render_template('errors/500.html'), 500

@app.errorhandler(403)
def forbidden_error(error):
    """Maneja errores 403 - Acceso denegado"""
    logger.warning(f'403 error: {request.url if request else "unknown"}')
    if request.path.startswith('/api/') or request.headers.get('X-Requested-With') == 'XMLHttpRequest':
        return jsonify({'error': 'Acceso denegado', 'ok': False}), 403
    return render_template('errors/403.html'), 403

@app.errorhandler(413)
def request_entity_too_large(error):
    """Maneja errores 413 - Archivo demasiado grande"""
    logger.warning(f'413 error: archivo excede tamaño máximo')
    if request.path.startswith('/api/') or request.headers.get('X-Requested-With') == 'XMLHttpRequest':
        return jsonify({'error': 'El archivo excede el tamaño máximo permitido (16MB)', 'ok': False}), 413
    flash('El archivo excede el tamaño máximo permitido (16MB)', 'danger')
    return redirect(request.referrer or url_for('dashboard.index'))

from routes.solicitudes import bp as solicitudes_bp
from routes.generar_word import bp_word
from routes.postulantes import bp_post
from routes.planes import bp_planes
from routes.auth import bp_auth
from routes.dashboard import bp_dash
from routes.admin import bp_admin
from routes.logs import bp_logs
from routes.csrf import csrf_token, validate_csrf_token
from routes.whatsapp_web import bp as whatsapp_web_bp
from routes.reportes import bp_rep
from routes.uploads import bp_upload
from routes.backup import bp_backup
from db.conexion import close_pool
import atexit
atexit.register(close_pool)

@app.context_processor
def inject_csrf():
    return dict(csrf_token=csrf_token)

@app.before_request
def global_csrf_check():
    if request.method in ('POST', 'PUT', 'DELETE', 'PATCH'):
        path = request.path
        if path in ('/ping',):
            return
        if path.startswith('/solicitudes/rechazar/'):
            return
        token = request.form.get('csrf_token') or request.headers.get('X-CSRF-Token', '')
        if not token or not validate_csrf_token(token):
            if request.headers.get('X-Requested-With') == 'XMLHttpRequest' or \
               request.headers.get('Accept') == 'application/json' or \
               request.content_type == 'application/json':
                return jsonify({'ok': False, 'error': 'Token CSRF inválido'}), 403
            flash('Token de seguridad inválido. Por favor intenta de nuevo.', 'danger')
            return redirect(request.referrer or url_for('dashboard.index'))

app.register_blueprint(solicitudes_bp, url_prefix='/solicitudes')
app.register_blueprint(bp_word)
app.register_blueprint(bp_post,    url_prefix='/postulantes')
app.register_blueprint(bp_planes,  url_prefix='/planes')
app.register_blueprint(bp_auth)
app.register_blueprint(bp_dash,  url_prefix='/dashboard')
app.register_blueprint(bp_admin, url_prefix='/admin')
app.register_blueprint(bp_logs,  url_prefix='')
app.register_blueprint(whatsapp_web_bp, url_prefix='/whatsapp')
app.register_blueprint(bp_rep, url_prefix='/reportes')
app.register_blueprint(bp_upload, url_prefix='/uploads')
app.register_blueprint(bp_backup)

@app.route('/')
def home():
    if session.get('usuario_id'):
        return redirect(url_for('dashboard.index'))
    return redirect(url_for('auth.login'))

# ============================================================
# PRODUCTION RUN
# ============================================================
if __name__ == '__main__':
    debug_mode = os.getenv('FLASK_DEBUG', 'true').lower() in ('true', '1', 'yes')
    app.run(
        debug=debug_mode,
        host=os.getenv('FLASK_HOST', '0.0.0.0'),
        port=int(os.getenv('FLASK_PORT', 5000))
    )
    