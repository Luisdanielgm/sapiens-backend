from typing import Dict, List, Optional, Any
from bson import ObjectId
from src.shared.database import get_db
from src.shared.exceptions import AppException

class WorkspaceAccessValidator:
    """
    Servicio centralizado para validar acceso a recursos basado en workspace_type
    """
    
    def __init__(self):
        self.db = get_db()
    
    def validate_module_access(self, module_id: str, workspace_info: Dict[str, Any], user_id: str) -> bool:
        """
        Valida si un usuario tiene acceso a un módulo virtual específico
        
        Args:
            module_id: ID del módulo virtual
            workspace_info: Información del workspace actual
            user_id: ID del usuario
            
        Returns:
            bool: True si tiene acceso, False en caso contrario
        """
        try:
            module = self.db.virtual_modules.find_one({"_id": ObjectId(module_id)})
            if not module:
                return False
            
            return self._validate_resource_access(module, workspace_info, user_id)
        except Exception:
            return False
    
    def validate_topic_access(self, topic_id: str, workspace_info: Dict[str, Any], user_id: str) -> bool:
        """
        Valida si un usuario tiene acceso a un tópico virtual específico
        
        Args:
            topic_id: ID del tópico virtual
            workspace_info: Información del workspace actual
            user_id: ID del usuario
            
        Returns:
            bool: True si tiene acceso, False en caso contrario
        """
        try:
            topic = self.db.virtual_topics.find_one({"_id": ObjectId(topic_id)})
            if not topic:
                return False
            
            return self._validate_resource_access(topic, workspace_info, user_id)
        except Exception:
            return False
    
    def validate_class_access(self, class_id: str, workspace_info: Dict[str, Any], user_id: str) -> bool:
        """
        Valida si un usuario tiene acceso a una clase específica
        
        Args:
            class_id: ID de la clase
            workspace_info: Información del workspace actual
            user_id: ID del usuario
            
        Returns:
            bool: True si tiene acceso, False en caso contrario
        """
        try:
            class_data = self.db.classes.find_one({"_id": ObjectId(class_id)})
            if not class_data:
                return False
            
            return self._validate_resource_access(class_data, workspace_info, user_id)
        except Exception:
            return False
    
    def validate_study_plan_access(self, plan_id: str, workspace_info: Dict[str, Any], user_id: str) -> bool:
        """
        Valida si un usuario tiene acceso a un plan de estudio específico
        
        Args:
            plan_id: ID del plan de estudio
            workspace_info: Información del workspace actual
            user_id: ID del usuario
            
        Returns:
            bool: True si tiene acceso, False en caso contrario
        """
        try:
            plan = self.db.study_plans.find_one({"_id": ObjectId(plan_id)})
            if not plan:
                return False
            
            return self._validate_resource_access(plan, workspace_info, user_id)
        except Exception:
            return False
    
    def get_accessible_modules(self, workspace_info: Dict[str, Any], user_id: str, 
                              additional_filters: Dict[str, Any] = None) -> List[Dict[str, Any]]:
        """
        Obtiene todos los módulos virtuales accesibles para el usuario en su workspace
        
        Args:
            workspace_info: Información del workspace actual
            user_id: ID del usuario
            additional_filters: Filtros adicionales para la consulta
            
        Returns:
            List[Dict[str, Any]]: Lista de módulos accesibles
        """
        base_query = additional_filters or {}
        filtered_query = self._apply_workspace_filters(base_query, workspace_info, user_id)
        
        return list(self.db.virtual_modules.find(filtered_query))
    
    def get_accessible_topics(self, workspace_info: Dict[str, Any], user_id: str,
                             additional_filters: Dict[str, Any] = None) -> List[Dict[str, Any]]:
        """
        Obtiene todos los tópicos virtuales accesibles para el usuario en su workspace
        
        Args:
            workspace_info: Información del workspace actual
            user_id: ID del usuario
            additional_filters: Filtros adicionales para la consulta
            
        Returns:
            List[Dict[str, Any]]: Lista de tópicos accesibles
        """
        base_query = additional_filters or {}
        filtered_query = self._apply_workspace_filters(base_query, workspace_info, user_id)
        
        return list(self.db.virtual_topics.find(filtered_query))
    
    def get_accessible_classes(self, workspace_info: Dict[str, Any], user_id: str,
                              additional_filters: Dict[str, Any] = None) -> List[Dict[str, Any]]:
        """
        Obtiene todas las clases accesibles para el usuario en su workspace
        
        Args:
            workspace_info: Información del workspace actual
            user_id: ID del usuario
            additional_filters: Filtros adicionales para la consulta
            
        Returns:
            List[Dict[str, Any]]: Lista de clases accesibles
        """
        base_query = additional_filters or {}
        filtered_query = self._apply_workspace_filters(base_query, workspace_info, user_id)
        
        return list(self.db.classes.find(filtered_query))
    
    def validate_workspace_operation(self, operation: str, workspace_info: Dict[str, Any], 
                                   user_role: str) -> bool:
        """
        Valida si un usuario puede realizar una operación específica en su workspace
        
        Args:
            operation: Tipo de operación (create, edit, delete, manage, etc.)
            workspace_info: Información del workspace actual
            user_role: Rol del usuario en el workspace
            
        Returns:
            bool: True si puede realizar la operación, False en caso contrario
        """
        workspace_type = workspace_info.get('workspace_type')
        
        # Definir permisos por tipo de workspace y rol
        permissions = {
            'INDIVIDUAL_STUDENT': {
                'OWNER': ['create', 'edit', 'delete', 'view'],
                'STUDENT': ['view']
            },
            'INDIVIDUAL_TEACHER': {
                'OWNER': ['create', 'edit', 'delete', 'manage', 'view'],
                'TEACHER': ['create', 'edit', 'view']
            },
            'INSTITUTE': {
                'INSTITUTE_ADMIN': ['create', 'edit', 'delete', 'manage', 'view'],
                'TEACHER': ['create', 'edit', 'view'],
                'STUDENT': ['view']
            }
        }
        
        workspace_permissions = permissions.get(workspace_type, {})
        user_permissions = workspace_permissions.get(user_role, [])
        
        return operation in user_permissions
    
    def _validate_resource_access(self, resource_data: Dict[str, Any], 
                                 workspace_info: Dict[str, Any], user_id: str) -> bool:
        """
        Método interno para validar acceso a un recurso específico
        
        Args:
            resource_data: Datos del recurso
            workspace_info: Información del workspace actual
            user_id: ID del usuario
            
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
    
    def _apply_workspace_filters(self, base_query: Dict[str, Any], 
                                workspace_info: Dict[str, Any], user_id: str) -> Dict[str, Any]:
        """
        Aplica filtros de workspace a una consulta de base de datos
        
        Args:
            base_query: Query base de MongoDB
            workspace_info: Información del workspace actual
            user_id: ID del usuario
            
        Returns:
            Dict[str, Any]: Query modificado con filtros de workspace
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
            # Puede acceder a recursos que creó o de su clase personal
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
            # Puede acceder a recursos del mismo instituto
            workspace_institute_id = workspace_info.get('institute_id')
            if workspace_institute_id:
                base_query['institute_id'] = ObjectId(workspace_institute_id)
        
        return base_query