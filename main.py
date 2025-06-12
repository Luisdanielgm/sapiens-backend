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

# Importar Blueprints
from src.users.routes import users_bp
from src.institute.routes import institute_bp
from src.academic.routes import academic_bp
from src.classes.routes import classes_bp
from src.study_plans.routes import study_plan_bp
from src.virtual.routes import virtual_bp
from src.invitations.routes import invitations_bp
from src.members.routes import members_bp
from src.analytics.routes import analytics_bp
from src.dashboards.routes import dashboards_bp
from src.indigenous_languages.routes import indigenous_languages_bp
from src.profiles.routes import profiles_bp
from src.student_individual_content.routes import student_individual_content_bp
from src.resources.routes import resources_bp
from src.deep_research.routes import deep_research_bp
from src.topic_resources.routes import topic_resources_bp
from src.content.routes import content_bp  # Sistema de contenido unificado

def create_app(config_object=active_config):
    """
    Crea y configura la aplicación Flask
    """
    app = Flask(APP_NAME)
    
    # Aplicar configuración
    app.config.from_object(config_object)
    
    # Configurar CORS
    CORS(app, resources={
        r"/api/*": {
            "origins": app.config["CORS_ORIGINS"],
            "methods": ["GET", "POST", "PUT", "DELETE", "OPTIONS"],
            "allow_headers": ["Content-Type", "Authorization"],
            "supports_credentials": True,
            "automatic_options": True
        }
    })

    # Desactivar modo estricto para slashes en URLs
    app.url_map.strict_slashes = False
    
    # Inicializar JWT
    jwt = JWTManager(app)

    # Sistema unificado de logging para endpoints
    @app.after_request
    def log_response(response):
        # Verificar el nivel de logging configurado
        api_logging = app.config.get('API_LOGGING', 'basic')
        
        if api_logging == 'none':
            # No hacer logging
            return response
            
        # Datos básicos para todos los niveles excepto 'none'
        method = request.method
        path = request.path
        status = response.status_code
        
        # Logging básico para todos los endpoints
        if api_logging == 'basic':
            # Solo registrar información básica de la solicitud
            logger.info(f"API: {method} {path} - Status: {status}")
            return response
            
        # Logging detallado (api_logging == 'detailed')
        # Obtener datos de la solicitud
        request_data = None
        if request.method in ['POST', 'PUT', 'PATCH'] and request.is_json:
            try:
                request_data = request.get_json()
            except Exception:
                request_data = "Error al parsear JSON"
        elif request.form:
            request_data = dict(request.form)
        elif request.args:
            request_data = dict(request.args)
            # Para solicitudes GET, los argumentos en la URL son relevantes
            if request.method == 'GET':
                logger.info(f"URL Query Params: {request_data}")
                # No establecer request_data para evitar duplicación en el log
                request_data = None
            
        # Obtener datos de la respuesta
        response_data = None
        if response.content_type == 'application/json':
            try:
                # Guardar los datos originales
                response_data = response.get_json()
            except Exception:
                response_data = response.get_data(as_text=True)
        
        # Endpoints específicos que queremos monitorear especialmente
        special_endpoints = ['/api/users/check', '/api/users/login', '/api/users/register']
        is_special = any(endpoint in path for endpoint in special_endpoints)
        
        # Logging detallado
        logger.info(f"API REQUEST: {method} {path}")
        if request_data and (is_special or api_logging == 'detailed'):
            logger.info(f"Request Data: {request_data}")
            
        logger.info(f"API RESPONSE: {method} {path} - Status: {status}")
        if response_data and (is_special or api_logging == 'detailed'):
            logger.info(f"Response Data: {response_data}")
            
        return response

    # Verificar conexión a la base de datos
    try:
        db = get_db()
        logger.info("Conexión a MongoDB establecida")
        
        # Configurar índices si estamos en modo de desarrollo o la variable de entorno lo indica
        if app.config['DEBUG'] or os.getenv('SETUP_INDEXES', '0') == '1':
            logger.info("Configurando índices de la base de datos...")
            setup_result = setup_database_indexes()
            if setup_result:
                logger.info("Índices configurados correctamente")
            else:
                logger.warning("No se pudieron configurar todos los índices")
    except Exception as e:
        logger.error(f"Error al conectar a MongoDB: {str(e)}")
        # No lanzar error para permitir ejecución aunque la BD no esté disponible
        # Pero registrar claramente que puede haber problemas
        logger.warning("La aplicación se está ejecutando sin conexión a la base de datos. Las operaciones pueden fallar.")
        
    # Registrar manejo de errores global
    @app.errorhandler(500)
    def handle_server_error(error):
        logger.error(f"Error del servidor: {error}")
        return jsonify({
            "success": False,
            "error": "ERROR_SERVIDOR",
            "message": "Error interno del servidor"
        }), 500
        
    @app.errorhandler(404)
    def handle_not_found(error):
        return jsonify({
            "success": False,
            "error": "NOT_FOUND",
            "message": "Recurso no encontrado"
        }), 404
        
    # Registrar handler para AppException para capturar excepciones no manejadas por handle_errors
    @app.errorhandler(Exception)
    def handle_unhandled_exception(error):
        from src.shared.exceptions import AppException
        
        if isinstance(error, AppException):
            response = {
                "success": False,
                "error": error.__class__.__name__,
                "message": str(error.message)
            }
            if hasattr(error, 'details') and error.details:
                response["details"] = error.details
            return jsonify(response), error.code
        
        # Error genérico solo para errores no controlados
        logger.error(f"Error no controlado: {error}")
        return jsonify({
            "success": False,
            "error": "ERROR_SERVIDOR",
            "message": "Error interno del servidor"
        }), 500

    # Registrar Blueprints
    app.register_blueprint(users_bp, url_prefix='/api/users')
    app.register_blueprint(institute_bp, url_prefix='/api/institute')
    app.register_blueprint(academic_bp, url_prefix='/api/academic')
    app.register_blueprint(classes_bp, url_prefix='/api/classes')
    app.register_blueprint(study_plan_bp, url_prefix='/api/study-plan')
    app.register_blueprint(virtual_bp, url_prefix='/api/virtual')
    app.register_blueprint(invitations_bp, url_prefix='/api/invitations')
    app.register_blueprint(members_bp, url_prefix='/api/members')
    app.register_blueprint(analytics_bp, url_prefix='/api/analytics')
    app.register_blueprint(dashboards_bp, url_prefix='/api/dashboards')
    app.register_blueprint(indigenous_languages_bp, url_prefix='/api/translations')
    app.register_blueprint(profiles_bp, url_prefix='/api/profiles')
    app.register_blueprint(student_individual_content_bp, url_prefix='/api/student-content')
    
    # Sistema de contenido unificado (REEMPLAZA games, simulations, quizzes)
    app.register_blueprint(content_bp)  # Ya incluye url_prefix='/api/content'
    
    # Otros sistemas especializados
    app.register_blueprint(resources_bp, url_prefix='/api/resources')
    app.register_blueprint(deep_research_bp, url_prefix='/api/deep-research')
    app.register_blueprint(topic_resources_bp, url_prefix='/api/topic-resources')

    # Alias para rutas de módulos (virtualización) bajo /api/modules para compatibilidad con frontend
    from src.study_plans.routes import get_virtualization_readiness, update_virtualization_settings
    app.add_url_rule(
        '/api/modules/<module_id>/virtualization-readiness',
        endpoint='get_virtualization_readiness_alias',
        view_func=get_virtualization_readiness,
        methods=['GET', 'OPTIONS']
    )
    app.add_url_rule(
        '/api/modules/<module_id>/virtualization-settings',
        endpoint='update_virtualization_settings_alias',
        view_func=update_virtualization_settings,
        methods=['PUT', 'OPTIONS']
    )

    @app.route('/')
    def health_check():
        """Endpoint para verificar la salud de la aplicación"""
        return jsonify({
            "status": "healthy", 
            "version": "1.0.0",
            "env": os.getenv('FLASK_ENV', 'development')
        })

    return app

# Crear la aplicación para que Vercel pueda encontrarla
app = create_app()

if __name__ == '__main__':
    # Cuando se ejecuta directamente (desarrollo local)
    logger.info(f"Iniciando aplicación en modo {os.getenv('FLASK_ENV', 'development')}")
    app.run(
        debug=app.config['DEBUG'], 
        host='0.0.0.0', 
        port=app.config['PORT']
    )