# routes/uploads.py
"""
Módulo para subir y gestionar archivos (fotos, documentos)
"""
import os
import uuid
from flask import Blueprint, request, jsonify, current_app
from werkzeug.utils import secure_filename
from routes.auth import modulo_requerido
from db.conexion import get_connection

bp_upload = Blueprint('uploads', __name__)

ALLOWED_EXTENSIONS = {'png', 'jpg', 'jpeg', 'gif', 'webp', 'pdf', 'doc', 'docx', 'xls', 'xlsx'}

def allowed_file(filename):
    return '.' in filename and filename.rsplit('.', 1)[1].lower() in ALLOWED_EXTENSIONS

def get_upload_folder():
    return os.path.join(current_app.root_path, 'static', 'uploads')

@bp_upload.route('/api/upload', methods=['POST'])
@modulo_requerido('solicitudes')
def upload_file():
    """Sube un archivo y retorna la ruta"""
    if 'file' not in request.files:
        return jsonify({'ok': False, 'error': 'No se encontro archivo'}), 400
    
    file = request.files['file']
    if file.filename == '':
        return jsonify({'ok': False, 'error': 'No se selecciono archivo'}), 400
    
    if not allowed_file(file.filename):
        return jsonify({'ok': False, 'error': 'Tipo de archivo no permitido'}), 400
    
    try:
        ext = file.filename.rsplit('.', 1)[1].lower()
        filename = f"{uuid.uuid4().hex}.{ext}"
        filepath = os.path.join(get_upload_folder(), filename)
        file.save(filepath)
        
        return jsonify({
            'ok': True,
            'filename': filename,
            'url': f"/uploads/{filename}",
            'size': os.path.getsize(filepath)
        })
    except Exception as e:
        return jsonify({'ok': False, 'error': str(e)}), 500

@bp_upload.route('/api/upload-checklist', methods=['POST'])
@modulo_requerido('solicitudes')
def upload_checklist():
    """Sube archivo y lo registra en checklist_documentos"""
    postulante_id = request.form.get('postulante_id')
    tipo_doc = request.form.get('tipo_doc', 'documento')
    detalle = request.form.get('detalle', '')
    
    if not postulante_id:
        return jsonify({'ok': False, 'error': 'Postulante requerido'}), 400
    
    if 'file' not in request.files:
        return jsonify({'ok': False, 'error': 'No se encontro archivo'}), 400
    
    file = request.files['file']
    if file.filename == '':
        return jsonify({'ok': False, 'error': 'No se selecciono archivo'}), 400
    
    if not allowed_file(file.filename):
        return jsonify({'ok': False, 'error': 'Tipo de archivo no permitido'}), 400
    
    try:
        ext = file.filename.rsplit('.', 1)[1].lower()
        filename = f"post_{postulante_id}_{uuid.uuid4().hex}.{ext}"
        filepath = os.path.join(get_upload_folder(), filename)
        file.save(filepath)
        
        conn = get_connection()
        cur = conn.cursor()
        cur.execute("""
            INSERT INTO checklist_documentos 
            (postulante_id, documento, tipo_doc, detalle, entregado, fecha_entrega)
            VALUES (%s, %s, %s, %s, 1, CURRENT_DATE)
        """, (postulante_id, filename, tipo_doc, detalle))
        conn.commit()
        doc_id = cur.lastrowid
        cur.close()
        conn.close()
        
        return jsonify({
            'ok': True,
            'doc_id': doc_id,
            'filename': filename,
            'url': f"/uploads/{filename}"
        })
    except Exception as e:
        return jsonify({'ok': False, 'error': str(e)}), 500

@bp_upload.route('/api/checklist/<int:postulante_id>')
@modulo_requerido('solicitudes')
def get_checklist(postulante_id):
    """Obtiene los documentos del checklist de un postulante"""
    conn = get_connection()
    cur = conn.cursor(dictionary=True)
    cur.execute("""
        SELECT id, documento, tipo_doc, detalle, entregado, observacion, fecha_entrega
        FROM checklist_documentos
        WHERE postulante_id = %s
        ORDER BY fecha_entrega DESC, id DESC
    """, (postulante_id,))
    docs = cur.fetchall()
    cur.close()
    conn.close()
    
    for doc in docs:
        if doc.get('documento'):
            doc['url'] = f"/uploads/{doc['documento']}"
            doc['es_imagen'] = doc['documento'].lower().split('.')[-1] in {'png', 'jpg', 'jpeg', 'gif', 'webp'}
        else:
            doc['url'] = None
            doc['es_imagen'] = False
    
    return jsonify({'ok': True, 'documentos': docs})

@bp_upload.route('/api/checklist/<int:doc_id>', methods=['DELETE'])
@modulo_requerido('solicitudes')
def delete_checklist_doc(doc_id):
    """Elimina un documento del checklist"""
    conn = get_connection()
    cur = conn.cursor(dictionary=True)
    
    cur.execute("SELECT documento FROM checklist_documentos WHERE id = %s", (doc_id,))
    doc = cur.fetchone()
    
    if not doc:
        cur.close()
        conn.close()
        return jsonify({'ok': False, 'error': 'Documento no encontrado'}), 404
    
    if doc.get('documento'):
        filepath = os.path.join(get_upload_folder(), doc['documento'])
        if os.path.exists(filepath):
            os.remove(filepath)
    
    cur.execute("DELETE FROM checklist_documentos WHERE id = %s", (doc_id,))
    conn.commit()
    cur.close()
    conn.close()
    
    return jsonify({'ok': True})

@bp_upload.route('/api/foto-postulante/<int:postulante_id>', methods=['POST'])
@modulo_requerido('solicitudes')
def upload_foto_postulante(postulante_id):
    """Sube foto de perfil del postulante"""
    if 'file' not in request.files:
        return jsonify({'ok': False, 'error': 'No se encontro archivo'}), 400
    
    file = request.files['file']
    if file.filename == '':
        return jsonify({'ok': False, 'error': 'No se selecciono archivo'}), 400
    
    ext = file.filename.rsplit('.', 1)[1].lower() if '.' in file.filename else 'jpg'
    if ext not in {'png', 'jpg', 'jpeg', 'gif', 'webp'}:
        return jsonify({'ok': False, 'error': 'Solo imagenes permitidas'}), 400
    
    try:
        filename = f"foto_{postulante_id}.{ext}"
        filepath = os.path.join(get_upload_folder(), filename)
        file.save(filepath)
        
        conn = get_connection()
        cur = conn.cursor()
        cur.execute("UPDATE postulantes SET foto = %s WHERE id = %s", (filename, postulante_id))
        conn.commit()
        cur.close()
        conn.close()
        
        return jsonify({
            'ok': True,
            'filename': filename,
            'url': f"/uploads/{filename}"
        })
    except Exception as e:
        return jsonify({'ok': False, 'error': str(e)}), 500
