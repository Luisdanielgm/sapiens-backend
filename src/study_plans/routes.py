from flask import request, jsonify
from .services import (
    StudyPlanService, 
    StudyPlanAssignmentService,
    ModuleService, 
    EvaluationService, 
    TopicService
)
from src.shared.standardization import APIBlueprint, APIRoute, ErrorCodes
from src.shared.constants import ROLES
from bson import ObjectId

study_plan_bp = APIBlueprint('study_plan', __name__)

study_plan_service = StudyPlanService()
assignment_service = StudyPlanAssignmentService()
module_service = ModuleService()
evaluation_service = EvaluationService()
topic_service = TopicService()

# Rutas para Plan de Estudio
@study_plan_bp.route('/', methods=['POST'])
@APIRoute.standard(auth_required_flag=True, required_fields=['version', 'author_id', 'name'])
def create_study_plan():
    """Crea un nuevo plan de estudios"""
    data = request.get_json()
    
    # El servicio ahora lanza excepciones que son manejadas por APIRoute.standard
    result = study_plan_service.create_study_plan(data)
    
    return APIRoute.success(
        {"id": result},
        message="Plan de estudios creado exitosamente",
        status_code=201
    )

@study_plan_bp.route('/', methods=['GET'])
@APIRoute.standard(auth_required_flag=True)
def list_study_plans():
    """Lista todos los planes de estudio"""
    try:
        study_plans = study_plan_service.list_study_plans()
        return APIRoute.success(data=study_plans)
    except Exception as e:
        return APIRoute.error(
            ErrorCodes.SERVER_ERROR,
            str(e),
            status_code=500
        )

@study_plan_bp.route('/<plan_id>', methods=['GET'])
@APIRoute.standard(auth_required_flag=True)
def get_study_plan(plan_id):
    """Obtiene un plan de estudios con sus módulos, temas y evaluaciones"""
    try:
        plan = study_plan_service.get_study_plan(plan_id)
        if plan:
            # Asegurar que sea serializable
            plan = ensure_json_serializable(plan)
            return APIRoute.success(data=plan)
        return APIRoute.error(
            ErrorCodes.NOT_FOUND,
            "Plan de estudios no encontrado"
        )
    except Exception as e:
        print(f"Error al obtener plan de estudios: {str(e)}")
        return APIRoute.error(
            ErrorCodes.SERVER_ERROR,
            str(e),
            status_code=500
        )

@study_plan_bp.route('/<plan_id>', methods=['PUT'])
@APIRoute.standard(auth_required_flag=True, roles=[ROLES["TEACHER"]])
def update_study_plan(plan_id):
    """Actualiza un plan de estudios existente"""
    data = request.get_json()
    
    # El servicio ahora lanza excepciones que son manejadas por APIRoute.standard
    study_plan_service.update_study_plan(plan_id, data)
    
    return APIRoute.success(
        message="Plan de estudios actualizado exitosamente"
    )

@study_plan_bp.route('/<plan_id>', methods=['DELETE'])
@APIRoute.standard(auth_required_flag=True, roles=[ROLES["TEACHER"], ROLES["INSTITUTE_ADMIN"]])
def delete_study_plan(plan_id):
    """Elimina un plan de estudios y sus componentes asociados"""
    # El servicio ahora lanza excepciones que son manejadas por APIRoute.standard
    study_plan_service.delete_study_plan(plan_id)
    
    return APIRoute.success(
        message="Plan de estudios eliminado exitosamente"
    )

@study_plan_bp.route('/<plan_id>/approve', methods=['PUT'])
@APIRoute.standard(auth_required_flag=True, roles=[ROLES["INSTITUTE_ADMIN"]])
def approve_study_plan(plan_id):
    """Aprueba un plan de estudios"""
    if study_plan_service.approve_study_plan(plan_id):
        return APIRoute.success(message="Plan de estudios aprobado exitosamente")
    return APIRoute.error(
        ErrorCodes.UPDATE_ERROR,
        "No se pudo aprobar el plan"
    )

# Rutas para Asignación de Planes a Clases
@study_plan_bp.route('/assignment', methods=['POST'])
@APIRoute.standard(auth_required_flag=True, roles=[ROLES["TEACHER"], ROLES["INSTITUTE_ADMIN"]], required_fields=['study_plan_id', 'class_id', 'subperiod_id', 'assigned_by'])
def assign_plan_to_class():
    """Asigna un plan de estudio a una clase en un subperiodo"""
    data = request.get_json()
    
    # El servicio ahora lanza excepciones que son manejadas por APIRoute.standard
    result = assignment_service.assign_plan_to_class(data)
    
    return APIRoute.success(
        {"id": result},
        message="Plan asignado exitosamente",
        status_code=201
    )

@study_plan_bp.route('/assignment/<assignment_id>', methods=['DELETE'])
@APIRoute.standard(auth_required_flag=True, roles=[ROLES["TEACHER"], ROLES["INSTITUTE_ADMIN"]])
def remove_plan_assignment(assignment_id):
    """Remueve una asignación de plan de estudio"""
    # El servicio ahora lanza excepciones que son manejadas por APIRoute.standard
    assignment_service.remove_plan_assignment(assignment_id)
    
    return APIRoute.success(
        message="Asignación de plan removida exitosamente"
    )

@study_plan_bp.route('/class/<class_id>/subperiod/<subperiod_id>/plan', methods=['GET'])
@APIRoute.standard(auth_required_flag=True)
def get_class_assigned_plan(class_id, subperiod_id):
    """Obtiene el plan de estudio asignado a una clase en un subperiodo"""
    try:
        assignment = assignment_service.get_class_assigned_plan(class_id, subperiod_id)
        
        if assignment:
            # Asegurar que sea serializable
            assignment = ensure_json_serializable(assignment)
            return APIRoute.success(data=assignment)
        return APIRoute.error(
            ErrorCodes.NOT_FOUND,
            "No hay plan asignado para esta clase y subperiodo"
        )
    except Exception as e:
        print(f"Error al obtener plan asignado: {str(e)}")
        return APIRoute.error(
            ErrorCodes.SERVER_ERROR,
            str(e),
            status_code=500
        )

@study_plan_bp.route('/assignments', methods=['GET'])
@APIRoute.standard(auth_required_flag=True)
def list_plan_assignments():
    """Lista todas las asignaciones de planes de estudio"""
    try:
        plan_id = request.args.get('plan_id')  # Opcional
        assignments = assignment_service.list_plan_assignments(plan_id)
        # Asegurar que sea serializable
        assignments = ensure_json_serializable(assignments)
        return APIRoute.success(data=assignments)
    except Exception as e:
        print(f"Error al listar asignaciones: {str(e)}")
        return APIRoute.error(
            ErrorCodes.SERVER_ERROR,
            str(e),
            status_code=500
        )

# Rutas para Módulos
@study_plan_bp.route('/module', methods=['POST'])
@APIRoute.standard(auth_required_flag=True, roles=[ROLES["TEACHER"]], required_fields=['study_plan_id', 'name', 'learning_outcomes', 'evaluation_rubric'])
def create_module():
    """Crea un nuevo módulo"""
    data = request.get_json()
    
    # Extraer topics del payload si existen
    topics_data = data.pop('topics', [])
    print(f"Topics extraídos del payload: {len(topics_data)}")
    
    success, module_id = module_service.create_module(data)
    print(f"Módulo creado: {success}, ID: {module_id}")
    
    if success:
        # Crear topics asociados al módulo
        topics_ids = []
        for i, topic_data in enumerate(topics_data):
            topic_data['module_id'] = module_id
            print(f"Creando topic {i+1}/{len(topics_data)}: {topic_data['name']}")
            topic_success, topic_id = topic_service.create_topic(topic_data)
            if topic_success:
                topics_ids.append(topic_id)
                print(f"Topic creado exitosamente: {topic_id}")
            
        return APIRoute.success(
            {
                "id": module_id,
                "topics": topics_ids
            },
            message="Módulo creado exitosamente",
            status_code=201
        )
    else:
        return APIRoute.error(
            ErrorCodes.CREATION_ERROR,
            module_id
        )

@study_plan_bp.route('/module/<module_id>', methods=['GET'])
@APIRoute.standard(auth_required_flag=True)
def get_module_details(module_id):
    """Obtiene detalles de un módulo con sus temas y evaluaciones"""
    module = module_service.get_module_details(module_id)
    if module:
        # Asegurar que sea serializable
        module = ensure_json_serializable(module)
        return APIRoute.success(data=module)
    return APIRoute.error(
        ErrorCodes.NOT_FOUND,
        "Módulo no encontrado"
    )

@study_plan_bp.route('/module/<module_id>', methods=['PUT'])
@APIRoute.standard(auth_required_flag=True, roles=[ROLES["TEACHER"]])
def update_module(module_id):
    """Actualiza un módulo"""
    try:
        data = request.get_json()
        success, message = module_service.update_module(module_id, data)
        
        if success:
            return APIRoute.success(message=message)
        else:
            return APIRoute.error(
                ErrorCodes.UPDATE_ERROR,
                message
            )
    except Exception as e:
        print(f"Error al actualizar módulo: {str(e)}")
        return APIRoute.error(
            ErrorCodes.SERVER_ERROR,
            str(e),
            status_code=500
        )

@study_plan_bp.route('/module/<module_id>', methods=['DELETE'])
@APIRoute.standard(auth_required_flag=True, roles=[ROLES["TEACHER"]])
def delete_module(module_id):
    """Elimina un módulo y sus componentes asociados"""
    try:
        success, message = module_service.delete_module(module_id)
        
        if success:
            return APIRoute.success(message=message)
        else:
            return APIRoute.error(
                ErrorCodes.DELETE_ERROR,
                message
            )
    except Exception as e:
        print(f"Error al eliminar módulo: {str(e)}")
        return APIRoute.error(
            ErrorCodes.SERVER_ERROR,
            str(e),
            status_code=500
        )

# Rutas para Topics
@study_plan_bp.route('/topic', methods=['POST'])
@APIRoute.standard(auth_required_flag=True, roles=[ROLES["TEACHER"]])
def create_topic():
    """Crea un nuevo topic para un módulo"""
    data = request.get_json()
    success, result = topic_service.create_topic(data)
    
    if success:
        return APIRoute.success(
            {"id": result},
            message="Topic creado exitosamente",
            status_code=201
        )
    else:
        return APIRoute.error(
            ErrorCodes.CREATION_ERROR,
            result
        )

@study_plan_bp.route('/topic', methods=['GET'])
@APIRoute.standard(auth_required_flag=True)
def get_topic():
    """Obtiene detalles de un topic específico"""
    try:
        topic_id = request.args.get('topic_id')
        
        if not topic_id:
            return APIRoute.error(
                ErrorCodes.MISSING_FIELD,
                "ID del topic es requerido"
            )
            
        topic = topic_service.get_topic(topic_id)
        
        if not topic:
            return APIRoute.error(
                ErrorCodes.NOT_FOUND,
                "Topic no encontrado"
            )
            
        # Asegurar que sea serializable
        topic = ensure_json_serializable(topic)
        return APIRoute.success(data=topic)
    except Exception as e:
        print(f"Error al obtener topic: {str(e)}")
        return APIRoute.error(
            ErrorCodes.SERVER_ERROR,
            str(e),
            status_code=500
        )

@study_plan_bp.route('/topic/<topic_id>', methods=['PUT'])
@APIRoute.standard(auth_required_flag=True, roles=[ROLES["TEACHER"]])
def update_topic(topic_id):
    """Actualiza un topic"""
    try:
        data = request.get_json()
        success, message = topic_service.update_topic(topic_id, data)
        
        if success:
            return APIRoute.success(message=message)
        else:
            return APIRoute.error(
                ErrorCodes.UPDATE_ERROR,
                message
            )
    except Exception as e:
        print(f"Error al actualizar topic: {str(e)}")
        return APIRoute.error(
            ErrorCodes.SERVER_ERROR,
            str(e),
            status_code=500
        )

@study_plan_bp.route('/topic/<topic_id>', methods=['DELETE'])
@APIRoute.standard(auth_required_flag=True, roles=[ROLES["TEACHER"]])
def delete_topic(topic_id):
    """Elimina un topic"""
    try:
        success, message = topic_service.delete_topic(topic_id)
        
        if success:
            return APIRoute.success(message=message)
        else:
            return APIRoute.error(
                ErrorCodes.DELETE_ERROR,
                message
            )
    except Exception as e:
        print(f"Error al eliminar topic: {str(e)}")
        return APIRoute.error(
            ErrorCodes.SERVER_ERROR,
            str(e),
            status_code=500
        )

@study_plan_bp.route('/module/<module_id>/topics', methods=['GET'])
@APIRoute.standard(auth_required_flag=True)
def get_module_topics(module_id):
    """Obtiene todos los topics de un módulo"""
    topics = topic_service.get_topics_by_module(module_id)
    # Asegurar que sea serializable
    topics = ensure_json_serializable(topics)
    return APIRoute.success(data=topics)

# Rutas para Evaluaciones
@study_plan_bp.route('/evaluation', methods=['POST'])
@APIRoute.standard(auth_required_flag=True, roles=[ROLES["TEACHER"]], required_fields=['module_id', 'title', 'description', 'weight', 'criteria', 'due_date'])
def create_evaluation():
    """Crea una nueva evaluación"""
    data = request.get_json()
    success, result = evaluation_service.create_evaluation(data)
    
    if success:
        return APIRoute.success(
            {"id": result},
            message="Evaluación creada exitosamente",
            status_code=201
        )
    else:
        return APIRoute.error(
            ErrorCodes.CREATION_ERROR,
            result
        )

@study_plan_bp.route('/evaluation/<evaluation_id>', methods=['GET'])
@APIRoute.standard(auth_required_flag=True)
def get_evaluation(evaluation_id):
    """Obtiene detalles de una evaluación específica"""
    try:
        evaluation = evaluation_service.get_evaluation(evaluation_id)
        
        if evaluation:
            # Asegurar que sea serializable
            evaluation = ensure_json_serializable(evaluation)
            return APIRoute.success(data=evaluation)
        return APIRoute.error(
            ErrorCodes.NOT_FOUND,
            "Evaluación no encontrada"
        )
    except Exception as e:
        print(f"Error al obtener evaluación: {str(e)}")
        return APIRoute.error(
            ErrorCodes.SERVER_ERROR,
            str(e),
            status_code=500
        )

@study_plan_bp.route('/evaluation/<evaluation_id>', methods=['PUT'])
@APIRoute.standard(auth_required_flag=True, roles=[ROLES["TEACHER"]])
def update_evaluation(evaluation_id):
    """Actualiza una evaluación"""
    try:
        data = request.get_json()
        success, message = evaluation_service.update_evaluation(evaluation_id, data)
        
        if success:
            return APIRoute.success(message=message)
        else:
            return APIRoute.error(
                ErrorCodes.UPDATE_ERROR,
                message
            )
    except Exception as e:
        print(f"Error al actualizar evaluación: {str(e)}")
        return APIRoute.error(
            ErrorCodes.SERVER_ERROR,
            str(e),
            status_code=500
        )

@study_plan_bp.route('/evaluation/<evaluation_id>', methods=['DELETE'])
@APIRoute.standard(auth_required_flag=True, roles=[ROLES["TEACHER"]])
def delete_evaluation(evaluation_id):
    """Elimina una evaluación y sus resultados asociados"""
    try:
        success, message = evaluation_service.delete_evaluation(evaluation_id)
        
        if success:
            return APIRoute.success(message=message)
        else:
            return APIRoute.error(
                ErrorCodes.DELETE_ERROR,
                message
            )
    except Exception as e:
        print(f"Error al eliminar evaluación: {str(e)}")
        return APIRoute.error(
            ErrorCodes.SERVER_ERROR,
            str(e),
            status_code=500
        )

@study_plan_bp.route('/evaluation/result', methods=['POST'])
@APIRoute.standard(auth_required_flag=True, roles=[ROLES["TEACHER"]], required_fields=['evaluation_id', 'student_id', 'score'])
def record_evaluation_result():
    """Registra el resultado de una evaluación"""
    data = request.get_json()
    success, result = evaluation_service.record_result(data)
    
    if success:
        return APIRoute.success(
            {"id": result},
            message="Resultado registrado exitosamente",
            status_code=201
        )
    else:
        return APIRoute.error(
            ErrorCodes.CREATION_ERROR,
            result
        )

@study_plan_bp.route('/evaluation/result/<result_id>', methods=['PUT'])
@APIRoute.standard(auth_required_flag=True, roles=[ROLES["TEACHER"]])
def update_evaluation_result(result_id):
    """Actualiza el resultado de una evaluación"""
    try:
        data = request.get_json()
        success, message = evaluation_service.update_result(result_id, data)
        
        if success:
            return APIRoute.success(message=message)
        else:
            return APIRoute.error(
                ErrorCodes.UPDATE_ERROR,
                message
            )
    except Exception as e:
        print(f"Error al actualizar resultado: {str(e)}")
        return APIRoute.error(
            ErrorCodes.SERVER_ERROR,
            str(e),
            status_code=500
        )

@study_plan_bp.route('/evaluation/result/<result_id>', methods=['DELETE'])
@APIRoute.standard(auth_required_flag=True, roles=[ROLES["TEACHER"]])
def delete_evaluation_result(result_id):
    """Elimina el resultado de una evaluación"""
    try:
        success, message = evaluation_service.delete_result(result_id)
        
        if success:
            return APIRoute.success(message=message)
        else:
            return APIRoute.error(
                ErrorCodes.DELETE_ERROR,
                message
            )
    except Exception as e:
        print(f"Error al eliminar resultado: {str(e)}")
        return APIRoute.error(
            ErrorCodes.SERVER_ERROR,
            str(e),
            status_code=500
        )

@study_plan_bp.route('/student/<student_id>/results', methods=['GET'])
@APIRoute.standard(auth_required_flag=True)
def get_student_results(student_id):
    """Obtiene resultados de evaluaciones de un estudiante"""
    module_id = request.args.get('module_id')  # Opcional
    results = evaluation_service.get_student_results(student_id, module_id)
    # Asegurar que sea serializable
    results = ensure_json_serializable(results)
    return APIRoute.success(data=results)

@study_plan_bp.route('/topic/theory', methods=['PUT'])
@APIRoute.standard(auth_required_flag=True, roles=[ROLES["TEACHER"]])
def update_topic_theory():
    """Update the theory content of a topic"""
    try:
        data = request.get_json()
        if 'theory_content' not in data:
            return APIRoute.error(
                ErrorCodes.MISSING_FIELD,
                "Theory content is required"
            )
            
        if 'topic_id' not in data:
            return APIRoute.error(
                ErrorCodes.MISSING_FIELD,
                "Topic ID is required"
            )
            
        topic_id = data.get('topic_id')
        theory_content = data.get('theory_content')
        
        success, message = topic_service.update_topic_theory_content(topic_id, theory_content)
        
        if not success:
            return APIRoute.error(
                ErrorCodes.NOT_FOUND,
                message
            )
            
        return APIRoute.success(
            {"message": "Theory content updated successfully", "topic_id": message},
            status_code=200
        )
    except Exception as e:
        return APIRoute.error(
            ErrorCodes.SERVER_ERROR,
            str(e),
            status_code=500
        )

@study_plan_bp.route('/topic/theory', methods=['GET'])
@APIRoute.standard(auth_required_flag=True)
def get_topic_theory():
    """Get the theory content of a topic"""
    try:
        topic_id = request.args.get('topic_id')
        
        if not topic_id:
            return APIRoute.error(
                ErrorCodes.MISSING_FIELD,
                "Topic ID is required as a query parameter"
            )
            
        theory_content = topic_service.get_topic_theory_content(topic_id)
        
        if theory_content is None:
            return APIRoute.error(
                ErrorCodes.NOT_FOUND,
                "Topic not found"
            )
            
        return APIRoute.success(data={"topic_id": topic_id, "theory_content": theory_content})
    except Exception as e:
        return APIRoute.error(
            ErrorCodes.SERVER_ERROR,
            str(e),
            status_code=500
        )

@study_plan_bp.route('/topic/theory', methods=['DELETE'])
@APIRoute.standard(auth_required_flag=True, roles=[ROLES["TEACHER"]])
def delete_topic_theory():
    """Delete the theory content of a topic"""
    try:
        topic_id = request.args.get('topic_id')
        
        if not topic_id:
            return APIRoute.error(
                ErrorCodes.MISSING_FIELD,
                "Topic ID is required as a query parameter"
            )
            
        success, message = topic_service.delete_topic_theory_content(topic_id)
        
        if not success:
            return APIRoute.error(
                ErrorCodes.NOT_FOUND,
                message
            )
            
        return APIRoute.success(
            {"message": "Theory content deleted successfully", "topic_id": message},
            status_code=200
        )
    except Exception as e:
        return APIRoute.error(
            ErrorCodes.SERVER_ERROR,
            str(e),
            status_code=500
        ) 