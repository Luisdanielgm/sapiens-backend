from flask import Blueprint
from .basic_routes import register_basic_routes
from .module_routes import register_module_routes
from .topic_routes import register_topic_routes
from .evaluation_routes import register_evaluation_routes

study_plan_bp = Blueprint('study_plan', __name__)

# Registrar todas las sub-rutas
register_basic_routes(study_plan_bp)
register_module_routes(study_plan_bp)
register_topic_routes(study_plan_bp)
register_evaluation_routes(study_plan_bp)  # Solo rutas de calificaciones de estudiantes

__all__ = ['study_plan_bp'] 