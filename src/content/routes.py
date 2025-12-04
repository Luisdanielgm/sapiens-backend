from flask import Blueprint, request, g, jsonify, make_response
from flask_jwt_extended import jwt_required, get_jwt_identity
from bson import ObjectId
import logging
import datetime
import json
import warnings

from src.shared.decorators import role_required
from src.shared.database import get_db
from src.shared.standardization import APIRoute, ErrorCodes
from .services import (
    ContentService,
    ContentTypeService,
    ContentResultService,
)
from src.content.template_integration_service import TemplateIntegrationService
from src.shared.constants import ROLES

content_bp = Blueprint('content', __name__, url_prefix='/api/content')

# Servicios
content_service = ContentService()
content_type_service = ContentTypeService()
content_result_service = ContentResultService()
template_integration_service = TemplateIntegrationService()

# Helper for deprecation responses with headers
def _deprecation_response(message: str, recommendation: str = None, status_code: int = 410, sunset: str = "2025-12-31"):
    """
    Construye una respuesta JSON con cabeceras HTTP de deprecación para endpoints legacy.
    """
    body = {
        "error": {
            "message": message
        }
    }
    if recommendation:
        body["error"]["recommendation"] = recommendation

    resp = make_response(jsonify(body), status_code)
    # Standard deprecation / sunset headers
    resp.headers['Deprecation'] = 'true'
    resp.headers['Sunset'] = sunset
    # Provide an explanatory Warning header (RFC 7234 compatible style)
    resp.headers['Warning'] = f'299 - "Deprecated API; use templates. Sunset: {sunset}"'
    return resp

# ============================================
# ENDPOINTS DE TIPOS DE CONTENIDO
# ============================================

@content_bp.route('/types', methods=['GET'])
@APIRoute.standard(auth_required_flag=True)
def get_content_types():
    """
    Obtiene todos los tipos de contenido disponibles.
    Query params: subcategory
    """
    try:
        subcategory = request.args.get('subcategory')  # game, simulation, quiz, diagram, etc.

        content_types = content_type_service.get_content_types(subcategory)

        return APIRoute.success(data={"content_types": content_types})
        
    except Exception as e:
        logging.error(f"Error obteniendo tipos de contenido: {str(e)}")
        return APIRoute.error(
            ErrorCodes.SERVER_ERROR,
            "Error interno del servidor",
            status_code=500,
        )

@content_bp.route('/types', methods=['POST'])
@APIRoute.standard(auth_required_flag=True, roles=[ROLES["ADMIN"]])
def create_content_type():
    """
    Crea un nuevo tipo de contenido.
    """
    try:
        data = request.json
        
        success, result = content_type_service.create_content_type(data)
        
        if success:
            return APIRoute.success(
                data={"content_type_id": result},
                message="Tipo de contenido creado exitosamente",
                status_code=201,
            )
        else:
            return APIRoute.error(ErrorCodes.CREATION_ERROR, result)
            
    except Exception as e:
        logging.error(f"Error creando tipo de contenido: {str(e)}")
        return APIRoute.error(
            ErrorCodes.SERVER_ERROR,
            "Error interno del servidor",
            status_code=500,
        )

# ============================================
# ENDPOINTS DE CONTENIDO UNIFICADO
# ============================================

@content_bp.route('/', methods=['POST'])
@APIRoute.standard(auth_required_flag=True, roles=[ROLES["TEACHER"], ROLES["ADMIN"]])
def create_content():
    """
    Crea contenido de cualquier tipo (game, simulation, quiz, diagram, slide, etc.)
    
    Body:
    {
        "topic_id": "ObjectId",
        "content_type": "game|simulation|quiz|diagram|text|video|slide|...",
        "title": "Título del contenido",
        "description": "Descripción",
        "content": "Contenido principal (string o dict según tipo)",
        "interactive_data": {...},  // Para tipos interactivos
        "difficulty": "easy|medium|hard",
        "estimated_duration": 15,
        "learning_objectives": [...],
        "tags": [...],
        "resources": [...],
        "generation_prompt": "...",  // Para contenido generado por IA

        "order": 1,  // Orden secuencial del contenido (opcional)
        "parent_content_id": "ObjectId"  // ID del contenido padre (opcional)
    }
    
    Para diapositivas (content_type: "slide"), los campos específicos deben enviarse dentro del objeto "content":
    {
        "topic_id": "...",
        "content_type": "slide",
        "content": {
            "full_text": "...",
            "slide_plan": "...",
            "content_html": "...",
            "narrative_text": "..."
        },

        "order": 1
    }
    
    POLÍTICAS DE VALIDACIÓN:
    - Los campos 'provider' y 'model' NO están permitidos en el payload. El sistema gestiona automáticamente la selección de proveedores.
    - Para slides: 'slide_plan' debe ser una cadena de texto (Markdown/texto plano), no un objeto JSON.

    - El HTML de slides tiene un límite de 150 KB (150,000 caracteres).
    
    COMPORTAMIENTO ESPECIAL PARA QUIZ:
    - Solo puede existir UN quiz por topic.
    - Si ya existen uno o más quizes para el topic_id especificado, TODOS se eliminarán automáticamente antes de crear el nuevo.
    - Esto garantiza que regenerar un quiz no cree duplicados ni deje residuos.
    - El ID retornado será siempre de un quiz nuevo (todos los anteriores se eliminan).
    - Se crea un nuevo documento con insert_one() después de eliminar todos los quizes previos con delete_many().
    """
    try:
        data = request.json
        data['creator_id'] = request.user_id
        
        success, result = content_service.create_content(data)

        if success:
            return APIRoute.success(
                data={"content_id": result},
                message="Contenido creado exitosamente",
                status_code=201,
            )
        else:
            return APIRoute.error(ErrorCodes.VALIDATION_ERROR, result)
            
    except Exception as e:
        logging.error(f"Error creando contenido: {str(e)}")
        return APIRoute.error(
            ErrorCodes.SERVER_ERROR,
            "Error interno del servidor",
            status_code=500,
        )

@content_bp.route('/bulk', methods=['POST'])
@APIRoute.standard(auth_required_flag=True, roles=[ROLES["TEACHER"], ROLES["ADMIN"]])
def create_bulk_content():
    """
    Crea múltiples contenidos en una sola transacción.

    Soporte mejorado para slides:
    - Para creación masiva de diapositivas skeleton considere usar el endpoint dedicado:
      POST /api/content/bulk/slides
    - Si se incluyen diapositivas en el array 'contents', los campos específicos de slide deben enviarse dentro del objeto "content":
        - content: {
            "full_text": texto plano usado para generar HTML/narrativa (obligatorio para skeleton slides)
            "content_html": contenido HTML (opcional, para slides no-skeleton)
            "narrative_text": texto narrativo (opcional, para slides no-skeleton)
            "slide_plan": (opcional)
          }
        - order: entero positivo indicando posición secuencial
        - parent_content_id: ObjectId del contenido padre (opcional)
        - Otros campos permitidos: interactive_data, resources, metadata, generation_prompt

    Validaciones realizadas por este endpoint (además de las del servicio):
    - Verifica que se haya enviado el array 'slides' y que no esté vacío
    - Todos los items deben ser content_type == 'slide'
    - Todas las slides deben compartir el mismo topic_id
    - Verifica que order sea una secuencia única y consecutiva comenzando en 1

    Responde con:
    - 201 + lista de IDs insertados en caso de éxito
    - 400 con mensaje de validación en caso de datos inválidos
    
    POLÍTICAS DE VALIDACIÓN:
    - Los campos 'provider' y 'model' NO están permitidos en ningún elemento del array.
    - 'slide_plan' debe ser string (texto/Markdown), no objeto JSON o array.
    - Límite de HTML por slide: 150 KB.
    
    COMPORTAMIENTO PARA QUIZ EN BULK:
    - Si el batch incluye uno o más quizzes, se eliminará cualquier quiz existente para cada topic_id antes de crear el nuevo.
    - Para múltiples quizzes del mismo topic_id en el batch, solo el último se persistirá (comportamiento "último gana").
    - Los quizzes anteriores en el batch serán reemplazados por el último quiz del mismo topic_id.
    """
    try:
        data = request.json
        contents_data = data.get('contents', [])
        
        if not contents_data:
            return APIRoute.error(
                ErrorCodes.VALIDATION_ERROR,
                "Se requiere al menos un contenido en el array 'contents'"
            )
        
        # Verificar duplicados para slides
        slides_data = [content for content in contents_data if content.get('content_type') == 'slide']
        quiz_data = [content for content in contents_data if content.get('content_type') == 'quiz']

        
        if slides_data:
            # Agrupar slides por topic_id para verificar duplicados
            topic_groups = {}
            for slide in slides_data:
                topic_id = slide.get('topic_id')
                order = slide.get('order')
                # Validate order is present and valid
                if order is None or not isinstance(order, int) or order < 1:
                    return APIRoute.error(
                        ErrorCodes.VALIDATION_ERROR,
                        "Todas las slides deben tener un campo 'order' con valor entero positivo"
                    )
                if topic_id:
                    if topic_id not in topic_groups:
                        topic_groups[topic_id] = []
                    topic_groups[topic_id].append(order)

            # Verificar duplicados en cada topic
            for topic_id, orders in topic_groups.items():
                # Check for duplicate orders within the request
                unique_orders = set(orders)
                if len(unique_orders) != len(orders):
                    duplicates = [order for order in set(orders) if orders.count(order) > 1]
                    return APIRoute.error(
                        ErrorCodes.VALIDATION_ERROR,
                        f"Se encontraron órdenes duplicados en la petición para el topic {topic_id}: {duplicates}"
                    )

                # Check for duplicates against existing database records
                duplicate_check = content_service.check_existing_skeletons(topic_id, list(unique_orders))
                if duplicate_check.get('has_duplicates'):
                    return APIRoute.error(
                        ErrorCodes.RESOURCE_ALREADY_EXISTS,
                        f"Se encontraron {duplicate_check['count']} skeletons duplicados para el topic {topic_id} en las posiciones: {duplicate_check['existing_orders']}. IDs existentes: {duplicate_check['existing_ids']}",
                        status_code=409,
                        data={
                            "duplicates_found": duplicate_check,
                            "suggestion": "Use GET /api/content/topic/{topicId}/check-duplicates para verificar duplicados antes de crear"
                        }
                    )

        # Agregar creator_id a todos los contenidos
        for content_data in contents_data:
            content_data['creator_id'] = request.user_id

        success, result = content_service.create_bulk_content(contents_data)

        if success:
            return APIRoute.success(
                data={"content_ids": result},
                message=f"Se crearon {len(result)} contenidos exitosamente",
                status_code=201,
            )
        else:
            # Usar VALIDATION_ERROR para fallos de validación (ej: "Violación de política")
            # y CREATION_ERROR para otros errores internos del servidor
            error_msg = result or "Error desconocido"
            if "Violación de política" in error_msg:
                return APIRoute.error(ErrorCodes.VALIDATION_ERROR, error_msg)
            else:
                return APIRoute.error(ErrorCodes.CREATION_ERROR, error_msg)
            
    except Exception as e:
        logging.error(f"Error creando contenidos en lote: {str(e)}")
        return APIRoute.error(
            ErrorCodes.SERVER_ERROR,
            "Error interno del servidor",
            status_code=500,
        )

@content_bp.route('/bulk/slides', methods=['POST'])
@APIRoute.standard(auth_required_flag=True, roles=[ROLES["TEACHER"], ROLES["ADMIN"]])
def create_bulk_slides():
    """
    Endpoint optimizado para creación masiva de diapositivas skeleton.

    Reglas y estructura:
    - Body: { "slides": [ { slide_object }, ... ] }
    - Cada slide_object debe contener:
        - topic_id: ObjectId (todas las slides deben pertenecer al mismo topic_id)
        - content_type: "slide" (estrictamente)
        - content: objeto con campos específicos de slide:
            - full_text: texto no vacío (se usará como base para la generación skeleton)
            - slide_plan: (opcional)
        - order: entero positivo. La secuencia debe ser consecutiva comenzando en 1 sin gaps.
        - parent_content_id: ObjectId (opcional)
        - Otros campos permitidos: interactive_data, resources, metadata, generation_prompt

    Validaciones realizadas por este endpoint (además de las del servicio):
    - Verifica que se haya enviado el array 'slides' y que no esté vacío
    - Todos los items deben ser content_type == 'slide'
    - Todas las slides deben compartir el mismo topic_id
    - Verifica que order sea una secuencia única y consecutiva comenzando en 1

    Responde con:
    - 201 + lista de IDs insertados en caso de éxito
    - 400 con mensaje de validación en caso de datos inválidos
    
    POLÍTICAS DE VALIDACIÓN ADICIONALES:
    - NO incluir campos 'provider' o 'model' en el payload.
    - 'slide_plan' (si se proporciona) debe ser string, no objeto.
    - HTML limitado a 150 KB por slide.
    - Cualquier violación de políticas resultará en error 400 con mensaje descriptivo.
    
    COMPORTAMIENTO IDEMPOTENTE (REGENERACIÓN):
    - Este endpoint implementa upsert por (topic_id, order): si ya existe un slide con el mismo topic_id y order, se actualizará en lugar de crear uno duplicado.
    - Si el nuevo lote tiene MENOS slides que una generación previa (ej: antes 10 slides, ahora 7), los slides sobrantes (8, 9, 10) se eliminarán automáticamente.
    - Esto permite regenerar contenido sin acumular slides duplicados o obsoletos.
    - Los IDs retornados pueden ser una mezcla de slides nuevos y actualizados.

    EJEMPLO DE REGENERACIÓN:
    1. Primera generación: crea slides con order 1-10 (10 slides)
    2. Segunda generación: envía slides con order 1-7 (7 slides)
       - Resultado: slides 1-7 se actualizan, slides 8-10 se eliminan
       - Retorna 7 IDs (algunos pueden ser los mismos de la primera generación si se reutilizaran)

    BREAKING CHANGE NOTICE:
    - Response field renamed from 'slide_ids' to 'content_ids' for consistency
    - 'slide_ids' field is deprecated and will be removed after 2025-12-31
    - During transition period (until 2025-12-31), both fields are returned with identical values
    - Update clients to use 'content_ids' instead of 'slide_ids' as soon as possible
    """
    try:
        data = request.json or {}
        slides_data = data.get('slides', [])

        if not slides_data or not isinstance(slides_data, list):
            return APIRoute.error(ErrorCodes.VALIDATION_ERROR, "Se requiere un array 'slides' con al menos un elemento")

        # Determine user id for creator_id
        user_id = getattr(request, 'user_id', None) or get_jwt_identity()

        # Basic validations before delegating to service to provide faster feedback
        first_topic = None
        seen_orders = []
        for idx, slide in enumerate(slides_data):
            if not isinstance(slide, dict):
                return APIRoute.error(ErrorCodes.VALIDATION_ERROR, f"Slide {idx+1} debe ser un objeto")

            # Ensure content_type is 'slide'
            if slide.get('content_type') != 'slide':
                return APIRoute.error(ErrorCodes.VALIDATION_ERROR, f"Slide {idx+1}: content_type debe ser 'slide'")

            # topic_id presence and consistency
            topic_id = slide.get('topic_id')
            if not topic_id:
                return APIRoute.error(ErrorCodes.VALIDATION_ERROR, f"Slide {idx+1}: topic_id es requerido")
            if first_topic is None:
                first_topic = topic_id
            else:
                if topic_id != first_topic:
                    return APIRoute.error(ErrorCodes.VALIDATION_ERROR, "Todas las diapositivas deben pertenecer al mismo topic_id")

            # order validations
            order = slide.get('order')
            if order is None or not isinstance(order, int) or order < 1:
                return APIRoute.error(ErrorCodes.VALIDATION_ERROR, f"Slide {idx+1}: order es requerido y debe ser un entero positivo")
            seen_orders.append(order)

            # content validations for slide fields
            content_obj = slide.get('content', {})
            if not isinstance(content_obj, dict):
                return APIRoute.error(ErrorCodes.VALIDATION_ERROR, f"Slide {idx+1}: 'content' debe ser un objeto")

            # full_text requirement for skeleton slides
            full_text = content_obj.get('full_text')
            if full_text is None or not isinstance(full_text, str) or not full_text.strip():
                return APIRoute.error(ErrorCodes.VALIDATION_ERROR, f"Slide {idx+1}: full_text es requerido y debe ser una cadena no vacía para crear skeleton")

            # template_snapshot validation removed - all configuration now in slide_plan

            # Attach creator_id for auditing
            slide['creator_id'] = user_id

        # Validate orders: unique and consecutive starting at 1
        seen_orders_sorted = sorted(seen_orders)
        if not seen_orders_sorted:
            return APIRoute.error(ErrorCodes.VALIDATION_ERROR, "No se encontraron órdenes válidos en las diapositivas")
        if seen_orders_sorted[0] != 1:
            return APIRoute.error(ErrorCodes.VALIDATION_ERROR, "La secuencia de 'order' debe comenzar en 1")
        for expected, actual in enumerate(seen_orders_sorted, start=1):
            if expected != actual:
                return APIRoute.error(ErrorCodes.VALIDATION_ERROR, f"La secuencia de 'order' debe ser consecutiva sin gaps. Esperado {expected}, encontrado {actual}")

        # template_snapshot logging removed - all configuration now in slide_plan
        logging.info(f"create_bulk_slides: Recibiendo {len(slides_data)} slides para topic {first_topic}")

        # Delegate to service optimized method
        success, result = content_service.create_bulk_slides_skeleton(slides_data)

        if success:
            response_data = {
                "content_ids": result,
                "slide_ids": result  # deprecated field for backward compatibility
            }

            resp = APIRoute.success(
                data=response_data,
                message=f"Se crearon {len(result)} slides skeleton exitosamente",
                status_code=201,
            )

            # Add deprecation headers for slide_ids field
            resp.headers['Deprecation'] = 'true'
            resp.headers['Sunset'] = '2025-12-31'
            resp.headers['Warning'] = '299 - "Field slide_ids is deprecated and will be removed. Use content_ids instead"'

            return resp
        else:
            # The service returns descriptive error strings; map to validation when applicable
            err_msg = result or "Error creando slides"
            return APIRoute.error(ErrorCodes.CREATION_ERROR, err_msg)

    except Exception as e:
        logging.error(f"Error creando slides en lote: {str(e)}")
        return APIRoute.error(
            ErrorCodes.SERVER_ERROR,
            "Error interno del servidor",
            status_code=500,
        )

@content_bp.route('/topic/<topic_id>', methods=['GET'])
@APIRoute.standard(auth_required_flag=True)
def get_topic_content(topic_id):
    """
    Obtiene todo el contenido de un tema.
    Query params: content_type (para filtrar por tipo específico)
    """
    try:
        content_type = request.args.get('content_type')
        
        contents = content_service.get_topic_content(topic_id, content_type)

        return APIRoute.success(data={"contents": contents})
        
    except Exception as e:
        import traceback
        logging.error(f"Error obteniendo contenido del tema: {str(e)}")
        logging.error(traceback.format_exc())
        return APIRoute.error(
            ErrorCodes.SERVER_ERROR,
            "Error interno del servidor",
            status_code=500,
        )

@content_bp.route('/topic/<topic_id>/check-duplicates', methods=['GET'])
@APIRoute.standard(auth_required_flag=True)
def check_topic_duplicates(topic_id):
    """
    Verifica si existen skeletons duplicados para un topic específico.

    Query params:
    - orders: lista de órdenes a verificar (ej: "1,2,3" o "1" multiple veces)

    Retorna:
    {
        "topic_id": "...",
        "requested_orders": [1, 2, 3],
        "duplicates_found": {
            "has_duplicates": true,
            "existing_orders": [1, 3],
            "existing_ids": ["...", "..."],
            "count": 2
        },
        "recommendation": "Los órdenes [1, 3] ya existen. Considere usar órdenes disponibles: [2, 4, 5]"
    }
    """
    try:
        # Validar topic_id
        if not ObjectId.is_valid(topic_id):
            return APIRoute.error(ErrorCodes.VALIDATION_ERROR, "ID de tema inválido")

        # Verify topic exists
        if not content_service.check_topic_exists(topic_id):
            return APIRoute.error(ErrorCodes.NOT_FOUND, "Topic no encontrado", status_code=404)

        # Obtener parámetro orders
        orders_param = request.args.get('orders', '')
        if not orders_param:
            return APIRoute.error(ErrorCodes.VALIDATION_ERROR, "Parámetro 'orders' es requerido")

        # Parsear órdenes
        try:
            orders = []
            for order_str in orders_param.split(','):
                order = int(order_str.strip())
                if order < 1:
                    return APIRoute.error(ErrorCodes.VALIDATION_ERROR, "Los órdenes deben ser números positivos")
                orders.append(order)
        except ValueError:
            return APIRoute.error(ErrorCodes.VALIDATION_ERROR, "El parámetro 'orders' debe contener números separados por comas")

        if not orders:
            return APIRoute.error(ErrorCodes.VALIDATION_ERROR, "Debe proporcionar al menos un orden válido")

        # Verificar duplicados
        duplicate_check = content_service.check_existing_skeletons(topic_id, orders)

        # Obtener órdenes disponibles si hay duplicados
        recommendation = None
        if duplicate_check.get('has_duplicates'):
            try:
                # Obtener todos los skeletons del topic
                existing_slides = content_service.get_topic_content(topic_id, content_type='slide')
                existing_orders = set(slide.get('order', 0) for slide in existing_slides if slide.get('status') == 'skeleton')

                # Encontrar órdenes disponibles
                requested_set = set(orders)
                available_orders = []
                max_order = max(max(existing_orders), max(requested_set)) if existing_orders or requested_set else 10

                for i in range(1, max_order + 10):
                    if i not in existing_orders and i not in requested_set:
                        available_orders.append(i)
                        if len(available_orders) >= len(duplicate_check.get('existing_orders', [])):
                            break

                if available_orders:
                    recommendation = f"Los órdenes {duplicate_check.get('existing_orders', [])} ya existen. Considere usar órdenes disponibles: {available_orders[:len(duplicate_check.get('existing_orders', []))]}"
            except Exception as e:
                logging.error(f"Error generando recomendación: {e}")
                recommendation = "Se encontraron duplicados. Verifique los órdenes existentes antes de crear."

        response_data = {
            "topic_id": topic_id,
            "requested_orders": orders,
            "duplicates_found": duplicate_check
        }

        if recommendation:
            response_data["recommendation"] = recommendation

        return APIRoute.success(data=response_data)

    except Exception as e:
        logging.error(f"Error verificando duplicados para topic {topic_id}: {str(e)}")
        return APIRoute.error(
            ErrorCodes.SERVER_ERROR,
            "Error interno del servidor",
            status_code=500,
        )

@content_bp.route('/topic/<topic_id>/interactive', methods=['GET'])
@APIRoute.standard(auth_required_flag=True)
def get_interactive_content(topic_id):
    """
    Obtiene solo contenido interactivo de un tema (games, simulations, quizzes).
    """
    try:
        contents = content_service.get_interactive_content(topic_id)

        return APIRoute.success(data={"interactive_contents": contents})
        
    except Exception as e:
        logging.error(f"Error obteniendo contenido interactivo: {str(e)}")
        return APIRoute.error(
            ErrorCodes.SERVER_ERROR,
            "Error interno del servidor",
            status_code=500,
        )

@content_bp.route('/<content_id>', methods=['GET'])
@APIRoute.standard(auth_required_flag=True)
def get_content_by_id(content_id):
    """
    Obtiene un contenido específico por su ID.
    """
    try:
        content = content_service.get_content(content_id)
        if not content:
            return APIRoute.error(
                ErrorCodes.NOT_FOUND,
                "Contenido no encontrado",
                status_code=404,
            )
        return APIRoute.success(data={"content": content})
    except Exception as e:
        logging.error(f"Error obteniendo contenido: {str(e)}")
        return APIRoute.error(
            ErrorCodes.SERVER_ERROR,
            "Error interno del servidor",
            status_code=500,
        )

@content_bp.route('/<content_id>', methods=['PUT'])
@APIRoute.standard(auth_required_flag=True, roles=[ROLES["TEACHER"], ROLES["ADMIN"]])
def update_content(content_id):
    """
    Actualiza contenido existente.
    
    POLÍTICAS:
    - No se permiten campos 'provider' o 'model' en actualizaciones.
    - 'slide_plan' debe ser string si se proporciona.
    """
    try:
        data = request.json
        
        success, result = content_service.update_content(content_id, data)

        if success:
            return APIRoute.success(data={"message": result})
        else:
            return APIRoute.error(ErrorCodes.UPDATE_ERROR, result)
            
    except Exception as e:
        logging.error(f"Error actualizando contenido: {str(e)}")
        return APIRoute.error(
            ErrorCodes.SERVER_ERROR,
            "Error interno del servidor",
            status_code=500,
        )

@content_bp.route('/<content_id>', methods=['DELETE'])
@APIRoute.standard(auth_required_flag=True, roles=[ROLES["TEACHER"], ROLES["ADMIN"]])
def delete_content(content_id):
    """
    Elimina contenido. Cuando se solicita en cascada, también elimina dependencias registradas
    (virtual_topic_contents, content_results, etc.).
    """
    try:
        payload = request.get_json(silent=True) or {}
        cascade_delete = payload.get('cascadeDelete', payload.get('cascade_delete'))
        if cascade_delete is None:
            cascade_delete = request.args.get('cascade', 'false')

        cascade = False
        if isinstance(cascade_delete, bool):
            cascade = cascade_delete
        elif isinstance(cascade_delete, str):
            cascade = cascade_delete.lower() in ('1', 'true', 'yes')

        success, result = content_service.delete_content(content_id, cascade=cascade)

        if success:
            return APIRoute.success(data={"message": result})
        else:
            return APIRoute.error(ErrorCodes.NOT_FOUND, result, status_code=404)
            
    except Exception as e:
        logging.error(f"Error eliminando contenido: {str(e)}")
        return APIRoute.error(
            ErrorCodes.SERVER_ERROR,
            "Error interno del servidor",
            status_code=500,
        )

# ============================================
# ENDPOINTS ESPECÍFICOS PARA ACTUALIZACIÓN PROGRESIVA DE DIAPOSITIVAS
# (PUT /api/content/{id}/html, PUT /api/content/{id}/narrative, GET /api/content/{id}/status)
# ============================================

@content_bp.route('/<content_id>/html', methods=['PUT'])
@APIRoute.standard(auth_required_flag=True, roles=[ROLES["TEACHER"], ROLES["ADMIN"]])
def update_slide_html(content_id):
    """
    Actualiza únicamente el campo content_html de una diapositiva.
    Body:
    {
        "content_html": "<div>...</div>"
    }
    Requisitos:
    - Autorización TEACHER/ADMIN
    - Valida existencia del contenido y que sea tipo 'slide'
    - Valida que content_html sea string y no vacío
    - Usa ContentService.update_slide_html para la actualización
    - Retorna detalles de estado tras la actualización
    """
    try:
        # Validar formato de ID
        if not ObjectId.is_valid(content_id):
            return APIRoute.error(ErrorCodes.VALIDATION_ERROR, "ID de contenido inválido")

        data = request.get_json() or {}
        content_html = data.get('content_html')

        if content_html is None:
            return APIRoute.error(ErrorCodes.VALIDATION_ERROR, "Campo 'content_html' requerido")
        if not isinstance(content_html, str):
            return APIRoute.error(ErrorCodes.VALIDATION_ERROR, "content_html debe ser una cadena de texto")

        # Comprobar existencia y tipo antes de intentar actualizar para mejorar mensajes de error
        current = content_service.get_content(content_id)
        if not current:
            return APIRoute.error(ErrorCodes.NOT_FOUND, "Contenido no encontrado", status_code=404)
        if current.get("content_type") != "slide":
            return APIRoute.error(ErrorCodes.VALIDATION_ERROR, "Solo se puede actualizar HTML para contenidos de tipo 'slide'")

        # Determinar updater_id (preferir request.user_id si existe)
        updater_id = getattr(request, 'user_id', None) or get_jwt_identity()

        success, message = content_service.update_slide_html(content_id, content_html, updater_id=updater_id)

        if success:
            # Obtener detalles de estado actualizados
            details = content_service.get_slide_status_details(content_id)
            return APIRoute.success(
                data={"status_details": details},
                message="HTML actualizado exitosamente"
            )
        else:
            # Mapear errores a códigos apropiados
            msg_lower = (message or "").lower()
            if "inválido" in msg_lower or "prohibida" in msg_lower or "mal formado" in msg_lower or "excede" in msg_lower or "demasiadas" in msg_lower or "vacío" in msg_lower or "uri" in msg_lower or "atributo" in msg_lower:
                return APIRoute.error(ErrorCodes.VALIDATION_ERROR, message)
            if "no encontrado" in msg_lower:
                return APIRoute.error(ErrorCodes.NOT_FOUND, message, status_code=404)
            # Fallback a error de actualización
            return APIRoute.error(ErrorCodes.UPDATE_ERROR, message)

    except Exception as e:
        logging.error(f"Error en endpoint update_slide_html para {content_id}: {str(e)}")
        return APIRoute.error(
            ErrorCodes.SERVER_ERROR,
            "Error interno del servidor",
            status_code=500,
        )

@content_bp.route('/<content_id>/full_html', methods=['PUT'])
@APIRoute.standard(auth_required_flag=True, roles=[ROLES["TEACHER"], ROLES["ADMIN"]])
def update_slide_full_html(content_id):
    """
    Guarda el documento HTML completo sin sanitización en content.full_html.
    Body:
    {
        "full_html": "<!DOCTYPE html>..."
    }
    - Verifica existencia y que sea slide
    - No sanitiza ni altera content.content_html
    - No cambia lógicas de estado (status)
    """
    try:
        if not ObjectId.is_valid(content_id):
            return APIRoute.error(ErrorCodes.VALIDATION_ERROR, "ID de contenido inválido")

        data = request.get_json() or {}
        full_html = data.get('full_html')

        if full_html is None:
            return APIRoute.error(ErrorCodes.VALIDATION_ERROR, "Campo 'full_html' requerido")
        if not isinstance(full_html, str):
            return APIRoute.error(ErrorCodes.VALIDATION_ERROR, "full_html debe ser una cadena de texto")

        current = content_service.get_content(content_id)
        if not current:
            return APIRoute.error(ErrorCodes.NOT_FOUND, "Contenido no encontrado", status_code=404)
        if current.get("content_type") != "slide":
            return APIRoute.error(ErrorCodes.VALIDATION_ERROR, "Solo se puede actualizar full_html para contenidos de tipo 'slide'")

        updater_id = getattr(request, 'user_id', None) or get_jwt_identity()

        success, message = content_service.update_slide_full_html(content_id, full_html, updater_id=updater_id)

        if success:
            details = content_service.get_slide_status_details(content_id)
            return APIRoute.success(
                data={"status_details": details},
                message="Full HTML guardado exitosamente"
            )
        else:
            msg_lower = (message or "").lower()
            if "inválido" in msg_lower or "excede" in msg_lower:
                return APIRoute.error(ErrorCodes.VALIDATION_ERROR, message)
            if "no encontrado" in msg_lower:
                return APIRoute.error(ErrorCodes.NOT_FOUND, message, status_code=404)
            return APIRoute.error(ErrorCodes.UPDATE_ERROR, message)

    except Exception as e:
        logging.error(f"Error en endpoint update_slide_full_html para {content_id}: {str(e)}")
        return APIRoute.error(
            ErrorCodes.SERVER_ERROR,
            "Error interno del servidor",
            status_code=500,
        )

@content_bp.route('/<content_id>/narrative', methods=['PUT'])
@APIRoute.standard(auth_required_flag=True, roles=[ROLES["TEACHER"], ROLES["ADMIN"]])
def update_slide_narrative(content_id):
    """
    Actualiza únicamente el campo narrative_text de una diapositiva.
    Body:
    {
        "narrative_text": "Texto narrativo..."
    }
    Requisitos:
    - Autorización TEACHER/ADMIN
    - Valida existencia del contenido y que sea tipo 'slide'
    - Valida que narrative_text sea string y no vacío y dentro de límites de tamaño
    - Usa ContentService.update_slide_narrative para la actualización
    - Retorna detalles de estado tras la actualización
    """
    try:
        if not ObjectId.is_valid(content_id):
            return APIRoute.error(ErrorCodes.VALIDATION_ERROR, "ID de contenido inválido")

        data = request.get_json() or {}
        narrative_text = data.get('narrative_text')

        if narrative_text is None:
            return APIRoute.error(ErrorCodes.VALIDATION_ERROR, "Campo 'narrative_text' requerido")
        if not isinstance(narrative_text, str):
            return APIRoute.error(ErrorCodes.VALIDATION_ERROR, "narrative_text debe ser una cadena de texto")

        # Comprobar existencia y tipo
        current = content_service.get_content(content_id)
        if not current:
            return APIRoute.error(ErrorCodes.NOT_FOUND, "Contenido no encontrado", status_code=404)
        if current.get("content_type") != "slide":
            return APIRoute.error(ErrorCodes.VALIDATION_ERROR, "Solo se puede actualizar narrativa para contenidos de tipo 'slide'")

        updater_id = getattr(request, 'user_id', None) or get_jwt_identity()

        success, message = content_service.update_slide_narrative(content_id, narrative_text, updater_id=updater_id)

        if success:
            details = content_service.get_slide_status_details(content_id)
            return APIRoute.success(
                data={"status_details": details},
                message="Narrativa actualizada exitosamente"
            )
        else:
            msg_lower = (message or "").lower()
            if "inválido" in msg_lower or "demasiado largo" in msg_lower or "vacío" in msg_lower:
                return APIRoute.error(ErrorCodes.VALIDATION_ERROR, message)
            if "no encontrado" in msg_lower:
                return APIRoute.error(ErrorCodes.NOT_FOUND, message, status_code=404)
            return APIRoute.error(ErrorCodes.UPDATE_ERROR, message)

    except Exception as e:
        logging.error(f"Error en endpoint update_slide_narrative para {content_id}: {str(e)}")
        return APIRoute.error(
            ErrorCodes.SERVER_ERROR,
            "Error interno del servidor",
            status_code=500,
        )

@content_bp.route('/<content_id>/status', methods=['GET'])
@APIRoute.standard(auth_required_flag=True)
def get_slide_status(content_id):
    """
    Consulta el estado actual de generación de una diapositiva específica.
    Retorna:
    {
        "content_id": "...",
        "status": "skeleton|html_ready|narrative_ready|draft|...",
        "has_content_html": bool,
        "has_narrative_text": bool,
        "has_full_text": bool,
        "content_html_length": int,
        "narrative_text_length": int,
        "full_text_length": int,
        "progress_estimate": 0-100,
        "created_at": "...",
        "updated_at": "...",
        "topic_id": "...",
        "last_updated_by": "..."
    }
    """
    try:
        if not ObjectId.is_valid(content_id):
            return APIRoute.error(ErrorCodes.VALIDATION_ERROR, "ID de contenido inválido")

        details = content_service.get_slide_status_details(content_id)
        if not details:
            return APIRoute.error(ErrorCodes.NOT_FOUND, "Contenido no encontrado", status_code=404)

        return APIRoute.success(data={"status_details": details})
    except Exception as e:
        logging.error(f"Error obteniendo estado de slide {content_id}: {str(e)}")
        return APIRoute.error(
            ErrorCodes.SERVER_ERROR,
            "Error interno del servidor",
            status_code=500,
        )

@content_bp.route('/topic/<topic_id>/slides/complete', methods=['GET'])
@APIRoute.standard(auth_required_flag=True)
def get_topic_complete_slides(topic_id):
    """
    Endpoint para obtener únicamente las slides completas (content_html + narrative_text).
    Query params:
        - limit (int, optional)
        - skip (int, optional)
    Retorna:
    {
        "slides": [...],
        "metadata": {
            "total_complete": int,
            "total_slides": int,
            "completion_percentage": float,
            "estimated_time_remaining_ms": int|null,
            "average_generation_time_ms": float|null
        }
    }
    """
    try:
        # Validate topic existence
        if not ObjectId.is_valid(topic_id) or not content_service.check_topic_exists(topic_id):
            return APIRoute.error(ErrorCodes.NOT_FOUND, "Topic no encontrado", status_code=404)

        # Parse pagination
        try:
            limit = request.args.get('limit', None)
            if limit is not None:
                limit = int(limit)
            skip = request.args.get('skip', 0)
            skip = int(skip) if skip is not None else 0
        except Exception:
            return APIRoute.error(ErrorCodes.VALIDATION_ERROR, "Parámetros de paginación inválidos")

        # Use specialized service method
        complete_res = content_service.get_complete_slides_only(topic_id, limit=limit, skip=skip)
        slides = complete_res.get('slides', [])
        total_complete = int(complete_res.get('total', len(slides)))

        # Total slides in topic (minimal projection)
        try:
            all_slides = content_service.get_topic_content(topic_id, content_type='slide', include_metadata=False)
            total_slides = len(all_slides)
        except Exception:
            total_slides = None

        completion_percentage = round((total_complete / total_slides * 100), 2) if total_slides and total_slides > 0 else 0.0

        # Try to obtain average/estimated time from generation status
        try:
            status_stats = content_service.get_slide_generation_status(topic_id)
            avg_time = status_stats.get('average_generation_time_ms')
            est_remaining = status_stats.get('estimated_time_remaining_ms')
        except Exception:
            avg_time = None
            est_remaining = None

        metadata = {
            "total_complete": total_complete,
            "total_slides": total_slides,
            "completion_percentage": completion_percentage,
            "average_generation_time_ms": avg_time,
            "estimated_time_remaining_ms": est_remaining
        }

        return APIRoute.success(data={"slides": slides, "metadata": metadata})
    except Exception as e:
        logging.error(f"Error en endpoint get_topic_complete_slides para topic {topic_id}: {str(e)}")
        return APIRoute.error(
            ErrorCodes.SERVER_ERROR,
            "Error interno del servidor",
            status_code=500,
        )

@content_bp.route('/topic/<topic_id>/slides/status', methods=['GET'])
@APIRoute.standard(auth_required_flag=True)
def get_topic_slides_status(topic_id):
    """
    Endpoint para verificar el progreso general de generación de slides de un topic.
    Query params:
        - render_engine (optional) : filtrar por motor de renderizado
        - group_by_parent (optional boolean)
    Respuesta:
        {
            "global": { ... }  # resultado de get_slide_generation_status()
            "filtered": { ... } # opcional, si se aplican filtros
        }
    """
    try:
        # Validate topic
        if not ObjectId.is_valid(topic_id) or not content_service.check_topic_exists(topic_id):
            return APIRoute.error(ErrorCodes.NOT_FOUND, "Topic no encontrado", status_code=404)

        render_engine = request.args.get('render_engine', None)
        group_by_parent_raw = request.args.get('group_by_parent', 'false')
        group_by_parent = str(group_by_parent_raw).lower() in ('1', 'true', 'yes', 'y')

        # Base (global) stats from existing method
        try:
            global_stats = content_service.get_slide_generation_status(topic_id) or {}
        except Exception as e:
            logging.error(f"Error obteniendo global slide generation status: {e}")
            global_stats = {}

        filtered_stats = None
        # If filters are provided, use optimized method to compute filtered stats
        if render_engine or group_by_parent:
            try:
                optimized = content_service.get_topic_slides_optimized(
                    topic_id=topic_id,
                    status_filter=None,
                    render_engine=render_engine,
                    group_by_parent=group_by_parent,
                    include_progress=True
                )
                filtered_stats = optimized.get('stats', {})
                # include by_parent if requested
                if group_by_parent:
                    filtered_stats = {
                        "stats": filtered_stats,
                        "by_parent": optimized.get('by_parent', {})
                    }
            except Exception as e:
                logging.error(f"Error obteniendo filtered stats para render_engine={render_engine} group_by_parent={group_by_parent}: {e}")
                filtered_stats = None

        response = {
            "global": global_stats
        }
        if filtered_stats is not None:
            response["filtered"] = filtered_stats
            response["filter_applied"] = {
                "render_engine": render_engine,
                "group_by_parent": group_by_parent
            }
        else:
            response["filter_applied"] = None

        return APIRoute.success(data=response)
    except Exception as e:
        logging.error(f"Error en endpoint get_topic_slides_status para topic {topic_id}: {str(e)}")
        return APIRoute.error(
            ErrorCodes.SERVER_ERROR,
            "Error interno del servidor",
            status_code=500,
        )

@content_bp.route('/topic/<topic_id>/slides/advanced', methods=['GET'])
@APIRoute.standard(auth_required_flag=True)
def get_topic_slides_advanced(topic_id):
    """
    Endpoint auxiliar que expone la funcionalidad de get_topic_slides_optimized / get_slides_with_advanced_filters.
    Query params:
        - status: comma-separated list of statuses (e.g. skeleton,html_ready,narrative_ready)
        - render_engine: filter by render engine
        - group_by_parent: boolean
        - include_progress: boolean
        - limit: int
        - skip: int
    """
    try:
        # Validate topic
        if not ObjectId.is_valid(topic_id) or not content_service.check_topic_exists(topic_id):
            return APIRoute.error(ErrorCodes.NOT_FOUND, "Topic no encontrado", status_code=404)

        # Parse params
        status_raw = request.args.get('status', None)
        status_list = None
        if status_raw:
            # support comma-separated or repeated params
            try:
                status_list = [s.strip() for s in status_raw.split(',') if s.strip()]
            except Exception:
                status_list = None

        render_engine = request.args.get('render_engine', None)
        group_by_parent_raw = request.args.get('group_by_parent', 'false')
        include_progress_raw = request.args.get('include_progress', 'true')
        try:
            group_by_parent = str(group_by_parent_raw).lower() in ('1', 'true', 'yes', 'y')
            include_progress = str(include_progress_raw).lower() in ('1', 'true', 'yes', 'y')
        except Exception:
            group_by_parent = False
            include_progress = True

        # Pagination
        try:
            limit_raw = request.args.get('limit', None)
            limit = int(limit_raw) if limit_raw is not None else None
        except Exception:
            return APIRoute.error(ErrorCodes.VALIDATION_ERROR, "Parámetro 'limit' inválido")
        try:
            skip_raw = request.args.get('skip', 0)
            skip = int(skip_raw) if skip_raw is not None else 0
        except Exception:
            return APIRoute.error(ErrorCodes.VALIDATION_ERROR, "Parámetro 'skip' inválido")

        # Use advanced filters method
        try:
            res = content_service.get_slides_with_advanced_filters(
                topic_id=topic_id,
                status=status_list,
                render_engine=render_engine,
                group_by_parent=group_by_parent,
                include_progress=include_progress,
                limit=limit,
                skip=skip
            )
            return APIRoute.success(data=res)
        except Exception as e:
            logging.error(f"Error ejecutando get_slides_with_advanced_filters: {e}")
            return APIRoute.error(ErrorCodes.SERVER_ERROR, "Error interno al obtener slides avanzados", status_code=500)

    except Exception as e:
        logging.error(f"Error en endpoint get_topic_slides_advanced para topic {topic_id}: {str(e)}")
        return APIRoute.error(
            ErrorCodes.SERVER_ERROR,
            "Error interno del servidor",
            status_code=500,
        )

# ============================================
# ENDPOINTS DE CONTENIDO PERSONALIZADO
# ============================================

@content_bp.route('/personalize', methods=['POST'])
@APIRoute.standard(auth_required_flag=True)
def personalize_content():
    """
    Personaliza contenido para un estudiante específico.
    
    Body:
    {
        "virtual_topic_id": "ObjectId",
        "content_id": "ObjectId",
        "student_id": "ObjectId",  // Opcional, por defecto usuario actual
        "cognitive_profile": {...}  // Opcional, se obtiene de BD si no se proporciona
    }
    """
    try:
        data = request.json
        student_id = data.get('student_id', request.user_id)
        
        # Obtener perfil cognitivo si no se proporciona
        cognitive_profile = data.get('cognitive_profile')
        if not cognitive_profile:
            profile = get_db().cognitive_profiles.find_one({"user_id": ObjectId(student_id)})
            if profile:
                cognitive_profile = profile
            else:
                return APIRoute.error(
                    ErrorCodes.NOT_FOUND,
                    "No se encontró perfil cognitivo para el estudiante",
                    status_code=404,
                )
        
        success, result = virtual_content_service.personalize_content(
            data['virtual_topic_id'],
            data['content_id'],
            student_id,
            cognitive_profile
        )

        if success:
            return APIRoute.success(
                data={"virtual_content_id": result},
                message="Contenido personalizado exitosamente",
                status_code=201,
            )
        else:
            return APIRoute.error(ErrorCodes.OPERATION_FAILED, result)
            
    except Exception as e:
        logging.error(f"Error personalizando contenido: {str(e)}")
        return APIRoute.error(
            ErrorCodes.SERVER_ERROR,
            "Error interno del servidor",
            status_code=500,
        )

@content_bp.route('/interaction', methods=['POST'])
@APIRoute.standard(auth_required_flag=True)
def track_interaction():
    """
    Registra interacción con contenido personalizado.
    
    Body:
    {
        "virtual_content_id": "ObjectId",
        "interaction_data": {
            "time_spent": 120,  // segundos
            "completion_percentage": 75.5,
            "completion_status": "in_progress|completed",
            "score": 85.0,  // Para contenido evaluable
            "interactions": [...]  // Detalles específicos de interacción
        }
    }
    """
    try:
        data = request.json
        
        success = virtual_content_service.track_interaction(
            data['virtual_content_id'],
            data['interaction_data']
        )

        if success:
            return APIRoute.success(
                data={"message": "Interacción registrada exitosamente"},
                message="Interacción registrada exitosamente",
            )
        else:
            return APIRoute.error(ErrorCodes.OPERATION_FAILED, "Error registrando interacción")
            
    except Exception as e:
        logging.error(f"Error registrando interacción: {str(e)}")
        return APIRoute.error(
            ErrorCodes.SERVER_ERROR,
            "Error interno del servidor",
            status_code=500,
        )

@content_bp.route('/results', methods=['POST'])
@APIRoute.standard(auth_required_flag=True)
def record_result():
    """
    Registra resultado de interacción con contenido (game, simulation, quiz, etc.)
    
    Body:
    {
        "virtual_content_id": "ObjectId",
        "student_id": "ObjectId",  // Opcional, por defecto usuario actual
        "session_data": {
            "score": 88.5,
            "completion_percentage": 95.0,
            "time_spent": 420,
            "content_specific_data": {...}  // Datos específicos según tipo de contenido
        },
        "learning_metrics": {
            "effectiveness": 0.87,
            "engagement": 0.92,
            "mastery_improvement": 0.15
        },
        "feedback": "Excelente trabajo...",
        "session_type": "completion|practice|assessment"
    }
    """
    try:
        data = request.json or {}
        fallback_student = getattr(request, 'user_id', None) or get_jwt_identity()
        data['student_id'] = data.get('student_id', fallback_student)

        success, result = content_result_service.record_result(data)

        if success:
            return APIRoute.success(
                data={"result_id": result},
                message="Resultado registrado exitosamente",
                status_code=201,
            )
        else:
            return APIRoute.error(ErrorCodes.OPERATION_FAILED, result)
            
    except Exception as e:
        logging.error(f"Error registrando resultado: {str(e)}")
        return APIRoute.error(
            ErrorCodes.SERVER_ERROR,
            "Error interno del servidor",
            status_code=500,
        )

@content_bp.route('/results/student/<student_id>', methods=['GET'])
@APIRoute.standard(auth_required_flag=True)
def get_student_results(student_id):
    """
    Obtiene resultados de un estudiante.
    Query params: 
        - virtual_content_id (filtrar por contenido virtual específico - clave principal)
        - content_type (filtrar por tipo de contenido - para compatibilidad)
    """
    try:
        # Verificar permisos: solo el mismo estudiante o profesores/admin
        current_user = get_jwt_identity()
        if current_user != student_id and g.user.get('role') not in [ROLES["TEACHER"], ROLES["ADMIN"]]:
            return APIRoute.error(
                ErrorCodes.PERMISSION_DENIED,
                "No autorizado para ver estos resultados",
                status_code=403,
            )
        
        virtual_content_id = request.args.get('virtual_content_id')
        content_type = request.args.get('content_type')
        evaluation_id = request.args.get('evaluation_id')
        topic_id = request.args.get('topic_id')

        results = content_result_service.get_student_results(
            student_id,
            content_type=content_type,
            virtual_content_id=virtual_content_id,
            evaluation_id=evaluation_id,
            topic_id=topic_id,
        )

        return APIRoute.success(data={"results": results})
        
    except Exception as e:
        logging.error(f"Error obteniendo resultados del estudiante: {str(e)}")
        return APIRoute.error(
            ErrorCodes.SERVER_ERROR,
            "Error interno del servidor",
            status_code=500,
        )

@content_bp.route('/results/my', methods=['GET'])
@APIRoute.standard(auth_required_flag=True)
def get_my_results():
    """
    Obtiene resultados del usuario actual.
    Query params: content_type
    """
    try:
        student_id = get_jwt_identity()
        content_type = request.args.get('content_type')
        topic_id = request.args.get('topic_id')
        results = content_result_service.get_student_results(
            student_id,
            content_type=content_type,
            topic_id=topic_id,
        )

        return APIRoute.success(data={"results": results})
        
    except Exception as e:
        logging.error(f"Error obteniendo mis resultados: {str(e)}")
        return APIRoute.error(
            ErrorCodes.SERVER_ERROR,
            "Error interno del servidor",
            status_code=500,
        )

# ============================================
# ENDPOINTS DE COMPATIBILIDAD (LEGACY)
# ============================================

@content_bp.route('/games', methods=['POST'])
@APIRoute.standard(auth_required_flag=True, roles=[ROLES["TEACHER"], ROLES["ADMIN"]])
def create_game_legacy():
    """
    DEPRECATED - Endpoint de compatibilidad para crear juegos.
    
    Este endpoint será eliminado en la próxima versión.
    No permite creación de nuevos games por defecto. Use templates interactivos.
    
    Para casos excepcionales, puede usar ?force_legacy=true pero solo ADMIN puede usar ese flag.
    """
    warnings.warn(
        "El endpoint /api/content/games está obsoleto. Usar /api/content/ con content_type='game'",
        DeprecationWarning,
        stacklevel=2
    )
    
    try:
        # Evaluate force_legacy param
        force_raw = request.args.get('force_legacy', 'false')
        force_legacy = str(force_raw).lower() in ('1', 'true', 'yes', 'y')

        user_id = getattr(request, 'user_id', None) or get_jwt_identity()
        user_role = None
        try:
            user_role = g.user.get('role') if getattr(g, 'user', None) else None
        except Exception:
            user_role = None

        # If not forcing legacy creation, block creation and inform user of deprecation
        if not force_legacy:
            msg = ("El endpoint para crear 'game' está en desuso y no admite la creación de nuevos juegos. "
                   "Por favor migre a plantillas interactivas (interactive_template) o use "
                   "POST /api/content/from-template para crear contenido interactivo. "
                   "Ver: GET /api/content/games/migration-info para detalles de migración.")
            logging.warning(f"Blocked create_game_legacy attempt by user={user_id} role={user_role} - deprecation enforced")
            return _deprecation_response(msg, recommendation="Use interactive templates via /api/content/from-template", status_code=410)

        # If force_legacy requested, ensure user is ADMIN
        if force_legacy and user_role != ROLES["ADMIN"]:
            logging.warning(f"Unauthorized force_legacy create_game_legacy attempt by user={user_id} role={user_role}")
            return _deprecation_response("El flag force_legacy está reservado para administradores.", recommendation=None, status_code=403)

        # Allow legacy creation only for ADMIN with explicit flag. Proceed to create content but mark as deprecated creation.
        data = request.json or {}
        data['content_type'] = 'game'
        data['creator_id'] = user_id

        # Compute creator roles for validation
        creator_roles = [user_role] if user_role else []

        logging.info(f"Creating legacy game by admin user={user_id}. Payload keys: {list(data.keys())}")

        # Pass allow_deprecated=True and creator_roles to service
        success, result = content_service.create_content(data, allow_deprecated=True, creator_roles=creator_roles)

        if success:
            resp = APIRoute.success(
                data={"game_id": result},
                message="Juego legacy creado exitosamente (uso de endpoint deprecated)",
                status_code=201,
            )
            # attach deprecation headers to the success response as well
            try:
                resp.headers['Deprecation'] = 'true'
                resp.headers['Sunset'] = '2025-12-31'
                resp.headers['Warning'] = '299 - "Deprecated API; use templates instead"'
            except Exception:
                pass
            return resp
        else:
            logging.error(f"Failed to create legacy game (admin attempt) user={user_id} error={result}")
            return APIRoute.error(ErrorCodes.CREATION_ERROR, result)
            
    except Exception as e:
        logging.error(f"Error creando juego (legacy): {str(e)}")
        return APIRoute.error(
            ErrorCodes.SERVER_ERROR,
            "Error interno del servidor",
            status_code=500,
        )

@content_bp.route('/simulations', methods=['POST'])
@APIRoute.standard(auth_required_flag=True, roles=[ROLES["TEACHER"], ROLES["ADMIN"]])
def create_simulation_legacy():
    """
    DEPRECATED - Endpoint de compatibilidad para crear simulaciones.
    
    Este endpoint será eliminado en la próxima versión.
    No permite creación de nuevas simulations por defecto. Use plantillas de simulación.
    
    Parámetros:
    - ?force_legacy=true : permite crear simulaciones legacy solo para ADMIN
    """
    warnings.warn(
        "El endpoint /api/content/simulations está obsoleto. Usar /api/content/ con content_type='simulation'",
        DeprecationWarning,
        stacklevel=2
    )
    
    try:
        # Evaluate force_legacy param
        force_raw = request.args.get('force_legacy', 'false')
        force_legacy = str(force_raw).lower() in ('1', 'true', 'yes', 'y')

        user_id = getattr(request, 'user_id', None) or get_jwt_identity()
        user_role = None
        try:
            user_role = g.user.get('role') if getattr(g, 'user', None) else None
        except Exception:
            user_role = None

        if not force_legacy:
            msg = ("El endpoint para crear 'simulation' está en desuso y no admite la creación de nuevas simulaciones. "
                   "Use plantillas de simulación (interactive_simulation_template) o "
                   "POST /api/content/from-template. Ver: GET /api/content/simulations/migration-info para detalles.")
            logging.warning(f"Blocked create_simulation_legacy attempt by user={user_id} role={user_role} - deprecation enforced")
            return _deprecation_response(msg, recommendation="Use simulation templates via /api/content/from-template", status_code=410)

        # If force_legacy requested, ensure user is ADMIN
        if force_legacy and user_role != ROLES["ADMIN"]:
            logging.warning(f"Unauthorized force_legacy create_simulation_legacy attempt by user={user_id} role={user_role}")
            return _deprecation_response("El flag force_legacy está reservado para administradores.", recommendation=None, status_code=403)

        # Allow legacy creation only for ADMIN with explicit flag. Proceed to create content but mark as deprecated creation.
        data = request.json or {}
        data['content_type'] = 'simulation'
        data['creator_id'] = user_id

        # Compute creator roles for validation
        creator_roles = [user_role] if user_role else []

        logging.info(f"Creating legacy simulation by admin user={user_id}. Payload keys: {list(data.keys())}")

        success, result = content_service.create_content(data, allow_deprecated=True, creator_roles=creator_roles)

        if success:
            resp = APIRoute.success(
                data={"simulation_id": result},
                message="Simulación legacy creada exitosamente (uso de endpoint deprecated)",
                status_code=201,
            )
            try:
                resp.headers['Deprecation'] = 'true'
                resp.headers['Sunset'] = '2025-12-31'
                resp.headers['Warning'] = '299 - "Deprecated API; use templates instead"'
            except Exception:
                pass
            return resp
        else:
            logging.error(f"Failed to create legacy simulation (admin attempt) user={user_id} error={result}")
            return APIRoute.error(ErrorCodes.CREATION_ERROR, result)
            
    except Exception as e:
        logging.error(f"Error creando simulación (legacy): {str(e)}")
        return APIRoute.error(
            ErrorCodes.SERVER_ERROR,
            "Error interno del servidor",
            status_code=500,
        )

@content_bp.route('/quizzes', methods=['POST'])
@APIRoute.standard(auth_required_flag=True, roles=[ROLES["TEACHER"], ROLES["ADMIN"]])
def create_quiz_legacy():
    """
    DEPRECATED - Endpoint de compatibilidad para crear quizzes.
    
    Este endpoint será eliminado en la próxima versión.
    Usar: POST /api/content/ con content_type="quiz"
    
    Nota: Quizzes no están siendo deshabilitados en esta fase, pero el endpoint se marca como deprecated.
    Se emiten warnings y cabeceras de deprecación.
    """
    warnings.warn(
        "El endpoint /api/content/quizzes está obsoleto. Usar /api/content/ con content_type='quiz'",
        DeprecationWarning,
        stacklevel=2
    )
    
    try:
        data = request.json
        data['content_type'] = 'quiz'
        user_id = getattr(request, 'user_id', None) or get_jwt_identity()
        data['creator_id'] = user_id
        
        success, result = content_service.create_content(data)

        if success:
            resp = APIRoute.success(
                data={"quiz_id": result},
                message="Quiz creado exitosamente",
                status_code=201,
            )
            # Attach deprecation headers as advisory (still allows creation)
            try:
                resp.headers['Deprecation'] = 'true'
                resp.headers['Sunset'] = '2025-12-31'
                resp.headers['Warning'] = '299 - "Deprecated API; prefer unified /api/content endpoint"'
            except Exception:
                pass
            logging.info(f"Legacy quiz created by user={user_id or 'unknown'}")
            return resp
        else:
            return APIRoute.error(ErrorCodes.CREATION_ERROR, result)
            
    except Exception as e:
        logging.error(f"Error creando quiz (legacy): {str(e)}")
        return APIRoute.error(
            ErrorCodes.SERVER_ERROR,
            "Error interno del servidor",
            status_code=500,
        )

@content_bp.route('/games/migration-info', methods=['GET'])
@APIRoute.standard(auth_required_flag=True)
def get_games_migration_info():
    """
    Retorna información y sugerencias para migrar juegos legacy a plantillas interactivas.
    Query params:
        - topic_id (opcional): si se provee, se analizan los juegos de ese topic
    """
    try:
        topic_id = request.args.get('topic_id', None)
        suggestions = content_service.get_legacy_content_migration_suggestions(topic_id=topic_id, content_type='game')
        return APIRoute.success(data={"migration_info": suggestions})
    except Exception as e:
        logging.error(f"Error obteniendo migration-info para games: {e}")
        return APIRoute.error(ErrorCodes.SERVER_ERROR, "Error interno del servidor", status_code=500)

@content_bp.route('/simulations/migration-info', methods=['GET'])
@APIRoute.standard(auth_required_flag=True)
def get_simulations_migration_info():
    """
    Retorna información y sugerencias para migrar simulaciones legacy a plantillas de simulación.
    Query params:
        - topic_id (opcional): si se provee, se analizan las simulaciones de ese topic
    """
    try:
        topic_id = request.args.get('topic_id', None)
        suggestions = content_service.get_legacy_content_migration_suggestions(topic_id=topic_id, content_type='simulation')
        return APIRoute.success(data={"migration_info": suggestions})
    except Exception as e:
        logging.error(f"Error obteniendo migration-info para simulations: {e}")
        return APIRoute.error(ErrorCodes.SERVER_ERROR, "Error interno del servidor", status_code=500)

@content_bp.route('/deprecated/status', methods=['GET'])
@APIRoute.standard(auth_required_flag=True)
def get_deprecated_status():
    """
    Retorna el estado general de deprecación y estadísticas de contenidos legacy.
    Query params:
        - topic_id (optional): filtrar por topic
        - module_id (optional): filtrar por módulo
    """
    try:
        topic_id = request.args.get('topic_id', None)
        module_id = request.args.get('module_id', None)
        try:
            stats = content_service.check_deprecated_content_usage(topic_id=topic_id, module_id=module_id)
        except TypeError:
            # fallback if service uses different signature
            try:
                stats = content_service.check_deprecated_content_usage(topic_id)
            except TypeError:
                stats = content_service.check_deprecated_content_usage()
        return APIRoute.success(data={"deprecated_status": stats})
    except Exception as e:
        logging.error(f"Error obteniendo deprecated status: {e}")
        return APIRoute.error(ErrorCodes.SERVER_ERROR, "Error interno del servidor", status_code=500)

# ============================================
# ENDPOINTS DE INTEGRACIÓN CON PLANTILLAS
# ============================================

@content_bp.route('/from-template', methods=['POST'])
@APIRoute.standard(auth_required_flag=True)
@role_required([ROLES["TEACHER"], ROLES["ADMIN"]])
def create_content_from_template():
    """
    Crea contenido basado en una plantilla.
    
    Body:
    {
        "template_id": "template_id",
        "topic_id": "topic_id", 
        "props": {"param1": "value1"},
        "assets": [{"id": "asset1", "name": "imagen.jpg", "url": "...", "type": "image"}],
        "learning_mix": {"V": 70, "A": 10, "K": 15, "R": 5},
        "content_type": "diagram", // opcional
        "template_metadata": {
            "interactive_summary": "...",
            "learning_objectives": ["..."],
            "estimated_duration_seconds": 300,
            "interaction_mode": "game"
        }
    }
    """
    try:
        user_id = get_jwt_identity()
        data = request.get_json()
        
        if not data:
            return APIRoute.error(ErrorCodes.VALIDATION_ERROR, "Datos requeridos")
        
        # Validar campos requeridos
        required_fields = ["template_id", "topic_id"]
        for field in required_fields:
            if field not in data:
                return APIRoute.error(ErrorCodes.VALIDATION_ERROR, f"Campo requerido: {field}")
        
        # Crear contenido desde plantilla
        template_metadata = data.get("template_metadata") if "template_metadata" in data else data.get("metadata")
        success, result = template_integration_service.create_content_from_template(
            template_id=data["template_id"],
            topic_id=data["topic_id"],
            props=data.get("props"),
            assets=data.get("assets"),
            learning_mix=data.get("learning_mix"),
            content_type=data.get("content_type"),
            template_metadata=template_metadata,
            created_by=user_id
        )
        
        if success:
            return APIRoute.success(
                data={"content_id": result},
                message="Contenido creado desde plantilla exitosamente"
            )
        else:
            return APIRoute.error(ErrorCodes.BUSINESS_LOGIC_ERROR, result)
            
    except Exception as e:
        logging.error(f"Error creando contenido desde plantilla: {str(e)}")
        return APIRoute.error(
            ErrorCodes.SERVER_ERROR,
            "Error interno del servidor",
            status_code=500,
        )

@content_bp.route('/<content_id>/template-data', methods=['GET'])
@APIRoute.standard(auth_required_flag=True)
def get_template_content_data(content_id):
    """
    Obtiene datos enriquecidos de contenido basado en plantilla.
    """
    try:
        content = template_integration_service.get_template_content(content_id)
        
        if not content:
            return APIRoute.error(ErrorCodes.NOT_FOUND, "Contenido no encontrado", status_code=404)
        
        return APIRoute.success(data={"content": content})
        
    except Exception as e:
        logging.error(f"Error obteniendo datos de plantilla: {str(e)}")
        return APIRoute.error(
            ErrorCodes.SERVER_ERROR,
            "Error interno del servidor",
            status_code=500,
        )

@content_bp.route('/<content_id>/template-update', methods=['PUT'])
@APIRoute.standard(auth_required_flag=True)
@role_required([ROLES["TEACHER"], ROLES["ADMIN"]])
def update_template_content(content_id):
    """
    Actualiza contenido basado en plantilla.
    
    Body:
    {
        "props": {"param1": "new_value"},
        "assets": [...],
        "learning_mix": {...},
        "status": "active"
    }
    """
    try:
        data = request.get_json()
        
        if not data:
            return APIRoute.error(ErrorCodes.VALIDATION_ERROR, "Datos requeridos")
        
        success, message = template_integration_service.update_template_content(content_id, data)
        
        if success:
            return APIRoute.success(message=message)
        else:
            return APIRoute.error(ErrorCodes.BUSINESS_LOGIC_ERROR, message)
            
    except Exception as e:
        logging.error(f"Error actualizando contenido de plantilla: {str(e)}")
        return APIRoute.error(
            ErrorCodes.SERVER_ERROR,
            "Error interno del servidor",
            status_code=500,
        )

@content_bp.route('/<content_id>/template-publish', methods=['POST'])
@APIRoute.standard(auth_required_flag=True)
@role_required([ROLES["TEACHER"], ROLES["ADMIN"]])
def publish_template_content(content_id):
    """
    Publica contenido basado en plantilla.
    """
    try:
        success, message = template_integration_service.publish_template_content(content_id)
        
        if success:
            return APIRoute.success(message=message)
        else:
            return APIRoute.error(ErrorCodes.BUSINESS_LOGIC_ERROR, message)
            
    except Exception as e:
        logging.error(f"Error publicando contenido de plantilla: {str(e)}")
        return APIRoute.error(
            ErrorCodes.SERVER_ERROR,
            "Error interno del servidor",
            status_code=500,
        )

@content_bp.route('/templates/available/<topic_id>', methods=['GET'])
@APIRoute.standard(auth_required_flag=True)
def get_available_templates_for_topic(topic_id):
    """
    Obtiene plantillas disponibles para usar en un tema.
    """
    try:
        user_id = get_jwt_identity()
        
        templates = template_integration_service.get_available_templates_for_topic(topic_id, user_id)
        
        return APIRoute.success(data={
            "templates": templates,
            "total": len(templates)
        })
        
    except Exception as e:
        logging.error(f"Error obteniendo plantillas disponibles: {str(e)}")
        return APIRoute.error(
            ErrorCodes.SERVER_ERROR,
            "Error interno del servidor",
            status_code=500,
        )

@content_bp.route('/<content_id>/migrate-to-template', methods=['POST'])
@APIRoute.standard(auth_required_flag=True)
@role_required([ROLES["TEACHER"], ROLES["ADMIN"]])
def migrate_content_to_template(content_id):
    """
    Migra contenido legacy existente para usar una plantilla.
    
    Body:
    {
        "template_id": "template_id"
    }
    """
    try:
        data = request.get_json()
        
        if not data or "template_id" not in data:
            return APIRoute.error(ErrorCodes.VALIDATION_ERROR, "template_id requerido")
        
        success, message = template_integration_service.migrate_content_to_template(
            content_id, data["template_id"]
        )
        
        if success:
            return APIRoute.success(message=message)
        else:
            return APIRoute.error(ErrorCodes.BUSINESS_LOGIC_ERROR, message)
            
    except Exception as e:
        logging.error(f"Error migrando contenido a plantilla: {str(e)}")
        return APIRoute.error(
            ErrorCodes.SERVER_ERROR,
            "Error interno del servidor",
            status_code=500,
        )

@content_bp.route('/template-feedback', methods=['POST'])
@APIRoute.standard(auth_required_flag=True)
def submit_template_feedback():
    """
    Envía feedback sobre el uso de plantillas al sistema de RL.
    """
    try:
        data = request.get_json()
        
        # Validar campos requeridos
        required_fields = ['student_id', 'topic_id', 'slide_id', 'template_id', 
                          'engagement_score', 'completion_score', 'satisfaction_score']
        
        for field in required_fields:
            if field not in data:
                return APIRoute.error(ErrorCodes.VALIDATION_ERROR, f"Campo requerido faltante: {field}")
        
        # Validar rangos de scores (0.0 - 1.0)
        score_fields = ['engagement_score', 'completion_score', 'satisfaction_score']
        for field in score_fields:
            if not (0.0 <= data[field] <= 1.0):
                return APIRoute.error(ErrorCodes.VALIDATION_ERROR, f"{field} debe estar entre 0.0 y 1.0")
        
        success = content_service.submit_template_feedback(
            data['student_id'], data['topic_id'], data['slide_id'],
            data['template_id'], data['engagement_score'],
            data['completion_score'], data['satisfaction_score']
        )
        
        if success:
            return APIRoute.success(message="Feedback enviado exitosamente al sistema de RL")
        else:
            return APIRoute.error(ErrorCodes.BUSINESS_LOGIC_ERROR, "Error al enviar feedback al sistema de RL")
            
    except Exception as e:
        logging.error(f"Error submitting template feedback: {str(e)}")
        return APIRoute.error(
            ErrorCodes.SERVER_ERROR,
            "Error interno del servidor",
            status_code=500,
        )

# Rutas para contenido embebido vs separado
@content_bp.route('/embedding/analyze', methods=['POST'])
@APIRoute.standard(auth_required_flag=True)
def analyze_embedding_strategy():
    """
    Analiza si un contenido debe ser embebido o separado de una diapositiva.
    """
    try:
        data = request.get_json()
        
        if 'slide_id' not in data or 'content_id' not in data:
            return APIRoute.error(ErrorCodes.VALIDATION_ERROR, "slide_id y content_id son requeridos")
        
        analysis = content_service.analyze_content_embedding_strategy(
            data['slide_id'], data['content_id']
        )
        
        return APIRoute.success(data={"analysis": analysis})
        
    except Exception as e:
        logging.error(f"Error analyzing embedding strategy: {str(e)}")
        return APIRoute.error(
            ErrorCodes.SERVER_ERROR,
            "Error interno del servidor",
            status_code=500,
        )

@content_bp.route('/embedding/embed', methods=['POST'])
@APIRoute.standard(auth_required_flag=True, roles=[ROLES["TEACHER"], ROLES["ADMIN"]])
def embed_content():
    """
    Embebe un contenido dentro de una diapositiva.
    """
    try:
        data = request.get_json()
        
        if 'slide_id' not in data or 'content_id' not in data:
            return APIRoute.error(ErrorCodes.VALIDATION_ERROR, "slide_id y content_id son requeridos")
        
        embed_position = data.get('embed_position', 'bottom')
        
        result = content_service.embed_content_in_slide(
            data['slide_id'], data['content_id'], embed_position
        )
        
        return APIRoute.success(data={"result": result})
        
    except Exception as e:
        logging.error(f"Error embedding content: {str(e)}")
        return APIRoute.error(
            ErrorCodes.SERVER_ERROR,
            "Error interno del servidor",
            status_code=500,
        )

@content_bp.route('/embedding/extract', methods=['POST'])
@APIRoute.standard(auth_required_flag=True, roles=[ROLES["TEACHER"], ROLES["ADMIN"]])
def extract_embedded_content():
    """
    Extrae un contenido embebido y lo convierte en contenido separado.
    """
    try:
        data = request.get_json()
        
        if 'slide_id' not in data or 'content_id' not in data:
            return APIRoute.error(ErrorCodes.VALIDATION_ERROR, "slide_id y content_id son requeridos")
        
        result = content_service.extract_embedded_content(
            data['slide_id'], data['content_id']
        )
        
        return APIRoute.success(data={"result": result})
        
    except Exception as e:
        logging.error(f"Error extracting embedded content: {str(e)}")
        return APIRoute.error(
            ErrorCodes.SERVER_ERROR,
            "Error interno del servidor",
            status_code=500,
        )

@content_bp.route('/embedding/recommendations/<topic_id>', methods=['GET'])
@APIRoute.standard(auth_required_flag=True)
def get_embedding_recommendations(topic_id):
    """
    Obtiene recomendaciones de embedding para todos los contenidos de un tema.
    """
    try:
        recommendations = content_service.get_embedding_recommendations(topic_id)
        
        return APIRoute.success(data={"recommendations": recommendations})
        
    except Exception as e:
        logging.error(f"Error getting embedding recommendations: {str(e)}")
        return APIRoute.error(
            ErrorCodes.SERVER_ERROR,
            "Error interno del servidor",
            status_code=500,
        )

@content_bp.route('/embedding/statistics/<topic_id>', methods=['GET'])
@APIRoute.standard(auth_required_flag=True)
def get_embedding_statistics(topic_id):
    """
    Obtiene estadísticas de embedding para un tema.
    """
    try:
        statistics = content_service.get_embedding_statistics(topic_id)
        
        return APIRoute.success(data={"statistics": statistics})
        
    except Exception as e:
        logging.error(f"Error getting embedding statistics: {str(e)}")
        return APIRoute.error(
            ErrorCodes.SERVER_ERROR,
            "Error interno del servidor",
            status_code=500,
        )

# ============================================
# ENDPOINTS DE GESTIÓN MANUAL DE SLIDES
# ============================================

@content_bp.route('/slides', methods=['POST'])
@APIRoute.standard(auth_required_flag=True, roles=[ROLES["TEACHER"], ROLES["ADMIN"]])
def create_slide_manual():
    """
    Crea una slide manualmente (no desde skeleton).
    
    Body:
    {
        "topic_id": "ObjectId",
        "title": "Título de la slide",
        "content_html": "<!DOCTYPE html>...",
        "order": 5,  // opcional, se calcula si no se proporciona
        "parent_content_id": "ObjectId",  // opcional, para variantes
        "status": "ready",  // opcional, default: 'ready'. Usar 'ready' para evitar polling de generación
        "content": {  // campos adicionales opcionales
            "baseline_mix": {"V": 40, "A": 40, "K": 15, "R": 5},
            "interactive_summary": "...",
            "attachment": {...}
        }
    }
    """
    try:
        data = request.json or {}
        user_id = getattr(request, 'user_id', None) or get_jwt_identity()
        
        # Validar campos requeridos
        if not data.get('topic_id'):
            return APIRoute.error(ErrorCodes.VALIDATION_ERROR, "topic_id es requerido")
        if not data.get('content_html'):
            return APIRoute.error(ErrorCodes.VALIDATION_ERROR, "content_html es requerido")
        
        # Construir datos del contenido
        content_data = {
            'topic_id': data['topic_id'],
            'content_type': 'slide',
            'creator_id': user_id,
            'status': data.get('status', 'ready'),  # Status por defecto 'ready' para slides manuales
            'render_engine': 'raw_html',  # Slides manuales siempre usan raw_html
            'content': {
                'title': data.get('title', 'Nueva Slide'),
                'content_html': data['content_html'],
                'status': data.get('status', 'ready'),  # También en content para consistencia
                **(data.get('content', {}))
            }
        }
        
        # Agregar order si se proporciona
        if 'order' in data:
            content_data['order'] = data['order']
            content_data['content']['order'] = data['order']  # También en content
        
        # Agregar parent_content_id si se proporciona
        if data.get('parent_content_id'):
            content_data['parent_content_id'] = data['parent_content_id']
            content_data['content']['parent_content_id'] = data['parent_content_id']
        
        logging.info(f"[SlideManual] Creando slide manual para topic {data['topic_id']}")
        
        success, result = content_service.create_content(content_data)
        
        if success:
            logging.info(f"[SlideManual] Slide creada con ID: {result}")
            return APIRoute.success(
                data={"id": result, "content_id": result},
                message="Slide creada exitosamente",
                status_code=201
            )
        else:
            logging.error(f"[SlideManual] Error creando slide: {result}")
            return APIRoute.error(ErrorCodes.CREATION_ERROR, result)
            
    except Exception as e:
        logging.error(f"[SlideManual] Error: {str(e)}")
        return APIRoute.error(
            ErrorCodes.SERVER_ERROR,
            "Error interno del servidor",
            status_code=500
        )

@content_bp.route('/slides/<slide_id>', methods=['PATCH'])
@APIRoute.standard(auth_required_flag=True, roles=[ROLES["TEACHER"], ROLES["ADMIN"]])
def update_slide_manual(slide_id):
    """
    Actualiza una slide existente.
    
    Body:
    {
        "title": "Nuevo título",
        "content_html": "<!DOCTYPE html>..."
    }
    """
    try:
        data = request.json or {}
        user_id = getattr(request, 'user_id', None) or get_jwt_identity()
        
        if not ObjectId.is_valid(slide_id):
            return APIRoute.error(ErrorCodes.VALIDATION_ERROR, "ID de slide inválido")
        
        # Verificar que existe
        current = content_service.get_content(slide_id)
        if not current:
            return APIRoute.error(ErrorCodes.NOT_FOUND, "Slide no encontrada", status_code=404)
        
        if current.get('content_type') != 'slide':
            return APIRoute.error(ErrorCodes.VALIDATION_ERROR, "El contenido no es una slide")
        
        # Construir update
        update_data = {}
        if 'title' in data:
            update_data['content.title'] = data['title']
        if 'content_html' in data:
            update_data['content.content_html'] = data['content_html']
        if 'order' in data:
            update_data['order'] = data['order']
        
        update_data['updated_at'] = datetime.datetime.utcnow()
        update_data['last_updated_by'] = user_id
        
        if not update_data:
            return APIRoute.error(ErrorCodes.VALIDATION_ERROR, "No hay campos para actualizar")
        
        logging.info(f"[SlideManual] Actualizando slide {slide_id}")
        
        success, result = content_service.update_content(slide_id, update_data)
        
        if success:
            return APIRoute.success(
                data={"id": slide_id},
                message="Slide actualizada exitosamente"
            )
        else:
            return APIRoute.error(ErrorCodes.UPDATE_ERROR, result)
            
    except Exception as e:
        logging.error(f"[SlideManual] Error actualizando slide: {str(e)}")
        return APIRoute.error(
            ErrorCodes.SERVER_ERROR,
            "Error interno del servidor",
            status_code=500
        )

@content_bp.route('/slides/<slide_id>', methods=['DELETE'])
@APIRoute.standard(auth_required_flag=True, roles=[ROLES["TEACHER"], ROLES["ADMIN"]])
def delete_slide_manual(slide_id):
    """
    Elimina una slide con opción de cascada.
    
    Query params:
    - cascade: "true" para eliminar también las variantes hijas
    
    Si se elimina una slide padre con cascade=true, todas sus variantes se eliminan.
    Después de eliminar, las demás slides se reordenan automáticamente.
    """
    try:
        if not ObjectId.is_valid(slide_id):
            return APIRoute.error(ErrorCodes.VALIDATION_ERROR, "ID de slide inválido")
        
        cascade = request.args.get('cascade', 'false').lower() in ('true', '1', 'yes')
        
        # Verificar que existe
        current = content_service.get_content(slide_id)
        if not current:
            return APIRoute.error(ErrorCodes.NOT_FOUND, "Slide no encontrada", status_code=404)
        
        topic_id = current.get('topic_id')
        
        logging.info(f"[SlideManual] Eliminando slide {slide_id} cascade={cascade}")
        
        # Si cascade, eliminar variantes primero
        deleted_count = 0
        if cascade:
            # Buscar variantes (hijos)
            db = get_db()
            variants = list(db.virtual_topic_contents.find({
                'parent_content_id': ObjectId(slide_id)
            }))
            
            for variant in variants:
                variant_id = str(variant['_id'])
                content_service.delete_content(variant_id, cascade=True)
                deleted_count += 1
                logging.info(f"[SlideManual] Variante eliminada: {variant_id}")
        
        # Determinar si la slide eliminada era una slide principal o variante
        deleted_parent_content_id = current.get('parent_content_id')
        is_main_slide = not deleted_parent_content_id
        deleted_order = current.get('order', 0)
        
        # Eliminar la slide
        success, result = content_service.delete_content(slide_id, cascade=True)
        
        if success:
            deleted_count += 1
            
            # Solo reordenar si se eliminó una slide PRINCIPAL (no variante)
            # Las variantes no afectan el orden de las slides principales
            if topic_id and is_main_slide:
                try:
                    db = get_db()
                    
                    # Obtener slides principales restantes ordenadas (sin parent_content_id)
                    remaining_main_slides = list(db.virtual_topic_contents.find({
                        'topic_id': ObjectId(topic_id),
                        'content_type': 'slide',
                        '$or': [
                            {'parent_content_id': {'$exists': False}},
                            {'parent_content_id': None}
                        ]
                    }).sort('order', 1))
                    
                    # Mapeo del viejo orden al nuevo orden
                    old_to_new_order = {}
                    
                    # Reasignar orden secuencial a slides principales (empezando en 1)
                    for idx, slide in enumerate(remaining_main_slides):
                        new_order = idx + 1  # Empezar desde 1, no desde 0
                        old_order = slide.get('order', 0)
                        
                        # Calcular índice del padre (si order >= 1000, es múltiplo de 1000)
                        old_main_index = old_order if old_order < 1000 else old_order // 1000
                        old_to_new_order[old_main_index] = new_order
                        
                        if old_order != new_order:
                            # Actualizar el orden en la raíz
                            update_op = {
                                '$set': {
                                    'order': new_order,
                                    'updated_at': datetime.datetime.utcnow()
                                }
                            }
                            
                            # Actualizar content.order solo si content existe y es un objeto
                            content_field = slide.get('content')
                            if isinstance(content_field, dict):
                                update_op['$set']['content.order'] = new_order
                            
                            db.virtual_topic_contents.update_one(
                                {'_id': slide['_id']},
                                update_op
                            )
                    
                    # Reordenar variantes: actualizar el orden basándose en el nuevo orden del padre
                    variants = list(db.virtual_topic_contents.find({
                        'topic_id': ObjectId(topic_id),
                        'content_type': 'slide',
                        'parent_content_id': {'$exists': True, '$ne': None}
                    }))
                    
                    for variant in variants:
                        old_variant_order = variant.get('order', 0)
                        if old_variant_order >= 1000:
                            old_parent_index = old_variant_order // 1000
                            variant_suffix = old_variant_order % 1000
                            
                            if old_parent_index in old_to_new_order:
                                new_parent_index = old_to_new_order[old_parent_index]
                                new_variant_order = new_parent_index * 1000 + variant_suffix
                                
                                if new_variant_order != old_variant_order:
                                    update_fields = {
                                        'order': new_variant_order,
                                        'updated_at': datetime.datetime.utcnow()
                                    }
                                    
                                    # Actualizar content.order solo si content existe y es un objeto
                                    content_field = variant.get('content')
                                    if isinstance(content_field, dict):
                                        update_fields['content.order'] = new_variant_order
                                        
                                        # Actualizar parent_order en variant si existe
                                        variant_meta = content_field.get('variant', {})
                                        if isinstance(variant_meta, dict) and 'parent_order' in variant_meta:
                                            update_fields['content.variant.parent_order'] = new_parent_index
                                    
                                    db.virtual_topic_contents.update_one(
                                        {'_id': variant['_id']},
                                        {'$set': update_fields}
                                    )
                    
                    logging.info(f"[SlideManual] Slides principales y variantes reordenadas para topic {topic_id}")
                except Exception as e:
                    logging.warning(f"[SlideManual] No se pudo reordenar: {e}")
            elif topic_id and not is_main_slide:
                # Si se eliminó una variante, no reordenar slides principales
                # Solo registrar en log
                logging.info(f"[SlideManual] Variante eliminada (orden {deleted_order}), no se reordenan slides principales")
            
            return APIRoute.success(
                data={"deleted_count": deleted_count, "reordered": True},
                message=f"Slide eliminada ({deleted_count} elementos)"
            )
        else:
            return APIRoute.error(ErrorCodes.NOT_FOUND, result, status_code=404)
            
    except Exception as e:
        logging.error(f"[SlideManual] Error eliminando slide: {str(e)}")
        return APIRoute.error(
            ErrorCodes.SERVER_ERROR,
            "Error interno del servidor",
            status_code=500
        )

@content_bp.route('/topics/<topic_id>/slides/reorder', methods=['PUT'])
@APIRoute.standard(auth_required_flag=True, roles=[ROLES["TEACHER"], ROLES["ADMIN"]])
def reorder_topic_slides(topic_id):
    """
    Reordena las slides de un topic.
    
    Body:
    {
        "slides": [
            {"id": "slide_id_1", "order": 0},
            {"id": "slide_id_2", "order": 1},
            ...
        ]
    }
    """
    try:
        if not ObjectId.is_valid(topic_id):
            return APIRoute.error(ErrorCodes.VALIDATION_ERROR, "ID de topic inválido")
        
        data = request.json or {}
        slides = data.get('slides', [])
        
        if not slides:
            return APIRoute.error(ErrorCodes.VALIDATION_ERROR, "Se requiere array 'slides' con elementos")
        
        logging.info(f"[SlideReorder] Reordenando {len(slides)} slides en topic {topic_id}")
        
        db = get_db()
        updated_count = 0
        
        for slide_data in slides:
            slide_id = slide_data.get('id')
            new_order = slide_data.get('order')
            
            if not slide_id or new_order is None:
                continue
            
            if not ObjectId.is_valid(slide_id):
                continue
            
            result = db.virtual_topic_contents.update_one(
                {'_id': ObjectId(slide_id), 'topic_id': ObjectId(topic_id)},
                {'$set': {'order': new_order, 'updated_at': datetime.datetime.utcnow()}}
            )
            
            if result.modified_count > 0:
                updated_count += 1
        
        logging.info(f"[SlideReorder] {updated_count} slides actualizadas")
        
        return APIRoute.success(
            data={"updated_count": updated_count},
            message=f"{updated_count} slides reordenadas"
        )
        
    except Exception as e:
        logging.error(f"[SlideReorder] Error: {str(e)}")
        return APIRoute.error(
            ErrorCodes.SERVER_ERROR,
            "Error interno del servidor",
            status_code=500
        )

@content_bp.route('/topics/<topic_id>/slides', methods=['GET'])
@APIRoute.standard(auth_required_flag=True)
def get_topic_slides_list(topic_id):
    """
    Obtiene las slides de un topic.
    
    Query params:
    - parents_only: "true" para obtener solo slides principales (sin variantes)
    - count_only: "true" para obtener solo el conteo
    """
    try:
        if not ObjectId.is_valid(topic_id):
            return APIRoute.error(ErrorCodes.VALIDATION_ERROR, "ID de topic inválido")
        
        parents_only = request.args.get('parents_only', 'false').lower() in ('true', '1', 'yes')
        count_only = request.args.get('count_only', 'false').lower() in ('true', '1', 'yes')
        
        db = get_db()
        
        # Construir filtro
        query = {
            'topic_id': ObjectId(topic_id),
            'content_type': 'slide'
        }
        
        if parents_only:
            # Solo slides sin parent_content_id o con parent_content_id null
            query['$or'] = [
                {'parent_content_id': {'$exists': False}},
                {'parent_content_id': None}
            ]
        
        if count_only:
            count = db.virtual_topic_contents.count_documents(query)
            return APIRoute.success(data={"count": count})
        
        # Obtener slides
        slides = list(db.virtual_topic_contents.find(query).sort('order', 1))
        
        # Serializar
        result = []
        for slide in slides:
            result.append({
                'id': str(slide['_id']),
                'title': slide.get('content', {}).get('title', f"Slide {slide.get('order', 0) + 1}"),
                'order': slide.get('order', 0),
                'status': slide.get('status', 'unknown'),
                'parent_content_id': str(slide['parent_content_id']) if slide.get('parent_content_id') else None,
                'content_type': slide.get('content_type'),
                'has_variants': False  # Se puede calcular si es necesario
            })
        
        # Calcular cuáles tienen variantes
        if parents_only:
            parent_ids = [ObjectId(s['id']) for s in result]
            if parent_ids:
                variant_counts = db.virtual_topic_contents.aggregate([
                    {'$match': {'parent_content_id': {'$in': parent_ids}}},
                    {'$group': {'_id': '$parent_content_id', 'count': {'$sum': 1}}}
                ])
                variant_map = {str(v['_id']): v['count'] for v in variant_counts}
                
                for slide in result:
                    slide['variant_count'] = variant_map.get(slide['id'], 0)
                    slide['has_variants'] = slide['variant_count'] > 0
        
        return APIRoute.success(data=result)
        
    except Exception as e:
        logging.error(f"[SlideList] Error: {str(e)}")
        return APIRoute.error(
            ErrorCodes.SERVER_ERROR,
            "Error interno del servidor",
            status_code=500
        )