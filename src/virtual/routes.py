from flask import request
from .services import VirtualModuleService, VirtualTopicService, VirtualEvaluationService
from src.shared.standardization import APIBlueprint, APIRoute, ErrorCodes
from src.shared.constants import ROLES

virtual_bp = APIBlueprint('virtual', __name__)

virtual_module_service = VirtualModuleService()
virtual_topic_service = VirtualTopicService()
virtual_evaluation_service = VirtualEvaluationService()

# Rutas para Módulos Virtuales
@virtual_bp.route('/module', methods=['POST'])
@APIRoute.standard(
    auth_required_flag=True,
    roles=[ROLES["TEACHER"]],
    required_fields=['study_plan_id', 'name', 'description']
)
def create_virtual_module():
    """Crea un nuevo módulo virtual"""
    data = request.get_json()
    success, result = virtual_module_service.create_module(data)
    
    if success:
        return APIRoute.success(
            data={"module_id": result},
            message="Módulo virtual creado exitosamente",
            status_code=201
        )
    return APIRoute.error(
        ErrorCodes.CREATION_ERROR,
        result,
        status_code=400
    )

@virtual_bp.route('/module/<module_id>', methods=['GET'])
@APIRoute.standard(auth_required_flag=True)
def get_virtual_module(module_id):
    """Obtiene detalles de un módulo virtual"""
    module = virtual_module_service.get_module_details(module_id)
    if module:
        return APIRoute.success(data={"module": module})
    return APIRoute.error(
        ErrorCodes.NOT_FOUND,
        "Módulo virtual no encontrado",
        status_code=404
    )

# Rutas para Temas Virtuales
@virtual_bp.route('/topic', methods=['POST'])
@APIRoute.standard(
    auth_required_flag=True,
    roles=[ROLES["TEACHER"]],
    required_fields=['virtual_module_id', 'name', 'description', 'content', 'multimedia_resources', 'order']
)
def create_virtual_topic():
    """Crea un nuevo tema virtual"""
    data = request.get_json()
    success, result = virtual_topic_service.create_topic(data)
    
    if success:
        return APIRoute.success(
            data={"topic_id": result},
            message="Tema virtual creado exitosamente",
            status_code=201
        )
    return APIRoute.error(
        ErrorCodes.CREATION_ERROR,
        result,
        status_code=400
    )

@virtual_bp.route('/module/<module_id>/topics', methods=['GET'])
@APIRoute.standard(auth_required_flag=True)
def get_module_topics(module_id):
    """Obtiene todos los temas de un módulo virtual"""
    topics = virtual_topic_service.get_module_topics(module_id)
    return APIRoute.success(data={"topics": topics})

# Rutas para Evaluaciones Virtuales
@virtual_bp.route('/evaluation', methods=['POST'])
@APIRoute.standard(
    auth_required_flag=True,
    roles=[ROLES["TEACHER"]],
    required_fields=['virtual_module_id', 'title', 'description', 'due_date', 
                   'topics_covered', 'questions', 'total_points', 'passing_score']
)
def create_virtual_evaluation():
    """Crea una nueva evaluación virtual"""
    data = request.get_json()
    success, result = virtual_evaluation_service.create_evaluation(data)
    
    if success:
        return APIRoute.success(
            data={"evaluation_id": result},
            message="Evaluación virtual creada exitosamente",
            status_code=201
        )
    return APIRoute.error(
        ErrorCodes.CREATION_ERROR,
        result,
        status_code=400
    )

@virtual_bp.route('/evaluation/submit', methods=['POST'])
@APIRoute.standard(
    auth_required_flag=True,
    roles=[ROLES["STUDENT"]],
    required_fields=['virtual_evaluation_id', 'student_id', 'answers']
)
def submit_evaluation():
    """Envía las respuestas de una evaluación virtual"""
    data = request.get_json()
    success, result = virtual_evaluation_service.submit_evaluation(data)
    
    if success:
        return APIRoute.success(
            data={"result_id": result},
            message="Evaluación enviada exitosamente",
            status_code=201
        )
    return APIRoute.error(
        ErrorCodes.SUBMISSION_ERROR,
        result,
        status_code=400
    )

@virtual_bp.route('/student/<student_id>/results', methods=['GET'])
@APIRoute.standard(auth_required_flag=True)
def get_student_results(student_id):
    """Obtiene los resultados de evaluaciones de un estudiante"""
    module_id = request.args.get('module_id')
    results = virtual_evaluation_service.get_student_results(student_id, module_id)
    return APIRoute.success(data={"results": results}) 