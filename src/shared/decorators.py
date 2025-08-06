from functools import wraps
from flask import request, jsonify, current_app
from flask_jwt_extended import verify_jwt_in_request, get_jwt_identity, get_jwt
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
            
            # Obtener información del workspace desde el JWT
            claims = get_jwt()
            request.workspace_id = claims.get("workspace_id")
            request.institute_id = claims.get("institute_id")
            request.workspace_role = claims.get("role")  # Rol específico del workspace
            
            user_main_role = user.get("role")
            request.user_roles = [user_main_role] if user_main_role else []
            
            logger.info(f"Auth_required: Usuario autenticado con ID: {user_id}, Rol global: {user_main_role}, Workspace: {request.workspace_id}, Rol workspace: {request.workspace_role}")
            
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
            
            # 1. Priorizar workspace_role del JWT (más específico)
            workspace_role = getattr(request, 'workspace_role', None)
            if workspace_role and workspace_role in all_roles:
                return f(*args, **kwargs)
            
            # 2. Verificar rol presente en el token (compatibilidad)
            claims = get_jwt()
            token_role = claims.get("role")
            if token_role and token_role in all_roles:
                return f(*args, **kwargs)

            # 3. Verificar rol global del usuario en la base de datos
            user = db.users.find_one({"_id": ObjectId(user_id)})
            if user and "role" in user and user["role"] in all_roles:
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

def workspace_required(f):
    """Decorador para verificar que el usuario tiene un workspace activo"""
    @wraps(f)
    def decorated_function(*args, **kwargs):
        # Verificar que auth_required ha sido ejecutado primero
        if not hasattr(request, 'user_id'):
            return jsonify({
                "success": False,
                "error": "ERROR_AUTENTICACION",
                "message": "Se requiere autenticación"
            }), 401
        
        workspace_id = getattr(request, 'workspace_id', None)
        if not workspace_id:
            return jsonify({
                "success": False,
                "error": "ERROR_WORKSPACE",
                "message": "Se requiere un workspace activo"
            }), 400
        
        return f(*args, **kwargs)
    return decorated_function

def workspace_filter(collection_name, workspace_field='institute_id'):
    """Decorador para filtrar automáticamente por workspace en consultas de base de datos"""
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
            
            # Obtener workspace_id del request
            workspace_id = getattr(request, 'workspace_id', None)
            institute_id = getattr(request, 'institute_id', None)
            
            # Agregar filtro de workspace al request para uso en la función
            if workspace_id and institute_id:
                request.workspace_filter = {workspace_field: ObjectId(institute_id)}
            else:
                request.workspace_filter = {}
            
            return f(*args, **kwargs)
        return decorated_function
    return decorator

def get_auth_user_id():
    """Obtiene el ID del usuario autenticado"""
    return getattr(request, 'user_id', None)

def get_workspace_id():
    """Obtiene el ID del workspace activo"""
    return getattr(request, 'workspace_id', None)

def get_institute_id():
    """Obtiene el ID del instituto del workspace activo"""
    return getattr(request, 'institute_id', None)

def get_workspace_role():
    """Obtiene el rol del usuario en el workspace activo"""
    return getattr(request, 'workspace_role', None)

def get_workspace_filter():
    """Obtiene el filtro de workspace para consultas de base de datos"""
    return getattr(request, 'workspace_filter', {})

def workspace_access_required(f):
    """
    Decorador para verificar que el usuario tiene acceso al workspace especificado en la URL
    Debe usarse después de auth_required
    """
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
        workspace_id = kwargs.get('workspace_id')
        
        if not workspace_id:
            return jsonify({
                "success": False,
                "error": "ERROR_WORKSPACE",
                "message": "ID de workspace requerido"
            }), 400
        
        # Verificar que el usuario tiene acceso al workspace
        db = get_db()
        try:
            membership = db.institute_members.find_one({
                "_id": ObjectId(workspace_id),
                "user_id": ObjectId(user_id)
            })
            
            if not membership:
                return jsonify({
                    "success": False,
                    "error": "ERROR_ACCESO",
                    "message": "No tienes acceso a este workspace"
                }), 403
            
            # Agregar información del workspace al request
            request.current_workspace = membership
            
        except Exception as e:
            return jsonify({
                "success": False,
                "error": "ERROR_SERVIDOR",
                "message": "Error al verificar acceso al workspace"
            }), 500
        
        return f(*args, **kwargs)
    return decorated_function

def workspace_owner_required(f):
    """
    Decorador para verificar que el usuario es propietario del workspace
    Debe usarse después de workspace_access_required
    
    Para workspaces individuales (INDIVIDUAL_STUDENT, INDIVIDUAL_TEACHER):
    - El usuario que tiene acceso es automáticamente el propietario
    
    Para workspaces institucionales (INSTITUTE):
    - Se verifica que el usuario tenga rol de administrador del instituto
    """
    @wraps(f)
    def decorated_function(*args, **kwargs):
        # Verificar que workspace_access_required ha sido ejecutado
        if not hasattr(request, 'current_workspace'):
            return jsonify({
                "success": False,
                "error": "ERROR_CONFIGURACION",
                "message": "Decorador mal configurado: se requiere workspace_access_required"
            }), 500
        
        workspace = request.current_workspace
        workspace_type = workspace.get('workspace_type', 'INSTITUTE')
        
        # Para workspaces individuales, el usuario que tiene acceso es el propietario
        if workspace_type in ['INDIVIDUAL_STUDENT', 'INDIVIDUAL_TEACHER']:
            # Si llegó hasta aquí, ya pasó workspace_access_required, por lo tanto es el propietario
            return f(*args, **kwargs)
        
        # Para workspaces institucionales, verificar rol de administrador
        user_role = workspace.get('role')
        if user_role not in ['INSTITUTE_ADMIN', 'ADMIN']:
            return jsonify({
                "success": False,
                "error": "ERROR_PERMISO",
                "message": "Solo el administrador del instituto puede realizar esta acción"
            }), 403
        
        return f(*args, **kwargs)
    return decorated_function

def workspace_type_required(allowed_types):
    """
    Decorador para verificar que el workspace es de un tipo específico
    Debe usarse después de workspace_access_required
    
    Args:
        allowed_types: Lista de tipos de workspace permitidos (ej: ['INDIVIDUAL', 'INSTITUTE'])
                      'INDIVIDUAL' es compatible con 'INDIVIDUAL_STUDENT' e 'INDIVIDUAL_TEACHER'
    """
    if isinstance(allowed_types, str):
        allowed_types = [allowed_types]
    
    def decorator(f):
        @wraps(f)
        def decorated_function(*args, **kwargs):
            # Verificar que workspace_access_required ha sido ejecutado
            if not hasattr(request, 'current_workspace'):
                return jsonify({
                    "success": False,
                    "error": "ERROR_CONFIGURACION",
                    "message": "Decorador mal configurado: se requiere workspace_access_required"
                }), 500
            
            workspace = request.current_workspace
            workspace_type = workspace.get('workspace_type', 'INSTITUTE')
            
            # Expandir tipos permitidos para compatibilidad
            expanded_allowed_types = []
            for allowed_type in allowed_types:
                if allowed_type == 'INDIVIDUAL':
                    # 'INDIVIDUAL' incluye ambos tipos específicos
                    expanded_allowed_types.extend(['INDIVIDUAL_STUDENT', 'INDIVIDUAL_TEACHER'])
                else:
                    expanded_allowed_types.append(allowed_type)
            
            if workspace_type not in expanded_allowed_types:
                return jsonify({
                    "success": False,
                    "error": "ERROR_TIPO_WORKSPACE",
                    "message": f"Esta acción solo está permitida en workspaces de tipo: {', '.join(allowed_types)}"
                }), 403
            
            return f(*args, **kwargs)
        return decorated_function
    return decorator

def workspace_permission_required(permission):
    """
    Decorador para verificar que el usuario tiene un permiso específico en el workspace
    Debe usarse después de workspace_access_required
    
    Args:
        permission: Permiso requerido (ej: 'can_edit', 'can_delete', 'can_manage_content')
    """
    def decorator(f):
        @wraps(f)
        def decorated_function(*args, **kwargs):
            # Verificar que workspace_access_required ha sido ejecutado
            if not hasattr(request, 'current_workspace'):
                return jsonify({
                    "success": False,
                    "error": "ERROR_CONFIGURACION",
                    "message": "Decorador mal configurado: se requiere workspace_access_required"
                }), 500
            
            workspace = request.current_workspace
            permissions = workspace.get('permissions', {})
            
            if not permissions.get(permission, False):
                return jsonify({
                    "success": False,
                    "error": "ERROR_PERMISO",
                    "message": f"No tienes el permiso '{permission}' en este workspace"
                }), 403
            
            return f(*args, **kwargs)
        return decorated_function
    return decorator

def workspace_role_required(required_roles):
    """
    Decorador para verificar que el usuario tiene uno de los roles requeridos en el workspace
    Debe usarse después de workspace_access_required
    
    Args:
        required_roles: Lista de roles requeridos o rol único (ej: ['OWNER', 'ADMIN'] o 'OWNER')
    """
    if isinstance(required_roles, str):
        required_roles = [required_roles]
    
    def decorator(f):
        @wraps(f)
        def decorated_function(*args, **kwargs):
            # Verificar que workspace_access_required ha sido ejecutado
            if not hasattr(request, 'current_workspace'):
                return jsonify({
                    "success": False,
                    "error": "ERROR_CONFIGURACION",
                    "message": "Decorador mal configurado: se requiere workspace_access_required"
                }), 500
            
            workspace = request.current_workspace
            user_role = workspace.get('role')
            
            if user_role not in required_roles:
                return jsonify({
                    "success": False,
                    "error": "ERROR_PERMISO",
                    "message": f"Se requiere uno de los siguientes roles: {', '.join(required_roles)}"
                }), 403
            
            return f(*args, **kwargs)
        return decorated_function
    return decorator

def workspace_data_isolation_required(f):
    """
    Decorador para asegurar el aislamiento de datos por workspace_type
    Debe usarse después de workspace_access_required
    
    Este decorador agrega filtros automáticos para asegurar que:
    - INDIVIDUAL_STUDENT: Solo ve sus propios datos
    - INDIVIDUAL_TEACHER: Solo ve datos de su clase personal
    - INSTITUTE: Ve datos del instituto completo
    """
    @wraps(f)
    def decorated_function(*args, **kwargs):
        # Verificar que workspace_access_required ha sido ejecutado
        if not hasattr(request, 'current_workspace'):
            return jsonify({
                "success": False,
                "error": "ERROR_CONFIGURACION",
                "message": "Decorador mal configurado: se requiere workspace_access_required"
            }), 500
        
        from src.shared.middleware import apply_workspace_data_filters
        
        workspace = request.current_workspace
        user_id = request.user_id
        
        # Usar la función de middleware para aplicar filtros
        base_query = {}
        isolation_filters = apply_workspace_data_filters(base_query, workspace, user_id)
        
        # Agregar filtros al request para uso en la función
        request.isolation_filters = isolation_filters
        
        return f(*args, **kwargs)
    return decorated_function