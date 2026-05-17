"""init_db.py — Restaura backup_inicial.sql si la DB está vacía.

Ejecutar antes de iniciar la app:
    python init_db.py
"""

import os
import logging
from config import DB_CONFIG
import psycopg2

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("init_db")

TABLAS = [
    "anios_decretados", "facultades", "carreras", "carreras_periodos",
    "modulos", "cursos_plan", "planes_estudio", "usuarios",
    "usuario_modulos", "plantillas_correo", "config_correo",
    "postulantes", "solicitudes", "solicitud_cursos",
    "checklist_documentos", "checklist_recepciones", "logs_sistema",
]

BACKUP_FILE = os.path.join(os.path.dirname(__file__), "backup_inicial.sql")


def _db_vacia(cur):
    for tabla in TABLAS:
        try:
            cur.execute(f"SELECT COUNT(*) FROM {tabla}")
            row = cur.fetchone()
            if row and row[0] > 0:
                return False
        except Exception:
            pass
    return True


def _parse_sql(sql):
    stmt = []
    in_string = False
    current = ""
    i = 0
    while i < len(sql):
        c = sql[i]
        if c == "'":
            if in_string and i + 1 < len(sql) and sql[i + 1] == "'":
                current += "''"
                i += 2
                continue
            elif i == 0 or sql[i - 1] != "\\":
                in_string = not in_string
            current += c
        elif c == ";" and not in_string:
            if current.strip():
                stmt.append(current.strip())
            current = ""
        else:
            current += c
        i += 1
    if current.strip():
        stmt.append(current.strip())
    return stmt


def main():
    if not os.path.isfile(BACKUP_FILE):
        logger.info("No se encontró backup_inicial.sql — se omite restauración")
        return

    logger.info("Conectando a la base de datos...")
    conn = psycopg2.connect(**DB_CONFIG)
    conn.autocommit = True
    cur = conn.cursor()

    if not _db_vacia(cur):
        logger.info("La base de datos ya tiene datos — se omite restauración")
        cur.close()
        conn.close()
        return

    logger.info("Base de datos vacía. Restaurando desde backup_inicial.sql...")
    with open(BACKUP_FILE, "r", encoding="utf-8") as f:
        contenido = f.read()

    statements = _parse_sql(contenido)
    ejecutados = 0
    errores = []

    for stmt in statements:
        stmt = stmt.strip()
        if not stmt or stmt.startswith("--"):
            continue
        try:
            if stmt.upper().startswith("INSERT INTO "):
                stmt = "INSERT INTO " + stmt[12:] + " ON CONFLICT DO NOTHING"
            cur.execute(stmt)
            ejecutados += 1
        except Exception as e:
            err_msg = f"Error en: {stmt[:120]}... -> {e}"
            errores.append(err_msg)
            logger.error(err_msg)

    cur.close()
    conn.close()

    if errores:
        logger.warning(f"Restaurado: {ejecutados} OK, {len(errores)} errores")
    else:
        logger.info(f"Restauración exitosa: {ejecutados} consultas ejecutadas")


if __name__ == "__main__":
    main()
