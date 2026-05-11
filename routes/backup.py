# routes/backup.py
from flask import Blueprint, Response, flash, redirect, url_for, request, render_template
from werkzeug.utils import secure_filename
from db.conexion import get_connection
from routes.auth import admin_requerido
import io, os, zipfile, re, logging
from datetime import datetime

logger = logging.getLogger(__name__)

bp_backup = Blueprint('backup', __name__)

TABLAS = [
    'anios_decretados', 'facultades', 'carreras', 'modulos', 'usuarios',
    'usuario_modulos', 'tipo_documentos', 'tipo_silabos', 'plantillas_correo',
    'config_correo', 'postulantes', 'solicitudes', 'solicitud_cursos',
    'checklist_documentos', 'planeacion_curricular', 'log_sistema'
]


def _escape(val):
    if val is None:
        return 'NULL'
    if isinstance(val, (int, float)):
        return str(val)
    if isinstance(val, datetime):
        return f"'{val.strftime('%Y-%m-%d %H:%M:%S')}'"
    s = str(val).replace("'", "''").replace('\r', '\\r').replace('\n', '\\n')
    return f"'{s}'"


def _dump_table(conn, table):
    cur = conn.cursor(dictionary=True)
    cur.execute(f"SELECT * FROM {table}")
    cols = [d[0] for d in cur.description]
    rows = cur.fetchall()
    cur.close()
    lines = [f"\n-- Table {table}\n"]
    lines.append(f"DELETE FROM {table};\n")
    if rows:
        for r in rows:
            vals = [_escape(r[c]) for c in cols]
            lines.append(f"INSERT INTO {table} ({', '.join(c for c in cols)}) VALUES ({', '.join(vals)});\n")
    return ''.join(lines)


@bp_backup.route('/admin/backup')
@admin_requerido
def index():
    return render_template('admin/backup.html')


@bp_backup.route('/admin/backup/descargar')
@admin_requerido
def hacer_backup():
    try:
        conn = get_connection()
        buffer = io.StringIO()
        buffer.write(f"-- Backup Sistema Convalidaciones\n-- {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n\n")
        buffer.write("SET session_replication_role = 'replica';\n\n")

        for tabla in TABLAS:
            try:
                buffer.write(_dump_table(conn, tabla))
            except Exception:
                pass

        buffer.write("\nSET session_replication_role = 'origin';\nCOMMIT;\n")
        conn.close()

        nombre = f"backup_sistema_{datetime.now().strftime('%Y%m%d_%H%M%S')}.sql"
        return Response(
            buffer.getvalue(),
            mimetype='application/sql',
            headers={'Content-Disposition': f'attachment; filename={nombre}'}
        )

    except Exception as e:
        flash(f'Error al generar backup: {e}', 'danger')
        return redirect(url_for('backup.index'))


@bp_backup.route('/admin/backup/completo')
@admin_requerido
def backup_completo():
    try:
        conn = get_connection()
        buffer_zip = io.BytesIO()

        with zipfile.ZipFile(buffer_zip, 'w', zipfile.ZIP_DEFLATED) as zf:
            sql_buffer = io.StringIO()
            sql_buffer.write(f"-- Backup Sistema Convalidaciones\n-- {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n\n")
            sql_buffer.write("SET session_replication_role = 'replica';\n\n")

            for tabla in TABLAS:
                try:
                    sql_buffer.write(_dump_table(conn, tabla))
                except Exception:
                    pass

            sql_buffer.write("\nSET session_replication_role = 'origin';\nCOMMIT;\n")
            zf.writestr(f"backup_{datetime.now().strftime('%Y%m%d_%H%M%S')}.sql", sql_buffer.getvalue())

            uploads_dir = os.path.join(os.path.dirname(os.path.dirname(__file__)), 'static', 'uploads')
            if os.path.isdir(uploads_dir):
                for root, _, files in os.walk(uploads_dir):
                    for fname in files:
                        fpath = os.path.join(root, fname)
                        arcname = os.path.relpath(fpath, os.path.dirname(uploads_dir))
                        zf.write(fpath, arcname)

        conn.close()
        buffer_zip.seek(0)
        nombre = f"backup_completo_{datetime.now().strftime('%Y%m%d_%H%M%S')}.zip"
        return Response(
            buffer_zip.getvalue(),
            mimetype='application/zip',
            headers={'Content-Disposition': f'attachment; filename={nombre}'}
        )

    except Exception as e:
        flash(f'Error al generar backup: {e}', 'danger')
        return redirect(url_for('backup.index'))


@bp_backup.route('/admin/backup/restaurar', methods=['POST'])
@admin_requerido
def restaurar():
    if 'archivo' not in request.files:
        flash('No se encontró archivo', 'danger')
        return redirect(url_for('backup.index'))

    archivo = request.files['archivo']
    if archivo.filename == '':
        flash('Selecciona un archivo', 'danger')
        return redirect(url_for('backup.index'))

    if not (archivo.filename.endswith('.sql') or archivo.filename.endswith('.zip')):
        flash('Formato no permitido. Solo .sql o .zip', 'danger')
        return redirect(url_for('backup.index'))

    try:
        contenido = archivo.read()

        if archivo.filename.endswith('.zip'):
            zf = zipfile.ZipFile(io.BytesIO(contenido))
            sql_files = [n for n in zf.namelist() if n.endswith('.sql')]
            if not sql_files:
                flash('El ZIP no contiene archivo SQL', 'danger')
                return redirect(url_for('backup.index'))
            sql_content = zf.read(sql_files[0]).decode('utf-8')
        else:
            sql_content = contenido.decode('utf-8')

        conn = get_connection()
        conn._conn.autocommit = True
        cur = conn.cursor()

        statements = _parse_sql(sql_content)
        total = len(statements)
        ejecutados = 0
        errores = []

        for stmt in statements:
            stmt = stmt.strip()
            if not stmt or stmt.startswith('--'):
                continue
            try:
                if stmt.upper().startswith('INSERT INTO '):
                    stmt = 'INSERT INTO ' + stmt[12:] + ' ON CONFLICT DO NOTHING'
                cur.execute(stmt)
                ejecutados += 1
            except Exception as e:
                err_msg = f"Error en: {stmt[:120]}... -> {str(e)}"
                errores.append(err_msg)
                logger.error(err_msg)

        conn.close()

        if errores:
            muestras = errores[:5]
            msg = f'Restaurado: {ejecutados} consultas OK, {len(errores)} errores. Primeros: {" | ".join(muestras)}'
            flash(msg, 'warning')
        else:
            flash(f'Restauración exitosa. {ejecutados} consultas ejecutadas.', 'success')

    except Exception as e:
        flash(f'Error al restaurar: {e}', 'danger')

    return redirect(url_for('backup.index'))


def _parse_sql(sql):
    stmt = []
    in_string = False
    current = ''
    i = 0
    while i < len(sql):
        c = sql[i]
        if c == "'":
            if in_string and i + 1 < len(sql) and sql[i + 1] == "'":
                current += "''"
                i += 2
                continue
            elif i == 0 or sql[i - 1] != '\\':
                in_string = not in_string
            current += c
        elif c == ';' and not in_string:
            if current.strip():
                stmt.append(current.strip())
            current = ''
        else:
            current += c
        i += 1
    if current.strip():
        stmt.append(current.strip())
    return stmt