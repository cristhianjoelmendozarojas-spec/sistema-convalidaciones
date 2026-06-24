import os
os.environ["SECRET_KEY"] = "tmp"
os.environ["DB_SSLMODE"] = "disable"
os.environ["DB_PASSWORD"] = os.environ.get("DB_PASSWORD", "postgres")
os.environ["DB_HOST"] = os.environ.get("DB_HOST", "localhost")
os.environ["DB_PORT"] = os.environ.get("DB_PORT", "5432")
os.environ["DB_USER"] = os.environ.get("DB_USER", "postgres")
os.environ["DB_NAME"] = os.environ.get("DB_NAME", "sistema_convalidacion")

import sys; sys.path.insert(0, '.')
import importlib
import config; importlib.reload(config)

from db.conexion import execute
sql = "UPDATE solicitudes SET codigo = REPLACE(codigo, 'SIMULACION-', 'IC-CONVALIDACION-') WHERE codigo LIKE 'SIMULACION-%'"
rows, _ = execute(sql, commit=True)
print(f'Registros actualizados: {rows}')
