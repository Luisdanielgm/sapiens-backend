from flask import Flask, jsonify
from flask_cors import CORS
from flask_jwt_extended import JWTManager
from src.shared.database import get_db
from config import active_config
import logging
import os

# Configuración de logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

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
from src.indigenous_languages.routes import indigenous_languages_bp
from src.profiles.routes import profiles_bp
from src.student_individual_content.routes import student_individual_content_bp
from src.games.routes import games_bp
from src.simulations.routes import simulations_bp

def create_app(config_object=active_config):
    """
    Crea y configura la aplicación Flask
    """
    app = Flask(__name__)
    
    # Aplicar configuración
    app.config.from_object(config_object)
    
    # Configurar CORS
    CORS(app, resources={
        r"/api/*": {
            "origins": app.config["CORS_ORIGINS"],
            "methods": ["GET", "POST", "PUT", "DELETE", "OPTIONS"],
            "allow_headers": ["Content-Type", "Authorization"],
            "supports_credentials": True
        }
    })

    # Desactivar modo estricto para slashes en URLs
    app.url_map.strict_slashes = False
    
    # Inicializar JWT
    jwt = JWTManager(app)

    # Verificar conexión a la base de datos
    try:
        db = get_db()
        logger.info("Conexión a MongoDB establecida")
    except Exception as e:
        logger.error(f"Error al conectar a MongoDB: {str(e)}")
        # No lanzar error para permitir ejecución aunque la BD no esté disponible
        
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
    app.register_blueprint(indigenous_languages_bp, url_prefix='/api/translations')
    app.register_blueprint(profiles_bp, url_prefix='/api/profiles')
    app.register_blueprint(student_individual_content_bp, url_prefix='/api/student-content')
    app.register_blueprint(games_bp, url_prefix='/api/games')
    app.register_blueprint(simulations_bp, url_prefix='/api/simulations')

    @app.route('/')
    def health_check():
        """Endpoint para verificar la salud de la aplicación"""
        return jsonify({
            "status": "healthy", 
            "version": "1.0.0",
            "env": os.getenv('FLASK_ENV', 'development')
        })

    return app

if __name__ == '__main__':
    app = create_app()
    logger.info(f"Iniciando aplicación en modo {os.getenv('FLASK_ENV', 'development')}")
    app.run(
        debug=app.config['DEBUG'], 
        host='0.0.0.0', 
        port=app.config['PORT']
    )