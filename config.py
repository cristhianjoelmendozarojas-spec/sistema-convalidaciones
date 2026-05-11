# config.py
# ============================================
# Configuración de base de datos y aplicación
# ============================================
import os
from datetime import timedelta
from dotenv import load_dotenv

load_dotenv()

# Años declarados por el gobierno peruano
# Formato: "AÑO": "Nombre del Año"
ANIOS_DECRETADOS = {
    2025: "Año de la Reconciliación Nacional",
    2026: "Año de la Esperanza y el Fortalecimiento de la Democracia",
    2027: "Año de la Reconciliación y el Desarrollo",
}

DB_CONFIG = {
    "host":     os.getenv("DB_HOST", "localhost"),
    "port":     int(os.getenv("DB_PORT", "5432")),
    "user":     os.getenv("DB_USER", "postgres"),
    "password": os.getenv("DB_PASSWORD", ""),
    "dbname":   os.getenv("DB_NAME", "sistema_convalidacion"),
}

class Config:
    SECRET_KEY = os.environ.get('SECRET_KEY') or 'dev-fallback-change-in-production'
    DB_CONFIG = DB_CONFIG
    
    JSON_SORT_KEYS = False
    MAX_CONTENT_LENGTH = 16 * 1024 * 1024

    SESSION_COOKIE_SECURE = os.getenv('FLASK_ENV') == 'production'
    SESSION_COOKIE_HTTPONLY = True
    SESSION_COOKIE_SAMESITE = 'Lax'
    PERMANENT_SESSION_LIFETIME = timedelta(hours=1)
    SESSION_REFRESH_EACH_REQUEST = True

def guardar_variable_env(clave, valor):
    """Guarda una variable en el archivo .env"""
    ruta_env = os.path.join(os.path.dirname(os.path.abspath(__file__)), '.env')
    
    with open(ruta_env, 'r', encoding='utf-8') as f:
        lineas = f.readlines()
    
    clave_normalizada = clave.upper()
    encontrada = False
    
    for i, linea in enumerate(lineas):
        if linea.strip().startswith(f'{clave_normalizada}='):
            lineas[i] = f'{clave_normalizada}={valor}\n'
            encontrada = True
            break
    
    if not encontrada:
        lineas.append(f'\n{clave_normalizada}={valor}\n')
    
    with open(ruta_env, 'w', encoding='utf-8') as f:
        f.writelines(lineas)
