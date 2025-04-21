import logging
from typing import List, Dict, Tuple, Optional
from bson import ObjectId
from datetime import datetime

from src.shared.standardization import VerificationBaseService
from src.shared.database import get_db
from .models import TopicResource

class TopicResourceService(VerificationBaseService):
    """
    Servicio para gestionar las vinculaciones entre topics y recursos.
    """
    def __init__(self):
        super().__init__(collection_name="topic_resources")
    
    def check_resource_exists(self, resource_id: str) -> bool:
        """
        Verifica si un recurso existe.
        
        Args:
            resource_id: ID del recurso
            
        Returns:
            bool: True si existe, False en caso contrario
        """
        try:
            resource = self.db.resources.find_one({"_id": ObjectId(resource_id)})
            return resource is not None
        except Exception:
            return False
    
    def check_topic_exists(self, topic_id: str) -> bool:
        """
        Verifica si un tema existe.
        
        Args:
            topic_id: ID del tema
            
        Returns:
            bool: True si existe, False en caso contrario
        """
        try:
            topic = self.db.topics.find_one({"_id": ObjectId(topic_id)})
            return topic is not None
        except Exception:
            return False
            
    def link_resource_to_topic(self, topic_id: str, resource_id: str, 
                              relevance_score: float = 0.5,
                              recommended_for: List[str] = None,
                              usage_context: str = "supplementary",
                              content_types: List[str] = None,
                              created_by: str = None) -> Tuple[bool, str]:
        """
        Vincula un recurso a un tema específico.
        
        Args:
            topic_id: ID del tema
            resource_id: ID del recurso
            relevance_score: Puntuación de relevancia (0.0-1.0)
            recommended_for: Perfiles recomendados
            usage_context: Contexto de uso ("primary", "supplementary", "advanced")
            content_types: Tipos de contenido compatibles
            created_by: ID del usuario que crea la relación
            
        Returns:
            Tuple[bool, str]: (éxito, id o mensaje de error)
        """
        try:
            # Verificar que el tema existe
            if not self.check_topic_exists(topic_id):
                return False, "El tema no existe"
                
            # Verificar que el recurso existe
            if not self.check_resource_exists(resource_id):
                return False, "El recurso no existe"
                
            # Verificar si ya existe la relación
            existing = self.collection.find_one({
                "topic_id": ObjectId(topic_id),
                "resource_id": ObjectId(resource_id)
            })
            
            if existing:
                # Actualizar relación existente
                result = self.collection.update_one(
                    {"_id": existing["_id"]},
                    {"$set": {
                        "relevance_score": relevance_score,
                        "recommended_for": recommended_for or [],
                        "usage_context": usage_context,
                        "content_types": content_types or [],
                        "status": "active"
                    }}
                )
                return True, str(existing["_id"])
            
            # Crear nueva relación
            topic_resource = TopicResource(
                topic_id=topic_id,
                resource_id=resource_id,
                relevance_score=relevance_score,
                recommended_for=recommended_for,
                usage_context=usage_context,
                content_types=content_types,
                created_by=created_by,
                status="active"
            )
            
            result = self.collection.insert_one(topic_resource.to_dict())
            return True, str(result.inserted_id)
            
        except Exception as e:
            logging.error(f"Error al vincular recurso a tema: {str(e)}")
            return False, str(e)
            
    def unlink_resource_from_topic(self, topic_id: str, resource_id: str) -> Tuple[bool, str]:
        """
        Desvincula un recurso de un tema.
        
        Args:
            topic_id: ID del tema
            resource_id: ID del recurso
            
        Returns:
            Tuple[bool, str]: (éxito, mensaje)
        """
        try:
            result = self.collection.update_one(
                {
                    "topic_id": ObjectId(topic_id),
                    "resource_id": ObjectId(resource_id)
                },
                {"$set": {"status": "deleted"}}
            )
            
            if result.modified_count > 0:
                return True, "Recurso desvinculado del tema correctamente"
            return False, "No se encontró la relación entre el tema y el recurso"
            
        except Exception as e:
            logging.error(f"Error al desvincular recurso de tema: {str(e)}")
            return False, str(e)
            
    def get_topic_resources(self, topic_id: str, 
                           cognitive_profile: Dict = None,
                           content_type: str = None,
                           usage_context: str = None) -> List[Dict]:
        """
        Obtiene recursos asociados a un tema, opcionalmente filtrados y personalizados.
        
        Args:
            topic_id: ID del tema
            cognitive_profile: Perfil cognitivo para personalización
            content_type: Tipo de contenido específico
            usage_context: Contexto de uso específico
            
        Returns:
            List[Dict]: Lista de recursos asociados
        """
        try:
            # Construir consulta base
            query = {
                "topic_id": ObjectId(topic_id),
                "status": "active"
            }
            
            # Filtrar por tipo de contenido si se especifica
            if content_type:
                query["content_types"] = content_type
                
            # Filtrar por contexto de uso si se especifica
            if usage_context:
                query["usage_context"] = usage_context
            
            # Obtener relaciones tema-recurso
            topic_resources = list(self.collection.find(query))
            
            # Si no hay resultados, devolver lista vacía
            if not topic_resources:
                return []
                
            # Obtener IDs de recursos
            resource_ids = [ObjectId(tr["resource_id"]) for tr in topic_resources]
            
            # Obtener detalles completos de los recursos
            resources = list(self.db.resources.find({"_id": {"$in": resource_ids}}))
            
            # Crear diccionario de recursos para acceso rápido
            resources_dict = {str(r["_id"]): r for r in resources}
            
            # Combinar información de recursos con metadatos de la relación
            result = []
            for tr in topic_resources:
                resource_id = str(tr["resource_id"])
                if resource_id in resources_dict:
                    resource = resources_dict[resource_id]
                    # Convertir ObjectId a strings para serialización
                    resource["_id"] = str(resource["_id"])
                    if "created_by" in resource:
                        resource["created_by"] = str(resource["created_by"])
                    if "folder_id" in resource and resource["folder_id"]:
                        resource["folder_id"] = str(resource["folder_id"])
                    
                    # Añadir metadatos de la relación
                    resource["relevance_score"] = tr.get("relevance_score", 0.5)
                    resource["usage_context"] = tr.get("usage_context", "supplementary")
                    resource["recommended_for"] = tr.get("recommended_for", [])
                    
                    # Personalizar basado en perfil cognitivo
                    if cognitive_profile:
                        # Calcular puntuación de afinidad con el perfil
                        profile_match = 0.5  # Valor base
                        
                        # Analizar estilo de aprendizaje predominante
                        learning_style = cognitive_profile.get("learning_style", {})
                        if learning_style:
                            max_style = max(learning_style.items(), key=lambda x: x[1])[0] if learning_style else None
                            
                            if max_style and max_style in tr.get("recommended_for", []):
                                profile_match += 0.3
                                
                            # Bonificación adicional para recursos específicamente adaptados
                            # a alguna condición específica del estudiante
                            if cognitive_profile.get("diagnosis") and any(
                                diagnosis in tr.get("recommended_for", []) 
                                for diagnosis in ["adhd_adapted", "dyslexia_adapted", "autism_adapted"]
                            ):
                                profile_match += 0.2
                                
                        resource["profile_match"] = profile_match
                    
                    result.append(resource)
            
            # Ordenar por relevancia y afinidad con el perfil
            if cognitive_profile:
                result.sort(key=lambda x: (x.get("profile_match", 0), x.get("relevance_score", 0)), reverse=True)
            else:
                result.sort(key=lambda x: x.get("relevance_score", 0), reverse=True)
                
            return result
            
        except Exception as e:
            logging.error(f"Error al obtener recursos de tema: {str(e)}")
            return []
    
    def get_resource_topics(self, resource_id: str) -> List[Dict]:
        """
        Obtiene los temas vinculados a un recurso específico.
        
        Args:
            resource_id: ID del recurso
            
        Returns:
            List[Dict]: Lista de temas vinculados al recurso
        """
        try:
            # Obtener todas las vinculaciones activas
            query = {
                "resource_id": ObjectId(resource_id),
                "status": "active"
            }
            
            # Obtener relaciones recurso-tema
            resource_topics = list(self.collection.find(query))
            
            # Si no hay resultados, devolver lista vacía
            if not resource_topics:
                return []
                
            # Obtener IDs de temas
            topic_ids = [ObjectId(rt["topic_id"]) for rt in resource_topics]
            
            # Obtener detalles completos de los temas
            topics = list(self.db.topics.find({"_id": {"$in": topic_ids}}))
            
            # Convertir ObjectId a strings para serialización
            for topic in topics:
                topic['_id'] = str(topic['_id'])
                topic['module_id'] = str(topic['module_id'])
            
            return topics
            
        except Exception as e:
            logging.error(f"Error al obtener temas de recurso: {str(e)}")
            return [] 