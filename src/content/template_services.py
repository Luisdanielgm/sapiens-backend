import logging
import re
import json
from datetime import datetime
from bson import ObjectId
from typing import Dict, List, Optional, Union
from pymongo import MongoClient
from pymongo.collection import Collection
import os

from .template_models import Template, TemplateInstance
from src.shared.database import get_db

class TemplateService:
    """
    Servicio para gestionar plantillas de contenido educativo HTML.
    """
    
    def __init__(self):
        self.db = get_db()
        self.templates_collection: Collection = self.db.templates
        
    def create_template(self, template_data: Dict, user_id: str) -> Template:
        """
        Crea una nueva plantilla.
        """
        try:
            # Validar datos mínimos
            if not template_data.get("name"):
                raise ValueError("El nombre de la plantilla es requerido")
            
            # Crear plantilla con datos por defecto (soporte de versiones)
            template = Template(
                name=template_data["name"],
                owner_id=user_id,
                html=template_data.get("html", ""),
                versions=template_data.get("versions"),
                description=template_data.get("description", ""),
                scope=template_data.get("scope", "private"),
                style_tags=template_data.get("style_tags", []),
                subject_tags=template_data.get("subject_tags", []),
                baseline_mix=template_data.get("baseline_mix"),
                capabilities=template_data.get("capabilities", {})
            )
            
            # Insertar en base de datos
            result = self.templates_collection.insert_one(template.to_dict())
            template._id = result.inserted_id
            
            logging.info(f"Template created with ID: {template._id}")
            return template
            
        except Exception as e:
            logging.error(f"Error creating template: {str(e)}")
            raise e
    
    def get_template(self, template_id: str) -> Optional[Template]:
        """
        Obtiene una plantilla por ID.
        """
        try:
            template_data = self.templates_collection.find_one({"_id": ObjectId(template_id)})
            if not template_data:
                return None
            
            return Template(**template_data)
            
        except Exception as e:
            logging.error(f"Error getting template {template_id}: {str(e)}")
            raise e
    
    def list_templates(self, 
                      owner_filter: str = "all", 
                      scope_filter: str = None, 
                      user_id: str = None,
                      workspace_id: str = None) -> List[Template]:
        """
        Lista plantillas con filtros.
        
        Args:
            owner_filter: "me" | "all"
            scope_filter: "public" | "org" | "private" | None
            user_id: ID del usuario actual
            workspace_id: ID del workspace actual
        """
        try:
            query = {}
            
            # Filtro de propietario
            if owner_filter == "me" and user_id:
                query["owner_id"] = ObjectId(user_id)
            elif owner_filter == "all":
                # Para "all", incluir públicas y del usuario/org
                scope_conditions = [{"scope": "public"}]
                
                if user_id:
                    scope_conditions.append({"owner_id": ObjectId(user_id)})
                
                # TODO: Añadir filtro por organización cuando se implemente
                if workspace_id:
                    # scope_conditions.append({"workspace_id": ObjectId(workspace_id), "scope": "org"})
                    pass
                
                query["$or"] = scope_conditions
            
            # Filtro de scope
            if scope_filter:
                if "$or" in query:
                    # Si ya hay filtro OR, combinar con scope
                    query = {"$and": [query, {"scope": scope_filter}]}
                else:
                    query["scope"] = scope_filter
            
            # Ejecutar consulta
            templates_data = list(self.templates_collection.find(query).sort("created_at", -1))
            
            return [Template(**template_data) for template_data in templates_data]
            
        except Exception as e:
            logging.error(f"Error listing templates: {str(e)}")
            raise e
    
    def update_template(self, template_id: str, update_data: Dict, user_id: str) -> Template:
        """
        Actualiza una plantilla existente.
        """
        try:
            # Verificar permisos
            template = self.get_template(template_id)
            if not template:
                raise ValueError("Plantilla no encontrada")
            
            if str(template.owner_id) != user_id:
                raise PermissionError("No tienes permisos para editar esta plantilla")
            
            # Si viene html, crear una nueva versión y actualizar campos derivados
            update_dict = {"updated_at": datetime.now()}
            if "html" in update_data and isinstance(update_data["html"], str):
                # agregar nueva versión al array versions
                latest_version_number = template.get_latest_version_number()
                new_version_number = latest_version_number + 1
                new_version = {
                    "version_number": new_version_number,
                    "html": update_data["html"],
                    "status": update_data.get("version_status", template.status),
                    "created_at": datetime.now()
                }
                update_dict.setdefault("$push", {})
                update_dict["$push"]["versions"] = new_version
                # sincronizar ‘html’ plano y ‘version’ principal para compatibilidad
                update_dict.setdefault("$set", {})
                update_dict["$set"].update({
                    "html": update_data["html"],
                    "version": str(new_version_number)
                })
                # permitir actualizar status/description/etc. en el mismo request
                scalar_fields = [
                    "name", "description", "scope", "status",
                    "style_tags", "subject_tags", "baseline_mix", "capabilities",
                    "props_schema", "defaults", "personalization"
                ]
                for field in scalar_fields:
                    if field in update_data:
                        update_dict["$set"][field] = update_data[field]
            else:
                # actualización normal de campos (sin nueva versión)
                scalar_fields = [
                    "name", "description", "scope", "status",
                    "style_tags", "subject_tags", "baseline_mix", "capabilities",
                    "props_schema", "defaults", "personalization"
                ]
                update_dict = {"$set": {"updated_at": datetime.now()}}
                for field in scalar_fields:
                    if field in update_data:
                        update_dict["$set"][field] = update_data[field]
            
            # Actualizar en base de datos
            result = self.templates_collection.update_one(
                {"_id": ObjectId(template_id)},
                update_dict
            )
            
            if result.modified_count == 0:
                raise ValueError("No se pudo actualizar la plantilla")
            
            # Retornar plantilla actualizada
            return self.get_template(template_id)
            
        except Exception as e:
            logging.error(f"Error updating template {template_id}: {str(e)}")
            raise e
    
    def fork_template(self, template_id: str, user_id: str, new_name: str = None) -> Template:
        """
        Crea una copia (fork) de una plantilla existente.
        """
        try:
            # Obtener plantilla original
            original = self.get_template(template_id)
            if not original:
                raise ValueError("Plantilla original no encontrada")
            
            # Solo se pueden hacer fork de plantillas públicas o propias
            if original.scope not in ["public", "org"] and str(original.owner_id) != user_id:
                raise PermissionError("No tienes permisos para hacer fork de esta plantilla")
            
            # Crear nueva plantilla
            fork_name = new_name or f"{original.name} (Fork)"
            
            fork_template = Template(
                name=fork_name,
                owner_id=user_id,
                html=original.get_latest_html(),
                versions=original.versions,
                description=f"Fork de: {original.name}",
                fork_of=str(original._id),
                props_schema=original.props_schema.copy(),
                defaults=original.defaults.copy(),
                baseline_mix=original.baseline_mix.copy(),
                capabilities=original.capabilities.copy(),
                style_tags=original.style_tags.copy(),
                subject_tags=original.subject_tags.copy(),
                scope="private",  # Los forks siempre empiezan como privados
                status="draft"
            )
            
            # Insertar en base de datos
            result = self.templates_collection.insert_one(fork_template.to_dict())
            fork_template._id = result.inserted_id
            
            logging.info(f"Template forked: {template_id} -> {fork_template._id}")
            return fork_template
            
        except Exception as e:
            logging.error(f"Error forking template {template_id}: {str(e)}")
            raise e
    
    def delete_template(self, template_id: str, user_id: str) -> bool:
        """
        Elimina una plantilla (solo el propietario).
        """
        try:
            # Verificar permisos
            template = self.get_template(template_id)
            if not template:
                raise ValueError("Plantilla no encontrada")
            
            if str(template.owner_id) != user_id:
                raise PermissionError("No tienes permisos para eliminar esta plantilla")
            
            # TODO: Verificar que no hay instancias activas de esta plantilla
            
            # Eliminar de base de datos
            result = self.templates_collection.delete_one({"_id": ObjectId(template_id)})
            
            return result.deleted_count > 0
            
        except Exception as e:
            logging.error(f"Error deleting template {template_id}: {str(e)}")
            raise e

class TemplateInstanceService:
    """
    Servicio para gestionar instancias de plantillas ligadas a temas.
    """
    
    def __init__(self):
        self.db = get_db()
        self.instances_collection: Collection = self.db.template_instances
        self.template_service = TemplateService()
        
    def create_instance(self, instance_data: Dict) -> TemplateInstance:
        """
        Crea una nueva instancia de plantilla.
        """
        try:
            # Validar que la plantilla existe
            template = self.template_service.get_template(instance_data["template_id"])
            if not template:
                raise ValueError("Plantilla no encontrada")
            
            # Crear instancia con valores por defecto de la plantilla
            initial_props = template.defaults.copy()
            initial_props.update(instance_data.get("props", {}))
            
            instance = TemplateInstance(
                template_id=instance_data["template_id"],
                template_version=template.version,
                topic_id=instance_data["topic_id"],
                props=initial_props,
                assets=instance_data.get("assets", []),
                learning_mix=instance_data.get("learning_mix")
            )
            
            # Insertar en base de datos
            result = self.instances_collection.insert_one(instance.to_dict())
            instance._id = result.inserted_id
            
            logging.info(f"Template instance created with ID: {instance._id}")
            return instance
            
        except Exception as e:
            logging.error(f"Error creating template instance: {str(e)}")
            raise e
    
    def get_instance(self, instance_id: str) -> Optional[TemplateInstance]:
        """
        Obtiene una instancia por ID.
        """
        try:
            instance_data = self.instances_collection.find_one({"_id": ObjectId(instance_id)})
            if not instance_data:
                return None
            
            return TemplateInstance(**instance_data)
            
        except Exception as e:
            logging.error(f"Error getting template instance {instance_id}: {str(e)}")
            raise e
    
    def get_instances_by_topic(self, topic_id: str) -> List[TemplateInstance]:
        """
        Obtiene todas las instancias de un tema.
        """
        try:
            instances_data = list(self.instances_collection.find({"topic_id": ObjectId(topic_id)}))
            return [TemplateInstance(**instance_data) for instance_data in instances_data]
            
        except Exception as e:
            logging.error(f"Error getting instances for topic {topic_id}: {str(e)}")
            raise e
    
    def update_instance(self, instance_id: str, update_data: Dict) -> TemplateInstance:
        """
        Actualiza una instancia de plantilla.
        """
        try:
            instance = self.get_instance(instance_id)
            if not instance:
                raise ValueError("Instancia no encontrada")
            
            # Campos actualizables
            allowed_fields = ["props", "assets", "learning_mix", "status"]
            
            update_dict = {"updated_at": datetime.now()}
            for field in allowed_fields:
                if field in update_data:
                    update_dict[field] = update_data[field]
            
            # Actualizar en base de datos
            result = self.instances_collection.update_one(
                {"_id": ObjectId(instance_id)},
                {"$set": update_dict}
            )
            
            if result.modified_count == 0:
                raise ValueError("No se pudo actualizar la instancia")
            
            return self.get_instance(instance_id)
            
        except Exception as e:
            logging.error(f"Error updating template instance {instance_id}: {str(e)}")
            raise e
    
    def publish_instance(self, instance_id: str) -> TemplateInstance:
        """
        Marca una instancia como publicada/activa.
        """
        try:
            return self.update_instance(instance_id, {"status": "active"})
            
        except Exception as e:
            logging.error(f"Error publishing template instance {instance_id}: {str(e)}")
            raise e
    
    def delete_instance(self, instance_id: str) -> bool:
        """
        Elimina una instancia de plantilla.
        """
        try:
            # TODO: Verificar que no hay VirtualTopicContent referenciando esta instancia
            
            result = self.instances_collection.delete_one({"_id": ObjectId(instance_id)})
            return result.deleted_count > 0
            
        except Exception as e:
            logging.error(f"Error deleting template instance {instance_id}: {str(e)}")
            raise e

class TemplateMarkupExtractor:
    """
    Servicio para extraer marcadores de personalización del HTML de plantillas.
    """
    
    @staticmethod
    def extract_markers(html_content: str) -> Dict:
        """
        Extrae marcadores de personalización del HTML de una plantilla.
        
        Busca:
        - data-sapiens-param="paramName" -> parámetros configurables
        - data-sapiens-asset="assetName" -> recursos externos requeridos
        - data-sapiens-slot="slotName" -> contenido personalizable por IA
        - data-sapiens-if="condition" -> lógica condicional
        """
        try:
            schema = {
                "type": "object",
                "properties": {},
                "required": []
            }
            
            # Buscar parámetros
            param_pattern = r'data-sapiens-param=["\']([^"\']+)["\']'
            param_matches = re.findall(param_pattern, html_content, re.IGNORECASE)
            
            for param_name in set(param_matches):
                # Inferir tipo básico del contexto
                param_type = TemplateMarkupExtractor._infer_param_type(html_content, param_name)
                
                schema["properties"][param_name] = {
                    "type": param_type,
                    "title": param_name.replace("_", " ").title(),
                    "description": f"Parámetro configurable: {param_name}"
                }
            
            # Buscar assets
            asset_pattern = r'data-sapiens-asset=["\']([^"\']+)["\']'
            asset_matches = re.findall(asset_pattern, html_content, re.IGNORECASE)
            
            for asset_name in set(asset_matches):
                schema["properties"][asset_name] = {
                    "type": "string",
                    "format": "uri",
                    "title": asset_name.replace("_", " ").title(),
                    "description": f"Recurso requerido: {asset_name}"
                }
            
            # Buscar slots de contenido personalizable
            slot_pattern = r'data-sapiens-slot=["\']([^"\']+)["\']'
            slot_matches = re.findall(slot_pattern, html_content, re.IGNORECASE)
            
            for slot_name in set(slot_matches):
                schema["properties"][slot_name] = {
                    "type": "string",
                    "format": "textarea",
                    "title": slot_name.replace("_", " ").title(),
                    "description": f"Contenido personalizable: {slot_name}"
                }
            
            # Buscar condiciones
            condition_pattern = r'data-sapiens-if=["\']([^"\']+)["\']'
            condition_matches = re.findall(condition_pattern, html_content, re.IGNORECASE)
            
            for condition in set(condition_matches):
                # Las condiciones suelen ser booleanas
                condition_param = f"show_{condition}"
                schema["properties"][condition_param] = {
                    "type": "boolean",
                    "title": f"Mostrar {condition}",
                    "description": f"Controla la visibilidad de: {condition}",
                    "default": True
                }
            
            # Buscar defaults en script
            defaults = TemplateMarkupExtractor._extract_defaults(html_content)
            
            return {
                "props_schema": schema,
                "defaults": defaults,
                "markers_found": {
                    "params": list(set(param_matches)),
                    "assets": list(set(asset_matches)),
                    "slots": list(set(slot_matches)),
                    "conditions": list(set(condition_matches))
                }
            }
            
        except Exception as e:
            logging.error(f"Error extracting markers: {str(e)}")
            raise e
    
    @staticmethod
    def _infer_param_type(html_content: str, param_name: str) -> str:
        """
        Infiere el tipo de un parámetro basado en el contexto HTML.
        """
        # Buscar el contexto donde aparece el parámetro
        context_pattern = rf'[^>]*data-sapiens-param=["\']?{re.escape(param_name)}["\']?[^<]*'
        context_match = re.search(context_pattern, html_content, re.IGNORECASE)
        
        if not context_match:
            return "string"
        
        context = context_match.group(0).lower()
        
        # Inferir tipo por contexto
        if 'color' in param_name.lower() or 'background' in context or 'color' in context:
            return "string"  # Podríamos usar "color" si el frontend lo soporta
        elif 'width' in param_name.lower() or 'height' in param_name.lower() or 'size' in param_name.lower():
            return "number"
        elif param_name.lower().startswith('is_') or param_name.lower().startswith('show_'):
            return "boolean"
        elif 'url' in param_name.lower() or 'src' in context:
            return "string"
        else:
            return "string"
    
    @staticmethod
    def _extract_defaults(html_content: str) -> Dict:
        """
        Extrae valores por defecto del script de configuración en el HTML.
        """
        try:
            # Buscar script con defaults
            script_pattern = r'<script[^>]*id=["\']sapiens-defaults["\'][^>]*type=["\']application/json["\'][^>]*>(.*?)</script>'
            script_match = re.search(script_pattern, html_content, re.IGNORECASE | re.DOTALL)
            
            if script_match:
                defaults_json = script_match.group(1).strip()
                return json.loads(defaults_json)
            
            return {}
            
        except (json.JSONDecodeError, Exception) as e:
            logging.warning(f"Could not extract defaults from HTML: {str(e)}")
            return {}
