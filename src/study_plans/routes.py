from flask import request, jsonify
from typing import Optional
from src.shared.standardization import APIBlueprint, APIRoute, ErrorCodes
from src.profiles.services import ProfileService
from .services import (
    StudyPlanService, 
    StudyPlanAssignmentService,
    ModuleService, 
    EvaluationService, 
    TopicService,
    ContentTypeService,
    LearningMethodologyService,
    TopicContentService,
    TopicResourceService
)
from src.resources.services import ResourceService
import logging
from src.shared.constants import ROLES
from bson import ObjectId
from src.shared.utils import ensure_json_serializable
from datetime import datetime
from src.shared.database import get_db
from .models import ContentTypes, LearningMethodologyTypes
from src.shared.constants import STATUS

study_plan_bp = APIBlueprint('study_plan', __name__)

study_plan_service = StudyPlanService()
assignment_service = StudyPlanAssignmentService()
module_service = ModuleService()
evaluation_service = EvaluationService()
topic_service = TopicService()
content_type_service = ContentTypeService()
methodology_service = LearningMethodologyService()
topic_content_service = TopicContentService()
resource_service = ResourceService()
topic_resource_service = TopicResourceService()

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
        email = request.args.get('email')
        study_plans = study_plan_service.list_study_plans(email)
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
        logging.error(f"Error al obtener plan de estudios: {str(e)}")
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
        logging.error(f"Error al obtener plan asignado: {str(e)}")
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
        logging.error(f"Error al listar asignaciones: {str(e)}")
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
    logging.info(f"Topics extraídos del payload: {len(topics_data)}")
    
    success, module_id = module_service.create_module(data)
    logging.info(f"Módulo creado: {success}, ID: {module_id}")
    
    if success:
        # Crear topics asociados al módulo
        topics_ids = []
        for i, topic_data in enumerate(topics_data):
            topic_data['module_id'] = module_id
            topic_success, topic_id = topic_service.create_topic(topic_data)
            if topic_success:
                topics_ids.append(topic_id)
                logging.info(f"Topic creado exitosamente: {topic_id}")
            
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
        
        success, message = topic_service.update_theory_content(topic_id, theory_content)
        
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

# Rutas para Tipos de Contenido
@study_plan_bp.route('/content-types', methods=['GET'])
@APIRoute.standard(auth_required_flag=True)
def list_content_types():
    """Lista todos los tipos de contenido disponibles"""
    try:
        category = request.args.get('category')
        content_types = content_type_service.list_content_types(category)
        return APIRoute.success(data=content_types)
    except Exception as e:
        logging.error(f"Error al listar tipos de contenido: {str(e)}")
        return APIRoute.error(
            ErrorCodes.SERVER_ERROR,
            str(e),
            status_code=500
        )

@study_plan_bp.route('/content-types', methods=['POST'])
@APIRoute.standard(auth_required_flag=True, roles=[ROLES["INSTITUTE_ADMIN"]], required_fields=['code', 'name', 'category', 'description'])
def create_content_type():
    """Crea un nuevo tipo de contenido"""
    try:
        data = request.get_json()
        success, result = content_type_service.create_content_type(data)
        
        if not success:
            return APIRoute.error(
                ErrorCodes.BAD_REQUEST,
                result,
                status_code=400
            )
            
        return APIRoute.success(
            {"id": result},
            message="Tipo de contenido creado exitosamente",
            status_code=201
        )
    except Exception as e:
        logging.error(f"Error al crear tipo de contenido: {str(e)}")
        return APIRoute.error(
            ErrorCodes.SERVER_ERROR,
            str(e),
            status_code=500
        )

@study_plan_bp.route('/content-types/<code>', methods=['GET'])
@APIRoute.standard(auth_required_flag=True)
def get_content_type(code):
    """Obtiene un tipo de contenido por su código"""
    try:
        content_type = content_type_service.get_content_type(code)
        
        if not content_type:
            return APIRoute.error(
                ErrorCodes.NOT_FOUND,
                "Tipo de contenido no encontrado",
                status_code=404
            )
            
        return APIRoute.success(data=content_type)
    except Exception as e:
        logging.error(f"Error al obtener tipo de contenido: {str(e)}")
        return APIRoute.error(
            ErrorCodes.SERVER_ERROR,
            str(e),
            status_code=500
        )

@study_plan_bp.route('/content-types/generate', methods=['POST'])
@APIRoute.standard(auth_required_flag=True, roles=[ROLES["TEACHER"]], 
                  required_fields=['topic_id', 'content_type', 'learning_methodology'])
def generate_content_by_type():
    """Genera contenido según tipo y metodología para un tema"""
    try:
        data = request.get_json()
        topic_id = data.get('topic_id')
        content_type = data.get('content_type')
        learning_methodology = data.get('learning_methodology')
        
        # Verificar que el tema existe
        topic = topic_service.get_topic(topic_id)
        if not topic:
            return APIRoute.error(
                ErrorCodes.NOT_FOUND,
                "Tema no encontrado",
                status_code=404
            )
            
        # Verificar que el tipo de contenido es válido
        if content_type not in ContentTypes.get_all_types():
            return APIRoute.error(
                ErrorCodes.BAD_REQUEST,
                f"Tipo de contenido '{content_type}' no válido",
                status_code=400
            )
            
        # Verificar que la metodología es válida
        methodology_service = LearningMethodologyService()
        methodology = methodology_service.get_methodology(learning_methodology)
        if not methodology:
            # Si no existe en BD, verificar si es una metodología predefinida
            valid_methodologies = list(LearningMethodologyTypes.get_categories())
            valid_methodologies_flat = []
            for category in valid_methodologies:
                valid_methodologies_flat.extend(LearningMethodologyTypes.get_categories()[category])
                
            if learning_methodology not in valid_methodologies_flat:
                return APIRoute.error(
                    ErrorCodes.BAD_REQUEST,
                    f"Metodología '{learning_methodology}' no válida",
                    status_code=400
                )
            
        # Generar contenido según tipo y metodología
        # Esto podría expandirse en el futuro con llamadas a una API de IA
        content_data = {
            "topic_id": topic_id,
            "content_type": content_type,
            "learning_methodologies": [learning_methodology],
            "content": f"Contenido generado para tema: {topic.get('name')} usando metodología {learning_methodology}",
            "ai_credits": True,
            "status": "draft"
        }
        
        # Crear el contenido 
        topic_content_service = TopicContentService()
        success, content_id = topic_content_service.create_content(content_data)
        
        if not success:
            return APIRoute.error(
                ErrorCodes.BAD_REQUEST,
                content_id,
                status_code=400
            )
        
        # Obtener el contenido creado
        content = topic_content_service.get_content(content_id)
        
        # Aplicar adaptación según metodología
        success, adapted_content = topic_content_service.adapt_content_to_methodology(content_id, learning_methodology)
        
        response = {
            "content_id": content_id,
            "original_content": content,
            "adapted_content": adapted_content if success else None
        }
            
        return APIRoute.success(
            data=response,
            message="Contenido generado exitosamente",
            status_code=201
        )
    except Exception as e:
        logging.error(f"Error al generar contenido: {str(e)}")
        return APIRoute.error(
            ErrorCodes.SERVER_ERROR,
            str(e),
            status_code=500
        )

# Rutas para Metodologías de Aprendizaje
@study_plan_bp.route('/learning-methods', methods=['GET'])
@APIRoute.standard(auth_required_flag=True)
def list_methodologies():
    """Lista todas las metodologías de aprendizaje disponibles"""
    try:
        methodologies = methodology_service.list_methodologies()
        return APIRoute.success(data=methodologies)
    except Exception as e:
        logging.error(f"Error al listar metodologías: {str(e)}")
        return APIRoute.error(
            ErrorCodes.SERVER_ERROR,
            str(e),
            status_code=500
        )

@study_plan_bp.route('/learning-methods', methods=['POST'])
@APIRoute.standard(auth_required_flag=True, roles=[ROLES["INSTITUTE_ADMIN"]], required_fields=['code', 'name', 'description'])
def create_methodology():
    """Crea una nueva metodología de aprendizaje"""
    try:
        data = request.get_json()
        success, result = methodology_service.create_methodology(data)
        
        if not success:
            return APIRoute.error(
                ErrorCodes.BAD_REQUEST,
                result,
                status_code=400
            )
            
        return APIRoute.success(
            {"id": result},
            message="Metodología creada exitosamente",
            status_code=201
        )
    except Exception as e:
        logging.error(f"Error al crear metodología: {str(e)}")
        return APIRoute.error(
            ErrorCodes.SERVER_ERROR,
            str(e),
            status_code=500
        )

@study_plan_bp.route('/learning-methods/compatibility', methods=['POST'])
@APIRoute.standard(auth_required_flag=True, required_fields=['cognitive_profile'])
def get_compatible_methodologies():
    """Obtiene metodologías compatibles con un perfil cognitivo"""
    try:
        data = request.get_json()
        cognitive_profile = data.get('cognitive_profile')
        
        methodologies = methodology_service.get_compatible_methodologies(cognitive_profile)
        return APIRoute.success(data=methodologies)
    except Exception as e:
        logging.error(f"Error al obtener metodologías compatibles: {str(e)}")
        return APIRoute.error(
            ErrorCodes.SERVER_ERROR,
            str(e),
            status_code=500
        )

@study_plan_bp.route('/learning-methods/list', methods=['GET'])
@APIRoute.standard(auth_required_flag=True)
def list_learning_methods():
    """Lista todas las metodologías de aprendizaje disponibles"""
    try:
        # Obtener metodologías por categoría del sistema
        methods_by_category = LearningMethodologyTypes.get_categories()
        
        # Generar respuesta completa con información por metodología
        response = {
            "by_category": methods_by_category
        }
        
        # Añadir compatibilidad por defecto
        response["default_compatibility"] = LearningMethodologyTypes.get_default_content_compatibility()
        
        # Buscar metodologías personalizadas en BD
        methodology_service = LearningMethodologyService()
        custom_methods = methodology_service.list_methodologies()
        
        response["custom_methods"] = custom_methods
        
        # Añadir información descriptiva para cada metodología
        descriptions = {}
        for category_name, methods in methods_by_category.items():
            for method_code in methods:
                # Buscar en base de datos si existe definición personalizada
                method_def = get_db().learning_methodologies.find_one({"code": method_code})
                
                if method_def:
                    descriptions[method_code] = {
                        "name": method_def.get("name", method_code),
                        "description": method_def.get("description", ""),
                        "category": category_name,
                        "compatible_content_types": method_def.get("compatible_content_types", []),
                        "cognitive_profile_match": method_def.get("cognitive_profile_match", {})
                    }
                else:
                    # Definición por defecto si no existe en BD
                    descriptions[method_code] = {
                        "name": method_code.replace("_", " ").title(),
                        "description": f"Metodología de aprendizaje {method_code}",
                        "category": category_name,
                        "compatible_content_types": [],
                        "cognitive_profile_match": {}
                    }
        
        response["descriptions"] = descriptions
        
        return APIRoute.success(data=response)
    except Exception as e:
        logging.error(f"Error al listar metodologías de aprendizaje: {str(e)}")
        return APIRoute.error(
            ErrorCodes.SERVER_ERROR,
            str(e),
            status_code=500
        )

@study_plan_bp.route('/learning-methods/compatibility', methods=['GET'])
@APIRoute.standard(auth_required_flag=True)
def get_methodology_compatibility():
    """Obtiene compatibilidad entre metodologías y perfiles cognitivos"""
    try:
        # Obtener el perfil cognitivo solicitado
        profile_type = request.args.get('profile_type') 
        
        # Si se proporciona un perfil específico, calcular compatibilidad
        if profile_type:
            methodology_service = LearningMethodologyService()
            compatibility = methodology_service.get_compatible_methodologies(profile_type)
            return APIRoute.success(data=compatibility)
        
        # Si no hay perfil específico, retornar información general
        response = {
            "compatible_methodologies": {
                "visual": LearningMethodologyTypes.get_categories()["sensory"][0:1],
                "auditory": LearningMethodologyTypes.get_categories()["sensory"][1:2],
                "read_write": LearningMethodologyTypes.get_categories()["sensory"][2:3],
                "kinesthetic": LearningMethodologyTypes.get_categories()["sensory"][3:4],
                "adhd": [LearningMethodologyTypes.ADHD_ADAPTED, LearningMethodologyTypes.MICROLEARNING, 
                         LearningMethodologyTypes.KINESTHETIC, LearningMethodologyTypes.GAMIFICATION],
                "dyslexia": [LearningMethodologyTypes.DYSLEXIA_ADAPTED, LearningMethodologyTypes.AUDITORY,
                            LearningMethodologyTypes.VISUAL, LearningMethodologyTypes.KINESTHETIC],
                "autism": [LearningMethodologyTypes.AUTISM_ADAPTED, LearningMethodologyTypes.VISUAL,
                          LearningMethodologyTypes.CONCEPT_MAPPING, LearningMethodologyTypes.MIND_MAP]
            }
        }
        
        return APIRoute.success(data=response)
    except Exception as e:
        logging.error(f"Error al obtener compatibilidad de metodologías: {str(e)}")
        return APIRoute.error(
            ErrorCodes.SERVER_ERROR,
            str(e),
            status_code=500
        )

# Rutas para Contenido de Temas
@study_plan_bp.route('/topic/<topic_id>/content', methods=['GET'])
@APIRoute.standard(auth_required_flag=True)
def get_topic_contents(topic_id):
    """Obtiene todos los contenidos asociados a un tema"""
    try:
        contents = topic_content_service.get_topic_contents(topic_id)
        return APIRoute.success(data=contents)
    except Exception as e:
        logging.error(f"Error al obtener contenidos del tema: {str(e)}")
        return APIRoute.error(
            ErrorCodes.SERVER_ERROR,
            str(e),
            status_code=500
        )

@study_plan_bp.route('/topic/<topic_id>/content/<content_type>', methods=['GET'])
@APIRoute.standard(auth_required_flag=True)
def get_topic_content_by_type(topic_id, content_type):
    """Obtiene un contenido específico de un tema según su tipo"""
    try:
        content = topic_content_service.get_topic_content_by_type(topic_id, content_type)
        
        if not content:
            return APIRoute.error(
                ErrorCodes.NOT_FOUND,
                f"Contenido de tipo '{content_type}' no encontrado para este tema",
                status_code=404
            )
            
        return APIRoute.success(data=content)
    except Exception as e:
        logging.error(f"Error al obtener contenido por tipo: {str(e)}")
        return APIRoute.error(
            ErrorCodes.SERVER_ERROR,
            str(e),
            status_code=500
        )

@study_plan_bp.route('/topic/content', methods=['POST'])
@APIRoute.standard(auth_required_flag=True, roles=[ROLES["TEACHER"]], required_fields=['topic_id', 'content', 'content_type'])
def create_topic_content():
    """Crea un nuevo contenido para un tema"""
    try:
        data = request.get_json()
        success, result = topic_content_service.create_content(data)
        
        if not success:
            return APIRoute.error(
                ErrorCodes.BAD_REQUEST,
                result,
                status_code=400
            )
            
        return APIRoute.success(
            {"id": result},
            message="Contenido creado exitosamente",
            status_code=201
        )
    except Exception as e:
        logging.error(f"Error al crear contenido: {str(e)}")
        return APIRoute.error(
            ErrorCodes.SERVER_ERROR,
            str(e),
            status_code=500
        )

@study_plan_bp.route('/topic/content/<content_id>', methods=['PUT'])
@APIRoute.standard(auth_required_flag=True, roles=[ROLES["TEACHER"]])
def update_topic_content(content_id):
    """Actualiza un contenido existente"""
    try:
        data = request.get_json()
        success, result = topic_content_service.update_content(content_id, data)
        
        if not success:
            return APIRoute.error(
                ErrorCodes.BAD_REQUEST,
                result,
                status_code=400
            )
            
        return APIRoute.success(
            message="Contenido actualizado exitosamente"
        )
    except Exception as e:
        logging.error(f"Error al actualizar contenido: {str(e)}")
        return APIRoute.error(
            ErrorCodes.SERVER_ERROR,
            str(e),
            status_code=500
        )

@study_plan_bp.route('/topic/content/<content_id>', methods=['DELETE'])
@APIRoute.standard(auth_required_flag=True, roles=[ROLES["TEACHER"]])
def delete_topic_content(content_id):
    """Elimina un contenido existente"""
    try:
        success, result = topic_content_service.delete_content(content_id)
        
        if not success:
            return APIRoute.error(
                ErrorCodes.BAD_REQUEST,
                result,
                status_code=400
            )
            
        return APIRoute.success(
            message="Contenido eliminado exitosamente"
        )
    except Exception as e:
        logging.error(f"Error al eliminar contenido: {str(e)}")
        return APIRoute.error(
            ErrorCodes.SERVER_ERROR,
            str(e),
            status_code=500
        )

# Rutas para Recursos de Aprendizaje
@study_plan_bp.route('/resources', methods=['GET'])
@APIRoute.standard(auth_required_flag=True)
def list_resources():
    """Lista recursos educativos, opcionalmente filtrados por tipo o etiquetas"""
    try:
        resource_type = request.args.get('type')
        tags = request.args.getlist('tag')
        resources = resource_service.list_resources(resource_type, tags if tags else None)
        return APIRoute.success(data=resources)
    except Exception as e:
        logging.error(f"Error al listar recursos: {str(e)}")
        return APIRoute.error(
            ErrorCodes.SERVER_ERROR,
            str(e),
            status_code=500
        )

@study_plan_bp.route('/resources', methods=['POST'])
@APIRoute.standard(auth_required_flag=True, roles=[ROLES["TEACHER"]], required_fields=['title', 'resource_type', 'url'])
def create_resource():
    """Crea un nuevo recurso educativo"""
    try:
        data = request.get_json()
        
        # Preparar los datos para el ResourceService
        resource_data = {
            "name": data.get('title'),
            "type": data.get('resource_type'),
            "url": data.get('url'),
            "description": data.get('description', ''),
            "tags": data.get('tags', []),
            "created_by": request.user_id
        }
        
        # Si se especifica un folder_id, incluirlo
        if 'folder_id' in data:
            resource_data['folder_id'] = data['folder_id']
            
        # Crear el recurso usando ResourceService
        success, result = resource_service.create_resource(resource_data)
        
        if not success:
            return APIRoute.error(
                ErrorCodes.BAD_REQUEST,
                result,
                status_code=400
            )
        
        # Si se especifica un topic_id, vincular el recurso al tema
        if 'topic_id' in data:
            topic_id = data['topic_id']
            try:
                # Vincular el recurso al tema
                link_success, link_result = topic_resource_service.link_resource_to_topic(
                    topic_id=topic_id,
                    resource_id=result,
                    relevance_score=data.get('relevance_score', 0.5),
                    recommended_for=data.get('recommended_for', []),
                    usage_context=data.get('usage_context', 'supplementary'),
                    content_types=data.get('content_types', []),
                    created_by=request.user_id
                )
                
                if not link_success:
                    logging.warning(f"No se pudo vincular el recurso {result} al tema {topic_id}: {link_result}")
            except Exception as e:
                logging.error(f"Error al vincular recurso al tema: {str(e)}")
            
        return APIRoute.success(
            {"id": result},
            message="Recurso creado exitosamente",
            status_code=201
        )
    except Exception as e:
        logging.error(f"Error al crear recurso: {str(e)}")
        return APIRoute.error(
            ErrorCodes.SERVER_ERROR,
            str(e),
            status_code=500
        )

@study_plan_bp.route('/resources/<resource_id>', methods=['GET'])
@APIRoute.standard(auth_required_flag=True)
def get_resource(resource_id):
    """Obtiene un recurso por su ID"""
    try:
        resource = resource_service.get_resource(resource_id)
        
        if not resource:
            return APIRoute.error(
                ErrorCodes.NOT_FOUND,
                "Recurso no encontrado",
                status_code=404
            )
            
        return APIRoute.success(data=resource)
    except Exception as e:
        logging.error(f"Error al obtener recurso: {str(e)}")
        return APIRoute.error(
            ErrorCodes.SERVER_ERROR,
            str(e),
            status_code=500
        )

@study_plan_bp.route('/resources/<resource_id>', methods=['PUT'])
@APIRoute.standard(auth_required_flag=True, roles=[ROLES["TEACHER"]])
def update_resource(resource_id):
    """Actualiza un recurso existente"""
    try:
        data = request.get_json()
        success, result = resource_service.update_resource(resource_id, data)
        
        if not success:
            return APIRoute.error(
                ErrorCodes.BAD_REQUEST,
                result,
                status_code=400
            )
            
        return APIRoute.success(
            message="Recurso actualizado exitosamente"
        )
    except Exception as e:
        logging.error(f"Error al actualizar recurso: {str(e)}")
        return APIRoute.error(
            ErrorCodes.SERVER_ERROR,
            str(e),
            status_code=500
        )

@study_plan_bp.route('/topic-resources/<topic_id>/<resource_id>', methods=['POST'])
@APIRoute.standard(auth_required_flag=True, roles=[ROLES["TEACHER"]], required_fields=['relevance_score', 'recommended_for', 'usage_context', 'content_types'])
def link_resource_to_topic(topic_id, resource_id):
    """
    Vincula un recurso específico a un tema.
    
    Args:
        topic_id: ID del tema
        resource_id: ID del recurso a vincular
    
    Returns:
        Respuesta con el estado de la operación
    """
    data = request.get_json()
    current_user = request.user
    
    relevance_score = data.get("relevance_score", 0.5)
    recommended_for = data.get("recommended_for", [])
    usage_context = data.get("usage_context", "supplementary")
    content_types = data.get("content_types", [])
    
    success, result = topic_resource_service.link_resource_to_topic(
        topic_id=topic_id,
        resource_id=resource_id,
        relevance_score=relevance_score,
        recommended_for=recommended_for,
        usage_context=usage_context,
        content_types=content_types,
        created_by=str(current_user["_id"])
    )
    
    if success:
        return {
            "success": True,
            "message": "Recurso vinculado correctamente al tema",
            "data": {"id": result}
        }
    else:
        raise APIRoute.error(
            ErrorCodes.BAD_REQUEST,
            result,
            status_code=400
        )

@study_plan_bp.route('/topic-resources/<topic_id>/<resource_id>', methods=['DELETE'])
@APIRoute.standard(auth_required_flag=True, roles=[ROLES["TEACHER"]])
def unlink_resource_from_topic(topic_id, resource_id):
    """
    Desvincula un recurso de un tema.
    
    Args:
        topic_id: ID del tema
        resource_id: ID del recurso
    
    Returns:
        Respuesta con el estado de la operación
    """
    current_user = request.user
    
    success, message = topic_resource_service.unlink_resource_from_topic(topic_id, resource_id)
    
    if success:
        return {
            "success": True,
            "message": message,
            "data": None
        }
    else:
        raise APIRoute.error(
            ErrorCodes.NOT_FOUND,
            message,
            status_code=404
        )

@study_plan_bp.route('/topic-resources/<topic_id>', methods=['GET'])
@APIRoute.standard(auth_required_flag=True)
def get_topic_resources(topic_id):
    """
    Obtiene todos los recursos asociados a un tema específico.
    
    Args:
        topic_id: ID del tema
    
    Returns:
        Lista de recursos asociados al tema
    """
    current_user = request.user
    content_type = request.args.get('content_type')
    usage_context = request.args.get('usage_context')
    personalized = request.args.get('personalized', 'false').lower() == 'true'
    
    # Obtener perfil cognitivo si es necesario para personalización
    cognitive_profile = None
    if personalized:
        profile_service = ProfileService()
        profile = profile_service.get_user_profile(str(current_user["_id"]))
        if profile:
            cognitive_profile = profile.get("cognitive_profile", {})
    
    resources = topic_resource_service.get_topic_resources(
        topic_id=topic_id,
        cognitive_profile=cognitive_profile,
        content_type=content_type,
        usage_context=usage_context
    )
    
    return {
        "success": True,
        "message": f"Se encontraron {len(resources)} recursos para el tema",
        "data": resources
    }

@study_plan_bp.route('/resource-topics/<resource_id>', methods=['GET'])
@APIRoute.standard(auth_required_flag=True)
def get_resource_topics(resource_id):
    """
    Obtiene todos los temas asociados a un recurso específico.
    
    Args:
        resource_id: ID del recurso
    
    Returns:
        Lista de temas asociados al recurso
    """
    current_user = request.user
    
    topics = topic_resource_service.get_resource_topics(resource_id)
    
    return {
        "success": True,
        "message": f"Se encontraron {len(topics)} temas para el recurso",
        "data": topics
    }
