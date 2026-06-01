"""setup_db.py — Crea el esquema completo de la BD desde cero.

Útil cuando Render elimina la base de datos y necesitas recrearla.

Uso:
    python setup_db.py

Requiere:
    - Variables de entorno DB_HOST, DB_USER, DB_PASSWORD, DB_NAME
      (o tener un archivo .env en el directorio del proyecto)
    - pip install psycopg2-binary python-dotenv
"""

import os
import sys

from dotenv import load_dotenv

load_dotenv()

DB_CONFIG = {
    "host": os.environ.get("DB_HOST", "localhost"),
    "port": int(os.environ.get("DB_PORT", 5432)),
    "user": os.environ.get("DB_USER", "postgres"),
    "password": os.environ.get("DB_PASSWORD", ""),
    "dbname": os.environ.get("DB_NAME", "sistema_convalidacion"),
    "sslmode": os.environ.get("DB_SSLMODE", "require"),
}

SCHEMA_FILE = os.path.join(os.path.dirname(__file__), "init_schema.sql")


def main():
    if not os.path.isfile(SCHEMA_FILE):
        print(f"ERROR: No se encuentra {SCHEMA_FILE}")
        sys.exit(1)

    print(f"Conectando a {DB_CONFIG['host']}/{DB_CONFIG['dbname']}...")
    try:
        import psycopg2
    except ImportError:
        print("ERROR: ejecuta 'pip install psycopg2-binary' primero")
        sys.exit(1)

    conn = psycopg2.connect(**DB_CONFIG)
    conn.autocommit = True
    cur = conn.cursor()

    print("Ejecutando init_schema.sql...")
    with open(SCHEMA_FILE, "r", encoding="utf-8") as f:
        sql = f.read()

    statements = []
    current = ""
    in_string = False
    i = 0
    while i < len(sql):
        c = sql[i]
        if c == "'":
            if in_string and i + 1 < len(sql) and sql[i + 1] == "'":
                current += "''"
                i += 2
                continue
            in_string = not in_string
            current += c
        elif c == ";" and not in_string:
            if current.strip():
                statements.append(current.strip())
            current = ""
        else:
            current += c
        i += 1
    if current.strip():
        statements.append(current.strip())

    ok = 0
    err = 0
    for stmt in statements:
        stmt = stmt.strip()
        if not stmt or stmt.startswith("--"):
            continue
        try:
            cur.execute(stmt)
            ok += 1
        except Exception as e:
            err += 1
            print(f"  ⚠  {e}")

    cur.close()
    conn.close()

    print(f"\n{'¡LISTO!' if err == 0 else 'COMPLETADO CON ERRORES'}")
    print(f"  {ok} sentencias ejecutadas")
    if err:
        print(f"  {err} errores (ignorables si ya existen)")
    print()
    print("Próximos pasos:")
    print(f"  1. python init_db.py          (si tienes backup_inicial.sql)")
    print(f"  2. python app.py              (iniciar el servidor)")
    print(f"  3. Login: admin / admin123")
    print()


if __name__ == "__main__":
    main()
