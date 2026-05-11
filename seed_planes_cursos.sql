-- Seed data for planes_estudio and cursos_plan
-- Needed to satisfy FK references from solicitudes and solicitud_cursos

DELETE FROM cursos_plan;
DELETE FROM planes_estudio;

-- Plan Local
INSERT INTO planes_estudio (id, nombre_plan, tipo_plan, periodo_academico, fecha_importacion)
VALUES (1, 'Plan de Estudios Local - Enfermeria', 'local', '2024-I', '2024-01-15 08:00:00');

-- Plan Externo
INSERT INTO planes_estudio (id, nombre_plan, tipo_plan, periodo_academico, fecha_importacion)
VALUES (2, 'Plan de Estudios Externo - Ciencias de la Salud', 'externo', '2024-I', '2024-01-15 08:00:00');

-- Cursos locales (plan_id=1)
INSERT INTO cursos_plan (id, plan_id, ciclo, codigo, nombre_curso, creditos, prerrequisito)
VALUES (1, 1, 'I', 'ENF101', 'Anatomia Humana', 4, NULL);
INSERT INTO cursos_plan (id, plan_id, ciclo, codigo, nombre_curso, creditos, prerrequisito)
VALUES (2, 1, 'II', 'ENF102', 'Fisiologia', 4, 'ENF101');
INSERT INTO cursos_plan (id, plan_id, ciclo, codigo, nombre_curso, creditos, prerrequisito)
VALUES (3, 1, 'III', 'ENF103', 'Farmacologia', 3, 'ENF102');
INSERT INTO cursos_plan (id, plan_id, ciclo, codigo, nombre_curso, creditos, prerrequisito)
VALUES (4, 1, 'IV', 'ENF104', 'Enfermeria Clinica', 5, 'ENF103');

-- Cursos externos (plan_id=2)
INSERT INTO cursos_plan (id, plan_id, ciclo, codigo, nombre_curso, creditos, prerrequisito)
VALUES (5, 2, 'I', 'SAL101', 'Anatomia General', 4, NULL);
INSERT INTO cursos_plan (id, plan_id, ciclo, codigo, nombre_curso, creditos, prerrequisito)
VALUES (6, 2, 'II', 'SAL102', 'Fisiologia General', 4, 'SAL101');
INSERT INTO cursos_plan (id, plan_id, ciclo, codigo, nombre_curso, creditos, prerrequisito)
VALUES (7, 2, 'III', 'SAL103', 'Patologia General', 3, 'SAL102');
INSERT INTO cursos_plan (id, plan_id, ciclo, codigo, nombre_curso, creditos, prerrequisito)
VALUES (8, 2, 'IV', 'SAL104', 'Salud Publica', 5, 'SAL103');
