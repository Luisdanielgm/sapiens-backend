from flask import request, jsonify, redirect
from typing import Optional
from src.shared.standardization import APIBlueprint, APIRoute, ErrorCodes
from src.profiles.services import ProfileService
from src.shared.decorators import auth_required, role_required, workspace_type_required, workspace_access_required
from src.shared.middleware import apply_workspace_filter, get_current_workspace_info
from .services import (
    StudyPlanService, 
    StudyPlanAssignmentService,
    ModuleService, 
    TopicService,
    ContentTypeService,
    LearningMethodologyService,
    ContentService,
    EvaluationService,
    EvaluationResourceService,
    TopicReadinessService,
    AutomaticGradingService
)
from src.resources.services import ResourceService, ResourceFolderService
import logging
from src.shared.constants import ROLES
from bson import ObjectId
from bson.errors import InvalidId
from src.shared.utils import ensure_json_serializable
from datetime import datetime
from src.shared.database import get_db
from src.content.models import ContentTypes, LearningMethodologyTypes
from src.shared.constants import STATUS
from werkzeug.utils import secure_filename
import os
from src.shared.logging import log_error

study_plan_bp = APIBlueprint('study_plan', __name__)

study_plan_service = StudyPlanService()
assignment_service = StudyPlanAssignmentService()
module_service = ModuleService()
evaluation_service = EvaluationService()
topic_service = TopicService()
content_type_service = ContentTypeService()
methodology_service = LearningMethodologyService()
topic_content_service = ContentService()
resource_service = ResourceService()
evaluation_resource_service = EvaluationResourceService()
folder_service = ResourceFolderService()
topic_readiness_service = TopicReadinessService()

# ==================== Alias /api/study-plan/evaluation* -> /api/evaluations* ====================

@study_plan_bp.route('/evaluation', methods=['POST'])
def proxy_create_evaluation():
    return redirect('/api/evaluations/', code=307)

@study_plan_bp.route('/evaluation/<evaluation_id>', methods=['GET', 'PUT', 'DELETE'])
def proxy_evaluation_crud(evaluation_id):
    return redirect(f'/api/evaluations/{evaluation_id}', code=307)

@study_plan_bp.route('/evaluations/<evaluation_id>/resources', methods=['GET', 'POST'])
def proxy_resources(evaluation_id):
    return redirect(f'/api/evaluations/{evaluation_id}/resources', code=307)

@study_plan_bp.route('/evaluations/<evaluation_id>/resources/<resource_id>', methods=['DELETE'])
def proxy_resource_delete(evaluation_id, resource_id):
    return redirect(f'/api/evaluations/{evaluation_id}/resources/{resource_id}', code=307)

@study_plan_bp.route('/evaluations/<evaluation_id>/submissions', methods=['GET', 'POST'])
def proxy_submissions(evaluation_id):
    return redirect(f'/api/evaluations/{evaluation_id}/submissions', code=307)

@study_plan_bp.route('/evaluation/submission/<submission_id>', methods=['PUT'])
def proxy_grade_submission(submission_id):
    return redirect(f'/api/evaluations/submissions/{submission_id}/grade', code=307)

# Rutas para Plan de Estudio
@study_plan_bp.route('/', methods=['POST'])
@auth_required
@workspace_access_required
@workspace_type_required(['INDIVIDUAL_TEACHER', 'INSTITUTE'])
def create_study_plan():
    """Crea un nuevo plan de estudios"""
    data = request.get_json()
    workspace_info = get_current_workspace_info()
    
    # Validar campos requeridos
    required_fields = ['version', 'name']
    for field in required_fields:
        if field not in data:
            return APIRoute.error(ErrorCodes.MISSING_FIELD, f"Campo requerido: {field}")
    
    # Asignar author_id del usuario actual
    data['author_id'] = request.user_id
    
    result = study_plan_service.create_study_plan(data, workspace_info=workspace_info)
    return APIRoute.success(
        {"id": result},
        message="Plan de estudios creado exitosamente",
        status_code=201
    )

@study_plan_bp.route('/', methods=['GET'])
@auth_required
@apply_workspace_filter('study_plans_per_subject')
def list_study_plans():
    """
    Lista todos los planes de estudio, con filtros opcionales por workspace.
    - `email`: Filtra por el email del autor.
    - `institute_id`: Filtra por el instituto al que están asociados los planes.
    """
    try:
        workspace_info = get_current_workspace_info()
        workspace_type = workspace_info.get('workspace_type')
        current_user_id = request.user_id
        
        email = request.args.get('email')
        institute_id = request.args.get('institute_id')
        
        # En workspaces individuales, restringir acceso a planes propios
        if workspace_type in ['INDIVIDUAL_TEACHER', 'INDIVIDUAL_STUDENT']:
            # Solo permitir ver planes del usuario actual
            # Obtener email del usuario desde la base de datos usando user_id
            from bson import ObjectId
            from src.shared.database import get_db
            db = get_db()
            user = db.users.find_one({'_id': ObjectId(request.user_id)})
            email = user['email'] if user else None
        
        study_plans = study_plan_service.list_study_plans(
            email=email, 
            institute_id=institute_id,
            workspace_info=workspace_info
        )
        
        return APIRoute.success(data=study_plans)
    except Exception as e:
        return APIRoute.error(
            ErrorCodes.SERVER_ERROR,
            str(e),
            status_code=500
        )

@study_plan_bp.route('/<plan_id>', methods=['GET'])
@auth_required
@apply_workspace_filter('study_plans_per_subject')
def get_study_plan(plan_id):
    """Obtiene un plan de estudios con sus módulos, temas y evaluaciones"""
    workspace_info = get_current_workspace_info()
    workspace_type = workspace_info.get('workspace_type')
    current_user_id = request.user_id
    
    plan = study_plan_service.get_study_plan(plan_id, workspace_info=workspace_info)
    
    if plan:
        # En workspaces individuales, verificar que el plan pertenece al usuario
        if workspace_type in ['INDIVIDUAL_TEACHER', 'INDIVIDUAL_STUDENT']:
            plan_author_id = plan.get('author_id')
            if str(plan_author_id) != str(current_user_id):
                return APIRoute.error(ErrorCodes.FORBIDDEN, "No tienes acceso a este plan de estudios")
        
        plan = ensure_json_serializable(plan)
        return APIRoute.success(data=plan)
    return APIRoute.error(ErrorCodes.NOT_FOUND, "Plan de estudios no encontrado")

@study_plan_bp.route('/<plan_id>', methods=['PUT'])
@APIRoute.standard(auth_required_flag=True, roles=[ROLES["TEACHER"]])
def update_study_plan(plan_id):
    """Actualiza un plan de estudios existente"""
    data = request.get_json()
    study_plan_service.update_study_plan(plan_id, data)
    return APIRoute.success(message="Plan de estudios actualizado exitosamente")

@study_plan_bp.route('/<plan_id>', methods=['DELETE'])
@APIRoute.standard(auth_required_flag=True, roles=[ROLES["TEACHER"], ROLES["INSTITUTE_ADMIN"]])
def delete_study_plan(plan_id):
    """Elimina un plan de estudios y sus componentes asociados"""
    payload = request.get_json(silent=True) or {}
    cascade_delete = bool(payload.get("cascadeDelete") or payload.get("cascade"))

    success, message = study_plan_service.delete_study_plan(plan_id, cascade=cascade_delete)
    if success:
        return APIRoute.success(data={"message": message}, message=message)
    return APIRoute.error(ErrorCodes.DELETE_ERROR, message)

# Rutas para Asignación de Planes a Clases
@study_plan_bp.route('/assignment', methods=['POST'])
@APIRoute.standard(auth_required_flag=True, roles=[ROLES["TEACHER"], ROLES["INSTITUTE_ADMIN"]], required_fields=['study_plan_id', 'class_id', 'subperiod_id', 'assigned_by'])
def assign_plan_to_class():
    """Asigna un plan de estudio a una clase en un subperiodo"""
    data = request.get_json()
    result = assignment_service.assign_plan_to_class(data)
    return APIRoute.success({"id": result}, message="Plan asignado exitosamente", status_code=201)

@study_plan_bp.route('/assignment/<assignment_id>', methods=['DELETE'])
@APIRoute.standard(auth_required_flag=True, roles=[ROLES["TEACHER"], ROLES["INSTITUTE_ADMIN"]])
def remove_plan_assignment(assignment_id):
    """Remueve una asignación de plan de estudio"""
    assignment_service.remove_plan_assignment(assignment_id)
    return APIRoute.success(message="Asignación de plan removida exitosamente")

@study_plan_bp.route('/class/<class_id>/subperiod/<subperiod_id>/plan', methods=['GET'])
@APIRoute.standard(auth_required_flag=True)
def get_class_assigned_plan(class_id, subperiod_id):
    """Obtiene el plan de estudio asignado a una clase en un subperiodo"""
    assignment = assignment_service.get_class_assigned_plan(class_id, subperiod_id)
    if assignment:
        assignment = ensure_json_serializable(assignment)
        return APIRoute.success(data=assignment)
    return APIRoute.error(ErrorCodes.NOT_FOUND, "No hay plan asignado para esta clase y subperiodo")

@study_plan_bp.route('/assignments', methods=['GET'])
@APIRoute.standard(auth_required_flag=True)
def list_plan_assignments():
    """Lista todas las asignaciones de planes de estudio"""
    plan_id = request.args.get('plan_id')
    assignments = assignment_service.list_plan_assignments(plan_id)
    assignments = ensure_json_serializable(assignments)
    return APIRoute.success(data=assignments)

# Rutas para Módulos
@study_plan_bp.route('/module', methods=['POST'])
@APIRoute.standard(auth_required_flag=True, roles=[ROLES["TEACHER"]], required_fields=['study_plan_id', 'name', 'learning_outcomes', 'evaluation_rubric', 'date_start', 'date_end'])
def create_module():
    """Crea un nuevo módulo"""
    data = request.get_json()
    topics_data = data.pop('topics', [])
    success, module_id = module_service.create_module(data)
    if success:
        topics_ids = []
        for topic_data in topics_data:
            topic_data['module_id'] = module_id
            topic_success, topic_id = topic_service.create_topic(topic_data)
            if topic_success:
                topics_ids.append(topic_id)
        return APIRoute.success(
            {"id": module_id, "topics": topics_ids},
            message="Módulo creado exitosamente",
            status_code=201
        )
    return APIRoute.error(ErrorCodes.CREATION_ERROR, module_id)

@study_plan_bp.route('/module/<module_id>', methods=['GET'])
@APIRoute.standard(auth_required_flag=True)
def get_module_details(module_id):
    """Obtiene detalles de un módulo con sus temas y evaluaciones"""
    module = module_service.get_module_details(module_id)
    if module:
        module = ensure_json_serializable(module)
        return APIRoute.success(data=module)
    return APIRoute.error(ErrorCodes.NOT_FOUND, "Módulo no encontrado")

@study_plan_bp.route('/module/<module_id>', methods=['PUT'])
@APIRoute.standard(auth_required_flag=True, roles=[ROLES["TEACHER"]])
def update_module(module_id):
    """Actualiza un módulo"""
    data = request.get_json()
    success, message = module_service.update_module(module_id, data)
    if success:
        return APIRoute.success(data={"message": message}, message=message)
    return APIRoute.error(ErrorCodes.UPDATE_ERROR, message)

@study_plan_bp.route('/module/<module_id>', methods=['DELETE'])
@APIRoute.standard(auth_required_flag=True, roles=[ROLES["TEACHER"]])
def delete_module(module_id):
    """Elimina un módulo y sus componentes asociados"""
    payload = request.get_json(silent=True) or {}
    cascade_delete = bool(payload.get("cascadeDelete") or payload.get("cascade"))

    success, message = module_service.delete_module(module_id, cascade=cascade_delete)
    if success:
        return APIRoute.success(data={"message": message}, message=message)
    return APIRoute.error(ErrorCodes.DELETE_ERROR, message)

@study_plan_bp.route('/module/<module_id>/virtualization-readiness', methods=['GET'])
@APIRoute.standard(auth_required_flag=True, roles=[ROLES['TEACHER']])
def get_virtualization_readiness(module_id):
    """Verifica los requisitos de virtualización de un módulo"""
    data = module_service.get_virtualization_readiness(module_id)
    return APIRoute.success(data=data)

# Rutas para Topics
@study_plan_bp.route('/topic', methods=['POST'])
@APIRoute.standard(auth_required_flag=True, roles=[ROLES["TEACHER"]], required_fields=['module_id', 'name', 'difficulty', 'date_start', 'date_end'])
def create_topic():
    """Crea un nuevo topic para un módulo"""
    data = request.get_json()
    success, result = topic_service.create_topic(data)
    if success:
        return APIRoute.success({"id": result}, message="Topic creado exitosamente", status_code=201)
    return APIRoute.error(ErrorCodes.CREATION_ERROR, result)

@study_plan_bp.route('/topic', methods=['GET'])
@APIRoute.standard(auth_required_flag=True)
def get_topic():
    """Obtiene detalles de un topic específico"""
    topic_id = request.args.get('topic_id')
    if not topic_id:
        return APIRoute.error(ErrorCodes.MISSING_FIELD, "ID del topic es requerido")
    topic = topic_service.get_topic(topic_id)
    if not topic:
        return APIRoute.error(ErrorCodes.NOT_FOUND, "Topic no encontrado")
    topic = ensure_json_serializable(topic)
    return APIRoute.success(data=topic)

@study_plan_bp.route('/topic/<topic_id>', methods=['PUT'])
@APIRoute.standard(auth_required_flag=True, roles=[ROLES["TEACHER"]])
def update_topic(topic_id):
    """Actualiza un topic"""
    data = request.get_json()
    success, message = topic_service.update_topic(topic_id, data)
    if success:
        return APIRoute.success(data={"message": message}, message=message)
    return APIRoute.error(ErrorCodes.UPDATE_ERROR, message)

@study_plan_bp.route('/topic/<topic_id>', methods=['DELETE'])
@APIRoute.standard(auth_required_flag=True, roles=[ROLES["TEACHER"]])
def delete_topic(topic_id):
    """Elimina un topic"""
    payload = request.get_json(silent=True) or {}
    cascade_delete = bool(payload.get("cascadeDelete") or payload.get("cascade"))

    success, message = topic_service.delete_topic(topic_id, cascade=cascade_delete)
    if success:
        return APIRoute.success(data={"message": message}, message=message)
    return APIRoute.error(ErrorCodes.DELETE_ERROR, message)

@study_plan_bp.route('/topic/<topic_id>/publish', methods=['PUT'])
@APIRoute.standard(auth_required_flag=True, roles=[ROLES["TEACHER"]])
def toggle_topic_publication(topic_id):
    """Cambia el estado de publicación de un tema"""
    data = request.get_json()
    published = data.get('published', True)
    success, message = topic_service.update_topic(topic_id, {"published": published})
    if success:
        action = "publicado" if published else "despublicado"
        return APIRoute.success(
            data={"topic_id": topic_id, "published": published},
            message=f"Tema {action} exitosamente"
        )
    return APIRoute.error(ErrorCodes.UPDATE_ERROR, message)


@study_plan_bp.route('/topic/theory', methods=['GET'])
@APIRoute.standard(auth_required_flag=True)
def get_topic_theory():
    """Obtiene el contenido teórico de un tema"""
    topic_id = request.args.get('topic_id')
    if not topic_id:
        return APIRoute.error(ErrorCodes.MISSING_FIELD, "ID del topic es requerido")
    result = topic_service.get_theory_content(topic_id)
    if not result:
        return APIRoute.error(ErrorCodes.NOT_FOUND, "Topic no encontrado")
    return APIRoute.success(data=result)


@study_plan_bp.route('/topic/theory', methods=['PUT'])
@APIRoute.standard(auth_required_flag=True, roles=[ROLES["TEACHER"]], required_fields=['topic_id', 'theory_content'])
def update_topic_theory():
    """Actualiza el contenido teórico de un tema con validación robusta"""
    data = request.get_json()
    topic_id = data.get('topic_id')
    theory_content = data.get('theory_content')
    
    # === VALIDACIÓN Y SANITIZACIÓN ROBUSTA ===
    try:
        # Log del tipo de dato recibido para debugging
        logging.info(f"update_topic_theory: Recibido tipo {type(theory_content)} para topic {topic_id}")
        
        # Validación inicial - verificar que no sea None
        if theory_content is None:
            logging.warning(f"update_topic_theory: theory_content es None para topic {topic_id}")
            return APIRoute.error(
                ErrorCodes.INVALID_DATA, 
                "El campo 'theory_content' no puede ser nulo"
            )
        
        # Caso ideal: ya es string
        if isinstance(theory_content, str):
            processed_content = theory_content
            logging.debug(f"update_topic_theory: theory_content es string válido para topic {topic_id}")
        
        # Caso problemático: es un objeto/diccionario
        elif isinstance(theory_content, dict):
            logging.warning(f"update_topic_theory: theory_content es dict para topic {topic_id}: {theory_content}")
            
            # Intentar extraer contenido de patrones comunes
            if 'content' in theory_content:
                processed_content = str(theory_content['content'])
                logging.info(f"update_topic_theory: Extraído contenido de campo 'content' para topic {topic_id}")
            elif 'text' in theory_content:
                processed_content = str(theory_content['text'])
                logging.info(f"update_topic_theory: Extraído contenido de campo 'text' para topic {topic_id}")
            elif 'value' in theory_content:
                processed_content = str(theory_content['value'])
                logging.info(f"update_topic_theory: Extraído contenido de campo 'value' para topic {topic_id}")
            elif 'data' in theory_content:
                processed_content = str(theory_content['data'])
                logging.info(f"update_topic_theory: Extraído contenido de campo 'data' para topic {topic_id}")
            else:
                # Si no hay campos reconocidos, rechazar el objeto
                logging.error(f"update_topic_theory: Objeto sin campos reconocidos para topic {topic_id}: {theory_content}")
                return APIRoute.error(
                    ErrorCodes.INVALID_DATA,
                    "El campo 'theory_content' debe ser texto, no un objeto. Verifique que está enviando el contenido como string."
                )
        
        # Caso de array/lista: rechazar
        elif isinstance(theory_content, (list, tuple)):
            logging.error(f"update_topic_theory: theory_content es lista/tupla para topic {topic_id}")
            return APIRoute.error(
                ErrorCodes.INVALID_DATA,
                "El campo 'theory_content' debe ser texto, no una lista o array."
            )
        
        # Otros tipos: intentar conversión con advertencia
        else:
            logging.warning(f"update_topic_theory: theory_content tipo no reconocido {type(theory_content)} para topic {topic_id}")
            processed_content = str(theory_content)
        
        # Validar que el contenido procesado no sea '[object Object]' o similar
        if processed_content in ['[object Object]', '[Object object]', 'undefined', 'null']:
            logging.error(f"update_topic_theory: Detectado contenido inválido '{processed_content}' para topic {topic_id}")
            return APIRoute.error(
                ErrorCodes.INVALID_DATA,
                f"Contenido inválido detectado: '{processed_content}'. Verifique que está enviando texto válido desde el frontend."
            )
        
        # Limpiar contenido
        processed_content = processed_content.strip()
        
        # Llamar al servicio con el contenido procesado
        success, message = topic_service.update_theory_content(topic_id, processed_content)
        
        if success:
            # Log exitoso con información del contenido
            content_length = len(processed_content)
            logging.info(f"update_topic_theory: Actualizado exitosamente topic {topic_id}, longitud: {content_length}")
            return APIRoute.success(message=message)
        else:
            return APIRoute.error(ErrorCodes.UPDATE_ERROR, message)
            
    except Exception as e:
        logging.error(f"update_topic_theory: Error inesperado para topic {topic_id}: {str(e)}")
        return APIRoute.error(
            ErrorCodes.SERVER_ERROR,
            f"Error interno al procesar el contenido teórico: {str(e)}"
        )


@study_plan_bp.route('/topic/theory', methods=['DELETE'])
@APIRoute.standard(auth_required_flag=True, roles=[ROLES["TEACHER"]])
def delete_topic_theory():
    """Elimina el contenido teórico de un tema"""
    topic_id = request.args.get('topic_id')
    if not topic_id:
        return APIRoute.error(ErrorCodes.MISSING_FIELD, "ID del topic es requerido")
    success, message = topic_service.delete_theory_content(topic_id)
    if success:
        return APIRoute.success(message=message)
    return APIRoute.error(ErrorCodes.DELETE_ERROR, message)


@study_plan_bp.route('/topic/<topic_id>/content-integrity', methods=['GET'])
@APIRoute.standard(auth_required_flag=True, roles=[ROLES["TEACHER"]])
def check_topic_content_integrity(topic_id):
    """Verifica la integridad de los datos de contenido teórico de un tema"""
    try:
        # Llamar al método de validación en TopicService
        integrity_report = topic_service.validate_theory_content_integrity(topic_id)
        
        # Log del resultado para debugging
        logging.info(f"check_topic_content_integrity: Verificación completada para topic {topic_id}")
        
        return APIRoute.success(
            data=integrity_report,
            message="Verificación de integridad completada"
        )
        
    except Exception as e:
        logging.error(f"check_topic_content_integrity: Error para topic {topic_id}: {str(e)}")
        return APIRoute.error(
            ErrorCodes.SERVER_ERROR,
            f"Error al verificar integridad del contenido: {str(e)}"
        )

@study_plan_bp.route('/topic/<topic_id>/readiness-status', methods=['GET'])
@APIRoute.standard(auth_required_flag=True)
def get_topic_readiness_status(topic_id):
    """Verifica si un tema está listo para ser publicado"""
    result = topic_readiness_service.check_readiness(topic_id)
    return APIRoute.success(data=result)

@study_plan_bp.route('/topic/<topic_id>/redundant-content', methods=['DELETE'])
@APIRoute.standard(auth_required_flag=True, roles=[ROLES["TEACHER"]])
def cleanup_topic_redundant_content(topic_id):
    """Limpia contenidos redundantes de tipo 'text' para un tema"""
    try:
        # Verificar que el usuario tiene permisos sobre el tema
        topic = topic_service.get_topic(topic_id)
        if not topic:
            return APIRoute.error(ErrorCodes.NOT_FOUND, "Tema no encontrado")
        
        # Llamar al método de limpieza en TopicService
        success, message = topic_service.cleanup_redundant_text_content(topic_id)
        
        if success:
            logging.info(f"cleanup_topic_redundant_content: {message} para topic {topic_id}")
            return APIRoute.success(
                data={"topic_id": topic_id, "cleanup_result": message},
                message=message
            )
        else:
            logging.warning(f"cleanup_topic_redundant_content: Fallo para topic {topic_id}: {message}")
            return APIRoute.error(ErrorCodes.OPERATION_FAILED, message)
            
    except Exception as e:
        logging.error(f"cleanup_topic_redundant_content: Error para topic {topic_id}: {str(e)}")
        return APIRoute.error(
            ErrorCodes.SERVER_ERROR,
            f"Error al limpiar contenidos redundantes: {str(e)}"
        )

@study_plan_bp.route('/module/<module_id>/topics', methods=['GET'])
@APIRoute.standard(auth_required_flag=True)
def get_module_topics(module_id):
    """Obtiene todos los topics de un módulo"""
    topics = topic_service.get_module_topics(module_id)
    topics = ensure_json_serializable(topics)
    return APIRoute.success(data=topics)

@study_plan_bp.route('/module/<module_id>/topics/publication-status', methods=['GET'])
@APIRoute.standard(auth_required_flag=True)
def get_module_topics_publication_status(module_id):
    """Obtiene el estado de publicación de todos los topics de un módulo"""
    try:
        topics = topic_service.get_module_topics(module_id)
        publication_status = []
        
        for topic in topics:
            publication_status.append({
                "topic_id": str(topic.get("_id")),
                "name": topic.get("name"),
                "published": topic.get("published", False)
            })
        
        publication_status = ensure_json_serializable(publication_status)
        return APIRoute.success(data={"topics": publication_status})
    except Exception as e:
        log_error(f"Error obteniendo estado de publicación de topics: {str(e)}")
        return APIRoute.error(ErrorCodes.SERVER_ERROR, str(e), status_code=500)


@study_plan_bp.route('/topic/<topic_id>/evaluations', methods=['GET'])
@APIRoute.standard(auth_required_flag=True)
def list_topic_evaluations_route(topic_id):
    """Lista las evaluaciones de un tema. Si se indica student_id, retorna el estado para ese estudiante."""
    student_id = request.args.get('student_id')
    if student_id:
        evaluations = evaluation_service.get_evaluations_status_for_student(topic_id, student_id)
    else:
        evaluations = evaluation_service.get_evaluations_by_topic(topic_id)
    evaluations = ensure_json_serializable(evaluations)
    return APIRoute.success(data={"evaluations": evaluations})

# New endpoints: Slides completeness for topic, slides completeness for module, and auto-publish topic

@study_plan_bp.route('/topic/<topic_id>/slides-completeness', methods=['GET'])
@APIRoute.standard(auth_required_flag=True, roles=[ROLES["TEACHER"], ROLES["INSTITUTE_ADMIN"], ROLES["ADMIN"]])
def get_topic_slides_completeness(topic_id):
    """
    Retorna el estado detallado de las diapositivas de un tema específico,
    incluyendo conteos por estado, porcentaje de completitud y listas de
    diapositivas que requieren HTML o narrativa.
    """
    try:
        # Verificar existencia del topic
        topic = topic_service.get_topic(topic_id)
        if not topic:
            return APIRoute.error(ErrorCodes.NOT_FOUND, "Tema no encontrado")

        db = get_db()
        try:
            topic_obj_id = ObjectId(topic_id)
        except InvalidId:
            return APIRoute.error(ErrorCodes.INVALID_DATA, "ID de topic inválido")

        slides = list(db.topic_contents.find({
            "topic_id": topic_obj_id,
            "content_type": "slide",
            "status": {"$ne": "deleted"}
        }, {
            "_id": 1,
            "status": 1,
            "content.content_html": 1,
            "content.narrative_text": 1,
            "title": 1,
            "order": 1
        }))

        total_slides = len(slides)
        slides_by_status = {"skeleton": 0, "html_ready": 0, "narrative_ready": 0}
        needing_html = []
        needing_narrative = []
        slide_summaries = []

        for s in slides:
            status = s.get("status", "skeleton")
            slides_by_status[status] = slides_by_status.get(status, 0) + 1

            slide_summary = {
                "slide_id": str(s.get("_id")),
                "status": status,
                "title": s.get("title"),
                "order": s.get("order")
            }
            slide_summaries.append(slide_summary)

            if status == "skeleton":
                needing_html.append(slide_summary)
            elif status == "html_ready":
                needing_narrative.append(slide_summary)

        narrative_ready = slides_by_status.get("narrative_ready", 0)
        completion_percentage = (narrative_ready / total_slides * 100) if total_slides > 0 else 0.0

        response = {
            "topic_id": topic_id,
            "topic_name": topic.get("name"),
            "total_slides": total_slides,
            "slides_by_status": slides_by_status,
            "completion_percentage": round(completion_percentage, 2),
            "needing_html_count": len(needing_html),
            "needing_narrative_count": len(needing_narrative),
            "needing_html": needing_html,
            "needing_narrative": needing_narrative,
            "slides": slide_summaries
        }

        return APIRoute.success(data=response)

    except Exception as e:
        logging.error(f"get_topic_slides_completeness: Error para topic {topic_id}: {str(e)}")
        return APIRoute.error(ErrorCodes.SERVER_ERROR, str(e), status_code=500)


@study_plan_bp.route('/module/<module_id>/slides-completeness', methods=['GET'])
@APIRoute.standard(auth_required_flag=True, roles=[ROLES["TEACHER"], ROLES["INSTITUTE_ADMIN"], ROLES["ADMIN"]])
def get_module_slides_completeness(module_id):
    """
    Retorna un resumen de completitud de diapositivas para todos los temas de un módulo,
    reutiliza la lógica de ModuleService.check_slides_completeness_for_module.
    """
    try:
        # Verificar existencia del módulo
        module = module_service.get_module(module_id)
        if not module:
            return APIRoute.error(ErrorCodes.NOT_FOUND, "Módulo no encontrado")

        stats = module_service.check_slides_completeness_for_module(module_id)
        # Enriquecer con nombre del módulo
        stats["module_id"] = module_id
        stats["module_name"] = module.get("name")

        return APIRoute.success(data=stats)
    except Exception as e:
        logging.error(f"get_module_slides_completeness: Error para módulo {module_id}: {str(e)}")
        return APIRoute.error(ErrorCodes.SERVER_ERROR, str(e), status_code=500)


@study_plan_bp.route('/topic/<topic_id>/auto-publish', methods=['PUT'])
@APIRoute.standard(auth_required_flag=True, roles=[ROLES["TEACHER"], ROLES["INSTITUTE_ADMIN"], ROLES["ADMIN"]])
def auto_publish_topic(topic_id):
    """
    Verifica automáticamente si un tema cumple los criterios para publicarse:
     - theory_content presente
     - al menos una diapositiva en estado 'narrative_ready'
     - al menos una evaluación asociada (quiz)
    Si cumple, marca published=true y retorna información detallada.

    Refactored to use service layer methods for consistency and maintainability.
    """
    try:
        # Verify topic exists first
        topic = topic_service.get_topic(topic_id)
        if not topic:
            return APIRoute.error(ErrorCodes.NOT_FOUND, "Tema no encontrado")

        # Use service layer methods to centralize business logic
        result = topic_service.publish_topic(topic_id, user_id=request.user_id)

        if result.get("success", False):
            return APIRoute.success(
                data={
                    "topic_id": topic_id,
                    "published": result.get("published", False),
                    "auto_published": result.get("auto_published", False),
                    "missing_requirements": result.get("missing_requirements", []),
                    "narrative_ready_slides": result.get("narrative_ready_slides", 0),
                    "has_theory": result.get("has_theory", False),
                    "has_evaluation": result.get("has_evaluation", False),
                    **({"reason": result.get("reason")} if result.get("reason") else {}),
                    **({"note": result.get("note")} if result.get("note") else {})
                },
                message=result.get("message", "Operación completada")
            )
        else:
            # Handle different error scenarios
            if "error" in result:
                if "inválido" in result["error"].lower():
                    return APIRoute.error(ErrorCodes.INVALID_DATA, result["error"])
                elif "no encontrado" in result["error"].lower():
                    return APIRoute.error(ErrorCodes.NOT_FOUND, result["error"])
                else:
                    return APIRoute.error(ErrorCodes.SERVER_ERROR, result["error"])
            else:
                return APIRoute.success(
                    data={
                        "topic_id": topic_id,
                        "published": result.get("published", False),
                        "auto_published": False,
                        "missing_requirements": result.get("missing_requirements", []),
                        "narrative_ready_slides": result.get("narrative_ready_slides", 0),
                        "has_theory": result.get("has_theory", False),
                        "has_evaluation": result.get("has_evaluation", False)
                    },
                    message=result.get("message", "Requisitos no cumplidos para auto-publicación")
                )

    except Exception as e:
        logging.error(f"auto_publish_topic: Error procesando auto-publicación para topic {topic_id}: {str(e)}")
        return APIRoute.error(ErrorCodes.SERVER_ERROR, str(e), status_code=500)


# Rutas para Evaluaciones
@study_plan_bp.route('/evaluation', methods=['POST'])
@APIRoute.standard(auth_required_flag=True, roles=[ROLES["TEACHER"]], required_fields=['topic_ids', 'title', 'description', 'weight', 'criteria', 'due_date'])
def create_evaluation():
    """Crea una nueva evaluación"""
    data = request.get_json()
    success, result = evaluation_service.create_evaluation(data)
    if success:
        return APIRoute.success({"id": result}, message="Evaluación creada exitosamente", status_code=201)
    return APIRoute.error(ErrorCodes.CREATION_ERROR, result)

@study_plan_bp.route('/evaluation/<evaluation_id>', methods=['GET'])
@APIRoute.standard(auth_required_flag=True)
def get_evaluation(evaluation_id):
    """Obtiene detalles de una evaluación específica"""
    evaluation = evaluation_service.get_evaluation(evaluation_id)
    if evaluation:
        evaluation = ensure_json_serializable(evaluation)
        return APIRoute.success(data=evaluation)
    return APIRoute.error(ErrorCodes.NOT_FOUND, "Evaluación no encontrada")

@study_plan_bp.route('/evaluation/<evaluation_id>', methods=['PUT'])
@APIRoute.standard(auth_required_flag=True, roles=[ROLES["TEACHER"]])
def update_evaluation(evaluation_id):
    """Actualiza una evaluación"""
    data = request.get_json()
    success, message = evaluation_service.update_evaluation(evaluation_id, data)
    if success:
        return APIRoute.success(data={"message": message}, message=message)
    return APIRoute.error(ErrorCodes.UPDATE_ERROR, message)

@study_plan_bp.route('/evaluation/<evaluation_id>', methods=['DELETE'])
@APIRoute.standard(auth_required_flag=True, roles=[ROLES["TEACHER"]])
def delete_evaluation(evaluation_id):
    """Elimina una evaluación y sus resultados asociados"""
    payload = request.get_json(silent=True) or {}
    cascade_delete = bool(payload.get("cascadeDelete") or payload.get("cascade"))

    success, message = evaluation_service.delete_evaluation(evaluation_id, cascade=cascade_delete)
    if success:
        return APIRoute.success(data={"message": message}, message=message)
    return APIRoute.error(ErrorCodes.DELETE_ERROR, message)

@study_plan_bp.route('/evaluation/result', methods=['POST'])
@APIRoute.standard(auth_required_flag=True, roles=[ROLES["TEACHER"]], required_fields=['evaluation_id', 'student_id', 'score'])
def record_evaluation_result():
    """
    Registra el resultado de una evaluación.
    Alias temporal hacia /api/evaluations/<id>/results para unificar el flujo.
    """
    data = request.get_json() or {}
    evaluation_id = data.get("evaluation_id")
    if not evaluation_id:
        return APIRoute.error(ErrorCodes.MISSING_FIELD, "evaluation_id requerido")
    try:
        return redirect(f'/api/evaluations/{evaluation_id}/results', code=307)
    except Exception as e:
        return APIRoute.error(ErrorCodes.SERVER_ERROR, str(e))

@study_plan_bp.route('/evaluation/result/<result_id>', methods=['PUT'])
@APIRoute.standard(auth_required_flag=True, roles=[ROLES["TEACHER"]])
def update_evaluation_result(result_id):
    """
    Actualiza el resultado de una evaluación.
    Alias temporal hacia /api/evaluations/<id>/results (requiere evaluation_id en body).
    """
    data = request.get_json() or {}
    evaluation_id = data.get("evaluation_id")
    if not evaluation_id:
        return APIRoute.error(ErrorCodes.MISSING_FIELD, "evaluation_id requerido")
    try:
        return redirect(f'/api/evaluations/{evaluation_id}/results', code=307)
    except Exception as e:
        return APIRoute.error(ErrorCodes.SERVER_ERROR, str(e))

@study_plan_bp.route('/evaluation/result/<result_id>', methods=['DELETE'])
@APIRoute.standard(auth_required_flag=True, roles=[ROLES["TEACHER"]])
def delete_evaluation_result(result_id):
    """Elimina el resultado de una evaluación"""
    success, message = evaluation_service.delete_result(result_id)
    if success:
        return APIRoute.success(data={"message": message}, message=message)
    return APIRoute.error(ErrorCodes.DELETE_ERROR, message)

@study_plan_bp.route('/student/<student_id>/results', methods=['GET'])
@APIRoute.standard(auth_required_flag=True)
def get_student_results(student_id):
    """Obtiene resultados de evaluaciones de un estudiante"""
    topic_id = request.args.get('topic_id')
    results = evaluation_service.get_student_results(student_id, topic_id)
    results = ensure_json_serializable(results)
    return APIRoute.success(data=results)

# Rutas para Recursos Vinculados a Evaluaciones
@study_plan_bp.route('/evaluations/<evaluation_id>/resources', methods=['POST'])
@APIRoute.standard(auth_required_flag=True, roles=[ROLES["TEACHER"], ROLES["STUDENT"], ROLES["ADMIN"]], required_fields=['resource_id', 'role'])
def link_resource_to_evaluation_route(evaluation_id):
    """Vincula un recurso existente a una evaluación con un rol específico."""
    data = request.get_json()
    created_by = request.user_id
    success, result = evaluation_resource_service.link_resource_to_evaluation(
        evaluation_id=evaluation_id,
        resource_id=data.get('resource_id'),
        role=data.get('role'),
        created_by=created_by
    )
    if not success:
        status_code = 404 if "no encontrado" in result else 400
        return APIRoute.error(ErrorCodes.OPERATION_FAILED, result, status_code=status_code)
    return APIRoute.success(data={"link_id": result}, message="Recurso vinculado exitosamente", status_code=201)

@study_plan_bp.route('/evaluations/<evaluation_id>/resources', methods=['GET'])
@APIRoute.standard(auth_required_flag=True)
def get_evaluation_resources_route(evaluation_id):
    """Obtiene los recursos vinculados a una evaluación."""
    role_filter = request.args.get('role')
    student_id_filter = request.args.get('student_id')
    # Lógica de permisos para estudiantes vs. profesores...
    resources = evaluation_resource_service.get_evaluation_resources(
        evaluation_id=evaluation_id,
        role=role_filter,
        student_id=student_id_filter
    )
    return APIRoute.success(data={"resources": resources})

@study_plan_bp.route('/evaluations/<evaluation_id>/resources/<resource_id>', methods=['DELETE'])
@APIRoute.standard(auth_required_flag=True, roles=[ROLES["TEACHER"], ROLES["STUDENT"], ROLES["ADMIN"]])
def remove_resource_from_evaluation_route(evaluation_id, resource_id):
    """Elimina la vinculación entre una evaluación y un recurso."""
    success, result = evaluation_resource_service.remove_resource_from_evaluation(evaluation_id, resource_id)
    if not success:
        status_code = 404 if "no encontrado" in result else 400
        return APIRoute.error(ErrorCodes.OPERATION_FAILED, result, status_code=status_code)
    return APIRoute.success(data={"message": result}, message=result)

@study_plan_bp.route('/evaluations/<evaluation_id>/submissions', methods=['POST'])
@APIRoute.standard(auth_required_flag=True, roles=[ROLES["STUDENT"]])
def upload_evaluation_submission(evaluation_id):
    """
    Legacy de subida de entregables. Deshabilitado para evitar escritura en disco.
    Usar `/api/evaluations/<id>/submissions` con `ResourceService` (resource_id/url).
    """
    return APIRoute.error(
        ErrorCodes.OPERATION_FAILED,
        "Subida legacy deshabilitada. Usa /api/evaluations/<id>/submissions con ResourceService.",
        status_code=410
    )


@study_plan_bp.route('/evaluations/<evaluation_id>/submissions', methods=['GET'])
@APIRoute.standard(auth_required_flag=True, roles=[ROLES["TEACHER"]])
def list_evaluation_submissions(evaluation_id):
    """Lista todas las entregas de una evaluación. Opcionalmente filtra por student_id."""
    student_id = request.args.get('student_id')
    if student_id:
        submissions = evaluation_service.get_submissions_by_evaluation_and_student(evaluation_id, student_id)
    else:
        submissions = evaluation_service.get_submissions_by_evaluation(evaluation_id)
    submissions = ensure_json_serializable(submissions)
    return APIRoute.success(data={"submissions": submissions})


@study_plan_bp.route('/evaluation/submission/<submission_id>', methods=['PUT'])
@APIRoute.standard(auth_required_flag=True, roles=[ROLES["TEACHER"], ROLES["ADMIN"]], required_fields=['grade'])
def grade_submission_manual(submission_id):
    """Califica manualmente una entrega de estudiante."""
    data = request.get_json() or {}
    grade_data = {
        'grade': data.get('grade'),
        'feedback': data.get('feedback', ''),
        'graded_by': request.user_id
    }
    success, message = evaluation_service.grade_submission(submission_id, grade_data)
    if success:
        return APIRoute.success(data={"message": message}, message=message)
    return APIRoute.error(ErrorCodes.OPERATION_FAILED, message)

@study_plan_bp.route('/submissions/<submission_id>/grade', methods=['POST'])
@APIRoute.standard(auth_required_flag=True, roles=[ROLES["TEACHER"], ROLES["ADMIN"]], required_fields=['grade'])
def grade_submission(submission_id):
    """Califica una entrega de estudiante (endpoint legacy)."""
    data = request.get_json() or {}
    grade_data = {
        'grade': data.get('grade'),
        'feedback': data.get('feedback', ''),
        'graded_by': request.user_id
    }
    success, message = evaluation_service.grade_submission(submission_id, grade_data)
    if success:
        return APIRoute.success(data={"message": message}, message=message)
    return APIRoute.error(ErrorCodes.OPERATION_FAILED, message)


@study_plan_bp.route('/evaluations/<evaluation_id>/grade', methods=['POST'])
@APIRoute.standard(
    auth_required_flag=True,
    roles=[ROLES["TEACHER"], ROLES["ADMIN"]],
    required_fields=["student_id", "score"]
)
def grade_evaluation(evaluation_id):
    """Permite asignar una nota manual a una evaluación."""
    data = request.get_json() or {}
    result_data = {
        "evaluation_id": evaluation_id,
        "student_id": data.get("student_id"),
        "score": data.get("score"),
        "feedback": data.get("feedback", ""),
        "graded_by": request.user_id
    }

    success, result = evaluation_service.record_result(result_data)
    if success:
        return APIRoute.success(
            {"content_result_id": result},
            message="Calificación registrada"
        )
    return APIRoute.error(ErrorCodes.OPERATION_FAILED, result)


# Ruta para Metodologías de Aprendizaje
@study_plan_bp.route('/methodologies', methods=['GET'])
@APIRoute.standard(auth_required_flag=True)
def list_methodologies():
    """Lista todas las metodologías de aprendizaje activas"""
    try:
        methodologies = methodology_service.list_methodologies()
        return APIRoute.success(
            {"methodologies": methodologies},
            message="Metodologías obtenidas exitosamente"
        )
    except Exception as e:
        log_error(f"Error al obtener metodologías: {str(e)}")
        return APIRoute.error(ErrorCodes.OPERATION_FAILED, "Error al obtener metodologías")
