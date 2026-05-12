# routes/correo.py
"""
Módulo de envío de correo
Soporta SMTP directo y SendGrid API (cloud-friendly)
"""
import smtplib
import ssl
import json
import base64
import urllib.request
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
from email.mime.base import MIMEBase
from email import encoders
from flask import jsonify
from db.conexion import get_connection

def get_config_correo(usuario_id=None):
    """Obtiene la configuración de correo activa del usuario"""
    from flask import session
    if usuario_id is None:
        usuario_id = session.get('usuario_id')
    
    es_admin = session.get('usuario_rol') == 'admin'
    
    conn = get_connection()
    cur = conn.cursor(dictionary=True)
    
    cur.execute("""
        SELECT correo_remitente, contrasena, nombre_remitente, smtp_host, smtp_puerto, ssl_habilitado, sendgrid_api_key
        FROM config_correo WHERE activo AND usuario_id = %s AND correo_remitente != ''
        LIMIT 1
    """, (usuario_id,))
    config = cur.fetchone()
    
    if not config and not es_admin:
        cur.execute("""
            SELECT correo_remitente, contrasena, nombre_remitente, smtp_host, smtp_puerto, ssl_habilitado, sendgrid_api_key
            FROM config_correo WHERE activo AND correo_remitente != '' AND usuario_id = 1
            LIMIT 1
        """)
        config = cur.fetchone()
    
    cur.close()
    conn.close()
    return config

def detectar_servidor(correo):
    """Detecta automáticamente el servidor SMTP según el dominio"""
    dominio = correo.lower().split('@')[1] if '@' in correo else ''
    
    servidores = {
        'gmail.com':    {'host': 'smtp.gmail.com', 'puerto': 587, 'ssl': True, 'tipo': 'gmail'},
        'outlook.com':  {'host': 'smtp-mail.outlook.com', 'puerto': 587, 'ssl': False, 'tipo': 'microsoft'},
        'hotmail.com':  {'host': 'smtp-mail.outlook.com', 'puerto': 587, 'ssl': False, 'tipo': 'microsoft'},
        'live.com':     {'host': 'smtp-mail.outlook.com', 'puerto': 587, 'ssl': False, 'tipo': 'microsoft'},
        'office365.com': {'host': 'smtp.office365.com', 'puerto': 587, 'ssl': False, 'tipo': 'microsoft'},
        'yahoo.com':    {'host': 'smtp.mail.yahoo.com', 'puerto': 587, 'ssl': True, 'tipo': 'yahoo'},
        'icloud.com':   {'host': 'smtp.mail.me.com', 'puerto': 587, 'ssl': True, 'tipo': 'icloud'},
        # Dominios educativos Perú
        'autonomadeica.edu.pe': {'host': 'smtp.office365.com', 'puerto': 587, 'ssl': False, 'tipo': 'microsoft'},
    }
    
    if dominio in servidores:
        return servidores[dominio]
    
    if dominio.endswith('.edu.pe'):
        return {
            'host': 'smtp.office365.com',
            'puerto': 587,
            'ssl': False,
            'tipo': 'microsoft',
            'es_edu': True
        }
    
    return None

def enviar_correo(destinatario, asunto, cuerpo_html, adjuntos=None, usuario_id=None):
    """
    Envía un correo electrónico
    
    Args:
        destinatario: Email del destinatario
        asunto: Asunto del correo
        cuerpo_html: Cuerpo del correo en HTML
        adjuntos: Lista de tuples (ruta_archivo, nombre_archivo)
        usuario_id: ID del usuario (usa sesión si no se especifica)
    
    Returns:
        dict con 'ok' y 'error' opcionales
    """
    from flask import session
    if usuario_id is None:
        usuario_id = session.get('usuario_id')
    
    config = get_config_correo(usuario_id)
    
    if not config or not config.get('correo_remitente'):
        return {
            'ok': False,
            'error': 'No hay configuracion de correo activa. Ve a Admin > Correo y configura tu cuenta de correo.'
        }
    
    correo_remitente = config['correo_remitente']
    nombre_remitente = config.get('nombre_remitente', 'Sistema')

    sendgrid_key = config.get('sendgrid_api_key')
    usar_sendgrid = bool(sendgrid_key and sendgrid_key.strip())

    if usar_sendgrid:
        return enviar_correo_sendgrid(
            destinatario, asunto, cuerpo_html,
            correo_remitente, nombre_remitente,
            sendgrid_key, adjuntos
        )

    if not config.get('contrasena'):
        return {
            'ok': False,
            'error': 'La contrasena del correo no esta configurada. '
                     'Para Gmail usa una "Contrasena de aplicacion" de 16 caracteres.'
        }

    smtp_config = detectar_servidor(correo_remitente)
    if not smtp_config:
        dominio = correo_remitente.lower().split('@')[1] if '@' in correo_remitente else ''
        return {
            'ok': False,
            'error': f'No se reconoce el dominio "{dominio}". '
                     'Dominios soportados automaticamente: Gmail, Outlook, Yahoo, iCloud, .edu.pe. '
                     'Para otros dominicos, configura manualmente el servidor SMTP en Admin > Correo.'
        }
    
    smtp_host = smtp_config['host']
    smtp_puerto = smtp_config['puerto']
    usar_ssl = smtp_config['ssl']
    
    try:
        msg = MIMEMultipart('alternative')
        msg['From'] = f'{nombre_remitente} <{correo_remitente}>'
        msg['To'] = destinatario
        msg['Subject'] = asunto
        
        html_part = MIMEText(cuerpo_html, 'html', 'utf-8')
        msg.attach(html_part)
        
        if adjuntos:
            for ruta, nombre in adjuntos:
                with open(ruta, 'rb') as f:
                    part = MIMEBase('application', 'octet-stream')
                    part.set_payload(f.read())
                encoders.encode_base64(part)
                part.add_header('Content-Disposition', f'attachment; filename={nombre}')
                msg.attach(part)
        
        if usar_ssl or smtp_puerto == 465:
            context = ssl.create_default_context()
            if smtp_puerto == 465:
                with smtplib.SMTP_SSL(smtp_host, 465, context=context) as server:
                    server.login(correo_remitente, config['contrasena'])
                    server.send_message(msg)
            else:
                with smtplib.SMTP(smtp_host, smtp_puerto, timeout=30) as server:
                    server.ehlo()
                    server.starttls(context=context)
                    server.ehlo()
                    server.login(correo_remitente, config['contrasena'])
                    server.send_message(msg)
        else:
            with smtplib.SMTP(smtp_host, smtp_puerto, timeout=30) as server:
                server.ehlo()
                server.starttls()
                server.login(correo_remitente, config['contrasena'])
                server.send_message(msg)
        
        return {'ok': True}
    
    except smtplib.SMTPAuthenticationError as e:
        error_msg = str(e).lower()
        
        if 'gmail' in correo_remitente.lower() or 'smtp.gmail.com' in smtp_host:
            if 'application-specific' in error_msg or 'app-specific' in error_msg or 'invalid credential' in error_msg:
                return {
                    'ok': False,
                    'error': 'Gmail requiere una "Contrasena de aplicacion", no tu contrasena normal. '
                             'Ve a tu cuenta Google > Seguridad > Contrasenas de aplicacion y genera una nueva.'
                }
            elif 'account' in error_msg and 'block' in error_msg:
                return {
                    'ok': False,
                    'error': 'Google bloquea el acceso. Ve a https://myaccount.google.com/security '
                             'y activa "Acceso a aplicaciones menos seguras" (o usa contrasena de aplicacion).'
                }
            else:
                return {
                    'ok': False,
                    'error': 'Error de autenticacion Gmail. Verifica: 1) Usar contrasena de aplicacion (16 caracteres), '
                             '2) Que la cuenta no tenga verificacion en 2 pasos restringida.'
                }
        
        elif 'outlook' in smtp_host or 'office365' in smtp_host:
            if 'authentication' in error_msg:
                return {
                    'ok': False,
                    'error': 'Error de autenticacion Outlook/Office 365. Verifica: '
                             '1) El correo y contrasena son correctos, '
                             '2) La cuenta no esta bloqueada, '
                             '3) Permitir acceso a aplicaciones menos seguras.'
                }
        
        else:
            return {
                'ok': False,
                'error': f'Error de autenticacion en {smtp_host}. Verifica tu correo y contrasena. '
                         f'Error: {str(e)[:100]}'
            }
    
    except smtplib.SMTPConnectError as e:
        return {
            'ok': False,
            'error': f'No se pudo conectar al servidor de correo ({smtp_host}:{smtp_puerto}). '
                     f'Verifica tu conexion a internet. Error: {str(e)[:80]}'
        }
    
    except smtplib.SMTPRecipientsRefused as e:
        return {'ok': False, 'error': f'Correo del destinatario rechazado: {str(e)}'}
    
    except smtplib.SMTPSenderRefused as e:
        return {'ok': False, 'error': f'Correo del remitente rechazado: {str(e)}'}
    
    except TimeoutError:
        return {
            'ok': False,
            'error': 'Tiempo de espera agotado. El servidor de correo no respondio. '
                     'Verifica tu conexion o intenta mas tarde.'
        }
    
    except smtplib.SMTPException as e:
        return {'ok': False, 'error': f'Error SMTP: {str(e)}'}
    
    except Exception as e:
        return {'ok': False, 'error': f'Error inesperado al enviar: {str(e)}'}


def enviar_correo_sendgrid(destinatario, asunto, cuerpo_html, correo_remitente, nombre_remitente, api_key, adjuntos=None):
    try:
        payload = {
            "personalizations": [{"to": [{"email": destinatario}]}],
            "from": {"email": correo_remitente, "name": nombre_remitente},
            "subject": asunto,
            "content": [{"type": "text/html", "value": cuerpo_html}],
        }

        if adjuntos:
            attachments = []
            for ruta, nombre in adjuntos:
                with open(ruta, 'rb') as f:
                    encoded = base64.b64encode(f.read()).decode('utf-8')
                attachments.append({
                    "filename": nombre,
                    "type": "application/octet-stream",
                    "content": encoded
                })
            payload["attachments"] = attachments

        data = json.dumps(payload).encode('utf-8')
        req = urllib.request.Request(
            "https://api.sendgrid.com/v3/mail/send",
            data=data,
            headers={
                "Authorization": f"Bearer {api_key}",
                "Content-Type": "application/json",
                "User-Agent": "Sistema-Convalidaciones/1.0"
            }
        )
        with urllib.request.urlopen(req, timeout=30) as resp:
            if resp.status in (200, 201, 202):
                return {'ok': True}
            return {'ok': False, 'error': f'SendGrid respondio con codigo {resp.status}'}

    except urllib.error.HTTPError as e:
        body = e.read().decode('utf-8', errors='replace')
        return {'ok': False, 'error': f'SendGrid error {e.code}: {body[:200]}'}
    except urllib.error.URLError as e:
        return {'ok': False, 'error': f'Error de conexion con SendGrid: {str(e.reason)[:100]}'}
    except Exception as e:
        return {'ok': False, 'error': f'Error inesperado al enviar via SendGrid: {str(e)}'}

def get_plantillas():
    """Obtiene las plantillas de correo activas"""
    conn = get_connection()
    cur = conn.cursor(dictionary=True)
    cur.execute("SELECT * FROM plantillas_correo WHERE activo ORDER BY fecha_creacion DESC")
    plantillas = cur.fetchall()
    cur.close()
    conn.close()
    return plantillas


def renderizar_plantilla(plantilla, datos):
    """Reemplaza las variables @campo o {{campo}} en la plantilla con los datos"""
    cuerpo = plantilla['cuerpo']
    asunto = plantilla['asunto']
    
    variables = {
        '@codigo': datos.get('codigo', ''),
        '{{codigo}}': datos.get('codigo', ''),
        '@nombre': datos.get('nombre', ''),
        '{{nombre}}': datos.get('nombre', ''),
        '@dni': datos.get('dni', ''),
        '{{dni}}': datos.get('dni', ''),
        '@programa': datos.get('programa', ''),
        '{{programa}}': datos.get('programa', ''),
        '@modalidad': datos.get('modalidad', ''),
        '{{modalidad}}': datos.get('modalidad', ''),
        '@ies_origen': datos.get('ies_origen', ''),
        '{{ies_origen}}': datos.get('ies_origen', ''),
        '@fecha': datos.get('fecha', ''),
        '{{fecha}}': datos.get('fecha', ''),
        '@total_costo': datos.get('total_costo', ''),
        '{{total_costo}}': datos.get('total_costo', ''),
        '@correo': datos.get('correo', ''),
        '{{correo}}': datos.get('correo', ''),
        '@celular': datos.get('celular', ''),
        '{{celular}}': datos.get('celular', ''),
    }
    
    for var, valor in variables.items():
        cuerpo = cuerpo.replace(var, str(valor) if valor else '-')
        asunto = asunto.replace(var, str(valor) if valor else '-')
    
    return asunto, cuerpo

def get_estado_correo():
    """Verifica si el correo está configurado y funciona"""
    config = get_config_correo()
    if not config:
        return {'configurado': False, 'mensaje': 'No hay configuración'}
    
    sendgrid_key = config.get('sendgrid_api_key')
    if sendgrid_key and sendgrid_key.strip():
        return {
            'configurado': True,
            'metodo': 'sendgrid',
            'correo': config['correo_remitente'],
            'nombre': config.get('nombre_remitente', ''),
            'servidor_detectado': None
        }
    
    if not config.get('contrasena'):
        return {'configurado': False, 'mensaje': 'Correo o contraseña vacíos'}
    
    return {
        'configurado': True,
        'metodo': 'smtp',
        'correo': config['correo_remitente'],
        'nombre': config.get('nombre_remitente', ''),
        'servidor_detectado': detectar_servidor(config['correo_remitente'])
    }
