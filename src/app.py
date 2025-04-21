from flask import Flask, jsonify, request
from flask_cors import CORS

from src.shared.database import get_db, init_db
from src.auth.routes import auth_bp
from src.users.routes import users_bp
from src.resources.routes import resources_bp
from src.study_plans.routes import study_plan_bp
from src.gamification.routes import gamification_bp
from src.topics.routes import topics_bp
from src.games.routes import games_bp
from src.simulations.routes import simulations_bp
from src.virtual.routes import virtual_bp
from src.topic_resources.routes import topic_resources_bp

from src.shared.standardization import standardize_response

def create_app(test_config=None):
    app = Flask(__name__)
    
    # Configuración CORS
    CORS(app, resources={r"/*": {"origins": "*"}})
    
    # Inicialización de la base de datos
    init_db()
    
    # Registrar blueprints
    app.register_blueprint(auth_bp, url_prefix='/api/auth')
    app.register_blueprint(users_bp, url_prefix='/api/users')
    app.register_blueprint(resources_bp, url_prefix='/api/resources')
    app.register_blueprint(study_plan_bp, url_prefix='/api/study-plan')
    app.register_blueprint(gamification_bp, url_prefix='/api/gamification')
    app.register_blueprint(topics_bp, url_prefix='/api/topics')
    app.register_blueprint(games_bp, url_prefix='/api/games')
    app.register_blueprint(simulations_bp, url_prefix='/api/simulations')
    app.register_blueprint(virtual_bp, url_prefix='/api/virtual')
    
    # Registrar nuevo blueprint para topic_resources
    app.register_blueprint(topic_resources_bp, url_prefix='/api/topic-resources')
    
    # Standardize all responses
    app.after_request(standardize_response)
    
    @app.route('/')
    def home():
        return jsonify({"message": "Bienvenido a SapiensAI API"})
    
    return app

app = create_app() 