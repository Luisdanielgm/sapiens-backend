from flask import request, jsonify
from flask_jwt_extended import create_access_token, jwt_required, get_jwt_identity
from bson.objectid import ObjectId
import json
import logging
from typing import Dict, List

from .services import UserService, CognitiveProfileService
from src.shared.standardization import APIBlueprint, APIRoute, ErrorCodes
from src.shared.utils import ensure_json_serializable
from src.shared.constants import ROLES
from src.shared.exceptions import AppException
from src.shared.database import get_db
from src.shared.logging import log_error, log_info, log_warning
from src.profiles.services import ProfileService
from src.members.services import MembershipService

users_bp = APIBlueprint('users', __name__)
user_service = UserService()
cognitive_profile_service = CognitiveProfileService()
profile_service = ProfileService()
membership_service = MembershipService()

@users_bp.route('/register', methods=['POST'])
@APIRoute.standard(required_fields=['email', 'password', 'name', 'role'])
def register():
    """Registro de un nuevo usuario con email y contraseña."""
    try:
        data = request.get_json()
        
        if user_service.verify_user_exists(data['email']):
            return APIRoute.error(ErrorCodes.ALREADY_EXISTS, "El correo electrónico ya está registrado.")

        success, user_id_or_error = user_service.register_user(data)

        if success:
            access_token = create_access_token(identity=user_id_or_error)
            user_info = user_service.get_user_info(data['email'])
            return APIRoute.success(
                data={"token": access_token, "user": user_info},
                message="Usuario registrado exitosamente.",
                status_code=201
            )
        else:
            return APIRoute.error(ErrorCodes.CREATION_ERROR, user_id_or_error)
    except Exception as e:
        log_error(f"Error en el endpoint de registro: {str(e)}", e, "users.routes")
        return APIRoute.error(ErrorCodes.SERVER_ERROR, "Ocurrió un error inesperado durante el registro.")

@users_bp.route('/login', methods=['POST'])
@APIRoute.standard(required_fields=['email', 'password'])
def login():
    """Login de usuario con email/contraseña y generación de token JWT."""
    try:
        data = request.get_json()
        email = data.get('email')
        password = data.get('password')

        user_info = user_service.login_user(email, password)

        if user_info:
            access_token = create_access_token(identity=user_info['id'])
            return APIRoute.success(
                data={"token": access_token, "user": user_info},
                message="Inicio de sesión exitoso."
            )
        else:
            return APIRoute.error(ErrorCodes.AUTHENTICATION_ERROR, "Credenciales inválidas o el usuario se registró con un proveedor social.")
            
    except Exception as e:
        log_error(f"Error en el endpoint de login: {str(e)}", e, "users.routes")
        return APIRoute.error(ErrorCodes.SERVER_ERROR, "Ocurrió un error inesperado durante el inicio de sesión.")

# --- (El resto de los endpoints del archivo, que ya están correctos) ---
# ... (get_user_profile, check, search, etc.) ...

@users_bp.route('/my-institutes', methods=['GET'])
@APIRoute.standard(auth_required_flag=True)
def get_my_institutes():
    """
    Obtiene la lista de institutos a los que pertenece el usuario autenticado,
    incluyendo su rol en cada uno.
    """
    try:
        user_id = get_jwt_identity()
        institutes = membership_service.get_user_institutes(user_id)
        institutes = ensure_json_serializable(institutes)
        return APIRoute.success(data={"institutes": institutes})
    except Exception as e:
        log_error(f"Error obteniendo los institutos del usuario: {str(e)}", e, "users.routes")
        return APIRoute.error(ErrorCodes.SERVER_ERROR, "Ocurrió un error al recuperar los institutos.")
