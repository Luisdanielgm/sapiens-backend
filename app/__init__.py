from flask import Flask, jsonify
from flask_cors import CORS

def create_app():
    app = Flask(__name__)
    CORS(app, resources={r"/*": {"origins": ["http://localhost:3000"]}}, supports_credentials=True)

    # Registrar blueprints
    from app.routes.user_routes import user_bp
    from app.routes.classroom_routes import classroom_bp
    from app.routes.content_routes import content_bp
    from app.routes.invitation_routes import invitation_bp
    from app.routes.statistics_routes import statistics_bp
    from app.routes.institute import institute_bp
    from app.routes.profile_routes import profile_bp
    from app.routes.study_plan import study_plan_bp
    from app.routes.virtual_module_routes import virtual_module_bp
    from app.routes.dashboard_routes import dashboard_bp

    app.register_blueprint(user_bp)
    app.register_blueprint(classroom_bp)
    app.register_blueprint(content_bp)
    app.register_blueprint(invitation_bp)
    app.register_blueprint(statistics_bp)
    app.register_blueprint(institute_bp)
    app.register_blueprint(profile_bp)
    app.register_blueprint(study_plan_bp)
    app.register_blueprint(virtual_module_bp)
    app.register_blueprint(dashboard_bp)

    @app.route('/')
    def index():
        return jsonify({"message": "Hello, World!"}), 200

    return app 