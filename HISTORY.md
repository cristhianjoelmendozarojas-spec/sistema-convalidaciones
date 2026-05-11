# Historial de Cambios - Sistema de Convalidaciones

## 2026-05-10

### Facultad/Carrera desde IDs
- Agregada columna `carrera_id` a `solicitudes` (ALTER TABLE)
- `generar_word.py`: facultad y carrera se obtienen vía `s.carrera_id → carreras → facultades`, con fallback por matching de `p.programa`
- `dashboard.py` `iniciar_convalidacion()`: ahora guarda `facultad_nombre` en sesión con JOIN a facultades
- `solicitudes.py` INSERT: incluye `carrera_id` desde sesión
- Backfill: 5 solicitudes existentes actualizadas con su `carrera_id` correcto
- `reportes.py`: agrupación por facultad ahora usa `s.carrera_id → carreras → facultades`

### Corrección de Bugs
- CSS sidebar: eliminada línea duplicada que rompía estilos del menú
- `solicitudes.py`: restauradas variables `costo_cred`/`costo_exam` eliminadas accidentalmente al editar INSERT

### Limpieza de Proyecto
- Eliminados: `detalle.html.bak`, `app.log`, `utils/`, `wsgi.py`, `render.yaml`
- Eliminados todos los `__pycache__`
- Eliminados directorios vacíos: `static/cache/reportes/`, `static/img/reportes/`
- `requirements.txt`: simplificado a 9 dependencias directas, eliminado `fpdf2` (no usado), quitadas transitivas y versiones fijas

### Mejoras UI
- Modal de confirmación al guardar convalidación (con resumen: conv/exam/pend + costos)
- Botón "Ir al detalle" en modal redirige a vista de detalle
- Auto-selección de carrera en formulario: si no existe en periodo más reciente, busca en todos los periodos

## 2026-04-28

### Correcciones de Errores
- Corregido texto chino incorrecto en config.py: "蝴蝶" → "Año de la Reconciliación y el Desarrollo"
- Corregido error 500 en checklist_recepciones: agregado try/except para manejo de errores
- Corregido IP hardcodeada en solicitudes.py: ahora usa variable APP_BASE_URL
- Corregido `cellulaire` → `celular` en postulantes_service.py (typo francés)

### Base de Datos - Coherencia
- Corregido uso de campo inexistente: `fecha_registro` → `fecha_importacion` en postulantes
- Verificadas todas las referencias a campos entre código y BD
- Confirmadas foreig keys: solicitudes→postulantes, solicitud_cursos→cursos_plan, etc.

### Optimización de Rendimiento
- Agregado Flask-Caching para datos estáticos:
  - Carreras: 10 minutos de caché
  - Planes por tipo: 15 minutos de caché
  - Cursos por plan: 15 minutos de caché
- Mejorado rendimiento，减少 consultas a BD repetitivas

### Configuración
- Agregada variable APP_BASE_URL en .env para enlaces en correos
- Actualizado requirements.txt con Flask-Caching

---

## 2026-04-27

### Estructura de Proyecto
- Refactorizado código: separacion de capas Routes/Services/DB
- Creado services/solicitud_service.py - logica de negocio solicitudes
- Creado services/postulantes_service.py - logica de negocio postulantes
- Creado services/dashboard_service.py ya existia
- Migrado routes/solicitudes.py para usar services

### Correccion de Errores
- Corregido error generar_codigo() en service - KeyError con fetch_one
- Agregado sys.path en app.py para importar modulos locales
- Corregido typo: postulates -> postulantes en postulantes.py

### Menu Sidebar
- Agregado Dashboard visible siempre para todos los usuarios
- Agregado boton Recargar permisos en footer
- Endpoint /dashboard/recargar-modulos para actualizarsession sin logout

### Modulo Convalidacion
- Eliminada seccion "Ingreso de Notas - Plan Externo (Origen)" ya no es necesaria

### Correo Electronico
-default_html_template con salto de linea antes de Bienvenido(a)
- Soporte agregado para dominio educativo @autonomadeica.edu.pe via Office 365

### WhatsApp
- Mensaje con salto de linea antes de Bienvenido(a)
- Mensaje con B mayuscula
- Corregido URL encoding para saltos de linea (%0A)

### Base de Datos
- Indices de rendimiento ya aplicados en BD
- Verificado que existen indices en: solicitudes, postulantes, solicitud_cursos, cursos_plan, planes_estudio, logs_sistema

### Configuracion Desarrollo
- Creado .flaskenv con FLASK_DEBUG=1 para auto-reload
- Modo debug por defecto true en app.py

### Produccion
- wsgi.pyya configurado para gunicorn
- app.log eliminado (__pycache__ ya eliminado)

---

## 2026-04-26

### Modulos del Sistema
- Agregados modulos "correo" y "whatsapp" para configuracion
- Asignacion de modulos por usuario desde Admin > Usuarios > Modulos
- Usuarios estandar pueden ver/crear sus propios correos configurados

### Configuracion de Correo
- Admin puede ver todos los correos de todos los usuarios
- Usuario estandar ve los suyos, si no tiene usa el correo activo del admin
- Plantillas precargadas para todos los usuarios
- Selecciona automaticamente el correo activo en el dropdown

### Menu Lateral
- Titulos de seccion (Admision, Convalidacion, etc.) solo visibles para admin
- Modulos de configuracion (correo, whatsapp) accesibles para usuarios con modulo asignado

### Correccion de IP
- Actualizada IP de confirmacion: 192.168.18.23

---

## 2026-04-20

### PDF Resolucion
- PORTADA en primera pagina
- Contenido con header/footer
- CONTRAPORTADA en ultima pagina

---

## 2026-04-15

### Cache
- Corregido error "I/O operation on closed file"
- Solucion: crear copia del buffer antes de guardar

### Descarga PDF
- Eliminada apertura en nueva pestana (target="_blank")
- Descarga directa desde vista previa