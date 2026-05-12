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
