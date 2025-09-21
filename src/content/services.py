from typing import Tuple, List, Dict, Optional, Any
from bson import ObjectId
from datetime import datetime, timedelta
import json
import logging

from src.shared.database import get_db
from src.shared.constants import STATUS
from src.shared.standardization import VerificationBaseService, ErrorCodes
from src.shared.exceptions import AppException
from .models import ContentType, TopicContent, VirtualTopicContent, ContentResult, ContentTypes
from .slide_style_service import SlideStyleService
import re
from src.ai_monitoring.services import AIMonitoringService
from .structured_sequence_service import StructuredSequenceService
from .template_recommendation_service import TemplateRecommendationService
from .embedded_content_service import EmbeddedContentService
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

    def create_content(self, content_data: Dict) -> Tuple[bool, str]:
        """
        Crea contenido de cualquier tipo (estático o interactivo).
        
        Args:
            content_data: Datos del contenido a crear
            
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

            # Validaciones específicas para diapositivas
            if content_type == "slide":
                slide_template = content_data.get("slide_template", {})
                if not slide_template:
                    return False, f"El contenido de tipo '{content_type}' requiere un campo 'slide_template' con la plantilla de fondo"
                
                # Validar estructura del slide_template usando el servicio
                if not self.slide_style_service.validate_slide_template(slide_template):
                    return False, "El slide_template no tiene una estructura válida"

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
                slide_template=content_data.get("slide_template", {}),  # Incluir slide_template
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
                    slide_template = content_data.get("slide_template", {})
                    if not slide_template:
                        raise ValueError(f"Contenido {i+1}: El contenido de tipo 'slide' requiere un campo 'slide_template'")

                    if not self.slide_style_service.validate_slide_template(slide_template):
                        raise ValueError(f"Contenido {i+1}: El slide_template no tiene una estructura válida")

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
                    slide_template=content_data.get("slide_template", {}),
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
                    slide_template=slide.get("slide_template", {}),
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
                {"$addFields": {"_order_null": {"$eq": [ {"$ifNull": ["$order", "__NULL__"]}, "__NULL__"] }}},
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
    
    def generate_slide_template(self, palette_name: str = None, font_family: str = None, custom_colors: Dict = None) -> Dict:
        """
        Genera un slide_template usando el servicio de estilo de diapositivas.
        
        Args:
            palette_name: Nombre de la paleta predefinida (opcional)
            font_family: Familia de fuente específica (opcional)
            custom_colors: Colores personalizados (opcional)
            
        Returns:
            Dict con el slide_template generado
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
                slide_template = update_data.get("slide_template", {})
                if slide_template:  # Solo validar si se proporciona slide_template
                    # Validar estructura básica de slide_template
                    required_template_fields = ["background", "styles"]
                    for field in required_template_fields:
                        if field not in slide_template:
                            return False, f"El slide_template debe incluir el campo '{field}'"

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
        de un tema. Utiliza aggregation pipeline para obtener métricas más detalladas:
            - counts por estado
            - slides_with_html, slides_with_narrative, slides_complete (ambos)
            - completion_percentage
            - average_generation_time (ms) basado en updated_at - created_at cuando esté disponible
            - estimated_time_remaining (ms) = avg_gen_time * pending_count
            - last_updated_slide (id + timestamp)
            - progress_trend: lista de counts por día (últimos 7 días)
        """
        try:
            match_stage = {
                "$match": {
                    "topic_id": ObjectId(topic_id),
                    "content_type": "slide",
                    "status": {"$ne": "deleted"}
                }
            }

            # Pipeline para métricas agregadas
            pipeline = [
                match_stage,
                {"$project": {
                    "status": 1,
                    "content_html": 1,
                    "narrative_text": 1,
                    "created_at": 1,
                    "updated_at": 1
                }},
                {"$addFields": {
                    "has_html": {"$cond": [{"$ifNull": ["$content_html", False]}, 1, 0]},
                    "has_narrative": {"$cond": [{"$ifNull": ["$narrative_text", False]}, 1, 0]},
                    "gen_time_ms": {
                        "$cond": [
                            {"$and": [{"$ifNull": ["$created_at", False]}, {"$ifNull": ["$updated_at", False]}]},
                            {"$subtract": ["$updated_at", "$created_at"]},
                            None
                        ]
                    },
                    "updated_day": {"$dateToString": {"format": "%Y-%m-%d", "date": {"$ifNull": ["$updated_at", "$created_at"]}}}
                }},
                {"$group": {
                    "_id": None,
                    "total": {"$sum": 1},
                    "by_status": {"$push": "$status"},
                    "slides_with_html": {"$sum": "$has_html"},
                    "slides_with_narrative": {"$sum": "$has_narrative"},
                    "slides_complete": {"$sum": {"$cond": [{"$and": [{"$eq": ["$has_html", 1]}, {"$eq": ["$has_narrative", 1]}]}, 1, 0]}},
                    "gen_times": {"$push": "$gen_time_ms"},
                    "last_updated": {"$max": "$updated_at"},
                    "updated_days": {"$push": "$updated_day"}
                }},
            ]

            agg_result = list(self.collection.aggregate(pipeline))
            if not agg_result:
                # No slides found -> return zeros
                return {
                    "total": 0,
                    "by_status": {},
                    "slides_with_html": 0,
                    "slides_with_narrative": 0,
                    "slides_complete": 0,
                    "completion_percentage": 0.0,
                    "average_generation_time_ms": None,
                    "estimated_time_remaining_ms": None,
                    "last_updated_slide": None,
                    "progress_trend": []
                }

            data = agg_result[0]

            # Compute by_status counts
            by_status_counts = {}
            for s in data.get("by_status", []):
                if not s:
                    s = "unknown"
                by_status_counts[s] = by_status_counts.get(s, 0) + 1

            total = data.get("total", 0)
            slides_with_html = int(data.get("slides_with_html", 0))
            slides_with_narrative = int(data.get("slides_with_narrative", 0))
            slides_complete = int(data.get("slides_complete", 0))

            completion_percentage = round((slides_complete / total * 100), 2) if total > 0 else 0.0

            # Average generation time (ms) ignoring nulls
            gen_times = [g for g in data.get("gen_times", []) if isinstance(g, (int, float))]
            avg_gen_time = None
            if gen_times:
                try:
                    avg_gen_time = sum(gen_times) / len(gen_times)
                    # ensure numeric
                    avg_gen_time = float(avg_gen_time)
                except Exception:
                    avg_gen_time = None

            # Estimated time remaining: avg_gen_time * pending_count (where pending = total - slides_with_html)
            pending_count = total - slides_with_html
            estimated_remaining = None
            if avg_gen_time is not None and pending_count > 0:
                estimated_remaining = int(avg_gen_time * pending_count)

            last_updated_ts = data.get("last_updated")
            last_updated_slide_info = None
            try:
                # Find the slide document with the last_updated timestamp to return id
                if last_updated_ts:
                    doc = self.collection.find_one({
                        "topic_id": ObjectId(topic_id),
                        "content_type": "slide",
                        "updated_at": last_updated_ts
                    }, {"_id": 1, "updated_at": 1})
                    if doc:
                        last_updated_slide_info = {
                            "content_id": str(doc["_id"]),
                            "updated_at": doc.get("updated_at").isoformat() if isinstance(doc.get("updated_at"), datetime) else doc.get("updated_at")
                        }
            except Exception:
                last_updated_slide_info = None

            # Progress trend: count of updates per day for the last 7 days
            try:
                # Build trend pipeline
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

            result = {
                "total": total,
                "by_status": by_status_counts,
                "slides_with_html": slides_with_html,
                "slides_with_narrative": slides_with_narrative,
                "slides_complete": slides_complete,
                "completion_percentage": completion_percentage,
                "average_generation_time_ms": avg_gen_time,
                "estimated_time_remaining_ms": estimated_remaining,
                "last_updated_slide": last_updated_slide_info,
                "progress_trend": progress_trend
            }
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
            }
        """
        try:
            if status_filter is None:
                status_filter = ["draft", "active", "published", "skeleton", "html_ready", "narrative_ready"]

            match = {
                "topic_id": ObjectId(topic_id),
                "content_type": "slide",
                "status": {"$in": status_filter}
            }
            if render_engine:
                match["render_engine"] = render_engine

            # Base pipeline to compute per-slide flags and generation times
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

            # For pagination of slides list, create a copy of pipeline for slides retrieval
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

            # Aggregation for overall stats (single query)
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

            result = {
                "stats": {
                    "total": total,
                    "slides_with_html": slides_with_html,
                    "slides_with_narrative": slides_with_narrative,
                    "slides_complete": slides_complete,
                    "pending": pending,
                    "completion_percentage": completion_percentage,
                    "average_generation_time_ms": float(avg_gen_time) if avg_gen_time is not None else None,
                    "estimated_time_remaining_ms": estimated_time_remaining_ms
                },
                "slides": slides_list
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

    
    def adapt_content_to_methodology(self, content_id: str, methodology_code: str) -> Tuple[bool, Dict]:
        """Adapta un contenido según una metodología de aprendizaje."""
        try:
            from src.study_plans.services import TopicContentService

            topic_content_service = TopicContentService()
            return topic_content_service.adapt_content_to_methodology(content_id, methodology_code)
        except Exception as e:
            logging.error(f"Error adaptando contenido: {str(e)}")
            return False, {"error": str(e)}

class VirtualContentService(VerificationBaseService):
    """
    Servicio para contenido personalizado por estudiante.
    Unifica virtual_games, virtual_simulations, etc.
    """
    def __init__(self):
        super().__init__(collection_name="virtual_topic_contents")

    def personalize_content(self, virtual_topic_id: str, content_id: str, 
                          student_id: str, cognitive_profile: Dict) -> Tuple[bool, str]:
        """
        Personaliza contenido para un estudiante específico.
        
        Args:
            virtual_topic_id: ID del tema virtual
            content_id: ID del contenido base
            student_id: ID del estudiante
            cognitive_profile: Perfil cognitivo del estudiante
            
        Returns:
            Tuple[bool, str]: (éxito, mensaje/ID)
        """
        try:
            # Obtener contenido base
            content = get_db().topic_contents.find_one({"_id": ObjectId(content_id)})
            if not content:
                return False, "Contenido no encontrado"

            # Generar adaptaciones basadas en perfil cognitivo
            personalization_data = self._generate_personalization(content, cognitive_profile)
            
            # Verificar si ya existe personalización
            existing = self.collection.find_one({
                "virtual_topic_id": ObjectId(virtual_topic_id),
                "content_id": ObjectId(content_id),
                "student_id": ObjectId(student_id)
            })
            
            if existing:
                # Actualizar personalización existente
                result = self.collection.update_one(
                    {"_id": existing["_id"]},
                    {"$set": {
                        "personalization_data": personalization_data,
                        "updated_at": datetime.now()
                    }}
                )
                return True, str(existing["_id"])
            else:
                # Crear nueva personalización
                virtual_content = VirtualTopicContent(
                    virtual_topic_id=virtual_topic_id,
                    content_id=content_id,
                    student_id=student_id,
                    personalization_data=personalization_data
                )
                
                result = self.collection.insert_one(virtual_content.to_dict())
                return True, str(result.inserted_id)
                
        except Exception as e:
            logging.error(f"Error personalizando contenido: {str(e)}")
            return False, f"Error interno: {str(e)}"

    def _generate_personalization(self, content: Dict, cognitive_profile: Dict) -> Dict:
        """
        Genera adaptaciones basadas en perfil cognitivo.
        """
        personalization = {
            "difficulty_adjustment": 0,
            "time_allocation": 1.0,
            "interface_adaptations": {},
            "content_adaptations": {},
            "accessibility_options": {}
        }
        
        # Adaptaciones por tipo de contenido
        content_type = content.get("content_type", "")
        
        # Adaptaciones generales por perfil VAK
        vak_scores = cognitive_profile.get("vak_scores", {})
        
        if vak_scores.get("visual", 0) > 0.7:
            personalization["content_adaptations"]["enhance_visuals"] = True
            personalization["interface_adaptations"]["visual_emphasis"] = True
            
        if vak_scores.get("auditory", 0) > 0.7:
            personalization["content_adaptations"]["add_audio"] = True
            personalization["accessibility_options"]["audio_descriptions"] = True
            
        if vak_scores.get("kinesthetic", 0) > 0.7:
            personalization["content_adaptations"]["increase_interactivity"] = True
            personalization["interface_adaptations"]["tactile_feedback"] = True
        
        # Adaptaciones por dificultades de aprendizaje
        learning_disabilities = cognitive_profile.get("learning_disabilities", {})
        
        if learning_disabilities.get("dyslexia"):
            personalization["accessibility_options"]["high_contrast"] = True
            personalization["accessibility_options"]["dyslexia_font"] = True
            personalization["content_adaptations"]["reduce_text_density"] = True
            
        if learning_disabilities.get("adhd"):
            personalization["interface_adaptations"]["minimize_distractions"] = True
            personalization["content_adaptations"]["shorter_segments"] = True
            personalization["time_allocation"] = 1.5  # Más tiempo
            
        # Adaptaciones específicas por tipo de contenido interactivo
        if content_type in ["game", "simulation", "quiz"]:
            if cognitive_profile.get("attention_span") == "short":
                personalization["content_adaptations"]["break_into_segments"] = True
                personalization["interface_adaptations"]["progress_indicators"] = True
                
        return personalization

    def track_interaction(self, virtual_content_id: str, interaction_data: Dict) -> bool:
        """
        Registra interacción con contenido personalizado.
        """
        try:
            update_data = {
                "interaction_tracking.last_accessed": datetime.now(),
                "interaction_tracking.access_count": {"$inc": 1},
                "updated_at": datetime.now()
            }
            
            # Agregar datos específicos de la interacción
            if interaction_data.get("time_spent"):
                update_data["interaction_tracking.total_time_spent"] = {"$inc": interaction_data["time_spent"]}
                
            if interaction_data.get("completion_percentage"):
                update_data["interaction_tracking.completion_percentage"] = interaction_data["completion_percentage"]
                
            if interaction_data.get("completion_status"):
                update_data["interaction_tracking.completion_status"] = interaction_data["completion_status"]
                
            result = self.collection.update_one(
                {"_id": ObjectId(virtual_content_id)},
                {"$set": update_data}
            )
            
            return result.modified_count > 0
            
        except Exception as e:
            logging.error(f"Error registrando interacción: {str(e)}")
            return False

class ContentResultService(VerificationBaseService):
    """
    Servicio unificado para resultados de contenido interactivo.
    Reemplaza GameResultService, SimulationResultService, QuizResultService.
    """
    def __init__(self):
        super().__init__(collection_name="content_results")

    def record_result(self, result_data: Dict) -> Tuple[bool, str]:
        """
        Registra resultado de interacción con contenido.
        
        Args:
            result_data: Datos del resultado
            
        Returns:
            Tuple[bool, str]: (éxito, mensaje/ID)
        """
        try:
            # Derivar score y métricas desde session_data/learning_metrics
            session_data = result_data.pop("session_data", {}) or {}
            learning_metrics = result_data.pop("learning_metrics", {}) or {}

            if "score" not in result_data:
                score = session_data.get("score")
                if score is None:
                    completion = session_data.get("completion_percentage")
                    if completion is not None:
                        score = completion / 100.0
                result_data["score"] = score if score is not None else 0.0

            metrics = result_data.get("metrics", {})
            metrics.update(session_data)
            metrics.update(learning_metrics)
            result_data["metrics"] = metrics

            # Asegurar que virtual_content_id esté presente si existe información suficiente
            if not result_data.get("virtual_content_id"):
                student_id = result_data.get("student_id")
                content_id = result_data.get("content_id")
                if student_id and content_id:
                    virtual_content = get_db().virtual_topic_contents.find_one({
                        "student_id": ObjectId(student_id),
                        "content_id": ObjectId(content_id)
                    })
                    if virtual_content:
                        result_data["virtual_content_id"] = str(virtual_content["_id"])
                    else:
                        logging.warning(
                            f"No se encontró virtual_content_id para content_id: {content_id}, student_id: {student_id}"
                        )

            # Validar y convertir evaluation_id si está presente
            if result_data.get("evaluation_id"):
                try:
                    ObjectId(result_data["evaluation_id"])  # Validar formato
                except Exception:
                    logging.warning(f"evaluation_id inválido: {result_data['evaluation_id']}")
                    result_data.pop("evaluation_id", None)

            content_result = ContentResult(**result_data)
            result = self.collection.insert_one(content_result.to_dict())

            if result_data.get("virtual_content_id"):
                try:
                    virtual_content_service = VirtualContentService()
                    virtual_content_service.track_interaction(
                        result_data["virtual_content_id"],
                        session_data,
                    )
                except Exception as track_error:
                    logging.warning(
                        f"Error actualizando tracking de contenido virtual: {track_error}"
                    )

            # Enviar feedback automático al sistema RL para aprendizaje granular
            try:
                from src.personalization.services import AdaptivePersonalizationService
                
                # Preparar datos de feedback para el modelo RL
                feedback_data = {
                    "student_id": result_data["student_id"],
                    "content_id": result_data.get("virtual_content_id") or result_data.get("content_id"),
                    "interaction_type": result_data.get("session_type", "content_interaction"),
                    "performance_score": result_data["score"],
                    "engagement_metrics": result_data.get("metrics", {})
                }
                
                # Enviar feedback al sistema RL de forma asíncrona
                personalization_service = AdaptivePersonalizationService()
                success, message = personalization_service.submit_learning_feedback(feedback_data)
                
                if success:
                    logging.info(f"Feedback RL enviado exitosamente para ContentResult {result.inserted_id}")
                else:
                    logging.warning(f"Error enviando feedback RL: {message}")
                    
            except Exception as rl_error:
                logging.warning(f"Error enviando feedback al sistema RL: {str(rl_error)}")

            return True, str(result.inserted_id)
            
        except Exception as e:
            logging.error(f"Error registrando resultado: {str(e)}")
            return False, f"Error interno: {str(e)}"

    def get_student_results(self, student_id: str, virtual_content_id: str = None, content_type: str = None, evaluation_id: str = None) -> List[Dict]:
        """
        Obtiene resultados de un estudiante, filtrados por virtual_content_id como clave principal.
        
        Args:
            student_id: ID del estudiante
            virtual_content_id: ID del contenido virtual (clave principal)
            content_type: Tipo de contenido (opcional, para compatibilidad)
            evaluation_id: ID de evaluación (opcional)
        """
        try:
            query = {"student_id": ObjectId(student_id)}
            
            # Usar virtual_content_id como filtro principal si se proporciona
            if virtual_content_id:
                query["virtual_content_id"] = ObjectId(virtual_content_id)
            elif content_type:
                # Fallback: buscar por tipo de contenido si no hay virtual_content_id
                # Buscar contenidos virtuales del tipo especificado
                virtual_contents = list(get_db().virtual_topic_contents.find({
                    "student_id": ObjectId(student_id),
                    "content_type": content_type
                }))
                
                if virtual_contents:
                    virtual_content_ids = [vc["_id"] for vc in virtual_contents]
                    query["virtual_content_id"] = {"$in": virtual_content_ids}
                else:
                    return []  # No hay contenidos virtuales de este tipo
            
            if evaluation_id:
                query["evaluation_id"] = ObjectId(evaluation_id)
            
            results = list(self.collection.find(query).sort("recorded_at", -1))
            
            # Convertir ObjectIds a strings para JSON
            for result in results:
                result["_id"] = str(result["_id"])
                result["student_id"] = str(result["student_id"])
                if result.get("content_id"):
                    result["content_id"] = str(result["content_id"])
                if result.get("virtual_content_id"):
                    result["virtual_content_id"] = str(result["virtual_content_id"])
                if result.get("evaluation_id"):
                    result["evaluation_id"] = str(result["evaluation_id"])
                
            return results
            
        except Exception as e:
            logging.error(f"Error obteniendo resultados del estudiante: {str(e)}")
            return []


class ContentPersonalizationService:
    """Procesa contenido para identificar marcadores de personalización"""

    marker_pattern = re.compile(r"{{(.*?)}}")

    @classmethod
    def extract_markers(cls, text: str) -> Dict:
        segments = []
        last_idx = 0
        for match in cls.marker_pattern.finditer(text):
            start, end = match.span()
            if start > last_idx:
                segments.append({"type": "static", "content": text[last_idx:start]})
            marker_id = match.group(1)
            segments.append({"type": "marker", "id": marker_id})
            last_idx = end
        if last_idx < len(text):
            segments.append({"type": "static", "content": text[last_idx:]})
        return {"segments": segments}
    
    @classmethod
    def apply_markers(cls, content: Dict, student: Dict) -> Dict:
        """
        Aplica marcadores de personalización reemplazando placeholders con datos del estudiante.
        
        Args:
            content: Contenido con posibles marcadores {{student.campo}}
            student: Datos del estudiante para reemplazar
            
        Returns:
            Dict: Contenido con marcadores reemplazados
        """
        try:
            # Crear una copia del contenido para no modificar el original
            personalized_content = content.copy()
            
            # Función auxiliar para reemplazar marcadores en texto
            def replace_markers_in_text(text: str) -> str:
                if not isinstance(text, str):
                    return text
                    
                def replace_marker(match):
                    marker = match.group(1).strip()
                    
                    # Soportar notación de punto para acceder a campos anidados
                    if marker.startswith('student.'):
                        field_path = marker[8:]  # Remover 'student.'
                        value = cls._get_nested_value(student, field_path)
                        return str(value) if value is not None else f"{{{{{marker}}}}}"
                    
                    # Marcadores directos del estudiante
                    if marker in student:
                        return str(student[marker])
                    
                    # Si no se encuentra el marcador, mantenerlo sin cambios
                    return f"{{{{{marker}}}}}"
                
                return cls.marker_pattern.sub(replace_marker, text)
            
            # Función auxiliar para procesar recursivamente estructuras de datos
            def process_data_structure(data):
                if isinstance(data, str):
                    return replace_markers_in_text(data)
                elif isinstance(data, dict):
                    return {key: process_data_structure(value) for key, value in data.items()}
                elif isinstance(data, list):
                    return [process_data_structure(item) for item in data]
                else:
                    return data
            
            # Aplicar reemplazo a todos los campos del contenido
            for key, value in personalized_content.items():
                personalized_content[key] = process_data_structure(value)
            
            return personalized_content
            
        except Exception as e:
            logging.error(f"Error aplicando marcadores de personalización: {str(e)}")
            return content  # Retornar contenido original en caso de error
    
    @classmethod
    def _get_nested_value(cls, data: Dict, field_path: str):
        """
        Obtiene un valor anidado usando notación de punto (ej: 'profile.name')
        """
        try:
            keys = field_path.split('.')
            value = data
            for key in keys:
                if isinstance(value, dict) and key in value:
                    value = value[key]
                else:
                    return None
            return value
        except Exception:
            return None