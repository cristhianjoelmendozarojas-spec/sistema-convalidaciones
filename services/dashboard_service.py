# services/dashboard_service.py
"""
Servicios para el dashboard y métricas.
"""

from db.conexion import Database


def get_metricas(mes=None, anio=None):
    filtro_sql = ""
    params = []
    if anio:
        filtro_sql += " AND EXTRACT(YEAR FROM s.fecha_registro) = %s"
        params.append(int(anio))
    if mes:
        filtro_sql += " AND EXTRACT(MONTH FROM s.fecha_registro) = %s"
        params.append(int(mes))

    with Database(dictionary=True) as db:
        db.cur.execute(
            f"""
            SELECT estado, COUNT(*) AS total
            FROM solicitudes s WHERE 1=1{filtro_sql}
            GROUP BY estado
        """,
            params,
        )
        estados = {r["estado"]: r["total"] for r in db.cur.fetchall()}

        total_emitidas = estados.get("emitido", 0)
        total_borradores = estados.get("borrador", 0)
        total_solicitudes = total_emitidas + total_borradores

        db.cur.execute("SELECT COUNT(*) AS total FROM postulantes")
        total_postulantes = db.cur.fetchone()["total"]

        db.cur.execute("""
            SELECT COUNT(*) AS total FROM postulantes p
            LEFT JOIN solicitudes s ON s.postulante_id = p.id
            WHERE s.id IS NULL
        """)
        sin_convalidacion = db.cur.fetchone()["total"]

        pct_avance = (
            round((total_solicitudes / total_postulantes * 100), 1)
            if total_postulantes
            else 0
        )

        db.cur.execute(
            f"""
            SELECT COALESCE(SUM(
                COALESCE(sc_conv.total_cred, 0) * s.costo_credito
                + COALESCE(sc_exam.cantidad, 0) * s.costo_examen
            ), 0) AS total_costo
            FROM solicitudes s
            LEFT JOIN (
                SELECT solicitud_id, SUM(cp.creditos) AS total_cred
                FROM solicitud_cursos sc
                JOIN cursos_plan cp ON sc.curso_local_id = cp.id
                WHERE sc.estado = 'convalidado'
                GROUP BY solicitud_id
            ) sc_conv ON sc_conv.solicitud_id = s.id
            LEFT JOIN (
                SELECT solicitud_id, COUNT(*) AS cantidad
                FROM solicitud_cursos
                WHERE estado = 'examen_suficiencia'
                GROUP BY solicitud_id
            ) sc_exam ON sc_exam.solicitud_id = s.id
            WHERE s.estado = 'emitido'{filtro_sql}
        """,
            params,
        )
        total_costo = float(db.cur.fetchone()["total_costo"])

        db.cur.execute("""
            SELECT s.id, s.codigo, s.estado, s.fecha_registro,
                   COALESCE(p.apellidos_nombres,'—') AS nombre,
                   COALESCE(p.programa,'—') AS programa
            FROM solicitudes s
            LEFT JOIN postulantes p ON s.postulante_id=p.id
            ORDER BY s.fecha_registro DESC LIMIT 6
        """)
        ultimas = db.cur.fetchall()

        db.cur.execute(
            f"""
            SELECT estado, COUNT(*) AS total
            FROM solicitudes s WHERE 1=1{filtro_sql}
            GROUP BY estado
        """,
            params,
        )
        por_estado = {r["estado"]: r["total"] for r in db.cur.fetchall()}

        db.cur.execute("""
            SELECT TO_CHAR(fecha_registro,'YYYY-MM') AS mes, COUNT(*) AS total
            FROM solicitudes
            WHERE fecha_registro >= NOW() - INTERVAL '6 MONTHS'
            GROUP BY mes ORDER BY mes
        """)
        por_mes = db.cur.fetchall()

        return {
            "total_emitidas": total_emitidas,
            "total_borradores": total_borradores,
            "total_solicitudes": total_solicitudes,
            "sin_convalidacion": sin_convalidacion,
            "total_postulantes": total_postulantes,
            "pct_avance": pct_avance,
            "total_costo": total_costo,
            "ultimas": ultimas,
            "por_estado": por_estado,
            "por_mes": por_mes,
        }


def get_facultades():
    with Database(dictionary=True) as db:
        db.cur.execute("""
            SELECT f.*, COUNT(c.id) AS total_carreras
            FROM facultades f
            LEFT JOIN carreras c ON c.facultad_id=f.id AND c.estado='activo'
            WHERE f.estado='activo'
            GROUP BY f.id ORDER BY f.nombre
        """)
        return db.cur.fetchall()


def get_carreras_facultad(facultad_id):
    with Database(dictionary=True) as db:
        db.cur.execute(
            """
            SELECT c.*, f.nombre AS facultad_nombre
            FROM carreras c
            JOIN facultades f ON c.facultad_id = f.id
            WHERE c.facultad_id=%s AND c.estado='activo'
            ORDER BY c.nombre
        """,
            (facultad_id,),
        )
        return db.cur.fetchall()


def get_carrera(carrera_id):
    with Database(dictionary=True) as db:
        db.cur.execute("SELECT * FROM carreras WHERE id=%s", (carrera_id,))
        return db.cur.fetchone()
