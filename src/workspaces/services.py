from typing import Dict, List, Optional, Tuple, Any
from bson import ObjectId
from datetime import datetime
from src.shared.database import get_db
from src.shared.exceptions import AppException
from src.classes.services import ClassService
from src.study_plans.services import StudyPlanService
from src.members.services import MembershipService

class WorkspaceService:
    """Servicio para gestión de workspaces y lógica de negocio relacionada"""
    
    def __init__(self):
        self.db = get_db()
        self.class_service = ClassService()
        self.study_plan_service = StudyPlanService()
        self.membership_service = MembershipService()
        
        # Tipos de workspace válidos
        self.VALID_WORKSPACE_TYPES = [
            "INSTITUTE",
            "INDIVIDUAL_STUDENT", 
            "INDIVIDUAL_TEACHER"
        ]
        
        # Esquema de nombres por tipo
        self.WORKSPACE_NAME_SCHEMAS = {
            "INDIVIDUAL_STUDENT": "Aprendizaje de {name}",
            "INDIVIDUAL_TEACHER": "Clases de {name}",
            "INSTITUTE": "{name}"  # Usa el nombre del instituto directamente
        }
    
    def validate_workspace_type(self, workspace_type: str) -> bool:
        """Validar que el tipo de workspace sea válido"""
        return workspace_type in self.VALID_WORKSPACE_TYPES
    
    def generate_workspace_name(self, workspace_type: str, user_name: str, custom_name: str = None) -> str:
        """Generar nombre de workspace según el esquema establecido"""
        if custom_name:
            return custom_name
            
        if workspace_type not in self.WORKSPACE_NAME_SCHEMAS:
            raise AppException(f"Tipo de workspace inválido: {workspace_type}", AppException.BAD_REQUEST)
            
        schema = self.WORKSPACE_NAME_SCHEMAS[workspace_type]
        return schema.format(name=user_name)
    
    def get_generic_institute(self) -> Dict[str, Any]:
        """Obtener el instituto genérico 'Academia Sapiens'"""
        generic_institute = self.db.institutes.find_one({"name": "Academia Sapiens"})
        
        if not generic_institute:
            # Crear instituto genérico si no existe
            generic_institute_data = {
                "name": "Academia Sapiens",
                "description": "Instituto genérico para workspaces individuales",
                "created_at": datetime.utcnow(),
                "status": "active",
                "type": "generic"
            }
            
            result = self.db.institutes.insert_one(generic_institute_data)
            generic_institute_data["_id"] = result.inserted_id
            return generic_institute_data
            
        return generic_institute
    
    def validate_workspace_ownership(self, workspace_id: str, user_id: str) -> bool:
        """Validar que el usuario es propietario del workspace"""
        try:
            membership = self.db.institute_members.find_one({
                "_id": ObjectId(workspace_id),
                "user_id": ObjectId(user_id)
            })
            return membership is not None
        except Exception:
            return False
    
    def get_workspace_by_id(self, workspace_id: str, user_id: str) -> Dict[str, Any]:
        """Obtener workspace específico validando pertenencia del usuario"""
        try:
            # Buscar membership del usuario
            membership = self.db.institute_members.find_one({
                "_id": ObjectId(workspace_id),
                "user_id": ObjectId(user_id)
            })
            
            if not membership:
                raise AppException("Workspace no encontrado o sin acceso", AppException.NOT_FOUND)
            
            # Obtener información del instituto
            institute = self.db.institutes.find_one({"_id": ObjectId(membership["institute_id"])})
            
            if not institute:
                raise AppException("Instituto asociado no encontrado", AppException.NOT_FOUND)
            
            # Construir respuesta del workspace
            workspace_data = {
                "workspace_id": str(membership["_id"]),
                "workspace_type": membership.get("workspace_type", "INSTITUTE"),
                "workspace_name": membership.get("workspace_name", institute["name"]),
                "role_in_workspace": membership["role"],
                "institute_id": str(membership["institute_id"]),
                "class_id": str(membership["class_id"]) if membership.get("class_id") else None,
                "status": membership.get("status", "active"),
                "joined_at": membership.get("joined_at", membership.get("created_at")),
                "metadata": {
                    "institute_name": institute["name"],
                    "institute_description": institute.get("description", ""),
                    "permissions": self._get_workspace_permissions(membership["role"], membership.get("workspace_type"))
                }
            }
            
            return workspace_data
            
        except Exception as e:
            if isinstance(e, AppException):
                raise
            raise AppException(f"Error al obtener workspace: {str(e)}", AppException.INTERNAL_ERROR)
    
    def create_personal_workspace(self, user_id: str, workspace_data: Dict[str, Any]) -> Tuple[bool, str, Dict[str, Any]]:
        """Crear workspace personal para usuario"""
        try:
            workspace_type = workspace_data.get("workspace_type")
            workspace_name = workspace_data.get("workspace_name")
            
            # Validaciones
            if not self.validate_workspace_type(workspace_type):
                raise AppException(f"Tipo de workspace inválido: {workspace_type}", AppException.BAD_REQUEST)
            
            if workspace_type == "INSTITUTE":
                raise AppException("No se pueden crear workspaces de tipo INSTITUTE manualmente", AppException.BAD_REQUEST)
            
            if not workspace_name or not workspace_name.strip():
                raise AppException("El nombre del workspace es requerido", AppException.BAD_REQUEST)
            
            # Verificar que el usuario no tenga ya un workspace del mismo tipo
            existing_workspace = self.db.institute_members.find_one({
                "user_id": ObjectId(user_id),
                "workspace_type": workspace_type
            })
            
            if existing_workspace:
                raise AppException(f"Ya tienes un workspace de tipo {workspace_type}", AppException.CONFLICT)
            
            # Obtener instituto genérico
            generic_institute = self.get_generic_institute()
            
            # Obtener información del usuario
            user = self.db.users.find_one({"_id": ObjectId(user_id)})
            if not user:
                raise AppException("Usuario no encontrado", AppException.NOT_FOUND)
            
            # Determinar rol según tipo de workspace
            role = "student" if workspace_type == "INDIVIDUAL_STUDENT" else "teacher"
            
            # Crear membership
            membership_data = {
                "institute_id": generic_institute["_id"],
                "user_id": ObjectId(user_id),
                "workspace_type": workspace_type,
                "workspace_name": workspace_name.strip(),
                "role": role,
                "status": "active",
                "joined_at": datetime.utcnow(),
                "created_at": datetime.utcnow()
            }
            
            # Si es profesor individual, crear clase personal
            if workspace_type == "INDIVIDUAL_TEACHER":
                class_data = {
                    "name": workspace_name.strip(),
                    "description": f"Clase personal de {user.get('name', 'Usuario')}",
                    "institute_id": generic_institute["_id"],
                    "created_by": ObjectId(user_id),
                    "status": "active",
                    "created_at": datetime.utcnow(),
                    "is_personal": True
                }
                
                class_result = self.db.classes.insert_one(class_data)
                membership_data["class_id"] = class_result.inserted_id
            
            # Insertar membership
            result = self.db.institute_members.insert_one(membership_data)
            workspace_id = str(result.inserted_id)
            
            # Construir respuesta
            response_data = {
                "workspace_id": workspace_id,
                "workspace_type": workspace_type,
                "workspace_name": workspace_name.strip(),
                "role_in_workspace": role,
                "institute_id": str(generic_institute["_id"]),
                "class_id": str(membership_data.get("class_id")) if membership_data.get("class_id") else None,
                "message": "Workspace personal creado exitosamente"
            }
            
            return True, "Workspace creado exitosamente", response_data
            
        except Exception as e:
            if isinstance(e, AppException):
                raise
            raise AppException(f"Error al crear workspace: {str(e)}", AppException.INTERNAL_ERROR)
    
    def update_workspace_info(self, workspace_id: str, user_id: str, update_data: Dict[str, Any]) -> Tuple[bool, str, Dict[str, Any]]:
        """Actualizar información de workspace"""
        try:
            # Validar que el workspace existe y pertenece al usuario
            if not self.validate_workspace_ownership(workspace_id, user_id):
                raise AppException("No tienes permisos para editar este workspace", AppException.FORBIDDEN)
            
            # Obtener workspace actual
            current_workspace = self.db.institute_members.find_one({"_id": ObjectId(workspace_id)})
            if not current_workspace:
                raise AppException("Workspace no encontrado", AppException.NOT_FOUND)
            
            # Validar campos permitidos
            allowed_fields = ["workspace_name", "description", "status"]
            update_fields = {}
            updated_field_names = []
            
            for field, value in update_data.items():
                if field in allowed_fields and value is not None:
                    if field == "workspace_name" and not value.strip():
                        raise AppException("El nombre del workspace no puede estar vacío", AppException.BAD_REQUEST)
                    
                    if field == "status" and value not in ["active", "inactive"]:
                        raise AppException("Estado inválido. Debe ser 'active' o 'inactive'", AppException.BAD_REQUEST)
                    
                    update_fields[field] = value.strip() if isinstance(value, str) else value
                    updated_field_names.append(field)
            
            if not update_fields:
                raise AppException("No hay campos válidos para actualizar", AppException.BAD_REQUEST)
            
            # Actualizar workspace
            update_fields["updated_at"] = datetime.utcnow()
            
            self.db.institute_members.update_one(
                {"_id": ObjectId(workspace_id)},
                {"$set": update_fields}
            )
            
            # Si se actualiza el nombre y hay clase asociada, actualizar también la clase
            if "workspace_name" in update_fields and current_workspace.get("class_id"):
                self.db.classes.update_one(
                    {"_id": current_workspace["class_id"]},
                    {"$set": {
                        "name": update_fields["workspace_name"],
                        "updated_at": datetime.utcnow()
                    }}
                )
            
            response_data = {
                "workspace_id": workspace_id,
                "workspace_name": update_fields.get("workspace_name", current_workspace.get("workspace_name")),
                "updated_fields": updated_field_names,
                "message": "Workspace actualizado exitosamente"
            }
            
            return True, "Workspace actualizado exitosamente", response_data
            
        except Exception as e:
            if isinstance(e, AppException):
                raise
            raise AppException(f"Error al actualizar workspace: {str(e)}", AppException.INTERNAL_ERROR)
    
    def create_study_plan_for_workspace(self, workspace_id: str, user_id: str, plan_data: Dict[str, Any]) -> Tuple[bool, str, Dict[str, Any]]:
        """Crear plan de estudio para workspace individual de estudiante"""
        try:
            # Validar que el workspace existe y pertenece al usuario
            workspace = self.get_workspace_by_id(workspace_id, user_id)
            
            # Validar que es workspace de estudiante individual
            if workspace["workspace_type"] != "INDIVIDUAL_STUDENT":
                raise AppException("Solo se pueden crear planes de estudio en workspaces de estudiantes individuales", AppException.BAD_REQUEST)
            
            # Validar que no tenga ya un plan activo
            existing_plan = self.db.study_plans.find_one({
                "user_id": ObjectId(user_id),
                "workspace_id": ObjectId(workspace_id),
                "status": {"$in": ["generating", "ready"]}
            })
            
            if existing_plan:
                raise AppException("Ya tienes un plan de estudio activo en este workspace", AppException.CONFLICT)
            
            # Validar datos del plan
            required_fields = ["title", "description", "objectives", "content_type", "difficulty_level", "estimated_duration_weeks"]
            for field in required_fields:
                if field not in plan_data or not plan_data[field]:
                    raise AppException(f"Campo requerido: {field}", AppException.BAD_REQUEST)
            
            if not isinstance(plan_data["objectives"], list) or len(plan_data["objectives"]) == 0:
                raise AppException("Debe proporcionar al menos un objetivo", AppException.BAD_REQUEST)
            
            if plan_data["content_type"] not in ["pdf", "text", "url"]:
                raise AppException("Tipo de contenido inválido", AppException.BAD_REQUEST)
            
            if plan_data["difficulty_level"] not in ["beginner", "intermediate", "advanced"]:
                raise AppException("Nivel de dificultad inválido", AppException.BAD_REQUEST)
            
            # Crear plan de estudio
            study_plan_data = {
                "title": plan_data["title"].strip(),
                "description": plan_data["description"].strip(),
                "objectives": [obj.strip() for obj in plan_data["objectives"] if obj.strip()],
                "user_id": ObjectId(user_id),
                "workspace_id": ObjectId(workspace_id),
                "institute_id": ObjectId(workspace["institute_id"]),
                "content_type": plan_data["content_type"],
                "difficulty_level": plan_data["difficulty_level"],
                "estimated_duration_weeks": int(plan_data["estimated_duration_weeks"]),
                "status": "generating",
                "created_at": datetime.utcnow(),
                "updated_at": datetime.utcnow()
            }
            
            if plan_data.get("document_url"):
                study_plan_data["document_url"] = plan_data["document_url"].strip()
            
            # Insertar plan
            result = self.db.study_plans.insert_one(study_plan_data)
            study_plan_id = str(result.inserted_id)
            
            # TODO: Aquí se debería encolar la tarea de generación automática
            # Por ahora simulamos con un task_id
            generation_task_id = f"gen_{study_plan_id}_{int(datetime.utcnow().timestamp())}"
            
            # Actualizar con task_id
            self.db.study_plans.update_one(
                {"_id": result.inserted_id},
                {"$set": {"generation_task_id": generation_task_id}}
            )
            
            # Calcular tiempo estimado de finalización (simulado)
            estimated_completion = datetime.utcnow()
            
            response_data = {
                "study_plan_id": study_plan_id,
                "title": plan_data["title"].strip(),
                "status": "generating",
                "generation_task_id": generation_task_id,
                "estimated_completion": estimated_completion.isoformat(),
                "message": "Plan de estudio iniciado. La generación comenzará en breve."
            }
            
            return True, "Plan de estudio creado exitosamente", response_data
            
        except Exception as e:
            if isinstance(e, AppException):
                raise
            raise AppException(f"Error al crear plan de estudio: {str(e)}", AppException.INTERNAL_ERROR)
    
    def _get_workspace_permissions(self, role: str, workspace_type: str = None) -> List[str]:
        """Obtener permisos según rol y tipo de workspace"""
        base_permissions = {
            "student": ["view_content", "submit_assignments", "view_grades"],
            "teacher": ["view_content", "create_content", "manage_students", "grade_assignments"],
            "institute_admin": ["manage_institute", "manage_users", "view_analytics"],
            "admin": ["full_access"]
        }
        
        permissions = base_permissions.get(role, [])
        
        # Permisos adicionales para workspaces individuales
        if workspace_type in ["INDIVIDUAL_STUDENT", "INDIVIDUAL_TEACHER"]:
            permissions.extend(["manage_workspace", "edit_workspace"])
            
            if workspace_type == "INDIVIDUAL_STUDENT":
                permissions.extend(["create_study_plan", "manage_study_plan"])
            elif workspace_type == "INDIVIDUAL_TEACHER":
                permissions.extend(["manage_personal_class", "create_assignments"])
        
        return permissions
    
    def apply_workspace_filters(self, query: Dict[str, Any], workspace_type: str, user_id: str, class_id: str = None) -> Dict[str, Any]:
        """Aplicar filtros según tipo de workspace para aislar datos"""
        if workspace_type == "INDIVIDUAL_TEACHER":
            # Solo clases propias
            query["$or"] = [
                {"created_by": ObjectId(user_id)},
                {"_id": ObjectId(class_id)} if class_id else {}
            ]
        elif workspace_type == "INDIVIDUAL_STUDENT":
            # Solo contenido propio - filtrar por planes de estudio del usuario
            user_plans = list(self.db.study_plans.find(
                {"user_id": ObjectId(user_id)},
                {"_id": 1}
            ))
            plan_ids = [plan["_id"] for plan in user_plans]
            
            if plan_ids:
                query["study_plan_id"] = {"$in": plan_ids}
            else:
                # Si no tiene planes, no mostrar nada
                query["_id"] = {"$in": []}
        
        return query