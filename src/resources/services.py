from typing import Tuple, List, Dict, Optional, Any
from bson import ObjectId
from datetime import datetime

from src.shared.database import get_db
from src.shared.constants import ROLES, COLLECTIONS, STATUS
from src.shared.standardization import VerificationBaseService, ErrorCodes
from src.shared.exceptions import AppException
from src.shared.logging import log_error
from .models import Resource, ResourceFolder

class ResourceService(VerificationBaseService):
    def __init__(self):
        super().__init__(collection_name="resources")
        
    def create_resource(self, resource_data: dict) -> Tuple[bool, str]:
        """
        Crea un nuevo recurso. No verifica duplicados por sí mismo.
        Usar get_or_create_external_resource para manejar recursos externos con URLs.
        
        Args:
            resource_data: Datos del recurso a crear
            
        Returns:
            Tuple[bool, str]: (éxito, id o mensaje de error)
        """
        try:
            # Validar si el usuario existe
            if not self.check_user_exists(resource_data.get("created_by")):
                return False, "El usuario creador no existe"
                
            # Validar si la carpeta existe (si se especifica)
            folder_id = resource_data.get("folder_id")
            if folder_id and not self.check_folder_exists(folder_id):
                return False, "La carpeta especificada no existe"
                
            # Crear recurso
            resource = Resource(**resource_data)
            result = self.collection.insert_one(resource.to_dict())
            return True, str(result.inserted_id)
        except Exception as e:
            log_error(f"Error al crear recurso: {str(e)}")
            return False, f"Error interno al crear recurso: {str(e)}"

    def get_or_create_external_resource(self, resource_data: dict) -> Tuple[bool, str, bool]:
        """
        Obtiene un recurso externo existente por URL y creador, o lo crea si no existe.
        Solo aplica a recursos de tipo 'link' o tipos considerados externos.

        Args:
            resource_data: Datos del recurso a crear/obtener. Debe incluir 'url', 'created_by', 'type'.

        Returns:
            Tuple[bool, str, bool]: (éxito, id del recurso, si ya existía)
                                     En caso de error, (False, mensaje de error, False)
        """
        resource_type = resource_data.get("type", "link") # Asumir link si no se especifica
        url = resource_data.get("url")
        created_by = resource_data.get("created_by")

        # Validar datos esenciales
        if not url or not created_by:
            return False, "URL y created_by son requeridos para get_or_create_external_resource", False
        
        # Considerar 'link' y otros tipos potencialmente externos como candidatos para no duplicación por URL
        # Podríamos tener una lista más explícita si fuera necesario
        if resource_type not in ["link", "video", "external_document"]: # Ejemplo de tipos externos
             # Si no es un tipo externo basado en URL, simplemente lo creamos
            success, result = self.create_resource(resource_data)
            return success, result, False

        try:
            # Intentar convertir created_by a ObjectId
            creator_id = ObjectId(created_by)

            # Buscar recurso existente con la misma URL y creado por el mismo usuario
            existing_resource = self.collection.find_one({
                "url": url,
                "created_by": creator_id,
                "type": resource_type # Asegurarse que el tipo también coincida
            })

            if existing_resource:
                # Recurso encontrado, devolver su ID
                return True, str(existing_resource["_id"]), True
            else:
                # Recurso no encontrado, proceder a crearlo
                # Asegurarse que is_external sea True para estos tipos
                resource_data['is_external'] = True
                success, new_resource_id = self.create_resource(resource_data)
                if success:
                    return True, new_resource_id, False
                else:
                    # create_resource ya logueó el error
                    return False, new_resource_id, False # new_resource_id contiene el mensaje de error aquí

        except Exception as e:
            log_error(f"Error en get_or_create_external_resource (URL: {url}, User: {created_by}): {str(e)}")
            return False, f"Error interno procesando recurso externo: {str(e)}", False
            
    def get_resource(self, resource_id: str) -> Optional[Dict]:
        """
        Obtiene un recurso por su ID
        
        Args:
            resource_id: ID del recurso
            
        Returns:
            Optional[Dict]: Datos del recurso o None si no existe
        """
        try:
            resource = self.collection.find_one({"_id": ObjectId(resource_id)})
            if not resource:
                return None
                
            # Convertir IDs a strings
            resource["_id"] = str(resource["_id"])
            resource["created_by"] = str(resource["created_by"])
            if resource.get("folder_id"):
                resource["folder_id"] = str(resource["folder_id"])
                
            return resource
        except Exception as e:
            log_error(f"Error al obtener recurso: {str(e)}")
            return None
            
    def update_resource(self, resource_id: str, updates: dict) -> Tuple[bool, str]:
        """
        Actualiza un recurso existente
        
        Args:
            resource_id: ID del recurso a actualizar
            updates: Campos a actualizar
            
        Returns:
            Tuple[bool, str]: (éxito, mensaje)
        """
        try:
            # Validar si el recurso existe
            resource = self.get_resource(resource_id)
            if not resource:
                return False, "El recurso no existe"
                
            # Validar si la carpeta existe (si se va a actualizar)
            folder_id = updates.get("folder_id")
            if folder_id and not self.check_folder_exists(folder_id):
                return False, "La carpeta especificada no existe"
            
            # Añadir fecha de actualización
            updates["updated_at"] = datetime.now()
            
            # Actualizar recurso
            result = self.collection.update_one(
                {"_id": ObjectId(resource_id)},
                {"$set": updates}
            )
            
            if result.modified_count > 0:
                return True, "Recurso actualizado correctamente"
            return False, "No se realizaron cambios"
        except Exception as e:
            log_error(f"Error al actualizar recurso: {str(e)}")
            return False, str(e)
            
    def delete_resource(self, resource_id: str) -> Tuple[bool, str]:
        """
        Elimina un recurso y todas sus vinculaciones con temas.
        
        Args:
            resource_id: ID del recurso a eliminar
            
        Returns:
            Tuple[bool, str]: (éxito, mensaje)
        """
        try:
            # 1. Eliminar todas las vinculaciones en topic_resources
            topic_links_deleted = get_db().topic_resources.delete_many({
                "resource_id": ObjectId(resource_id)
            }).deleted_count
            
            # 2. Eliminar el recurso
            result = self.collection.delete_one({"_id": ObjectId(resource_id)})
            
            if result.deleted_count > 0:
                return True, f"Recurso eliminado correctamente. {topic_links_deleted} vinculaciones eliminadas."
            
            # Si el recurso no se encontró pero sí había links, podría ser un estado inconsistente
            if topic_links_deleted > 0:
                 log_error(f"Recurso {resource_id} no encontrado, pero se eliminaron {topic_links_deleted} vinculaciones.")
                 return True, f"Recurso no encontrado, pero se eliminaron {topic_links_deleted} vinculaciones."

            return False, "El recurso no existe o ya fue eliminado"
        except Exception as e:
            log_error(f"Error al eliminar recurso {resource_id}: {str(e)}")
            return False, f"Error interno al eliminar recurso: {str(e)}"
            
    def get_teacher_resources(self, teacher_id: str, folder_id: Optional[str] = None) -> List[Dict]:
        """
        Obtiene todos los recursos de un profesor, opcionalmente filtrando por carpeta
        
        Args:
            teacher_id: ID del profesor
            folder_id: ID de la carpeta (opcional)
            
        Returns:
            List[Dict]: Lista de recursos
        """
        try:
            query = {"created_by": ObjectId(teacher_id)}
            
            # Si se especifica una carpeta, filtrar por ella
            if folder_id:
                query["folder_id"] = ObjectId(folder_id)
            
            resources = list(self.collection.find(query))
            
            # Convertir IDs a strings
            for resource in resources:
                resource["_id"] = str(resource["_id"])
                resource["created_by"] = str(resource["created_by"])
                if resource.get("folder_id"):
                    resource["folder_id"] = str(resource["folder_id"])
                
            return resources
        except Exception as e:
            log_error(f"Error al obtener recursos del profesor: {str(e)}")
            return []
            
    def search_resources(self, teacher_id: str, query: str, filters: Optional[Dict] = None) -> List[Dict]:
        """
        Busca recursos por texto y filtros
        
        Args:
            teacher_id: ID del profesor
            query: Texto a buscar
            filters: Filtros adicionales (tipo, tags, rango de fechas)
            
        Returns:
            List[Dict]: Lista de recursos que coinciden con la búsqueda
        """
        try:
            # Construir pipeline de agregación para búsqueda
            pipeline = []
            
            # Filtrar por profesor
            match_stage = {
                "$match": {
                    "created_by": ObjectId(teacher_id)
                }
            }
            
            # Añadir búsqueda de texto si se proporciona
            if query and query.strip():
                match_stage["$match"]["$or"] = [
                    {"name": {"$regex": query, "$options": "i"}},
                    {"description": {"$regex": query, "$options": "i"}},
                    {"tags": {"$elemMatch": {"$regex": query, "$options": "i"}}}
                ]
            
            pipeline.append(match_stage)
            
            # Aplicar filtros adicionales
            if filters:
                if filters.get("types"):
                    pipeline.append({"$match": {"type": {"$in": filters["types"]}}})
                
                if filters.get("tags"):
                    pipeline.append({"$match": {"tags": {"$elemMatch": {"$in": filters["tags"]}}}})
                
                if filters.get("start_date") and filters.get("end_date"):
                    pipeline.append({
                        "$match": {
                            "created_at": {
                                "$gte": datetime.fromisoformat(filters["start_date"]),
                                "$lte": datetime.fromisoformat(filters["end_date"])
                            }
                        }
                    })
            
            # Ejecutar la agregación
            resources = list(self.collection.aggregate(pipeline))
            
            # Convertir IDs a strings
            for resource in resources:
                resource["_id"] = str(resource["_id"])
                resource["created_by"] = str(resource["created_by"])
                if resource.get("folder_id"):
                    resource["folder_id"] = str(resource["folder_id"])
            
            return resources
        except Exception as e:
            log_error(f"Error al buscar recursos: {str(e)}")
            return []
            
    def check_folder_exists(self, folder_id: str) -> bool:
        """
        Verifica si una carpeta existe
        
        Args:
            folder_id: ID de la carpeta
            
        Returns:
            bool: True si la carpeta existe, False en caso contrario
        """
        try:
            folder = get_db().resource_folders.find_one({"_id": ObjectId(folder_id)})
            return folder is not None
        except Exception:
            return False
            
    def get_teacher_by_email(self, email: str) -> Optional[str]:
        """
        Obtiene el ID de un profesor por su email
        
        Args:
            email: Email del profesor
            
        Returns:
            Optional[str]: ID del profesor o None si no existe
        """
        try:
            user = get_db().users.find_one({"email": email, "role": ROLES["TEACHER"]})
            if user:
                return str(user["_id"])
            return None
        except Exception:
            return None


class ResourceFolderService(VerificationBaseService):
    def __init__(self):
        super().__init__(collection_name="resource_folders")
        
    def create_folder(self, folder_data: dict) -> Tuple[bool, str]:
        """
        Crea una nueva carpeta de recursos
        
        Args:
            folder_data: Datos de la carpeta a crear
            
        Returns:
            Tuple[bool, str]: (éxito, id o mensaje de error)
        """
        try:
            # Validar si el usuario existe
            if not self.check_user_exists(folder_data.get("created_by")):
                return False, "El usuario no existe"
                
            # Validar si la carpeta padre existe (si se especifica)
            parent_id = folder_data.get("parent_id")
            if parent_id and not self.folder_exists(parent_id):
                return False, "La carpeta padre no existe"
                
            # Crear carpeta
            folder = ResourceFolder(**folder_data)
            result = self.collection.insert_one(folder.to_dict())
            return True, str(result.inserted_id)
        except Exception as e:
            log_error(f"Error al crear carpeta: {str(e)}")
            return False, str(e)
            
    def get_folder(self, folder_id: str) -> Optional[Dict]:
        """
        Obtiene una carpeta por su ID
        
        Args:
            folder_id: ID de la carpeta
            
        Returns:
            Optional[Dict]: Datos de la carpeta o None si no existe
        """
        try:
            folder = self.collection.find_one({"_id": ObjectId(folder_id)})
            if not folder:
                return None
                
            # Convertir IDs a strings
            folder["_id"] = str(folder["_id"])
            folder["created_by"] = str(folder["created_by"])
            if folder.get("parent_id"):
                folder["parent_id"] = str(folder["parent_id"])
                
            return folder
        except Exception as e:
            log_error(f"Error al obtener carpeta: {str(e)}")
            return None
            
    def update_folder(self, folder_id: str, updates: dict) -> Tuple[bool, str]:
        """
        Actualiza una carpeta existente
        
        Args:
            folder_id: ID de la carpeta a actualizar
            updates: Campos a actualizar
            
        Returns:
            Tuple[bool, str]: (éxito, mensaje)
        """
        try:
            # Validar si la carpeta existe
            folder = self.get_folder(folder_id)
            if not folder:
                return False, "La carpeta no existe"
                
            # Validar si la carpeta padre existe (si se va a actualizar)
            parent_id = updates.get("parent_id")
            if parent_id:
                # Evitar ciclos: una carpeta no puede ser su propio padre o ancestro
                if parent_id == folder_id:
                    return False, "Una carpeta no puede ser su propio padre"
                
                # Verificar si la carpeta padre existe
                if not self.folder_exists(parent_id):
                    return False, "La carpeta padre no existe"
                    
                # Evitar ciclos en la jerarquía
                if self.would_create_cycle(folder_id, parent_id):
                    return False, "No se puede crear un ciclo en la jerarquía de carpetas"
            
            # Añadir fecha de actualización
            updates["updated_at"] = datetime.now()
            
            # Actualizar carpeta
            result = self.collection.update_one(
                {"_id": ObjectId(folder_id)},
                {"$set": updates}
            )
            
            if result.modified_count > 0:
                return True, "Carpeta actualizada correctamente"
            return False, "No se realizaron cambios"
        except Exception as e:
            log_error(f"Error al actualizar carpeta: {str(e)}")
            return False, str(e)
            
    def delete_folder(self, folder_id: str) -> Tuple[bool, str]:
        """
        Elimina una carpeta y opcionalmente sus recursos. 
        Mueve las subcarpetas al nivel superior.
        
        Args:
            folder_id: ID de la carpeta a eliminar
            
        Returns:
            Tuple[bool, str]: (éxito, mensaje)
        """
        try:
            # Verificar si la carpeta existe
            folder = self.get_folder(folder_id)
            if not folder:
                return False, "La carpeta no existe"
                
            # Eliminar recursos asociados a la carpeta usando ResourceService
            # NOTA: Esto requiere que ResourceService tenga un método para eliminar por folder_id
            # o iterar y eliminar uno por uno. Por simplicidad, asumimos que se hace aquí.
            # Se podría refactorizar para que ResourceService maneje esto.
            resources_in_folder = list(get_db().resources.find({"folder_id": ObjectId(folder_id)}))
            resources_deleted_count = 0
            resource_service = ResourceService() # Instancia para eliminar recursos
            for resource in resources_in_folder:
                success, _ = resource_service.delete_resource(str(resource["_id"]))
                if success:
                    resources_deleted_count += 1
            
            # Buscar carpetas hijas
            child_folders = list(self.collection.find({"parent_id": ObjectId(folder_id)}))
            
            # Mover subcarpetas al nivel superior (parent_id = null)
            children_updated = 0
            if child_folders:
                update_result = self.collection.update_many(
                    {"parent_id": ObjectId(folder_id)},
                    {"$set": {"parent_id": None, "updated_at": datetime.now()}}
                )
                children_updated = update_result.modified_count
            
            # Eliminar la carpeta
            result = self.collection.delete_one({"_id": ObjectId(folder_id)})
            
            if result.deleted_count > 0:
                message = f"Carpeta eliminada. {resources_deleted_count} recursos eliminados. {children_updated} subcarpetas movidas al nivel superior."
                return True, message
            return False, "No se pudo eliminar la carpeta"
        except Exception as e:
            log_error(f"Error al eliminar carpeta: {str(e)}")
            return False, str(e)
            
    def get_teacher_folders(self, teacher_id: str) -> List[Dict]:
        """
        Obtiene todas las carpetas de un profesor
        
        Args:
            teacher_id: ID del profesor
            
        Returns:
            List[Dict]: Lista de carpetas
        """
        try:
            folders = list(self.collection.find({"created_by": ObjectId(teacher_id)}))
            
            # Convertir IDs a strings
            for folder in folders:
                folder["_id"] = str(folder["_id"])
                folder["created_by"] = str(folder["created_by"])
                if folder.get("parent_id"):
                    folder["parent_id"] = str(folder["parent_id"])
            
            return folders
        except Exception as e:
            log_error(f"Error al obtener carpetas del profesor: {str(e)}")
            return []
            
    def get_folder_tree(self, teacher_id: str) -> List[Dict]:
        """
        Obtiene el árbol de carpetas de un profesor con sus recursos
        
        Args:
            teacher_id: ID del profesor
            
        Returns:
            List[Dict]: Árbol de carpetas con recursos
        """
        try:
            # Obtener todas las carpetas del profesor
            folders = self.get_teacher_folders(teacher_id)
            
            # Agrupar carpetas por parent_id
            folder_map = {}
            root_folders = []
            
            # Primera pasada: crear mapa y añadir campos para hijos
            for folder in folders:
                folder_id = folder["_id"]
                folder["children"] = []
                folder["resources"] = []
                folder_map[folder_id] = folder
                
                # Si no tiene padre, es una carpeta raíz
                if not folder.get("parent_id"):
                    root_folders.append(folder)
            
            # Segunda pasada: construir jerarquía
            for folder in folders:
                parent_id = folder.get("parent_id")
                if parent_id and parent_id in folder_map:
                    folder_map[parent_id]["children"].append(folder)
            
            # Obtener recursos y añadirlos a sus carpetas
            resource_service = ResourceService()
            all_resources = resource_service.get_teacher_resources(teacher_id)
            
            # Agrupar recursos por carpeta
            root_resources = []
            for resource in all_resources:
                folder_id = resource.get("folder_id")
                if folder_id and folder_id in folder_map:
                    folder_map[folder_id]["resources"].append(resource)
                elif not folder_id:
                    # Recursos sin carpeta
                    root_resources.append(resource)
            
            # Agregar recursos sin carpeta al resultado
            tree = {
                "folders": root_folders,
                "resources": root_resources
            }
            
            return tree
        except Exception as e:
            log_error(f"Error al obtener árbol de carpetas: {str(e)}")
            return {"folders": [], "resources": []}
            
    def folder_exists(self, folder_id: str) -> bool:
        """
        Verifica si una carpeta existe
        
        Args:
            folder_id: ID de la carpeta
            
        Returns:
            bool: True si la carpeta existe, False en caso contrario
        """
        try:
            return self.collection.find_one({"_id": ObjectId(folder_id)}) is not None
        except Exception:
            return False
            
    def would_create_cycle(self, folder_id: str, parent_id: str) -> bool:
        """
        Verifica si asignar parent_id como padre de folder_id crearía un ciclo
        
        Args:
            folder_id: ID de la carpeta a actualizar
            parent_id: ID de la carpeta padre candidata
            
        Returns:
            bool: True si se crearía un ciclo, False en caso contrario
        """
        try:
            # Verificar si la carpeta padre es descendiente de la carpeta actual
            current_id = parent_id
            visited = set()
            
            while current_id:
                if current_id == folder_id:
                    return True
                
                if current_id in visited:
                    # Ciclo detectado en la estructura existente
                    return True
                
                visited.add(current_id)
                
                # Obtener el padre de la carpeta actual
                current_folder = self.collection.find_one({"_id": ObjectId(current_id)})
                if not current_folder or not current_folder.get("parent_id"):
                    break
                    
                current_id = str(current_folder["parent_id"])
            
            return False
        except Exception:
            # En caso de error, prevenir el cambio
            return True 