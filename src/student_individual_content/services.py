from typing import Dict, List, Optional, Tuple
from datetime import datetime
from bson import ObjectId

from src.shared.database import get_db
from src.shared.standardization import VerificationBaseService, ErrorCodes
from src.shared.exceptions import AppException
import logging
from src.student_individual_content.models import StudentIndividualContent


class StudentIndividualContentService(VerificationBaseService):
    """
    Servicio para gestionar el contenido individual de los estudiantes.
    Incluye funcionalidad para crear, actualizar, eliminar y consultar contenido.
    """
    def __init__(self):
        super().__init__(collection_name="contents")
        
    # ========== MÉTODOS DE VERIFICACIÓN ESTANDARIZADOS ==========
    def check_student_exists(self, student_id: str) -> bool:
        """
        Verifica si un estudiante existe.
        
        Args:
            student_id: ID del estudiante a verificar
            
        Returns:
            bool: True si el estudiante existe, False en caso contrario
        """
        try:
            student_id_obj = ObjectId(student_id) if isinstance(student_id, str) else student_id
            student = get_db().users.find_one({"_id": student_id_obj, "role": "STUDENT"})
            return student is not None
        except Exception:
            return False
            
    def check_class_exists(self, class_id: str) -> bool:
        """
        Verifica si una clase existe.
        
        Args:
            class_id: ID de la clase a verificar
            
        Returns:
            bool: True si la clase existe, False en caso contrario
        """
        try:
            class_id_obj = ObjectId(class_id) if isinstance(class_id, str) else class_id
            class_exists = get_db().classes.find_one({"_id": class_id_obj})
            return class_exists is not None
        except Exception:
            return False
            
    def check_student_in_class(self, student_id: str, class_id: str) -> bool:
        """
        Verifica si un estudiante es miembro de una clase.
        
        Args:
            student_id: ID del estudiante a verificar
            class_id: ID de la clase a verificar
            
        Returns:
            bool: True si el estudiante es miembro de la clase, False en caso contrario
        """
        try:
            student_id_obj = ObjectId(student_id) if isinstance(student_id, str) else student_id
            class_id_obj = ObjectId(class_id) if isinstance(class_id, str) else class_id
            
            is_member = get_db().class_members.find_one({
                "class_id": class_id_obj,
                "user_id": student_id_obj,
                "role": "STUDENT"
            })
            return is_member is not None
        except Exception:
            return False
            
    def check_content_exists(self, content_id: str) -> bool:
        """
        Verifica si un contenido existe.
        
        Args:
            content_id: ID del contenido a verificar
            
        Returns:
            bool: True si el contenido existe, False en caso contrario
        """
        try:
            content = self.collection.find_one({"_id": ObjectId(content_id)})
            return content is not None
        except Exception:
            return False
        
    def create_content(self, content_data: Dict) -> Tuple[bool, str]:
        """
        Crea un nuevo contenido individual para un estudiante.
        
        Args:
            content_data: Datos del contenido a crear
            
        Returns:
            Tuple[bool, str]: (Éxito, Mensaje/ID)
        """
        try:
            # Convertir IDs a ObjectId si es necesario
            class_id = ObjectId(content_data["class_id"]) if ObjectId.is_valid(content_data["class_id"]) else content_data["class_id"]
            student_id = ObjectId(content_data["student_id"]) if ObjectId.is_valid(content_data["student_id"]) else content_data["student_id"]
            
            # Verificar que el estudiante existe
            if not self.check_student_exists(student_id):
                return False, "Estudiante no encontrado o no es un estudiante válido"
                
            # Verificar que la clase existe
            if not self.check_class_exists(class_id):
                return False, "Clase no encontrada"
                
            # Verificar que el estudiante es miembro de la clase
            if not self.check_student_in_class(student_id, class_id):
                return False, "El estudiante no es miembro de esta clase"
                
            # Crear el contenido
            content_obj = StudentIndividualContent(
                class_id=class_id,
                student_id=student_id,
                title=content_data.get("title", "Sin título"),
                content=content_data.get("content", ""),
                content_type=content_data.get("content_type", "text"),
                tags=content_data.get("tags", []),
                metadata=content_data.get("metadata", {})
            )
            
            result = self.collection.insert_one(content_obj.to_dict())
            return True, str(result.inserted_id)
            
        except Exception as e:
            logging.error(f"Error al crear contenido: {str(e)}")
            return False, str(e)
            
    def update_content(self, content_id: str, updates: Dict) -> Tuple[bool, str]:
        """
        Actualiza un contenido individual existente.
        
        Args:
            content_id: ID del contenido a actualizar
            updates: Datos a actualizar
            
        Returns:
            Tuple[bool, str]: (Éxito, Mensaje)
        """
        try:
            # Verificar que el contenido existe
            if not self.check_content_exists(content_id):
                return False, "Contenido no encontrado"
                
            # Evitar actualizar campos críticos
            if "class_id" in updates:
                del updates["class_id"]
            if "student_id" in updates:
                del updates["student_id"]
                
            # Actualizar timestamp
            updates["updated_at"] = datetime.now()
            
            result = self.collection.update_one(
                {"_id": ObjectId(content_id)},
                {"$set": updates}
            )
            
            if result.modified_count > 0:
                return True, "Contenido actualizado correctamente"
            return False, "No se realizaron cambios"
            
        except Exception as e:
            print(f"Error al actualizar contenido: {str(e)}")
            return False, str(e)
            
    def get_content(self, content_id: str) -> Optional[Dict]:
        """
        Obtiene un contenido individual específico.
        
        Args:
            content_id: ID del contenido a obtener
            
        Returns:
            Optional[Dict]: Datos del contenido o None si no existe
        """
        try:
            content = self.collection.find_one({"_id": ObjectId(content_id)})
            if not content:
                return None
                
            # Convertir ObjectId a string para serialización
            content["_id"] = str(content["_id"])
            content["class_id"] = str(content["class_id"])
            content["student_id"] = str(content["student_id"])
            
            # Obtener información adicional
            class_info = get_db().classes.find_one({"_id": ObjectId(content["class_id"])})
            student_info = get_db().users.find_one({"_id": ObjectId(content["student_id"])})
            
            if class_info:
                content["class_info"] = {
                    "name": class_info.get("name", ""),
                    "subject": class_info.get("subject", "")
                }
                
            if student_info:
                content["student_info"] = {
                    "name": student_info.get("name", ""),
                    "email": student_info.get("email", "")
                }
                
            return content
            
        except Exception as e:
            logging.error(f"Error al obtener contenido: {str(e)}")
            return None
            
    def get_student_content(self, student_id: str, class_id: Optional[str] = None) -> List[Dict]:
        """
        Obtiene todo el contenido de un estudiante, opcionalmente filtrado por clase.
        
        Args:
            student_id: ID del estudiante
            class_id: ID opcional de la clase para filtrar
            
        Returns:
            List[Dict]: Lista de contenidos
        """
        try:
            query = {"student_id": ObjectId(student_id)}
            
            if class_id:
                query["class_id"] = ObjectId(class_id)
                
            contents = list(self.collection.find(query).sort("created_at", -1))
            
            # Convertir ObjectId a string para serialización
            for content in contents:
                content["_id"] = str(content["_id"])
                content["class_id"] = str(content["class_id"])
                content["student_id"] = str(content["student_id"])
                
                # Obtener información de la clase
                class_info = get_db().classes.find_one({"_id": ObjectId(content["class_id"])})
                if class_info:
                    content["class_info"] = {
                        "name": class_info.get("name", ""),
                        "subject": class_info.get("subject", "")
                    }
                    
            return contents
            
        except Exception as e:
            logging.error(f"Error al obtener contenido del estudiante: {str(e)}")
            return []
            
    def delete_content(self, content_id: str) -> Tuple[bool, str]:
        """
        Elimina un contenido individual.
        
        Args:
            content_id: ID del contenido a eliminar
            
        Returns:
            Tuple[bool, str]: (Éxito, Mensaje)
        """
        try:
            # Verificar que el contenido existe
            if not self.check_content_exists(content_id):
                return False, "Contenido no encontrado"
                
            result = self.collection.delete_one({"_id": ObjectId(content_id)})
            
            if result.deleted_count > 0:
                return True, "Contenido eliminado correctamente"
            return False, "No se pudo eliminar el contenido"
            
        except Exception as e:
            logging.error(f"Error al eliminar contenido: {str(e)}")
            return False, str(e)
