# Historial de cambios

## 2026-06-23 — Corrección carga de planes en convalidación

### Problema
El formulario de convalidación de cursos mostraba error 500 al cargar los planes de estudio.

### Causa raíz
`get_cache()` en `services/solicitud_service.py` devolvía un `dict` en lugar del backend de caché real. Flask-Caching 2.3.1 almacena los backends dentro de un diccionario:

```python
app.extensions["cache"] = {CacheInstance: SimpleCache_backend}
```

Al llamar `current_app.extensions.get("cache")`, se obtenía el `dict` y fallaba al ejecutar `.set()`.

### Archivos modificados

| Archivo | Cambio |
|---------|--------|
| `services/solicitud_service.py` | `get_cache()` ahora itera sobre los valores del dict interno y retorna el backend real (SimpleCache). También se filtraron planes con `tipo_plan` vacío/NULL como "locales". |
| `routes/solicitudes.py` | Se agregó try/except a `api_planes_por_tipo()` para capturar errores y retornar JSON. Se corrigió IndentationError en `_get_s_basico`. |
| `routes/planes.py` | Misma corrección de filtro: `tipo_plan` vacío/NULL se muestra como "local". |
| `templates/solicitudes/convalidacion.html` | Se escaparon caracteres especiales en `s.codigo` y `s.nombre` dentro de JS. Se agregó `.catch()` al fetch con manejo de error visible. Se corrigió la asignación de `_PLAN_LOCAL_ID`/`_PLAN_EXTERNO_ID` para que `None` → `null` en JS. |

### Cambios anteriores (sesiones previas)

- **Módulo Correo**: subpáginas Guardados, Configuración, Plantillas
- **Sidebar**: hover dropdown con avatar, Recargar permisos y Cerrar sesión
- **UX/UI**: tipografía, cards, botones, tablas, modales, login page
- **reportlab**: fixed `_escape()` para manejar strings y números
- **record_notas/consolidado_preview**: fixed doble cierre de cursor/connection
- **Importación de plan**: se agregó `clear_planes_cache()` para invalidar caché al importar/editar/eliminar planes
