import logging
from datetime import datetime
from bson import ObjectId
from typing import Dict, List, Optional, Any, Tuple

from src.shared.database import get_db
from .services import ContentService
from .template_services import TemplateService, TemplateInstanceService
from .template_models import Template, TemplateInstance
from .models import TopicContent

class TemplateIntegrationService:
    """
    Servicio de integración entre el sistema de plantillas y el contenido legacy.
    Maneja la creación de TopicContent basado en plantillas y su integración con virtualización.
    """
    
    def __init__(self):
        self.db = get_db()
        self.content_service = ContentService()
        self.template_service = TemplateService()
        self.instance_service = TemplateInstanceService()
        
    def create_content_from_template(self, 
                                   template_id: str, 
                                   topic_id: str, 
                                   props: Dict = None,
                                   assets: List[Dict] = None,
                                   learning_mix: Dict = None,
                                   content_type: str = None) -> Tuple[bool, str]:
        """
        Crea contenido para un tema basado en una plantilla.
        
        Args:
            template_id: ID de la plantilla a usar
            topic_id: ID del tema donde crear el contenido
            props: Propiedades para personalizar la plantilla
            assets: Assets específicos para esta instancia
            learning_mix: Mix VARK personalizado
            content_type: Tipo de contenido a crear (inferido de la plantilla si no se proporciona)
            
        Returns:
            Tuple[bool, str]: (éxito, mensaje/ID del contenido creado)
        """
        try:
            # Verificar que la plantilla existe
            template = self.template_service.get_template(template_id)
            if not template:
                return False, "Plantilla no encontrada"
            
            # Verificar que el tema existe
            if not self.content_service.check_topic_exists(topic_id):
                return False, "Tema no encontrado"
            
            # Crear instancia de plantilla
            instance_data = {
                "template_id": template_id,
                "topic_id": topic_id,
                "props": props or {},
                "assets": assets or [],
                "learning_mix": learning_mix
            }
            
            instance = self.instance_service.create_instance(instance_data)
            
            # Inferir content_type de la plantilla si no se proporciona
            if not content_type:
                content_type = self._infer_content_type_from_template(template)
            
            # Crear TopicContent asociado
            content_data = {
                "topic_id": topic_id,
                "content": "",  # El contenido será renderizado dinámicamente
                "content_type": content_type,
                "render_engine": "html_template",
                "instance_id": str(instance._id),
                "template_id": template_id,
                "template_version": template.version,
                "learning_mix": learning_mix or template.baseline_mix,
                "status": "draft",
                "interactive_data": {
                    "template_based": True,
                    "capabilities": template.capabilities
                },
                "personalization_markers": {
                    "template_id": template_id,
                    "instance_id": str(instance._id),
                    "is_template_based": True
                }
            }
            
            success, content_id = self.content_service.create_content(content_data)
            
            if not success:
                # Si falla la creación del contenido, limpiar la instancia
                self.instance_service.delete_instance(str(instance._id))
                return False, f"Error creando contenido: {content_id}"
            
            logging.info(f"Content created from template {template_id}: {content_id}")
            return True, content_id
            
        except Exception as e:
            logging.error(f"Error creating content from template: {str(e)}")
            return False, f"Error interno: {str(e)}"
    
    def get_template_content(self, content_id: str) -> Optional[Dict]:
        """
        Obtiene contenido basado en plantilla con datos enriquecidos.
        
        Args:
            content_id: ID del contenido
            
        Returns:
            Datos del contenido enriquecidos con información de plantilla
        """
        try:
            # Obtener contenido base
            content = self.content_service.get_content(content_id)
            if not content:
                return None
            
            # Si no es contenido basado en plantilla, retornar tal como está
            if content.get("render_engine") != "html_template":
                return content
            
            # Enriquecer con datos de plantilla
            instance_id = content.get("instance_id")
            if instance_id:
                instance = self.instance_service.get_instance(instance_id)
                if instance:
                    template = self.template_service.get_template(str(instance.template_id))
                    if template:
                        content["template_data"] = {
                            "template": template.to_dict(),
                            "instance": instance.to_dict(),
                            "preview_url": f"/preview/instance/{instance_id}"
                        }
            
            return content
            
        except Exception as e:
            logging.error(f"Error getting template content {content_id}: {str(e)}")
            return None
    
    def update_template_content(self, content_id: str, update_data: Dict) -> Tuple[bool, str]:
        """
        Actualiza contenido basado en plantilla.
        
        Args:
            content_id: ID del contenido
            update_data: Datos a actualizar (principalmente props de la instancia)
            
        Returns:
            Tuple[bool, str]: (éxito, mensaje)
        """
        try:
            # Obtener contenido actual
            content = self.content_service.get_content(content_id)
            if not content:
                return False, "Contenido no encontrado"
            
            if content.get("render_engine") != "html_template":
                return False, "El contenido no está basado en plantilla"
            
            instance_id = content.get("instance_id")
            if not instance_id:
                return False, "Instancia de plantilla no encontrada"
            
            # Actualizar instancia si hay props
            if "props" in update_data or "assets" in update_data or "learning_mix" in update_data:
                instance_update = {}
                if "props" in update_data:
                    instance_update["props"] = update_data["props"]
                if "assets" in update_data:
                    instance_update["assets"] = update_data["assets"]
                if "learning_mix" in update_data:
                    instance_update["learning_mix"] = update_data["learning_mix"]
                
                _ = self.instance_service.update_instance(instance_id, instance_update)
                
                # Actualizar learning_mix en el contenido también
                if "learning_mix" in update_data:
                    content_update = {
                        "learning_mix": update_data["learning_mix"],
                        "updated_at": datetime.now()
                    }
                    self.content_service.update_content(content_id, content_update)
            
            # Actualizar otros campos del contenido si están presentes
            content_fields = ["status", "personalization_markers"]
            content_update = {}
            for field in content_fields:
                if field in update_data:
                    content_update[field] = update_data[field]
            
            if content_update:
                content_update["updated_at"] = datetime.now()
                success, message = self.content_service.update_content(content_id, content_update)
                if not success:
                    return False, message
            
            return True, "Contenido actualizado exitosamente"
            
        except Exception as e:
            logging.error(f"Error updating template content {content_id}: {str(e)}")
            return False, f"Error interno: {str(e)}"
    
    def publish_template_content(self, content_id: str) -> Tuple[bool, str]:
        """
        Publica contenido basado en plantilla (marca instancia y contenido como activos).
        """
        try:
            content = self.content_service.get_content(content_id)
            if not content:
                return False, "Contenido no encontrado"
            
            if content.get("render_engine") != "html_template":
                return False, "El contenido no está basado en plantilla"
            
            instance_id = content.get("instance_id")
            if instance_id:
                # Publicar instancia
                self.instance_service.publish_instance(instance_id)
            
            # Actualizar estado del contenido
            success, message = self.content_service.update_content(content_id, {
                "status": "active"
            })
            
            return success, message
            
        except Exception as e:
            logging.error(f"Error publishing template content {content_id}: {str(e)}")
            return False, f"Error interno: {str(e)}"
    
    def get_available_templates_for_topic(self, topic_id: str, user_id: str = None) -> List[Dict]:
        """
        Obtiene plantillas disponibles para usar en un tema específico.
        
        Args:
            topic_id: ID del tema
            user_id: ID del usuario (para filtrar plantillas privadas)
            
        Returns:
            Lista de plantillas disponibles
        """
        try:
            # Obtener plantillas públicas y del usuario
            templates = self.template_service.list_templates(
                owner_filter="all",
                user_id=user_id
            )
            
            # Filtrar solo plantillas utilizables
            usable_templates = [
                template.to_dict() for template in templates 
                if template.status in ["usable", "certified"]
            ]
            
            # TODO: Filtrar por compatibilidad con el tema (por subject_tags, etc.)
            
            return usable_templates
            
        except Exception as e:
            logging.error(f"Error getting available templates: {str(e)}")
            return []
    
    def migrate_content_to_template(self, content_id: str, template_id: str) -> Tuple[bool, str]:
        """
        Migra contenido legacy existente para usar una plantilla.
        
        Args:
            content_id: ID del contenido existente
            template_id: ID de la plantilla a usar
            
        Returns:
            Tuple[bool, str]: (éxito, mensaje)
        """
        try:
            # Obtener contenido actual
            content = self.content_service.get_content(content_id)
            if not content:
                return False, "Contenido no encontrado"
            
            # Verificar que no sea ya basado en plantilla
            if content.get("render_engine") == "html_template":
                return False, "El contenido ya está basado en plantilla"
            
            # Obtener plantilla
            template = self.template_service.get_template(template_id)
            if not template:
                return False, "Plantilla no encontrada"
            
            # Crear instancia de plantilla intentando mapear el contenido existente
            props = self._extract_props_from_legacy_content(content, template)
            
            instance_data = {
                "template_id": template_id,
                "topic_id": content["topic_id"],
                "props": props,
                "learning_mix": content.get("learning_mix")
            }
            
            instance = self.instance_service.create_instance(instance_data)
            
            # Actualizar contenido para usar plantilla
            update_data = {
                "render_engine": "html_template",
                "instance_id": str(instance._id),
                "template_id": template_id,
                "template_version": template.version,
                "personalization_markers": {
                    **content.get("personalization_markers", {}),
                    "template_id": template_id,
                    "instance_id": str(instance._id),
                    "is_template_based": True,
                    "migrated_from_legacy": True
                }
            }
            
            success, message = self.content_service.update_content(content_id, update_data)
            
            if not success:
                # Limpiar instancia si falla
                self.instance_service.delete_instance(str(instance._id))
                return False, f"Error migrando contenido: {message}"
            
            return True, "Contenido migrado exitosamente"
            
        except Exception as e:
            logging.error(f"Error migrating content to template: {str(e)}")
            return False, f"Error interno: {str(e)}"
    
    def _infer_content_type_from_template(self, template: Template) -> str:
        """
        Infiere el tipo de contenido basado en las características de la plantilla.
        """
        # Usar tags de estilo para inferir tipo
        style_tags = template.style_tags
        
        if "mindmap" in style_tags or "diagram" in style_tags:
            return "diagram"
        elif "game" in style_tags or "interactive" in style_tags:
            return "simulation"  # Usar simulation como tipo genérico para contenido interactivo
        elif "presentation" in style_tags or "slide" in style_tags:
            return "slide"
        elif "exercise" in style_tags or "practice" in style_tags:
            return "completion_exercise"
        else:
            return "interactive_content"  # Tipo genérico
    
    def _extract_props_from_legacy_content(self, content: Dict, template: Template) -> Dict:
        """
        Extrae propiedades de contenido legacy para mapear a una plantilla.
        """
        props = {}
        
        # Mapear contenido básico si existe
        if content.get("content"):
            props["content"] = content["content"]
        
        # Mapear datos interactivos
        if content.get("interactive_data"):
            interactive_data = content["interactive_data"]
            
            # Mapear campos comunes
            common_mappings = {
                "title": "title",
                "description": "description",
                "instructions": "instructions",
                "question": "question",
                "feedback": "feedback"
            }
            
            for legacy_key, prop_key in common_mappings.items():
                if legacy_key in interactive_data:
                    props[prop_key] = interactive_data[legacy_key]
        
        # Aplicar defaults de la plantilla para campos no mapeados
        for prop_name, default_value in template.defaults.items():
            if prop_name not in props:
                props[prop_name] = default_value
        
        return props
