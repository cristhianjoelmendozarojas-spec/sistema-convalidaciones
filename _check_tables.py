import os, re, psycopg2
from dotenv import load_dotenv
load_dotenv()

with open('routes/backup.py', 'r') as f:
    content = f.read()
match = re.search(r'TABLAS = \[(.*?)\]', content, re.DOTALL)
backup_tables = set(re.findall(r"'([^']+)'", match.group(1)))

conn = psycopg2.connect(
    host=os.getenv('DB_HOST', 'localhost'),
    port=int(os.getenv('DB_PORT', '5432')),
    user=os.getenv('DB_USER', 'postgres'),
    password=os.getenv('DB_PASSWORD', ''),
    dbname=os.getenv('DB_NAME', 'sistema_convalidacion'),
    sslmode=os.getenv('DB_SSLMODE', 'require'),
)
cur = conn.cursor()
cur.execute("SELECT table_name FROM information_schema.tables WHERE table_schema = 'public' AND table_type = 'BASE TABLE'")
db_tables = set(r[0] for r in cur.fetchall())
cur.close()
conn.close()

print("=== En backup.py ===")
for t in sorted(backup_tables):
    print(f"  {t}")

print("\n=== En DB real ===")
for t in sorted(db_tables):
    print(f"  {t}")

print("\n--- Diferencias ---")
print(f"En backup pero NO en DB: {backup_tables - db_tables}")
print(f"En DB pero NO en backup: {db_tables - backup_tables}")
if backup_tables == db_tables:
    print("TODO COINCIDE. 17/17 tablas incluidas.")
else:
    print(f"FALTAN: {db_tables - backup_tables}")
