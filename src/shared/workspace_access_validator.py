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
            plan = self.db.study_plans_per_subject.find_one({"_id": ObjectId(plan_id)})
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
    
    def _validate_resource_access(self, resource: Dict[str, Any], workspace_info: Dict[str, Any], user_id: str) -> bool:
        """Valida acceso a un recurso según el workspace actual"""
        try:
            workspace_type = workspace_info.get('workspace_type')
            workspace_id = workspace_info.get('workspace_id')
            institute_id = workspace_info.get('institute_id')
            
            if workspace_type == 'INSTITUTE':
                # En workspaces institucionales, validar por institute_id si existe
                if resource.get('institute_id') and str(resource.get('institute_id')) != str(institute_id):
                    return False
                return True
            
            if workspace_type == 'INDIVIDUAL_TEACHER':
                # En workspaces individuales de profesor, validar por workspace_id si existe
                if resource.get('workspace_id') and str(resource.get('workspace_id')) != str(workspace_id):
                    return False
                # Validar autor cuando aplique
                if resource.get('author_id') and str(resource.get('author_id')) != str(user_id):
                    return False
                return True
            
            if workspace_type == 'INDIVIDUAL_STUDENT':
                # En workspaces individuales de estudiante, solo recursos propios
                if resource.get('author_id') and str(resource.get('author_id')) != str(user_id):
                    return False
                # Si es plan personal, debe coincidir workspace
                if resource.get('is_personal') and resource.get('workspace_id') and str(resource.get('workspace_id')) != str(workspace_id):
                    return False
                return True
            
            return False
        except Exception:
            return False
    
    def _apply_workspace_filters(self, base_query: Dict[str, Any], workspace_info: Dict[str, Any], user_id: str) -> Dict[str, Any]:
        """
        Aplica filtros según tipo de workspace para consultas de recursos
        """
        query = dict(base_query)  # Copia para no mutar el original
        workspace_type = workspace_info.get('workspace_type')
        workspace_id = workspace_info.get('workspace_id')
        institute_id = workspace_info.get('institute_id')
        
        if workspace_type == 'INSTITUTE':
            if institute_id:
                query['institute_id'] = ObjectId(institute_id)
        elif workspace_type == 'INDIVIDUAL_TEACHER':
            if workspace_id:
                query['workspace_id'] = ObjectId(workspace_id)
                query['author_id'] = ObjectId(user_id)
        elif workspace_type == 'INDIVIDUAL_STUDENT':
            # Solo recursos de planes personales del usuario
            personal_plans = list(self.db.study_plans_per_subject.find(
                {"author_id": ObjectId(user_id), "is_personal": True},
                {"_id": 1}
            ))
            plan_ids = [plan["_id"] for plan in personal_plans]
            if plan_ids:
                query['study_plan_id'] = {"$in": plan_ids}
            else:
                query['_id'] = {"$in": []}
        return query