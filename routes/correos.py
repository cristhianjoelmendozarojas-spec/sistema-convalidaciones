# routes/correos.py
"""
Módulo de envío de correo SMTP.
- Producción (Render): usa Brevo como relay SMTP con las credenciales
  BREVO_SMTP_LOGIN y BREVO_SMTP_PASSWORD en variables de entorno.
  El campo 'From' se respeta — Brevo hace el relay sin cambiar el remitente.
- Local (desarrollo): SMTP directo con las credenciales guardadas en BD.
"""

import os
import smtplib
import ssl
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
from email.mime.base import MIMEBase
from email import encoders
from db.conexion import get_connection

# ============================================================
# CONFIGURACIÓN BREVO
# ============================================================
BREVO_HOST = "smtp-relay.brevo.com"
BREVO_PUERTO = 2525
BREVO_LOGIN = os.getenv("BREVO_SMTP_LOGIN", "ab1c77001@smtp-brevo.com")
BREVO_PASSWORD = os.getenv("BREVO_SMTP_PASSWORD", "")


# ============================================================
# CONFIGURACIÓN DE BD
# ============================================================


def get_config_correo(usuario_id=None):
    """Obtiene la configuración de correo activa del usuario"""
    from flask import session

    if usuario_id is None:
        usuario_id = session.get("usuario_id")

    es_admin = session.get("usuario_rol") == "admin"

    conn = get_connection()
    cur = conn.cursor(dictionary=True)

    cur.execute(
        """
        SELECT correo_remitente, contrasena, nombre_remitente, smtp_host, smtp_puerto, ssl_habilitado
        FROM config_correo WHERE activo AND usuario_id = %s AND correo_remitente != ''
        LIMIT 1
    """,
        (usuario_id,),
    )
    config = cur.fetchone()

    if not config and not es_admin:
        cur.execute("""
            SELECT correo_remitente, contrasena, nombre_remitente, smtp_host, smtp_puerto, ssl_habilitado
            FROM config_correo WHERE activo AND correo_remitente != '' AND usuario_id = 1
            LIMIT 1
        """)
        config = cur.fetchone()

    cur.close()
    conn.close()
    return config


def get_config_correo_por_id(config_id):
    """Obtiene una configuración de correo específica por su ID"""
    conn = get_connection()
    cur = conn.cursor(dictionary=True)
    cur.execute(
        """
        SELECT cc.*, u.nombre_completo as nombre_remitente
        FROM config_correo cc
        LEFT JOIN usuarios u ON cc.usuario_id = u.id
        WHERE cc.id = %s
        LIMIT 1
    """,
        (config_id,),
    )
    config = cur.fetchone()
    cur.close()
    conn.close()
    return config


def detectar_servidor(correo):
    """Detecta el servidor SMTP según el dominio (para referencia en admin)"""
    dominio = correo.lower().split("@")[1] if "@" in correo else ""

    servidores = {
        "gmail.com": {
            "host": "smtp.gmail.com",
            "puerto": 2525,
            "ssl": True,
            "tipo": "gmail",
        },
        "outlook.com": {
            "host": "smtp-mail.outlook.com",
            "puerto": 2525,
            "ssl": False,
            "tipo": "microsoft",
        },
        "hotmail.com": {
            "host": "smtp-mail.outlook.com",
            "puerto": 2525,
            "ssl": False,
            "tipo": "microsoft",
        },
        "live.com": {
            "host": "smtp-mail.outlook.com",
            "puerto": 2525,
            "ssl": False,
            "tipo": "microsoft",
        },
        "office365.com": {
            "host": "smtp.office365.com",
            "puerto": 2525,
            "ssl": False,
            "tipo": "microsoft",
        },
        "yahoo.com": {
            "host": "smtp.mail.yahoo.com",
            "puerto": 2525,
            "ssl": True,
            "tipo": "yahoo",
        },
        "icloud.com": {
            "host": "smtp.mail.me.com",
            "puerto": 2525,
            "ssl": True,
            "tipo": "icloud",
        },
        "autonomadeica.edu.pe": {
            "host": "smtp.office365.com",
            "puerto": 2525,
            "ssl": False,
            "tipo": "microsoft",
        },
    }

    if dominio in servidores:
        return servidores[dominio]
    if dominio.endswith(".edu.pe"):
        return {
            "host": "smtp.office365.com",
            "puerto": 2525,
            "ssl": False,
            "tipo": "microsoft",
            "es_edu": True,
        }
    return None


# ============================================================
# CONSTRUCCIÓN DEL MENSAJE
# ============================================================


def _construir_mensaje(
    remitente_nombre, correo_remitente, destinatario, asunto, cuerpo_html, adjuntos=None
):
    msg = MIMEMultipart("mixed")
    msg["From"] = f"{remitente_nombre} <{correo_remitente}>"
    msg["To"] = destinatario
    msg["Subject"] = asunto
    msg.attach(MIMEText(cuerpo_html, "html", "utf-8"))

    if adjuntos:
        for ruta, nombre in adjuntos:
            with open(ruta, "rb") as f:
                part = MIMEBase("application", "octet-stream")
                part.set_payload(f.read())
            encoders.encode_base64(part)
            part.add_header("Content-Disposition", f'attachment; filename="{nombre}"')
            msg.attach(part)

    return msg


# ============================================================
# ENVÍO VIA BREVO RELAY (producción)
# ============================================================


def _enviar_brevo(msg, correo_remitente, destinatario):
    """
    Usa Brevo como relay SMTP. Las credenciales son de Brevo,
    pero el From del mensaje respeta el correo configurado en BD.
    """
    if not BREVO_PASSWORD:
        return {
            "ok": False,
            "error": "BREVO_SMTP_PASSWORD no está configurada en las variables de entorno de Render.",
        }

    # Incluir al remitente como BCC para que aparezca en su bandeja de entrada
    destinatarios = [destinatario, correo_remitente]

    try:
        context = ssl.create_default_context()
        with smtplib.SMTP(BREVO_HOST, BREVO_PUERTO, timeout=30) as server:
            server.ehlo()
            server.starttls(context=context)
            server.ehlo()
            server.login(BREVO_LOGIN, BREVO_PASSWORD)
            server.sendmail(correo_remitente, destinatarios, msg.as_string())
        return {"ok": True}

    except smtplib.SMTPAuthenticationError:
        return {
            "ok": False,
            "error": "Error de autenticación con Brevo. Verifica BREVO_SMTP_PASSWORD en Render.",
        }
    except smtplib.SMTPConnectError:
        return {
            "ok": False,
            "error": f"No se pudo conectar a {BREVO_HOST}:{BREVO_PUERTO}.",
        }
    except TimeoutError:
        return {"ok": False, "error": "Tiempo de espera agotado conectando a Brevo."}
    except Exception as e:
        return {"ok": False, "error": f"Error SMTP Brevo: {str(e)}"}


# ============================================================
# ENVÍO VIA SMTP DIRECTO (desarrollo local)
# ============================================================


def _enviar_smtp_directo(msg, correo_remitente, destinatario, config):
    """SMTP directo con credenciales del usuario — solo para desarrollo local."""
    smtp_cfg = detectar_servidor(correo_remitente)
    if not smtp_cfg:
        dominio = correo_remitente.split("@")[1] if "@" in correo_remitente else ""
        return {"ok": False, "error": f'Dominio "{dominio}" no reconocido para SMTP.'}

    smtp_host = smtp_cfg["host"]
    smtp_puerto = smtp_cfg["puerto"]

    # Incluir al remitente como BCC para que aparezca en su bandeja de entrada
    destinatarios = [destinatario, correo_remitente]

    try:
        context = ssl.create_default_context()
        if smtp_puerto == 465:
            with smtplib.SMTP_SSL(smtp_host, 465, context=context) as server:
                server.login(correo_remitente, config["contrasena"])
                server.sendmail(correo_remitente, destinatarios, msg.as_string())
        else:
            with smtplib.SMTP(smtp_host, smtp_puerto, timeout=30) as server:
                server.ehlo()
                server.starttls(context=context)
                server.ehlo()
                server.login(correo_remitente, config["contrasena"])
                server.sendmail(correo_remitente, destinatarios, msg.as_string())
        return {"ok": True}

    except smtplib.SMTPAuthenticationError:
        return {
            "ok": False,
            "error": "Error de autenticación. Para Gmail usa contraseña de aplicación (16 caracteres).",
        }
    except smtplib.SMTPConnectError:
        return {
            "ok": False,
            "error": f"No se pudo conectar a {smtp_host}:{smtp_puerto}.",
        }
    except TimeoutError:
        return {
            "ok": False,
            "error": "Tiempo de espera agotado conectando al servidor SMTP.",
        }
    except Exception as e:
        return {"ok": False, "error": f"Error SMTP: {str(e)}"}


# ============================================================
# FUNCIÓN PRINCIPAL
# ============================================================


def enviar_correo(
    destinatario, asunto, cuerpo_html, adjuntos=None, usuario_id=None, config_id=None
):
    """
    Envía un correo electrónico.

    - Si BREVO_SMTP_PASSWORD está en entorno → relay via Brevo (producción)
    - Si no → SMTP directo con credenciales de BD (desarrollo local)

    El remitente siempre es el correo configurado en BD por el usuario.
    Si se proporciona config_id, se usa esa configuración específica.
    """
    from flask import session

    if config_id:
        config = get_config_correo_por_id(config_id)
    else:
        if usuario_id is None:
            usuario_id = session.get("usuario_id")
        config = get_config_correo(usuario_id)

    if not config or not config.get("correo_remitente"):
        return {
            "ok": False,
            "error": "No hay configuración de correo activa. Ve a Admin > Correo y configura tu cuenta.",
        }

    correo_remitente = config["correo_remitente"]
    nombre_remitente = config.get("nombre_remitente", "Sistema UAI")

    msg = _construir_mensaje(
        nombre_remitente, correo_remitente, destinatario, asunto, cuerpo_html, adjuntos
    )

    # Producción: Brevo disponible
    if BREVO_PASSWORD:
        return _enviar_brevo(msg, correo_remitente, destinatario)

    # Local: SMTP directo
    if not config.get("contrasena"):
        return {
            "ok": False,
            "error": "La contraseña del correo no está configurada. "
            'Para Gmail usa una "Contraseña de aplicación" de 16 caracteres. '
            "En producción (Render) agrega BREVO_SMTP_PASSWORD.",
        }

    return _enviar_smtp_directo(msg, correo_remitente, destinatario, config)


# ============================================================
# PLANTILLAS Y UTILIDADES
# ============================================================


def get_plantillas():
    """Obtiene las plantillas de correo activas"""
    conn = get_connection()
    cur = conn.cursor(dictionary=True)
    cur.execute(
        "SELECT * FROM plantillas_correo WHERE activo ORDER BY fecha_creacion DESC"
    )
    plantillas = cur.fetchall()
    cur.close()
    conn.close()
    return plantillas


def renderizar_plantilla(plantilla, datos):
    """Reemplaza las variables @campo o {{campo}} en la plantilla con los datos"""
    cuerpo = plantilla["cuerpo"]
    asunto = plantilla["asunto"]

    variables = {
        "@codigo": datos.get("codigo", ""),
        "{{codigo}}": datos.get("codigo", ""),
        "@nombre": datos.get("nombre", ""),
        "{{nombre}}": datos.get("nombre", ""),
        "@dni": datos.get("dni", ""),
        "{{dni}}": datos.get("dni", ""),
        "@programa": datos.get("programa", ""),
        "{{programa}}": datos.get("programa", ""),
        "@modalidad": datos.get("modalidad", ""),
        "{{modalidad}}": datos.get("modalidad", ""),
        "@ies_origen": datos.get("ies_origen", ""),
        "{{ies_origen}}": datos.get("ies_origen", ""),
        "@fecha": datos.get("fecha", ""),
        "{{fecha}}": datos.get("fecha", ""),
        "@total_costo": datos.get("total_costo", ""),
        "{{total_costo}}": datos.get("total_costo", ""),
        "@correo": datos.get("correo", ""),
        "{{correo}}": datos.get("correo", ""),
        "@celular": datos.get("celular", ""),
        "{{celular}}": datos.get("celular", ""),
    }

    for var, valor in variables.items():
        cuerpo = cuerpo.replace(var, str(valor) if valor else "-")
        asunto = asunto.replace(var, str(valor) if valor else "-")

    return asunto, cuerpo


def get_estado_correo():
    """Verifica si el correo está configurado"""
    if BREVO_PASSWORD:
        config = get_config_correo()
        correo = (
            config.get("correo_remitente", "no configurado")
            if config
            else "no configurado"
        )
        return {
            "configurado": True,
            "proveedor": "Brevo Relay",
            "correo": correo,
            "mensaje": f"Enviando via Brevo relay desde {correo}",
        }

    config = get_config_correo()
    if not config:
        return {"configurado": False, "mensaje": "No hay configuración"}
    if not config.get("correo_remitente") or not config.get("contrasena"):
        return {"configurado": False, "mensaje": "Correo o contraseña vacíos"}

    return {
        "configurado": True,
        "proveedor": "SMTP directo",
        "correo": config["correo_remitente"],
        "nombre": config.get("nombre_remitente", ""),
        "servidor_detectado": detectar_servidor(config["correo_remitente"]),
    }
