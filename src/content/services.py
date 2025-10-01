from typing import Tuple, List, Dict, Optional, Any
from bson import ObjectId
from datetime import datetime, timedelta
import json
import logging
import threading

from src.shared.database import get_db
from src.shared.constants import STATUS
from src.shared.standardization import VerificationBaseService, ErrorCodes
from src.shared.exceptions import AppException
from .models import ContentType, TopicContent, VirtualTopicContent, ContentResult, ContentTypes, DeprecatedContentTypes, LearningMethodologyTypes
from .slide_style_service import SlideStyleService
import re
from src.ai_monitoring.services import AIMonitoringService
from .structured_sequence_service import StructuredSequenceService
from .template_recommendation_service import TemplateRecommendationService
from .embedded_content_service import EmbeddedContentService
from .content_personalization_service import ContentPersonalizationService
import bleach

class ContentTypeService(VerificationBaseService):
    """
    Servicio para gestionar tipos de contenido unificados.
    Reemplaza servicios separados de game types, simulation types, etc.
    """
    def __init__(self):
        super().__init__(collection_name="content_types")

    def create_content_type(self, content_type_data: Dict) -> Tuple[bool, str]:
        """
        Crea un nuevo tipo de contenido.
        
        Args:
            content_type_data: Datos del tipo de contenido
            
        Returns:
            Tuple[bool, str]: (éxito, mensaje/ID)
        """
        try:
            # Verificar que no exista el código
            existing = self.collection.find_one({"code": content_type_data.get("code")})
            if existing:
                return False, "Ya existe un tipo de contenido con ese código"

            content_type = ContentType(**content_type_data)
            result = self.collection.insert_one(content_type.to_dict())
            
            return True, str(result.inserted_id)
        except Exception as e:
            logging.error(f"Error creando tipo de contenido: {str(e)}")
            return False, f"Error interno: {str(e)}"

    def get_content_types(self, subcategory: str = None) -> List[Dict]:
        """
        Obtiene tipos de contenido filtrados.
        
        Args:
            subcategory: Subcategoría a filtrar ("game", "simulation", "quiz", etc.)
            
        Returns:
            Lista de tipos de contenido
        """
        query = {"status": "active"}
        if subcategory:
            query["subcategory"] = subcategory
            
        content_types = list(self.collection.find(query))
        for ct in content_types:
            ct["_id"] = str(ct["_id"])
        return content_types

    def get_content_type(self, code: str) -> Optional[Dict]:
        """
        Obtiene un tipo de contenido específico por código.
        """
        content_type = self.collection.find_one({"code": code, "status": "active"})
        if content_type:
            content_type["_id"] = str(content_type["_id"])
        return content_type

# Default status mapping by content type
DEFAULT_STATUS_BY_TYPE = {
    "slide": ["draft", "active", "published", "skeleton", "html_ready", "narrative_ready"],
    "default": ["draft", "active", "published"]
}


class ContentService(VerificationBaseService):
    """
    Servicio unificado para gestionar TODO tipo de contenido.
    Reemplaza GameService, SimulationService, QuizService, etc.
    """
    def __init__(self):
        super().__init__(collection_name="topic_contents")
        self.content_type_service = ContentTypeService()
        self.slide_style_service = SlideStyleService()
        self.structured_sequence_service = StructuredSequenceService(get_db())
        self.template_recommendation_service = TemplateRecommendationService()
        self.embedded_content_service = EmbeddedContentService(self.db)

        # Simple in-memory caches for expensive aggregated stats
        # Structure: { cache_key: { "ts": datetime, "value": ... } }
        self._stats_cache: Dict[str, Dict[str, Any]] = {}
        self._cache_lock = threading.Lock()
        # Default TTL (seconds) for stats cache
        self._stats_cache_ttl = 10

    def check_topic_exists(self, topic_id: str) -> bool:
        """Verifica si un tema existe."""
        try:
            topic = self.db.topics.find_one({"_id": ObjectId(topic_id)})
            return topic is not None
        except Exception:
            return False

    def validate_slide_html_content(self, html_content: str) -> Tuple[bool, str]:
        """
        Valida que el HTML de una diapositiva sea seguro y tenga estructura básica.
        Reglas:
            - Debe ser str no vacío
            - Tamaño máximo razonable (p.ej. 15000 caracteres para slides)
            - No debe contener etiquetas peligrosas (<script>, <iframe>, <object>, <embed>, <link>, <meta>, <base>)
            - No debe contener atributos de evento inline (onerror=, onclick=, etc.)
            - No debe usar esquemas 'javascript:' en href/src ni data: que pueda incrustar HTML/scripts
            - No debe contener expresiones CSS peligrosas (expression(), url(javascript:...))
            - Comprobación básica de equilibrio de '<' y '>' para detectar fragmentos rotos
        Retorna (True, "") si es válido, o (False, "mensaje de error") si no.
        """
        try:
            if not isinstance(html_content, str):
                logging.debug("validate_slide_html_content: contenido no es str")
                return False, "HTML debe ser una cadena de texto"
            raw = html_content
            if not raw.strip():
                logging.debug("validate_slide_html_content: contenido vacío o solo espacios")
                return False, "HTML no debe estar vacío"

            # Tamaño razonable para una slide individual
            max_len = 15000
            if len(raw) > max_len:
                logging.warning(f"validate_slide_html_content: HTML demasiado largo ({len(raw)} > {max_len})")
                return False, f"HTML excede el tamaño máximo permitido de {max_len} caracteres"

            low = raw.lower()

            # Prohibir tags peligrosos explícitos
            dangerous_tags = ["script", "iframe", "object", "embed", "link", "meta", "base"]
            for tag in dangerous_tags:
                if f"<{tag}" in low or f"</{tag}" in low:
                    logging.warning(f"validate_slide_html_content: encontrado tag prohibido <{tag}>")
                    return False, f"HTML contiene etiqueta <{tag}> prohibida"

            # Prohibir eventos inline (on*)
            if re.search(r'on[a-z]+\s*=', low):
                logging.warning("validate_slide_html_content: encontrado atributo de evento inline (on*)")
                return False, "HTML contiene atributos de evento inline (on*) que están prohibidos"

            # Prohibir javascript: URIs
            if "javascript:" in low:
                logging.warning("validate_slide_html_content: encontrado javascript: URI")
                return False, "HTML contiene URIs javascript: que están prohibidas"

            # Prohibir data: URIs that could embed scripts or HTML (basic)
            if re.search(r'data:\s*text\/html', low) or re.search(r'data:\s*text\/javascript', low):
                logging.warning("validate_slide_html_content: encontrado data:text/html o data:text/javascript")
                return False, "HTML contiene data: URIs potencialmente peligrosas"

            # CSS expression() and javascript in url()
            if "expression(" in low or re.search(r'url\(\s*javascript:', low):
                logging.warning("validate_slide_html_content: encontrado expression() o url(javascript:...) en CSS")
                return False, "HTML contiene expresiones CSS potencialmente peligrosas"

            # Comprobar equilibrio básico de <> para detectar HTML truncado
            lt_count = raw.count("<")
            gt_count = raw.count(">")
            if abs(lt_count - gt_count) > 5:  # allow small imbalance for fragments, but not large mismatches
                logging.debug(f"validate_slide_html_content: desequilibrio en etiquetas (<: {lt_count}, >: {gt_count})")
                return False, "HTML parece estar mal formado (desequilibrio de etiquetas)"

            # Comprobar número de etiquetas para evitar payloads excesivos
            tag_count = len(re.findall(r"<[a-zA-Z]+[^\>]*>", raw))
            if tag_count > 500:
                logging.warning(f"validate_slide_html_content: demasiadas etiquetas HTML ({tag_count})")
                return False, "HTML contiene demasiadas etiquetas; posiblemente intento de abuso"

            # Comprobar existencia de contenido significativo (texto o tags comunes)
            if not re.search(r"[A-Za-z0-9]", raw) and tag_count == 0:
                logging.debug("validate_slide_html_content: sin texto alfanumérico ni etiquetas detectadas")
                return False, "HTML no contiene contenido válido"

            # Es aceptable si el HTML es un fragmento ligero; registrar advertencias cuando aplica
            if tag_count == 0:
                logging.debug("validate_slide_html_content: HTML parece ser texto plano o fragmento sin etiquetas")

            logging.debug("validate_slide_html_content: HTML validado correctamente")
            return True, ""
        except Exception as e:
            logging.error(f"Error validando HTML de slide: {str(e)}")
            return False, f"Error validando HTML: {str(e)}"

    def sanitize_slide_html_content(self, html: str) -> str:
        """
        Sanitiza el HTML de una diapositiva removiendo tags y atributos peligrosos.
        Usa bleach con una allowlist para limpiar el contenido.
        """
        try:
            if not html or not isinstance(html, str):
                return ""

            allowed_tags = [
                'div', 'p', 'span', 'h1', 'h2', 'h3', 'h4', 'h5', 'h6',
                'ul', 'ol', 'li', 'a', 'img', 'strong', 'em', 'i', 'b',
                'br', 'hr', 'blockquote', 'code', 'pre', 'table', 'tr', 'td',
                'th', 'thead', 'tbody', 'caption'
            ]
            allowed_attrs = {
                '*': ['class', 'style'],
                'a': ['href', 'title'],
                'img': ['src', 'alt', 'title'],
                'table': ['border', 'cellpadding', 'cellspacing'],
            }
            allowed_protocols = ['http', 'https', 'mailto']

            cleaned = bleach.clean(
                html,
                tags=allowed_tags,
                attributes=allowed_attrs,
                protocols=allowed_protocols,
                strip=True  # Remover tags no permitidos en lugar de escapar
            )
            return cleaned
        except Exception as e:
            logging.error(f"Error sanitizando HTML: {str(e)}")
            return ""  # Retornar vacío en caso de error para evitar inyección

    def create_content(self, content_data: Dict, allow_deprecated: bool = False, creator_roles: Optional[List[str]] = None) -> Tuple[bool, str]:
        """
        Crea contenido de cualquier tipo (estático o interactivo).
        
        Args:
            content_data: Datos del contenido a crear
            allow_deprecated: Si True permite crear tipos deprecated (solo para administradores en casos excepcionales)
            
        Returns:
            Tuple[bool, str]: (éxito, mensaje/ID)
        """
        try:
            # Validaciones básicas
            topic_id = content_data.get("topic_id")
            content_type = content_data.get("content_type")
            
            # TEMPORAL: Comentar validación de topic_id para pruebas
            # if not topic_id or not self.check_topic_exists(topic_id):
            #     return False, "El tema especificado no existe"
                
            # Verificar que el tipo de contenido existe
            content_type_def = self.content_type_service.get_content_type(content_type)
            if not content_type_def:
                return False, f"Tipo de contenido '{content_type}' no válido"

            # Validate deprecation of content type
            allowed, info = self.validate_content_type_deprecation(content_type, allow_deprecated=allow_deprecated, creator_roles=creator_roles)
            if not allowed:
                # info may contain suggestion metadata or message
                message = info.get("message") if isinstance(info, dict) and info.get("message") else f"El tipo de contenido '{content_type}' está en desuso y no puede crearse. Considere migrar a plantillas interactivas."
                # attach replacement suggestion if available
                if isinstance(info, dict) and info.get("replacement"):
                    message = f"{message} Reemplazo recomendado: {info.get('replacement')}"
                logging.warning(f"create_content: intento de crear contenido deprecated type='{content_type}' topic='{topic_id}' allowed={allow_deprecated}")
                return False, message

            # Validaciones específicas para diapositivas
            if content_type == "slide":
                slide_template = content_data.get("slide_template", "")
                if not slide_template:
                    return False, f"El contenido de tipo '{content_type}' requiere un campo 'slide_template' con el prompt para la plantilla"
                
                # Validar estructura del slide_template usando el servicio
                if not self.slide_style_service.validate_slide_template(slide_template):
                    return False, "El slide_template no es un prompt válido"

                # If client provided template_snapshot (new field), validate it too
                template_snapshot = content_data.get("template_snapshot")
                if template_snapshot is not None:
                    valid_ts, ts_msg = self.validate_template_snapshot(template_snapshot)
                    if not valid_ts:
                        return False, f"template_snapshot inválido: {ts_msg}"

                # Validar nuevos campos de diapositiva si se proporcionan
                content_html = content_data.get("content_html")
                narrative_text = content_data.get("narrative_text")
                full_text = content_data.get("full_text")

                if content_html is not None:
                    valid, msg = self.validate_slide_html_content(content_html)
                    if not valid:
                        return False, f"content_html inválido: {msg}"

                if narrative_text is not None and not isinstance(narrative_text, str):
                    return False, "narrative_text debe ser una cadena de texto si se proporciona"

                if full_text is not None and not isinstance(full_text, str):
                    return False, "full_text debe ser una cadena de texto si se proporciona"

            # Crear contenido explícitamente para mapear campos
            # Convertir content a string si es dict para el extractor de marcadores
            content_for_markers = content_data.get("content", "")
            if isinstance(content_for_markers, dict):
                content_for_markers = json.dumps(content_for_markers, ensure_ascii=False)
            markers = ContentPersonalizationService.extract_markers(
                content_for_markers or json.dumps(content_data.get("interactive_data", {}))
            )

            # Determinar estado inicial para diapositivas en función de los campos provistos
            # SOLO si el cliente no proporcionó un status explícito, salvo que el caso sea skeleton
            initial_status = content_data.get("status", "draft")
            if content_type == "slide":
                # Derivar status automáticamente
                ch = content_data.get("content_html")
                nt = content_data.get("narrative_text")
                ft = content_data.get("full_text")

                # If it's clearly a skeleton (only full_text present and no html/narrative),
                # force status to 'skeleton' regardless of client-provided status.
                if ft and not ch and not nt:
                    initial_status = "skeleton"
                else:
                    # Preserve explicit status if provided; otherwise derive
                    if "status" in content_data:
                        initial_status = content_data["status"]
                    else:
                        if ch and nt:
                            initial_status = "narrative_ready"
                        elif ch:
                            initial_status = "html_ready"
                        elif ft:
                            initial_status = "skeleton"
                        else:
                            initial_status = "draft"

            content = TopicContent(
                topic_id=topic_id,
                content_type=content_type,
                content=content_data.get("content", ""),
                interactive_data=content_data.get("interactive_data"),
                learning_methodologies=content_data.get("learning_methodologies"),
                adaptation_options=content_data.get("metadata"), # Mapeo clave
                resources=content_data.get("resources"),
                web_resources=content_data.get("web_resources"),
                generation_prompt=content_data.get("generation_prompt"),
                ai_credits=content_data.get("ai_credits", True),
                personalization_markers=markers,
                slide_template=content_data.get("slide_template", ""),  # Incluir slide_template
                status=initial_status,
                content_html=content_data.get("content_html"),
                narrative_text=content_data.get("narrative_text"),
                full_text=content_data.get("full_text"),
                template_snapshot=content_data.get("template_snapshot"),  # Incluir template_snapshot
                order=content_data.get("order"),
                parent_content_id=content_data.get("parent_content_id")
            )
            result = self.collection.insert_one(content.to_dict())
            
            # Logging específico para creación de diapositivas con nuevos campos
            if content_type == "slide":
                logging.info(f"Slide creado para topic {topic_id} con id {result.inserted_id}. status={initial_status}, has_html={'content_html' in content_data}, has_narrative={'narrative_text' in content_data}")

            # Actualizar métricas del tipo de contenido
            self.content_type_service.collection.update_one(
                {"code": content_type},
                {"$inc": {"usage_count": 1}}
            )
            
            return True, str(result.inserted_id)
            
        except Exception as e:
            logging.error(f"Error creando contenido: {str(e)}")
            return False, f"Error interno: {str(e)}"

    def validate_content_type_deprecation(self, content_type: str, allow_deprecated: bool = False, creator_roles: Optional[List[str]] = None) -> Tuple[bool, Optional[Dict]]:
        """
        Valida si un tipo de contenido está marcado como deprecated y si se permite su creación.
        Args:
            content_type: Código del tipo de contenido a validar
            allow_deprecated: Flag explícito para permitir creación de tipos deprecated (solo administradores)
            creator_roles: Lista de roles del creador (p.ej. ['ADMIN']). Si incluye 'ADMIN' se permite crear cuando allow_deprecated=True
        Returns:
            (True, info_dict) si está permitido (info_dict puede tener metadata sobre reemplazo)
            (False, info_dict_or_message) si no está permitido; info_dict puede contener metadata de DeprecatedContentTypes.info_for
        """
        try:
            if not content_type:
                return True, None
            # Chequear si está en la lista de deprecated definida en modelos
            if DeprecatedContentTypes.is_deprecated(content_type):
                info = DeprecatedContentTypes.info_for(content_type) or {}
                # Si allow_deprecated explícito y rol admin en creator_roles -> permitir, pero registrar
                is_admin = False
                try:
                    if creator_roles and isinstance(creator_roles, list):
                        is_admin = any(r.upper() == "ADMIN" for r in creator_roles)
                except Exception:
                    is_admin = False

                if allow_deprecated and is_admin:
                    logging.warning(f"validate_content_type_deprecation: creación permitida de tipo deprecated '{content_type}' por ADMIN (allow_deprecated=True)")
                    return True, info
                # If allow_deprecated True but no admin role, still disallow and log
                if allow_deprecated and not is_admin:
                    logging.warning(f"validate_content_type_deprecation: intento de allow_deprecated sin rol ADMIN para tipo '{content_type}'")
                    return False, {"message": "Permiso insuficiente para crear contenido deprecated. Se requiere rol ADMIN para usar allow_deprecated."}

                # Default: disallow creation
                logging.info(f"validate_content_type_deprecation: intento de creación bloqueado para tipo deprecated '{content_type}'")
                return False, info or {"message": f"El tipo '{content_type}' está en desuso y no puede crearse. Use plantillas interactivas en su lugar."}
            # Not deprecated
            return True, None
        except Exception as e:
            logging.error(f"Error validando deprecación de tipo de contenido '{content_type}': {e}", exc_info=True)
            # En caso de error, probar si el tipo está deprecated
            try:
                is_deprecated = DeprecatedContentTypes.is_deprecated(content_type)
                if is_deprecated:
                    logging.warning(f"validate_content_type_deprecation: error de validación para tipo deprecated '{content_type}', bloqueando creación por seguridad")
                    return False, {'message': 'Tipo en desuso; no se permite creación por error de validación'}
                else:
                    logging.warning(f"validate_content_type_deprecation: error de validación para tipo no deprecated '{content_type}', permitiendo creación por seguridad")
                    return True, None
            except Exception as inner_e:
                logging.error(f"validate_content_type_deprecation: error secundario al verificar deprecación durante manejo de error para '{content_type}': {inner_e}", exc_info=True)
                # Si no podemos determinar el estado de deprecación, permitir creación para no bloquear el flujo
                return True, None

    def get_legacy_content_migration_suggestions(self, topic_id: Optional[str] = None, content_type: Optional[str] = None) -> Dict:
        """
        Analiza contenidos legacy (game, simulation) en el tema y propone sugerencias de migración a plantillas.
        Retorna un dict con:
            - topic_id (si se proporciona)
            - totals: {type: count}
            - last_created_at per type
            - sample_contents: list of sample content metadata (id, title, learning_methodologies)
            - suggested_templates: recomendaciones por tipo/metodología

        Args:
            topic_id: ID del tema a analizar (opcional). Si es None, se agregan datos globales.
            content_type: Tipo de contenido específico a filtrar (opcional). Si se proporciona,
                         solo se analizan contenidos de ese tipo.
        """
        try:
            deprecated_types = ContentTypes.get_deprecated_types()

            # Build query based on parameters
            query = {
                "content_type": {"$in": deprecated_types},
                "status": {"$ne": "deleted"}
            }

            # If content_type is provided, filter only that type
            if content_type:
                if content_type not in deprecated_types:
                    return {"error": f"content_type '{content_type}' no es un tipo deprecated válido"}
                query["content_type"] = content_type

            # If topic_id is provided, filter by topic
            if topic_id:
                query["topic_id"] = ObjectId(topic_id)

            cursor = self.collection.find(query, {
                "_id": 1,
                "content_type": 1,
                "learning_methodologies": 1,
                "interactive_data": 1,
                "created_at": 1,
                "updated_at": 1,
                "content": 1,
                "topic_id": 1
            }).sort([("created_at", -1)])

            contents = list(cursor)
            totals: Dict[str, int] = {}
            last_created: Dict[str, Optional[datetime]] = {}
            samples: Dict[str, List[Dict]] = {}
            methodology_counter: Dict[str, Dict[str, int]] = {}

            for c in contents:
                ctype = c.get("content_type")
                totals[ctype] = totals.get(ctype, 0) + 1
                created = c.get("created_at")
                if created:
                    prev = last_created.get(ctype)
                    if not prev or (isinstance(created, datetime) and created > prev):
                        last_created[ctype] = created

                # gather sample up to 5 per type
                samples.setdefault(ctype, [])
                if len(samples[ctype]) < 5:
                    samples[ctype].append({
                        "content_id": str(c.get("_id")),
                        "topic_id": str(c.get("topic_id")),
                        "learning_methodologies": c.get("learning_methodologies", []),
                        "interactive_data_keys": list(c.get("interactive_data", {}).keys()) if isinstance(c.get("interactive_data"), dict) else [],
                        "content_preview": (c.get("content")[:250] if isinstance(c.get("content"), str) else None)
                    })

                # count methodologies
                for m in (c.get("learning_methodologies") or []):
                    methodology_counter.setdefault(ctype, {})
                    methodology_counter[ctype][m] = methodology_counter[ctype].get(m, 0) + 1

            # Build suggested templates using metadata and LearningMethodologyTypes mapping
            suggested_templates: Dict[str, List[str]] = {}
            for ctype in (deprecated_types if not content_type else [content_type]):
                # base replacement from DeprecatedContentTypes
                meta = DeprecatedContentTypes.info_for(ctype) or {}
                base_replacement = meta.get("replacement")
                suggestions = []
                if base_replacement:
                    suggestions.append(base_replacement)
                # if kinesthetic/gamification methodologies are common, include kinesthetic template mappings
                meth_counts = methodology_counter.get(ctype, {})
                # pick top methodologies
                top_methods = sorted(meth_counts.items(), key=lambda x: x[1], reverse=True)[:3]
                for m, _ in top_methods:
                    # if methodology is kinesthetic or gamification, add mapped templates
                    if m in (LearningMethodologyTypes.KINESTHETIC, LearningMethodologyTypes.GAMIFICATION):
                        mapped = LearningMethodologyTypes.map_kinesthetic_to_templates().get(m, [])
                        for t in mapped:
                            if t not in suggestions:
                                suggestions.append(t)
                    else:
                        # also include collaborative/project_based suggestions
                        mapped = LearningMethodologyTypes.map_kinesthetic_to_templates().get(m, [])
                        if mapped:
                            for t in mapped:
                                if t not in suggestions:
                                    suggestions.append(t)
                suggested_templates[ctype] = suggestions

            result = {
                "totals": totals,
                "last_created_at": {k: (v.isoformat() if isinstance(v, datetime) else None) for k, v in last_created.items()},
                "sample_contents": samples,
                "methodology_distribution": methodology_counter,
                "suggested_templates": suggested_templates
            }

            # Only include topic_id if it was provided
            if topic_id:
                result["topic_id"] = topic_id

            return result
        except Exception as e:
            logging.error(f"Error generando sugerencias de migración para topic {topic_id}: {e}")
            return {"error": str(e)}

    def check_deprecated_content_usage(self, topic_id: Optional[str] = None, module_id: Optional[str] = None) -> Dict:
        """
        Consulta estadísticas de uso de contenidos deprecated por topic o por módulo.
        Retorna:
            - scope (topic/module/all)
            - totals_by_type
            - last_created_by_type
            - sample_ids_by_type
            - recommended_actions (human readable)
        Nota: module_id handling intenta resolver topics pertenecientes al módulo si existe la colección topics
        """
        try:
            deprecated_types = ContentTypes.get_deprecated_types()
            query = {"content_type": {"$in": deprecated_types}, "status": {"$ne": "deleted"}}

            scope = "all"
            if topic_id:
                try:
                    query["topic_id"] = ObjectId(topic_id)
                    scope = f"topic:{topic_id}"
                except Exception:
                    return {"error": "topic_id inválido"}
            elif module_id:
                # intentar obtener topics pertenecientes al módulo (campo module_id en topics)
                try:
                    topics = list(self.db.topics.find({"module_id": module_id}, {"_id": 1}))
                    topic_ids = [t["_id"] for t in topics]
                    if topic_ids:
                        query["topic_id"] = {"$in": topic_ids}
                        scope = f"module:{module_id}"
                    else:
                        # if no topics found, return empty stats
                        return {
                            "scope": f"module:{module_id}",
                            "totals_by_type": {},
                            "last_created_by_type": {},
                            "sample_ids_by_type": {},
                            "recommended_actions": ["No se encontraron topics en el módulo especificado."]
                        }
                except Exception as e:
                    logging.warning(f"check_deprecated_content_usage: no se pudo resolver module_id -> topics: {e}")
                    return {"error": "module_id procesado incorrectamente"}

            cursor = self.collection.find(query, {
                "_id": 1,
                "content_type": 1,
                "created_at": 1,
                "learning_methodologies": 1
            }).sort([("created_at", -1)])
            items = list(cursor)

            totals_by_type: Dict[str, int] = {}
            last_created_by_type: Dict[str, Optional[datetime]] = {}
            sample_ids_by_type: Dict[str, List[str]] = {}
            methodology_summary: Dict[str, Dict[str, int]] = {}

            for it in items:
                ctype = it.get("content_type")
                totals_by_type[ctype] = totals_by_type.get(ctype, 0) + 1
                created = it.get("created_at")
                if created:
                    prev = last_created_by_type.get(ctype)
                    if not prev or (isinstance(created, datetime) and created > prev):
                        last_created_by_type[ctype] = created
                sample_ids_by_type.setdefault(ctype, [])
                if len(sample_ids_by_type[ctype]) < 10:
                    sample_ids_by_type[ctype].append(str(it.get("_id")))

                for m in (it.get("learning_methodologies") or []):
                    methodology_summary.setdefault(ctype, {})
                    methodology_summary[ctype][m] = methodology_summary[ctype].get(m, 0) + 1

            # Build recommended actions
            recommended_actions = []
            for ctype in deprecated_types:
                count = totals_by_type.get(ctype, 0)
                if count == 0:
                    recommended_actions.append(f"No hay contenidos '{ctype}' en el scope {scope}.")
                    continue
                meta = DeprecatedContentTypes.info_for(ctype) or {}
                replacement = meta.get("replacement", "interactive_template")
                sunset = meta.get("sunset_date")
                sunset_str = sunset.isoformat() if isinstance(sunset, datetime) else str(sunset) if sunset else "N/A"
                recommended_actions.append(
                    f"Tipo '{ctype}': {count} elementos. Última creación: {last_created_by_type.get(ctype).isoformat() if isinstance(last_created_by_type.get(ctype), datetime) else 'desconocida'}. "
                    f"Recomendación: migrar a '{replacement}'. Fecha de sunset: {sunset_str}."
                )

            result = {
                "scope": scope,
                "totals_by_type": totals_by_type,
                "last_created_by_type": {k: (v.isoformat() if isinstance(v, datetime) else None) for k, v in last_created_by_type.items()},
                "sample_ids_by_type": sample_ids_by_type,
                "methodology_summary": methodology_summary,
                "recommended_actions": recommended_actions
            }
            return result
        except Exception as e:
            logging.error(f"Error en check_deprecated_content_usage: {e}")
            return {"error": str(e)}

    def create_bulk_content(self, contents_data: List[Dict]) -> Tuple[bool, List[str]]:
        """
        Crea múltiples contenidos en una sola transacción.
        
        Args:
            contents_data: Lista de datos de contenidos a crear
            
        Returns:
            Tuple[bool, List[str]]: (éxito, lista_de_IDs_creados_o_mensaje_error)
        """
        if not contents_data:
            return False, "No se proporcionaron contenidos para crear"
        
        # Iniciar sesión de transacción
        session = self.db.client.start_session()
        transaction_active = False
        
        try:
            session.start_transaction()
            transaction_active = True
            
            created_ids = []
            content_types_usage = {}
            
            # Validaciones previas
            for i, content_data in enumerate(contents_data):
                topic_id = content_data.get("topic_id")
                content_type = content_data.get("content_type")
                
                # Validar campos requeridos
                if not topic_id:
                    raise ValueError(f"Contenido {i+1}: topic_id es requerido")
                if not content_type:
                    raise ValueError(f"Contenido {i+1}: content_type es requerido")
                
                # Verificar que el tipo de contenido existe
                content_type_def = self.content_type_service.get_content_type(content_type)
                if not content_type_def:
                    raise ValueError(f"Contenido {i+1}: Tipo de contenido '{content_type}' no válido")
                
                # Validaciones específicas para diapositivas
                if content_type == "slide":
                    slide_template = content_data.get("slide_template", "")
                    
                    # Log the received data for debugging
                    logging.info(f"Contenido {i+1}: Procesando slide con slide_template='{slide_template[:100] if slide_template else 'EMPTY'}...'")
                    
                    # Auto-generate slide_template if not provided or invalid
                    if not slide_template or not self.slide_style_service.validate_slide_template(slide_template):
                        if not slide_template:
                            logging.info(f"Contenido {i+1}: slide_template no proporcionado, generando automáticamente")
                        else:
                            logging.warning(f"Contenido {i+1}: slide_template inválido, regenerando automáticamente")
                        
                        # Generate a default slide template
                        slide_template = self.slide_style_service.generate_slide_template()
                        content_data["slide_template"] = slide_template
                        logging.info(f"Contenido {i+1}: slide_template generado automáticamente")

                    # Detectar caso skeleton: full_text presente sin content_html ni narrative_text
                    ft = content_data.get("full_text")
                    ch = content_data.get("content_html")
                    nt = content_data.get("narrative_text")

                    is_skeleton = ft and not ch and not nt

                    # Validar template_snapshot según el tipo de slide
                    template_snapshot = content_data.get("template_snapshot")
                    if is_skeleton:
                        # Para skeleton slides, template_snapshot es obligatorio
                        if template_snapshot is None:
                            raise ValueError(f"Contenido {i+1}: Las diapositivas skeleton requieren 'template_snapshot'. Use /api/content/bulk/slides para creación optimizada de skeleton slides.")

                        valid_ts, ts_msg = self.validate_template_snapshot(template_snapshot)
                        if not valid_ts:
                            raise ValueError(f"Contenido {i+1}: template_snapshot inválido: {ts_msg}")
                    else:
                        # Para non-skeleton slides, template_snapshot es opcional pero se valida si se proporciona
                        if template_snapshot is not None:
                            valid_ts, ts_msg = self.validate_template_snapshot(template_snapshot)
                            if not valid_ts:
                                raise ValueError(f"Contenido {i+1}: template_snapshot inválido: {ts_msg}")

                    # Validar estructura de slides en content_data
                    slides = content_data.get("content_data", {}).get("slides", [])
                    if slides:
                        for j, slide in enumerate(slides):
                            if "order" not in slide:
                                raise ValueError(f"Contenido {i+1}, slide {j+1}: El campo 'order' es requerido en cada slide")
                            if not isinstance(slide.get("order"), int) or slide.get("order") < 1:
                                raise ValueError(f"Contenido {i+1}, slide {j+1}: El campo 'order' debe ser un entero positivo")
                            # Validar campos de cada slide si están presentes
                            if "content_html" in slide and slide.get("content_html") is not None:
                                valid, msg = self.validate_slide_html_content(slide.get("content_html"))
                                if not valid:
                                    raise ValueError(f"Contenido {i+1}, slide {j+1}: content_html inválido: {msg}")
                            if "narrative_text" in slide and slide.get("narrative_text") is not None and not isinstance(slide.get("narrative_text"), str):
                                raise ValueError(f"Contenido {i+1}, slide {j+1}: narrative_text debe ser una cadena de texto")
                            if "full_text" in slide and slide.get("full_text") is not None and not isinstance(slide.get("full_text"), str):
                                raise ValueError(f"Contenido {i+1}, slide {j+1}: full_text debe ser una cadena de texto")

                    # Validar campos a nivel de contenido (cuando se usan como single slide entries)
                    if "content_html" in content_data and content_data.get("content_html") is not None:
                        valid, msg = self.validate_slide_html_content(content_data.get("content_html"))
                        if not valid:
                            raise ValueError(f"Contenido {i+1}: content_html inválido: {msg}")
                    if "narrative_text" in content_data and content_data.get("narrative_text") is not None and not isinstance(content_data.get("narrative_text"), str):
                        raise ValueError(f"Contenido {i+1}: narrative_text debe ser una cadena de texto")
                    if "full_text" in content_data and content_data.get("full_text") is not None and not isinstance(content_data.get("full_text"), str):
                        raise ValueError(f"Contenido {i+1}: full_text debe ser una cadena de texto")
                
                # Contar uso de tipos de contenido
                content_types_usage[content_type] = content_types_usage.get(content_type, 0) + 1
            
            # Validar orden secuencial si se proporciona
            self._validate_sequential_order(contents_data)
            
            # Crear contenidos uno por uno dentro de la transacción
            for i, content_data in enumerate(contents_data):
                # Extraer marcadores de personalización
                content_for_markers = content_data.get("content", "")
                if isinstance(content_for_markers, dict):
                    content_for_markers = json.dumps(content_for_markers, ensure_ascii=False)
                markers = ContentPersonalizationService.extract_markers(
                    content_for_markers or json.dumps(content_data.get("interactive_data", {}))
                )

                # Determinar estado inicial para diapositivas en función de los campos provistos
                # SOLO si el cliente no proporcionó un status explícito, salvo que el caso sea skeleton
                initial_status = content_data.get("status", "draft")
                if content_data.get("content_type") == "slide":
                    ch = content_data.get("content_html")
                    nt = content_data.get("narrative_text")
                    ft = content_data.get("full_text")

                    # If clearly skeleton -> force skeleton regardless of provided status
                    if ft and not ch and not nt:
                        initial_status = "skeleton"
                    else:
                        if "status" in content_data:
                            initial_status = content_data["status"]
                        else:
                            if ch and nt:
                                initial_status = "narrative_ready"
                            elif ch:
                                initial_status = "html_ready"
                            elif ft:
                                initial_status = "skeleton"
                            else:
                                initial_status = "draft"
                
                # Crear objeto de contenido
                content = TopicContent(
                    topic_id=content_data.get("topic_id"),
                    content_type=content_data.get("content_type"),
                    content=content_data.get("content", ""),
                    interactive_data=content_data.get("interactive_data"),
                    learning_methodologies=content_data.get("learning_methodologies"),
                    adaptation_options=content_data.get("metadata"),
                    resources=content_data.get("resources"),
                    web_resources=content_data.get("web_resources"),
                    generation_prompt=content_data.get("generation_prompt"),
                    ai_credits=content_data.get("ai_credits", True),
                    personalization_markers=markers,
                    slide_template=content_data.get("slide_template", ""),
                    status=initial_status,
                    order=content_data.get("order"),
                    parent_content_id=content_data.get("parent_content_id"),
                    content_html=content_data.get("content_html"),
                    narrative_text=content_data.get("narrative_text"),
                    full_text=content_data.get("full_text"),
                    template_snapshot=content_data.get("template_snapshot")  # Incluir template_snapshot
                )
                
                # Insertar en la base de datos
                result = self.collection.insert_one(content.to_dict(), session=session)
                created_ids.append(str(result.inserted_id))

                # Logging para cada slide creado con campos HTML/narrativa
                if content_data.get("content_type") == "slide":
                    logging.info(f"Bulk: Slide creado para topic {content_data.get('topic_id')} con id {result.inserted_id}. status={initial_status}, has_html={'content_html' in content_data}, has_narrative={'narrative_text' in content_data}")
            
            # Actualizar métricas de tipos de contenido
            for content_type, count in content_types_usage.items():
                self.content_type_service.collection.update_one(
                    {"code": content_type},
                    {"$inc": {"usage_count": count}},
                    session=session
                )
            
            # Confirmar transacción
            session.commit_transaction()
            transaction_active = False
            
            logging.info(f"Creados {len(created_ids)} contenidos en lote exitosamente")
            return True, created_ids
            
        except Exception as e:
            # Solo hacer rollback si la transacción está activa
            if transaction_active:
                try:
                    session.abort_transaction()
                except Exception:
                    pass  # Ignorar errores en abort si ya fue abortada
            
            error_msg = str(e)
            logging.error(f"Error en creación bulk: {error_msg}")
            return False, error_msg
            
        finally:
            session.end_session()
    
    def create_bulk_slides_skeleton(self, slides_data: List[Dict]) -> Tuple[bool, List[str]]:
        """
        Creación masiva optimizada para diapositivas skeleton.
        Requisitos estrictos:
         - Todos los items deben tener content_type == 'slide'
         - Todos deben pertenecer al mismo topic_id
         - Cada slide debe incluir full_text (string) y template_snapshot (objeto/dict)
         - El orden (order) debe existir para cada slide y ser una secuencia consecutiva comenzando en 1
         - Las diapositivas serán creadas con status='skeleton' sin importar lo que envíe el cliente
        """
        if not slides_data:
            return False, "No se proporcionaron diapositivas para crear"

        # Validaciones iniciales
        first_topic = slides_data[0].get("topic_id")
        for i, slide in enumerate(slides_data):
            if slide.get("content_type") != "slide":
                return False, f"Elemento {i+1}: content_type debe ser 'slide'"
            if slide.get("topic_id") != first_topic:
                return False, "Todas las diapositivas deben pertenecer al mismo topic_id"
            if "order" not in slide or not isinstance(slide.get("order"), int) or slide.get("order") < 1:
                return False, f"Elemento {i+1}: order es requerido y debe ser entero positivo"
            if "full_text" not in slide or not isinstance(slide.get("full_text"), str) or not slide.get("full_text").strip():
                return False, f"Elemento {i+1}: full_text es requerido para crear una slide skeleton y debe ser una cadena no vacía"
            ts = slide.get("template_snapshot")
            if ts is None:
                return False, f"Elemento {i+1}: template_snapshot es requerido y debe ser un objeto con estilos"
            valid_ts, ts_msg = self.validate_template_snapshot(ts)
            if not valid_ts:
                return False, f"Elemento {i+1}: template_snapshot inválido: {ts_msg}"

        # Validar secuencia de orders: deben ser únicos y consecutivos comenzando en 1
        orders = sorted([s["order"] for s in slides_data])
        if orders[0] != 1:
            return False, "La secuencia de 'order' debe comenzar en 1"
        for idx, val in enumerate(orders, start=1):
            if val != idx:
                return False, f"La secuencia de 'order' debe ser consecutiva sin gaps. Esperado {idx}, encontrado {val}"

        # Preparar inserciones en transacción
        session = self.db.client.start_session()
        transaction_active = False
        try:
            session.start_transaction()
            transaction_active = True

            docs = []
            for slide in slides_data:
                # Extract markers
                content_for_markers = slide.get("content", "")
                if isinstance(content_for_markers, dict):
                    content_for_markers = json.dumps(content_for_markers, ensure_ascii=False)
                markers = ContentPersonalizationService.extract_markers(
                    content_for_markers or json.dumps(slide.get("interactive_data", {}))
                )

                # Auto-generate slide_template if not provided or invalid
                slide_template = slide.get("slide_template", "")
                if not slide_template or not self.slide_style_service.validate_slide_template(slide_template):
                    slide_template = self.slide_style_service.generate_slide_template()
                    logging.info(f"create_bulk_slides_skeleton: slide_template generado automáticamente para slide {slide.get('order', 'N/A')}")

                content_obj = TopicContent(
                    topic_id=slide.get("topic_id"),
                    content_type="slide",
                    content=slide.get("content", ""),
                    interactive_data=slide.get("interactive_data"),
                    learning_methodologies=slide.get("learning_methodologies"),
                    adaptation_options=slide.get("metadata"),
                    resources=slide.get("resources"),
                    web_resources=slide.get("web_resources"),
                    generation_prompt=slide.get("generation_prompt"),
                    ai_credits=slide.get("ai_credits", True),
                    personalization_markers=markers,
                    slide_template=slide_template,
                    # Force skeleton status regardless of provided status
                    status="skeleton",
                    order=slide.get("order"),
                    parent_content_id=slide.get("parent_content_id"),
                    content_html=None,  # Ensure data consistency for skeleton slides
                    narrative_text=None,  # Ensure data consistency for skeleton slides
                    full_text=slide.get("full_text")
                )
                d = content_obj.to_dict()
                # Store template_snapshot explicitly as provided for later rendering use
                d["template_snapshot"] = slide.get("template_snapshot")
                docs.append(d)

            # Insertar en bloque
            result = self.collection.insert_many(docs, session=session)
            inserted_ids = [str(_id) for _id in result.inserted_ids]

            # Actualizar contador de uso para slides
            self.content_type_service.collection.update_one(
                {"code": "slide"},
                {"$inc": {"usage_count": len(inserted_ids)}},
                session=session
            )

            session.commit_transaction()
            transaction_active = False

            logging.info(f"create_bulk_slides_skeleton: Insertadas {len(inserted_ids)} slides skeleton para topic {first_topic}")
            # Log structure of template_snapshot for debugging (capped verbosity)
            try:
                logging.debug(f"create_bulk_slides_skeleton: template_snapshot ejemplo: {json.dumps(slides_data[0].get('template_snapshot'), ensure_ascii=False)[:200]}")
            except Exception:
                pass

            return True, inserted_ids
        except Exception as e:
            if transaction_active:
                try:
                    session.abort_transaction()
                except Exception:
                    pass
            logging.error(f"Error en create_bulk_slides_skeleton: {e}")
            return False, str(e)
        finally:
            session.end_session()

    def _validate_sequential_order(self, contents_data: List[Dict], types: Tuple[str, ...] = ('slide',)) -> None:
        """
        Valida que el orden secuencial sea consistente si se proporciona.

        Args:
            contents_data: Lista de contenidos a validar
            types: Tupla de tipos de contenido a validar (default: solo slides)
        """
        groups = {}

        for i, content_data in enumerate(contents_data):
            # Solo incluir en la validación si el tipo de contenido está en los tipos especificados
            content_type = content_data.get("content_type")
            if content_type not in types:
                continue

            topic_id = content_data.get("topic_id")
            parent_id = content_data.get("parent_content_id")
            order = content_data.get("order")
            
            if order is not None:
                group_key = f"{topic_id}_{parent_id or 'root'}"
                
                if group_key not in groups:
                    groups[group_key] = []
                
                groups[group_key].append({
                    "index": i,
                    "order": order,
                    "content_type": content_type
                })
        
        # Validar cada grupo
        for group_key, items in groups.items():
            # Ordenar por order
            items.sort(key=lambda x: x["order"])
            
            # Verificar que no haya duplicados
            orders = [item["order"] for item in items]
            if len(orders) != len(set(orders)):
                duplicates = [order for order in set(orders) if orders.count(order) > 1]
                raise ValueError(f"Orden duplicado encontrado en grupo {group_key}: {duplicates}")
            
            # Verificar secuencia consecutiva desde 1 (incluso si hay un solo item)
            expected_order = 1
            for item in items:
                if item["order"] != expected_order:
                    raise ValueError(f"Orden secuencial incorrecto en grupo {group_key}: esperado {expected_order}, encontrado {item['order']}")
                expected_order += 1

    def get_topic_content(self, topic_id: str, content_type: str = None, status_filter: Optional[List[str]] = None, include_metadata: bool = True, limit: Optional[int] = None, skip: int = 0) -> List[Dict]:
        """
        Obtiene contenido de un tema, opcionalmente filtrado por tipo.
        Ordena por campo 'order' ascendente, con fallback a created_at descendente.

        Parámetros:
            status_filter: Lista de estados a filtrar (ej: ['skeleton','html_ready'])
            include_metadata: Si True (default) devuelve documentos completos para compatibilidad hacia atrás.
                            Si False, devuelve solo campos mínimos para optimizar performance.
            limit, skip: Paginación opcional

        Compatibilidad hacia atrás: include_metadata=True (default) devuelve documentos completos como en versiones anteriores;
                            cuando es False, se aplica una proyección mínima.
        """
        try:
            # Construir filtro de status por defecto según content_type si no se especifica
            if status_filter is None:
                status_filter = DEFAULT_STATUS_BY_TYPE.get(content_type, DEFAULT_STATUS_BY_TYPE["default"])

            query = {
                "topic_id": ObjectId(topic_id),
                "status": {"$in": status_filter}
            }

            if content_type:
                query["content_type"] = content_type

            # Proyección: por defecto (include_metadata=True) devuelve documentos completos para compatibilidad hacia atrás
            # Solo usar proyección mínima si include_metadata es explícitamente False
            if include_metadata:
                # Documentos completos por defecto para mantener compatibilidad
                projection = None
            else:
                # Si no se solicita metadata, usar proyección mínima
                projection = {
                    "content_type": 1,
                    "order": 1,
                    "status": 1,
                    "parent_content_id": 1
                }

            # Usar aggregation pipeline para soportar sorting con nulls y paginación de manera consistente
            pipeline = [
                {"$match": query},
                # Añadir a pipeline campo que indica si order es null para ordenar correctamente
                {"$addFields": {"_order_null": {"$eq": ["$order", None]}}},
                {"$sort": {"_order_null": 1, "order": 1, "created_at": -1}}
            ]

            # Solo añadir etapa de proyección si se especifica una
            if projection is not None:
                pipeline.append({"$project": projection})

            if skip and skip > 0:
                pipeline.append({"$skip": int(skip)})
            if limit and limit > 0:
                pipeline.append({"$limit": int(limit)})

            contents_cursor = self.collection.aggregate(pipeline)
            contents = list(contents_cursor)

            # Convertir ObjectIds a strings
            for content in contents:
                if content.get("_id"):
                    content["_id"] = str(content["_id"])
                if content.get("topic_id"):
                    try:
                        content["topic_id"] = str(content["topic_id"])
                    except Exception:
                        pass
                if content.get("creator_id"):
                    content["creator_id"] = str(content["creator_id"])
                if content.get("parent_content_id"):
                    try:
                        content["parent_content_id"] = str(content["parent_content_id"])
                    except Exception:
                        content["parent_content_id"] = content.get("parent_content_id")
            return contents

        except Exception as e:
            logging.error(f"Error obteniendo contenido del tema: {str(e)}")
            return []
    
    def get_structured_topic_content(self, topic_id: str, student_id: str = None) -> List[Dict]:
        """
        Obtiene contenido de un tema usando la secuencia estructurada.
        Reemplaza la intercalación aleatoria con una secuencia predecible:
        diapositivas → contenidos opcionales → evaluación
        
        Args:
            topic_id: ID del tema
            student_id: ID del estudiante (para personalización futura)
            
        Returns:
            Lista de contenidos en secuencia estructurada
        """
        try:
            return self.structured_sequence_service.get_structured_content_sequence(
                topic_id=topic_id,
                student_id=student_id
            )
        except Exception as e:
            logging.error(f"Error obteniendo secuencia estructurada: {str(e)}")
            # Fallback al método tradicional si falla la secuencia estructurada
            return self.get_topic_content(topic_id)
    
    def validate_topic_sequence(self, topic_id: str) -> Tuple[bool, List[str]]:
        """
        Valida la integridad de la secuencia estructurada de un tema.
        
        Args:
            topic_id: ID del tema
            
        Returns:
            Tuple[bool, List[str]]: (es_válida, lista_de_errores)
        """
        try:
            return self.structured_sequence_service.validate_sequence_integrity(topic_id)
        except Exception as e:
            logging.error(f"Error validando secuencia del tema: {str(e)}")
            return False, [f"Error interno: {str(e)}"]
    
    def reorder_topic_slides(self, topic_id: str, slide_order_mapping: Dict[str, int]) -> Tuple[bool, str]:
        """
        Reordena las diapositivas de un tema.
        
        Args:
            topic_id: ID del tema
            slide_order_mapping: Dict {slide_id: new_order}
            
        Returns:
            Tuple[bool, str]: (éxito, mensaje)
        """
        try:
            return self.structured_sequence_service.reorder_slides(topic_id, slide_order_mapping)
        except Exception as e:
            logging.error(f"Error reordenando diapositivas: {str(e)}")
            return False, f"Error interno: {str(e)}"
    
    def get_topic_sequence_statistics(self, topic_id: str) -> Dict:
        """
        Obtiene estadísticas de la secuencia estructurada de un tema.
        
        Args:
            topic_id: ID del tema
            
        Returns:
            Dict con estadísticas de la secuencia
        """
        try:
            return self.structured_sequence_service.get_sequence_statistics(topic_id)
        except Exception as e:
            logging.error(f"Error obteniendo estadísticas de secuencia: {str(e)}")
            return {}
    
    def generate_slide_template(self, palette_name: str = None, font_family: str = None, custom_colors: Dict = None) -> str:
        """
        Genera un slide_template usando el servicio de estilo de diapositivas.
        
        Args:
            palette_name: Nombre de la paleta predefinida (opcional)
            font_family: Familia de fuente específica (opcional)
            custom_colors: Colores personalizados (opcional)
            
        Returns:
            String con el prompt para generar el slide_template
        """
        return self.slide_style_service.generate_slide_template(
            palette_name=palette_name,
            font_family=font_family,
            custom_colors=custom_colors
        )
    
    def get_available_slide_palettes(self) -> List[str]:
        """
        Obtiene las paletas de colores disponibles para diapositivas.
        
        Returns:
            Lista de nombres de paletas disponibles
        """
        return self.slide_style_service.get_available_palettes()
    
    def get_slide_palette_preview(self, palette_name: str) -> Optional[Dict]:
        """
        Obtiene una vista previa de una paleta específica.
        
        Args:
            palette_name: Nombre de la paleta
            
        Returns:
            Dict con los colores de la paleta o None si no existe
        """
        return self.slide_style_service.get_palette_preview(palette_name)

    def get_interactive_content(self, topic_id: str) -> List[Dict]:
        """
        Obtiene solo contenido interactivo de un tema.
        """
        try:
            # Obtener tipos interactivos
            type_codes = ContentTypes.get_categories().get("interactive", [])
            
            query = {
                "topic_id": ObjectId(topic_id),
                "content_type": {"$in": type_codes},
                "status": {"$in": ["active", "published"]}
            }
            
            contents = list(self.collection.find(query))
            
            for content in contents:
                content["_id"] = str(content["_id"])
                content["topic_id"] = str(content["topic_id"])
                
            return contents
            
        except Exception as e:
            logging.error(f"Error obteniendo contenido interactivo: {str(e)}")
            return []

    def get_template_recommendations(self, topic_id: str, student_id: str = None) -> Dict:
        """
        Obtiene recomendaciones de plantillas para cada diapositiva de un tema.
        
        Args:
            topic_id: ID del tema
            student_id: ID del estudiante (para personalización futura)
            
        Returns:
            Dict con recomendaciones por diapositiva
        """
        try:
            return self.template_recommendation_service.get_topic_recommendations(
                topic_id=topic_id,
                student_id=student_id
            )
        except Exception as e:
            logging.error(f"Error obteniendo recomendaciones de plantillas: {str(e)}")
            return {}
    
    def apply_template_recommendations(self, topic_id: str, recommendations: Dict) -> Tuple[bool, str]:
        """
        Aplica recomendaciones de plantillas a las diapositivas de un tema.
        
        Args:
            topic_id: ID del tema
            recommendations: Dict con recomendaciones {slide_id: template_id}
            
        Returns:
            Tuple[bool, str]: (éxito, mensaje)
        """
        try:
            return self.template_recommendation_service.apply_recommendations(
                topic_id=topic_id,
                recommendations=recommendations
            )
        except Exception as e:
            logging.error(f"Error aplicando recomendaciones de plantillas: {str(e)}")
            return False, f"Error interno: {str(e)}"
    
    def get_slide_template_compatibility(self, slide_id: str, template_id: str) -> Dict:
        """
        Analiza la compatibilidad entre una diapositiva y una plantilla.
        
        Args:
            slide_id: ID de la diapositiva
            template_id: ID de la plantilla
            
        Returns:
            Dict con análisis de compatibilidad
        """
        try:
            return self.template_recommendation_service.analyze_slide_template_compatibility(
                slide_id=slide_id,
                template_id=template_id
            )
        except Exception as e:
            logging.error(f"Error analizando compatibilidad de plantilla: {str(e)}")
            return {}
    
    def submit_template_feedback(self, student_id: str, topic_id: str, slide_id: str,
                               template_id: str, feedback_data: Dict) -> Tuple[bool, str]:
        """
        Envía feedback sobre el uso de una plantilla al sistema RL.
        
        Args:
            student_id: ID del estudiante
            topic_id: ID del tema
            slide_id: ID de la diapositiva
            template_id: ID de la plantilla utilizada
            feedback_data: Datos de feedback
            
        Returns:
            Tuple[bool, str]: (éxito, mensaje)
        """
        return self.template_recommendation_service.submit_template_feedback(
            student_id, topic_id, slide_id, template_id, feedback_data
        )
    
    # Métodos para contenido embebido vs separado
    def analyze_content_embedding_strategy(self, slide_id: str, content_id: str):
        """
        Analiza si un contenido debe ser embebido o separado de una diapositiva.
        """
        return self.embedded_content_service.analyze_content_embedding_strategy(slide_id, content_id)
    
    def embed_content_in_slide(self, slide_id: str, content_id: str, embed_position: str = 'bottom'):
        """
        Embebe uncontenido dentro de una diapositiva.
        """
        return self.embedded_content_service.embed_content_in_slide(slide_id, content_id, embed_position)
    
    def extract_embedded_content(self, slide_id: str, content_id: str):
        """
        Extrae un contenido embebido y lo convierte en contenido separado.
        """
        return self.embedded_content_service.extract_embedded_content(slide_id, content_id)
    
    def get_embedding_recommendations(self, topic_id: str):
        """
        Obtiene recomendaciones de embedding para todos los contenidos de un tema.
        """
        return self.embedded_content_service.get_embedding_recommendations(topic_id)
    
    def get_embedding_statistics(self, topic_id: str):
        """
        Obtiene estadísticas de embedding para un tema.
        """
        return self.embedded_content_service.get_embedding_statistics(topic_id)
    
    def validate_template_snapshot(self, template_snapshot: Any) -> Tuple[bool, str]:
        """
        Valida la estructura esperada del campo `template_snapshot` que describe estilos de slide.
        Se espera un objeto/dict con campos como:
            - palette: dict {primary: "#FFFFFF", secondary: "#000000", ...}
            - grid: dict {columns: int, gap: int, rows: optional int}
            - fontFamilies: list of str
            - spacing: dict {small: int, medium: int, large: int}
            - breakpoints: dict {mobile: int, tablet: int, desktop: int}
        Retorna (True, "") si válido, o (False, "mensaje") si inválido.
        """
        try:
            if not isinstance(template_snapshot, dict):
                logging.debug("validate_template_snapshot: template_snapshot debe ser un objeto/dict")
                return False, "template_snapshot debe ser un objeto JSON (no un string)"
            
            # Required top-level keys (flexible)
            required_keys = ["palette", "grid", "fontFamilies", "spacing", "breakpoints"]
            for key in required_keys:
                if key not in template_snapshot:
                    return False, f"Falta campo requerido en template_snapshot: '{key}'"

            # Validate palette
            palette = template_snapshot.get("palette")
            if not isinstance(palette, dict) or not palette:
                return False, "palette debe ser un objeto con al menos un color"
            hex_color_re = re.compile(r'^#([A-Fa-f0-9]{6}|[A-Fa-f0-9]{3})$')
            for name, color in palette.items():
                if not isinstance(color, str) or not hex_color_re.match(color.strip()):
                    return False, f"palette.{name} debe ser un color hex válido (ej. '#RRGGBB')"

            # Validate grid
            grid = template_snapshot.get("grid")
            if not isinstance(grid, dict):
                return False, "grid debe ser un objeto con configuración de grillas"
            columns = grid.get("columns")
            if not isinstance(columns, int) or columns < 1:
                return False, "grid.columns debe ser un entero >= 1"
            if "gap" in grid and (not isinstance(grid.get("gap"), int) or grid.get("gap") < 0):
                return False, "grid.gap debe ser un entero >= 0 si se proporciona"

            # Validate fontFamilies
            font_families = template_snapshot.get("fontFamilies")
            if not isinstance(font_families, list) or not font_families or not all(isinstance(f, str) for f in font_families):
                return False, "fontFamilies debe ser una lista de cadenas de texto indicando familias de fuentes"

            # Validate spacing
            spacing = template_snapshot.get("spacing")
            if not isinstance(spacing, dict):
                return False, "spacing debe ser un objeto con valores numéricos"
            for k, v in spacing.items():
                if not isinstance(v, (int, float)) or v < 0:
                    return False, f"spacing.{k} debe ser un número >= 0"

            # Validate breakpoints
            breakpoints = template_snapshot.get("breakpoints")
            if not isinstance(breakpoints, dict) or not breakpoints:
                return False, "breakpoints debe ser un objeto con al menos un punto de ruptura"
            for name, val in breakpoints.items():
                if not isinstance(val, int) or val <= 0:
                    return False, f"breakpoints.{name} debe ser un entero positivo"

            logging.debug("validate_template_snapshot: estructura válida")
            return True, ""
        except Exception as e:
            logging.error(f"Error validando template_snapshot: {e}")
            return False, f"Error validando template_snapshot: {str(e)}"

    def update_content(self, content_id: str, update_data: Dict) -> Tuple[bool, str]:
        """
        Actualiza contenido existente.
        """
        try:
            # Obtener contenido actual para validaciones
            current_content = self.get_content(content_id)
            if not current_content:
                return False, "Contenido no encontrado"

            # Validaciones específicas para diapositivas
            content_type = update_data.get("content_type", current_content.get("content_type"))
            if content_type == "slide" and "slide_template" in update_data:
                slide_template = update_data.get("slide_template", "")
                if slide_template:  # Solo validar si se proporciona slide_template
                    # Validar que slide_template sea un prompt válido
                    if not self.slide_style_service.validate_slide_template(slide_template):
                        return False, "El slide_template no es un prompt válido"

            update_data["updated_at"] = datetime.now()

            # Manejo de marcadores si cambia el contenido
            if "content" in update_data or "interactive_data" in update_data:
                # Convertir content a string si es dict para el extractor de marcadores
                content_for_markers = update_data.get("content", "")
                if isinstance(content_for_markers, dict):
                    content_for_markers = json.dumps(content_for_markers, ensure_ascii=False)
                markers = ContentPersonalizationService.extract_markers(
                    content_for_markers or json.dumps(update_data.get("interactive_data", {}))
                )
                update_data["personalization_markers"] = markers

            # Validaciones y lógica adicional para campos de diapositivas HTML/narrativa/full_text
            if content_type == "slide":
                # Determine prospective values after update
                prospective_content_html = update_data.get("content_html", current_content.get("content_html"))
                prospective_narrative = update_data.get("narrative_text", current_content.get("narrative_text"))
                prospective_full_text = update_data.get("full_text", current_content.get("full_text"))

                # If content_html provided in update_data, validate it
                if "content_html" in update_data and update_data.get("content_html") is not None:
                    valid, msg = self.validate_slide_html_content(update_data.get("content_html"))
                    if not valid:
                        return False, f"content_html inválido: {msg}"
                    update_data["render_engine"] = "raw_html"
                    logging.info(f"Actualizando content_html para slide {content_id}")

                # Validate narrative_text / full_text types if provided
                if "narrative_text" in update_data and update_data.get("narrative_text") is not None and not isinstance(update_data.get("narrative_text"), str):
                    return False, "narrative_text debe ser una cadena de texto si se proporciona"
                if "full_text" in update_data and update_data.get("full_text") is not None and not isinstance(update_data.get("full_text"), str):
                    return False, "full_text debe ser una cadena de texto si se proporciona"

                # Update status based on presence of fields (prospective)
                new_status = current_content.get("status", "draft")
                if prospective_content_html and prospective_narrative:
                    new_status = "narrative_ready"
                elif prospective_content_html:
                    new_status = "html_ready"
                elif prospective_full_text and not prospective_content_html:
                    # only full_text present -> skeleton
                    new_status = "skeleton"
                # If no special fields present, keep the existing status unless explicitly provided
                # Allow explicit status override if provided
                if "status" in update_data:
                    new_status = update_data.get("status", new_status)

                update_data["status"] = new_status
                logging.info(f"update_content: slide {content_id} status será actualizado a '{new_status}'")

            result = self.collection.update_one(
                {"_id": ObjectId(content_id)},
                {"$set": update_data}
            )
            
            if result.modified_count > 0:
                return True, "Contenido actualizado exitosamente"
            else:
                return False, "No se encontró el contenido o no hubo cambios"
                
        except Exception as e:
            logging.error(f"Error actualizando contenido: {str(e)}")
            return False, f"Error interno: {str(e)}"

    def delete_content(self, content_id: str) -> Tuple[bool, str]:
        """
        Elimina contenido (soft delete) y sus contenidos hijos en cascada.
        """
        try:
            # Primero eliminar contenidos hijos (cascada)
            child_contents = self.collection.find({"parent_content_id": ObjectId(content_id)})
            child_count = 0
            
            for child in child_contents:
                child_result = self.collection.update_one(
                    {"_id": child["_id"]},
                    {"$set": {"status": "deleted", "updated_at": datetime.now()}}
                )
                if child_result.modified_count > 0:
                    child_count += 1
            
            # Luego eliminar el contenido principal
            result = self.collection.update_one(
                {"_id": ObjectId(content_id)},
                {"$set": {"status": "deleted", "updated_at": datetime.now()}}
            )
            
            if result.modified_count > 0:
                message = "Contenido eliminado exitosamente"
                if child_count > 0:
                    message += f" (incluyendo {child_count} contenidos hijos)"
                return True, message
            else:
                return False, "No se encontró el contenido"
                
        except Exception as e:
            logging.error(f"Error eliminando contenido: {str(e)}")
            return False, f"Error interno: {str(e)}"

    def get_content(self, content_id: str) -> Optional[Dict]:
        """Obtiene un contenido específico por su ID."""
        try:
            content = self.collection.find_one({"_id": ObjectId(content_id)})
            if not content:
                return None

            content["_id"] = str(content["_id"])
            content["topic_id"] = str(content["topic_id"])
            if content.get("creator_id"):
                content["creator_id"] = str(content["creator_id"])
            if content.get("parent_content_id"):
                content["parent_content_id"] = str(content["parent_content_id"])

            return content
        except Exception as e:
            logging.error(f"Error obteniendo contenido: {str(e)}")
            return None

    def get_slide_generation_status(self, topic_id: str) -> Dict:
        """
        Retorna estadísticas sobre el estado de generación de las diapositivas
        de un tema. Incluye:
            - counts por estado
            - slides_with_html, slides_with_narrative, slides_complete (ambos)
            - completion_percentage
            - average_generation_time_ms
            - estimated_time_remaining_ms
            - last_completed_slide (id + timestamp)
            - progress_trend (últimos 7 días)
            - slides_by_render_engine
            - parent_content_groups (stats por parent_content_id)
            - quality_metrics (avg html length, avg narrative length)
            - bottleneck_analysis (slides con mayor tiempo de generación)
        Implementa cache temporal para mejorar rendimiento en consultas frecuentes.
        """
        try:
            cache_key = f"slide_status::{topic_id}"
            with self._cache_lock:
                cached = self._stats_cache.get(cache_key)
                if cached:
                    ts = cached.get("ts")
                    if ts and (datetime.utcnow() - ts).total_seconds() < self._stats_cache_ttl:
                        logging.debug(f"get_slide_generation_status: returning cached status for topic {topic_id}")
                        return cached.get("value", {})

            # Build base query
            base_query = {
                "topic_id": ObjectId(topic_id),
                "content_type": "slide",
                "status": {"$ne": "deleted"}
            }

            # Fetch slides with fields needed for metrics
            slides_cursor = self.collection.find(base_query, {
                "_id": 1,
                "status": 1,
                "content_html": 1,
                "narrative_text": 1,
                "created_at": 1,
                "updated_at": 1,
                "render_engine": 1,
                "parent_content_id": 1
            })

            slides = list(slides_cursor)
            total = len(slides)
            if total == 0:
                result_empty = {
                    "total": 0,
                    "by_status": {},
                    "slides_with_html": 0,
                    "slides_with_narrative": 0,
                    "slides_complete": 0,
                    "completion_percentage": 0.0,
                    "average_generation_time_ms": None,
                    "estimated_time_remaining_ms": None,
                    "last_completed_slide": None,
                    "progress_trend": [],
                    "slides_by_render_engine": {},
                    "parent_content_groups": {},
                    "quality_metrics": {},
                    "bottleneck_analysis": []
                }
                with self._cache_lock:
                    self._stats_cache[cache_key] = {"ts": datetime.utcnow(), "value": result_empty}
                return result_empty

            by_status_counts: Dict[str, int] = {}
            slides_with_html = 0
            slides_with_narrative = 0
            slides_complete = 0
            gen_times_ms: List[float] = []
            slides_by_render_engine: Dict[str, int] = {}
            parent_groups: Dict[str, Dict[str, Any]] = {}
            html_lengths: List[int] = []
            narrative_lengths: List[int] = []
            last_completed_slide = None

            for s in slides:
                status = s.get("status") or "unknown"
                by_status_counts[status] = by_status_counts.get(status, 0) + 1

                has_html = bool(s.get("content_html"))
                has_narr = bool(s.get("narrative_text"))

                if has_html:
                    slides_with_html += 1
                    html_lengths.append(len(s.get("content_html") or ""))
                if has_narr:
                    slides_with_narrative += 1
                    narrative_lengths.append(len(s.get("narrative_text") or ""))
                if has_html and has_narr:
                    slides_complete += 1
                    # track last completed slide by updated_at
                    updated_at = s.get("updated_at") or s.get("created_at")
                    if updated_at:
                        if (last_completed_slide is None) or (isinstance(updated_at, datetime) and updated_at > last_completed_slide.get("updated_at")):
                            last_completed_slide = {
                                "content_id": str(s["_id"]),
                                "updated_at": updated_at
                            }

                # compute gen time if possible
                created = s.get("created_at")
                updated = s.get("updated_at")
                if isinstance(created, datetime) and isinstance(updated, datetime):
                    try:
                        delta_ms = (updated - created).total_seconds() * 1000.0
                        if delta_ms >= 0:
                            gen_times_ms.append(delta_ms)
                    except Exception:
                        pass

                # render engine counts
                engine = s.get("render_engine") or "unknown"
                slides_by_render_engine[engine] = slides_by_render_engine.get(engine, 0) + 1

                # parent grouping
                parent_raw = s.get("parent_content_id")
                try:
                    parent_key = str(parent_raw) if parent_raw is not None else "root"
                except Exception:
                    parent_key = "root"
                pg = parent_groups.setdefault(parent_key, {"total": 0, "with_html": 0, "with_narrative": 0, "complete": 0})
                pg["total"] += 1
                if has_html:
                    pg["with_html"] += 1
                if has_narr:
                    pg["with_narrative"] += 1
                if has_html and has_narr:
                    pg["complete"] += 1

            completion_percentage = round((slides_complete / total * 100), 2) if total > 0 else 0.0
            avg_gen_time = float(sum(gen_times_ms) / len(gen_times_ms)) if gen_times_ms else None
            pending_count = total - slides_with_html
            estimated_remaining = int(avg_gen_time * pending_count) if (avg_gen_time is not None and pending_count > 0) else None

            # quality metrics
            quality_metrics = {}
            try:
                quality_metrics["avg_html_length"] = round(sum(html_lengths) / len(html_lengths), 2) if html_lengths else 0
                quality_metrics["avg_narrative_length"] = round(sum(narrative_lengths) / len(narrative_lengths), 2) if narrative_lengths else 0
                quality_metrics["sample_html_length_distribution"] = {
                    "min": min(html_lengths) if html_lengths else 0,
                    "max": max(html_lengths) if html_lengths else 0,
                    "count": len(html_lengths)
                }
            except Exception:
                quality_metrics = {}

            # bottleneck analysis: slides with largest gen times
            bottleneck_analysis = []
            try:
                # Query top 3 by (updated_at - created_at)
                bottleneck_pipeline = [
                    {"$match": base_query},
                    {"$project": {
                        "_id": 1,
                        "created_at": 1,
                        "updated_at": 1,
                        "content_html": 1,
                        "narrative_text": 1
                    }},
                    {"$addFields": {
                        "gen_time_ms": {
                            "$cond": [
                                {"$and": [{"$ifNull": ["$created_at", False]}, {"$ifNull": ["$updated_at", False]}]},
                                {"$subtract": ["$updated_at", "$created_at"]},
                                None
                            ]
                        }
                    }},
                    {"$sort": {"gen_time_ms": -1}},
                    {"$limit": 5}
                ]
                top_bottlenecks = list(self.collection.aggregate(bottleneck_pipeline))
                for b in top_bottlenecks:
                    gen_time = b.get("gen_time_ms")
                    # gen_time may be a datetime delta coming from mongo pipeline; handle gracefully
                    try:
                        gen_time_val = float(gen_time)
                    except Exception:
                        gen_time_val = None
                    bottleneck_analysis.append({
                        "content_id": str(b["_id"]),
                        "gen_time_ms": gen_time_val,
                        "has_html": bool(b.get("content_html")),
                        "has_narrative": bool(b.get("narrative_text"))
                    })
            except Exception:
                bottleneck_analysis = []

                # progress trend: last 7 days updates (per day)
            try:
                from_date = datetime.utcnow() - timedelta(days=6)
                trend_pipeline = [
                    {"$match": {
                        "topic_id": ObjectId(topic_id),
                        "content_type": "slide",
                        "updated_at": {"$gte": from_date}
                    }},
                    {"$project": {"day": {"$dateToString": {"format": "%Y-%m-%d", "date": {"$ifNull": ["$updated_at", "$created_at"]}}}}},
                    {"$group": {"_id": "$day", "count": {"$sum": 1}}},
                    {"$sort": {"_id": 1}}
                ]
                trend_docs = list(self.collection.aggregate(trend_pipeline))
                progress_trend = [{ "date": t["_id"], "count": t["count"] } for t in trend_docs]
            except Exception:
                progress_trend = []

            last_completed_slide_info = None
            if last_completed_slide:
                try:
                    last_completed_slide_info = {
                        "content_id": last_completed_slide["content_id"],
                        "updated_at": last_completed_slide["updated_at"].isoformat() if isinstance(last_completed_slide["updated_at"], datetime) else last_completed_slide["updated_at"]
                    }
                except Exception:
                    last_completed_slide_info = None

            result = {
                "total": total,
                "by_status": by_status_counts,
                "slides_with_html": slides_with_html,
                "slides_with_narrative": slides_with_narrative,
                "slides_complete": slides_complete,
                "completion_percentage": completion_percentage,
                "average_generation_time_ms": avg_gen_time,
                "estimated_time_remaining_ms": estimated_remaining,
                "last_completed_slide": last_completed_slide_info,
                "progress_trend": progress_trend,
                "slides_by_render_engine": slides_by_render_engine,
                "parent_content_groups": parent_groups,
                "quality_metrics": quality_metrics,
                "bottleneck_analysis": bottleneck_analysis
            }

            # cache result
            with self._cache_lock:
                self._stats_cache[cache_key] = {"ts": datetime.utcnow(), "value": result}

            return result
        except Exception as e:
            logging.error(f"Error obteniendo estado de generación de slides para topic {topic_id}: {str(e)}")
            return {}
    
    def update_slide_html(self, content_id: str, html_content: str, updater_id: str = None) -> Tuple[bool, str]:
        """
        Actualiza únicamente el campo content_html de una diapositiva.
        - Valida existencia del contenido y que sea tipo 'slide'
        - Valida HTML mediante validate_slide_html_content
        - Actualiza status a 'html_ready' o 'narrative_ready' si ya existe narrativa
        - Registra logging detallado
        """
        try:
            if not isinstance(html_content, str):
                return False, "content_html debe ser una cadena de texto"

            current = self.get_content(content_id)
            if not current:
                logging.debug(f"update_slide_html: contenido {content_id} no encontrado")
                return False, "Contenido no encontrado"
            if current.get("content_type") != "slide":
                logging.debug(f"update_slide_html: contenido {content_id} no es tipo slide")
                return False, "El contenido no es una diapositiva"

            sanitized_html = self.sanitize_slide_html_content(html_content)
            valid, msg = self.validate_slide_html_content(sanitized_html)
            if not valid:
                logging.info(f"update_slide_html: validación fallida para slide {content_id}: {msg} (después de sanitización)")
                return False, f"content_html inválido después de sanitización: {msg}"

            update_data = {
                "content_html": sanitized_html,
                "updated_at": datetime.now(),
                "render_engine": "raw_html"
            }

            # Determinar nuevo estado
            existing_narrative = current.get("narrative_text")
            if existing_narrative:
                update_data["status"] = "narrative_ready"
            else:
                update_data["status"] = "html_ready"

            # Registrar quien hizo la actualización si se pasa updater_id
            if updater_id:
                update_data["last_updated_by"] = updater_id

            result = self.collection.update_one(
                {"_id": ObjectId(content_id)},
                {"$set": update_data}
            )

            if result.modified_count > 0:
                logging.info(f"update_slide_html: slide {content_id} actualizado a status {update_data.get('status')} by {updater_id or 'unknown'}")
                # Invalidate relevant caches for the topic
                try:
                    current_topic = current.get("topic_id")
                    cache_key = f"slide_status::{current_topic}"
                    with self._cache_lock:
                        if cache_key in self._stats_cache:
                            del self._stats_cache[cache_key]
                except Exception:
                    pass
                return True, "HTML de la diapositiva actualizado exitosamente"
            else:
                logging.debug(f"update_slide_html: no hubo cambios al actualizar slide {content_id}")
                return False, "No se realizaron cambios en el contenido"
        except Exception as e:
            logging.error(f"Error en update_slide_html para {content_id}: {str(e)}")
            return False, f"Error interno: {str(e)}"

    def update_slide_narrative(self, content_id: str, narrative_text: str, updater_id: str = None) -> Tuple[bool, str]:
        """
        Actualiza únicamente el campo narrative_text de una diapositiva.
        - Valida existencia del contenido y que sea tipo 'slide'
        - Valida tamaño y formato del texto narrativo
        - Actualiza status a 'narrative_ready' si la diapositiva ya tiene HTML
        - Logging específico
        """
        try:
            if not isinstance(narrative_text, str):
                return False, "narrative_text debe ser una cadena de texto"

            narrative_trim = narrative_text.strip()
            if not narrative_trim:
                return False, "narrative_text no debe estar vacío"

            max_len = 5000
            if len(narrative_trim) > max_len:
                logging.warning(f"update_slide_narrative: narrative_text demasiado largo ({len(narrative_trim)} > {max_len})")
                return False, f"narrative_text excede el tamaño máximo permitido de {max_len} caracteres"

            current = self.get_content(content_id)
            if not current:
                logging.debug(f"update_slide_narrative: contenido {content_id} no encontrado")
                return False, "Contenido no encontrado"
            if current.get("content_type") != "slide":
                logging.debug(f"update_slide_narrative: contenido {content_id} no es tipo slide")
                return False, "El contenido no es una diapositiva"

            update_data = {
                "narrative_text": narrative_trim,
                "updated_at": datetime.now()
            }

            # Si ya existe HTML, marcar como narrative_ready
            existing_html = current.get("content_html")
            if existing_html:
                update_data["status"] = "narrative_ready"
            else:
                # Mantener estado actual si no hay HTML; no forzar narrative_ready
                update_data["status"] = current.get("status", "draft")

            if updater_id:
                update_data["last_updated_by"] = updater_id

            result = self.collection.update_one(
                {"_id": ObjectId(content_id)},
                {"$set": update_data}
            )

            if result.modified_count > 0:
                logging.info(f"update_slide_narrative: slide {content_id} narrative actualizado. nuevo_status={update_data.get('status')}")
                # Invalidate relevant caches for the topic
                try:
                    current_topic = current.get("topic_id")
                    cache_key = f"slide_status::{current_topic}"
                    with self._cache_lock:
                        if cache_key in self._stats_cache:
                            del self._stats_cache[cache_key]
                except Exception:
                    pass
                return True, "Narrativa de la diapositiva actualizada exitosamente"
            else:
                logging.debug(f"update_slide_narrative: no hubo cambios al actualizar narrativa slide {content_id}")
                return False, "No se realizaron cambios en la narrativa"
        except Exception as e:
            logging.error(f"Error en update_slide_narrative para {content_id}: {str(e)}")
            return False, f"Error interno: {str(e)}"

    def get_slide_status_details(self, content_id: str) -> Dict:
        """
        Retorna detalles sobre el estado de generación de una diapositiva específica.
        Incluye flags de presencia de campos, estado actual, timestamps y una estimación de progreso.
        Useful para polling desde el frontend para ver avance de generación.
        """
        try:
            current = self.get_content(content_id)
            if not current:
                logging.debug(f"get_slide_status_details: contenido {content_id} no encontrado")
                return {}

            status = current.get("status", "unknown")
            has_html = bool(current.get("content_html"))
            has_narrative = bool(current.get("narrative_text"))
            has_full_text = bool(current.get("full_text"))

            # Estimación simple de progreso (0-100)
            if has_html and has_narrative:
                progress = 100
            elif has_html:
                progress = 70
            elif has_full_text:
                progress = 40
            else:
                progress = 0

            created_at = current.get("created_at")
            updated_at = current.get("updated_at")

            # Convertir timestamps a ISO si son datetime para serialización
            def iso(dt):
                try:
                    if isinstance(dt, datetime):
                        return dt.isoformat()
                    return dt
                except Exception:
                    return None

            details = {
                "content_id": content_id,
                "status": status,
                "has_content_html": has_html,
                "has_narrative_text": has_narrative,
                "has_full_text": has_full_text,
                "content_html_length": len(current.get("content_html") or ""),
                "narrative_text_length": len(current.get("narrative_text") or ""),
                "full_text_length": len(current.get("full_text") or ""),
                "progress_estimate": progress,
                "created_at": iso(created_at),
                "updated_at": iso(updated_at),
                "topic_id": current.get("topic_id"),
                "last_updated_by": current.get("last_updated_by")
            }

            logging.debug(f"get_slide_status_details: detalles para {content_id}: {details}")
            return details
        except Exception as e:
            logging.error(f"Error obteniendo detalles de estado para slide {content_id}: {str(e)}")
            return {}

    def check_topic_slides_completeness(self, topic_id: str) -> Dict:
        """
        Verifica la completitud de las diapositivas de un tema:
            - Calcula porcentajes de completitud (html + narrative)
            - Identifica slides faltantes o incompletas con razones
            - Valida orden secuencial correcto por parent_content_id
            - Valida consistencia de template_snapshot entre slides (si aplica)
        Retorna un reporte detallado.
        """
        try:
            query = {
                "topic_id": ObjectId(topic_id),
                "content_type": "slide",
                "status": {"$ne": "deleted"}
            }
            slides = list(self.collection.find(query, {
                "_id": 1, "order": 1, "parent_content_id": 1,
                "content_html": 1, "narrative_text": 1, "full_text": 1,
                "template_snapshot": 1, "status": 1, "created_at": 1, "updated_at": 1
            }).sort([("order", 1), ("created_at", 1)]))

            total = len(slides)
            if total == 0:
                return {
                    "total": 0,
                    "percent_complete": 0.0,
                    "missing_or_incomplete": [],
                    "sequence_errors": [],
                    "template_snapshot_issues": [],
                    "per_parent": {}
                }

            missing_or_incomplete = []
            template_snapshots = {}
            per_parent = {}
            sequence_errors = []

            for s in slides:
                sid = str(s["_id"])
                order = s.get("order")
                parent = s.get("parent_content_id")
                try:
                    parent_key = str(parent) if parent is not None else "root"
                except Exception:
                    parent_key = "root"

                if parent_key not in per_parent:
                    per_parent[parent_key] = {"slides": [], "orders": []}

                has_html = bool(s.get("content_html"))
                has_narrative = bool(s.get("narrative_text"))
                has_full_text = bool(s.get("full_text"))
                status = s.get("status", "")

                # Reasons for incomplete
                reasons = []
                if not has_html:
                    reasons.append("missing_html")
                if not has_narrative:
                    reasons.append("missing_narrative")
                # skeleton is acceptable but still incomplete for virtualization if no html
                if status == "skeleton" and not has_html:
                    reasons.append("skeleton_without_html")
                if not reasons:
                    # complete slide
                    pass
                else:
                    missing_or_incomplete.append({
                        "content_id": sid,
                        "order": order,
                        "parent_content_id": parent_key,
                        "reasons": reasons,
                        "status": status
                    })

                # Track template_snapshot consistency: build a fingerprint of keys for simplicity
                ts = s.get("template_snapshot")
                if ts is None:
                    # record missing template_snapshot
                    template_snapshots.setdefault("missing", []).append(sid)
                else:
                    try:
                        # fingerprint as sorted keys list
                        keys = sorted(list(ts.keys())) if isinstance(ts, dict) else ["non_dict_snapshot"]
                        key_sig = tuple(keys)
                        template_snapshots.setdefault(key_sig, []).append(sid)
                    except Exception:
                        template_snapshots.setdefault("invalid", []).append(sid)

                per_parent[parent_key]["slides"].append({
                    "content_id": sid,
                    "order": order,
                    "has_html": has_html,
                    "has_narrative": has_narrative,
                    "status": status
                })
                if isinstance(order, int):
                    per_parent[parent_key]["orders"].append(order)

            # Validate sequence per parent: consecutive from 1
            for parent_key, info in per_parent.items():
                orders = sorted([o for o in info["orders"] if isinstance(o, int)])
                if not orders:
                    continue
                if orders[0] != 1:
                    sequence_errors.append({
                        "parent_content_id": parent_key,
                        "error": "sequence_not_starting_at_1",
                        "orders": orders
                    })
                expected = 1
                for o in orders:
                    if o != expected:
                        sequence_errors.append({
                            "parent_content_id": parent_key,
                            "error": "sequence_gap_or_mismatch",
                            "expected": expected,
                            "found": o,
                            "orders": orders
                        })
                        break
                    expected += 1

            # Template snapshot issues: if more than one signature besides 'missing' exists -> inconsistent
            ts_issues = []
            sigs = [k for k in template_snapshots.keys()]
            # Count distinct non-missing signatures
            non_missing_sigs = [k for k in sigs if k != "missing" and k != "invalid"]
            if len(set(non_missing_sigs)) > 1:
                ts_issues.append({
                    "issue": "inconsistent_template_signatures",
                    "signatures_count": len(set(non_missing_sigs)),
                    "details": {str(k): v for k, v in template_snapshots.items()}
                })
            if "missing" in template_snapshots:
                ts_issues.append({
                    "issue": "missing_template_snapshot",
                    "count": len(template_snapshots.get("missing", [])),
                    "examples": template_snapshots.get("missing", [])[:5]
                })
            if "invalid" in template_snapshots:
                ts_issues.append({
                    "issue": "invalid_template_snapshot",
                    "count": len(template_snapshots.get("invalid", [])),
                    "examples": template_snapshots.get("invalid", [])[:5]
                })

            complete_count = total - len(missing_or_incomplete)
            percent_complete = round((complete_count / total * 100), 2)

            report = {
                "total": total,
                "complete_count": complete_count,
                "percent_complete": percent_complete,
                "missing_or_incomplete": missing_or_incomplete,
                "sequence_errors": sequence_errors,
                "template_snapshot_issues": ts_issues,
                "per_parent": per_parent
            }
            return report
        except Exception as e:
            logging.error(f"Error verificando completitud de slides para topic {topic_id}: {e}")
            return {}
    
    def get_topic_slides_optimized(self, topic_id: str, status_filter: Optional[List[str]] = None,
                                   render_engine: Optional[str] = None, group_by_parent: bool = False,
                                   include_progress: bool = True, limit: Optional[int] = None, skip: int = 0) -> Dict:
        """
        Método optimizado para consultas de diapositivas con filtros avanzados.
        Soporta:
            - filtros por status (lista),
            - filtro por render_engine (ej: 'raw_html'),
            - agrupamiento por parent_content_id,
            - inclusión de metadatos de progreso (total, completed, pending),
            - paginación (limit, skip)

        Retorna:
            {
                "stats": { total, completed, pending, slides_with_html, slides_with_narrative },
                "slides": [ ... ]  # lista de slides (paginada si se solicita)
                "by_parent": { parent_id: { stats:..., slides: [...] } }  # opcional
                "last_completed_slide": {...},
                "completion_trend": [...],
                "generation_efficiency": {...}
            }
        Implementa validaciones adicionales, caching para stats y optimizaciones cuando se solicitan sólo slides completas.
        """
        try:
            # Validate topic_id
            try:
                topic_obj_id = ObjectId(topic_id)
            except Exception:
                logging.error(f"get_topic_slides_optimized: topic_id inválido: {topic_id}")
                return {}

            if status_filter is None:
                status_filter = ["draft", "active", "published", "skeleton", "html_ready", "narrative_ready"]

            # Normalize group_by_parent to bool
            group_by_parent = bool(group_by_parent)

            match: Dict[str, Any] = {
                "topic_id": topic_obj_id,
                "content_type": "slide",
                "status": {"$in": status_filter}
            }
            if render_engine:
                match["render_engine"] = render_engine

            # If caller only wants completed slides (both html and narrative present), route to specialized fast method
            only_completed = set(status_filter) == {"narrative_ready"} or (status_filter == ["narrative_ready"])
            if only_completed and not group_by_parent and not include_progress and limit is None and skip == 0 and not render_engine:
                # Very fast path: use specialized query to retrieve completed slides
                try:
                    comp = self.get_complete_slides_only(topic_id)
                    return {
                        "stats": {
                            "total": len(comp.get("slides", [])),
                            "slides_complete": len(comp.get("slides", []))
                        },
                        "slides": comp.get("slides", []),
                        "last_completed_slide": comp.get("last_completed_slide"),
                        "completion_trend": comp.get("completion_trend", []),
                        "generation_efficiency": comp.get("generation_efficiency")
                    }
                except Exception as e:
                    logging.debug(f"get_topic_slides_optimized: fast path get_complete_slides_only failed: {e}")
                    # fallback to full pipeline

            # Base projection pipeline
            pipeline = [
                {"$match": match},
                {"$project": {
                    "_id": 1,
                    "order": 1,
                    "parent_content_id": 1,
                    "status": 1,
                    "content_html": 1,
                    "narrative_text": 1,
                    "created_at": 1,
                    "updated_at": 1,
                    "render_engine": 1,
                    "has_html": {"$cond": [{"$ifNull": ["$content_html", False]}, 1, 0]},
                    "has_narrative": {"$cond": [{"$ifNull": ["$narrative_text", False]}, 1, 0]},
                    "gen_time_ms": {
                        "$cond": [
                            {"$and": [{"$ifNull": ["$created_at", False]}, {"$ifNull": ["$updated_at", False]}]},
                            {"$subtract": ["$updated_at", "$created_at"]},
                            None
                        ]
                    }
                }},
                {"$sort": {"order": 1, "created_at": 1}}
            ]

            # Slides retrieval pipeline with pagination
            slides_pipeline = list(pipeline)
            if skip and skip > 0:
                slides_pipeline.append({"$skip": int(skip)})
            if limit and limit > 0:
                slides_pipeline.append({"$limit": int(limit)})

            slides_cursor = self.collection.aggregate(slides_pipeline)
            slides_list = []
            for s in slides_cursor:
                try:
                    slide_item = {
                        "content_id": str(s["_id"]),
                        "order": s.get("order"),
                        "parent_content_id": str(s.get("parent_content_id")) if s.get("parent_content_id") else None,
                        "status": s.get("status"),
                        "has_html": bool(s.get("has_html")),
                        "has_narrative": bool(s.get("has_narrative")),
                        "created_at": s.get("created_at").isoformat() if isinstance(s.get("created_at"), datetime) else s.get("created_at"),
                        "updated_at": s.get("updated_at").isoformat() if isinstance(s.get("updated_at"), datetime) else s.get("updated_at"),
                        "render_engine": s.get("render_engine")
                    }
                except Exception:
                    slide_item = {"content_id": str(s.get("_id"))}
                slides_list.append(slide_item)

            # Stats: try to use cached aggregated stats
            cache_key = f"slides_optimized_stats::{topic_id}::{render_engine}::{','.join(sorted(status_filter))}::{group_by_parent}"
            with self._cache_lock:
                cached = self._stats_cache.get(cache_key)
                if cached and (datetime.utcnow() - cached.get("ts")).total_seconds() < self._stats_cache_ttl:
                    logging.debug(f"get_topic_slides_optimized: using cached stats for key {cache_key}")
                    cached_stats = cached.get("value", {})
                else:
                    # Compute stats
                    stats_pipeline = [
                        {"$match": match},
                        {"$group": {
                            "_id": None,
                            "total": {"$sum": 1},
                            "slides_with_html": {"$sum": {"$cond": [{"$ifNull": ["$content_html", False]}, 1, 0]}},
                            "slides_with_narrative": {"$sum": {"$cond": [{"$ifNull": ["$narrative_text", False]}, 1, 0]}},
                            "slides_complete": {"$sum": {"$cond": [{"$and": [{"$ifNull": ["$content_html", False]}, {"$ifNull": ["$narrative_text", False]}]}, 1, 0]}},
                            "avg_gen_time_ms": {"$avg": {"$cond": [
                                {"$and": [{"$ifNull": ["$created_at", False]}, {"$ifNull": ["$updated_at", False]}]},
                                {"$subtract": ["$updated_at", "$created_at"]},
                                None
                            ]}}
                        }}
                    ]
                    stats_res = list(self.collection.aggregate(stats_pipeline))
                    if stats_res:
                        st = stats_res[0]
                        total = int(st.get("total", 0))
                        slides_with_html = int(st.get("slides_with_html", 0))
                        slides_with_narrative = int(st.get("slides_with_narrative", 0))
                        slides_complete = int(st.get("slides_complete", 0))
                        avg_gen_time = st.get("avg_gen_time_ms")
                    else:
                        total = slides_with_html = slides_with_narrative = slides_complete = 0
                        avg_gen_time = None

                    pending = total - slides_with_html
                    completion_percentage = round((slides_complete / total * 100), 2) if total > 0 else 0.0
                    estimated_time_remaining_ms = int(avg_gen_time * pending) if (avg_gen_time is not None and pending > 0) else None

                    # Determine last completed slide
                    last_completed = None
                    try:
                        last_doc = self.collection.find_one({
                            "topic_id": topic_obj_id,
                            "content_type": "slide",
                            "content_html": {"$ne": None},
                            "narrative_text": {"$ne": None},
                        }, sort=[("updated_at", -1)], projection={"_id": 1, "updated_at": 1})
                        if last_doc:
                            last_completed = {
                                "content_id": str(last_doc["_id"]),
                                "updated_at": last_doc.get("updated_at").isoformat() if isinstance(last_doc.get("updated_at"), datetime) else last_doc.get("updated_at")
                            }
                    except Exception:
                        last_completed = None

                    # completion trend last 7 days
                    try:
                        from_date = datetime.utcnow() - timedelta(days=6)
                        trend_pipeline = [
                            {"$match": {
                                "topic_id": topic_obj_id,
                                "content_type": "slide",
                                "updated_at": {"$gte": from_date}
                            }},
                            {"$project": {"day": {"$dateToString": {"format": "%Y-%m-%d", "date": {"$ifNull": ["$updated_at", "$created_at"]}}}}},
                            {"$group": {"_id": "$day", "count": {"$sum": 1}}},
                            {"$sort": {"_id": 1}}
                        ]
                        trend_docs = list(self.collection.aggregate(trend_pipeline))
                        progress_trend = [{ "date": t["_id"], "count": t["count"] } for t in trend_docs]
                    except Exception:
                        progress_trend = []

                    # generation_efficiency heuristic: slides_complete / (avg_gen_time_ms + 1)
                    try:
                        generation_efficiency = None
                        if avg_gen_time is not None and avg_gen_time > 0:
                            generation_efficiency = round((slides_complete / total) / (avg_gen_time / 1000.0 + 1e-6), 6) if total > 0 else None
                        else:
                            generation_efficiency = None
                    except Exception:
                        generation_efficiency = None

                    cached_stats = {
                        "total": total,
                        "slides_with_html": slides_with_html,
                        "slides_with_narrative": slides_with_narrative,
                        "slides_complete": slides_complete,
                        "pending": pending,
                        "completion_percentage": completion_percentage,
                        "average_generation_time_ms": float(avg_gen_time) if avg_gen_time is not None else None,
                        "estimated_time_remaining_ms": estimated_time_remaining_ms,
                        "last_completed_slide": last_completed,
                        "completion_trend": progress_trend,
                        "generation_efficiency": generation_efficiency
                    }

                    with self._cache_lock:
                        self._stats_cache[cache_key] = {"ts": datetime.utcnow(), "value": cached_stats}

            result = {
                "stats": {
                    "total": cached_stats.get("total", 0),
                    "slides_with_html": cached_stats.get("slides_with_html", 0),
                    "slides_with_narrative": cached_stats.get("slides_with_narrative", 0),
                    "slides_complete": cached_stats.get("slides_complete", 0),
                    "pending": cached_stats.get("pending", 0),
                    "completion_percentage": cached_stats.get("completion_percentage", 0.0),
                    "average_generation_time_ms": cached_stats.get("average_generation_time_ms"),
                    "estimated_time_remaining_ms": cached_stats.get("estimated_time_remaining_ms")
                },
                "slides": slides_list,
                "last_completed_slide": cached_stats.get("last_completed_slide"),
                "completion_trend": cached_stats.get("completion_trend"),
                "generation_efficiency": cached_stats.get("generation_efficiency")
            }

            if group_by_parent:
                # Group slides by parent_content_id and compute per-parent stats
                group_pipeline = [
                    {"$match": match},
                    {"$project": {
                        "parent_content_id": {"$ifNull": ["$parent_content_id", None]},
                        "has_html": {"$cond": [{"$ifNull": ["$content_html", False]}, 1, 0]},
                        "has_narrative": {"$cond": [{"$ifNull": ["$narrative_text", False]}, 1, 0]},
                        "complete": {"$cond": [{"$and": [{"$ifNull": ["$content_html", False]}, {"$ifNull": ["$narrative_text", False]}]}, 1, 0]},
                        "order": 1
                    }},
                    {"$group": {
                        "_id": {"parent": "$parent_content_id"},
                        "total": {"$sum": 1},
                        "with_html": {"$sum": "$has_html"},
                        "with_narrative": {"$sum": "$has_narrative"},
                        "complete": {"$sum": "$complete"},
                        "orders": {"$push": "$order"}
                    }}
                ]
                grouped = list(self.collection.aggregate(group_pipeline))
                by_parent = {}
                for g in grouped:
                    parent_key = str(g["_id"]["parent"]) if g["_id"]["parent"] else "root"
                    total_p = int(g.get("total", 0))
                    with_html_p = int(g.get("with_html", 0))
                    with_narrative_p = int(g.get("with_narrative", 0))
                    complete_p = int(g.get("complete", 0))
                    by_parent[parent_key] = {
                        "total": total_p,
                        "with_html": with_html_p,
                        "with_narrative": with_narrative_p,
                        "complete": complete_p,
                        "orders": sorted([o for o in g.get("orders", []) if isinstance(o, int)])
                    }
                result["by_parent"] = by_parent

            return result
        except Exception as e:
            logging.error(f"Error en get_topic_slides_optimized para topic {topic_id}: {e}")
            return {}
