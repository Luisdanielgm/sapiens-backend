from typing import Tuple, List, Dict, Optional, Any
from bson import ObjectId
from datetime import datetime, timedelta
import json
import logging
import threading
from pymongo import ReturnDocument
from pymongo.errors import DuplicateKeyError
from concurrent.futures import ThreadPoolExecutor

from src.shared.database import get_db
from src.shared.constants import STATUS
from src.shared.standardization import VerificationBaseService, ErrorCodes
from src.shared.exceptions import AppException
from src.shared.utils import normalize_objectid
from src.shared.cascade_deletion_service import CascadeDeletionService
from .models import ContentType, TopicContent, VirtualTopicContent, ContentResult, ContentTypes, DeprecatedContentTypes, LearningMethodologyTypes
from .slide_style_service import SlideStyleService
import re
from src.ai_monitoring.services import AIMonitoringService
from .structured_sequence_service import StructuredSequenceService
from .template_recommendation_service import TemplateRecommendationService
from .embedded_content_service import EmbeddedContentService
from .content_personalization_service import ContentPersonalizationService
from src.personalization.services import AdaptivePersonalizationService
import bleach

# Constants for policy validation error messages
FORBIDDEN_KEYS_ERROR_MSG = "Los campos 'provider' y 'model' no están permitidos en payloads de contenido. El sistema gestiona automáticamente la selección de proveedores."
FORBIDDEN_KEYS_ERROR_MSG_SHORT = "Los campos 'provider' y 'model' no están permitidos en payloads de contenido."
SLIDE_PLAN_TYPE_ERROR_MSG = "El campo 'slide_plan' debe ser una cadena de texto (Markdown/texto plano), no un objeto JSON o array."

# Allowlist de scripts externos seguros (framework visual de slides)
SLIDE_SCRIPT_WHITELIST = [
    "https://cdn.jsdelivr.net/gh/Luisdanielgm/framework_slide@c126feeade8624922fe87119bddaac4828061cd9/sapiens.js",
    "https://cdn.jsdelivr.net/gh/Luisdanielgm/framework_slide@main/sapiens.js"
]

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
        if not code:
            return None

        normalized_code = code.strip().lower()

        # Soportar tipos internos no registrados en la colección
        if normalized_code == "slide_template":
            return {
                "code": "slide_template",
                "name": "Slide Template",
                "description": "Plantilla base reutilizable para renderizar diapositivas",
                "status": "active",
                "subcategory": "template",
                "builtin": True
            }

        content_type = self.collection.find_one({"code": normalized_code, "status": "active"})
        if content_type:
            content_type["_id"] = str(content_type["_id"])
        return content_type

# Default status mapping by content type
DEFAULT_STATUS_BY_TYPE = {
    "slide": ["draft", "active", "published", "skeleton", "html_ready", "narrative_ready"],
    "slide_template": ["draft", "active", "template"],
    "default": ["draft", "active", "published"]
}


class ContentService(VerificationBaseService):
    """
    Servicio unificado para gestionar TODO tipo de contenido.
    Reemplaza GameService, SimulationService, QuizService, etc.
    """
    _CONTENT_TYPE_ALIASES = {
        'document': 'documents',
        'documents': 'documents',
        'doc': 'documents',
        'docx': 'documents',
        'pdf': 'documents',
        'video_content': 'video',
        'image_content': 'image',
        'audio_content': 'audio',
        'external_link': 'link',
        'link': 'link',
        'slide-template': 'slide_template'
    }

    def _normalize_content_type(self, content_type: Optional[str]) -> Optional[str]:
        if not content_type:
            return content_type
        normalized = content_type.strip().lower()
        return self._CONTENT_TYPE_ALIASES.get(normalized, normalized)

    def _apply_content_type_alias(self, payload: Dict[str, Any]) -> Optional[str]:
        raw_type = payload.get('content_type')
        normalized = self._normalize_content_type(raw_type)
        if normalized and raw_type != normalized:
            payload['content_type'] = normalized
        return normalized

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
        self._eval_executor = ThreadPoolExecutor(max_workers=4, thread_name_prefix="content_eval")

    def _normalize_content_field(self, doc: Dict[str, Any]) -> Dict[str, Any]:
        """
        Normaliza el campo 'content' de un documento para asegurar que sea un dict.
        Previene errores cuando el campo contiene datos no migrados o corruptos.
        """
        content = doc.get("content")
        if isinstance(content, dict):
            return content
        else:
            # Si content no es dict (None, str, list, etc.), usar dict vacío
            return {}

    def check_topic_exists(self, topic_id: str) -> bool:
        """Verifica si un tema existe."""
        try:
            topic = self.db.topics.find_one({"_id": ObjectId(topic_id)})
            return topic is not None
        except Exception:
            return False

    def validate_slide_html_content(
        self,
        html_content: str,
        allow_full_document: bool = False,
        allow_iframe: bool = False,
    ) -> Tuple[bool, str]:
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

            # Tamaño razonable para una slide individual (150 KB = 153,600 bytes)
            max_bytes = (2 * 1024 * 1024) if allow_full_document else (150 * 1024)  # 150KB or 2MB
            current_bytes = len(html_content.encode('utf-8'))
            if current_bytes > max_bytes:
                logging.warning(f"validate_slide_html_content: HTML demasiado largo ({current_bytes} bytes > {max_bytes} bytes)")
                return False, f"HTML excede el tamaño máximo permitido de 150 KB ({current_bytes:,} bytes de {max_bytes:,} bytes permitidos)"

            low = raw.lower()

            # Prohibir tags peligrosos explícitos
            base_dangerous = ["object", "embed"]
            if not allow_iframe:
                base_dangerous.append("iframe")

            dangerous_tags = base_dangerous if allow_full_document else base_dangerous + ["link", "meta", "base"]
            for tag in dangerous_tags:
                if f"<{tag}" in low or f"</{tag}" in low:
                    logging.warning(f"validate_slide_html_content: encontrado tag prohibido <{tag}>")
                    return False, f"HTML contiene etiqueta <{tag}> prohibida"

            # Permitir solo scripts externos expresamente autorizados
            if "<script" in low:
                script_tags = re.findall(r"<script[^>]*>", raw, flags=re.IGNORECASE)
                if not script_tags:
                    logging.warning("validate_slide_html_content: <script> sin tag de apertura reconocido")
                    return False, "HTML contiene etiqueta <script> prohibida"
                for tag in script_tags:
                    src_match = re.search(r'src\s*=\s*"([^"]+)"|src\s*=\s*\'([^\']+)\'', tag, flags=re.IGNORECASE)
                    src_value = None
                    if src_match:
                        src_value = src_match.group(1) or src_match.group(2)
                    if not src_value:
                        logging.warning("validate_slide_html_content: <script> sin atributo src")
                        return False, "HTML contiene etiqueta <script> sin src (prohibido)"

                    normalized_src = src_value.strip()
                    normalized_src_base = normalized_src.split("?")[0].lower()
                    if not any(normalized_src_base.startswith(allowed.lower()) for allowed in SLIDE_SCRIPT_WHITELIST):
                        logging.warning(f"validate_slide_html_content: script src no permitido {normalized_src}")
                        return False, "HTML contiene etiqueta <script> con src no autorizado"

            # Prohibir eventos inline (on*) salvo cuando se permite documento completo
            if not allow_full_document:
                if re.search(r'on[a-z]+\s*=', low):
                    logging.warning("validate_slide_html_content: encontrado atributo de evento inline (on*)")
                    return False, "HTML contiene atributos de evento inline (on*) que estan prohibidos"
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

            # Pre filtrar scripts permitidos y eliminar el resto
            def _sanitize_script_tag(match):
                attrs = match.group(1) or ""
                src_match = re.search(r'src\s*=\s*"([^"]+)"|src\s*=\s*\'([^\']+)\'', attrs, flags=re.IGNORECASE)
                if not src_match:
                    return ""  # eliminar scripts sin src
                src_value = (src_match.group(1) or src_match.group(2) or "").strip()
                normalized_src_base = src_value.split("?")[0].lower()
                if any(normalized_src_base.startswith(allowed.lower()) for allowed in SLIDE_SCRIPT_WHITELIST):
                    # Forzamos script limpio y sin contenido inline
                    return f'<script src="{src_value}"></script>'
                return ""

            filtered_html = re.sub(r'<script([^>]*)>(.*?)</script>', _sanitize_script_tag, html, flags=re.IGNORECASE | re.DOTALL)
            filtered_html = re.sub(r'<script([^>]*)/>', _sanitize_script_tag, filtered_html, flags=re.IGNORECASE)

            allowed_tags = [
                'div', 'p', 'span', 'h1', 'h2', 'h3', 'h4', 'h5', 'h6',
                'ul', 'ol', 'li', 'a', 'img', 'strong', 'em', 'i', 'b',
                'br', 'hr', 'blockquote', 'code', 'pre', 'table', 'tr', 'td',
                'th', 'thead', 'tbody', 'caption', 'script'
            ]
            allowed_attrs = {
                '*': ['class', 'style'],
                'a': ['href', 'title'],
                'img': ['src', 'alt', 'title'],
                'table': ['border', 'cellpadding', 'cellspacing'],
                'script': ['src'],
            }
            allowed_protocols = ['http', 'https', 'mailto']

            cleaned = bleach.clean(
                filtered_html,
                tags=allowed_tags,
                attributes=allowed_attrs,
                protocols=allowed_protocols,
                strip=True  # Remover tags no permitidos en lugar de escapar
            )
            return cleaned
        except Exception as e:
            logging.error(f"Error sanitizando HTML: {str(e)}")
            return ""  # Retornar vacío en caso de error para evitar inyección

    def _is_path_whitelisted_for_forbidden_keys(self, path: str) -> bool:
        """
        Determina si una ruta está en la lista blanca donde provider/model son permitidos.
        Estas rutas corresponden a datos históricos o plantillas donde estos campos son legítimos.

        Args:
            path: Ruta actual en formato "a.b.c" o "a[0].b"

        Returns:
            bool: True si la ruta está en lista blanca (permitida), False si debe validarse
        """
        # Lista blanca de rutas donde provider/model son permitidos
        # Normalizar la ruta quitando índices de array para comparación
        # Usar regex para reemplazar cualquier índice de array [número] con un punto
        normalized_path = re.sub(r'\[\d+\]', '.', path)
        # Eliminar puntos consecutivos que puedan resultar de la normalización
        normalized_path = re.sub(r'\.+', '.', normalized_path)
        # Eliminar punto final si existe (excepto si es el único carácter)
        if normalized_path.endswith('.') and len(normalized_path) > 1:
            normalized_path = normalized_path.rstrip('.')

        whitelist_patterns = [
            # No whitelist patterns needed for template_snapshot as it has been removed
        ]

        return any(normalized_path.startswith(pattern) for pattern in whitelist_patterns)

    def _is_path_allowed_for_detection(self, path: str) -> bool:
        """
        Determina si una ruta debe ser validada para detección de provider/model.

        Args:
            path: Ruta actual en formato "a.b.c" o "a[0].b"

        Returns:
            bool: Siempre retorna True para cualquier ruta
        """
        return True

    def _detect_forbidden_keys_recursive(self, data: Any, forbidden_fields: List[str], current_path: str = "", context: str = "", user_id: Optional[str] = None, topic_id: Optional[str] = None) -> Tuple[bool, str]:
        """
        Función auxiliar recursiva que recorre dicts y listas para detectar claves prohibidas.
        Aplica restricciones de ruta específicas para evitar falsos positivos.
        Registra el context y ruta de clave en el log para auditoría.

        RUTAS INCLUIDAS PARA DETECCIÓN:
        - Raíz (sin prefijo): provider, model
        - content.*: provider, model (excepto en rutas excluidas específicas)
        - contents[*].*: provider, model (para bulk payloads)
        - slides[*].*: provider, model (para bulk slides)

        RUTAS EXCLUIDAS (lista blanca donde no se aplica detección):
        - Ninguna actualmente (template_snapshot ha sido eliminado)

        Args:
            data: Estructura de datos a analizar (dict, list, o cualquier tipo)
            forbidden_fields: Lista de campos prohibidos a buscar
            current_path: Ruta actual dentro de la estructura (para logging)
            context: Contexto de la operación para auditoría
            user_id: ID del usuario para auditoría
            topic_id: ID del topic para auditoría

        Returns:
            Tuple[bool, str]: (True, "") si no se encontraron claves prohibidas,
                             (False, "Campo prohibido encontrado en ruta: X") si se encontraron
        """
        try:
            if isinstance(data, dict):
                for key, value in data.items():
                    # Construir nueva ruta
                    new_path = f"{current_path}.{key}" if current_path else key

                    # Verificar si la clave actual está prohibida Y está en una ruta permitida
                    if key in forbidden_fields:
                        # Verificar si la ruta actual está en la lista blanca (excluida de detección)
                        if self._is_path_whitelisted_for_forbidden_keys(new_path):
                            # Está en lista blanca, permitir y continuar recursión
                            is_valid, error_msg = self._detect_forbidden_keys_recursive(
                                value, forbidden_fields, new_path, context, user_id, topic_id
                            )
                            if not is_valid:
                                return False, error_msg
                            continue

                        # Cualquier aparición de clave prohibida fuera de lista blanca dispara violación
                        full_path = new_path
                        logging.warning(f"POLICY_VIOLATION: Intento de enviar campo prohibido '{key}' en ruta '{full_path}' en {context}. user_id={user_id}, topic_id={topic_id}, timestamp={datetime.now().isoformat()}")
                        return False, f"Campo prohibido '{key}' encontrado en ruta: {full_path}"

                    # Recursión para valores anidados
                    is_valid, error_msg = self._detect_forbidden_keys_recursive(
                        value, forbidden_fields, new_path, context, user_id, topic_id
                    )
                    if not is_valid:
                        return False, error_msg

            elif isinstance(data, list):
                # Para listas, iterar sobre cada elemento con índice en la ruta
                for index, item in enumerate(data):
                    new_path = f"{current_path}[{index}]" if current_path else f"[{index}]"

                    # Recursión para elementos de la lista
                    is_valid, error_msg = self._detect_forbidden_keys_recursive(
                        item, forbidden_fields, new_path, context, user_id, topic_id
                    )
                    if not is_valid:
                        return False, error_msg

            # Para otros tipos (str, int, etc.), no hacer nada - no pueden contener claves prohibidas

            return True, ""

        except Exception as e:
            logging.error(f"Error en detección recursiva de claves prohibidas en ruta '{current_path}' en {context}: {str(e)}")
            return False, f"Error interno validando estructura anidada en ruta {current_path}: {str(e)}"

    def _validate_content_payload_policy(self, payload_data: Dict, context: str, user_id: Optional[str] = None, topic_id: Optional[str] = None) -> Tuple[bool, str]:
        """
        Valida que los payloads de contenido cumplan con las políticas establecidas.

        Políticas implementadas:
        1. Detección restringida de campos prohibidos ('provider', 'model')
           - Rutas permitidas: raíz, content.*, contents[*].*, slides[*].*
           - Rutas excluidas (lista blanca): Ninguna actualmente
        2. Validación de tipos de datos específicos (slide_plan debe ser string)
        3. Validaciones adicionales para payloads bulk

        Esta implementación evita falsos positivos en datos históricos mientras
        mantiene la seguridad en rutas críticas del payload.
        """
        try:
            # Definir campos prohibidos
            forbidden_fields = ['provider', 'model']

            # Validación recursiva con restricciones de ruta para detectar campos prohibidos solo en ubicaciones específicas
            is_recursive_valid, recursive_error = self._detect_forbidden_keys_recursive(
                payload_data, forbidden_fields, "", context, user_id, topic_id
            )
            if not is_recursive_valid:
                return False, f"Violación de política: {recursive_error}. El sistema gestiona automáticamente la selección de proveedores. Los campos 'provider'/'model' no están permitidos en payloads de contenido."

            # Validación específica a nivel raíz (solo slide_plan)
            # Las validaciones de provider/model ya están cubiertas por _detect_forbidden_keys_recursive

            # Validar que 'content' sea un objeto si está presente
            content_field = payload_data.get('content')
            if content_field is not None and not isinstance(content_field, dict):
                logging.warning(f"POLICY_VIOLATION: 'content' debe ser un objeto JSON, recibido {type(content_field).__name__} en {context}. user_id={user_id}, topic_id={topic_id}")
                return False, "El campo 'content' debe ser un objeto con subcampos (p. ej., content.full_text, content.slide_plan, content.content_html, content.narrative_text)."

            # Validar tipo de 'slide_plan'
            slide_plan = (payload_data.get('content') or {}).get('slide_plan') if isinstance(payload_data.get('content'), dict) else payload_data.get('slide_plan')
            if slide_plan is not None:
                if not isinstance(slide_plan, str):
                    logging.warning(f"POLICY_VIOLATION: slide_plan debe ser string, recibido {type(slide_plan).__name__} en {context}. user_id={user_id}, topic_id={topic_id}")
                    return False, SLIDE_PLAN_TYPE_ERROR_MSG
                # Validar que slide_plan no sea una cadena vacía después de strip()
                if slide_plan.strip() == "":
                    logging.warning(f"POLICY_VIOLATION: slide_plan no puede ser una cadena vacía en {context}. user_id={user_id}, topic_id={topic_id}")
                    return False, "El campo 'slide_plan' no puede ser una cadena vacía"

            # Validar tipo de slide_plan en payloads bulk
            if 'contents' in payload_data:
                for item in payload_data['contents']:
                    if not isinstance(item, dict):
                        continue
                    # Validar slide_plan en cada item (provider/model ya validados recursivamente)
                    slide_plan_item = item.get('content', {}).get('slide_plan') or item.get('slide_plan')
                    if slide_plan_item is not None:
                        if not isinstance(slide_plan_item, str):
                            logging.warning(f"POLICY_VIOLATION: slide_plan debe ser string en bulk item, recibido {type(slide_plan_item).__name__} en {context}. user_id={user_id}, topic_id={topic_id}")
                            return False, SLIDE_PLAN_TYPE_ERROR_MSG
                        # Validar que slide_plan no sea una cadena vacía después de strip()
                        if slide_plan_item.strip() == "":
                            logging.warning(f"POLICY_VIOLATION: slide_plan no puede ser una cadena vacía en bulk item en {context}. user_id={user_id}, topic_id={topic_id}")
                            return False, "El campo 'slide_plan' no puede ser una cadena vacía"

            if 'slides' in payload_data:
                for item in payload_data['slides']:
                    if not isinstance(item, dict):
                        continue
                    # Validar slide_plan en cada item (provider/model ya validados recursivamente)
                    slide_plan_item = item.get('content', {}).get('slide_plan') or item.get('slide_plan')
                    if slide_plan_item is not None:
                        if not isinstance(slide_plan_item, str):
                            logging.warning(f"POLICY_VIOLATION: slide_plan debe ser string en bulk slides item, recibido {type(slide_plan_item).__name__} en {context}. user_id={user_id}, topic_id={topic_id}")
                            return False, SLIDE_PLAN_TYPE_ERROR_MSG
                        # Validar que slide_plan no sea una cadena vacía después de strip()
                        if slide_plan_item.strip() == "":
                            logging.warning(f"POLICY_VIOLATION: slide_plan no puede ser una cadena vacía en bulk slides item en {context}. user_id={user_id}, topic_id={topic_id}")
                            return False, "El campo 'slide_plan' no puede ser una cadena vacía"

            # Validar tipo de slide_plan en content
            content = payload_data.get('content', {})
            if isinstance(content, dict):
                # Validar slide_plan en content (provider/model ya validados recursivamente)
                slide_plan_content = content.get('slide_plan')
                if slide_plan_content is not None:
                    if not isinstance(slide_plan_content, str):
                        logging.warning(f"POLICY_VIOLATION: slide_plan debe ser string en content, recibido {type(slide_plan_content).__name__} en {context}. user_id={user_id}, topic_id={topic_id}")
                        return False, SLIDE_PLAN_TYPE_ERROR_MSG
                    # Validar que slide_plan no sea una cadena vacía después de strip()
                    if slide_plan_content.strip() == "":
                        logging.warning(f"POLICY_VIOLATION: slide_plan no puede ser una cadena vacía en content en {context}. user_id={user_id}, topic_id={topic_id}")
                        return False, "El campo 'slide_plan' no puede ser una cadena vacía"

            # Validar tipo de slide_plan en content_data.slides
            content_data = payload_data.get('content_data', {})
            if isinstance(content_data, dict):
                slides = content_data.get('slides', [])
                if isinstance(slides, list):
                    for slide in slides:
                        if isinstance(slide, dict):
                            # Validar slide_plan en cada slide (provider/model ya validados recursivamente)
                            slide_plan_nested = slide.get('slide_plan')
                            if slide_plan_nested is not None:
                                if not isinstance(slide_plan_nested, str):
                                    logging.warning(f"POLICY_VIOLATION: slide_plan debe ser string en content_data.slides, recibido {type(slide_plan_nested).__name__} en {context}. user_id={user_id}, topic_id={topic_id}")
                                    return False, SLIDE_PLAN_TYPE_ERROR_MSG
                                # Validar que slide_plan no sea una cadena vacía después de strip()
                                if slide_plan_nested.strip() == "":
                                    logging.warning(f"POLICY_VIOLATION: slide_plan no puede ser una cadena vacía en content_data.slides en {context}. user_id={user_id}, topic_id={topic_id}")
                                    return False, "El campo 'slide_plan' no puede ser una cadena vacía"

            return True, ""
        except Exception as e:
            logging.error(f"Error validando política de payload en {context}: {str(e)}")
            return False, f"Error interno validando política: {str(e)}"

    def _normalize_baseline_mix(self, value) -> Optional[Dict]:
        if not isinstance(value, dict):
            return None
        normalized: Dict = {}
        for key, raw in value.items():
            if isinstance(raw, (int, float)):
                normalized[key] = raw
            elif isinstance(raw, str):
                try:
                    normalized[key] = float(raw)
                except ValueError:
                    continue
        return normalized or None

    def _resolve_baseline_mix(self, payload: Optional[Dict]) -> Optional[Dict]:
        if not isinstance(payload, dict):
            return None

        def from_source(value) -> Optional[Dict]:
            return self._normalize_baseline_mix(value)

        for candidate in (
            payload.get("baseline_mix"),
            payload.get("learning_mix"),
        ):
            normalized = from_source(candidate)
            if normalized:
                return normalized

        content_field = payload.get("content")
        if isinstance(content_field, dict):
            normalized = from_source(content_field.get("baseline_mix"))
            if normalized:
                return normalized

        interactive_data = payload.get("interactive_data")
        if isinstance(interactive_data, dict):
            metadata = interactive_data.get("metadata")
            if isinstance(metadata, dict):
                normalized = from_source(metadata.get("baseline_mix"))
                if normalized:
                    return normalized

        personalization = payload.get("personalization_data")
        if isinstance(personalization, dict):
            normalized = from_source(personalization.get("baseline_mix"))
            if normalized:
                return normalized

        markers = payload.get("personalization_markers")
        if isinstance(markers, dict):
            template_metadata = markers.get("template_metadata")
            if isinstance(template_metadata, dict):
                normalized = from_source(template_metadata.get("baseline_mix"))
                if normalized:
                    return normalized

        return None

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
            content_type = self._apply_content_type_alias(content_data)

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

            # Validar políticas de payload (campos prohibidos, tipos)
            user_id = content_data.get('creator_id')
            topic_id = content_data.get('topic_id')
            valid_policy, policy_msg = self._validate_content_payload_policy(
                content_data,
                context='create_content',
                user_id=user_id,
                topic_id=topic_id
            )
            if not valid_policy:
                return False, policy_msg

            # Validar que topic_id exista y sea válido para crear quizzes
            if content_type == "quiz":
                if not topic_id:
                    return False, "El campo 'topic_id' es requerido para crear un quiz"
                if not ObjectId.is_valid(topic_id):
                    return False, "El campo 'topic_id' debe ser un ObjectId válido para crear un quiz"

            # Para quiz, necesitaremos manejar la transacción más tarde después de crear el objeto content
            # topic_id_obj se inicializará en la sección específica para quiz
            topic_id_obj = ObjectId(topic_id) if topic_id else None

            # Validaciones específicas para diapositivas
            if content_type == "slide":

                # Extraer campos de slide desde content_data['content'] en lugar de raíz
                slide_fields = (content_data.get('content') or {})



            # Extraer campos de slide desde content_data['content'] para todos los tipos de contenido
            # (solo se usará para slides, pero se define aquí para disponibilidad general)
            slide_fields = (content_data.get('content') or {})

            # Validaciones específicas para diapositivas
            if content_type == "slide":
                # Validar nuevos campos de diapositiva si se proporcionan
                content_html = slide_fields.get("content_html")
                narrative_text = slide_fields.get("narrative_text")
                full_text = slide_fields.get("full_text")
                slide_plan = slide_fields.get("slide_plan")


                # Backward compatibility: si no existen en content, intentar raíz temporalmente
                deprecated_fields_used = []
                if content_html is None:
                    content_html = content_data.get("content_html")
                    if content_html is not None:
                        deprecated_fields_used.append("content_html")
                if narrative_text is None:
                    narrative_text = content_data.get("narrative_text")
                    if narrative_text is not None:
                        deprecated_fields_used.append("narrative_text")
                if full_text is None:
                    full_text = content_data.get("full_text")
                    if full_text is not None:
                        deprecated_fields_used.append("full_text")
                if slide_plan is None:
                    slide_plan = content_data.get("slide_plan")
                    if slide_plan is not None:
                        deprecated_fields_used.append("slide_plan")


                # Log warnings for deprecated root field usage
                for field in deprecated_fields_used:
                    logging.warning(
                        f"create_content: Uso de campo raíz '{field}' está deprecado. "
                        f"Migre a usar content.{field} dentro del objeto content. "
                        f"Topic ID: {topic_id}, Content type: {content_type}"
                    )

                # NOTA: Para mantener compatibilidad con la API existente (Tuple[bool, str]),
                # no se puede agregar un flag "deprecated_fields_used" en la respuesta.
                # Los clientes deben monitorear los logs para detectar uso de campos deprecados
                # y planificar la migración a la estructura content.{field}

                if content_html is not None:
                    valid, msg = self.validate_slide_html_content(content_html)
                    if not valid:
                        return False, f"content_html inválido: {msg}"

                if narrative_text is not None and not isinstance(narrative_text, str):
                    return False, "narrative_text debe ser una cadena de texto si se proporciona"

                if full_text is not None and not isinstance(full_text, str):
                    return False, "full_text debe ser una cadena de texto si se proporciona"

                if slide_plan is not None:
                    if not isinstance(slide_plan, str):
                        return False, SLIDE_PLAN_TYPE_ERROR_MSG

            # Crear contenido explícitamente para mapear campos
            # Convertir content a string si es dict para el extractor de marcadores
            content_for_markers = content_data.get("content", "")
            if isinstance(content_for_markers, dict):
                content_for_markers = json.dumps(content_for_markers, ensure_ascii=False)
            markers = ContentPersonalizationService.extract_markers(
                content_for_markers or json.dumps(content_data.get("interactive_data", {}))
            )

            baseline_mix = self._resolve_baseline_mix(content_data)

            # Determinar estado inicial para diapositivas en función de los campos provistos
            # SOLO si el cliente no proporcionó un status explícito, salvo que el caso sea skeleton
            initial_status = content_data.get("status", "draft")
            if content_type == "slide":
                # Derivar status automáticamente usando slide_fields
                ch = slide_fields.get("content_html")
                nt = slide_fields.get("narrative_text")
                ft = slide_fields.get("full_text")

                # Backward compatibility: si no existen en slide_fields, intentar raíz temporalmente
                if ch is None:
                    ch = content_data.get("content_html")
                if nt is None:
                    nt = content_data.get("narrative_text")
                if ft is None:
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

            # Prepare kwargs for slide fields
            kwargs = {}
            if content_type == "slide":
                # Usar slide_fields con backward compatibility
                full_text = slide_fields.get("full_text")
                content_html = slide_fields.get("content_html")
                narrative_text = slide_fields.get("narrative_text")
                slide_plan = slide_fields.get("slide_plan")

                # Backward compatibility: si no existen en slide_fields, intentar raíz temporalmente
                if full_text is None:
                    full_text = content_data.get("full_text")
                if content_html is None:
                    content_html = content_data.get("content_html")
                if narrative_text is None:
                    narrative_text = content_data.get("narrative_text")
                if slide_plan is None:
                    slide_plan = content_data.get("slide_plan")


                # Agregar a kwargs si no son None
                if full_text is not None:
                    kwargs["full_text"] = full_text
                if content_html is not None:
                    kwargs["content_html"] = content_html
                if narrative_text is not None:
                    kwargs["narrative_text"] = narrative_text
                if slide_plan is not None:
                    kwargs["slide_plan"] = slide_plan


            content = TopicContent(
                topic_id=topic_id,
                content=content_data.get("content", ""),
                content_type=content_type,
                interactive_data=content_data.get("interactive_data"),
                learning_methodologies=content_data.get("learning_methodologies"),
                adaptation_options=content_data.get("metadata"), # Mapeo clave
                resources=content_data.get("resources"),
                web_resources=content_data.get("web_resources"),
                generation_prompt=content_data.get("generation_prompt"),
                ai_credits=content_data.get("ai_credits", True),
                personalization_markers=markers,
                learning_mix=content_data.get("learning_mix"),
                baseline_mix=baseline_mix,
                status=initial_status,
                order=content_data.get("order"),
                parent_content_id=content_data.get("parent_content_id"),
                **kwargs
            )

            # Para quiz, usar transacción para garantizar atomicidad en delete+insert
            if content_type == "quiz" and topic_id_obj:
                # Iniciar transacción para operación atómica
                with self.db.client.start_session() as session:
                    with session.start_transaction():
                        try:
                            # Eliminar todos los quizzes existentes para este topic dentro de la transacción
                            delete_result = self.collection.delete_many(
                                {
                                    "topic_id": topic_id_obj,
                                    "content_type": "quiz"
                                },
                                session=session
                            )

                            if delete_result.deleted_count > 0:
                                logging.warning(
                                    f"create_content: Eliminados {delete_result.deleted_count} quizzes previos para topic {topic_id} en transacción."
                                )

                            # Insertar el nuevo quiz dentro de la misma transacción
                            result = self.collection.insert_one(content.to_dict(), session=session)
                            content_id = str(result.inserted_id)

                            logging.info(
                                f"create_content: Nuevo quiz creado exitosamente para topic {topic_id} con id {content_id} en transacción. "
                                f"Todos los quizzes previos fueron eliminados atómicamente."
                            )

                            # La transacción se confirma automáticamente al salir del bloque with

                        except DuplicateKeyError:
                            # En caso de condición de carrera, reintentar o retornar error consistente
                            logging.warning(f"create_content: Detección de condición de carrera al crear quiz para topic {topic_id}")
                            return False, "No se puede crear el quiz: ya existe un quiz para este tema. Por favor, inténtelo nuevamente."

                        except Exception as e:
                            # La transacción se revertirá automáticamente
                            logging.error(f"create_content: Error en transacción de quiz para topic {topic_id}: {str(e)}")
                            return False, f"Error al crear quiz: {str(e)}"
            else:
                # Para otros tipos de contenido, usar inserción normal
                result = self.collection.insert_one(content.to_dict())
                content_id = str(result.inserted_id)

                # Logging específico para creación de diapositivas con nuevos campos
                if content_type == "slide":
                    # Check both slide_fields and root for backward compatibility
                    has_html = 'content_html' in slide_fields or 'content_html' in content_data
                    has_narrative = 'narrative_text' in slide_fields or 'narrative_text' in content_data
                    logging.info(f"Slide creado para topic {topic_id} con id {content_id}. status={initial_status}, has_html={has_html}, has_narrative={has_narrative}")

            # Actualizar métricas del tipo de contenido
            # Para quiz, siempre incrementar usage_count ya que siempre es una inserción nueva
            # Para otros tipos, siempre incrementar
            should_increment_usage = True

            if should_increment_usage:
                self.content_type_service.collection.update_one(
                    {"code": content_type},
                    {"$inc": {"usage_count": 1}}
                )

            return True, content_id

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
                    return False, {'message': 'Tipo en uso; no se permite creación por error de validación'}
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

    def check_existing_skeletons(self, topic_id: str, orders: List[int]) -> Dict[str, Any]:
        """
        Verifica si ya existen skeletons con el mismo topic_id y order.

        Args:
            topic_id: ID del tema a verificar
            orders: Lista de órdenes a verificar

        Returns:
            Dict con información sobre duplicados encontrados
        """
        try:
            existing_skeletons = list(self.collection.find({
                "topic_id": ObjectId(topic_id),
                "order": {"$in": orders},
                "status": "skeleton"
            }, {"_id": 1, "order": 1}))

            if existing_skeletons:
                existing_orders = [doc["order"] for doc in existing_skeletons]
                existing_ids = [str(doc["_id"]) for doc in existing_skeletons]
                return {
                    "has_duplicates": True,
                    "existing_orders": existing_orders,
                    "existing_ids": existing_ids,
                    "count": len(existing_skeletons)
                }

            return {
                "has_duplicates": False,
                "existing_orders": [],
                "existing_ids": [],
                "count": 0
            }
        except Exception as e:
            logging.error(f"Error verificando skeletons existentes: {e}")
            return {
                "has_duplicates": False,
                "existing_orders": [],
                "existing_ids": [],
                "count": 0,
                "error": str(e)
            }

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
            quiz_deleted_topics = set()  # Local variable to track quiz deletions in this batch (thread-safe)

            # IMPLEMENTACIÓN "ÚLTIMO GANA": Preprocesar quizzes para mantener solo el último por topic_id
            # Esto evita conflictos con el índice único idx_unique_quiz_per_topic y asegura el comportamiento documentado
            last_quiz_index_by_topic = {}
            filtered_contents_data = []
            quiz_replacements = {}  # Para logging de reemplazos intra-batch

            for i, content_data in enumerate(contents_data):
                if content_data.get("content_type") == "quiz":
                    topic_id = content_data.get("topic_id")
                    if topic_id:
                        # Si ya vimos un quiz para este topic, reemplazamos con el último
                        if topic_id in last_quiz_index_by_topic:
                            previous_index = last_quiz_index_by_topic[topic_id]
                            quiz_replacements[topic_id] = {
                                "previous_index": previous_index + 1,
                                "new_index": i + 1,
                                "previous_item": contents_data[previous_index],
                                "new_item": content_data
                            }
                            logging.info(
                                f"create_bulk_content: Reemplazando quiz en batch para topic_id '{topic_id}'. "
                                f"Elemento {previous_index + 1} será reemplazado por elemento {i + 1} (comportamiento 'último gana')."
                            )

                        # Guardar el índice del último quiz para este topic
                        last_quiz_index_by_topic[topic_id] = i

                # Agregar siempre al filtrado (no-quizzes siempre se incluyen)
                filtered_contents_data.append(content_data)

            # Eliminar quizzes anteriores que fueron reemplazados (mantener solo el último de cada topic)
            # Reconstruir la lista final filtrada excluyendo quizzes reemplazados
            final_contents_data = []
            for i, content_data in enumerate(filtered_contents_data):
                if content_data.get("content_type") != "quiz":
                    # No-quizzes siempre se incluyen
                    final_contents_data.append(content_data)
                else:
                    topic_id = content_data.get("topic_id")
                    # Incluir solo si es el último quiz para este topic
                    if topic_id and last_quiz_index_by_topic.get(topic_id) == i:
                        final_contents_data.append(content_data)
                    elif not topic_id:
                        # Si no tiene topic_id (inválido), incluir para que falle en validación posterior
                        final_contents_data.append(content_data)

            # Reemplazar contents_data con la versión filtrada
            contents_data = final_contents_data

            # Logging del resumen de reemplazos
            if quiz_replacements:
                affected_topics = list(quiz_replacements.keys())
                logging.info(
                    f"create_bulk_content: Resumen de reemplazos 'último gana' en batch: "
                    f"{len(quiz_replacements)} topic(s) afectados: {affected_topics}. "
                    f"Total de elementos en batch después de filtrado: {len(contents_data)}."
                )

            # Validaciones previas
            for i, content_data in enumerate(contents_data):
                topic_id = content_data.get("topic_id")
                content_type = self._apply_content_type_alias(content_data) or content_data.get("content_type")
                
                # Validar campos requeridos
                if not topic_id:
                    raise ValueError(f"Contenido {i+1}: topic_id es requerido")
                if not content_type:
                    raise ValueError(f"Contenido {i+1}: content_type es requerido")
                
                # Verificar que el tipo de contenido existe
                content_type_def = self.content_type_service.get_content_type(content_type)
                if not content_type_def:
                    raise ValueError(f"Contenido {i+1}: Tipo de contenido '{content_type}' no válido")

                # Validar políticas de payload (campos prohibidos, tipos) - Early validation
                user_id = content_data.get('creator_id')
                valid_policy, policy_msg = self._validate_content_payload_policy(
                    content_data,
                    context=f'create_bulk_content[{i+1}]',
                    user_id=user_id,
                    topic_id=topic_id
                )
                if not valid_policy:
                    raise ValueError(f"Contenido {i+1}: {policy_msg}")

                # Validaciones específicas para diapositivas
                if content_type == "slide":
                    # Define slide_fields from content object with fallback to root for compatibility
                    slide_fields = (content_data.get('content') or {})

                    # Log the received data for debugging
                    logging.info(f"Contenido {i+1}: Procesando slide...")

                    # Detectar caso skeleton: full_text presente sin content_html ni narrative_text
                    ft = slide_fields.get("full_text")
                    ch = slide_fields.get("content_html")
                    nt = slide_fields.get("narrative_text")

                    # Backward compatibility: si no existen en content, intentar raíz temporalmente
                    deprecated_fields_used = []
                    if ft is None:
                        ft = content_data.get("full_text")
                        if ft is not None:
                            deprecated_fields_used.append("full_text")
                    if ch is None:
                        ch = content_data.get("content_html")
                        if ch is not None:
                            deprecated_fields_used.append("content_html")
                    if nt is None:
                        nt = content_data.get("narrative_text")
                        if nt is not None:
                            deprecated_fields_used.append("narrative_text")

                    # template_snapshot has been removed - all configuration is now in slide_plan

                    # Log warnings for deprecated root field usage
                    for field in deprecated_fields_used:
                        logging.warning(
                            f"create_bulk_content: Uso de campo raíz '{field}' está deprecado en elemento {i+1}. "
                            f"Migre a usar content.{field} dentro del objeto content. "
                            f"Topic ID: {topic_id}, Content type: {content_type}"
                        )

                    # NOTA: Para mantener compatibilidad con la API existente (Tuple[bool, List[str]]),
                    # no se puede agregar un flag "deprecated_fields_used" en la respuesta.
                    # Los clientes deben monitorear los logs para detectar uso de campos deprecados
                    # y planificar la migración a la estructura content.{field}

                    is_skeleton = ft and not ch and not nt
                    # Skeleton slides validation removed - template_snapshot no longer used

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
                    # Priorizar slide_fields, fallback a raíz para backward compatibility
                    content_html = slide_fields.get("content_html")
                    narrative_text = slide_fields.get("narrative_text")
                    full_text = slide_fields.get("full_text")

                    # Backward compatibility: si no existen en content, intentar raíz temporalmente
                    if content_html is None:
                        content_html = content_data.get("content_html")
                    if narrative_text is None:
                        narrative_text = content_data.get("narrative_text")
                    if full_text is None:
                        full_text = content_data.get("full_text")

                    if content_html is not None:
                        valid, msg = self.validate_slide_html_content(content_html)
                        if not valid:
                            raise ValueError(f"Contenido {i+1}: content_html inválido: {msg}")
                    if narrative_text is not None and not isinstance(narrative_text, str):
                        raise ValueError(f"Contenido {i+1}: narrative_text debe ser una cadena de texto")
                    if full_text is not None and not isinstance(full_text, str):
                        raise ValueError(f"Contenido {i+1}: full_text debe ser una cadena de texto")
                
                # Contar uso de tipos de contenido
                content_types_usage[content_type] = content_types_usage.get(content_type, 0) + 1
            
            # Validar orden secuencial si se proporciona
            self._validate_sequential_order(contents_data)
            
            # Crear contenidos uno por uno dentro de la transacción
            for i, content_data in enumerate(contents_data):
                # Garantizar un solo quiz por topic en bulk creation
                if content_data.get("content_type") == "quiz":
                    topic_id_for_quiz = content_data.get("topic_id")
                    if topic_id_for_quiz:
                        topic_id_obj = ObjectId(topic_id_for_quiz) if not isinstance(topic_id_for_quiz, ObjectId) else topic_id_for_quiz
                        
                        # Verificar si ya procesamos eliminación de quiz para este topic en este batch
                        # (para evitar múltiples deletes si el batch tiene múltiples quizzes del mismo topic)
                        topic_key = str(topic_id_obj)
                        if topic_key not in quiz_deleted_topics:
                            # Eliminar quiz(zes) existente(s) para este topic
                            existing_count = self.collection.count_documents({
                                "topic_id": topic_id_obj,
                                "content_type": "quiz"
                            }, session=session)
                            
                            if existing_count > 0:
                                delete_result = self.collection.delete_many({
                                    "topic_id": topic_id_obj,
                                    "content_type": "quiz"
                                }, session=session)
                                
                                logging.warning(
                                    f"create_bulk_content: Eliminado(s) {delete_result.deleted_count} quiz(zes) existente(s) "
                                    f"para topic {topic_id_for_quiz} antes de crear nuevo quiz en batch. "
                                    f"Elemento {i+1} del batch."
                                )
                            
                            # Marcar que ya eliminamos quiz para este topic en este batch
                            quiz_deleted_topics.add(topic_key)

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
                    # Define slide_fields from content object with fallback to root for compatibility
                    slide_fields = (content_data.get('content') or {})

                    ch = slide_fields.get("content_html")
                    nt = slide_fields.get("narrative_text")
                    ft = slide_fields.get("full_text")

                    # Backward compatibility: si no existen en content, intentar raíz temporalmente
                    if ch is None:
                        ch = content_data.get("content_html")
                    if nt is None:
                        nt = content_data.get("narrative_text")
                    if ft is None:
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
                
                # Prepare kwargs for slide fields
                kwargs = {}
                if content_data.get("content_type") == "slide":
                    # Use slide_fields already defined above, or define again if needed
                    if 'slide_fields' not in locals():
                        slide_fields = (content_data.get('content') or {})

                    # Priorizar slide_fields, fallback a raíz para backward compatibility
                    full_text = slide_fields.get("full_text")
                    content_html = slide_fields.get("content_html")
                    narrative_text = slide_fields.get("narrative_text")
                    slide_plan = slide_fields.get("slide_plan")
                    # template_snapshot removed - all configuration is now in slide_plan

                    # Backward compatibility: si no existen en content, intentar raíz temporalmente
                    if full_text is None:
                        full_text = content_data.get("full_text")
                    if content_html is None:
                        content_html = content_data.get("content_html")
                    if narrative_text is None:
                        narrative_text = content_data.get("narrative_text")
                    if slide_plan is None:
                        slide_plan = content_data.get("slide_plan")

                    if full_text is not None:
                        kwargs["full_text"] = full_text
                    if content_html is not None:
                        kwargs["content_html"] = content_html
                    if narrative_text is not None:
                        kwargs["narrative_text"] = narrative_text
                    if slide_plan is not None:
                        kwargs["slide_plan"] = slide_plan
                
                # Crear objeto de contenido
                baseline_mix = self._resolve_baseline_mix(content_data)
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
                    learning_mix=content_data.get("learning_mix"),
                    baseline_mix=baseline_mix,

                    status=initial_status,
                    order=content_data.get("order"),
                    parent_content_id=content_data.get("parent_content_id"),
                    **kwargs
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
         - Cada slide debe incluir full_text (string) y slide_plan (string) en el campo content
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
            # Get payload from content field
            payload = slide.get('content') or {}

            # Validate full_text from payload
            full_text = payload.get('full_text')
            if not full_text or not isinstance(full_text, str) or not full_text.strip():
                return False, f"Elemento {i+1}: full_text es requerido en payload.content para crear una slide skeleton y debe ser una cadena no vacía"



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

            logging.info(
                f"create_bulk_slides_skeleton: Iniciando upsert de {len(slides_data)} slides para topic {first_topic}. "
                f"Modo idempotente: actualizará slides existentes por (topic_id, order)"
            )

            upserted_count = 0
            inserted_count = 0
            updated_count = 0
            final_ids = []
            sentinel_ids = []  # Track IDs that had the _was_inserted sentinel for cleanup

            for slide in slides_data:
                # Validar políticas de payload
                user_id = slide.get('creator_id')
                topic_id = slide.get('topic_id')
                valid_policy, policy_msg = self._validate_content_payload_policy(
                    slide,
                    context=f'create_bulk_slides_skeleton[{slide.get("order", "N/A")}]',
                    user_id=user_id,
                    topic_id=topic_id
                )
                if not valid_policy:
                    return False, f"Elemento {slide.get('order', 'N/A')}: {policy_msg}"

                # Get payload from content field
                payload = slide.get('content') or {}

                # Extract markers
                content_for_markers = payload
                if isinstance(content_for_markers, dict):
                    content_for_markers = json.dumps(content_for_markers, ensure_ascii=False)
                markers = ContentPersonalizationService.extract_markers(
                    content_for_markers or json.dumps(slide.get("interactive_data", {}))
                )



                # Prepare kwargs for slide fields from payload
                kwargs = {}
                if payload.get("full_text") is not None:
                    kwargs["full_text"] = payload.get("full_text")
                if payload.get("slide_plan") is not None:
                    kwargs["slide_plan"] = payload.get("slide_plan")

                baseline_mix = self._resolve_baseline_mix(slide)
                content_obj = TopicContent(
                    topic_id=slide.get("topic_id"),
                    content_type="slide",
                    content=payload,
                    interactive_data=slide.get("interactive_data"),
                    learning_methodologies=slide.get("learning_methodologies"),
                    adaptation_options=slide.get("metadata"),
                    resources=slide.get("resources"),
                    web_resources=slide.get("web_resources"),
                    generation_prompt=slide.get("generation_prompt"),
                    ai_credits=slide.get("ai_credits", True),
                    personalization_markers=markers,
                    learning_mix=slide.get("learning_mix"),
                    baseline_mix=baseline_mix,
                    # Force skeleton status regardless of provided status
                    status="skeleton",
                    order=slide.get("order"),
                    parent_content_id=slide.get("parent_content_id"),
                    **kwargs
                )
                d = content_obj.to_dict()

                filter_query = {
                    "topic_id": normalize_objectid(slide.get("topic_id")),
                    "content_type": "slide",
                    "order": slide.get("order")
                }
                
                # Preparar documento para upsert separando campos de actualización e inserción
                upsert_doc = d.copy()
                if "_id" in upsert_doc:
                    del upsert_doc["_id"]

                # Eliminar updated_at si existe para evitar conflicto con $currentDate
                if "updated_at" in upsert_doc:
                    del upsert_doc["updated_at"]

                # Campos que siempre se deben actualizar (excluyendo campos inmutables)
                update_doc = {}
                # Campos que solo se deben establecer en inserción (campos inmutables)
                insert_only_doc = {}

                # Lista de campos inmutables que no deben ser actualizados
                immutable_fields = ["created_at", "status", "updated_at"]

                # Extraer campos de content para actualización con notación punteada (solo skeleton)
                content_updates = {}
                content_data = upsert_doc.pop('content', {})

                # Solo actualizar campos específicos de skeleton, preservando content_html y narrative_text
                skeleton_fields = ['full_text', 'slide_plan']  # template_snapshot removed
                for field in skeleton_fields:
                    if field in content_data:
                        content_updates[f'content.{field}'] = content_data[field]

                for key, value in upsert_doc.items():
                    if key in immutable_fields:
                        insert_only_doc[key] = value
                    else:
                        update_doc[key] = value

                # Agregar actualizaciones de content con notación punteada
                update_doc.update(content_updates)

                # Para nuevos inserts, establecer created_at solo si no existe y agregar sentinel
                insert_only_doc["created_at"] = datetime.now()
                insert_only_doc["_was_inserted"] = True  # Sentinel to track insert vs update

                # Usar find_one_and_update para obtener el _id en una sola operación
                doc = self.collection.find_one_and_update(
                    filter_query,
                    {"$set": update_doc, "$setOnInsert": insert_only_doc, "$currentDate": {"updated_at": True}},
                    upsert=True,
                    return_document=ReturnDocument.AFTER,
                    projection={"_id": 1, "_was_inserted": 1},
                    session=session
                )

                # Siempre tenemos un documento con _id thanks to ReturnDocument.AFTER
                doc_id = str(doc["_id"])
                final_ids.append(doc_id)

                # Determinar si fue insert o update usando el sentinel
                if doc.get("_was_inserted"):
                    inserted_count += 1
                    sentinel_ids.append(doc_id)
                    logging.info(f"create_bulk_slides_skeleton: Insertado nuevo slide order={slide.get('order')} para topic {first_topic}, id={doc_id}")
                else:
                    updated_count += 1
                    logging.info(f"create_bulk_slides_skeleton: Actualizado slide existente order={slide.get('order')} para topic {first_topic}")
                
                upserted_count += 1

            # Eliminar slides sobrantes si el nuevo lote tiene menos slides
            max_order = max(s.get("order") for s in slides_data)
            delete_filter = {
                "topic_id": normalize_objectid(first_topic),
                "content_type": "slide",
                "order": {"$gt": max_order},
                "$or": [
                    {"parent_content_id": None},
                    {"parent_content_id": {"$exists": False}}
                ]
            }
            
            delete_result = self.collection.delete_many(delete_filter, session=session)
            
            if delete_result.deleted_count > 0:
                logging.warning(
                    f"create_bulk_slides_skeleton: Eliminados {delete_result.deleted_count} slides sobrantes "
                    f"con order > {max_order} para topic {first_topic} (regeneración con menos slides)"
                )

            # Limpiar los campos sentinel de las inserciones en una sola operación bulk
            if sentinel_ids:
                # Convertir string IDs a ObjectId para el query
                sentinel_object_ids = []
                for sid in sentinel_ids:
                    try:
                        sentinel_object_ids.append(ObjectId(sid))
                    except Exception:
                        # Skip invalid IDs but continue with valid ones
                        continue

                if sentinel_object_ids:
                    cleanup_result = self.collection.update_many(
                        {"_id": {"$in": sentinel_object_ids}},
                        {"$unset": {"_was_inserted": ""}},
                        session=session
                    )
                    if cleanup_result.modified_count > 0:
                        logging.debug(f"create_bulk_slides_skeleton: Limpiados {cleanup_result.modified_count} campos _was_inserted")

            # Actualizar contador de uso para slides
            self.content_type_service.collection.update_one(
                {"code": "slide"},
                {"$inc": {"usage_count": inserted_count}},  # Solo contar nuevas inserciones
                session=session
            )

            session.commit_transaction()
            transaction_active = False

            logging.info(
                f"create_bulk_slides_skeleton: Procesados {upserted_count} slides para topic {first_topic}: "
                f"{inserted_count} nuevos, {updated_count} actualizados, {delete_result.deleted_count if 'delete_result' in locals() else 0} eliminados"
            )
            # template_snapshot logging removed - field no longer used

            return True, final_ids
        except DuplicateKeyError as e:
            if transaction_active:
                try:
                    session.abort_transaction()
                except Exception:
                    pass
            error_msg = str(e)
            if "idx_unique_topic_content_order" in error_msg:
                logging.error(f"Error de índice único en create_bulk_slides_skeleton: {error_msg}")
                return False, f"Error de índice único: ya existe una slide con este orden para el tema especificado"
            else:
                logging.error(f"Error de índice único en create_bulk_slides_skeleton: {error_msg}")
                return False, f"Error de índice único: {error_msg}"
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
            # Solo incluir en la validacion si el tipo de contenido esta en los tipos especificados
            content_type = self._apply_content_type_alias(content_data) or content_data.get("content_type")
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
                # If no content_type is specified, use the broadest filter (slide) to ensure we get all variants
                # regardless of their specific sub-status (like narrative_ready)
                default_key = content_type if content_type else "slide"
                status_filter = DEFAULT_STATUS_BY_TYPE.get(default_key, DEFAULT_STATUS_BY_TYPE["default"])

            query = {
                "topic_id": ObjectId(topic_id),
                "status": {"$in": status_filter}
            }

            if content_type:
                query["content_type"] = content_type
            else:
                # Exclude slide_template by default when fetching all content
                query["content_type"] = {"$ne": "slide_template"}

            # Proyección: por defecto (include_metadata=True) devuelve documentos completos para compatibilidad hacia atrás
            # Solo usar proyección mínima si include_metadata es explícito False
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

            # Convertir ObjectIds a strings y fechas a ISO format
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
            Tuple[bool, str]: (es_válida, lista_de_errores)
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
    


    def update_content(self, content_id: str, update_data: Dict) -> Tuple[bool, str]:
        """
        Actualiza contenido existente.
        """
        try:
            # Obtener contenido actual para validaciones
            current_content = self.get_content(content_id)
            if not current_content:
                return False, "Contenido no encontrado"

            # Validar políticas de payload para actualizaciones
            user_id = update_data.get('creator_id') or current_content.get('creator_id')
            topic_id = current_content.get('topic_id')
            valid_policy, policy_msg = self._validate_content_payload_policy(
                update_data,
                context=f'update_content[{content_id}]',
                user_id=user_id,
                topic_id=topic_id
            )
            if not valid_policy:
                return False, policy_msg

            applied_type = None
            if 'content_type' in update_data:
                applied_type = self._apply_content_type_alias(update_data)

            # Validaciones especificas para diapositivas
            content_type = applied_type or current_content.get("content_type")

            update_data["updated_at"] = datetime.now()

            # Extraer claves punteadas que comienzan con 'content.' temprano
            dotted_content_updates = {}
            keys_to_remove = [key for key in update_data.keys() if key.startswith('content.')]
            for key in keys_to_remove:
                # Extraer el subcampo (p.ej., 'content_html' de 'content.content_html')
                subfield = key[len('content.'):]  # Remover el prefijo 'content.'
                if subfield:  # Asegurarse que no esté vacío
                    dotted_content_updates[subfield] = update_data[key]
                del update_data[key]

            # Validar y sanitizar content_html antes de normalizar si viene a nivel raíz
            if 'content_html' in update_data and update_data.get('content_html') is not None:
                valid, msg = self.validate_slide_html_content(update_data.get('content_html'))
                if not valid:
                    return False, f"content_html inválido: {msg}"
                # Sanitizar y reemplazar el valor
                update_data['content_html'] = self.sanitize_slide_html_content(update_data.get('content_html'))
                # Establecer render_engine para HTML
                update_data['render_engine'] = 'raw_html'
                logging.info(f"Validación y sanitización de content_html a nivel raíz para slide {content_id}")

            # Normalizar siempre los campos de slide al espacio content.*
            # antes de construir el $set para evitar escribir campos raíz
            root_fields_to_normalize = ['content_html', 'narrative_text', 'full_text', 'slide_plan']

            # Construir content_updates unificado fusionando en orden:
            # 1. Existing content dict
            # 2. Moved root fields
            # 3. Dotted content keys
            content_updates = update_data.get('content', {})
            if not isinstance(content_updates, dict):
                content_updates = {}

            # Mover claves raíz a content_updates
            moved_root_fields = {}
            for field in root_fields_to_normalize:
                if field in update_data:
                    moved_root_fields[field] = update_data.pop(field)

            # Fusionar todo en content_updates
            content_updates = {**content_updates, **moved_root_fields, **dotted_content_updates}

            raw_baseline_mix = content_updates.get('baseline_mix')
            if raw_baseline_mix is None:
                raw_baseline_mix = update_data.get('baseline_mix')
            normalized_baseline_mix = self._normalize_baseline_mix(raw_baseline_mix)
            if normalized_baseline_mix:
                content_updates['baseline_mix'] = normalized_baseline_mix
                update_data['baseline_mix'] = normalized_baseline_mix
            else:
                if raw_baseline_mix is not None and 'baseline_mix' in content_updates:
                    content_updates.pop('baseline_mix', None)
                if raw_baseline_mix is not None and 'baseline_mix' in update_data:
                    update_data.pop('baseline_mix', None)

            # Aplicar validaciones en content_updates unificado
            if content_updates.get('content_html') is not None:
                valid, msg = self.validate_slide_html_content(content_updates.get('content_html'))
                if not valid:
                    return False, f"content_html inválido: {msg}"
                # Sanitizar el valor
                content_updates['content_html'] = self.sanitize_slide_html_content(content_updates.get('content_html'))
                # Establecer render_engine para HTML
                update_data['render_engine'] = 'raw_html'
                logging.info(f"Validación y sanitización de content_html unificado para slide {content_id}")

            # Validar tipos de datos en content_updates
            if content_updates.get('narrative_text') is not None and not isinstance(content_updates.get('narrative_text'), str):
                return False, "content.narrative_text debe ser una cadena de texto si se proporciona"
            if content_updates.get('full_text') is not None and not isinstance(content_updates.get('full_text'), str):
                return False, "content.full_text debe ser una cadena de texto si se proporciona"

            # template_snapshot validation removed - field no longer used

            # Asegurar que el $set final no incluya ninguna de estas claves a nivel raíz
            for field in root_fields_to_normalize:
                if field in update_data:
                    del update_data[field]

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
                # Determinar valores prospectivos después de la actualización usando content_updates unificado
                # Normalizar content de current_content para acceso seguro
                current_content_normalized = self._normalize_content_field(current_content)

                prospective_content_html = (
                    content_updates.get('content_html') or
                    current_content_normalized.get('content_html')
                )
                prospective_narrative = (
                    content_updates.get('narrative_text') or
                    current_content_normalized.get('narrative_text')
                )
                prospective_full_text = (
                    content_updates.get('full_text') or
                    current_content_normalized.get('full_text')
                )

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

                # template_snapshot validation removed - field no longer used

            # Construir set_ops con claves punteadas para content_updates unificado
            # Esto evita sobrescribir el subdocumento 'content' completo
            set_ops = {}

            # Expandir content_updates unificado en claves punteadas
            if content_updates:
                for k, v in content_updates.items():
                    set_ops['content.' + k] = v

            # Eliminar 'content' de update_data si existe para evitar sobrescribir el subdocumento completo
            if 'content' in update_data:
                del update_data['content']

            # Fusionar set_ops con el resto de update_data para el $set final
            final_set_data = {**update_data, **set_ops}

            result = self.collection.update_one(
                {"_id": ObjectId(content_id)},
                {"$set": final_set_data}
            )
            
            if result.modified_count > 0:
                return True, "Contenido actualizado exitosamente"
            else:
                return False, "No se encontró el contenido o no hubo cambios"
                
        except Exception as e:
            logging.error(f"Error actualizando contenido: {str(e)}")
            return False, f"Error interno: {str(e)}"

    def delete_content(self, content_id: str, cascade: bool = False) -> Tuple[bool, str]:
        """
        Elimina contenido. Con cascade=True se eliminan físicamente todas las dependencias
        registradas en CascadeDeletionService; de lo contrario se aplica un soft delete.
        """
        try:
            content_id_obj = ObjectId(content_id)
            content = self.collection.find_one({"_id": content_id_obj})
            if not content:
                return False, "Contenido no encontrado"

            if cascade:
                cascade_service = CascadeDeletionService()
                cascade_result = cascade_service.delete_with_cascade('topic_contents', content_id)
                if not cascade_result.get('success', False):
                    return False, cascade_result.get('error', 'No se pudo eliminar el contenido en cascada')

                total_deleted = cascade_result.get('total_deleted', 0)
                dependencies_deleted = max(total_deleted - 1, 0)
                message = "Contenido eliminado en cascada"
                if dependencies_deleted > 0:
                    message += f" (incluye {dependencies_deleted} dependencias)"
                return True, message

            # Soft delete conservando histórico
            child_contents = self.collection.find({"parent_content_id": content_id_obj})
            child_count = 0

            for child in child_contents:
                child_result = self.collection.update_one(
                    {"_id": child["_id"]},
                    {"$set": {"status": "deleted", "updated_at": datetime.now()}}
                )
                if child_result.modified_count > 0:
                    child_count += 1

            result = self.collection.update_one(
                {"_id": content_id_obj},
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
                "content.content_html": 1,
                "content.narrative_text": 1,
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

                content = self._normalize_content_field(s)
                has_html = bool(content.get("content_html"))
                has_narr = bool(content.get("narrative_text"))

                if has_html:
                    slides_with_html += 1
                    html_lengths.append(len(content.get("content_html") or ""))
                if has_narr:
                    slides_with_narrative += 1
                    narrative_lengths.append(len(content.get("narrative_text") or ""))
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
                parent = s.get("parent_content_id")
                try:
                    parent_key = str(parent) if parent is not None else "root"
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
                        "content.content_html": 1,
                        "content.narrative_text": 1
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
                    content_b = b.get("content", {})
                    bottleneck_analysis.append({
                        "content_id": str(b["_id"]),
                        "gen_time_ms": gen_time_val,
                        "has_html": bool(content_b.get("content_html")),
                        "has_narrative": bool(content_b.get("narrative_text"))
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

            raw_html = html_content
            valid, msg = self.validate_slide_html_content(raw_html, allow_full_document=True, allow_iframe=True)
            if not valid:
                logging.info(f"update_slide_html: validacion fallida para slide {content_id}: {msg} (documento completo)")
                return False, f"content_html invalido: {msg}"

            update_data = {
                "content.content_html": raw_html,
                "updated_at": datetime.now(),
                "render_engine": "raw_html"
            }

            # Determinar nuevo estado
            existing_narrative = current.get("content", {}).get("narrative_text")
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

    def update_slide_full_html(self, content_id: str, full_html: str, updater_id: str = None) -> Tuple[bool, str]:
        """
        Guarda el documento HTML completo en content.full_html sin sanitización.
        No altera content.content_html ni el status derivado.
        Aplica un límite de tamaño razonable para evitar documentos excesivos.
        """
        try:
            if not isinstance(full_html, str):
                return False, "full_html debe ser una cadena de texto"

            # Límite de tamaño: ~2 MB para documento completo
            max_bytes = 2 * 1024 * 1024
            if len(full_html.encode('utf-8')) > max_bytes:
                return False, "full_html excede el tamaño máximo permitido de 2MB"

            current = self.get_content(content_id)
            if not current:
                logging.debug(f"update_slide_full_html: contenido {content_id} no encontrado")
                return False, "Contenido no encontrado"
            if current.get("content_type") != "slide":
                logging.debug(f"update_slide_full_html: contenido {content_id} no es tipo slide")
                return False, "El contenido no es una diapositiva"

            update_data = {
                "content.full_html": full_html,
                "updated_at": datetime.now()
            }

            if updater_id:
                update_data["last_updated_by"] = updater_id

            result = self.collection.update_one(
                {"_id": ObjectId(content_id)},
                {"$set": update_data}
            )

            if result.modified_count > 0:
                logging.info(f"update_slide_full_html: slide {content_id} full_html actualizado by {updater_id or 'unknown'}")
                # Invalidate caches de estado si aplica (no cambia status, pero refrescar por updated_at)
                try:
                    current_topic = current.get("topic_id")
                    cache_key = f"slide_status::{current_topic}"
                    with self._cache_lock:
                        if cache_key in self._stats_cache:
                            del self._stats_cache[cache_key]
                except Exception:
                    pass
                return True, "Full HTML de la diapositiva guardado exitosamente"
            else:
                logging.debug(f"update_slide_full_html: no hubo cambios al actualizar slide {content_id}")
                return False, "No se realizaron cambios en el contenido"
        except Exception as e:
            logging.error(f"Error en update_slide_full_html para {content_id}: {str(e)}")
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
                "content.narrative_text": narrative_trim,
                "updated_at": datetime.now()
            }

            # Si ya existe HTML, marcar como narrative_ready
            existing_html = current.get("content", {}).get("content_html")
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
            content = self._normalize_content_field(current)
            has_html = bool(content.get("content_html"))
            has_narrative = bool(content.get("narrative_text"))
            has_full_text = bool(content.get("full_text"))

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
                "content_html_length": len(content.get("content_html") or ""),
                "narrative_text_length": len(content.get("narrative_text") or ""),
                "full_text_length": len(content.get("full_text") or ""),
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
                "content.content_html": 1, "content.narrative_text": 1, "content.full_text": 1,
                "status": 1, "created_at": 1, "updated_at": 1
            }).sort([("order", 1), ("created_at", 1)]))

            total = len(slides)
            if total == 0:
                return {
                    "total": 0,
                    "percent_complete": 0.0,
                    "missing_or_incomplete": [],
                    "sequence_errors": [],
                    "per_parent": {}
                }

            missing_or_incomplete = []
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

                content = self._normalize_content_field(s)
                has_html = bool(content.get("content_html"))
                has_narrative = bool(content.get("narrative_text"))
                has_full_text = bool(content.get("full_text"))
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

                # template_snapshot tracking removed - field no longer used

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

            # template_snapshot issues processing removed - field no longer used

            complete_count = total - len(missing_or_incomplete)
            percent_complete = round((complete_count / total * 100), 2)

            report = {
                "total": total,
                "complete_count": complete_count,
                "percent_complete": percent_complete,
                "missing_or_incomplete": missing_or_incomplete,
                "sequence_errors": sequence_errors,
                "per_parent": per_parent
            }
            return report
        except Exception as e:
            logging.error(f"Error verificando completitud de slides para topic {topic_id}: {e}")
            return {}
    
    def get_complete_slides_only(self, topic_id: str) -> Dict:
        """
        Obtiene solo slides completos (con content_html y narrative_text no nulos).
        Fast path optimizado para consultas que solo necesitan slides ya completados.

        Args:
            topic_id: ID del topic

        Returns:
            Dict con {
                slides: [...],
                last_completed_slide: {...},
                completion_trend: [...],
                generation_efficiency: {...}
            }
        """
        try:
            topic_obj_id = ObjectId(topic_id)

            # Pipeline para obtener slides completos con métricas
            pipeline = [
                {
                    "$match": {
                        "topic_id": topic_obj_id,
                        "content_type": "slide",
                        "status": "narrative_ready",
                        "content.content_html": {"$exists": True, "$ne": None},
                        "content.narrative_text": {"$exists": True, "$ne": None}
                    }
                },
                {
                    "$project": {
                        "_id": 1,
                        "order": 1,
                        "parent_content_id": 1,
                        "status": 1,
                        "content.content_html": 1,
                        "content.narrative_text": 1,
                        "created_at": 1,
                        "updated_at": 1,
                        "render_engine": 1,
                        "gen_time_ms": {
                            "$cond": [
                                {"$and": [
                                    {"$ifNull": ["$created_at", False]},
                                    {"$ifNull": ["$updated_at", False]}
                                ]},
                                {"$subtract": ["$updated_at", "$created_at"]},
                                None
                            ]
                        }
                    }
                },
                {"$sort": {"order": 1}},
                {
                    "$group": {
                        "_id": None,
                        "slides": {"$push": "$$ROOT"},
                        "total_gen_time": {"$sum": "$gen_time_ms"},
                        "avg_gen_time": {"$avg": "$gen_time_ms"},
                        "max_gen_time": {"$max": "$gen_time_ms"},
                        "min_gen_time": {"$min": "$gen_time_ms"},
                        "last_updated": {"$max": "$updated_at"},
                        "last_order": {"$max": "$order"}
                    }
                }
            ]

            result = list(self.collection.aggregate(pipeline))

            if not result:
                return {
                    "slides": [],
                    "last_completed_slide": None,
                    "completion_trend": [],
                    "generation_efficiency": {
                        "total_slides": 0,
                        "avg_gen_time_ms": 0,
                        "total_gen_time_ms": 0
                    }
                }

            data = result[0]
            slides = data.get("slides", [])

            # Encontrar el último slide completado
            last_completed_slide = None
            if slides:
                last_slide = max(slides, key=lambda x: x.get("order", 0))
                last_completed_slide = {
                    "id": str(last_slide["_id"]),
                    "order": last_slide["order"],
                    "status": last_slide["status"],
                    "updated_at": last_slide["updated_at"]
                }

            # Calcular tendencia de completación (basada en updated_at)
            completion_trend = []
            if len(slides) > 1:
                # Agrupar slides por día para mostrar tendencia
                daily_counts = {}
                for slide in slides:
                    date = slide["updated_at"].strftime("%Y-%m-%d")
                    daily_counts[date] = daily_counts.get(date, 0) + 1

                # Convertir a lista ordenada para tendencia
                completion_trend = [
                    {"date": date, "completed_slides": count}
                    for date, count in sorted(daily_counts.items())
                ]

            # Métricas de eficiencia de generación
            generation_efficiency = {
                "total_slides": len(slides),
                "avg_gen_time_ms": int(data.get("avg_gen_time", 0) or 0),
                "total_gen_time_ms": int(data.get("total_gen_time", 0) or 0),
                "max_gen_time_ms": int(data.get("max_gen_time", 0) or 0),
                "min_gen_time_ms": int(data.get("min_gen_time", 0) or 0)
            }

            return {
                "slides": slides,
                "last_completed_slide": last_completed_slide,
                "completion_trend": completion_trend,
                "generation_efficiency": generation_efficiency
            }

        except Exception as e:
            logging.error(f"Error en get_complete_slides_only para topic {topic_id}: {e}")
            # Retornar estructura vacía en caso de error para mantener compatibilidad
            return {
                "slides": [],
                "last_completed_slide": None,
                "completion_trend": [],
                "generation_efficiency": {
                    "total_slides": 0,
                    "avg_gen_time_ms": 0,
                    "total_gen_time_ms": 0
                }
            }

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
                    "content.content_html": 1,
                    "content.narrative_text": 1,
                    "created_at": 1,
                    "updated_at": 1,
                    "render_engine": 1,
                    "has_html": {"$cond": [{"$ifNull": ["$content.content_html", False]}, 1, 0]},
                    "has_narrative": {"$cond": [{"$ifNull": ["$content.narrative_text", False]}, 1, 0]},
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
            cache_key = f"slides_optimized_stats::{topic_id}::{render_engine}::{','.join(sorted(status_filter))}::{group_by_parent}::{include_progress}"
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
                            "slides_with_html": {"$sum": {"$cond": [{"$ifNull": ["$content.content_html", False]}, 1, 0]}},
                            "slides_with_narrative": {"$sum": {"$cond": [{"$ifNull": ["$content.narrative_text", False]}, 1, 0]}},
                            "slides_complete": {"$sum": {"$cond": [{"$and": [{"$ifNull": ["$content.content_html", False]}, {"$ifNull": ["$content.narrative_text", False]}]}, 1, 0]}} ,
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
                            "content.content_html": {"$ne": None},
                            "content.narrative_text": {"$ne": None},
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
                        "average_generation_time_ms": avg_gen_time,
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
                        "has_html": {"$cond": [{"$ifNull": ["$content.content_html", False]}, 1, 0]},
                        "has_narrative": {"$cond": [{"$ifNull": ["$content.narrative_text", False]}, 1, 0]},
                        "complete": {"$cond": [{"$and": [{"$ifNull": ["$content.content_html", False]}, {"$ifNull": ["$content.narrative_text", False]}]}, 1, 0]},
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


class ContentResultService:
    """
    Gestiona el almacenamiento y consulta de resultados de contenido (slides, juegos, quizzes, etc.).
    Reúne metadatos del contenido virtual/original para que evaluaciones, personalización y RL tengan
    información consistente sin depender del frontend.
    """

    def __init__(self):
        self.db = get_db()
        self.collection = self.db.content_results
        self.virtual_contents = self.db.virtual_topic_contents
        self.virtual_topics = self.db.virtual_topics
        self.topic_contents = self.db.topic_contents

    # ---------------------------------------------------------------------
    # Public API
    # ---------------------------------------------------------------------
    def record_result(self, result_data: Dict) -> Tuple[bool, str]:
        """
        Inserta un ContentResult normalizado en MongoDB.
        """
        try:
            normalized = self._normalize_payload(result_data)
            content_result = ContentResult(**normalized)
            insert_result = self.collection.insert_one(content_result.to_dict())
            self._refresh_vakr_async(str(content_result.student_id))
            self._trigger_evaluation_processing_async(
                str(content_result.student_id),
                normalized.get("topic_id"),
            )
            return True, str(insert_result.inserted_id)
        except ValueError as ve:
            logging.warning(f"ContentResult inválido: {ve}")
            return False, str(ve)
        except Exception as exc:
            logging.error(f"Error guardando ContentResult: {exc}")
            return False, "Error interno al guardar el resultado"

    def get_student_results(
        self,
        student_id: str,
        content_type: Optional[str] = None,
        virtual_content_id: Optional[str] = None,
        evaluation_id: Optional[str] = None,
        topic_id: Optional[str] = None,
        limit: int = 200,
    ) -> List[Dict]:
        """
        Obtiene los resultados de un estudiante con filtros opcionales.
        """
        try:
            student_oid = self._safe_object_id(student_id)
            if not student_oid:
                raise ValueError("student_id inválido")

            query: Dict[str, Any] = {"student_id": student_oid}

            if content_type:
                query["content_type"] = content_type
            else:
                # Exclude slide_template by default when fetching all content
                query["content_type"] = {"$ne": "slide_template"}

            if virtual_content_id:
                vc_oid = self._safe_object_id(virtual_content_id)
                if vc_oid:
                    query["virtual_content_id"] = vc_oid

            if evaluation_id:
                eval_oid = self._safe_object_id(evaluation_id)
                if eval_oid:
                    query["evaluation_id"] = eval_oid

            if topic_id:
                topic_oid = self._safe_object_id(topic_id)
                if topic_oid:
                    query["topic_id"] = topic_oid

            cursor = (
                self.collection.find(query)
                .sort("recorded_at", -1)
                .limit(max(limit, 1))
            )
            return [self._serialize_result(doc) for doc in cursor]
        except Exception as exc:
            logging.error(f"Error obteniendo resultados de estudiante {student_id}: {exc}")
            return []

    def get_results_by_content(
        self,
        content_id: str,
        student_id: Optional[str] = None,
        limit: int = 200,
    ) -> List[Dict]:
        """
        Devuelve resultados asociados a un TopicContent específico.
        """
        try:
            content_oid = self._safe_object_id(content_id)
            if not content_oid:
                raise ValueError("content_id inválido")

            query: Dict[str, Any] = {"content_id": content_oid}
            if student_id:
                student_oid = self._safe_object_id(student_id)
                if student_oid:
                    query["student_id"] = student_oid

            cursor = (
                self.collection.find(query)
                .sort("recorded_at", -1)
                .limit(max(limit, 1))
            )
            return [self._serialize_result(doc) for doc in cursor]
        except Exception as exc:
            logging.error(f"Error obteniendo resultados del contenido {content_id}: {exc}")
            return []

    def get_selection_statistics(
        self,
        topic_id: Optional[str] = None,
        student_id: Optional[str] = None,
        since: Optional[datetime] = None,
    ) -> Dict[str, Any]:
        """
        Devuelve métricas agregadas por estrategia de selección (heurística vs worker/RL).
        """
        try:
            match_stage: Dict[str, Any] = {}

            if topic_id:
                topic_oid = self._safe_object_id(topic_id)
                if topic_oid:
                    match_stage["topic_id"] = topic_oid

            if student_id:
                student_oid = self._safe_object_id(student_id)
                if student_oid:
                    match_stage["student_id"] = student_oid

            if since and isinstance(since, datetime):
                match_stage["recorded_at"] = {"$gte": since}

            pipeline = []
            if match_stage:
                pipeline.append({"$match": match_stage})

            pipeline.extend(
                [
                    {
                        "$group": {
                            "_id": {
                                "strategy": {
                                    "$ifNull": ["$metrics.selection_strategy", "$metrics.selection_source"]
                                },
                                "source": "$metrics.selection_source",
                            },
                            "count": {"$sum": 1},
                            "avg_score": {"$avg": "$score"},
                            "avg_vark_score": {"$avg": "$metrics.vark_score"},
                            "rl_usage": {"$avg": {"$cond": ["$metrics.selection_via_rl", 1, 0]}},
                        }
                    },
                    {
                        "$project": {
                            "_id": 0,
                            "strategy": "$_id.strategy",
                            "source": "$_id.source",
                            "count": 1,
                            "avg_score": 1,
                            "avg_vark_score": 1,
                            "selection_via_rl_ratio": "$rl_usage",
                        }
                    },
                    {"$sort": {"count": -1}},
                ]
            )

            results = list(self.collection.aggregate(pipeline))
            total = sum(item.get("count", 0) for item in results) or 1

            for item in results:
                item["percentage"] = round(item.get("count", 0) / total, 4)

            return {"total_results": total, "strategies": results}
        except Exception as exc:
            logging.error(f"Error agregando métricas de selección: {exc}")
            return {"total_results": 0, "strategies": []}

    # ---------------------------------------------------------------------
    # Normalización y helpers
    # ---------------------------------------------------------------------
    def _normalize_payload(self, data: Dict) -> Dict[str, Any]:
        if not isinstance(data, dict):
            raise ValueError("Payload inválido para ContentResult")

        payload = dict(data)
        session_data = payload.get("session_data") or {}
        if not isinstance(session_data, dict):
            session_data = {}

        metrics = payload.get("metrics") or {}
        if not isinstance(metrics, dict):
            metrics = {}

        learning_metrics = payload.get("learning_metrics") or {}
        if not isinstance(learning_metrics, dict):
            learning_metrics = {}

        rl_context = payload.get("rl_context") or {}
        if not isinstance(rl_context, dict):
            rl_context = {}

        fallback_mode_signal = metrics.get("fallback_mode")
        if fallback_mode_signal is None:
            metrics["fallback_mode"] = bool(rl_context.get("fallback_mode"))
        else:
            metrics["fallback_mode"] = bool(fallback_mode_signal)

        if not metrics.get("rl_error"):
            rl_error = rl_context.get("rl_error") or rl_context.get("error_message")
            if rl_error:
                metrics["rl_error"] = rl_error

        if "circuit_state" not in metrics:
            circuit_state = rl_context.get("circuit_state")
            if circuit_state is not None:
                metrics["circuit_state"] = circuit_state

        baseline_mix = payload.get("baseline_mix") or {}
        if not isinstance(baseline_mix, dict):
            baseline_mix = {}

        completion_percentage = payload.get("completion_percentage")
        if completion_percentage is None:
            completion_percentage = session_data.get("completion_percentage")
        if completion_percentage is not None:
            metrics.setdefault("completion_percentage", completion_percentage)

        metadata = {}
        if payload.get("virtual_content_id"):
            metadata = self._extract_virtual_content_metadata(payload["virtual_content_id"])

        student_id = payload.get("student_id") or metadata.get("student_id")
        if not student_id:
            raise ValueError("student_id es requerido")
        student_oid = self._safe_object_id(student_id)
        if not student_oid:
            raise ValueError("student_id inválido")
        student_id = str(student_oid)

        content_id = payload.get("content_id") or metadata.get("content_id")
        evaluation_id = payload.get("evaluation_id")
        if not content_id and evaluation_id:
            content_id = evaluation_id
        if content_id:
            content_oid = self._safe_object_id(content_id)
            if not content_oid:
                raise ValueError("content_id inválido")
            content_id = str(content_oid)

        # ContentResult exige al menos content_id o virtual_content_id
        if not content_id and not payload.get("virtual_content_id"):
            raise ValueError("Se requiere content_id o virtual_content_id")

        topic_id = payload.get("topic_id") or metadata.get("topic_id")
        if topic_id:
            topic_oid = self._safe_object_id(topic_id)
            topic_id = str(topic_oid) if topic_oid else None

        content_type = payload.get("content_type") or metadata.get("content_type") or "unknown"
        variant_label = payload.get("variant_label") or metadata.get("variant_label")
        template_instance_id = payload.get("template_instance_id") or metadata.get("template_instance_id")
        if template_instance_id:
            template_oid = self._safe_object_id(template_instance_id)
            if template_oid:
                template_instance_id = str(template_oid)
        template_usage_id = (
            payload.get("template_usage_id")
            or metadata.get("template_usage_id")
            or session_data.get("template_usage_id")
        )
        if template_usage_id:
            template_usage_id = str(template_usage_id)
        elif content_id:
            template_usage_id = str(content_id)
        prediction_id = payload.get("prediction_id") or metadata.get("prediction_id")
        baseline_mix = baseline_mix or metadata.get("baseline_mix") or {}

        metrics.setdefault("virtual_topic_id", metadata.get("virtual_topic_id"))
        metrics.setdefault("virtual_module_id", metadata.get("virtual_module_id"))
        metrics.setdefault("topic_order", metadata.get("topic_order"))
        metrics.setdefault("content_title", metadata.get("content_title"))
        metrics.setdefault("variant_label", variant_label)

        personalization_data = metadata.get("personalization_data") or {}
        if personalization_data.get("selection_strategy") and "selection_strategy" not in metrics:
            metrics["selection_strategy"] = personalization_data.get("selection_strategy")

        score = self._normalize_score(
            payload.get("score"),
            session_data,
            completion_percentage,
        )

        recorded_at = payload.get("recorded_at")
        if isinstance(recorded_at, str):
            try:
                recorded_at = datetime.fromisoformat(recorded_at)
            except ValueError:
                recorded_at = None
        if not isinstance(recorded_at, datetime):
            recorded_at = datetime.now()

        virtual_content_id = metadata.get("virtual_content_id") or payload.get("virtual_content_id")
        if virtual_content_id:
            vc_oid = self._safe_object_id(virtual_content_id)
            if not vc_oid:
                raise ValueError("virtual_content_id inválido")
            virtual_content_id = str(vc_oid)

        normalized = {
            "student_id": str(student_id),
            "score": score,
            "content_id": str(content_id) if content_id else None,
            "virtual_content_id": virtual_content_id,
            "evaluation_id": evaluation_id,
            "feedback": payload.get("feedback"),
            "metrics": self._convert_objectids(metrics),
            "session_type": payload.get("session_type", "content_interaction"),
            "topic_id": str(topic_id) if topic_id else None,
            "content_type": content_type,
            "variant_label": variant_label,
            "template_instance_id": str(template_instance_id) if template_instance_id else None,
            "template_usage_id": template_usage_id,
            "baseline_mix": baseline_mix,
            "prediction_id": prediction_id,
            "rl_context": self._convert_objectids(rl_context),
            "session_data": self._convert_objectids(session_data),
            "learning_metrics": self._convert_objectids(learning_metrics),
            "recorded_at": recorded_at,
        }
        return normalized

    def _extract_virtual_content_metadata(self, virtual_content_id: str) -> Dict[str, Any]:
        metadata: Dict[str, Any] = {}
        vc_oid = self._safe_object_id(virtual_content_id)
        if not vc_oid:
            raise ValueError("virtual_content_id inválido")

        virtual_content = self.virtual_contents.find_one({"_id": vc_oid})
        if not virtual_content:
            raise ValueError("Contenido virtual no encontrado")

        personalization_data = virtual_content.get("personalization_data") or {}
        metadata["virtual_content_id"] = str(virtual_content["_id"])
        metadata["content_id"] = self._stringify_object_id(
            virtual_content.get("content_id") or virtual_content.get("original_content_id")
        )
        if metadata.get("content_id") and not metadata.get("template_usage_id"):
            metadata["template_usage_id"] = metadata["content_id"]
        metadata["content_type"] = virtual_content.get("content_type")
        metadata["virtual_topic_id"] = self._stringify_object_id(virtual_content.get("virtual_topic_id"))
        metadata["student_id"] = self._stringify_object_id(virtual_content.get("student_id"))
        metadata["personalization_data"] = personalization_data
        metadata["baseline_mix"] = personalization_data.get("baseline_mix")
        metadata["prediction_id"] = personalization_data.get("prediction_id")
        metadata["variant_label"] = personalization_data.get("variant_label") or personalization_data.get("variant")
        metadata["template_instance_id"] = self._stringify_object_id(
            virtual_content.get("instance_id") or personalization_data.get("template_instance_id")
        )

        virtual_topic_id = virtual_content.get("virtual_topic_id")
        if virtual_topic_id:
            virtual_topic = self.virtual_topics.find_one({"_id": virtual_topic_id})
            if virtual_topic:
                metadata["topic_id"] = self._stringify_object_id(virtual_topic.get("topic_id"))
                metadata["virtual_module_id"] = self._stringify_object_id(virtual_topic.get("virtual_module_id"))
                metadata["topic_order"] = virtual_topic.get("order")

        content_id = metadata.get("content_id")
        content_oid = self._safe_object_id(content_id)
        if content_oid:
            topic_content = self.topic_contents.find_one({"_id": content_oid})
            if topic_content:
                metadata["content_type"] = metadata.get("content_type") or topic_content.get("content_type")
                metadata["topic_id"] = metadata.get("topic_id") or self._stringify_object_id(topic_content.get("topic_id"))
                metadata["baseline_mix"] = (
                    metadata.get("baseline_mix")
                    or topic_content.get("baseline_mix")
                    or (topic_content.get("content", {}).get("baseline_mix") if isinstance(topic_content.get("content"), dict) else None)
                    or topic_content.get("learning_mix")
                )
                variant = topic_content.get("variant") or {}
                metadata["variant_label"] = metadata.get("variant_label") or variant.get("variant_label")
                metadata["variant_index"] = variant.get("variant_index")
                metadata["parent_order"] = variant.get("parent_order")
                attachment = topic_content.get("attachment") or {}
                if not metadata.get("template_instance_id"):
                    metadata["template_instance_id"] = self._stringify_object_id(
                        attachment.get("template_instance_id") or topic_content.get("instance_id")
                    )
                metadata["template_version"] = attachment.get("template_version") or topic_content.get("template_version")

                content_field = topic_content.get("content")
                if isinstance(content_field, dict):
                    metadata["content_title"] = content_field.get("title")
                else:
                    metadata["content_title"] = topic_content.get("title")
                if not metadata.get("template_usage_id"):
                    metadata["template_usage_id"] = self._stringify_object_id(topic_content.get("_id"))

        return metadata

    def _normalize_score(
        self,
        raw_score: Optional[Any],
        session_data: Dict,
        completion_percentage: Optional[Any],
    ) -> float:
        score = raw_score
        if score is None:
            score = session_data.get("score")
        if score is None and completion_percentage is not None:
            score = completion_percentage
        if score is None:
            score = session_data.get("completion_percentage")
        if score is None:
            score = 0.0

        try:
            score = float(score)
        except (TypeError, ValueError):
            score = 0.0

        # Si el score viene en 0-100, normalizarlo
        if score > 1.0:
            if score <= 100:
                score = score / 100.0
            else:
                score = 1.0
        return max(0.0, min(1.0, score))

    def normalize_score(
        self,
        raw_score: Optional[Any],
        session_data: Optional[Dict] = None,
        completion_percentage: Optional[Any] = None,
    ) -> float:
        """Exposes normalized score logic for reuse in routes."""
        return self._normalize_score(raw_score, session_data or {}, completion_percentage)

    def _serialize_result(self, document: Dict) -> Dict:
        result = dict(document)
        result["_id"] = str(result["_id"])

        for key in ["student_id", "content_id", "virtual_content_id", "evaluation_id", "topic_id", "template_instance_id", "template_usage_id"]:
            if result.get(key):
                result[key] = str(result[key])

        recorded_at = result.get("recorded_at")
        if isinstance(recorded_at, datetime):
            result["recorded_at"] = recorded_at.isoformat()

        result["metrics"] = self._convert_objectids(result.get("metrics") or {})
        result["session_data"] = self._convert_objectids(result.get("session_data") or {})
        result["learning_metrics"] = self._convert_objectids(result.get("learning_metrics") or {})
        result["baseline_mix"] = result.get("baseline_mix") or {}
        result["rl_context"] = self._convert_objectids(result.get("rl_context") or {})
        return result

    def _refresh_vakr_async(self, student_id: str) -> None:
        def worker():
            try:
                service = AdaptivePersonalizationService()
                service.get_vakr_statistics(student_id, force_refresh=True)
                logging.info(f"VAKR stats refreshed for student {student_id}")
            except Exception as exc:
                logging.warning(f"Unable to refresh VAKR stats for {student_id}: {exc}")

        thread = threading.Thread(target=worker, daemon=True)
        thread.start()

    def _trigger_evaluation_processing_async(self, student_id: str, topic_id: Optional[str]) -> None:
        if not student_id or not topic_id:
            return

        try:
            self._eval_executor.submit(self._process_evaluation_updates, student_id, topic_id)
        except Exception as exc:
            logging.warning(f"Unable to submit evaluation processing task: {exc}")

    def _process_evaluation_updates(self, student_id: str, topic_id: str) -> None:
        try:
            topic_oid = self._safe_object_id(topic_id)
            if not topic_oid:
                return

            evaluations = list(
                self.db.evaluations.find({"topic_ids": topic_oid}, {"_id": 1})
            )
            if not evaluations:
                return

            from src.evaluations.services import EvaluationService

            evaluation_service = EvaluationService()
            for evaluation in evaluations:
                evaluation_id = str(evaluation["_id"])
                try:
                    evaluation_service.process_content_result_grading(
                        evaluation_id, student_id
                    )
                    logging.info(
                        "ContentResultService: evaluación %s actualizada para estudiante %s",
                        evaluation_id,
                        student_id,
                    )
                except Exception as exc:
                    logging.warning(
                        "ContentResultService: no se pudo actualizar evaluación %s para estudiante %s: %s",
                        evaluation_id,
                        student_id,
                        exc,
                    )
        except Exception as exc:
            logging.warning(
                "ContentResultService: error disparando actualización de evaluaciones para topic %s / estudiante %s: %s",
                topic_id,
                student_id,
                exc,
            )

    def _safe_object_id(self, value: Optional[Any]) -> Optional[ObjectId]:
        if not value:
            return None
        if isinstance(value, ObjectId):
            return value
        try:
            return ObjectId(str(value))
        except Exception:
            return None

    def _stringify_object_id(self, value: Optional[Any]) -> Optional[str]:
        if isinstance(value, ObjectId):
            return str(value)
        if value is None:
            return None
        return str(value)

    def _convert_objectids(self, value: Any) -> Any:
        if isinstance(value, ObjectId):
            return str(value)
        if isinstance(value, list):
            return [self._convert_objectids(item) for item in value]
        if isinstance(value, dict):
            return {key: self._convert_objectids(val) for key, val in value.items()}
        return value
