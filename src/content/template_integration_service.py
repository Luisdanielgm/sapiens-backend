import logging
from datetime import datetime
from bson import ObjectId
from typing import Dict, List, Optional, Any, Tuple

from src.shared.database import get_db
from .services import ContentService
from .template_services import TemplateService, TemplateInstanceService
from .template_models import Template
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
                                   content_type: str = None,
                                   template_metadata: Optional[Dict] = None,
                                   created_by: Optional[str] = None) -> Tuple[bool, str]:
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
            
            # Preparar metadatos pedagógicos
            normalized_metadata = self._prepare_template_metadata(template_metadata)

            # Inferir content_type de la plantilla si no se proporciona
            if not content_type:
                content_type = self._infer_content_type_from_template(template)
            
            # Crear TopicContent asociado
            content_payload = normalized_metadata.copy() if isinstance(normalized_metadata, dict) else {}
            content_data = {
                "topic_id": topic_id,
                "content": content_payload,
                "content_type": content_type,
                "render_engine": "html_template",
                "template_id": template_id,
                "template_version": template.version,
                "learning_mix": learning_mix or template.baseline_mix,
                "status": "draft",
                "interactive_data": {
                    "template_based": True,
                    "capabilities": template.capabilities,
                    "metadata": normalized_metadata or {}
                },
                "personalization_markers": {
                    "template_id": template_id,
                    "is_template_based": True
                }
            }

            if normalized_metadata:
                metadata_markers = {
                    key: normalized_metadata.get(key)
                    for key in ["interactive_summary", "interaction_mode", "estimated_duration_seconds"]
                    if normalized_metadata.get(key) is not None
                }
                if metadata_markers:
                    content_data["personalization_markers"]["template_metadata"] = metadata_markers
            
            success, content_id = self.content_service.create_content(content_data)
            
            if not success:
                return False, f"Error creando contenido: {content_id}"

            self.template_service.record_template_usage(
                template=template,
                topic_id=topic_id,
                content_id=content_id,
                user_id=created_by,
                metadata=normalized_metadata,
                status=content_data.get("status"),
                source="content.from_template"
            )
            
            logging.info(f"Content created from template {template_id}: {content_id}")
            return True, content_id
            
        except Exception as e:
            logging.error(f"Error creating content from template: {str(e)}")
            return False, f"Error interno: {str(e)}"

    def apply_template_to_content(self,
                                  template_id: str,
                                  topic_id: str,
                                  content_payload: Dict,
                                  *,
                                  order: Optional[int] = None,
                                  parent_content_id: Optional[str] = None,
                                  learning_mix: Optional[Dict] = None,
                                  content_type: str = "slide",
                                  status: str = "draft",
                                  template_metadata: Optional[Dict] = None,
                                  personalization_markers: Optional[Dict] = None,
                                  created_by: Optional[str] = None) -> Tuple[bool, str]:
        """
        Inserta un artefacto basado en plantilla directamente como TopicContent sin crear template_instance.
        """
        try:
            template = self.template_service.get_template(template_id)
            if not template:
                return False, "Plantilla no encontrada"

            if not self.content_service.check_topic_exists(topic_id):
                return False, "Tema no encontrado"

            if not isinstance(content_payload, dict):
                return False, "El contenido debe ser un objeto"

            normalized_metadata = self._prepare_template_metadata(
                template_metadata or (template.defaults if isinstance(getattr(template, "defaults", None), dict) else None)
            )

            final_content = content_payload.copy()

            attachment = final_content.get("attachment") or {}
            if not isinstance(attachment, dict):
                attachment = {}
            attachment.setdefault("type", "interactive_template")
            attachment["template_id"] = template_id
            attachment["template_version"] = template.version
            final_content["attachment"] = attachment

            if normalized_metadata:
                final_content["template_metadata"] = normalized_metadata

            learning_mix_payload = learning_mix or content_payload.get("baseline_mix") or template.baseline_mix
            if isinstance(final_content.get("baseline_mix"), dict):
                learning_mix_payload = final_content.get("baseline_mix")

            merged_markers = {}
            if isinstance(personalization_markers, dict):
                merged_markers.update(personalization_markers)
            existing_markers = content_payload.get("personalization_markers")
            if isinstance(existing_markers, dict):
                merged_markers.update(existing_markers)
            merged_markers.update({
                "template_id": template_id,
                "template_name": template.name,
                "template_metadata": normalized_metadata
            })

            content_data = {
                "topic_id": topic_id,
                "content": final_content,
                "content_type": content_type or content_payload.get("content_type") or "slide",
                "render_engine": "html_template",
                "template_id": template_id,
                "template_version": template.version,
                "learning_mix": learning_mix_payload,
                "order": order if order is not None else content_payload.get("order"),
                "parent_content_id": parent_content_id or content_payload.get("parent_content_id"),
                "status": status or content_payload.get("status") or "draft",
                "personalization_markers": merged_markers
            }

            success, content_id = self.content_service.create_content(content_data)
            if not success:
                return False, content_id

            usage_metadata = final_content.get("template_metadata") or normalized_metadata
            self.template_service.record_template_usage(
                template=template,
                topic_id=topic_id,
                content_id=content_id,
                user_id=created_by,
                parent_content_id=parent_content_id or content_payload.get("parent_content_id"),
                order=content_data.get("order"),
                metadata=usage_metadata,
                status=content_data.get("status"),
                source="templates.apply"
            )
            return True, content_id
        except Exception as e:
            logging.error(f"Error applying template to content: {str(e)}")
            return False, f"Error interno: {str(e)}"

    def _prepare_template_metadata(self, metadata: Optional[Dict]) -> Dict:
        """
        Normaliza los metadatos pedagógicos asociados a una instancia/TopicContent.
        """
        if not isinstance(metadata, dict):
            return {}

        normalized: Dict[str, Any] = {}

        summary = metadata.get("interactive_summary")
        if isinstance(summary, str):
            summary = summary.strip()
            if summary:
                normalized["interactive_summary"] = summary

        objectives = metadata.get("learning_objectives")
        if isinstance(objectives, list):
            cleaned = [str(obj).strip() for obj in objectives if str(obj).strip()]
            if cleaned:
                normalized["learning_objectives"] = cleaned
        elif isinstance(objectives, str):
            cleaned = [segment.strip() for segment in objectives.split("\n") if segment.strip()]
            if cleaned:
                normalized["learning_objectives"] = cleaned

        duration = metadata.get("estimated_duration_seconds") or metadata.get("estimated_duration")
        if isinstance(duration, (int, float)):
            duration_int = int(duration)
            if duration_int > 0:
                normalized["estimated_duration_seconds"] = duration_int
        elif isinstance(duration, str) and duration.isdigit():
            duration_int = int(duration)
            if duration_int > 0:
                normalized["estimated_duration_seconds"] = duration_int

        interaction_mode = metadata.get("interaction_mode") or metadata.get("activity_mode")
        if isinstance(interaction_mode, str):
            interaction_mode = interaction_mode.strip()
            if interaction_mode:
                normalized["interaction_mode"] = interaction_mode

        accessibility = metadata.get("accessibility_tags")
        if isinstance(accessibility, list):
            cleaned = [str(tag).strip() for tag in accessibility if str(tag).strip()]
            if cleaned:
                normalized["accessibility_tags"] = cleaned

        audience = metadata.get("target_audience")
        if isinstance(audience, str):
            audience = audience.strip()
            if audience:
                normalized["target_audience"] = audience

        return normalized
    
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
            normalized_metadata = None
            if "template_metadata" in update_data or "metadata" in update_data:
                normalized_metadata = self._prepare_template_metadata(
                    update_data.get("template_metadata") or update_data.get("metadata")
                )

            if "props" in update_data or "assets" in update_data or "learning_mix" in update_data or normalized_metadata:
                instance_update = {}
                if "props" in update_data:
                    instance_update["props"] = update_data["props"]
                if "assets" in update_data:
                    instance_update["assets"] = update_data["assets"]
                if "learning_mix" in update_data:
                    instance_update["learning_mix"] = update_data["learning_mix"]
                if normalized_metadata:
                    instance_update["metadata"] = normalized_metadata
                
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

            if normalized_metadata:
                existing_content = content.get("content") if isinstance(content.get("content"), dict) else {}
                new_content_block = existing_content.copy()
                new_content_block.update(normalized_metadata)
                content_update["content"] = new_content_block

                existing_interactive_data = content_update.get("interactive_data") or content.get("interactive_data") or {}
                interactive_data_update = existing_interactive_data.copy()
                interactive_data_update["metadata"] = normalized_metadata
                content_update["interactive_data"] = interactive_data_update

                personalization_markers = content_update.get("personalization_markers")
                if isinstance(personalization_markers, dict):
                    personalization_markers = personalization_markers.copy()
                else:
                    personalization_markers = (content.get("personalization_markers") or {}).copy()
                metadata_markers = {
                    key: normalized_metadata.get(key)
                    for key in ["interactive_summary", "interaction_mode", "estimated_duration_seconds"]
                    if normalized_metadata.get(key) is not None
                }
                if metadata_markers:
                    personalization_markers["template_metadata"] = metadata_markers
                    content_update["personalization_markers"] = personalization_markers
            
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
