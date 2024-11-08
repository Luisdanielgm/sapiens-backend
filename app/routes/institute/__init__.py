"""
Módulo de rutas para la gestión de institutos educativos.
Incluye rutas para operaciones básicas, programas, periodos y miembros.
"""

from flask import Blueprint
from .basic_routes import register_basic_routes
from .program_routes import register_program_routes
from .period_routes import register_period_routes
from .member_routes import register_member_routes

institute_bp = Blueprint('institute', __name__)

# Registrar todas las sub-rutas
register_basic_routes(institute_bp)
register_program_routes(institute_bp)
register_period_routes(institute_bp)
register_member_routes(institute_bp)

__all__ = ['institute_bp'] 