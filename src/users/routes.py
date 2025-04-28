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

users_bp = APIBlueprint('users', __name__)
user_service = UserService()
cognitive_profile_service = CognitiveProfileService()
profile_service = ProfileService()

@users_bp.route('/register', methods=['POST'])
@APIRoute.standard(required_fields=['email', 'name', 'role'])
def register_user():
    """
    Registra un nuevo usuario en el sistema.
    
    Body:
        email: Email del usuario
        name: Nombre del usuario
        role: Rol del usuario (STUDENT, TEACHER, ADMIN, INSTITUTE_ADMIN)
        picture: URL de la imagen de perfil (opcional)
        institute_name: Nombre del instituto (requerido para INSTITUTE_ADMIN)
    """
    data = request.get_json()
    
    # Mapear camelCase a snake_case para compatibilidad con frontend
    if 'birthDate' in data:
        data['birth_date'] = data.pop('birthDate')
    if 'instituteName' in data:
        data['institute_name'] = data.pop('instituteName')
    
    # Validar campos
    if data.get('role') == 'INSTITUTE_ADMIN' and not data.get('institute_name'):
        return APIRoute.error(
            ErrorCodes.MISSING_FIELDS, 
            "Se requiere el nombre del instituto para el rol INSTITUTE_ADMIN",
            status_code=400
        )
        
    success, result = user_service.register_user(data, data.get('institute_name'))
    
    if success:
        return APIRoute.success(
            data={"id": result},
            message="Usuario registrado correctamente",
            status_code=201
        )
    else:
        return APIRoute.error(
            ErrorCodes.BAD_REQUEST,
            result,
            status_code=400
        )

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
        return APIRoute.success(message=message)
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
        return APIRoute.success(message="Perfil cognitivo actualizado correctamente")
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
@APIRoute.standard(required_fields=['email'])
def login():
    """Login de usuario y generación de token JWT"""
    try:
        data = request.get_json()
        email = data.get('email')
        password = data.get('password')
        google_login = data.get('google_login', False)
        google_credential = data.get('credential')
        
        # Verificar si es login normal o con Google
        if google_login:
            if not email or not google_credential:
                return APIRoute.error(
                    ErrorCodes.MISSING_FIELDS,
                    "Email y credential son requeridos para inicio de sesión con Google",
                    status_code=400
                )
                
            # Aquí se implementaría la lógica de verificación del token de Google
            # Por ahora, simplemente buscamos al usuario por email
            db = get_db()
            user = db.users.find_one({"email": email})
            
            if not user:
                return APIRoute.error(
                    ErrorCodes.USER_NOT_FOUND,
                    "Usuario no encontrado",
                    status_code=404
                )
        else:
            # Login normal con contraseña
            if not email or not password:
                return APIRoute.error(
                    ErrorCodes.MISSING_FIELDS,
                    "Email y contraseña son requeridos",
                    status_code=400
                )
            
            # Verificar credenciales
            db = get_db()
            user = db.users.find_one({"email": email})
            
            if not user or not user_service.verify_password(password, user.get('password', '')):
                return APIRoute.error(
                    ErrorCodes.AUTHENTICATION_ERROR,
                    "Credenciales inválidas",
                    status_code=401
                )
        
        # Generar token
        access_token = create_access_token(identity=str(user['_id']))
        
        return APIRoute.success(
            data={
                "token": access_token,
                "user": {
                    "id": str(user['_id']),
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
