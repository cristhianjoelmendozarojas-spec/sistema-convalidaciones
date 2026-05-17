import psycopg2
import io
import os
import zipfile
from datetime import datetime

from os import environ

DB = {
    "host": environ.get("DB_HOST", "localhost"),
    "port": int(environ.get("DB_PORT", 5432)),
    "user": environ.get("DB_USER", "postgres"),
    "password": environ.get("DB_PASSWORD", ""),
    "dbname": environ.get("DB_NAME", "sistema_convalidacion"),
    "sslmode": environ.get("DB_SSLMODE", "require"),
}

TABLAS_ORDER = [
    "anios_decretados",
    "facultades",
    "carreras",
    "carreras_periodos",
    "modulos",
    "cursos_plan",
    "planes_estudio",
    "usuarios",
    "usuario_modulos",
    "plantillas_correo",
    "config_correo",
    "postulantes",
    "solicitudes",
    "solicitud_cursos",
    "checklist_documentos",
    "checklist_recepciones",
    "logs_sistema",
]

EXCLUIR_COLUMNAS = {}


def conectar():
    return psycopg2.connect(**DB)


def columnas_tabla(cur, tabla):
    cur.execute(f"""
        SELECT column_name, column_default
        FROM information_schema.columns
        WHERE table_schema = 'public' AND table_name = '{tabla}'
        ORDER BY ordinal_position
    """)
    return [(r[0], r[1]) for r in cur.fetchall()]


def secuencias_tabla(cur, tabla):
    cur.execute(f"""
        SELECT column_name, column_default
        FROM information_schema.columns
        WHERE table_schema = 'public'
          AND table_name = '{tabla}'
          AND column_default LIKE 'nextval(%'
    """)
    return [r[0] for r in cur.fetchall()]


def escape_valor(val, col_type=None):
    if val is None:
        return "NULL"
    if isinstance(val, bool):
        return "TRUE" if val else "FALSE"
    if isinstance(val, (int, float)):
        return str(val)
    if isinstance(val, (datetime,)):
        return f"'{val.strftime('%Y-%m-%d %H:%M:%S')}'"
    s = str(val).replace("'", "''")
    return f"'{s}'"


def dump_tabla(cur, tabla):
    cols = columnas_tabla(cur, tabla)
    excluir = EXCLUIR_COLUMNAS.get(tabla, [])
    col_names = [c[0] for c in cols if c[0] not in excluir]
    seq_cols = secuencias_tabla(cur, tabla)

    cur.execute(f'SELECT * FROM "{tabla}" ORDER BY 1')
    rows = cur.fetchall()
    if not rows:
        return f"-- Table {tabla}: sin datos\n"

    lines = [f"\n-- Table {tabla} ({len(rows)} registros)\n"]
    lines.append(f'DELETE FROM "{tabla}";\n')
    if seq_cols:
        lines.append(
            f'ALTER SEQUENCE IF EXISTS "{tabla}_{seq_cols[0]}_seq" RESTART WITH {len(rows) + 1};\n'
        )

    for row in rows:
        vals = []
        for i, c in enumerate(cols):
            if c[0] in excluir:
                continue
            vals.append(escape_valor(row[i]))
        cols_sql = ", ".join(f'"{c}"' for c in col_names)
        vals_sql = ", ".join(vals)
        lines.append(f'INSERT INTO "{tabla}" ({cols_sql}) VALUES ({vals_sql});\n')

    return "".join(lines)


def respaldar():
    print("Conectando a la base de datos...")
    conn = conectar()
    cur = conn.cursor()
    now = datetime.now()
    timestamp = now.strftime("%Y%m%d_%H%M%S")

    sql = io.StringIO()
    sql.write("-- Backup Completo - Sistema Convalidaciones\n")
    sql.write(f"-- Fecha: {now.strftime('%Y-%m-%d %H:%M:%S')}\n")
    sql.write(f"-- Base de datos: {DB['dbname']}\n\n")
    sql.write("SET session_replication_role = 'replica';\n\n")

    for tabla in TABLAS_ORDER:
        try:
            print(f"  Respaldando {tabla}...")
            sql.write(dump_tabla(cur, tabla))
        except Exception as e:
            print(f"  ! Error en {tabla}: {e}")

    sql.write("\nSET session_replication_role = 'origin';\n\n")
    cur.close()
    conn.close()

    buffer_zip = io.BytesIO()
    with zipfile.ZipFile(buffer_zip, "w", zipfile.ZIP_DEFLATED) as zf:
        zf.writestr(f"backup_{timestamp}.sql", sql.getvalue())

    nombre_zip = f"backup_completo_{timestamp}.zip"
    with open(nombre_zip, "wb") as f:
        f.write(buffer_zip.getvalue())

    print(f"\nBackup completado: {nombre_zip}")
    print(f"Tamaño: {os.path.getsize(nombre_zip) / 1024:.1f} KB")
    return nombre_zip


if __name__ == "__main__":
    respaldar()
