# Sistema de Convalidaciones — UAI

Sistema web para gestión de convalidaciones de estudios universitarios. Administra postulantes, solicitudes, planes de estudio, checklists documentarios y generación de resoluciones PDF.

## Stack

- **Backend:** Python 3 + Flask
- **Base de datos:** PostgreSQL
- **Frontend:** HTML + Jinja2 + CSS vanilla
- **PDF:** ReportLab + PyMuPDF
- **Despliegue:** Render

## Requisitos

- Python 3.10+
- PostgreSQL

## Instalación local

```bash
git clone <repo>
cd sistema-convalidaciones

python -m venv .venv
.venv\Scripts\activate    # Windows
source .venv/bin/activate  # Linux/Mac

pip install -r requirements.txt
```

## Configuración

Crear archivo `.env` en la raíz:

```env
DB_HOST=localhost
DB_PORT=5432
DB_USER=postgres
DB_PASSWORD=tu_password
DB_NAME=sistema_convalidacion
DB_SSLMODE=require
SECRET_KEY=una_clave_segura_aqui
FLASK_DEBUG=true
FLASK_HOST=0.0.0.0
FLASK_PORT=5000
```

### Base de datos

Opción 1 — Script Python (recomendado):

```bash
python setup_db.py
```

Opción 2 — psql directo:

```bash
psql -U postgres -d sistema_convalidacion -f init_schema.sql
```

Esto crea las 17 tablas, índices, y seed data (admin, módulos, plantillas).

### Demo (sin login)

En la página de login hay un botón **🚀 Acceso Demo** que permite explorar el sistema en modo solo lectura, sin credenciales.

## Ejecutar

```bash
python app.py
```

Servidor en `http://localhost:5000`.

### Usuario por defecto

- **Usuario:** `admin`
- **Contraseña:** `admin123`

## Estructura

```
routes/         → Controladores (blueprints)
services/       → Lógica de negocio
db/             → Conexión, pool, cache, validadores
templates/      → Jinja2 HTML
plantillas_word/→ Recursos para PDF (imágenes, docx)
init_schema.sql → Esquema completo de BD (tablas + índices + seed)
setup_db.py     → Script para inicializar la BD desde cero
```

## Módulos principales

| Ruta | Módulo |
|------|--------|
| `/` | Dashboard |
| `/postulantes/` | CRUD e importación de postulantes |
| `/solicitudes/` | Solicitudes de convalidación |
| `/planes/` | Planes de estudio |
| `/admin/` | Administración (usuarios, carreras, facultades) |
| `/reportes/` | Reportes y descargas masivas |

## Backup

El sistema incluye backup desde el panel Admin > Respaldo:

- **Descargar SQL** — datos de las 17 tablas
- **Descargar completo** — datos + archivos subidos (ZIP)
- **Restaurar** — subir un `.sql` o `.zip` previo

Para backup completo del esquema + datos desde terminal:

```bash
python backup_total.py
```

## Despliegue en Render

El proyecto incluye `render.yaml` con la configuración para Render. Solo conectar el repo y Render aprovisiona automáticamente la base de datos y el servicio web.

Variables de entorno requeridas en producción:

| Variable | Descripción |
|----------|-------------|
| `SECRET_KEY` | Clave para firmar sesiones |
| `FLASK_ENV=production` | Entorno de producción |
| `FLASK_DEBUG=false` | Deshabilitar debug mode |

Las credenciales de BD se asignan automáticamente desde el servicio PostgreSQL de Render.

## Linter

```bash
ruff check .
ruff format .
```
