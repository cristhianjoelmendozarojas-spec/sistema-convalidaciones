# services/postulantes_service.py
"""
Servicios de lógica de negocio para postulantes.
Separa la lógica de las rutas para mejor mantenibilidad.
"""

from db.conexion import Database, fetch_one, fetch_all


def get_postulante_por_dni(dni):
    """Busca postulante por DNI."""
    return fetch_one(
        """
        SELECT id, codigo, apellidos_nombres, dni, programa, sexo,
               modalidad_estudios, modalidad_admision, semestre_academico,
               turno, asesora, correo, celular, institucion_procedencia
        FROM postulantes WHERE dni=%s LIMIT 1
    """,
        (dni,),
    )


def buscar_postulantes(query, limite=20):
    """Busca postulantes por texto."""
    if not query or len(query) < 2:
        return []
    like = f"%{query}%"
    return fetch_all(
        """
        SELECT id, codigo, apellidos_nombres, dni, programa, sexo,
               modalidad_estudios, modalidad_admision, semestre_academico,
               turno, asesora, correo, celular, institucion_procedencia
        FROM postulantes
        WHERE apellidos_nombres LIKE %s OR dni LIKE %s OR codigo LIKE %s OR programa LIKE %s
        ORDER BY apellidos_nombres
        LIMIT %s
    """,
        (like, like, like, like, limite),
    )


def get_postulantes_lista(page=1, per_page=20, filtros=None):
    """Lista paginada de postulantes."""
    offset = (page - 1) * per_page

    where_clauses = ["1=1"]
    params = []

    if filtros:
        if filtros.get("programa"):
            where_clauses.append("programa LIKE %s")
            params.append(f"%{filtros['programa']}%")
        if filtros.get("modalidad"):
            where_clauses.append("modalidad_estudios=%s")
            params.append(filtros["modalidad"])
        if filtros.get("turno"):
            where_clauses.append("turno=%s")
            params.append(filtros["turno"])

    where_sql = " AND ".join(where_clauses)

    total = fetch_one(
        f"SELECT COUNT(*) as total FROM postulantes WHERE {where_sql}", tuple(params)
    )
    total = total["total"] if total else 0

    params_with_limit = params + [per_page, offset]
    rows = fetch_all(
        f"""
        SELECT id, codigo, apellidos_nombres, dni, programa, sexo,
               modalidad_estudios, modalidad_admision, semestre_academico,
               turno, asesora, correo, celular
        FROM postulantes
        WHERE {where_sql}
        ORDER BY fecha_importacion DESC
        LIMIT %s OFFSET %s
    """,
        tuple(params_with_limit),
    )

    return {
        "items": rows,
        "total": total,
        "page": page,
        "per_page": per_page,
        "pages": (total + per_page - 1) // per_page,
    }


def crear_postulante(data):
    """Crea un nuevo postulante."""
    with Database(dictionary=False) as db:
        db.cur.execute(
            """
            INSERT INTO postulantes
                (codigo, tipo_documento, dni, apellidos_nombres, celular, correo,
                 departamento, provincia, distrito, sexo, fecha_nacimiento, edad,
                 local, facultad, programa, modalidad_admision, semestre_academico,
                 modalidad_estudios, turno, asesora)
            VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
        """,
            (
                data.get("codigo"),
                data.get("tipo_documento"),
                data.get("dni"),
                data.get("apellidos_nombres"),
                data.get("celular"),
                data.get("correo"),
                data.get("departamento"),
                data.get("provincia"),
                data.get("distrito"),
                data.get("sexo"),
                data.get("fecha_nacimiento"),
                data.get("edad"),
                data.get("local"),
                data.get("facultad"),
                data.get("programa"),
                data.get("modalidad_admision"),
                data.get("semestre_academico"),
                data.get("modalidad_estudios"),
                data.get("turno"),
                data.get("asesora"),
            ),
        )
        db.commit()
        return db.cur.lastrowid


def actualizar_postulante(postulante_id, data):
    """Actualiza un postulante existente."""
    campos = []
    valores = []

    for campo in [
        "tipo_documento",
        "dni",
        "apellidos_nombres",
        "celular",
        "correo",
        "departamento",
        "provincia",
        "distrito",
        "sexo",
        "fecha_nacimiento",
        "edad",
        "local",
        "facultad",
        "programa",
        "modalidad_admision",
        "semestre_academico",
        "modalidad_estudios",
        "turno",
        "asesora",
    ]:
        if campo in data:
            campos.append(f"{campo}=%s")
            valores.append(data[campo])

    if not campos:
        return False

    valores.append(postulante_id)

    with Database(dictionary=False) as db:
        db.cur.execute(
            f"""
            UPDATE postulantes SET {", ".join(campos)} WHERE id=%s
        """,
            tuple(valores),
        )
        db.commit()
        return db.cur.rowcount > 0


def get_postulante_por_codigo(codigo):
    """Busca postulant por código."""
    return fetch_one("SELECT * FROM postulantes WHERE codigo=%s LIMIT 1", (codigo,))


def get_postulantes_sin_solicitud():
    """Postulantes que no tienen solicitud de convalidación."""
    return fetch_all("""
        SELECT p.* 
        FROM postulantes p
        LEFT JOIN solicitudes s ON s.postulante_id = p.id
        WHERE s.id IS NULL
        ORDER BY p.apellidos_nombres
    """)


def get_estadisticas_postulantes():
    """Estadísticas globales de postulantes."""
    stats = {}

    r = fetch_one("SELECT COUNT(*) as total FROM postulantes")
    stats["total"] = r["total"] if r else 0

    r = fetch_one(
        "SELECT COUNT(*) as total FROM postulantes WHERE EXTRACT(YEAR FROM fecha_importacion)=EXTRACT(YEAR FROM NOW())"
    )
    stats["este_anio"] = r["total"] if r else 0

    r = fetch_one("""
        SELECT programa, COUNT(*) as total 
        FROM postulantes 
        GROUP BY programa 
        ORDER BY total DESC 
        LIMIT 5
    """)
    stats["por_programa"] = r if r else []

    return stats
