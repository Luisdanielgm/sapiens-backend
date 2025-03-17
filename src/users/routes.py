from flask import request, jsonify
from flask_jwt_extended import create_access_token, jwt_required, get_jwt_identity
from bson.objectid import ObjectId
import json
import logging

from .services import UserService, CognitiveProfileService
from src.shared.standardization import APIBlueprint, APIRoute, ErrorCodes
from src.shared.utils import ensure_json_serializable
from src.shared.constants import ROLES
from src.shared.exceptions import AppException
from src.shared.database import get_db
from src.shared.logging import log_error, log_info

users_bp = APIBlueprint('users', __name__)
user_service = UserService()
cognitive_profile_service = CognitiveProfileService()

@users_bp.route('/register', methods=['POST'])
@APIRoute.standard(required_fields=['email', 'name', 'role'])
def register_user():
    """Registra un nuevo usuario"""
    try:
        data = request.get_json()
        institute_name = data.pop('institute_name', None)
        
        success, result = user_service.register_user(data, institute_name)
        
        if success:
            return APIRoute.success(
                data={"user_id": result},
                message="Usuario registrado exitosamente",
                status_code=201
            )
        return APIRoute.error(
            ErrorCodes.REGISTRATION_ERROR,
            result
        )
    except Exception as e:
        return APIRoute.error(
            ErrorCodes.REGISTRATION_ERROR,
            str(e),
            status_code=500
        )

@users_bp.route('/profile/<email>', methods=['GET'])
@APIRoute.standard(auth_required_flag=True)
def get_user_profile(email):
    """
    Obtiene el perfil completo de un usuario
    
    Args:
        email (str): Email del usuario
    """
    try:
        profile = user_service.get_user_profile(email)
        if profile:
            return APIRoute.success(data=profile)
        return APIRoute.error(
            ErrorCodes.USER_NOT_FOUND,
            f"No se encontró el perfil para el email: {email}",
            status_code=404
        )
    except Exception as e:
        return APIRoute.error(
            ErrorCodes.SERVER_ERROR,
            str(e),
            status_code=500
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
    """Busca usuarios por email parcial"""
    try:
        partial_email = request.args.get('email')
        if not partial_email or '@' not in partial_email:
            return APIRoute.error(
                ErrorCodes.EMAIL_INVALID,
                "Email inválido",
                status_code=400
            )
            
        suggestions = user_service.search_users_by_email(partial_email)
        return APIRoute.success(data={"suggestions": suggestions})
    except Exception as e:
        return APIRoute.error(
            ErrorCodes.SERVER_ERROR,
            str(e),
            status_code=500
        )

@users_bp.route('/info', methods=['GET'])
@APIRoute.standard(auth_required_flag=True)
def get_user_info():
    """Obtiene información básica de un usuario"""
    try:
        email = request.args.get('email')
        if not email:
            return APIRoute.error(
                ErrorCodes.EMAIL_REQUIRED,
                "Se requiere el email del usuario",
                status_code=400
            )

        user = user_service.get_user_info(email)
        if user:
            return APIRoute.success(data={"user": user})
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

@users_bp.route('/student/<email>', methods=['DELETE'])
@APIRoute.standard(auth_required_flag=True)
def delete_student(email):
    """Elimina un estudiante y todos sus datos asociados"""
    try:
        success, message = user_service.delete_student(email)
        if success:
            return APIRoute.success(message=message)
        return APIRoute.error(
            ErrorCodes.DELETE_ERROR,
            message,
            status_code=400
        )
    except Exception as e:
        return APIRoute.error(
            ErrorCodes.DELETE_ERROR,
            str(e),
            status_code=500
        )

@users_bp.route('/profile/cognitive', methods=['GET'])
@APIRoute.standard(auth_required_flag=True)
def get_cognitive_profile():
    """
    Obtiene el perfil cognitivo de un usuario
    
    Args:
        email (query parameter): Email del usuario
        
    Returns:
        200 OK: Perfil cognitivo del usuario
        404 Not Found: Usuario o perfil no encontrado
        500 Internal Server Error: Error en el servidor
    """
    try:
        email = request.args.get('email')
        if not email:
            return APIRoute.error(
                ErrorCodes.MISSING_FIELDS,
                "Se requiere especificar un email",
                status_code=400
            )
            
        log_info(f"Solicitando perfil cognitivo para: {email}", "users.routes")
        profile = cognitive_profile_service.get_cognitive_profile(email)
        
        if profile:
            return APIRoute.success(data={"profile": profile})
        
        # Verificar si el usuario existe pero no tiene perfil
        user_exists = user_service.verify_user_exists(email)
        if user_exists:
            return APIRoute.error(
                ErrorCodes.NOT_FOUND,
                "El usuario existe pero no tiene perfil cognitivo configurado",
                status_code=404
            )
        
        return APIRoute.error(
            ErrorCodes.USER_NOT_FOUND,
            "Perfil no encontrado",
            status_code=404
        )
    except Exception as e:
        log_error(f"Error al obtener perfil cognitivo: {str(e)}", e, "users.routes")
        return APIRoute.error(
            ErrorCodes.SERVER_ERROR,
            str(e),
            status_code=500
        )

@users_bp.route('/profile/cognitive', methods=['PUT'])
@APIRoute.standard(auth_required_flag=True)
@APIRoute.standard(required_fields=['email', 'profile'])
def update_cognitive_profile():
    """
    Actualiza el perfil cognitivo de un usuario por email
    
    Body:
        email: Email del usuario
        profile: Datos del perfil cognitivo (objeto JSON)
        
    Returns:
        200 OK: Perfil actualizado correctamente
        400 Bad Request: Error en la solicitud
        404 Not Found: Usuario no encontrado
        500 Internal Server Error: Error en el servidor
    """
    try:
        data = request.get_json()
        email = data.get('email')
        profile_data = data.get('profile')
        
        # Verificar si el usuario existe
        if not user_service.verify_user_exists(email):
            return APIRoute.error(
                ErrorCodes.USER_NOT_FOUND,
                f"No se encontró usuario con el email: {email}",
                status_code=404
            )
        
        # Verificar formato del perfil
        if not profile_data:
            return APIRoute.error(
                ErrorCodes.INVALID_DATA,
                "Los datos del perfil no pueden estar vacíos",
                status_code=400
            )
        
        # Asegurarse de que el profile_data esté en formato adecuado
        if isinstance(profile_data, dict):
            # Si es un diccionario, lo dejaremos para que el servicio lo maneje
            pass
        elif isinstance(profile_data, str):
            # Si es string, verificar que sea JSON válido
            try:
                json.loads(profile_data)
            except json.JSONDecodeError:
                return APIRoute.error(
                    ErrorCodes.INVALID_DATA,
                    "El perfil debe ser un objeto JSON válido",
                    status_code=400
                )
        else:
            return APIRoute.error(
                ErrorCodes.INVALID_DATA,
                "Formato de perfil inválido",
                status_code=400
            )
        
        log_info(f"Actualizando perfil cognitivo para usuario: {email}", "users.routes")
        success = cognitive_profile_service.update_cognitive_profile(email, profile_data)
        
        if success:
            return APIRoute.success(message="Perfil cognitivo actualizado exitosamente")
        
        return APIRoute.error(
            ErrorCodes.UPDATE_ERROR,
            "Error al actualizar perfil cognitivo",
            status_code=500
        )
    except Exception as e:
        log_error(f"Error al actualizar perfil cognitivo para {email}", e, "users.routes")
        return APIRoute.error(
            ErrorCodes.SERVER_ERROR,
            str(e),
            status_code=500
        )

@users_bp.route('/<user_id>', methods=['GET'])
@APIRoute.standard(auth_required_flag=True)
def get_user(user_id):
    """Obtiene un usuario por su ID"""
    try:
        user = user_service.get_user_by_id(user_id)
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
    """Obtiene el perfil completo de un usuario por ID"""
    try:
        profile = user_service.get_user_profile(user_id)
        if profile:
            return APIRoute.success(data=profile)
        return APIRoute.error(
            ErrorCodes.USER_NOT_FOUND,
            "Perfil no encontrado",
            status_code=404
        )
    except Exception as e:
        return APIRoute.error(
            ErrorCodes.SERVER_ERROR,
            str(e),
            status_code=500
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
