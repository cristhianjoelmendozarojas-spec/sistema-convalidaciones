-- ═══════════════════════════════════════════════════════════════
-- Optimización de Base de Datos — Sistema Convalidaciones UAI
-- ═══════════════════════════════════════════════════════════════
-- Ejecutar: psql -U postgres -d sistema_convalidacion -f optimizar_bd.sql
-- ═══════════════════════════════════════════════════════════════

-- ── 1. Extensiones ─────────────────────────────────────────
CREATE EXTENSION IF NOT EXISTS pg_trgm;

-- ── 2. Índices para FK (JOINs) ─────────────────────────────
CREATE INDEX IF NOT EXISTS idx_solicitudes_postulante   ON solicitudes(postulante_id);
CREATE INDEX IF NOT EXISTS idx_solicitudes_carrera      ON solicitudes(carrera_id);
CREATE INDEX IF NOT EXISTS idx_solicitudes_plan_local   ON solicitudes(plan_local_id);
CREATE INDEX IF NOT EXISTS idx_solicitudes_plan_externo ON solicitudes(plan_externo_id);

CREATE INDEX IF NOT EXISTS idx_solicitud_cursos_solicitud   ON solicitud_cursos(solicitud_id);
CREATE INDEX IF NOT EXISTS idx_solicitud_cursos_local       ON solicitud_cursos(curso_local_id);
CREATE INDEX IF NOT EXISTS idx_solicitud_cursos_externo     ON solicitud_cursos(curso_externo_id);

CREATE INDEX IF NOT EXISTS idx_cursos_plan_plan             ON cursos_plan(plan_id);
CREATE INDEX IF NOT EXISTS idx_carreras_facultad            ON carreras(facultad_id);
CREATE INDEX IF NOT EXISTS idx_checklist_postulante         ON checklist_documentos(postulante_id);
CREATE INDEX IF NOT EXISTS idx_checklist_recepciones_doc    ON checklist_recepciones(documento_id);
CREATE INDEX IF NOT EXISTS idx_usuario_modulos_usuario      ON usuario_modulos(usuario_id);
CREATE INDEX IF NOT EXISTS idx_usuario_modulos_modulo       ON usuario_modulos(modulo_id);
CREATE INDEX IF NOT EXISTS idx_logs_usuario                 ON logs_sistema(usuario_id);

-- ── 3. Índices para WHERE frecuentes ───────────────────────
CREATE INDEX IF NOT EXISTS idx_postulantes_dni              ON postulantes(dni);
CREATE INDEX IF NOT EXISTS idx_postulantes_programa         ON postulantes(programa);
CREATE INDEX IF NOT EXISTS idx_postulantes_modalidad        ON postulantes(modalidad_estudios);
CREATE INDEX IF NOT EXISTS idx_solicitudes_codigo           ON solicitudes(codigo);
CREATE INDEX IF NOT EXISTS idx_solicitudes_token            ON solicitudes(token_confirmacion);

-- ── 4. Índices para ORDER BY ───────────────────────────────
CREATE INDEX IF NOT EXISTS idx_solicitudes_fecha_registro   ON solicitudes(fecha_registro DESC);
CREATE INDEX IF NOT EXISTS idx_postulantes_apellidos        ON postulantes(apellidos_nombres);
CREATE INDEX IF NOT EXISTS idx_logs_fecha                   ON logs_sistema(fecha DESC);

-- ── 5. Índice trigram para búsqueda por texto (%palabra%) ──
CREATE INDEX IF NOT EXISTS idx_postulantes_nombres_trgm
    ON postulantes USING gin (apellidos_nombres gin_trgm_ops);

CREATE INDEX IF NOT EXISTS idx_postulantes_dni_trgm
    ON postulantes USING gin (dni gin_trgm_ops);

-- ── 6. Analizar tablas (actualiza estadísticas al planner) ─
ANALYZE;
