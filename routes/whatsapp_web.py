# routes/whatsapp_web.py
"""
Módulo de WhatsApp Web
"""
import os
from urllib.parse import quote
from flask import Blueprint, jsonify, request

bp = Blueprint('whatsapp_web', __name__)

SESSION_FILE = 'whatsapp_connected.txt'

def is_connected():
    return os.path.exists(SESSION_FILE)

def set_connected(val):
    if val:
        with open(SESSION_FILE, 'w') as f:
            f.write('1')
    elif os.path.exists(SESSION_FILE):
        os.remove(SESSION_FILE)

@bp.route('/status')
def whatsapp_status():
    return jsonify({'ok': True, 'connected': is_connected()})

@bp.route('/connect')
def whatsapp_connect():
    try:
        import webbrowser
        webbrowser.open('https://web.whatsapp.com', new=2)
        set_connected(True)
        return jsonify({'ok': True, 'message': 'WhatsApp Web abierto'})
    except Exception as e:
        return jsonify({'ok': False, 'error': str(e)})

@bp.route('/check-connect', methods=['POST'])
def whatsapp_check_connect():
    set_connected(True)
    return jsonify({'ok': True, 'connected': True})

@bp.route('/disconnect', methods=['POST'])
def whatsapp_disconnect():
    set_connected(False)
    return jsonify({'ok': True})

@bp.route('/send', methods=['POST'])
def whatsapp_send():
    data = request.get_json() or {}
    telefono = data.get('telefono', '')
    mensaje = data.get('mensaje', '')
    
    if not telefono:
        return jsonify({'ok': False, 'error': 'Teléfono requerido'})
    
    telefono_limpio = ''.join(c for c in telefono if c.isdigit())
    
    if telefono_limpio.startswith('51'):
        pass
    elif telefono_limpio.startswith('9') and len(telefono_limpio) == 9:
        telefono_limpio = '51' + telefono_limpio
    else:
        telefono_limpio = '51' + telefono_limpio
    
    if len(telefono_limpio) < 10:
        return jsonify({'ok': False, 'error': f'Número demasiado corto: {telefono_limpio}'})
    
    mensaje_url = quote(mensaje.encode('utf-8'), safe='').replace('%5Cn', '%0A')
    
    return jsonify({
        'ok': True,
        'open_url': True,
        'phone': telefono_limpio,
        'url': f'https://wa.me/{telefono_limpio}?text={mensaje_url}'
    })


def enviar_mensaje_whatsapp(destinatario, mensaje):
    """
    Envía un mensaje de WhatsApp usando la API de WhatsApp Web.
    Retorna un dict con 'ok' y opcionalmente 'error'.
    """
    telefono_limpio = ''.join(c for c in destinatario if c.isdigit())
    
    if telefono_limpio.startswith('9') and len(telefono_limpio) == 9:
        telefono_formato = '+51' + telefono_limpio
    elif telefono_limpio.startswith('51') and len(telefono_limpio) >= 10:
        telefono_formato = '+51' + telefono_limpio[2:]
    else:
        telefono_formato = '+51' + telefono_limpio
    
    if len(telefono_formato) < 12:
        return {'ok': False, 'error': f'Número demasiado corto: {telefono_formato}'}
    
    mensaje_url = quote(mensaje.encode('utf-8'), safe='').replace('%5Cn', '%0A')
    
    return {
        'ok': True,
        'open_url': True,
        'phone': telefono_formato,
        'url': f'https://wa.me/{telefono_formato}?text={mensaje_url}'
    }
