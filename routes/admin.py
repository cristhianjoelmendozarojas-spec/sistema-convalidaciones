# routes/admin.py
from flask import (
    Blueprint,
    render_template,
    request,
    redirect,
    url_for,
    flash,
    jsonify,
    session,
)
from db.conexion import get_connection
from routes.auth import admin_requerido, tiene_modulo, hash_password
from routes.logger import registrar

bp_admin = Blueprint("admin", __name__)


# ─────────────────────────────────────────────────────────────
# USUARIOS
# ─────────────────────────────────────────────────────────────


@bp_admin.route("/usuarios")
@admin_requerido
def usuarios():
    conn = get_connection()
    cur = conn.cursor(dictionary=True)
    cur.execute("SELECT * FROM usuarios ORDER BY fecha_creacion DESC")
    usuarios = cur.fetchall()
    cur.close()
    conn.close()
    return render_template("admin/usuarios.html", usuarios=usuarios)


@bp_admin.route("/usuarios/crear", methods=["POST"])
@admin_requerido
def crear_usuario():
    d = request.get_json()
    conn = get_connection()
    cur = conn.cursor()
    try:
        cur.execute(
            """
            INSERT INTO usuarios (dni, contrasena, nombre_completo, rol, estado, primer_acceso)
            VALUES (%s, %s, %s, %s, %s, TRUE)
        """,
            (
                d["dni"].strip(),
                hash_password(d["dni"].strip()),
                d.get("nombre_completo", "").strip(),
                d.get("rol", "usuario"),
                d.get("estado", "activo"),
            ),
        )
        conn.commit()
        registrar("crear", "usuarios", f"Usuario creado: {d['dni']}")
        return jsonify({"ok": True, "id": cur.lastrowid})
    except Exception as e:
        conn.rollback()
        return jsonify({"ok": False, "error": str(e)}), 400
    finally:
        cur.close()
        conn.close()


@bp_admin.route("/usuarios/editar/<int:uid>", methods=["POST"])
@admin_requerido
def editar_usuario(uid):
    d = request.get_json()
    conn = get_connection()
    cur = conn.cursor()
    try:
        cur.execute(
            """
            UPDATE usuarios SET nombre_completo=%s, rol=%s, estado=%s
            WHERE id=%s
        """,
            (
                d.get("nombre_completo", "").strip(),
                d.get("rol", "usuario"),
                d.get("estado", "activo"),
                uid,
            ),
        )
        conn.commit()
        registrar("editar", "usuarios", f"Usuario editado: id={uid}", uid)
        return jsonify({"ok": True})
    except Exception as e:
        conn.rollback()
        return jsonify({"ok": False, "error": str(e)}), 400
    finally:
        cur.close()
        conn.close()


@bp_admin.route("/usuarios/toggle/<int:uid>", methods=["POST"])
@admin_requerido
def toggle_usuario(uid):
    conn = get_connection()
    cur = conn.cursor(dictionary=True)
    try:
        cur.execute("SELECT estado FROM usuarios WHERE id=%s", (uid,))
        row = cur.fetchone()
        nuevo = "inactivo" if row["estado"] == "activo" else "activo"
        cur.execute("UPDATE usuarios SET estado=%s WHERE id=%s", (nuevo, uid))
        conn.commit()
        return jsonify({"ok": True, "estado": nuevo})
    except Exception as e:
        conn.rollback()
        return jsonify({"ok": False, "error": str(e)}), 400
    finally:
        cur.close()
        conn.close()


@bp_admin.route("/usuarios/reset/<int:uid>", methods=["POST"])
@admin_requerido
def reset_contrasena(uid):
    conn = get_connection()
    cur = conn.cursor(dictionary=True)
    try:
        cur.execute("SELECT dni FROM usuarios WHERE id=%s", (uid,))
        row = cur.fetchone()
        cur.execute(
            "UPDATE usuarios SET contrasena=%s, primer_acceso=TRUE WHERE id=%s",
            (hash_password(row["dni"]), uid),
        )
        conn.commit()
        return jsonify({"ok": True})
    except Exception as e:
        conn.rollback()
        return jsonify({"ok": False, "error": str(e)}), 400
    finally:
        cur.close()
        conn.close()


# ─────────────────────────────────────────────────────────────
# FACULTADES
# ─────────────────────────────────────────────────────────────


@bp_admin.route("/usuarios/eliminar/<int:uid>", methods=["POST"])
@admin_requerido
def eliminar_usuario(uid):
    conn = get_connection()
    cur = conn.cursor()
    try:
        cur.execute("DELETE FROM usuarios WHERE id=%s", (uid,))
        conn.commit()
        registrar("eliminar", "usuarios", f"Usuario eliminado: id={uid}", uid)
        return jsonify({"ok": True})
    except Exception as e:
        conn.rollback()
        return jsonify({"ok": False, "error": str(e)}), 400
    finally:
        cur.close()
        conn.close()


@bp_admin.route("/facultades")
@admin_requerido
def facultades():
    conn = get_connection()
    cur = conn.cursor(dictionary=True)
    cur.execute("""
        SELECT f.*, COUNT(c.id) AS total_carreras
        FROM facultades f
        LEFT JOIN carreras c ON c.facultad_id=f.id
        GROUP BY f.id ORDER BY f.nombre
    """)
    facultades = cur.fetchall()
    cur.close()
    conn.close()
    return render_template("admin/facultades.html", facultades=facultades)


@bp_admin.route("/facultades/crear", methods=["POST"])
@admin_requerido
def crear_facultad():
    d = request.get_json()
    conn = get_connection()
    cur = conn.cursor()
    try:
        cur.execute(
            """
            INSERT INTO facultades (nombre, codigo, descripcion, estado)
            VALUES (%s, %s, %s, %s)
        """,
            (
                d["nombre"].strip(),
                d.get("codigo", "").strip(),
                d.get("descripcion", "").strip(),
                d.get("estado", "activo"),
            ),
        )
        conn.commit()
        registrar("crear", "facultades", f"Facultad creada: {d['nombre']}")
        return jsonify({"ok": True, "id": cur.lastrowid})
    except Exception as e:
        conn.rollback()
        return jsonify({"ok": False, "error": str(e)}), 400
    finally:
        cur.close()
        conn.close()


@bp_admin.route("/facultades/editar/<int:fid>", methods=["POST"])
@admin_requerido
def editar_facultad(fid):
    d = request.get_json()
    conn = get_connection()
    cur = conn.cursor()
    try:
        cur.execute(
            """
            UPDATE facultades SET nombre=%s, codigo=%s, descripcion=%s, estado=%s
            WHERE id=%s
        """,
            (
                d["nombre"].strip(),
                d.get("codigo", "").strip(),
                d.get("descripcion", "").strip(),
                d.get("estado", "activo"),
                fid,
            ),
        )
        conn.commit()
        return jsonify({"ok": True})
    except Exception as e:
        conn.rollback()
        return jsonify({"ok": False, "error": str(e)}), 400
    finally:
        cur.close()
        conn.close()


@bp_admin.route("/facultades/eliminar/<int:fid>", methods=["POST"])
@admin_requerido
def eliminar_facultad(fid):
    conn = get_connection()
    cur = conn.cursor()
    try:
        cur.execute("DELETE FROM facultades WHERE id=%s", (fid,))
        conn.commit()
        return jsonify({"ok": True})
    except Exception as e:
        conn.rollback()
        return jsonify({"ok": False, "error": str(e)}), 400
    finally:
        cur.close()
        conn.close()


# ─────────────────────────────────────────────────────────────
# CARRERAS
# ─────────────────────────────────────────────────────────────


@bp_admin.route("/carreras")
@admin_requerido
def carreras():
    conn = get_connection()
    cur = conn.cursor(dictionary=True)
    cur.execute("""
        SELECT c.*, f.nombre AS facultad_nombre
        FROM carreras c
        JOIN facultades f ON c.facultad_id=f.id
        ORDER BY f.nombre, c.nombre
    """)
    carreras = cur.fetchall()
    # Para cada carrera, obtener sus periodos
    for c in carreras:
        cur.execute(
            """
            SELECT id, periodo, costo_convalidacion, costo_examen
            FROM carreras_periodos
            WHERE carrera_id=%s
            ORDER BY periodo DESC
        """,
            (c["id"],),
        )
        c["periodos"] = cur.fetchall()
    cur.execute(
        "SELECT id, nombre FROM facultades WHERE estado='activo' ORDER BY nombre"
    )
    facultades = cur.fetchall()
    cur.close()
    conn.close()
    return render_template(
        "admin/carreras.html", carreras=carreras, facultades=facultades
    )


@bp_admin.route("/carreras/crear", methods=["POST"])
@admin_requerido
def crear_carrera():
    d = request.get_json()
    conn = get_connection()
    cur = conn.cursor()
    try:
        cur.execute(
            """
            INSERT INTO carreras (facultad_id, nombre, codigo, estado)
            VALUES (%s, %s, %s, %s)
        """,
            (
                d["facultad_id"],
                d["nombre"].strip(),
                d.get("codigo", "").strip(),
                d.get("estado", "activo"),
            ),
        )
        conn.commit()
        nuevo_id = cur.lastrowid
        registrar("crear", "carreras", f"Carrera creada: {d['nombre']}")
        return jsonify({"ok": True, "id": nuevo_id})
    except Exception as e:
        conn.rollback()
        return jsonify({"ok": False, "error": str(e)}), 400
    finally:
        cur.close()
        conn.close()


@bp_admin.route("/carreras/editar/<int:cid>", methods=["POST"])
@admin_requerido
def editar_carrera(cid):
    d = request.get_json()
    conn = get_connection()
    cur = conn.cursor()
    try:
        cur.execute(
            """
            UPDATE carreras
            SET facultad_id=%s, nombre=%s, codigo=%s, estado=%s
            WHERE id=%s
        """,
            (
                d["facultad_id"],
                d["nombre"].strip(),
                d.get("codigo", "").strip(),
                d.get("estado", "activo"),
                cid,
            ),
        )
        conn.commit()
        return jsonify({"ok": True})
    except Exception as e:
        conn.rollback()
        return jsonify({"ok": False, "error": str(e)}), 400
    finally:
        cur.close()
        conn.close()


@bp_admin.route("/carreras/eliminar/<int:cid>", methods=["POST"])
@admin_requerido
def eliminar_carrera(cid):
    conn = get_connection()
    cur = conn.cursor()
    try:
        cur.execute("DELETE FROM carreras WHERE id=%s", (cid,))
        conn.commit()
        return jsonify({"ok": True})
    except Exception as e:
        conn.rollback()
        return jsonify({"ok": False, "error": str(e)}), 400
    finally:
        cur.close()
        conn.close()


# ── PERIODOS POR CARRERA ────────────────────────────────


@bp_admin.route("/carreras/periodos/<int:cid>")
@admin_requerido
def listar_periodos(cid):
    conn = get_connection()
    cur = conn.cursor(dictionary=True)
    cur.execute(
        """
        SELECT id, carrera_id, periodo, costo_convalidacion, costo_examen
        FROM carreras_periodos
        WHERE carrera_id=%s
        ORDER BY periodo DESC
    """,
        (cid,),
    )
    data = cur.fetchall()
    cur.close()
    conn.close()
    return jsonify(data)


@bp_admin.route("/carreras/periodos/crear", methods=["POST"])
@admin_requerido
def crear_periodo():
    d = request.get_json()
    conn = get_connection()
    cur = conn.cursor()
    try:
        cur.execute(
            """
            INSERT INTO carreras_periodos (carrera_id, periodo, costo_convalidacion, costo_examen)
            VALUES (%s, %s, %s, %s)
        """,
            (
                d["carrera_id"],
                d["periodo"].strip(),
                float(d.get("costo_convalidacion", 60)),
                float(d.get("costo_examen", 130)),
            ),
        )
        conn.commit()
        registrar(
            "crear",
            "carreras_periodos",
            f"Periodo {d['periodo']} agregado a carrera id={d['carrera_id']}",
        )
        return jsonify({"ok": True, "id": cur.lastrowid})
    except Exception as e:
        conn.rollback()
        return jsonify({"ok": False, "error": str(e)}), 400
    finally:
        cur.close()
        conn.close()


@bp_admin.route("/carreras/periodos/editar/<int:pid>", methods=["POST"])
@admin_requerido
def editar_periodo(pid):
    d = request.get_json()
    conn = get_connection()
    cur = conn.cursor()
    try:
        cur.execute(
            """
            UPDATE carreras_periodos
            SET periodo=%s, costo_convalidacion=%s, costo_examen=%s
            WHERE id=%s
        """,
            (
                d["periodo"].strip(),
                float(d.get("costo_convalidacion", 60)),
                float(d.get("costo_examen", 130)),
                pid,
            ),
        )
        conn.commit()
        return jsonify({"ok": True})
    except Exception as e:
        conn.rollback()
        return jsonify({"ok": False, "error": str(e)}), 400
    finally:
        cur.close()
        conn.close()


@bp_admin.route("/carreras/periodos/eliminar/<int:pid>", methods=["POST"])
@admin_requerido
def eliminar_periodo(pid):
    conn = get_connection()
    cur = conn.cursor()
    try:
        cur.execute("DELETE FROM carreras_periodos WHERE id=%s", (pid,))
        conn.commit()
        return jsonify({"ok": True})
    except Exception as e:
        conn.rollback()
        return jsonify({"ok": False, "error": str(e)}), 400
    finally:
        cur.close()
        conn.close()


@bp_admin.route("/api/facultades")
@admin_requerido
def api_facultades():
    conn = get_connection()
    cur = conn.cursor(dictionary=True)
    cur.execute(
        "SELECT id, nombre FROM facultades WHERE estado='activo' ORDER BY nombre"
    )
    data = cur.fetchall()
    cur.close()
    conn.close()
    return jsonify(data)


# ─────────────────────────────────────────────────────────────
# MÓDULOS DE USUARIO
# ─────────────────────────────────────────────────────────────


@bp_admin.route("/usuarios/modulos/<int:uid>")
@admin_requerido
def get_modulos_usuario(uid):
    """Devuelve los módulos asignados y disponibles para un usuario."""
    conn = get_connection()
    cur = conn.cursor(dictionary=True)

    # Todos los módulos activos
    cur.execute("SELECT * FROM modulos WHERE activo ORDER BY orden")
    todos = cur.fetchall()

    # Módulos ya asignados al usuario
    cur.execute(
        """
        SELECT m.clave FROM usuario_modulos um
        JOIN modulos m ON um.modulo_id = m.id
        WHERE um.usuario_id = %s
    """,
        (uid,),
    )
    asignados = {r["clave"] for r in cur.fetchall()}

    cur.close()
    conn.close()

    for m in todos:
        m["asignado"] = m["clave"] in asignados

    return jsonify({"ok": True, "modulos": todos})


@bp_admin.route("/usuarios/modulos/<int:uid>/guardar", methods=["POST"])
@admin_requerido
def guardar_modulos_usuario(uid):
    """Reemplaza los módulos asignados a un usuario."""
    from routes.logger import registrar

    data = request.get_json()
    claves = data.get("claves", [])  # lista de claves a asignar

    conn = get_connection()
    cur = conn.cursor()
    try:
        # Eliminar asignaciones actuales
        cur.execute("DELETE FROM usuario_modulos WHERE usuario_id=%s", (uid,))

        # Insertar nuevas
        if claves:
            cur.execute(
                """
                INSERT INTO usuario_modulos (usuario_id, modulo_id)
                SELECT %s, id FROM modulos WHERE clave IN ({})
            """.format(",".join(["%s"] * len(claves))),
                [uid] + claves,
            )

        conn.commit()
        registrar(
            "editar", "usuarios", f"Módulos actualizados para usuario id={uid}", uid
        )
        return jsonify({"ok": True})
    except Exception as e:
        conn.rollback()
        return jsonify({"ok": False, "error": str(e)}), 400
    finally:
        cur.close()
        conn.close()


@bp_admin.route("/modulos")
@admin_requerido
def listar_modulos():
    """Lista todos los módulos del sistema."""
    conn = get_connection()
    cur = conn.cursor(dictionary=True)
    cur.execute("""
        SELECT m.*, COUNT(um.id) AS total_usuarios
        FROM modulos m
        LEFT JOIN usuario_modulos um ON um.modulo_id = m.id
        GROUP BY m.id ORDER BY m.orden
    """)
    modulos = cur.fetchall()
    cur.close()
    conn.close()
    return render_template("admin/modulos.html", modulos=modulos)


@bp_admin.route("/modulos/crear", methods=["POST"])
@admin_requerido
def crear_modulo():
    d = request.get_json()
    conn = get_connection()
    cur = conn.cursor()
    try:
        cur.execute(
            """
            INSERT INTO modulos (clave, nombre, descripcion, icono, orden)
            VALUES (%s, %s, %s, %s, %s)
        """,
            (
                d["clave"].strip().lower(),
                d["nombre"].strip(),
                d.get("descripcion", "").strip(),
                d.get("icono", "📦"),
                int(d.get("orden", 99)),
            ),
        )
        conn.commit()
        return jsonify({"ok": True, "id": cur.lastrowid})
    except Exception as e:
        conn.rollback()
        return jsonify({"ok": False, "error": str(e)}), 400
    finally:
        cur.close()
        conn.close()


@bp_admin.route("/modulos/editar/<int:mid>", methods=["POST"])
@admin_requerido
def editar_modulo(mid):
    d = request.get_json()
    conn = get_connection()
    cur = conn.cursor()
    try:
        cur.execute(
            """
            UPDATE modulos SET nombre=%s, descripcion=%s, icono=%s, orden=%s, activo=%s
            WHERE id=%s
        """,
            (
                d["nombre"].strip(),
                d.get("descripcion", "").strip(),
                d.get("icono", "📦"),
                int(d.get("orden", 99)),
                bool(int(d.get("activo", 1))),
                mid,
            ),
        )
        conn.commit()
        return jsonify({"ok": True})
    except Exception as e:
        conn.rollback()
        return jsonify({"ok": False, "error": str(e)}), 400
    finally:
        cur.close()
        conn.close()


# ─────────────────────────────────────────────────────────────
# CONFIGURACIÓN DE CORREO DEL USUARIO
# ─────────────────────────────────────────────────────────────


@bp_admin.route("/correo")
def correo():
    if not tiene_modulo("correo"):
        flash("No tienes acceso a este módulo", "warning")
        return redirect(url_for("dashboard.index"))
    usuario_id = session.get("usuario_id")
    es_admin = session.get("usuario_rol") == "admin"
    conn = get_connection()
    cur = conn.cursor(dictionary=True)

    if es_admin:
        cur.execute("SELECT * FROM config_correo ORDER BY fecha_creacion DESC")
    else:
        cur.execute(
            """
            SELECT * FROM config_correo 
            WHERE usuario_id=%s 
            ORDER BY fecha_creacion DESC
        """,
            (usuario_id,),
        )
    configs = cur.fetchall()

    cur.execute("""
        SELECT * FROM plantillas_correo 
        WHERE activo 
        ORDER BY fecha_creacion DESC
    """)
    plantillas = cur.fetchall()

    cur.close()
    conn.close()
    return render_template("admin/correo.html", configs=configs, plantillas=plantillas)


@bp_admin.route("/correo/guardar", methods=["POST"])
def guardar_correo():
    if not tiene_modulo("correo"):
        return jsonify({"ok": False, "error": "No tienes acceso"}), 403

    from routes.correos import detectar_servidor

    usuario_id = session.get("usuario_id")
    correo = request.form.get("correo", "").strip()
    contrasena = request.form.get("contrasena", "").strip()
    nombre = (
        request.form.get("nombre_remitente", "").strip() or "Sistema Convalidaciones"
    )

    if not correo or "@" not in correo:
        flash("Ingresa un correo válido", "danger")
        return redirect(url_for("admin.correo"))

    smtp_info = detectar_servidor(correo)
    if smtp_info:
        smtp_host = smtp_info["host"]
        smtp_puerto = smtp_info["puerto"]
        ssl_habilitado = True if smtp_info["ssl"] else False
    else:
        smtp_host = request.form.get("smtp_host", "smtp.gmail.com")
        smtp_puerto = int(request.form.get("smtp_puerto", 587))
        ssl_habilitado = request.form.get("ssl_habilitado", "1") == "1"

    conn = get_connection()
    cur = conn.cursor()
    try:
        cur.execute(
            """
            INSERT INTO config_correo 
            (usuario_id, correo_remitente, contrasena, nombre_remitente, smtp_host, smtp_puerto, ssl_habilitado, activo)
            VALUES (%s, %s, %s, %s, %s, %s, %s, TRUE)
        """,
            (
                usuario_id,
                correo,
                contrasena,
                nombre,
                smtp_host,
                smtp_puerto,
                ssl_habilitado,
            ),
        )
        conn.commit()
        flash("Correo guardado correctamente", "success")
    except Exception as e:
        conn.rollback()
        flash(f"Error: {str(e)}", "danger")
    finally:
        cur.close()
        conn.close()

    return redirect(url_for("admin.correo"))


@bp_admin.route("/correo/eliminar/<int:id>", methods=["POST"])
def eliminar_correo(id):
    if not tiene_modulo("correo"):
        return jsonify({"ok": False, "error": "No tienes acceso"}), 403
    usuario_id = session.get("usuario_id")
    conn = get_connection()
    cur = conn.cursor()
    try:
        cur.execute(
            "DELETE FROM config_correo WHERE id=%s AND usuario_id=%s", (id, usuario_id)
        )
        conn.commit()
        return jsonify({"ok": True})
    except Exception as e:
        conn.rollback()
        return jsonify({"ok": False, "error": str(e)})
    finally:
        cur.close()
        conn.close()


@bp_admin.route("/correo/set-activo/<int:id>", methods=["POST"])
def set_correo_activo(id):
    if not tiene_modulo("correo"):
        return jsonify({"ok": False, "error": "No tienes acceso"}), 403
    usuario_id = session.get("usuario_id")
    conn = get_connection()
    cur = conn.cursor()
    try:
        cur.execute(
            "UPDATE config_correo SET activo=FALSE WHERE usuario_id=%s", (usuario_id,)
        )
        cur.execute(
            "UPDATE config_correo SET activo=TRUE WHERE id=%s AND usuario_id=%s",
            (id, usuario_id),
        )
        conn.commit()
        return jsonify({"ok": True})
    except Exception as e:
        conn.rollback()
        return jsonify({"ok": False, "error": str(e)})
    finally:
        cur.close()
        conn.close()


@bp_admin.route("/plantillas/guardar", methods=["POST"])
def guardar_plantilla():
    if not tiene_modulo("correo"):
        return jsonify({"ok": False, "error": "No tienes acceso"}), 403
    nombre = request.form.get("nombre", "").strip()
    asunto = request.form.get("asunto", "").strip()
    cuerpo = request.form.get("cuerpo", "").strip()

    if not nombre or not asunto or not cuerpo:
        return jsonify({"ok": False, "error": "Todos los campos son requeridos"})

    conn = get_connection()
    cur = conn.cursor()
    try:
        cur.execute(
            """
            INSERT INTO plantillas_correo (nombre, asunto, cuerpo, activo)
            VALUES (%s, %s, %s, TRUE)
        """,
            (nombre, asunto, cuerpo),
        )
        conn.commit()
        return jsonify({"ok": True, "id": cur.lastrowid})
    except Exception as e:
        conn.rollback()
        return jsonify({"ok": False, "error": str(e)})
    finally:
        cur.close()
        conn.close()


@bp_admin.route("/plantillas/eliminar/<int:id>", methods=["POST"])
def eliminar_plantilla(id):
    if not tiene_modulo("correo"):
        return jsonify({"ok": False, "error": "No tienes acceso"}), 403
    print(f"ELIMINAR PLANTILLA: id={id}")
    conn = get_connection()
    cur = conn.cursor()
    try:
        cur.execute("DELETE FROM plantillas_correo WHERE id=%s", (id,))
        conn.commit()
        print("Eliminado OK")
        return jsonify({"ok": True})
    except Exception as e:
        print(f"Error: {e}")
        conn.rollback()
        return jsonify({"ok": False, "error": str(e)})
    finally:
        cur.close()
        conn.close()


@bp_admin.route("/correo/probar", methods=["POST"])
def probar_correo():
    if not tiene_modulo("correo"):
        return jsonify({"ok": False, "error": "No tienes acceso"}), 403
    from routes.correos import enviar_correo

    destinatario = request.form.get("destinatario", "").strip()

    if not destinatario or "@" not in destinatario:
        return jsonify({"ok": False, "error": "Ingresa un correo válido de prueba"})

    cuerpo_html = """
    <html>
    <body style="font-family: Arial, sans-serif; color: #333;">
        <h2 style="color: #1F3864;">Prueba de configuración</h2>
        <p>Este es un correo de prueba desde el Sistema de Convalidaciones.</p>
        <p>Si recibiste este mensaje, la configuración de correo está correcta.</p>
        <hr>
        <p style="color: #666; font-size: 12px;">
            Sistema de Convalidaciones UAI
        </p>
    </body>
    </html>
    """

    resultado = enviar_correo(
        destinatario, "Prueba - Sistema de Convalidaciones", cuerpo_html
    )
    return jsonify(resultado)


@bp_admin.route("/correo/estado")
@admin_requerido
def estado_correo():
    if not tiene_modulo("correo"):
        return jsonify({"ok": False, "error": "No tienes acceso"}), 403
    from routes.correos import get_estado_correo

    return jsonify(get_estado_correo())


# AÑOS DECRETADOS
@bp_admin.route("/anios")
@admin_requerido
def anios():
    conn = get_connection()
    cur = conn.cursor(dictionary=True)
    cur.execute("SELECT * FROM anios_decretados ORDER BY anio DESC")
    anios = cur.fetchall()
    cur.close()
    conn.close()
    return render_template("admin/anios.html", anios=anios)


@bp_admin.route("/anios/crear", methods=["POST"])
@admin_requerido
def crear_anio():
    d = request.get_json()
    conn = get_connection()
    cur = conn.cursor()
    try:
        cur.execute(
            """
            INSERT INTO anios_decretados (anio, nombre, estado)
            VALUES (%s, %s, %s)
        """,
            (int(d["anio"]), d["nombre"].strip(), d.get("estado", "activo")),
        )
        conn.commit()
        registrar("crear", "anios_decretados", f"Año creado: {d['anio']}")
        return jsonify({"ok": True, "id": cur.lastrowid})
    except Exception as e:
        conn.rollback()
        return jsonify({"ok": False, "error": str(e)}), 400
    finally:
        cur.close()
        conn.close()


@bp_admin.route("/anios/editar/<int:aid>", methods=["POST"])
@admin_requerido
def editar_anio(aid):
    d = request.get_json()
    conn = get_connection()
    cur = conn.cursor()
    try:
        cur.execute(
            """
            UPDATE anios_decretados SET anio=%s, nombre=%s, estado=%s
            WHERE id=%s
        """,
            (int(d["anio"]), d["nombre"].strip(), d.get("estado", "activo"), aid),
        )
        conn.commit()
        registrar("editar", "anios_decretados", f"Año editado: id={aid}", aid)
        return jsonify({"ok": True})
    except Exception as e:
        conn.rollback()
        return jsonify({"ok": False, "error": str(e)}), 400
    finally:
        cur.close()
        conn.close()


@bp_admin.route("/anios/toggle/<int:aid>", methods=["POST"])
@admin_requerido
def toggle_anio(aid):
    conn = get_connection()
    cur = conn.cursor(dictionary=True)
    try:
        cur.execute("SELECT estado FROM anios_decretados WHERE id=%s", (aid,))
        row = cur.fetchone()
        nuevo = "inactivo" if row["estado"] == "activo" else "activo"
        cur.execute("UPDATE anios_decretados SET estado=%s WHERE id=%s", (nuevo, aid))
        conn.commit()
        return jsonify({"ok": True, "estado": nuevo})
    except Exception as e:
        conn.rollback()
        return jsonify({"ok": False, "error": str(e)}), 400
    finally:
        cur.close()
        conn.close()


@bp_admin.route("/anios/eliminar/<int:aid>", methods=["POST"])
@admin_requerido
def eliminar_anio(aid):
    conn = get_connection()
    cur = conn.cursor()
    try:
        cur.execute("DELETE FROM anios_decretados WHERE id=%s", (aid,))
        conn.commit()
        registrar("eliminar", "anios_decretados", f"Año eliminado: id={aid}", aid)
        return jsonify({"ok": True})
    except Exception as e:
        conn.rollback()
        return jsonify({"ok": False, "error": str(e)}), 400
    finally:
        cur.close()
        conn.close()


@bp_admin.route("/whatsapp")
def whatsapp():
    if not tiene_modulo("whatsapp"):
        flash("No tienes acceso a este módulo", "warning")
        return redirect(url_for("dashboard.index"))
    return render_template("admin/whatsapp.html")


@bp_admin.route("/optimizar-bd", methods=["POST"])
@admin_requerido
def optimizar_bd():
    """Ejecuta optimizar_bd.sql contra la base de datos activa."""
    import os
    import re

    ruta = os.path.join(
        os.path.dirname(os.path.abspath(__file__)), "..", "optimizar_bd.sql"
    )
    if not os.path.exists(ruta):
        return jsonify({"ok": False, "error": "optimizar_bd.sql no encontrado"})

    with open(ruta, "r", encoding="utf-8") as f:
        sql = f.read()

    # Limpiar comentarios y dividir en sentencias
    sql_limpio = re.sub(r"--.*?\n", "\n", sql)
    sentencias = [s.strip() for s in sql_limpio.split(";") if s.strip()]

    conn = get_connection()
    cur = conn.cursor()
    resultados = []
    errores = 0
    try:
        for i, stmt in enumerate(sentencias):
            try:
                cur.execute(stmt)
                conn.commit()
                resultados.append({"ok": True, "n": i + 1, "sql": stmt[:80]})
            except Exception as e:
                conn.rollback()
                # IF NOT EXISTS evita errores reales, pero algunos pueden fallar (ej. pg_trgm sin permisos)
                errores += 1
                resultados.append(
                    {"ok": False, "n": i + 1, "error": str(e)[:200], "sql": stmt[:80]}
                )

        # ANALYZE final
        try:
            cur.execute("ANALYZE")
            conn.commit()
        except Exception:
            pass

        registrar(
            "optimizar",
            "bd",
            f"Migración BD: {len(resultados)} stmts, {errores} errores",
        )
        return jsonify(
            {
                "ok": True,
                "total": len(resultados),
                "errores": errores,
                "resultados": resultados,
            }
        )
    except Exception as e:
        conn.rollback()
        return jsonify({"ok": False, "error": str(e)[:300]})
    finally:
        cur.close()
        conn.close()
