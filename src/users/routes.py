from flask import request, jsonify
from flask_jwt_extended import create_access_token, jwt_required, get_jwt_identity
from bson.objectid import ObjectId
import json
import logging
from typing import Dict, List
from datetime import datetime

from .services import UserService
from src.shared.standardization import APIBlueprint, APIRoute, ErrorCodes
from src.shared.utils import ensure_json_serializable
from src.shared.constants import ROLES, normalize_role
from src.shared.exceptions import AppException
from src.shared.database import get_db
from src.shared.logging import log_error, log_info, log_warning
from src.profiles.services import ProfileService
from src.members.services import MembershipService

users_bp = APIBlueprint('users', __name__)
user_service = UserService()
profile_service = ProfileService()
membership_service = MembershipService()

@users_bp.route('/register', methods=['POST'])
@APIRoute.standard(required_fields=['email', 'password', 'name', 'role'])
def register():
    """Registro de un nuevo usuario con email y contraseña."""
    try:
        data = request.get_json()
        
        if user_service.verify_user_exists(data['email']):
            return APIRoute.error(ErrorCodes.EMAIL_IN_USE, "El correo electrónico ya está registrado.")

        success, user_id_or_error = user_service.register_user(data)

        if success:
            workspaces = membership_service.get_user_workspaces(user_id_or_error)
            if workspaces:
                first_ws = workspaces[0]
                claims = {
                    "email": data.get("email"),
                    "workspace_id": first_ws["_id"],
                    "institute_id": first_ws["institute_id"],
                    "role": normalize_role(first_ws["role"])
                }
            else:
                claims = {"email": data.get("email")}
            access_token = create_access_token(identity=user_id_or_error, additional_claims=claims)
            user_info = user_service.get_user_info(data['email'])
            if user_info and user_info.get("role"):
                user_info["role"] = normalize_role(user_info["role"])
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
            # --- Flujo de Login con Google Mejorado ---
            import requests
            # Validar ID token
            validation_url = f"https://oauth2.googleapis.com/tokeninfo?id_token={google_credential}"
            response = requests.get(validation_url)
            if response.status_code != 200:
                return APIRoute.error(ErrorCodes.AUTHENTICATION_ERROR, "Token de Google inválido")
            token_data = response.json()
            if token_data.get('email') != email:
                return APIRoute.error(ErrorCodes.AUTHENTICATION_ERROR, "Email no coincide con el token")

            # Buscar usuario
            user = user_service.collection.find_one({"email": email})

            if user:
                # Actualizar proveedor si necesario
                if not user.get("provider"):
                    user_service.collection.update_one(
                        {"_id": user["_id"]},
                        {"$set": {"provider": "google", "updated_at": datetime.now()}}
                    )
            else:
                # Crear nuevo usuario
                new_user_data = {
                    "email": email,
                    "name": token_data.get('name', email.split('@')[0]),
                    "role": "STUDENT",
                    "provider": "google",
                    "created_at": datetime.now(),
                    "updated_at": datetime.now()
                }
                success, user_id = user_service.register_user(new_user_data)  # Ajustar si register_user necesita más campos
                if not success:
                    return APIRoute.error(ErrorCodes.CREATION_ERROR, user_id)
                user = user_service.collection.find_one({"_id": ObjectId(user_id)})

            user_info = {
                "id": str(user["_id"]),
                "name": user["name"],
                "email": user["email"],
                "role": normalize_role(user["role"])
            }
        elif password:
            # --- Flujo de Login con Email/Contraseña ---
            user_info = user_service.login_user(email, password)
        else:
            return APIRoute.error(ErrorCodes.MISSING_FIELDS, "Se requiere contraseña o credencial de Google.")

        # -- Generación de Token --
        if user_info:
            workspaces = membership_service.get_user_workspaces(user_info['id'])
            if workspaces:
                first_ws = workspaces[0]
                claims = {
                    "email": user_info.get("email"),
                    "workspace_id": first_ws["_id"],
                    "institute_id": first_ws["institute_id"],
                    "role": normalize_role(first_ws["role"])
                }
            else:
                claims = {"email": user_info.get("email")}
            access_token = create_access_token(identity=user_info['id'], additional_claims=claims)
            if user_info.get("role"):
                user_info["role"] = normalize_role(user_info["role"])
            return APIRoute.success(
                data={"token": access_token, "user": user_info},
                message="Inicio de sesión exitoso.",
            )
        else:
            return APIRoute.error(ErrorCodes.AUTHENTICATION_ERROR, "Credenciales inválidas o usuario no encontrado.")
            
    except Exception as e:
        log_error(f"Error en el endpoint de login: {str(e)}", e, "users.routes")
        return APIRoute.error(ErrorCodes.SERVER_ERROR, "Ocurrió un error inesperado durante el inicio de sesión.")

# --- (El resto de los endpoints del archivo, que ya están correctos) ---
# ... (get_user_profile, check, search, etc.) ...

@users_bp.route('/check', methods=['POST'])
@APIRoute.standard(required_fields=['email'])
def check_user():
    """Checks if a user with the provided email exists."""
    try:
        data = request.get_json() or {}
        exists = user_service.verify_user_exists(data['email'])
        return APIRoute.success(data={"exists": exists})
    except Exception as e:
        log_error(f"Error verificando usuario: {str(e)}", e, "users.routes")
        return APIRoute.error(ErrorCodes.SERVER_ERROR, "Error interno al verificar el usuario")


@users_bp.route('/profile/cognitive', methods=['GET'])
@APIRoute.standard(auth_required_flag=True)
def get_my_cognitive_profile():
    """Returns the cognitive profile for the current user."""
    try:
        user_id = request.args.get('user_id') or get_jwt_identity()
        profile = profile_service.get_cognitive_profile(user_id)
        if profile:
            return APIRoute.success(data={"profile": profile})
        return APIRoute.error(
            ErrorCodes.RESOURCE_NOT_FOUND,
            "Cognitive profile not found",
            status_code=404,
        )
    except Exception as e:
        log_error(f"Error obteniendo perfil cognitivo: {str(e)}", e, "users.routes")
        return APIRoute.error(ErrorCodes.SERVER_ERROR, "Error interno al obtener el perfil cognitivo")


@users_bp.route('/profile/cognitive', methods=['PUT'])
@APIRoute.standard(auth_required_flag=True, required_fields=['profile_data'])
def update_my_cognitive_profile():
    """Updates the cognitive profile for the current user."""
    try:
        data = request.get_json() or {}
        user_id = get_jwt_identity()
        profile_data = data.get('profile_data', {})
        success = profile_service.update_cognitive_profile(user_id, profile_data)
        if success:
            return APIRoute.success(message="Cognitive profile updated")
        return APIRoute.error(
            ErrorCodes.UPDATE_ERROR,
            "Unable to update cognitive profile",
            status_code=400,
        )
    except Exception as e:
        log_error(f"Error actualizando perfil cognitivo: {str(e)}", e, "users.routes")
        return APIRoute.error(ErrorCodes.SERVER_ERROR, "Error interno al actualizar el perfil cognitivo")

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


@users_bp.route('/switch-institute/<institute_id>', methods=['POST'])
@APIRoute.standard(auth_required_flag=True)
def switch_institute(institute_id):
    """Genera un nuevo JWT para el instituto seleccionado si el usuario es miembro"""
    try:
        user_id = get_jwt_identity()
        if not membership_service.check_institute_member_exists(institute_id, user_id):
            return APIRoute.error(ErrorCodes.UNAUTHORIZED, "No pertenece al instituto indicado")
        user_info = user_service.get_user_info_by_id(user_id)
        claims = {"institute_id": institute_id}
        if user_info and user_info.get("role"):
            claims["role"] = normalize_role(user_info["role"])
        token = create_access_token(identity=user_id, additional_claims=claims)
        return APIRoute.success(data={"token": token})
    except Exception as e:
        log_error(f"Error en switch_institute: {str(e)}", e, "users.routes")
        return APIRoute.error(ErrorCodes.SERVER_ERROR, "No se pudo cambiar de instituto")


@users_bp.route('/forgot-password', methods=['POST'])
@APIRoute.standard(required_fields=['email'])
def forgot_password():
    """Inicia el proceso de recuperación de contraseña."""
    try:
        data = request.get_json()
        email = data.get('email')
        user_service.generate_reset_token(email)
        return APIRoute.success(message="Si el correo existe, se enviaron las instrucciones para restablecer la contraseña.")
    except Exception as e:
        log_error(f"Error en forgot_password: {str(e)}", e, "users.routes")
        return APIRoute.error(ErrorCodes.SERVER_ERROR, "No se pudo procesar la solicitud.")


@users_bp.route('/reset-password', methods=['POST'])
@APIRoute.standard(required_fields=['token', 'password'])
def reset_password():
    """Aplica una nueva contraseña usando el token proporcionado."""
    try:
        data = request.get_json()
        success, msg = user_service.reset_password(data['token'], data['password'])
        if success:
            return APIRoute.success(message=msg)
        else:
            return APIRoute.error(ErrorCodes.UPDATE_ERROR, msg)
    except Exception as e:
        log_error(f"Error en reset_password: {str(e)}", e, "users.routes")
        return APIRoute.error(ErrorCodes.SERVER_ERROR, "No se pudo actualizar la contraseña.")

@users_bp.route('/verify-token', methods=['GET'])
@APIRoute.standard(auth_required_flag=True)
def verify_token():
    return APIRoute.success(message="Token is valid")

@users_bp.route('/verify-token-debug', methods=['GET'])
@APIRoute.standard(auth_required_flag=True)
def verify_token_debug():
    from flask_jwt_extended import get_jwt
    return APIRoute.success(data={"claims": get_jwt()})

@users_bp.route('/me', methods=['GET'])
@APIRoute.standard(auth_required_flag=True)
def get_current_user():
    """Obtiene la información del usuario autenticado actual."""
    try:
        user_id = get_jwt_identity()
        user_info = user_service.get_user_info_by_id(user_id)
        
        if user_info:
            # Normalizar el rol si existe
            if user_info.get("role"):
                user_info["role"] = normalize_role(user_info["role"])
            
            # Obtener workspaces del usuario
            workspaces = membership_service.get_user_workspaces(user_id)
            user_info["workspaces"] = workspaces if workspaces else []
            
            return APIRoute.success(data={"user": user_info})
        else:
            return APIRoute.error(ErrorCodes.RESOURCE_NOT_FOUND, "Usuario no encontrado")
            
    except Exception as e:
        log_error(f"Error obteniendo información del usuario actual: {str(e)}", e, "users.routes")
        return APIRoute.error(ErrorCodes.SERVER_ERROR, "Error interno al obtener la información del usuario")

@users_bp.route('/me/api-keys', methods=['PUT'])
@APIRoute.standard(auth_required_flag=True)
def update_my_api_keys():
    """Updates the API keys for the current user."""
    try:
        data = request.get_json() or {}
        user_id = get_jwt_identity()
        api_keys = data.get('api_keys', {})
        success, message = user_service.update_user(user_id, {"api_keys": api_keys})
        if success:
            return APIRoute.success(message="API keys updated")
        return APIRoute.error(
            ErrorCodes.UPDATE_ERROR,
            message,
            status_code=400,
        )
    except Exception as e:
        log_error(f"Error updating API keys: {str(e)}", e, "users.routes")
        return APIRoute.error(ErrorCodes.SERVER_ERROR, "Error interno al actualizar las claves de API")

@users_bp.route('/me/api-keys', methods=['GET'])
@APIRoute.standard(auth_required_flag=True)
def get_my_api_keys():
    """Gets the API keys for the current user."""
    try:
        user_id = get_jwt_identity()
        api_keys = user_service.get_user_api_keys(user_id)
        
        if api_keys is not None:
            return APIRoute.success(data={"api_keys": api_keys})
        else:
            return APIRoute.error(ErrorCodes.RESOURCE_NOT_FOUND, "Usuario no encontrado")
            
    except Exception as e:
        log_error(f"Error getting API keys: {str(e)}", e, "users.routes")
        return APIRoute.error(ErrorCodes.SERVER_ERROR, "Error interno al obtener las claves de API")

@users_bp.route('/search', methods=['GET', 'OPTIONS'])
def search_users():
    """
    Busca usuarios por email parcial.
    
    Query Parameters:
        email: Email parcial o completo a buscar
    """
    # Manejar preflight OPTIONS antes de cualquier validación
    if request.method == 'OPTIONS':
        return "", 200
    
    # Aplicar autenticación solo para GET
    from src.shared.decorators import auth_required
    from src.shared.decorators import handle_errors
    
    @handle_errors
    @auth_required
    def _search_users():
        try:
            email = request.args.get('email', '').strip()
            
            if not email:
                return APIRoute.error(
                    ErrorCodes.MISSING_FIELDS,
                    "El parámetro 'email' es requerido",
                    status_code=400
                )
            
            # Buscar usuarios que coincidan con el email parcial
            users = user_service.collection.find(
                {"email": {"$regex": email, "$options": "i"}},
                {"email": 1, "name": 1, "_id": 1, "picture": 1}
            ).limit(10)  # Limitar a 10 resultados
            
            results = []
            for user in users:
                results.append({
                    "id": str(user["_id"]),
                    "email": user.get("email", ""),
                    "name": user.get("name", ""),
                    "picture": user.get("picture", "")
                })
            
            return APIRoute.success(data={"users": results})
                
        except Exception as e:
            log_error(f"Error buscando usuarios: {str(e)}", e, "users.routes")
            return APIRoute.error(ErrorCodes.SERVER_ERROR, "Error interno al buscar usuarios")
    
    return _search_users()
