# Historial de Cambios — Sistema de Convalidaciones

## 2026-05-12

### Problema: "Error de conexión" al enviar correo desde Render

**Archivos:** `.env`, `config.py`

**Causa:** El `.env` apuntaba a `localhost` en vez de a la base de datos de Render (`dpg-d80sgq67r5hc73bu539g-a.oregon-postgres.render.com`). La BD `sistema_convalidacion` no existía localmente.

**Solución:**
1. Actualizar `.env` con credenciales de Render (host, user, password).
2. Agregar `sslmode=require` a `DB_CONFIG` en `config.py` (requerido por Render PostgreSQL).

---

### Diagnóstico SMTP desde producción

| Prueba | Resultado |
|--------|-----------|
| Conexión SMTP desde máquina local | ✅ Exitosa (Gmail, Office365) |
| Envío de prueba desde Render | ❌ `Network is unreachable` (Render bloquea puertos SMTP 587/465) |

**Conclusión:** Render bloquea tráfico SMTP saliente en su plan gratuito. Para enviar correos desde Render se necesita:

1. **Plan pago de Render** — desbloquea SMTP, o
2. **API HTTPS** (Gmail API / Microsoft Graph) — usa puerto 443, no bloqueado.

---

### Commits realizados

| Hash | Mensaje |
|------|---------|
| `86ccbe5` | Fix: add sslmode=require to DB_CONFIG for cloud PostgreSQL (Render) |
| `96d8d50` | Revert "Feat: add SendGrid API support as alternative to SMTP for cloud hosting" |

---

## 2026-05-11

### Problema: Error 500 al cargar detalle/convalidación por NULL en `costo_credito`/`costo_examen`

**Archivos:** `services/solicitud_service.py:66-67`

**Causa:** `float(None)` cuando la BD devuelve NULL en `costo_credito` o `costo_examen`.

**Solución:** Usar `float(x or 60)` y `float(x or 130)` como valores por defecto.

---

### Problema: Error de sintaxis SQL por falta de f-string

**Archivos:** `services/solicitud_service.py:45`

**Causa:** La consulta SQL usaba `{_ORDEN_CICLO}` pero la cadena no tenía prefijo `f`, causando interpolación literal.

**Solución:** Agregar prefijo `f` a la cadena SQL.

---

### Problema: `PgConnection.cursor()` no acepta `cursor_factory` como kwarg

**Archivos:** `routes/generar_word.py:94,110`

**Causa:** Se pasaba `cursor_factory=RealDictCursor` pero `PgConnection.cursor()` solo acepta `dictionary=True`.

**Solución:** Cambiar a `conn.cursor(dictionary=True)` y eliminar import de `RealDictCursor`.

---

### Problema: Error 500 sin mensaje en rutas `convalidar` y `ver`

**Archivos:** `routes/solicitudes.py:270-276, 95-101`

**Causa:** Las rutas no tenían try/except, mostraban página 500 genérica.

**Solución:** Agregar try/except con `traceback.print_exc()` y flash con el error real.

---

### Problema: CSRF token inválido en peticiones AJAX POST

**Archivos:** `app.py:119`, `templates/solicitudes/lista.html`

**Causa:** El `before_request` de CSRF redirigía con HTML aunque la petición esperara JSON (fetch → `.then(r => r.json())`). El `.catch()` mostraba "Error de conexion".

**Solución:**
1. En `app.py`: agregar `request.content_type == 'application/json'` como condición para responder con JSON en vez de redirect.
2. En `lista.html`: agregar header `X-CSRF-Token` explícito y `Accept: application/json` en todos los fetch POST (eliminar, enviar correo, WhatsApp send, WhatsApp log).

---

### Problema: "Error de conexion" al enviar correo (persistente)

**Archivos:** `routes/solicitudes.py:496-497`, `routes/generar_word.py:301-302`

**Causa 1:** `get_connection()` estaba fuera del bloque `try/except` en `enviar_correo`, `guardar_convalidacion`, `eliminar_curso` y `editar_curso`. Si fallaba la conexión a PostgreSQL, Flask devolvía HTML 500 (no JSON), el `.catch()` mostraba "Error de conexion".

**Causa 2:** `float(s["costo_credito"])` en `generar_word.py` sin manejo de NULL — misma traza que el primer error pero en el generador de PDF.

**Solución:**
1. Mover `get_connection()` dentro del `try` en todas las rutas. Inicializar `conn = None; cur = None` antes del try y verificar en finally.
2. Cambiar `float(s["costo_credito"])` por `float(s.get("costo_credito") or 0)`.

---

### Commits realizados

| Hash | Mensaje |
|------|---------|
| `13baae9` | Fix: replace cursor_factory with dictionary param in PgConnection.cursor() |
| `3bdaa9c` | Fix: add missing f-prefix to SQL query with {_ORDEN_CICLO} interpolation |
| `7f87f11` | Add error handling to convalidar/ver routes to capture 500 details |
| `71a20ab` | Fix: ensure costo_credito/costo_examen default to 60/130 when NULL in DB |
| `837746b` | Fix: handle NULL costo_credito/costo_examen in convalidacion (prevents 500 error) |
| `dde9f3e` | Fix: add explicit CSRF tokens to all POST fetches and handle JSON content type in CSRF check |
| `4d0a611` | Fix: move get_connection() inside try blocks to prevent unhandled 500 errors; fix float(None) in generar_word.py |

---

### Pendiente

- Hacer deploy en Render (push a `origin/main` gatilla auto-deploy si está configurado)
- Probar en producción: envío de correo, WhatsApp, confirmación, reporte de notas
- Si persisten errores CSRF, agregar exclusión por blueprint como fallback

---

## 2026-05-13

### Problema: Descarga de Excel "como video" y preview sin "EXAMEN SUFICIENCIA"

**Archivos:** `routes/solicitudes.py`

**Causa 1 (download):** El bloque `except Exception as e:` estaba duplicado en `consolidado_excel`. El primer except retornaba texto plano, el segundo se ejecutaba pero las conexiones ya se cerraban antes de enviar el archivo.

**Causa 2 (preview):** La columna "Nombre del curso" (Convalidación) siempre mostraba `local_nombre` sin importar el estado. No se evaluaba `estado == 'examen_suficiencia'` para mostrar "EXAMEN SUFICIENCIA".

**Solución:**
1. Reemplazar el `except` duplicado por `try/except/finally` que siempre cierra `cur` y `conn`.
2. Agregar lógica por estado en la columna "Nombre del curso":
   - `convalidado` → `local_nombre`
   - `examen_suficiencia` → "EXAMEN SUFICIENCIA"
   - `pendiente` → `periodo_lectivo`
   - `sin_validar` → `periodo_lectivo` o "—"
3. Nota solo visible para `convalidado`.
4. Mostrar `-` cuando créditos son 0 (local y externo).

---

### Problema: UNION ORDER BY inválido en PostgreSQL

**Archivos:** `routes/solicitudes.py`

**Causa:** Se agregó `UNION ALL` para incluir cursos sin `curso_externo_id`, pero PostgreSQL no permite expresiones (COALESCE) en ORDER BY de UNION.

**Solución:** Agregar `sort_nombre` como columna calculada en cada SELECT y usarla en ORDER BY. Luego se revirtió el UNION porque los exámenes de suficiencia sí tenían curso externo vinculado, haciendo innecesario el UNION.

---

### Problema: Filas "None" en consolidado por UNION ALL

**Archivos:** `routes/solicitudes.py`

**Causa:** El `UNION ALL` agregaba filas con columnas NULL para cursos sin `curso_externo_id`, mostrando "none" en la tabla.

**Solución:** Revertir a la query original simple sin UNION. La query `FROM cursos_plan cp_e LEFT JOIN solicitud_cursos sc` ya incluye todos los cursos del plan externo con su estado correcto.

---

### Commits realizados

| Hash | Mensaje |
|------|---------|
| `e331875` | Fix: replace duplicate except with try/except/finally |
| `ac0caf9` | Fix: show '-' for 0 credits in consolidado (Excel + preview) |
| `187667c` | Fix: include examen_suficiencia courses without external plan link |
| `54698ed` | Fix: use sort_nombre column for UNION ORDER BY (PostgreSQL compat) |
| `dc0df28` | Revert UNION ALL, keep original query for consolidado |

---

## 2026-05-13 (tarde)

### Cambios en consulta de consolidado (Excel + Preview)

**Archivos:** `routes/solicitudes.py`

**Cambios:**
- La query del reporte ahora parte de `solicitud_cursos` en vez de `cursos_plan cp_e`
- Se invierten los JOINs: `cp_externo` apunta a `curso_local_id` (datos del plan local) y `cp_local` apunta a `curso_externo_id` (datos del plan externo)
- Se añade columna `convalidacion` con CASE: muestra nombre externo si convalidado, "Examen Suficiencia" si examen, o periodo lectivo si pendiente
- Se añade columna `cred` (créditos del curso externo)
- Filtro `curso_local_id IS NOT NULL` para omitir registros huérfanos
- Encabezados: CICLO, CÓDIGO, NOMBRE DEL CURSO, CRÉD., PRERREQ., NOMBRE DEL CURSO, CRÉD., NOTA

---

### Drag & Drop — planificación académica manual

**Archivos:** `templates/solicitudes/convalidacion.html`

**Cambios:**
- Los cursos pendientes se renderizan como **cards draggables** en columnas por periodo
- **HTML5 Drag & Drop API** para mover cursos entre periodos
- **Validación de prerrequisitos** en doble dirección:
  - El curso movido no puede tener su prerrequisito en el mismo periodo destino
  - El curso movido no puede ser prerrequisito de otro curso en el periodo destino
- **Tarjetas con indicador visual** de conflicto (borde rojo + etiqueta ⚠ Conflicto)
- Botón **"Auto-planificar"** que ejecuta el algoritmo automático
- Se eliminó `recalcularPeriodos()` de `guardarConvalidacion()` para preservar cambios manuales
- `planificar()` ahora agrupa por `_periodoMap` en lugar de recalcular internamente

### Persistencia de periodos al restaurar

**Archivos:** `templates/solicitudes/convalidacion.html`

**Problema:** Al recargar la página de convalidación, `renderTabla()` llamaba a `recalcularPeriodos()` que sobrescribía los periodos guardados manualmente.

**Solución:**
- `restaurarGuardado()` recolecta `savedPeriodos` del API, llama `recalcularPeriodos()` para llenar cursos sin periodo, luego **sobrescribe** `_periodoMap` con los guardados
- `renderTabla()` detecta si ya hay periodos asignados (`tienePendPeriodos`) y salta `recalcularPeriodos()` en ese caso

### Bugfix: validación de prerrequisitos con early return

**Archivos:** `templates/solicitudes/convalidacion.html`

**Problema:** `validarPrerrequisito()` retornaba `null` inmediatamente si el curso arrastrado no tenía prerrequisito, impidiendo el segundo chequeo (cuando el curso arrastrado ES prerrequisito de otro en el periodo destino).

**Solución:** Separar los dos chequeos en bloques independientes sin early return.

---

## 2026-05-15

### Fix: remitente de correo ignoraba selección del modal

**Archivos:** `routes/correos.py`, `routes/solicitudes.py`

**Problema:** El frontend enviaba `remitente_id` (config ID seleccionado) pero el backend lo ignoraba y siempre usaba `session.get('usuario_id')` para buscar la configuración, cayendo en la del admin si el usuario no tenía configuración activa propia.

**Solución:**
1. Nueva función `get_config_correo_por_id(config_id)` en `correos.py` que obtiene una configuración específica por ID.
2. `enviar_correo()` ahora acepta `config_id`. Si se proporciona, usa esa configuración.
3. En `solicitudes.py` se extrae `remitente_id` del body y se pasa como `config_id`.

---

### Fix: correo no aparece en bandeja de enviados del remitente

**Archivos:** `routes/correos.py`

**Problema:** SMTP directo solo entrega al destinatario, no guarda copia en "Enviados". Para Office365/educativos el problema es más notorio.

**Solución:** Incluir al remitente como BCC en `sendmail()` en ambas funciones (`_enviar_smtp_directo` y `_enviar_brevo`), agregando `correo_remitente` a la lista de destinatarios.

---

### Feature: usuario y fecha en registro de notas (solicitud_cursos)

**Archivos:** `migracion_postgresql.sql`, `routes/solicitudes.py`

**Cambios:**
1. Columnas `usuario_id INTEGER` y `fecha_registro TIMESTAMP DEFAULT CURRENT_TIMESTAMP` agregadas a `solicitud_cursos`.
2. `guardar_convalidacion()` inserta con `usuario_id` y `NOW()`.
3. `editar_curso()` actualiza `usuario_id` y `fecha_registro=NOW()`.

---

### Feature: último usuario que registró notas en el pie del record

**Archivos:** `routes/solicitudes.py`

**Cambios:**
- Se consulta el último `usuario_id` con `fecha_registro` en `solicitud_cursos` para la solicitud.
- Se muestra en el footer del record de notas HTML y PDF: `- Ultimo registro de notas por: [usuario] [fecha]`.

---

### Feature: quien emitió la convalidación en el historial

**Archivos:** `routes/solicitudes.py`

**Cambio:** `marcar_emitido()` ahora registra: `Solicitud emitida por [usuario_nombre]: id=X`.

---

### Feature: botón de historial completo para admin

**Archivos:** `routes/solicitudes.py`, `templates/solicitudes/lista.html`

**Cambios:**
1. Nuevo endpoint `GET /solicitudes/historial/<id>` que retorna todos los logs de la solicitud.
2. Botón 📋 en acciones visible solo para admin (`session.get('usuario_rol') == 'admin'`).
3. Modal que muestra fecha, usuario y descripción de cada acción.

---

### Fix: fecha de emisión automática en nueva solicitud

**Archivos:** `routes/solicitudes.py`, `templates/solicitudes/formulario.html`

**Cambios:**
1. Backend: `nueva()` siempre asigna `dt.now().strftime('%Y-%m-%d')`, ignora el valor del formulario.
2. Frontend: JavaScript autocompleta `#fecha_header` con la fecha actual al cargar y sincroniza al hidden field. Se quitó el `required` del campo.

---

### Fix: orden de cursos en consolidado por ciclo

**Archivos:** `routes/solicitudes.py`

**Cambio:** El `ORDER BY` del consolidado-preview ordena por `cp_externo.ciclo` primero y luego por `cp_externo.codigo`.

---

### Fix: planificación académica a 5 columnas

**Archivos:** `templates/solicitudes/convalidacion.html`

**Cambios:**
1. `#plan_container` cambió de grid layout con `repeat(5, 1fr)` para mostrar máximo 5 columnas por fila.
2. Se eliminó `max-height:360px;overflow-y:auto` para que se vean todas las filas sin scroll interno.
