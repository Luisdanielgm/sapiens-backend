from flask import Flask, jsonify, request
from flask_cors import CORS
from flask_jwt_extended import JWTManager
from src.shared.database import get_db, setup_database_indexes
from config import active_config, validate_env_vars
import logging
import os
import sys
import datetime
from src.shared.constants import APP_PREFIX, APP_NAME

# Configuración de logging
logging_level = logging.DEBUG if active_config.DEBUG else logging.INFO
logging.basicConfig(
    level=logging_level,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

# Verificar variables de entorno críticas
if not validate_env_vars():
    logger.critical("Faltan variables de entorno críticas. Por favor, configure el archivo .env")
    if os.getenv('ENFORCE_ENV_VALIDATION', '0') == '1':
        sys.exit(1)
    else:
        logger.warning("Continuando a pesar de la falta de variables de entorno. Esto puede causar errores.")

def create_app(config_object=active_config):
    """
    Factory function para crear la aplicación Flask
    """
    app = Flask(__name__)
    app.config.from_object(config_object)
    
    # Configurar CORS
    CORS(app, origins=app.config['CORS_ORIGINS'])
    
    # Configurar JWT
    jwt = JWTManager(app)
    
    # Configurar base de datos
    try:
        logger.info("Configurando conexión a la base de datos...")
        db = get_db()
        logger.info("✓ Conexión a MongoDB establecida exitosamente")
        
        # Configurar índices
        logger.info("Configurando índices de la base de datos...")
        setup_database_indexes()
        logger.info("✓ Índices configurados exitosamente")
        
    except Exception as e:
        logger.error(f"Error configurando la base de datos: {e}")
        if app.config.get('REQUIRE_DB', True):
            raise
    
    # Ruta de prueba
    @app.route('/')
    def health_check():
        return jsonify({
            'status': 'success',
            'message': f'{APP_NAME} API está funcionando correctamente',
            'timestamp': datetime.datetime.now().isoformat(),
            'version': '1.0.0',
            'environment': app.config.get('FLASK_ENV', 'development')
        })
    
    @app.route('/health')
    def health():
        return jsonify({
            'status': 'healthy',
            'database': 'connected',
            'timestamp': datetime.datetime.now().isoformat()
        })
    
    logger.info("✓ Aplicación Flask configurada exitosamente")
    return app

# Crear la aplicación
app = create_app()

if __name__ == '__main__':
    logger.info(f"Iniciando aplicación en modo {os.getenv('FLASK_ENV', 'development')}")
    logger.info(f"Puerto: {app.config['PORT']}")
    logger.info(f"Debug: {app.config['DEBUG']}")
    app.run(
        debug=app.config['DEBUG'], 
        host='0.0.0.0', 
        port=app.config['PORT']
    )