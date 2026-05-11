-- Migración de MySQL a PostgreSQL para Sistema de Convalidaciones UAI
-- Ejecutar en la base de datos PostgreSQL destino

CREATE TABLE IF NOT EXISTS usuarios (
    id SERIAL PRIMARY KEY,
    dni VARCHAR(20) NOT NULL UNIQUE,
    contrasena VARCHAR(255) NOT NULL,
    nombre_completo VARCHAR(255),
    rol VARCHAR(50) DEFAULT 'usuario',
    estado VARCHAR(20) DEFAULT 'activo',
    primer_acceso BOOLEAN DEFAULT TRUE,
    fecha_creacion TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE IF NOT EXISTS modulos (
    id SERIAL PRIMARY KEY,
    clave VARCHAR(100) NOT NULL UNIQUE,
    nombre VARCHAR(255) NOT NULL,
    descripcion TEXT,
    icono VARCHAR(50) DEFAULT '📦',
    orden INTEGER DEFAULT 99,
    activo BOOLEAN DEFAULT TRUE
);

CREATE TABLE IF NOT EXISTS usuario_modulos (
    id SERIAL PRIMARY KEY,
    usuario_id INTEGER NOT NULL REFERENCES usuarios(id) ON DELETE CASCADE,
    modulo_id INTEGER NOT NULL REFERENCES modulos(id) ON DELETE CASCADE
);

CREATE TABLE IF NOT EXISTS facultades (
    id SERIAL PRIMARY KEY,
    nombre VARCHAR(255) NOT NULL,
    codigo VARCHAR(50),
    descripcion TEXT,
    estado VARCHAR(20) DEFAULT 'activo'
);

CREATE TABLE IF NOT EXISTS carreras (
    id SERIAL PRIMARY KEY,
    facultad_id INTEGER NOT NULL REFERENCES facultades(id) ON DELETE CASCADE,
    nombre VARCHAR(255) NOT NULL,
    codigo VARCHAR(50),
    periodo VARCHAR(20),
    costo_convalidacion NUMERIC(10,2) DEFAULT 60,
    costo_examen NUMERIC(10,2) DEFAULT 130,
    estado VARCHAR(20) DEFAULT 'activo'
);

CREATE TABLE IF NOT EXISTS planes_estudio (
    id SERIAL PRIMARY KEY,
    nombre_plan VARCHAR(255) NOT NULL,
    tipo_plan VARCHAR(50) DEFAULT 'local',
    periodo_academico VARCHAR(50),
    fecha_importacion TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE IF NOT EXISTS cursos_plan (
    id SERIAL PRIMARY KEY,
    plan_id INTEGER NOT NULL REFERENCES planes_estudio(id) ON DELETE CASCADE,
    ciclo VARCHAR(5) NOT NULL,
    codigo VARCHAR(50),
    nombre_curso VARCHAR(255) NOT NULL,
    creditos INTEGER NOT NULL,
    prerrequisito VARCHAR(255)
);

CREATE TABLE IF NOT EXISTS postulantes (
    id SERIAL PRIMARY KEY,
    codigo VARCHAR(50) UNIQUE,
    tipo_documento VARCHAR(50),
    dni VARCHAR(20),
    apellidos_nombres VARCHAR(255),
    celular VARCHAR(20),
    correo VARCHAR(255),
    departamento VARCHAR(100),
    provincia VARCHAR(100),
    distrito VARCHAR(100),
    sexo VARCHAR(20),
    fecha_nacimiento DATE,
    edad INTEGER,
    local VARCHAR(100),
    facultad VARCHAR(255),
    institucion_procedencia VARCHAR(255),
    programa VARCHAR(255),
    modalidad_admision VARCHAR(100),
    semestre_academico VARCHAR(50),
    modalidad_estudios VARCHAR(100),
    turno VARCHAR(50),
    asesora VARCHAR(255),
    fecha_registro_origen DATE,
    escala_matricula VARCHAR(50),
    escala_pensiones VARCHAR(50),
    monto_expediente NUMERIC(10,2),
    estado_expediente VARCHAR(50),
    fecha_pago_expediente DATE,
    monto_postulacion NUMERIC(10,2),
    estado_postulacion VARCHAR(50),
    fecha_pago_postulacion DATE,
    monto_matricula NUMERIC(10,2),
    estado_matricula VARCHAR(50),
    fecha_pago_matricula DATE,
    foto VARCHAR(255),
    fecha_importacion TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    fecha_actualizacion TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE IF NOT EXISTS solicitudes (
    id SERIAL PRIMARY KEY,
    codigo VARCHAR(100) NOT NULL,
    postulante_id INTEGER REFERENCES postulantes(id) ON DELETE SET NULL,
    carrera_id INTEGER REFERENCES carreras(id) ON DELETE SET NULL,
    plan_local_id INTEGER REFERENCES planes_estudio(id) ON DELETE SET NULL,
    plan_externo_id INTEGER REFERENCES planes_estudio(id) ON DELETE SET NULL,
    fecha_emision DATE,
    fecha_registro TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    estado VARCHAR(50) DEFAULT 'borrador',
    observacion TEXT,
    costo_credito NUMERIC(10,2) DEFAULT 60,
    costo_examen NUMERIC(10,2) DEFAULT 130,
    confirmado INTEGER DEFAULT 0,
    token_confirmacion VARCHAR(255),
    estado_confirmacion VARCHAR(50),
    fecha_confirmacion TIMESTAMP
);

CREATE TABLE IF NOT EXISTS solicitud_cursos (
    id SERIAL PRIMARY KEY,
    solicitud_id INTEGER NOT NULL REFERENCES solicitudes(id) ON DELETE CASCADE,
    curso_local_id INTEGER REFERENCES cursos_plan(id) ON DELETE SET NULL,
    curso_externo_id INTEGER REFERENCES cursos_plan(id) ON DELETE SET NULL,
    nota NUMERIC(5,2),
    estado VARCHAR(50) DEFAULT 'pendiente',
    periodo_lectivo VARCHAR(50)
);

CREATE TABLE IF NOT EXISTS logs_sistema (
    id SERIAL PRIMARY KEY,
    usuario_id INTEGER,
    usuario_dni VARCHAR(20),
    accion VARCHAR(50),
    modulo VARCHAR(50),
    descripcion TEXT,
    entidad_id INTEGER,
    ip VARCHAR(50),
    fecha TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE IF NOT EXISTS config_correo (
    id SERIAL PRIMARY KEY,
    usuario_id INTEGER REFERENCES usuarios(id) ON DELETE CASCADE,
    correo_remitente VARCHAR(255),
    contrasena VARCHAR(255),
    nombre_remitente VARCHAR(255),
    smtp_host VARCHAR(255),
    smtp_puerto INTEGER,
    ssl_habilitado BOOLEAN DEFAULT TRUE,
    activo BOOLEAN DEFAULT FALSE,
    fecha_creacion TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE IF NOT EXISTS plantillas_correo (
    id SERIAL PRIMARY KEY,
    nombre VARCHAR(255),
    asunto VARCHAR(255),
    cuerpo TEXT,
    activo BOOLEAN DEFAULT TRUE,
    fecha_creacion TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE IF NOT EXISTS checklist_documentos (
    id SERIAL PRIMARY KEY,
    postulante_id INTEGER NOT NULL REFERENCES postulantes(id) ON DELETE CASCADE,
    documento VARCHAR(255),
    tipo_doc VARCHAR(50),
    detalle TEXT,
    es_silabo BOOLEAN DEFAULT FALSE,
    archivo VARCHAR(255),
    entregado BOOLEAN DEFAULT FALSE,
    observacion TEXT,
    fecha_entrega DATE
);

CREATE TABLE IF NOT EXISTS checklist_recepciones (
    id SERIAL PRIMARY KEY,
    documento_id INTEGER NOT NULL REFERENCES checklist_documentos(id) ON DELETE CASCADE,
    area VARCHAR(255),
    fecha_recepcion DATE,
    observaciones TEXT,
    registrado_por VARCHAR(255),
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE IF NOT EXISTS anios_decretados (
    id SERIAL PRIMARY KEY,
    anio INTEGER NOT NULL UNIQUE,
    nombre VARCHAR(255) NOT NULL,
    estado VARCHAR(20) DEFAULT 'activo'
);

-- Insertar año decretado por defecto
INSERT INTO anios_decretados (anio, nombre, estado) VALUES (2026, 'Año de la Esperanza y el Fortalecimiento de la Democracia', 'activo') ON CONFLICT (anio) DO NOTHING;

-- Insertar administrador por defecto (contraseña: admin123)
INSERT INTO usuarios (dni, contrasena, nombre_completo, rol, estado, primer_acceso)
VALUES ('admin', '$2b$12$LJ3m4ys3Lk0TSwHnbfOMiOXPm1Qlq5Gz0Yq0Z0Z0Z0Z0Z0Z0Z0', 'Administrador', 'admin', 'activo', FALSE)
ON CONFLICT (dni) DO NOTHING;
