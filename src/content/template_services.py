import logging
import re
import json
import copy
from datetime import datetime
from bson import ObjectId
from typing import Any, Dict, List, Optional, Union, Tuple
from pymongo import MongoClient
from pymongo.collection import Collection
import os

from .template_models import Template, TemplateInstance
from src.shared.database import get_db
from .models import LearningMethodologyTypes, DeprecatedContentTypes, ContentTypes

class TemplateService:
    """
    Servicio para gestionar plantillas de contenido educativo HTML.
    """
    
    def __init__(self):
        self.db = get_db()
        self.templates_collection: Collection = self.db.templates
        self.template_usage_collection: Collection = self.db.template_usage
        # No crear TemplateInstanceService aquí para evitar recursión entre inicializadores.
    
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
                capabilities=template_data.get("capabilities", {}),
                template_config=copy.deepcopy(template_data.get("template_config", {}))
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

            # Limpiar datos para evitar problemas de compatibilidad
            cleaned_data = self._clean_template_data(template_data)
            return Template(**cleaned_data)

        except Exception as e:
            logging.error(f"Error getting template {template_id}: {str(e)}")
            raise e

    def _clean_template_data(self, template_data: Dict) -> Dict:
        """
        Limpia y valida los datos de la plantilla para evitar errores de construcción.
        """
        try:
            cleaned = {}

            # Campos requeridos
            cleaned['name'] = template_data.get('name', 'Sin nombre')
            cleaned['owner_id'] = str(template_data.get('owner_id', ''))

            # Campos opcionales con valores por defecto
            cleaned['html'] = template_data.get('html', '')
            cleaned['engine'] = template_data.get('engine', 'html')
            cleaned['version'] = template_data.get('version', '1.0.0')
            cleaned['scope'] = template_data.get('scope', 'private')
            cleaned['status'] = template_data.get('status', 'draft')
            cleaned['description'] = template_data.get('description', '')
            cleaned['fork_of'] = template_data.get('fork_of')
            cleaned['props_schema'] = template_data.get('props_schema', {})
            cleaned['defaults'] = template_data.get('defaults', {})
            cleaned['baseline_mix'] = template_data.get('baseline_mix', {"V": 25, "A": 25, "K": 25, "R": 25})
            cleaned['capabilities'] = template_data.get('capabilities', {})
            cleaned['style_tags'] = template_data.get('style_tags', [])
            cleaned['subject_tags'] = template_data.get('subject_tags', [])
            cleaned['versions'] = template_data.get('versions', [])
            # Propagar metadata de personalización si existe (estado de extracción de marcadores, etc.)
            cleaned['personalization'] = template_data.get('personalization', {})
            cleaned['template_config'] = template_data.get('template_config', {})

            # Campos de fecha
            cleaned['_id'] = template_data.get('_id')
            cleaned['created_at'] = template_data.get('created_at')
            cleaned['updated_at'] = template_data.get('updated_at')

            return cleaned

        except Exception as e:
            logging.error(f"Error limpiando datos de plantilla: {str(e)}")
            raise ValueError(f"Error procesando datos de plantilla: {str(e)}")

    def record_template_usage(
        self,
        template: Template,
        *,
        topic_id: Optional[str],
        content_id: str,
        user_id: Optional[str] = None,
        parent_content_id: Optional[str] = None,
        order: Optional[Union[int, float]] = None,
        metadata: Optional[Dict] = None,
        status: Optional[str] = None,
        source: Optional[str] = None,
    ) -> None:
        """
        Registra un snapshot del uso de una plantilla para analytics.
        Los errores se registran como warning sin interrumpir el flujo principal.
        """
        if not template or not content_id:
            return

        metadata_payload: Dict[str, Any] = {}
        if isinstance(metadata, dict):
            metadata_payload = metadata
        elif isinstance(getattr(template, "defaults", None), dict):
            metadata_payload = template.defaults  # type: ignore[assignment]

        usage_doc: Dict[str, Any] = {
            "template_id": self._object_id_or_str(getattr(template, "_id", None)),
            "template_name": getattr(template, "name", None),
            "template_version": getattr(template, "version", None),
            "topic_id": self._object_id_or_str(topic_id),
            "content_id": self._object_id_or_str(content_id),
            "parent_content_id": self._object_id_or_str(parent_content_id),
            "order": order,
            "baseline_mix": getattr(template, "baseline_mix", None),
            "style_tags": getattr(template, "style_tags", None),
            "subject_tags": getattr(template, "subject_tags", None),
            "capabilities": getattr(template, "capabilities", None),
            "metadata": metadata_payload,
            "created_by": self._object_id_or_str(user_id),
            "status": status,
            "source": source or "template.apply",
            "used_at": datetime.utcnow(),
        }

        try:
            usage_doc = {k: v for k, v in usage_doc.items() if v is not None}
            if usage_doc:
                self.template_usage_collection.insert_one(usage_doc)
        except Exception as exc:
            logging.warning(
                f"record_template_usage failed for template {getattr(template, '_id', None)}: {exc}"
            )
    
    def list_templates(self, 
                      owner_filter: str = "all", 
                      scope_filter: str = None, 
                      user_id: str = None,
                      workspace_id: str = None,
                      style_tags: Optional[List[str]] = None,
                      subject_tags: Optional[List[str]] = None,
                      learning_methodology: Optional[str] = None,
                      compatibility_mode: Optional[str] = None,
                      migration_recommended: Optional[bool] = None,
                      limit: int = 100,
                      skip: int = 0,
                      sort: Optional[List[Tuple[str, int]]] = None) -> List[Template]:
        """
        Lista plantillas con filtros optimizados. Mueve la lógica de filtrado por tags al nivel de consulta MongoDB.
        
        Args:
            owner_filter: "me" | "all"
            scope_filter: "public" | "org" | "private" | None
            user_id: ID del usuario actual
            workspace_id: ID del workspace actual
            style_tags: lista de tags de estilo a filtrar (coincidencia ALL)
            subject_tags: lista de tags de materia a filtrar (coincidencia ANY)
            learning_methodology: filtrar plantillas compatibles con esta metodología
            compatibility_mode: modo de compatibilidad (p.ej. "kinesthetic") para incluir plantillas mapeadas
            migration_recommended: si True, solo plantillas marcadas como recomendadas para migración legacy
            limit: número máximo de resultados
            skip: offset
            sort: lista de tuplas (campo, dir) para sort
        """
        try:
            query = {}
            
            # Filtro de propietario
            if owner_filter == "me" and user_id:
                try:
                    query["owner_id"] = ObjectId(user_id)
                except Exception:
                    query["owner_id"] = user_id
            elif owner_filter == "all":
                # Para "all", incluir públicas y del usuario/org
                scope_conditions = [{"scope": "public"}]
                
                if user_id:
                    try:
                        scope_conditions.append({"owner_id": ObjectId(user_id)})
                    except Exception:
                        scope_conditions.append({"owner_id": user_id})
                
                    # Añadir plantillas privadas del usuario
                    scope_conditions.append({"scope": {"$in": ["public", "org", "private"]}})
                
                # Si workspace_id disponible, preferir org scope también
                if workspace_id:
                    # Buscar plantillas de scope org asociadas al workspace (campo workspace_id)
                    try:
                        scope_conditions.append({"workspace_id": ObjectId(workspace_id), "scope": "org"})
                    except Exception:
                        scope_conditions.append({"workspace_id": workspace_id, "scope": "org"})
                
                query["$or"] = scope_conditions
            
            # Filtro de scope explícito
            if scope_filter:
                # Combinar correctamente con posibles $or preexistentes
                if "$or" in query:
                    query = {"$and": [query, {"scope": scope_filter}]}
                else:
                    query["scope"] = scope_filter
            
            # Filtrado por style_tags: requerir que el array style_tags del documento contenga al menos todos los solicitados
            if style_tags:
                if isinstance(style_tags, str):
                    style_tags = [style_tags]
                # usar $all para requerir todos los tags; si se desea $in, cambiar a {"$in": style_tags}
                query["style_tags"] = {"$all": style_tags}
            
            # Filtrado por subject_tags: coincidencia ANY (al menos uno)
            if subject_tags:
                if isinstance(subject_tags, str):
                    subject_tags = [subject_tags]
                query["subject_tags"] = {"$in": subject_tags}
            
            # Filtrado por metodología de aprendizaje: mirar en capabilities.compatible_methodologies o en capabilities.learning_methodologies
            if learning_methodology:
                # buscar en posibles ubicaciones dentro de capabilities
                query["$or"] = query.get("$or", []) + [
                    {"capabilities.compatible_methodologies": learning_methodology},
                    {"capabilities.learning_methodologies": learning_methodology},
                    {"capabilities.methodologies": learning_methodology}
                ]
                # Si previously had a top-level $and container we must keep consistent, but Mongo will accept multiple $or as list
                
            # compatibility_mode: por ejemplo 'kinesthetic' -> map to recommended template tags/mappings
            if compatibility_mode:
                # Map methodology keywords to template name hints using LearningMethodologyTypes mapping
                mapped = LearningMethodologyTypes.map_kinesthetic_to_templates().get(compatibility_mode, [])
                if mapped:
                    # Buscar por name o por capabilities.recommendation
                    query["$or"] = query.get("$or", []) + [
                        {"name": {"$in": mapped}},
                        {"capabilities.recommended_aliases": {"$in": mapped}},
                        {"capabilities.modes": compatibility_mode}
                    ]
                else:
                    # Fallback: attempt to match capability flag
                    query["capabilities.mode"] = compatibility_mode
            
            # migration_recommended: buscar plantillas marcadas para reemplazar legacy games/simulations
            if migration_recommended is not None:
                if migration_recommended:
                    # Buscar campo capabilities.replaces_legacy o migration_recommended = True
                    query["$or"] = query.get("$or", []) + [
                        {"capabilities.replaces_legacy": True},
                        {"migration_recommended": True},
                        {"capabilities.legacy_compatibility": True}
                    ]
                else:
                    # Explicit negative filter
                    query["$and"] = query.get("$and", []) + [
                        {"capabilities.replaces_legacy": {"$ne": True}},
                        {"migration_recommended": {"$ne": True}},
                        {"capabilities.legacy_compatibility": {"$ne": True}}
                    ]
            
            # Ejecutar consulta con paginación y sort opcional
            cursor = self.templates_collection.find(query)
            # aplicar sort por defecto si no se entrega sort
            if sort:
                cursor = cursor.sort(sort)
            else:
                cursor = cursor.sort("created_at", -1)
            if skip and skip > 0:
                cursor = cursor.skip(int(skip))
            if limit and limit > 0:
                cursor = cursor.limit(int(limit))
            
            templates_data = list(cursor)
            
            # Construir objetos Template (se usa _clean_template_data en get_template; aquí usamos Template(**data) similar a antes)
            result = []
            for td in templates_data:
                # intentar limpiar datos parcialmente para evitar errores si faltan campos
                try:
                    result.append(Template(**td))
                except Exception:
                    # fallback: reconstruir con campos mínimos
                    try:
                        cleaned = self._clean_template_data(td)
                        result.append(Template(**cleaned))
                    except Exception:
                        logging.warning(f"list_templates: no se pudo construir Template para documento {_id if ( _id := td.get('_id')) else 'unknown'}; se omite")
                        continue
            
            return result
            
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

            # Validar y sanitizar datos de entrada
            if "html" in update_data:
                html_content = update_data["html"]
                if not isinstance(html_content, str):
                    raise ValueError("El campo 'html' debe ser una cadena de texto")

                # Verificar que el HTML tenga contenido significativo
                if len(html_content.strip()) < 10:
                    raise ValueError("El contenido HTML debe tener al menos 10 caracteres de contenido significativo")

                # Limitar tamaño del HTML (máximo 1MB)
                if len(html_content) > 1024 * 1024:
                    raise ValueError("El contenido HTML es demasiado grande (máximo 1MB)")

                # Actualizar el dato sanitizado
                update_data["html"] = html_content
            
            # Si viene html, crear una nueva versión y actualizar campos derivados
            update_dict = {"$set": {"updated_at": datetime.now()}}
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
                    "props_schema", "defaults", "personalization", "template_config"
                ]
                for field in scalar_fields:
                    if field in update_data:
                        # Validar campos específicos
                        if field == "name" and update_data[field]:
                            if not isinstance(update_data[field], str) or len(update_data[field].strip()) == 0:
                                raise ValueError("El nombre de la plantilla no puede estar vacío")
                            if len(update_data[field]) > 200:
                                raise ValueError("El nombre de la plantilla no puede tener más de 200 caracteres")

                        if field == "scope" and update_data[field]:
                            valid_scopes = ["private", "org", "public"]
                            if update_data[field] not in valid_scopes:
                                raise ValueError(f"El scope debe ser uno de: {valid_scopes}")

                        if field == "status" and update_data[field]:
                            valid_statuses = ["draft", "usable", "certified"]
                            if update_data[field] not in valid_statuses:
                                raise ValueError(f"El status debe ser uno de: {valid_statuses}")

                        update_dict["$set"][field] = update_data[field]
            else:
                # actualización normal de campos (sin nueva versión)
                scalar_fields = [
                    "name", "description", "scope", "status",
                    "style_tags", "subject_tags", "baseline_mix", "capabilities",
                    "props_schema", "defaults", "personalization", "template_config"
                ]
                update_dict = {"$set": {"updated_at": datetime.now()}}
                for field in scalar_fields:
                    if field in update_data:
                        # Validar campos específicos
                        if field == "name" and update_data[field]:
                            if not isinstance(update_data[field], str) or len(update_data[field].strip()) == 0:
                                raise ValueError("El nombre de la plantilla no puede estar vacío")
                            if len(update_data[field]) > 200:
                                raise ValueError("El nombre de la plantilla no puede tener más de 200 caracteres")

                        if field == "scope" and update_data[field]:
                            valid_scopes = ["private", "org", "public"]
                            if update_data[field] not in valid_scopes:
                                raise ValueError(f"El scope debe ser uno de: {valid_scopes}")

                        if field == "status" and update_data[field]:
                            valid_statuses = ["draft", "usable", "certified"]
                            if update_data[field] not in valid_statuses:
                                raise ValueError(f"El status debe ser uno de: {valid_statuses}")

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
                template_config=copy.deepcopy(getattr(original, "template_config", {})),
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

    # Nuevo método optimizado para el endpoint /api/templates/available
    def get_available_templates_for_teacher(self,
                                            teacher_id: str,
                                            workspace_id: Optional[str] = None,
                                            subject: Optional[str] = None,
                                            style: Optional[str] = None,
                                            scope: Optional[str] = "public",
                                            learning_methodology: Optional[str] = None,
                                            compatibility: Optional[str] = None,
                                            limit: int = 50,
                                            skip: int = 0) -> List[Dict]:
        """
        Retorna una lista de plantillas optimizadas para profesores, incluyendo metadata adicional:
        usage_statistics, effectiveness_metrics, migration_compatibility.
        Usa list_templates() internamente para los filtros principales.
        """
        try:
            style_tags = [style] if style else None
            subject_tags = [subject] if subject else None

            # Llamar a list_templates con parámetros apropiados
            templates = self.list_templates(
                owner_filter="all",
                scope_filter=scope,
                user_id=teacher_id,
                workspace_id=workspace_id,
                style_tags=style_tags,
                subject_tags=subject_tags,
                learning_methodology=learning_methodology,
                compatibility_mode=compatibility,
                migration_recommended=None,
                limit=limit,
                skip=skip
            )

            # Preparar colecciones auxiliares para métricas
            instances_coll = self.db.template_instances
            metrics_coll = self.db.template_metrics if "template_metrics" in self.db.list_collection_names() else None

            enriched = []
            for t in templates:
                try:
                    tid = t._id if hasattr(t, "_id") else None
                    tid_obj = ObjectId(tid) if tid else None

                    # usage_count: cantidad de instancias basadas en esta plantilla
                    usage_count = 0
                    if tid_obj:
                        try:
                            usage_count = instances_coll.count_documents({"template_id": tid_obj})
                        except Exception:
                            # fallback: count by string id
                            usage_count = instances_coll.count_documents({"template_id": str(tid_obj)})
                    
                    # effectiveness_score: intentar leer de template_metrics collection si existe
                    effectiveness_score = None
                    if metrics_coll and tid_obj:
                        try:
                            m = metrics_coll.find_one({"template_id": tid_obj})
                            if m and "effectiveness_score" in m:
                                effectiveness_score = float(m.get("effectiveness_score"))
                        except Exception:
                            effectiveness_score = None

                    # migration_compatibility: heurística simple
                    caps = getattr(t, "capabilities", {}) or {}
                    migration_compatibility = bool(caps.get("replaces_legacy") or caps.get("legacy_compatibility") or getattr(t, "migration_recommended", False))

                    # Build result entry
                    entry = {
                        "template_id": str(tid) if tid else None,
                        "name": getattr(t, "name", ""),
                        "description": getattr(t, "description", ""),
                        "scope": getattr(t, "scope", ""),
                        "style_tags": getattr(t, "style_tags", []),
                        "subject_tags": getattr(t, "subject_tags", []),
                        "usage_statistics": {
                            "usage_count": usage_count
                        },
                        "effectiveness_metrics": {
                            "effectiveness_score": effectiveness_score
                        },
                        "migration_compatibility": migration_compatibility,
                        "owner_id": str(getattr(t, "owner_id", "")),
                        "created_at": getattr(t, "created_at", None),
                        "updated_at": getattr(t, "updated_at", None)
                    }
                    enriched.append(entry)
                except Exception as e:
                    logging.warning(f"get_available_templates_for_teacher: error enriqueciendo plantilla: {e}")
                    continue

            # Priorizar plantillas compatibles con migración (si las hay)
            enriched.sort(key=lambda x: (not x.get("migration_compatibility", False), -(x.get("usage_statistics", {}).get("usage_count", 0))),)
            return enriched

        except Exception as e:
            logging.error(f"Error in get_available_templates_for_teacher: {e}")
            return []

    def create_template_instance_for_topic(self,
                                           template_id: str,
                                           topic_id: str,
                                           creator_id: str,
                                           props: Optional[Dict] = None,
                                           auto_generate: bool = False,
                                           migration_source: Optional[Dict] = None,
                                           create_topic_content: bool = False,
                                           content_type_for_instance: str = "slide") -> Dict:
        """
        Encapsula la lógica para crear una instancia de plantilla ligada a un tema.
        Valida permisos, crea la instancia y opcionalmente crea un TopicContent vinculado.
        Soporta extracción de props desde contenidos legacy (migration_source).
        """
        try:
            # Validar plantilla
            template_doc = self.templates_collection.find_one({"_id": ObjectId(template_id)})
            if not template_doc:
                return {"success": False, "error": "Plantilla no encontrada"}

            # Validar acceso según scope
            scope = template_doc.get("scope", "private")
            owner_id = template_doc.get("owner_id")
            if scope == "private" and str(owner_id) != str(creator_id):
                return {"success": False, "error": "No tienes permisos para usar esta plantilla (privada)"}

            # Validar topic existe usando ContentService
            from .services import ContentService
            content_service = ContentService()
            if not content_service.check_topic_exists(topic_id):
                return {"success": False, "error": "Topic no encontrado"}

            # Si viene migration_source intentar mapear props automáticamente
            instance_props = {}
            try:
                instance_props.update(template_doc.get("defaults", {}) or {})
                if props:
                    instance_props.update(props)
                if migration_source and isinstance(migration_source, dict):
                    # Extraer props básicos desde interactive_data o generation_prompt
                    ms_interactive = migration_source.get("interactive_data", {})
                    if isinstance(ms_interactive, dict):
                        # Merge keys that match props_schema if available
                        instance_props.update({k: v for k, v in ms_interactive.items() if k not in instance_props})
                    # If generation_prompt exists, map to 'prompt' prop if template expects it
                    prompt = migration_source.get("generation_prompt")
                    if prompt and "prompt" in (template_doc.get("props_schema") or {}):
                        instance_props["prompt"] = prompt
            except Exception as e:
                logging.warning(f"create_template_instance_for_topic: error mapeando migration_source: {e}")

            # Crear instancia usando TemplateInstanceService
            from .template_services import TemplateInstanceService as _TIS  # local import to avoid circular references at module import time
            # Note: using local import path above to reference same file class; Python will resolve it to current module object.
            instance_service = _TIS()
            instance_payload = {
                "template_id": str(template_doc.get("_id")),
                "topic_id": topic_id,
                "creator_id": creator_id,
                "props": instance_props,
                "assets": template_doc.get("assets", []),
                "learning_mix": template_doc.get("baseline_mix")
            }
            instance_obj = instance_service.create_instance(instance_payload)

            # Opcional: crear TopicContent vinculado a la instancia (inserción directa para evitar validaciones estrictas)
            created_content_id = None
            if create_topic_content:
                try:
                    content_doc = {
                        "topic_id": ObjectId(topic_id),
                        "content": migration_source.get("content") if isinstance(migration_source, dict) else "",
                        "content_type": content_type_for_instance,
                        "interactive_data": migration_source.get("interactive_data") if isinstance(migration_source, dict) else {},
                        "learning_methodologies": migration_source.get("learning_methodologies", []),
                        "render_engine": "html_template",
                        "instance_id": instance_obj._id,
                        "template_id": template_doc.get("_id"),
                        "template_version": template_doc.get("version"),
                        "status": "draft",
                        "created_at": datetime.now(),
                        "updated_at": datetime.now()
                    }
                    result = self.db.topic_contents.insert_one(content_doc)
                    created_content_id = str(result.inserted_id)
                except Exception as e:
                    logging.warning(f"create_template_instance_for_topic: no se pudo crear TopicContent vinculado: {e}")

            # Registrar evento de uso para estadísticas simples
            try:
                self.db.template_usage.insert_one({
                    "template_id": template_doc.get("_id"),
                    "instance_id": instance_obj._id,
                    "topic_id": ObjectId(topic_id),
                    "creator_id": creator_id,
                    "migration_source": migration_source,
                    "created_at": datetime.now()
                })
            except Exception:
                # no fatal
                pass

            response = {
                "success": True,
                "instance_id": str(instance_obj._id),
                "template_id": str(template_doc.get("_id")),
                "created_content_id": created_content_id
            }

            # Si auto_generate True, delegar a servicios de generación (no implementado aquí, sólo flag)
            if auto_generate:
                # Encolar tarea de generación o llamar a generator if exists (omitir implementación detallada aquí)
                try:
                    # registrar petición para procesar en background
                    self.db.template_generation_queue.insert_one({
                        "instance_id": instance_obj._id,
                        "requested_by": creator_id,
                        "status": "pending",
                        "created_at": datetime.now()
                    })
                except Exception:
                    pass

            return response

        except Exception as e:
            logging.error(f"Error in create_template_instance_for_topic: {e}")
            return {"success": False, "error": str(e)}

    # Métodos especializados para migración de contenidos legacy (games/simulations)
    def analyze_legacy_content_for_migration(self, topic_id: Optional[str] = None, module_id: Optional[str] = None, workspace_id: Optional[str] = None) -> Dict:
        """
        Analiza contenidos legacy (game, simulation) en el scope dado y determina templates compatibles.
        Retorna análisis por contenido con heurísticas de compatibilidad.
        """
        try:
            from .services import ContentService
            content_service = ContentService()
            # Reutilizar lógica existente si el ContentService la expone
            suggestions = content_service.get_legacy_content_migration_suggestions(topic_id=topic_id)
            deprecated_types = ContentTypes.get_deprecated_types()
            results = {
                "summary": suggestions,
                "analysis": []
            }

            # Buscar contenidos legacy concretos
            query = {"content_type": {"$in": deprecated_types}, "status": {"$ne": "deleted"}}
            if topic_id:
                query["topic_id"] = ObjectId(topic_id)
            if module_id:
                # intentar resolver topics en module - si falla, omitir
                try:
                    topics = list(self.db.topics.find({"module_id": module_id}, {"_id": 1}))
                    topic_ids = [t["_id"] for t in topics]
                    if topic_ids:
                        query["topic_id"] = {"$in": topic_ids}
                except Exception:
                    pass

            legacy_contents = list(self.db.topic_contents.find(query))
            for lc in legacy_contents:
                cid = lc.get("_id")
                methodologies = lc.get("learning_methodologies", []) or []
                interactive_keys = list(lc.get("interactive_data", {}).keys()) if isinstance(lc.get("interactive_data"), dict) else []
                complexity = len(interactive_keys)
                # candidate templates: buscar por subject_tags similares o capabilities.replaces_legacy
                candidate_query = {
                    "$or": [
                        {"capabilities.replaces_legacy": True},
                        {"migration_recommended": True},
                        {"subject_tags": {"$in": lc.get("subject_tags", []) or []}},
                        {"capabilities.compatible_methodologies": {"$in": methodologies}}
                    ]
                }
                candidates = list(self.templates_collection.find(candidate_query).limit(10))
                scored = []
                for c in candidates:
                    # heurística de puntuación: coincidencia en metodologías + flags + subject overlap
                    score = 0
                    caps = c.get("capabilities", {}) or {}
                    comp_meth = caps.get("compatible_methodologies", []) or []
                    # +2 por cada methodology match
                    for m in methodologies:
                        if m in comp_meth:
                            score += 2
                    # +3 si replaces_legacy
                    if caps.get("replaces_legacy"):
                        score += 3
                    # +1 por subject overlap
                    subj_overlap = len(set(c.get("subject_tags", []) or []).intersection(set(lc.get("subject_tags", []) or [])))
                    score += subj_overlap
                    # +1 if template explicitly recommended
                    if c.get("migration_recommended"):
                        score += 1
                    scored.append({
                        "template_id": str(c.get("_id")),
                        "name": c.get("name"),
                        "score": score,
                        "capabilities": caps
                    })
                # sort candidates by score desc
                scored.sort(key=lambda x: -x["score"])
                results["analysis"].append({
                    "content_id": str(cid),
                    "content_type": lc.get("content_type"),
                    "topic_id": str(lc.get("topic_id")) if lc.get("topic_id") else None,
                    "methodologies": methodologies,
                    "interactive_keys": interactive_keys,
                    "migration_complexity": complexity,
                    "recommended_templates": scored[:5]
                })

            return results
        except Exception as e:
            logging.error(f"Error in analyze_legacy_content_for_migration: {e}")
            return {"error": str(e)}

    def get_migration_recommendations(self, content_id: str) -> Dict:
        """
        Provee recomendaciones detalladas de templates para migrar un contenido legacy específico.
        """
        try:
            from .services import ContentService
            content_service = ContentService()
            content = content_service.get_content(content_id)
            if not content:
                return {"error": "Contenido no encontrado"}

            methodologies = content.get("learning_methodologies", []) or []
            subject_tags = content.get("subject_tags", []) or []
            interactive_keys = list(content.get("interactive_data", {}).keys()) if isinstance(content.get("interactive_data"), dict) else []

            # Buscar plantillas candidatas
            candidate_query = {
                "$or": [
                    {"capabilities.replaces_legacy": True},
                    {"migration_recommended": True},
                    {"subject_tags": {"$in": subject_tags}},
                    {"capabilities.compatible_methodologies": {"$in": methodologies}}
                ]
            }
            candidates = list(self.templates_collection.find(candidate_query))

            recommendations = []
            for c in candidates:
                caps = c.get("capabilities", {}) or {}
                comp_meth = caps.get("compatible_methodologies", []) or []
                score = 0
                for m in methodologies:
                    if m in comp_meth:
                        score += 3
                if caps.get("replaces_legacy"):
                    score += 4
                # subject overlap
                subj_overlap = len(set(subject_tags).intersection(set(c.get("subject_tags", []) or [])))
                score += subj_overlap
                # small boost for explicit migration_recommended
                if c.get("migration_recommended"):
                    score += 1

                recommendations.append({
                    "template_id": str(c.get("_id")),
                    "name": c.get("name"),
                    "description": c.get("description"),
                    "score": score,
                    "capabilities": caps
                })

            recommendations.sort(key=lambda x: -x["score"])
            return {
                "content_id": content_id,
                "recommendations": recommendations[:10],
                "methodologies": methodologies,
                "interactive_keys": interactive_keys
            }

        except Exception as e:
            logging.error(f"Error in get_migration_recommendations: {e}")
            return {"error": str(e)}

    def execute_content_migration(self, content_id: str, template_id: str, mark_legacy: bool = True, creator_id: Optional[str] = None, migration_notes: Optional[str] = None) -> Dict:
        """
        Ejecuta la migración automática de un contenido legacy (game/simulation) a una instancia de template.
        Realiza validaciones de compatibilidad y crea la instancia + nuevo TopicContent.
        """
        try:
            content_service = ContentService()
            content = content_service.get_content(content_id)
            if not content:
                return {"success": False, "error": "Contenido legacy no encontrado"}

            template = self.templates_collection.find_one({"_id": ObjectId(template_id)})
            if not template:
                return {"success": False, "error": "Template destino no encontrado"}

            # Calcular compatibilidad simple
            content_methods = content.get("learning_methodologies", []) or []
            template_methods = (template.get("capabilities", {}) or {}).get("compatible_methodologies", []) or []
            compatibility_score = 0
            for m in content_methods:
                if m in template_methods:
                    compatibility_score += 1

            # If template declares replaces_legacy, boost
            if (template.get("capabilities", {}) or {}).get("replaces_legacy"):
                compatibility_score += 2

            if compatibility_score <= 0:
                # Still allow if forced? For safety, require at least some match
                return {"success": False, "error": "Template no compatible (compatibility_score=0). Selecciona otra plantilla o revisa recomendaciones."}

            # Crear instancia usando TemplateInstanceService
            from .template_services import TemplateInstanceService as _TIS  # local import
            instance_service = _TIS()
            # Map props from legacy interactive_data or generation_prompt
            props = {}
            interactive_data = content.get("interactive_data") or {}
            if isinstance(interactive_data, dict):
                # Take keys that match template defaults if possible, otherwise pass full interactive_data under a single 'legacy_data' prop
                props.update(interactive_data)
            if content.get("generation_prompt"):
                props.setdefault("prompt", content.get("generation_prompt"))

            instance_payload = {
                "template_id": str(template.get("_id")),
                "topic_id": str(content.get("topic_id")),
                "creator_id": creator_id or str(content.get("creator_id", "")),
                "props": props,
                "assets": template.get("assets", []),
                "learning_mix": template.get("baseline_mix")
            }
            instance_obj = instance_service.create_instance(instance_payload)

            # Crear nuevo TopicContent que referencia la instancia
            new_content_doc = {
                "topic_id": content.get("topic_id"),
                "content": content.get("content", ""),
                "content_type": "interactive_exercise",  # represent migrated interactive as interactive_exercise
                "interactive_data": props,
                "learning_methodologies": content.get("learning_methodologies", []),
                "render_engine": "html_template",
                "instance_id": instance_obj._id,
                "template_id": template.get("_id"),
                "template_version": template.get("version"),
                "status": "draft",
                "created_at": datetime.now(),
                "updated_at": datetime.now(),
                "migration_meta": {
                    "source_content_id": ObjectId(content_id),
                    "compatibility_score": compatibility_score,
                    "migration_notes": migration_notes
                }
            }
            result = self.db.topic_contents.insert_one(new_content_doc)
            new_content_id = str(result.inserted_id)

            # Marcar legacy content como migrado si aplica
            if mark_legacy:
                try:
                    self.db.topic_contents.update_one(
                        {"_id": ObjectId(content_id)},
                        {"$set": {"status": "migrated", "migrated_at": datetime.now(), "migrated_to": ObjectId(new_content_id)}}
                    )
                except Exception as e:
                    logging.warning(f"execute_content_migration: no se pudo marcar legacy como migrado: {e}")

            # Registrar en log de migraciones
            try:
                self.db.template_migrations.insert_one({
                    "legacy_content_id": ObjectId(content_id),
                    "new_content_id": ObjectId(new_content_id),
                    "template_id": template.get("_id"),
                    "instance_id": instance_obj._id,
                    "compatibility_score": compatibility_score,
                    "executed_by": creator_id,
                    "created_at": datetime.now(),
                    "notes": migration_notes
                })
            except Exception:
                pass

            return {
                "success": True,
                "new_content_id": new_content_id,
                "instance_id": str(instance_obj._id),
                "compatibility_score": compatibility_score
            }

        except Exception as e:
            logging.error(f"Error in execute_content_migration: {e}")
            return {"success": False, "error": str(e)}

    def get_migration_status(self, workspace_id: Optional[str] = None) -> Dict:
        """
        Provee estadísticas generales de migración por workspace:
        - counts de legacy pendientes
        - templates más usados para migración
        - progreso general
        """
        try:
            deprecated_types = ContentTypes.get_deprecated_types()

            base_query = {"content_type": {"$in": deprecated_types}, "status": {"$ne": "deleted"}}
            if workspace_id:
                # intentamos filtrar por topics del workspace si existe campo workspace_id en topics
                try:
                    topics = list(self.db.topics.find({"workspace_id": workspace_id}, {"_id": 1}))
                    topic_ids = [t["_id"] for t in topics]
                    if topic_ids:
                        base_query["topic_id"] = {"$in": topic_ids}
                except Exception:
                    pass

            total_legacy = self.db.topic_contents.count_documents(base_query)
            migrated_query = dict(base_query)
            migrated_query["status"] = "migrated"
            migrated_count = self.db.topic_contents.count_documents(migrated_query)

            # Templates used for migration
            pipeline = [
                {"$match": {}},
                {"$group": {"_id": "$template_id", "count": {"$sum": 1}}},
                {"$sort": {"count": -1}},
                {"$limit": 10}
            ]
            top_templates_raw = list(self.db.template_migrations.aggregate(pipeline)) if "template_migrations" in self.db.list_collection_names() else []
            top_templates = []
            for t in top_templates_raw:
                try:
                    tid = t.get("_id")
                    tpl = self.templates_collection.find_one({"_id": tid})
                    top_templates.append({
                        "template_id": str(tid),
                        "name": tpl.get("name") if tpl else None,
                        "count": int(t.get("count", 0))
                    })
                except Exception:
                    continue

            progress_percent = round((migrated_count / total_legacy * 100), 2) if total_legacy > 0 else 0.0

            return {
                "workspace_id": workspace_id,
                "total_legacy_contents": int(total_legacy),
                "migrated_count": int(migrated_count),
                "progress_percent": progress_percent,
                "top_templates_used_for_migration": top_templates
            }
        except Exception as e:
            logging.error(f"Error in get_migration_status: {e}")
            return {"error": str(e)}
    def _object_id_or_str(self, value: Optional[Union[str, ObjectId]]) -> Optional[Union[str, ObjectId]]:
        """
        Convierte valores a ObjectId cuando es posible; devuelve strings limpios en caso contrario.
        """
        if value is None:
            return None
        if isinstance(value, ObjectId):
            return value
        try:
            return ObjectId(value)
        except Exception:
            return str(value)


class TemplateInstanceService:
    """
    Servicio para gestionar instancias de plantillas ligadas a temas.
    """
    
    def __init__(self):
        self.db = get_db()
        self.instances_collection: Collection = self.db.template_instances
        self.template_service = TemplateService()
        self.templates_collection = self.db.templates
        self.content_collection = self.db.topic_contents
        
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
                creator_id=instance_data.get("creator_id"),
                props=initial_props,
                assets=instance_data.get("assets", []),
                learning_mix=instance_data.get("learning_mix"),
                metadata=instance_data.get("metadata") if instance_data.get("metadata") is not None else instance_data.get("template_metadata")
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
            allowed_fields = ["props", "assets", "learning_mix", "status", "metadata"]
            
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
    
    def create_content_instance(self, template_id: str, parent_content_id: str, 
                               topic_id: str, creator_id: str, 
                               instance_props: Dict = None) -> Tuple[bool, str]:
        """
        Crea una instancia de plantilla vinculada a un contenido específico (diapositiva).
        
        Args:
            template_id: ID de la plantilla base
            parent_content_id: ID del contenido padre (diapositiva)
            topic_id: ID del tema
            creator_id: ID del creador
            instance_props: Propiedades específicas para la instancia
            
        Returns:
            Tuple[bool, str]: (éxito, mensaje/ID)
        """
        try:
            # Verificar que la plantilla existe
            template = self.templates_collection.find_one({"_id": ObjectId(template_id)})
            if not template:
                return False, "Plantilla no encontrada"
            
            # Verificar que el contenido padre existe
            parent_content = self.content_collection.find_one({"_id": ObjectId(parent_content_id)})
            if not parent_content:
                return False, "Contenido padre no encontrado"
            
            # Verificar que el contenido padre es del tipo correcto (slide)
            if parent_content.get("content_type") != "slide":
                return False, "El contenido padre debe ser de tipo 'slide'"
            
            # Extraer marcadores de la plantilla
            extractor = TemplateMarkupExtractor()
            markers = extractor.extract_markers(template.get("html_content", ""))
            
            # Crear instancia con propiedades por defecto
            default_props = markers.get("defaults", {})
            if instance_props:
                default_props.update(instance_props)
            
            # Crear nueva instancia vinculada al contenido
            instance = TemplateInstance(
                template_id=str(template["_id"]),
                topic_id=topic_id,
                creator_id=creator_id,
                template_version=template.get("version", "1.0.0"),
                parent_content_id=parent_content_id,
                props=default_props,
                assets={},
                learning_mix=template.get("learning_mix", {}),
                status="draft"
            )
            
            instance_dict = instance.to_dict()
            
            result = self.instances_collection.insert_one(instance_dict)
            return True, str(result.inserted_id)
            
        except Exception as e:
            logging.error(f"Error creating content instance: {str(e)}")
            return False, f"Error creando instancia: {str(e)}"
    
    def get_instances_by_content(self, parent_content_id: str) -> List[TemplateInstance]:
        """
        Obtiene todas las instancias de plantillas vinculadas a un contenido específico.
        
        Args:
            parent_content_id: ID del contenido padre
            
        Returns:
            Lista de instancias vinculadas al contenido
        """
        try:
            instances = list(self.instances_collection.find({
                "parent_content_id": ObjectId(parent_content_id)
            }).sort("created_at", -1))
            
            result = []
            for instance_data in instances:
                instance = TemplateInstance(
                    template_id=str(instance_data["template_id"]),
                    topic_id=str(instance_data["topic_id"]),
                    creator_id=str(instance_data["creator_id"]),
                    props=instance_data.get("props", {}),
                    assets=instance_data.get("assets", {}),
                    learning_mix=instance_data.get("learning_mix", {}),
                    status=instance_data.get("status", "draft"),
                    _id=instance_data["_id"],
                    created_at=instance_data.get("created_at"),
                    updated_at=instance_data.get("updated_at")
                )
                # Añadir parent_content_id si existe
                if "parent_content_id" in instance_data:
                    instance.parent_content_id = str(instance_data["parent_content_id"])
                
                result.append(instance)
            
            return result
            
        except Exception as e:
            logging.error(f"Error getting instances for content {parent_content_id}: {str(e)}")
            raise e
    
    def update_content_templates(self, parent_content_id: str, 
                                template_assignments: List[Dict]) -> Tuple[bool, str]:
        """
        Actualiza las plantillas asignadas a un contenido específico.
        
        Args:
            parent_content_id: ID del contenido padre
            template_assignments: Lista de asignaciones {template_id, props, status}
            
        Returns:
            Tuple[bool, str]: (éxito, mensaje)
        """
        try:
            # Obtener instancias existentes
            existing_instances = self.get_instances_by_content(parent_content_id)
            existing_template_ids = {inst.template_id for inst in existing_instances}
            
            # Procesar nuevas asignaciones
            new_template_ids = set()
            for assignment in template_assignments:
                template_id = assignment.get("template_id")
                if not template_id:
                    continue
                    
                new_template_ids.add(template_id)
                
                # Si la instancia ya existe, actualizarla
                existing_instance = next(
                    (inst for inst in existing_instances if inst.template_id == template_id), 
                    None
                )
                
                if existing_instance:
                    # Actualizar instancia existente
                    update_data = {
                        "props": assignment.get("props", existing_instance.props),
                        "status": assignment.get("status", existing_instance.status)
                    }
                    self.update_instance(str(existing_instance._id), update_data)
                else:
                    # Crear nueva instancia
                    parent_content = self.content_collection.find_one({"_id": ObjectId(parent_content_id)})
                    if parent_content:
                        self.create_content_instance(
                            template_id=template_id,
                            parent_content_id=parent_content_id,
                            topic_id=str(parent_content["topic_id"]),
                            creator_id=str(parent_content.get("creator_id", "")),
                            instance_props=assignment.get("props", {})
                        )
            
            # Eliminar instancias que ya no están asignadas
            templates_to_remove = existing_template_ids - new_template_ids
            for instance in existing_instances:
                if instance.template_id in templates_to_remove:
                    self.delete_instance(str(instance._id))
            
            return True, "Plantillas actualizadas correctamente"
            
        except Exception as e:
            logging.error(f"Error updating content templates: {str(e)}")
            return False, f"Error actualizando plantillas: {str(e)}"

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
