import re

def parse_values(values_str):
    """Parse comma-separated SQL values respecting string literals and NULL."""
    vals = []
    cur = ''
    depth = 0
    in_str = False
    for ch in values_str:
        if ch == "'":
            in_str = not in_str
            cur += ch
        elif ch == '(' and not in_str:
            depth += 1
            cur += ch
        elif ch == ')' and not in_str:
            depth -= 1
            cur += ch
        elif ch == ',' and depth == 0 and not in_str:
            vals.append(cur.strip())
            cur = ''
        else:
            cur += ch
    if cur.strip():
        vals.append(cur.strip())
    return vals

def split_sql_into_statements(sql):
    """Split SQL into individual statements respecting string literals."""
    stmts = []
    cur = ''
    in_str = False
    for ch in sql:
        if ch == "'":
            in_str = not in_str
            cur += ch
        elif ch == ';' and not in_str:
            if cur.strip():
                stmts.append(cur.strip() + ';')
            cur = ''
        else:
            cur += ch
    if cur.strip():
        stmts.append(cur.strip())
    return stmts

def is_boolean_column(col_name):
    return col_name in ('activo', 'primer_acceso', 'ssl_habilitado', 'entregado', 'es_silabo')

def find_paren_pair(s, start):
    """Find the closing `)` matching the opening `(` at position `start`, respecting string literals."""
    i = start
    depth = 0
    in_str = False
    for i in range(start, len(s)):
        ch = s[i]
        if ch == "'":
            in_str = not in_str
        elif ch == '(' and not in_str:
            depth += 1
        elif ch == ')' and not in_str:
            depth -= 1
            if depth == 0:
                return i
    return -1

def extract_cols_and_vals(stmt):
    """Extract column list and value list from an INSERT statement, respecting string literals."""
    # Find the first ( for column list
    paren_start = stmt.index('(')
    paren_end = find_paren_pair(stmt, paren_start)
    if paren_end == -1:
        return None, None
    cols_str = stmt[paren_start+1:paren_end]
    
    # Find VALUES keyword
    rest = stmt[paren_end+1:]
    vals_idx = rest.upper().find('VALUES')
    if vals_idx == -1:
        return None, None
    
    # Find the ( for values list
    vals_part = rest[vals_idx + 6:]
    vals_paren = vals_part.index('(')
    vals_end = find_paren_pair(vals_part, vals_paren)
    if vals_end == -1:
        return None, None
    vals_str = vals_part[vals_paren+1:vals_end]
    
    return cols_str, vals_str

def fix_insert(stmt):
    """Fix a single INSERT statement from MySQL to PostgreSQL format."""
    if not stmt.upper().startswith('INSERT INTO '):
        return stmt
    
    m = re.match(r'INSERT\s+INTO\s+(\w+)', stmt)
    if not m:
        return stmt
    table = m.group(1)
    
    extra_cols_map = {
        'anios_decretados': ['fecha_creacion'],
        'facultades': ['fecha_creacion'],
        'carreras': ['fecha_creacion'],
        'usuarios': ['fecha_actualizacion'],
        'usuario_modulos': ['fecha_asignacion'],
        'plantillas_correo': ['fecha_actualizacion'],
        'config_correo': ['fecha_actualizacion'],
        'postulantes': ['origen_importacion', 'importado_por'],
        'solicitudes': ['fecha_emision_timestamp', 'emitido_por'],
    }
    extra_cols = extra_cols_map.get(table, [])
    
    cols_str, vals_str = extract_cols_and_vals(stmt)
    if cols_str is None:
        return stmt
    
    cols = [c.strip() for c in cols_str.split(',')]
    vals = parse_values(vals_str)
    
    if len(cols) != len(vals):
        return stmt
    
    indices_to_remove = set()
    for extra_col in extra_cols:
        if extra_col in cols:
            idx = cols.index(extra_col)
            indices_to_remove.add(idx)
    
    fixed_vals = []
    for i, (col, val) in enumerate(zip(cols, vals)):
        if i in indices_to_remove:
            continue
        if is_boolean_column(col) and val in ('0', '1'):
            fixed_vals.append('TRUE' if val == '1' else 'FALSE')
        else:
            fixed_vals.append(val)
    
    fixed_cols = [c for i, c in enumerate(cols) if i not in indices_to_remove]
    
    return f"INSERT INTO {table} ({', '.join(fixed_cols)}) VALUES ({', '.join(fixed_vals)});"


sql = open('backup_20260510_021603.sql', 'r', encoding='utf-8').read()

# Global replacements
sql = sql.replace("SET FOREIGN_KEY_CHECKS=0;", "SET session_replication_role = 'replica';")
sql = sql.replace("SET UNIQUE_CHECKS=0;", "")
sql = sql.replace("SET autocommit=0;", "")
sql = sql.replace("SET FOREIGN_KEY_CHECKS=1;", "SET session_replication_role = 'origin';")
sql = sql.replace("SET UNIQUE_CHECKS=1;", "")
sql = sql.replace('`', '')
sql = sql.replace("INSERT IGNORE INTO", "INSERT INTO")

stmts = split_sql_into_statements(sql)
fixed_stmts = [fix_insert(s) for s in stmts]

result = '\n'.join(fixed_stmts)
# Clean up
result = re.sub(r'\n{3,}', '\n\n', result)
# Remove empty SET lines
result = re.sub(r'SET\s+;\n', '', result)

open('backup_convertido_postgresql.sql', 'w', encoding='utf-8').write(result)
print("Conversion complete!")
