from flask import request, jsonify
from flask_jwt_extended import create_access_token, jwt_required, get_jwt_identity
from bson.objectid import ObjectId
import json
import logging
from typing import Dict, List
from datetime import datetime

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
@APIRoute.standard(required_fields=['email'])
def login():
    """
    Maneja el login tanto para usuarios locales (email/contraseña) como para
    proveedores sociales (Google).
    """
    try:
        data = request.get_json()
        email = data.get('email')
        password = data.get('password')
        google_credential = data.get('credential') # Para login con Google

        user_info = None

        if google_credential:
            # --- Flujo de Login con Google (Corregido) ---
            user = user_service.collection.find_one({
                "email": email,
                # El usuario debe ser de Google o no tener un proveedor definido (para usuarios antiguos)
                "$or": [
                    {"provider": "google"},
                    {"provider": {"$exists": False}}
                ]
            })

            if user:
                # Si el usuario es antiguo y no tiene proveedor, actualizarlo
                if not user.get("provider"):
                    user_service.collection.update_one(
                        {"_id": user["_id"]},
                        {"$set": {"provider": "google", "updated_at": datetime.now()}}
                    )

                user_info = {
                    "id": str(user["_id"]),
                    "name": user["name"],
                    "email": user["email"],
                    "role": user["role"]
                }
        elif password:
            # --- Flujo de Login con Email/Contraseña ---
            user_info = user_service.login_user(email, password)
        else:
            return APIRoute.error(ErrorCodes.MISSING_FIELDS, "Se requiere contraseña o credencial de Google.")

        # -- Generación de Token --
        if user_info:
            access_token = create_access_token(identity=user_info['id'])
            return APIRoute.success(
                data={"token": access_token, "user": user_info},
                message="Inicio de sesión exitoso."
            )
        else:
            return APIRoute.error(ErrorCodes.AUTHENTICATION_ERROR, "Credenciales inválidas o usuario no encontrado.")
            
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
