# routes/csrf.py
"""
Protección CSRF simple para Flask.
Genera y valida tokens en formularios POST.
"""
import secrets
from functools import wraps
from flask import session, request, jsonify

CSRF_TOKEN_LENGTH = 32

def generate_csrf_token():
    if 'csrf_token' not in session:
        session['csrf_token'] = secrets.token_hex(CSRF_TOKEN_LENGTH)
    return session['csrf_token']

def validate_csrf_token(token):
    return 'csrf_token' in session and secrets.compare_digest(session['csrf_token'], token)

def csrf_protected(f):
    @wraps(f)
    def decorated(*args, **kwargs):
        if request.method in ('POST', 'PUT', 'DELETE', 'PATCH'):
            token = request.form.get('csrf_token') or request.headers.get('X-CSRF-Token', '')
            if not token or not validate_csrf_token(token):
                return jsonify({'ok': False, 'error': 'Token CSRF inválido'}), 403
        return f(*args, **kwargs)
    return decorated

def csrf_token():
    return generate_csrf_token()
