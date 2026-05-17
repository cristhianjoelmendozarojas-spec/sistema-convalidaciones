# routes/logger.py
# ─────────────────────────────────────────────────────────────────
# Helper de logs SIN importar auth.py — evita importación circular.
# auth.py  → logger.py  ✓
# logs.py  → logger.py  ✓
# Todos los demás módulos → logger.py  ✓
# ─────────────────────────────────────────────────────────────────
from flask import session, request
from db.conexion import get_connection


def registrar(accion, modulo, descripcion, entidad_id=None):
    """
    Registra una acción en logs_sistema.
    Nunca lanza excepción — los logs no deben romper el flujo principal.

    Uso:
        from routes.logger import registrar
        registrar('crear', 'solicitudes', f'Solicitud creada: {codigo}', nuevo_id)
    """
    try:
        conn = get_connection()
        cur = conn.cursor()
        cur.execute(
            """
            INSERT INTO logs_sistema
                (usuario_id, usuario_dni, accion, modulo, descripcion, entidad_id, ip)
            VALUES (%s, %s, %s, %s, %s, %s, %s)
        """,
            (
                session.get("usuario_id"),
                session.get("usuario_dni", "—"),
                accion,
                modulo,
                descripcion[:500],
                entidad_id,
                request.remote_addr,
            ),
        )
        conn.commit()
    except Exception:
        pass
    finally:
        try:
            cur.close()
            conn.close()
        except Exception:
            pass
