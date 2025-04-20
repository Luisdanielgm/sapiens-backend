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
        Asegura que los recursos se creen siempre dentro de la jerarquía del usuario.
        
        Args:
            resource_data: Datos del recurso a crear. Debe incluir 'created_by'.
                          El parámetro 'email' es opcional pero recomendado para verificar jerarquía.
            
        Returns:
            Tuple[bool, str]: (éxito, id o mensaje de error)
        """
        try:
            # Validar si el usuario existe
            created_by = resource_data.get("created_by")
            if not created_by or not self.check_user_exists(created_by):
                return False, "El usuario creador no existe o no se especificó"
            
            # Obtener email para jerarquía (si no está en resource_data)
            email = resource_data.pop("email", None)  # Quitar de resource_data para evitar conflicto con modelo
            if not email:
                # Intentar obtener email del usuario por created_by
                user = self.db.users.find_one({"_id": ObjectId(created_by)})
                if user and "email" in user:
                    email = user["email"]
            
            # Asegurar que el recurso se guarde en la jerarquía del usuario
            folder_id = resource_data.get("folder_id")
            
            if email:  # Si tenemos email, podemos verificar/crear jerarquía
                folder_service = ResourceFolderService()
                try:
                    # Obtener/crear carpeta raíz del usuario
                    root_folder = folder_service.get_user_root_folder(email)
                    root_folder_id = str(root_folder["_id"])
                    
                    # Si no se especifica folder_id, usar la carpeta raíz del usuario
                    if not folder_id:
                        resource_data["folder_id"] = root_folder_id
                    else:
                        # Verificar que folder_id está dentro de la jerarquía
                        is_in_hierarchy = folder_service._verify_folder_in_user_hierarchy(
                            ObjectId(folder_id), root_folder["_id"]
                        )
                        
                        if not is_in_hierarchy:
                            # Si no está en jerarquía, usar la carpeta raíz
                            resource_data["folder_id"] = root_folder_id
                            # También podríamos buscar/crear una subcarpeta como "Recursos de Clases"
                except Exception as e:
                    log_error(f"Error al verificar jerarquía para recurso: {str(e)}")
                    # Continuar sin modificar folder_id
            
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
                
                # Verificar si necesitamos buscar/ubicar en la jerarquía del usuario
                try:
                    # Buscar usuario para obtener email
                    user = self.db.users.find_one({"_id": creator_id})
                    if user and "email" in user:
                        email = user["email"]
                        
                        # Utilizar el servicio de carpetas para obtener/crear la jerarquía
                        folder_service = ResourceFolderService()
                        root_folder = folder_service.get_user_root_folder(email)
                        
                        # Si se especifica folder_id, verificar que está en la jerarquía
                        if "folder_id" in resource_data and resource_data["folder_id"]:
                            folder_id = ObjectId(resource_data["folder_id"])
                            # Verificar si está en la jerarquía
                            is_in_hierarchy = folder_service._verify_folder_in_user_hierarchy(
                                folder_id, root_folder["_id"])
                            
                            if not is_in_hierarchy:
                                # Si no está en la jerarquía, buscar "Recursos de Clases" o crear
                                class_resources_folder = self.db.resource_folders.find_one({
                                    "created_by": creator_id,
                                    "name": "Recursos de Clases",
                                    "parent_id": root_folder["_id"]
                                })
                                
                                if not class_resources_folder:
                                    # Crear carpeta "Recursos de Clases" dentro de la raíz
                                    folder_data = {
                                        "name": "Recursos de Clases",
                                        "created_by": str(creator_id),
                                        "description": "Recursos utilizados en clases y temas",
                                        "parent_id": str(root_folder["_id"]),
                                        "email": email
                                    }
                                    success, folder_id = folder_service.create_folder(folder_data)
                                    if success:
                                        resource_data["folder_id"] = folder_id
                                else:
                                    resource_data["folder_id"] = str(class_resources_folder["_id"])
                        else:
                            # Si no se especifica folder_id, usar "Recursos de Clases" por defecto
                            class_resources_folder = self.db.resource_folders.find_one({
                                "created_by": creator_id,
                                "name": "Recursos de Clases",
                                "parent_id": root_folder["_id"]
                            })
                            
                            if not class_resources_folder:
                                # Crear carpeta "Recursos de Clases"
                                folder_data = {
                                    "name": "Recursos de Clases",
                                    "created_by": str(creator_id),
                                    "description": "Recursos utilizados en clases y temas",
                                    "parent_id": str(root_folder["_id"]),
                                    "email": email
                                }
                                success, folder_id = folder_service.create_folder(folder_data)
                                if success:
                                    resource_data["folder_id"] = folder_id
                            else:
                                resource_data["folder_id"] = str(class_resources_folder["_id"])
                except Exception as e:
                    log_error(f"Error al gestionar carpeta para recurso externo: {str(e)}")
                    # Continuar sin modificar folder_id
                
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
            
    def update_resource(self, resource_id: str, updates: dict, email: str = None) -> Tuple[bool, str]:
        """
        Actualiza un recurso existente, asegurando que permanezca en la jerarquía del usuario
        
        Args:
            resource_id: ID del recurso a actualizar
            updates: Campos a actualizar
            email: Email del usuario (opcional, para verificación de jerarquía)
            
        Returns:
            Tuple[bool, str]: (éxito, mensaje)
        """
        try:
            # Validar si el recurso existe
            resource = self.get_resource(resource_id)
            if not resource:
                return False, "El recurso no existe"
            
            # Validar si se va a cambiar la carpeta
            new_folder_id = updates.get("folder_id")
            if new_folder_id is not None:
                # Si se proporciona email, verificar que la nueva carpeta está en la jerarquía
                if email:
                    try:
                        folder_service = ResourceFolderService()
                        root_folder = folder_service.get_user_root_folder(email)
                        
                        # Si folder_id es None o vacío, usar la carpeta raíz del usuario
                        if not new_folder_id:
                            updates["folder_id"] = str(root_folder["_id"])
                        else:
                            # Verificar que la nueva carpeta está en la jerarquía
                            is_in_hierarchy = folder_service._verify_folder_in_user_hierarchy(
                                ObjectId(new_folder_id), root_folder["_id"]
                            )
                            
                            if not is_in_hierarchy:
                                return False, "No puedes mover el recurso fuera de tu espacio de usuario"
                    except Exception as e:
                        log_error(f"Error al verificar jerarquía para actualización: {str(e)}")
                        # Si falla la verificación, rechazar el cambio de carpeta
                        return False, f"Error al verificar jerarquía: {str(e)}"
                
                # Validar si la carpeta existe
                if new_folder_id and not self.check_folder_exists(new_folder_id):
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
            
    def get_teacher_resources(self, teacher_id: str, folder_id: Optional[str] = None, email: str = None) -> List[Dict]:
        """
        Obtiene todos los recursos de un profesor, opcionalmente filtrando por carpeta
        y respetando jerarquía de usuario.
        
        Args:
            teacher_id: ID del profesor
            folder_id: ID de la carpeta (opcional)
            email: Email del profesor para restringir a jerarquía (opcional)
            
        Returns:
            List[Dict]: Lista de recursos
        """
        try:
            query = {"created_by": ObjectId(teacher_id)}
            
            # Si se especifica una carpeta, filtrar por ella
            if folder_id:
                query["folder_id"] = ObjectId(folder_id)
            
            # Si se proporciona email, restringir a la jerarquía del usuario
            if email:
                try:
                    # Obtener toda la jerarquía de carpetas del usuario
                    folder_service = ResourceFolderService()
                    root_folder = folder_service.get_user_root_folder(email)
                    folder_ids = folder_service.get_all_folders_in_hierarchy(root_folder["_id"])
                    
                    # Si ya se especificó un folder_id, verificar que está en la jerarquía
                    if folder_id:
                        folder_id_obj = ObjectId(folder_id)
                        if folder_id_obj not in folder_ids:
                            return [] # La carpeta no está en la jerarquía
                    else:
                        # Restringir a recursos en carpetas de la jerarquía o sin carpeta
                        query["$or"] = [
                            {"folder_id": {"$in": folder_ids}},
                            {"folder_id": {"$exists": False}}
                        ]
                except Exception as e:
                    log_error(f"Error al obtener jerarquía para recursos: {str(e)}")
                    # Continuar con la consulta básica
            
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
            
    def search_resources(self, teacher_id: str, query: str, filters: Optional[Dict] = None, email: str = None) -> List[Dict]:
        """
        Busca recursos por texto y filtros, respetando jerarquía de usuario
        
        Args:
            teacher_id: ID del profesor
            query: Texto a buscar
            filters: Filtros adicionales (tipo, tags, rango de fechas)
            email: Email del profesor para restringir a jerarquía (opcional)
            
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
            
            # Si se proporciona email, restringir a la jerarquía del usuario
            if email:
                try:
                    # Obtener toda la jerarquía de carpetas del usuario
                    folder_service = ResourceFolderService()
                    root_folder = folder_service.get_user_root_folder(email)
                    folder_ids = folder_service.get_all_folders_in_hierarchy(root_folder["_id"])
                    
                    # Restringir a recursos en carpetas de la jerarquía o sin carpeta
                    match_stage["$match"]["$or"] = [
                        {"folder_id": {"$in": folder_ids}},
                        {"folder_id": {"$exists": False}}
                    ]
                except Exception as e:
                    log_error(f"Error al obtener jerarquía para búsqueda: {str(e)}")
                    # Continuar con la consulta básica
            
            # Añadir búsqueda de texto si se proporciona
            if query and query.strip():
                if "$or" not in match_stage["$match"]:
                    match_stage["$match"]["$or"] = []
                
                match_stage["$match"]["$or"].extend([
                    {"name": {"$regex": query, "$options": "i"}},
                    {"description": {"$regex": query, "$options": "i"}},
                    {"tags": {"$elemMatch": {"$regex": query, "$options": "i"}}}
                ])
            
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
        
    def get_user_root_folder(self, email: str) -> dict:
        """
        Obtiene o crea la carpeta raíz del usuario basada en su email.
        
        Args:
            email: Email del usuario
            
        Returns:
            Dict: Datos de la carpeta raíz
            
        Raises:
            AppException: Si no se encuentra el usuario o hay error al crear la carpeta
        """
        try:
            user = self.db.users.find_one({"email": email})
            if not user:
                raise AppException("Usuario no encontrado", AppException.NOT_FOUND)
                
            user_id = user["_id"]
            username = email.split('@')[0]
            
            # Buscar carpeta raíz existente de varias formas para evitar duplicación
            # 1. Primero por metadata.root_user
            root_folder = self.collection.find_one({
                "metadata.root_user": username
            })
            
            # 2. Si no encuentra, buscar por el criterio original
            if not root_folder:
                root_folder = self.collection.find_one({
                    "created_by": user_id,
                    "name": username,
                    "parent_id": None
                })
                
            # 3. Búsqueda amplia como último recurso
            if not root_folder:
                root_folder = self.collection.find_one({
                    "$or": [
                        {"name": username, "created_by": user_id, "parent_id": None},
                        {"metadata.root_user": username}
                    ]
                })
            
            # Si no existe, crearla con metadatos adecuados
            if not root_folder:
                folder_data = {
                    "name": username,
                    "created_by": str(user_id),
                    "description": "Carpeta personal del usuario",
                    "metadata": {
                        "root_user": username
                    }
                }
                folder = ResourceFolder(**folder_data)
                result = self.collection.insert_one(folder.to_dict())
                if not result.inserted_id:
                    raise AppException("Error al crear carpeta raíz", AppException.INTERNAL_ERROR)
                
                root_folder = self.collection.find_one({"_id": result.inserted_id})
            
            return root_folder
        except Exception as e:
            log_error(f"Error al obtener/crear carpeta raíz: {str(e)}")
            raise
        
    def _verify_folder_in_user_hierarchy(self, folder_id: ObjectId, root_id: ObjectId) -> bool:
        """
        Verifica recursivamente que una carpeta está dentro de la jerarquía del usuario.
        
        Args:
            folder_id: ID de la carpeta a verificar
            root_id: ID de la carpeta raíz del usuario
            
        Returns:
            bool: True si la carpeta está en la jerarquía, False en caso contrario
        """
        # Si es la misma carpeta raíz, está en la jerarquía
        if folder_id == root_id:
            return True
            
        # Encontrar la carpeta
        folder = self.collection.find_one({"_id": folder_id})
        if not folder:
            return False
            
        # Si no tiene parent_id, no está en la jerarquía (a menos que sea la raíz)
        if not folder.get("parent_id"):
            return False
            
        # Si su parent_id es la raíz, está en la jerarquía
        if folder["parent_id"] == root_id:
            return True
            
        # Recursivamente verificar hacia arriba
        return self._verify_folder_in_user_hierarchy(folder["parent_id"], root_id)
        
    def get_all_folders_in_hierarchy(self, root_id: ObjectId) -> List[ObjectId]:
        """
        Obtiene todos los IDs de carpetas en la jerarquía de un usuario.
        
        Args:
            root_id: ID de la carpeta raíz
            
        Returns:
            List[ObjectId]: Lista de IDs de carpetas en la jerarquía
        """
        # Implementación con enfoque recursivo
        result = [root_id]
        
        # Buscar subcarpetas directas
        children = list(self.collection.find({"parent_id": root_id}))
        
        # Para cada hijo, añadir recursivamente sus descendientes
        for child in children:
            child_id = child["_id"]
            result.append(child_id)
            result.extend(self.get_all_folders_in_hierarchy(child_id))
            
        return result

    def create_folder(self, folder_data: dict) -> Tuple[bool, str]:
        """
        Crea una nueva carpeta de recursos dentro de la jerarquía del usuario
        
        Args:
            folder_data: Datos de la carpeta a crear (debe incluir email o created_by)
            
        Returns:
            Tuple[bool, str]: (éxito, id o mensaje de error)
        """
        try:
            # Obtener email del usuario
            email = folder_data.pop("email", None)  # Eliminar del dict para evitar conflicto con el modelo
            
            # Si no se proporciona email, intentar obtener usuario por created_by
            if not email and "created_by" in folder_data:
                user = self.db.users.find_one({"_id": ObjectId(folder_data["created_by"])})
                if user and "email" in user:
                    email = user["email"]
            
            if not email:
                return False, "Se requiere email o created_by para crear carpeta"
                
            # Validar si el usuario existe
            if not self.check_user_exists(folder_data.get("created_by")):
                return False, "El usuario no existe"
            
            # Obtener carpeta raíz del usuario
            root_folder = self.get_user_root_folder(email)
            
            # Si no se especifica parent_id, usar la carpeta raíz
            if "parent_id" not in folder_data or not folder_data["parent_id"]:
                folder_data["parent_id"] = str(root_folder["_id"])
            else:
                # Verificar que parent_id pertenece a la jerarquía del usuario
                parent_id = ObjectId(folder_data["parent_id"])
                is_in_hierarchy = self._verify_folder_in_user_hierarchy(parent_id, root_folder["_id"])
                if not is_in_hierarchy:
                    return False, "No se puede crear la carpeta fuera de tu espacio de usuario"
            
            # Validar si la carpeta padre existe (aunque este paso ya se comprobó en _verify_folder_in_user_hierarchy)
            parent_id = folder_data.get("parent_id")
            if parent_id and not self.folder_exists(parent_id):
                return False, "La carpeta padre no existe"
                
            # Crear carpeta
            folder = ResourceFolder(**folder_data)
            
            # Verificar que no se crearía un ciclo
            if self.would_create_cycle(None, folder_data.get("parent_id")):
                return False, "Esta operación crearía un ciclo en la estructura de carpetas"
                
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
            
    def update_folder(self, folder_id: str, updates: dict, email: str = None) -> Tuple[bool, str]:
        """
        Actualiza una carpeta existente asegurando que permanezca en la jerarquía del usuario
        
        Args:
            folder_id: ID de la carpeta a actualizar
            updates: Campos a actualizar
            email: Email del usuario (opcional, para verificación de jerarquía)
            
        Returns:
            Tuple[bool, str]: (éxito, mensaje)
        """
        try:
            # Validar si la carpeta existe
            folder = self.get_folder(folder_id)
            if not folder:
                return False, "La carpeta no existe"
                
            # Si se proporcionó email, verificar jerarquía
            if email:
                # Obtener carpeta raíz del usuario
                root_folder = self.get_user_root_folder(email)
                
                # No permitir modificar la carpeta raíz
                if str(root_folder["_id"]) == folder_id:
                    return False, "No se puede modificar la carpeta raíz del usuario"
                
                # Verificar que la carpeta pertenece a la jerarquía del usuario
                is_in_hierarchy = self._verify_folder_in_user_hierarchy(ObjectId(folder_id), root_folder["_id"])
                if not is_in_hierarchy:
                    return False, "No tienes permiso para modificar esta carpeta"
                
                # Si se está cambiando parent_id, verificar que está en la jerarquía
                if "parent_id" in updates and updates["parent_id"]:
                    parent_id = ObjectId(updates["parent_id"])
                    is_parent_in_hierarchy = self._verify_folder_in_user_hierarchy(parent_id, root_folder["_id"])
                    if not is_parent_in_hierarchy:
                        return False, "No puedes mover la carpeta fuera de tu espacio de usuario"
            
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
            
    def delete_folder(self, folder_id: str, email: str = None) -> Tuple[bool, str]:
        """
        Elimina una carpeta y sus recursos, verificando jerarquía.
        Mueve las subcarpetas al nivel superior (dentro de la jerarquía).
        
        Args:
            folder_id: ID de la carpeta a eliminar
            email: Email del usuario (opcional, para verificación de jerarquía)
            
        Returns:
            Tuple[bool, str]: (éxito, mensaje)
        """
        try:
            # Verificar si la carpeta existe
            folder = self.get_folder(folder_id)
            if not folder:
                return False, "La carpeta no existe"
                
            # Si se proporcionó email, verificar jerarquía
            if email:
                # Obtener carpeta raíz del usuario
                root_folder = self.get_user_root_folder(email)
                
                # No permitir eliminar la carpeta raíz
                if str(root_folder["_id"]) == folder_id:
                    return False, "No puedes eliminar tu carpeta raíz"
                
                # Verificar que la carpeta pertenece a la jerarquía del usuario
                is_in_hierarchy = self._verify_folder_in_user_hierarchy(ObjectId(folder_id), root_folder["_id"])
                if not is_in_hierarchy:
                    return False, "No tienes permiso para eliminar esta carpeta"
            
            # Eliminar recursos asociados a la carpeta usando ResourceService
            resources_in_folder = list(get_db().resources.find({"folder_id": ObjectId(folder_id)}))
            resources_deleted_count = 0
            resource_service = ResourceService() # Instancia para eliminar recursos
            for resource in resources_in_folder:
                success, _ = resource_service.delete_resource(str(resource["_id"]))
                if success:
                    resources_deleted_count += 1
            
            # Buscar carpetas hijas
            child_folders = list(self.collection.find({"parent_id": ObjectId(folder_id)}))
            
            # Si hay carpeta raíz y estamos dentro de jerarquía, mover a carpeta raíz
            # en lugar de nivel superior (null)
            parent_id = None
            if email:
                root_folder = self.get_user_root_folder(email)
                # Si la carpeta a eliminar no es de primer nivel (directamente bajo raíz)
                folder_parent = folder.get("parent_id")
                if folder_parent:
                    # Usar el parent actual de la carpeta
                    parent_id = folder_parent
                else:
                    # Si es de primer nivel, usar la raíz
                    parent_id = root_folder["_id"]
            
            # Mover subcarpetas al nuevo parent_id (raíz o null)
            children_updated = 0
            if child_folders:
                update_data = {"updated_at": datetime.now()}
                if parent_id:
                    update_data["parent_id"] = parent_id
                else:
                    # $unset para quitar parent_id completamente
                    update_result = self.collection.update_many(
                        {"parent_id": ObjectId(folder_id)},
                        {"$unset": {"parent_id": ""}, "$set": {"updated_at": datetime.now()}}
                    )
                    children_updated = update_result.modified_count
                
                if parent_id:
                    update_result = self.collection.update_many(
                        {"parent_id": ObjectId(folder_id)},
                        {"$set": update_data}
                    )
                    children_updated = update_result.modified_count
            
            # Eliminar la carpeta
            result = self.collection.delete_one({"_id": ObjectId(folder_id)})
            
            if result.deleted_count > 0:
                message = f"Carpeta eliminada. {resources_deleted_count} recursos eliminados. {children_updated} subcarpetas movidas."
                return True, message
            return False, "No se pudo eliminar la carpeta"
        except Exception as e:
            log_error(f"Error al eliminar carpeta: {str(e)}")
            return False, str(e)
            
    def get_teacher_folders(self, teacher_id: str, email: str = None) -> List[Dict]:
        """
        Obtiene todas las carpetas de un profesor, opcionalmente restringidas a su jerarquía
        
        Args:
            teacher_id: ID del profesor
            email: Email del profesor (opcional, para restringir a jerarquía)
            
        Returns:
            List[Dict]: Lista de carpetas
        """
        try:
            # Construir consulta básica
            query = {"created_by": ObjectId(teacher_id)}
            
            # Si se proporcionó email, restringir a jerarquía
            if email:
                try:
                    root_folder = self.get_user_root_folder(email)
                    folder_ids = self.get_all_folders_in_hierarchy(root_folder["_id"])
                    
                    # Usar $in para obtener solo carpetas en la jerarquía
                    query["_id"] = {"$in": folder_ids}
                except Exception as e:
                    log_error(f"Error al obtener jerarquía para carpetas: {str(e)}")
                    # Continuar con la consulta básica si falla
            
            folders = list(self.collection.find(query))
            
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
            
    def get_folder_tree(self, teacher_id: str = None, email: str = None) -> Dict:
        """
        Obtiene el árbol de carpetas de un usuario con sus recursos,
        opcionalmente restringido a la jerarquía del usuario.
        Si se proporciona email pero no teacher_id, se usa el email para buscar el ID del usuario.
        
        Args:
            teacher_id: ID del usuario (opcional si se proporciona email)
            email: Email del usuario (opcional, para restringir a jerarquía)
            
        Returns:
            Dict: Árbol de carpetas con recursos
        """
        try:
            # Si no se proporcionó teacher_id pero sí email, obtener el ID del usuario
            if not teacher_id and email:
                user = self.db.users.find_one({"email": email})
                if user:
                    teacher_id = str(user["_id"])
                else:
                    # Si no se encuentra el usuario, devolver árbol vacío
                    return {"folders": [], "resources": []}
            
            # Verificar que tenemos un teacher_id para continuar
            if not teacher_id:
                return {"folders": [], "resources": []}
            
            # Obtener todas las carpetas del profesor (opcionalmente en jerarquía)
            folders = self.get_teacher_folders(teacher_id, email)
            
            # Obtener la carpeta raíz si se proporcionó email
            root_folder_id = None
            if email:
                try:
                    root_folder = self.get_user_root_folder(email)
                    root_folder_id = str(root_folder["_id"])
                except Exception as e:
                    log_error(f"Error al obtener carpeta raíz para árbol: {str(e)}")
                    # Continuar sin carpeta raíz
            
            # Agrupar carpetas por parent_id
            folder_map = {}
            root_folders = []
            
            # Primera pasada: crear mapa y añadir campos para hijos
            for folder in folders:
                folder_id = folder["_id"]
                folder["children"] = []
                folder["resources"] = []
                folder_map[folder_id] = folder
                
                # Si no tiene padre o su padre es la raíz, es una carpeta de primer nivel
                if not folder.get("parent_id") or (root_folder_id and folder.get("parent_id") == root_folder_id):
                    root_folders.append(folder)
            
            # Segunda pasada: construir jerarquía
            for folder in folders:
                parent_id = folder.get("parent_id")
                # Solo vincular si el padre no es la raíz (ya agregada como root_folder)
                if parent_id and parent_id in folder_map and parent_id != root_folder_id:
                    folder_map[parent_id]["children"].append(folder)
            
            # Obtener recursos y añadirlos a sus carpetas
            resource_service = ResourceService()
            
            # Si tenemos email, obtener recursos en la jerarquía
            all_resources = []
            if email:
                # Implementación básica - idealmente ResourceService tendría un método para esto
                if root_folder_id:
                    folder_ids = [ObjectId(f["_id"]) for f in folders]
                    all_resources = list(get_db().resources.find({
                        "created_by": ObjectId(teacher_id),
                        "folder_id": {"$in": folder_ids}
                    }))
                    
                    # Convertir ObjectIds a strings
                    for resource in all_resources:
                        resource["_id"] = str(resource["_id"])
                        resource["created_by"] = str(resource["created_by"])
                        if resource.get("folder_id"):
                            resource["folder_id"] = str(resource["folder_id"])
            else:
                # Sin restricción de jerarquía
                all_resources = resource_service.get_teacher_resources(teacher_id)
            
            # Agrupar recursos por carpeta
            root_resources = []
            for resource in all_resources:
                folder_id = resource.get("folder_id")
                if folder_id and folder_id in folder_map:
                    folder_map[folder_id]["resources"].append(resource)
                elif not folder_id or (root_folder_id and folder_id == root_folder_id):
                    # Recursos sin carpeta o en la raíz
                    root_resources.append(resource)
            
            # Construir la respuesta
            tree = {
                "folders": root_folders,
                "resources": root_resources
            }
            
            # Si tenemos raíz, agregarla como elemento especial
            if root_folder_id and root_folder_id in folder_map:
                tree["root"] = folder_map[root_folder_id]
            
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