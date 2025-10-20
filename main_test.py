from flask import Flask, jsonify
from flask_cors import CORS
from flask_jwt_extended import JWTManager
from config import active_config, validate_env_vars
import logging
import os
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
    logger.warning("Continuando sin validación completa...")

def create_app(config_object=active_config):
    """
    Factory function para crear la aplicación Flask sin base de datos
    """
    app = Flask(__name__)
    app.config.from_object(config_object)
    
    # Configurar CORS
    CORS(app, origins=app.config['CORS_ORIGINS'])
    
    # Configurar JWT
    jwt = JWTManager(app)
    
    logger.info("✓ Aplicación Flask configurada sin base de datos")
    
    # Ruta de prueba
    @app.route('/')
    def health_check():
        return jsonify({
            'status': 'success',
            'message': f'{APP_NAME} API está funcionando correctamente',
            'timestamp': datetime.datetime.now().isoformat(),
            'version': '1.0.0',
            'environment': app.config.get('FLASK_ENV', 'development'),
            'database': 'not_connected'
        })
    
    @app.route('/health')
    def health():
        return jsonify({
            'status': 'healthy',
            'database': 'not_connected',
            'timestamp': datetime.datetime.now().isoformat()
        })
    
    @app.route('/test-db')
    def test_db():
        try:
            from src.shared.database import get_db
            db = get_db()
            return jsonify({
                'status': 'success',
                'database': 'connected',
                'db_name': db.name,
                'timestamp': datetime.datetime.now().isoformat()
            })
        except Exception as e:
            return jsonify({
                'status': 'error',
                'database': 'failed',
                'error': str(e),
                'timestamp': datetime.datetime.now().isoformat()
            }), 500
    
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