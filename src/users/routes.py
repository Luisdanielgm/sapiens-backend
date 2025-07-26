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
        
        # Verificar si el usuario ya existe
        if user_service.verify_user_exists(data['email']):
            return APIRoute.error(ErrorCodes.ALREADY_EXISTS, "El correo electrónico ya está registrado.")

        success, user_id_or_error = user_service.register_user(data)

        if success:
            # Generar token de sesión inmediatamente después del registro
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

@users_bp.route('/profile/<email>', methods=['GET'])
@APIRoute.standard(auth_required_flag=True)
def get_user_profile(email):
    """
    Obtiene el perfil completo de un usuario.
    
    Args:
        email: Email del usuario
    """
    profile = profile_service.get_user_profile(email)
    
    if profile:
        return APIRoute.success(data={"profile": profile})
    else:
        return APIRoute.error(
            ErrorCodes.RESOURCE_NOT_FOUND,
            "Perfil de usuario no encontrado",
            status_code=404
        )

@users_bp.route('/check', methods=['POST'])
@APIRoute.standard(required_fields=['email', 'name', 'picture'])
def verify_user():
    """Verifica si un usuario existe por su email"""
    try:
        data = request.get_json()
        email = data.get('email')
        
        if not email:
            return APIRoute.error(
                ErrorCodes.MISSING_FIELDS,
                "El campo email es requerido",
                status_code=400
            )
            
        user_exists = user_service.verify_user_exists(email)
        return APIRoute.success(data={'userExists': user_exists})
    except Exception as e:
        return APIRoute.error(
            ErrorCodes.SERVER_ERROR,
            str(e),
            status_code=500
        )

@users_bp.route('/search', methods=['GET'])
@APIRoute.standard(auth_required_flag=True)
def search_users():
    """
    Busca usuarios por email parcial.
    
    Query params:
        email: Email parcial para buscar
    """
    email = request.args.get('email', '')
    
    if not email or len(email) < 3:
        return APIRoute.error(
            ErrorCodes.BAD_REQUEST,
            "Se requiere al menos 3 caracteres para buscar",
            status_code=400
        )
        
    results = user_service.search_users_by_email(email)
    
    return APIRoute.success(
        data={"users": results},
        message=f"Se encontraron {len(results)} usuarios"
    )

@users_bp.route('/user-info', methods=['GET'])
@APIRoute.standard(auth_required_flag=True)
def get_user_info():
    """
    Obtiene información básica de un usuario.
    
    Args:
        email: Email del usuario
    """
    email = request.args.get('email')
    if not email:
        return APIRoute.error(
            ErrorCodes.MISSING_FIELDS,
            "El campo email es requerido",
            status_code=400
        )
    user_info = user_service.get_user_info(email)
    
    if user_info:
        return APIRoute.success(data={"user": user_info})
    else:
        return APIRoute.error(
            ErrorCodes.RESOURCE_NOT_FOUND,
            "Usuario no encontrado",
            status_code=404
        )

@users_bp.route('/student/<email>', methods=['DELETE'])
@APIRoute.standard(auth_required_flag=True, roles=[ROLES["ADMIN"], ROLES["INSTITUTE_ADMIN"]])
def delete_student(email):
    """
    Elimina un estudiante y todos sus datos asociados.
    
    Args:
        email: Email del estudiante a eliminar
    """
    success, message = user_service.delete_student(email)
    
    if success:
        return APIRoute.success(data={"deleted": True}, message=message)
    else:
        return APIRoute.error(
            ErrorCodes.BAD_REQUEST,
            message,
            status_code=400
        )

@users_bp.route('/cognitive-profile', methods=['GET'])
@APIRoute.standard(auth_required_flag=True)
def get_cognitive_profile():
    """
    Obtiene el perfil cognitivo de un estudiante.
    Este endpoint está obsoleto y será eliminado en futuras versiones.
    Use /profiles/cognitive/<user_id_or_email> en su lugar.
    
    Query params:
        email: Email del estudiante
    """
    email = request.args.get('email')
    if not email:
        return APIRoute.error(
            ErrorCodes.MISSING_FIELDS,
            "Se requiere el parámetro 'email'",
            status_code=400
        )
        
    log_warning(
        "Se está utilizando un endpoint obsoleto (GET /users/cognitive-profile). " +
        "Utilice GET /profiles/cognitive/<user_id_or_email> en su lugar.",
        "users.routes"
    )
        
    # Redireccionar al nuevo servicio centralizado de perfiles
    profile = profile_service.get_cognitive_profile(email)
    
    if profile:
        return APIRoute.success(data={"profile": profile})
    else:
        return APIRoute.error(
            ErrorCodes.RESOURCE_NOT_FOUND,
            "Perfil cognitivo no encontrado",
            status_code=404
        )

@users_bp.route('/cognitive-profile', methods=['PUT'])
@APIRoute.standard(auth_required_flag=True, required_fields=['email', 'profile_data'])
def update_cognitive_profile():
    """
    Actualiza el perfil cognitivo de un estudiante.
    Este endpoint está obsoleto y será eliminado en futuras versiones.
    Use PUT /profiles/cognitive en su lugar.
    
    Body:
        email: Email del estudiante
        profile_data: Datos del perfil cognitivo
    """
    data = request.get_json()
    email = data.get('email')
    profile_data = data.get('profile_data')
    
    log_warning(
        "Se está utilizando un endpoint obsoleto (PUT /users/cognitive-profile). " +
        "Utilice PUT /profiles/cognitive en su lugar.",
        "users.routes"
    )
    
    # Redireccionar al nuevo servicio centralizado de perfiles
    success = profile_service.update_cognitive_profile(email, profile_data)

    if success:
        success_message = "Perfil cognitivo actualizado correctamente"
        return APIRoute.success(data={"updated": True}, message=success_message)
    else:
        return APIRoute.error(
            ErrorCodes.BAD_REQUEST,
            "Error actualizando perfil cognitivo",
            status_code=400
        )

@users_bp.route('/email/<email>', methods=['GET'])
@APIRoute.standard(auth_required_flag=True)
def get_user_by_email(email):
    """Obtiene un usuario por su correo electrónico"""
    try:
        user = user_service.get_user_by_email(email)
        if user:
            return APIRoute.success(data=user)
        return APIRoute.error(
            ErrorCodes.USER_NOT_FOUND,
            "Usuario no encontrado",
            status_code=404
        )
    except Exception as e:
        return APIRoute.error(
            ErrorCodes.SERVER_ERROR,
            str(e),
            status_code=500
        )

@users_bp.route('/profile/<user_id>', methods=['GET'])
@APIRoute.standard(auth_required_flag=True)
def get_user_profile_by_id(user_id):
    """
    Obtiene el perfil completo de un usuario por su ID.
    
    Args:
        user_id: ID del usuario
    """
    profile = profile_service.get_user_profile(user_id)
    
    if profile:
        return APIRoute.success(data={"profile": profile})
    else:
        return APIRoute.error(
            ErrorCodes.RESOURCE_NOT_FOUND,
            "Perfil de usuario no encontrado",
            status_code=404
        )

@users_bp.route('/login', methods=['POST'])
@APIRoute.standard(required_fields=['email', 'password'])
def login():
    """Login de usuario con email/contraseña y generación de token JWT."""
    try:
        data = request.get_json()
        email = data.get('email')
        password = data.get('password')

        # Usar el nuevo servicio de login
        user_info = user_service.login_user(email, password)

        if user_info:
            access_token = create_access_token(identity=user_info['id'])
            return APIRoute.success(
                data={"token": access_token, "user": user_info},
                message="Inicio de sesión exitoso."
            )
        else:
            # Manejar también el caso de login social (si se quiere mantener)
            # Por ahora, solo devolvemos error de credenciales.
            return APIRoute.error(ErrorCodes.AUTHENTICATION_ERROR, "Credenciales inválidas o el usuario se registró con un proveedor social.")
            
    except Exception as e:
        log_error(f"Error en el endpoint de login: {str(e)}", e, "users.routes")
        return APIRoute.error(ErrorCodes.SERVER_ERROR, "Ocurrió un error inesperado durante el inicio de sesión.")

@users_bp.route('/by-email', methods=['GET'])
@APIRoute.standard(auth_required_flag=True)
def get_user_by_email_jwt():
    """Obtener información de usuario por email"""
    try:
        email = request.args.get('email')
        if not email:
            return APIRoute.error(
                ErrorCodes.EMAIL_REQUIRED,
                "Email requerido",
                status_code=400
            )
        
        db = get_db()
        user = db.users.find_one({"email": email})
        
        if not user:
            return APIRoute.error(
                ErrorCodes.USER_NOT_FOUND,
                "Usuario no encontrado",
                status_code=404
            )
        
        return APIRoute.success(
            data={
                "user": {
                    "_id": str(user['_id']),
                    "name": user.get('name', ''),
                    "email": user.get('email', ''),
                    "role": user.get('role', '')
                }
            }
        )
    except Exception as e:
        return APIRoute.error(
            ErrorCodes.SERVER_ERROR,
            str(e),
            status_code=500
        )

@users_bp.route('/verify-token', methods=['GET'])
@APIRoute.standard(auth_required_flag=True)
def verify_token():
    """Verifica si el token JWT es válido"""
    try:
        # Si llegamos hasta aquí, significa que el token es válido
        # porque el decorador auth_required ya lo verificó
        
        # Obtener información del usuario autenticado
        user_id = request.user_id
        db = get_db()
        user = db.users.find_one({"_id": ObjectId(user_id)})
        
        if not user:
            return APIRoute.error(
                ErrorCodes.USER_NOT_FOUND,
                "Usuario no encontrado",
                status_code=404
            )
        
        return APIRoute.success(
            data={
                "user": {
                    "id": str(user['_id']),
                    "name": user.get('name', ''),
                    "email": user.get('email', ''),
                    "role": user.get('role', '')
                }
            },
            message="Token válido"
        )
    except Exception as e:
        import traceback
        import logging
        logging.getLogger(__name__).error(f"Error en verify_token: {str(e)}\n{traceback.format_exc()}")
        return APIRoute.error(
            ErrorCodes.SERVER_ERROR,
            str(e),
            status_code=500
        )

@users_bp.route('/my-institutes', methods=['GET'])
@APIRoute.standard(auth_required_flag=True)
def get_my_institutes():
    """
    Obtiene la lista de institutos a los que pertenece el usuario autenticado,
    incluyendo su rol en cada uno.
    """
    try:
        user_id = get_jwt_identity()
        
        # Usar el servicio de membresía para obtener los institutos
        institutes = membership_service.get_user_institutes(user_id)
        
        # Asegurarse de que los datos son serializables
        institutes = ensure_json_serializable(institutes)
        
        return APIRoute.success(data={"institutes": institutes})
            
    except Exception as e:
        log_error(f"Error obteniendo los institutos del usuario: {str(e)}", e, "users.routes")
        return APIRoute.error(ErrorCodes.SERVER_ERROR, "Ocurrió un error al recuperar los institutos.")
