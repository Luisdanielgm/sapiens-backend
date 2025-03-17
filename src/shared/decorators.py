from functools import wraps
from flask import request, jsonify, current_app
from flask_jwt_extended import verify_jwt_in_request, get_jwt_identity
import jwt
from bson.objectid import ObjectId
from src.shared.database import get_db
from src.shared.constants import ROLES
from src.shared.exceptions import AppException
import logging

def handle_errors(f):
    """Decorador para manejar excepciones en las rutas"""
    @wraps(f)
    def decorated_function(*args, **kwargs):
        try:
            return f(*args, **kwargs)
        except AppException as e:
            response = {
                "success": False,
                "error": e.__class__.__name__,
                "message": str(e.message)
            }
            # Incluir detalles si existen
            if hasattr(e, 'details') and e.details:
                response["details"] = e.details
            return jsonify(response), e.code
        except Exception as e:
            current_app.logger.error(f"Error inesperado: {str(e)}")
            return jsonify({
                "success": False,
                "error": "ERROR_SERVIDOR",
                "message": "Error interno del servidor"
            }), 500
    return decorated_function

def auth_required(f):
    """Decorador para requerir autenticación mediante JWT"""
    @wraps(f)
    def decorated_function(*args, **kwargs):
        logger = logging.getLogger(__name__)
        
        try:
            # Usar flask_jwt_extended para verificar el token
            verify_jwt_in_request()
            # Guardar el ID del usuario para usarlo en la función
            user_id = get_jwt_identity()
            logger.info(f"Auth_required: Token JWT válido para usuario con ID: {user_id}")
            
            # Verificar que el usuario existe en la base de datos
            db = get_db()
            user = db.users.find_one({"_id": ObjectId(user_id)})
            
            if not user:
                logger.warning(f"Auth_required: Usuario con ID {user_id} no encontrado en la base de datos")
                return jsonify({
                    "success": False,
                    "error": "ERROR_AUTENTICACION",
                    "message": "Usuario no encontrado"
                }), 401
                
            # Guardar información relevante del usuario en el request
            request.user_id = user_id
            request.user_role = user.get("role")
            logger.info(f"Auth_required: Usuario autenticado con rol: {request.user_role}")
            
            return f(*args, **kwargs)
        except Exception as e:
            logger.error(f"Auth_required: Error de autenticación: {str(e)}")
            return jsonify({
                "success": False,
                "error": "ERROR_AUTENTICACION",
                "message": "Error de autenticación"
            }), 401
    return decorated_function

def role_required(required_roles):
    """
    Decorador para verificar que el usuario tiene al menos uno de los roles requeridos.
    Debe usarse después de auth_required.
    
    Args:
        required_roles: Puede ser un string con el nombre del rol o una lista de roles.
                       También acepta valores del diccionario ROLES o las claves.
    """
    # Convertir a lista si es un string
    if isinstance(required_roles, str):
        required_roles = [required_roles]
    
    # Normalizar roles (convertir cualquier clave de ROLES a su valor)
    normalized_roles = []
    for role in required_roles:
        if role in ROLES.keys():
            normalized_roles.append(ROLES[role])
        else:
            normalized_roles.append(role)
    
    # Agregar versiones en mayúsculas de los roles normalizados
    uppercase_roles = [role.upper() for role in normalized_roles]
    # Incluir ambas versiones para la comparación
    all_roles = normalized_roles + uppercase_roles
    
    def decorator(f):
        @wraps(f)
        def decorated_function(*args, **kwargs):
            # Verificar que auth_required ha sido ejecutado primero
            if not hasattr(request, 'user_id'):
                return jsonify({
                    "success": False,
                    "error": "ERROR_AUTENTICACION",
                    "message": "Se requiere autenticación"
                }), 401
            
            user_id = request.user_id
            db = get_db()
            
            # Primero verificar si el usuario tiene el rol directamente en su documento
            user = db.users.find_one({"_id": ObjectId(user_id)})
            if user and "role" in user:
                # Comprobar tanto en minúsculas como en mayúsculas
                if user["role"] in all_roles:
                    return f(*args, **kwargs)
            
            # Roles que pueden ser verificados en institutos
            institute_roles = ['ADMIN', 'INSTITUTE_ADMIN', 'TEACHER', 'STUDENT']
            institute_roles_upper = [role.upper() for role in institute_roles]
            all_institute_roles = institute_roles + institute_roles_upper
            
            # Verificar si la ruta contiene un institute_id
            institute_id = kwargs.get('institute_id')
            if institute_id:
                for role in all_roles:
                    if role in all_institute_roles:
                        # Verificar si el usuario tiene el rol en el instituto
                        member = db.institute_members.find_one({
                            "institute_id": ObjectId(institute_id),
                            "user_id": ObjectId(user_id),
                            "role": role
                        })
                        
                        if member:
                            return f(*args, **kwargs)
            
            # Verificar si la ruta contiene un class_id
            class_id = kwargs.get('class_id')
            if class_id:
                for role in all_roles:
                    if role.lower() in ['TEACHER', 'STUDENT']:
                        # Verificar si el usuario es miembro de la clase con el rol requerido
                        member = db.class_members.find_one({
                            "class_id": ObjectId(class_id),
                            "user_id": ObjectId(user_id),
                            "role": role
                        })
                        
                        if member:
                            return f(*args, **kwargs)
            
            # Si llegamos hasta aquí, el usuario no tiene los permisos necesarios
            return jsonify({
                "success": False, 
                "error": "ERROR_PERMISO",
                "message": "No tiene los permisos necesarios"
            }), 403
            
        return decorated_function
    return decorator

def validate_json(required_fields=None, schema=None):
    """Decorador para validar JSON en las solicitudes"""
    def decorator(f):
        @wraps(f)
        def decorated_function(*args, **kwargs):
            # Verificar que la solicitud contiene JSON
            if not request.is_json:
                return jsonify({
                    "success": False,
                    "error": "ERROR_FORMATO",
                    "message": "Se esperaba contenido JSON"
                }), 400
            
            data = request.get_json()
            
            # Validar campos requeridos si se especifican
            if required_fields:
                missing_fields = [field for field in required_fields if field not in data]
                if missing_fields:
                    return jsonify({
                        "success": False,
                        "error": "CAMPOS_FALTANTES",
                        "message": f"Faltan campos requeridos: {', '.join(missing_fields)}"
                    }), 400
            
            # Validar esquema si se especifica
            if schema:
                try:
                    from src.shared.validators import validate_schema
                    is_valid, errors = validate_schema(data, schema)
                    if not is_valid:
                        return jsonify({
                            "success": False,
                            "error": "DATOS_INVALIDOS",
                            "message": "Datos inválidos",
                            "details": errors
                        }), 400
                except ImportError:
                    pass
            
            return f(*args, **kwargs)
        return decorated_function
    return decorator

def get_auth_user_id():
    """Obtiene el ID del usuario autenticado"""
    return getattr(request, 'user_id', None) 