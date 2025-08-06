from flask import request, g
from bson import ObjectId
from src.shared.database import get_db
from functools import wraps
import logging

logger = logging.getLogger(__name__)

class WorkspaceFilterMiddleware:
    """
    Middleware para aplicar filtros automáticos basados en el tipo de workspace
    y garantizar el aislamiento de datos entre workspaces individuales e institucionales.
    """
    
    def __init__(self, app=None):
        self.app = app
        if app is not None:
            self.init_app(app)
    
    def init_app(self, app):
        """Inicializa el middleware con la aplicación Flask"""
        app.before_request(self.before_request)
    
    def before_request(self):
        """Ejecuta antes de cada request para configurar filtros de workspace"""
        try:
            # Solo aplicar filtros si el usuario está autenticado
            if not hasattr(request, 'user_id'):
                return
            
            # Obtener información del workspace actual
            workspace_id = getattr(request, 'workspace_id', None)
            workspace_type = getattr(request, 'workspace_type', None)
            institute_id = getattr(request, 'institute_id', None)
            
            if not workspace_id or not workspace_type:
                return
            
            # Configurar filtros automáticos basados en el tipo de workspace
            self._setup_workspace_filters(workspace_type, institute_id, workspace_id)
            
        except Exception as e:
            logger.error(f"Error en WorkspaceFilterMiddleware: {str(e)}")
            # No interrumpir el request por errores en el middleware
            pass
    
    def _setup_workspace_filters(self, workspace_type, institute_id, workspace_id):
        """Configura los filtros automáticos según el tipo de workspace"""
        
        # Inicializar objeto de filtros en el request
        if not hasattr(request, 'workspace_filters'):
            request.workspace_filters = {}
        
        if workspace_type in ['INDIVIDUAL_STUDENT', 'INDIVIDUAL_TEACHER']:
            # Para workspaces individuales: filtrar por institute_id del workspace
            request.workspace_filters.update({
                'institute_filter': {'institute_id': ObjectId(institute_id)},
                'class_filter': {'institute_id': ObjectId(institute_id)},
                'content_filter': {'institute_id': ObjectId(institute_id)},
                'study_plan_filter': {'institute_id': ObjectId(institute_id)},
                'analytics_filter': {'institute_id': ObjectId(institute_id)}
            })
            
            # Para estudiantes individuales, filtrar también por user_id en algunos casos
            if workspace_type == 'INDIVIDUAL_STUDENT':
                user_id = getattr(request, 'user_id', None)
                if user_id:
                    request.workspace_filters.update({
                        'personal_filter': {'user_id': ObjectId(user_id)},
                        'progress_filter': {'user_id': ObjectId(user_id)}
                    })
        
        elif workspace_type == 'INSTITUTE':
            # Para workspaces institucionales: filtrar por institute_id
            request.workspace_filters.update({
                'institute_filter': {'institute_id': ObjectId(institute_id)},
                'class_filter': {'institute_id': ObjectId(institute_id)},
                'content_filter': {'institute_id': ObjectId(institute_id)},
                'study_plan_filter': {'institute_id': ObjectId(institute_id)},
                'analytics_filter': {'institute_id': ObjectId(institute_id)}
            })
        
        # Agregar filtro general de workspace
        request.workspace_filters['workspace_filter'] = {
            'workspace_id': ObjectId(workspace_id)
        }

def apply_workspace_filter(collection_name, custom_filter=None):
    """
    Decorador para aplicar automáticamente filtros de workspace a consultas de base de datos
    
    Args:
        collection_name: Nombre de la colección (ej: 'classes', 'content', 'study_plans')
        custom_filter: Filtro personalizado adicional (opcional)
    """
    def decorator(f):
        @wraps(f)
        def decorated_function(*args, **kwargs):
            # Obtener filtros del request
            workspace_filters = getattr(request, 'workspace_filters', {})
            
            # Determinar qué filtro aplicar según la colección
            filter_key = f"{collection_name}_filter"
            if filter_key not in workspace_filters:
                filter_key = 'institute_filter'  # Fallback al filtro de instituto
            
            base_filter = workspace_filters.get(filter_key, {})
            
            # Combinar con filtro personalizado si se proporciona
            if custom_filter:
                base_filter.update(custom_filter)
            
            # Agregar el filtro al request para uso en la función
            request.auto_filter = base_filter
            
            return f(*args, **kwargs)
        return decorated_function
    return decorator

def get_workspace_filter(collection_name='default'):
    """
    Obtiene el filtro de workspace apropiado para una colección específica
    
    Args:
        collection_name: Nombre de la colección
    
    Returns:
        dict: Filtro de MongoDB apropiado para la colección
    """
    workspace_filters = getattr(request, 'workspace_filters', {})
    
    # Mapeo de colecciones a filtros específicos
    filter_mapping = {
        'classes': 'class_filter',
        'content': 'content_filter',
        'study_plans': 'study_plan_filter',
        'analytics': 'analytics_filter',
        'progress': 'progress_filter',
        'personal': 'personal_filter'
    }
    
    filter_key = filter_mapping.get(collection_name, 'institute_filter')
    return workspace_filters.get(filter_key, {})

def ensure_workspace_isolation():
    """
    Decorador para garantizar el aislamiento de datos entre workspaces
    Debe usarse en endpoints que manejan datos sensibles
    """
    def decorator(f):
        @wraps(f)
        def decorated_function(*args, **kwargs):
            # Verificar que el workspace está configurado
            workspace_type = getattr(request, 'workspace_type', None)
            workspace_id = getattr(request, 'workspace_id', None)
            
            if not workspace_type or not workspace_id:
                from flask import jsonify
                return jsonify({
                    "success": False,
                    "error": "ERROR_WORKSPACE",
                    "message": "Workspace no configurado correctamente"
                }), 400
            
            # Configurar aislamiento estricto
            if not hasattr(request, 'workspace_filters'):
                request.workspace_filters = {}
            
            # Agregar validación adicional para workspaces individuales
            if workspace_type in ['INDIVIDUAL_STUDENT', 'INDIVIDUAL_TEACHER']:
                user_id = getattr(request, 'user_id', None)
                if user_id:
                    request.isolation_filter = {
                        'user_id': ObjectId(user_id),
                        'workspace_id': ObjectId(workspace_id)
                    }
            
            return f(*args, **kwargs)
        return decorated_function
    return decorator

# Funciones de utilidad para usar en servicios
def get_current_workspace_info():
    """
    Obtiene información completa del workspace actual
    
    Returns:
        dict: Información del workspace (id, type, institute_id, etc.)
    """
    return {
        'workspace_id': getattr(request, 'workspace_id', None),
        'workspace_type': getattr(request, 'workspace_type', None),
        'institute_id': getattr(request, 'institute_id', None),
        'user_id': getattr(request, 'user_id', None),
        'workspace_role': getattr(request, 'workspace_role', None)
    }

def validate_resource_access(resource_data: dict, workspace_info: dict, user_id: str) -> bool:
    """
    Valida si un usuario tiene acceso a un recurso específico basado en su workspace_type
    
    Args:
        resource_data: Datos del recurso (debe incluir campos como user_id, institute_id, class_id, etc.)
        workspace_info: Información del workspace actual
        user_id: ID del usuario que solicita acceso
        
    Returns:
        bool: True si tiene acceso, False en caso contrario
    """
    workspace_type = workspace_info.get('workspace_type')
    
    if not workspace_type:
        return False
    
    # Para workspaces de estudiantes individuales
    if workspace_type == 'INDIVIDUAL_STUDENT':
        # Solo puede acceder a sus propios recursos
        return (
            str(resource_data.get('user_id')) == user_id or
            str(resource_data.get('student_id')) == user_id
        )
    
    # Para workspaces de profesores individuales
    elif workspace_type == 'INDIVIDUAL_TEACHER':
        # Puede acceder a recursos que creó o de su clase personal
        workspace_class_id = workspace_info.get('class_id')
        return (
            str(resource_data.get('created_by')) == user_id or
            str(resource_data.get('user_id')) == user_id or
            (workspace_class_id and str(resource_data.get('class_id')) == workspace_class_id)
        )
    
    # Para workspaces institucionales
    elif workspace_type == 'INSTITUTE':
        # Puede acceder a recursos del mismo instituto
        workspace_institute_id = workspace_info.get('institute_id')
        return (
            workspace_institute_id and 
            str(resource_data.get('institute_id')) == workspace_institute_id
        )
    
    return False

def apply_workspace_data_filters(base_query: dict, workspace_info: dict, user_id: str) -> dict:
    """
    Aplica filtros de datos basados en el workspace_type para asegurar el aislamiento
    
    Args:
        base_query: Query base de MongoDB
        workspace_info: Información del workspace actual
        user_id: ID del usuario
        
    Returns:
        dict: Query modificado con filtros de workspace
    """
    workspace_type = workspace_info.get('workspace_type')
    
    if not workspace_type:
        return base_query
    
    # Para workspaces de estudiantes individuales
    if workspace_type == 'INDIVIDUAL_STUDENT':
        # Solo sus propios datos
        base_query['$or'] = [
            {'user_id': ObjectId(user_id)},
            {'student_id': ObjectId(user_id)}
        ]
    
    # Para workspaces de profesores individuales
    elif workspace_type == 'INDIVIDUAL_TEACHER':
        # Solo datos que creó o de su clase personal
        workspace_class_id = workspace_info.get('class_id')
        or_conditions = [
            {'created_by': ObjectId(user_id)},
            {'user_id': ObjectId(user_id)}
        ]
        
        if workspace_class_id:
            or_conditions.append({'class_id': ObjectId(workspace_class_id)})
        
        base_query['$or'] = or_conditions
    
    # Para workspaces institucionales
    elif workspace_type == 'INSTITUTE':
        # Solo datos del instituto
        workspace_institute_id = workspace_info.get('institute_id')
        if workspace_institute_id:
            base_query['institute_id'] = ObjectId(workspace_institute_id)
    
    return base_query

def is_individual_workspace():
    """
    Verifica si el workspace actual es individual
    
    Returns:
        bool: True si es workspace individual
    """
    workspace_type = getattr(request, 'workspace_type', None)
    return workspace_type in ['INDIVIDUAL_STUDENT', 'INDIVIDUAL_TEACHER']

def is_institute_workspace():
    """
    Verifica si el workspace actual es institucional
    
    Returns:
        bool: True si es workspace institucional
    """
    workspace_type = getattr(request, 'workspace_type', None)
    return workspace_type == 'INSTITUTE'