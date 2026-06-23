-- Restaurar en Neon - solo registros compatibles
-- usuario_id=1 (admin) existe en el seed

INSERT INTO usuario_modulos (usuario_id, modulo_id) VALUES 
(1, 6), (1, 7), (1, 8) ON CONFLICT DO NOTHING;
