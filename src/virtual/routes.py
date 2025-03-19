from flask import request
from src.shared.standardization import APIBlueprint, APIRoute, ErrorCodes
from src.shared.constants import ROLES
from src.shared.database import get_db
from bson import ObjectId
from datetime import datetime
import logging

from .services import VirtualModuleService, VirtualTopicService, VirtualEvaluationService
from src.study_plans.models import ContentTypes, LearningMethodologyTypes

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

@virtual_bp.route('/generate', methods=['POST'])
@APIRoute.standard(auth_required_flag=True, roles=[ROLES["STUDENT"], ROLES["TEACHER"]], required_fields=['class_id', 'study_plan_id'])
def generate_virtual_modules():
    """Genera o actualiza módulos virtuales personalizados para un estudiante"""
    try:
        data = request.get_json()
        class_id = data.get('class_id')
        study_plan_id = data.get('study_plan_id')
        student_id = request.user_id  # El estudiante que solicita la generación
        
        # Opción para especificar otro estudiante (solo para profesores)
        if data.get('student_id') and "TEACHER" in request.user_roles:
            student_id = data.get('student_id')
            
        # Preferencias de personalización (opcionales)
        preferences = data.get('preferences', {})
        adaptive_options = data.get('adaptive_options', {})
        
        # 1. Verificar que el estudiante está inscrito en la clase
        enrollment = get_db().enrollments.find_one({
            "student_id": ObjectId(student_id),
            "class_id": ObjectId(class_id),
            "status": "active"
        })
        
        if not enrollment:
            return APIRoute.error(
                ErrorCodes.UNAUTHORIZED,
                "No estás inscrito en esta clase o la inscripción no está activa",
                status_code=403
            )
            
        # 2. Verificar que el plan de estudios está asignado a la clase
        assignment = get_db().study_plan_assignments.find_one({
            "class_id": ObjectId(class_id),
            "study_plan_id": ObjectId(study_plan_id),
            "is_active": True
        })
        
        if not assignment:
            return APIRoute.error(
                ErrorCodes.BAD_REQUEST,
                "El plan de estudios no está asignado a esta clase",
                status_code=400
            )
            
        # 3. Verificar que el plan de estudios existe
        study_plan = get_db().study_plans.find_one({
            "_id": ObjectId(study_plan_id)
        })
        
        if not study_plan:
            return APIRoute.error(
                ErrorCodes.NOT_FOUND,
                "Plan de estudios no encontrado",
                status_code=404
            )
            
        # 4. Obtener perfil cognitivo del estudiante
        student = get_db().users.find_one({"_id": ObjectId(student_id)})
        if not student:
            return APIRoute.error(
                ErrorCodes.NOT_FOUND,
                "Estudiante no encontrado",
                status_code=404
            )
            
        cognitive_profile = student.get("cognitive_profile", {})
        
        # 5. Obtener perfil cognitivo personalizado si existe en opciones adaptativas
        if adaptive_options.get("cognitive_profile"):
            cognitive_profile = {**cognitive_profile, **adaptive_options.get("cognitive_profile")}
            
        # 6. Comenzar generación de módulos virtuales
        # Obtener módulos del plan de estudios
        modules = list(get_db().modules.find({"study_plan_id": ObjectId(study_plan_id)}))
        
        # Crear o actualizar módulos virtuales
        created = []
        updated = []
        errors = []
        
        for module in modules:
            try:
                module_id = str(module["_id"])
                
                # Verificar si ya existe un módulo virtual para este estudiante y módulo
                existing = get_db().virtual_modules.find_one({
                    "module_id": ObjectId(module_id),
                    "student_id": ObjectId(student_id)
                })
                
                # Datos para crear/actualizar
                module_data = {
                    "module_id": module_id,
                    "student_id": student_id,
                    "name": module.get("name"),
                    "adaptations": {
                        "cognitive_profile": cognitive_profile,
                        "preferences": preferences
                    },
                    "status": "active"
                }
                
                if existing:
                    # Actualizar módulo existente
                    result = get_db().virtual_modules.update_one(
                        {"_id": existing["_id"]},
                        {"$set": {
                            "adaptations": module_data["adaptations"],
                            "updated_at": datetime.now()
                        }}
                    )
                    
                    updated.append({
                        "module_id": module_id,
                        "virtual_module_id": str(existing["_id"])
                    })
                else:
                    # Crear nuevo módulo virtual
                    result = get_db().virtual_modules.insert_one({
                        "module_id": ObjectId(module_id),
                        "student_id": ObjectId(student_id),
                        "name": module.get("name"),
                        "adaptations": module_data["adaptations"],
                        "status": "active",
                        "created_at": datetime.now(),
                        "updated_at": datetime.now(),
                        "progress": 0.0,
                        "completion_status": "not_started"
                    })
                    
                    created.append({
                        "module_id": module_id,
                        "virtual_module_id": str(result.inserted_id)
                    })
                    
                # Para cada módulo, procesar temas
                await_generation = data.get('await_content_generation', False)
                if await_generation:
                    virtual_module_id = str(existing["_id"]) if existing else str(result.inserted_id)
                    generate_virtual_topics(module_id, student_id, virtual_module_id, cognitive_profile, preferences)
                
            except Exception as e:
                errors.append({
                    "module_id": module_id if 'module_id' in locals() else "unknown",
                    "error": str(e)
                })
        
        # 7. Iniciar generación asincrónica de temas si no se esperó por ella
        # (esto se haría con un sistema de colas en una implementación completa)
        if not data.get('await_content_generation', False):
            # En una implementación real, aquí se añadiría una tarea asincrónica
            pass
        
        return APIRoute.success(
            data={
                "created_modules": created,
                "updated_modules": updated,
                "errors": errors,
                "message": "Generación de contenido personalizado iniciada"
            },
            message="Módulos virtuales generados exitosamente",
            status_code=201 if created else 200
        )
    except Exception as e:
        logging.error(f"Error al generar módulos virtuales: {str(e)}")
        return APIRoute.error(
            ErrorCodes.SERVER_ERROR,
            str(e),
            status_code=500
        )

@virtual_bp.route('/student/<student_id>/recommendations', methods=['GET'])
@APIRoute.standard(auth_required_flag=True)
def get_personalized_recommendations(student_id):
    """Obtiene recomendaciones personalizadas para un estudiante"""
    try:
        # Parámetro opcional para recomendaciones específicas de un módulo
        module_id = request.args.get('module_id')
        topic_id = request.args.get('topic_id')
        
        # Verificar que el estudiante existe
        student = get_db().users.find_one({"_id": ObjectId(student_id)})
        if not student:
            return APIRoute.error(
                ErrorCodes.NOT_FOUND,
                "Estudiante no encontrado",
                status_code=404
            )
            
        # Obtener perfil cognitivo del estudiante
        cognitive_profile = student.get("cognitive_profile", {})
        
        # Generar recomendaciones según el perfil
        recommendations = {
            "learning_methodologies": [],
            "content_types": [],
            "resources": []
        }
        
        # 1. Metodologías de aprendizaje recomendadas
        learning_method_strengths = {}
        
        # Calcular compatibilidad con metodologías según perfil
        for method_type, compatibility in LearningMethodologyTypes.get_default_content_compatibility().items():
            score = 0
            
            # Aumentar puntuación según perfil cognitivo
            if method_type == "visual" and cognitive_profile.get("visual_strength", 0) > 0.6:
                score += 2
            elif method_type == "auditory" and cognitive_profile.get("auditory_strength", 0) > 0.6:
                score += 2
            elif method_type == "read_write" and cognitive_profile.get("read_write_strength", 0) > 0.6:
                score += 2
            elif method_type == "kinesthetic" and cognitive_profile.get("kinesthetic_strength", 0) > 0.6:
                score += 2
                
            # Ajustar según adaptaciones específicas
            if method_type == "adhd_adapted" and cognitive_profile.get("adhd", False):
                score += 3
            elif method_type == "dyslexia_adapted" and cognitive_profile.get("dyslexia", False):
                score += 3
            elif method_type == "autism_adapted" and cognitive_profile.get("autism", False):
                score += 3
                
            if score > 0:
                learning_method_strengths[method_type] = score
        
        # Ordenar metodologías por puntuación
        sorted_methods = sorted(learning_method_strengths.items(), key=lambda x: x[1], reverse=True)
        recommendations["learning_methodologies"] = [
            {"code": method, "score": score} 
            for method, score in sorted_methods[:5]
        ]
        
        # 2. Tipos de contenido recomendados según metodologías
        content_type_scores = {}
        
        # Puntuar tipos de contenido según metodologías recomendadas
        for method, score in sorted_methods[:3]:  # Usar top 3 metodologías
            compatible_types = LearningMethodologyTypes.get_default_content_compatibility().get(method, [])
            for content_type in compatible_types:
                if content_type in content_type_scores:
                    content_type_scores[content_type] += score
                else:
                    content_type_scores[content_type] = score
        
        # Ordenar tipos de contenido por puntuación
        sorted_types = sorted(content_type_scores.items(), key=lambda x: x[1], reverse=True)
        recommendations["content_types"] = [
            {"code": ctype, "score": score} 
            for ctype, score in sorted_types[:8]  # Recomendar top 8 tipos
        ]
        
        # 3. Recursos específicos según tema/módulo si se proporciona
        if topic_id:
            # Importar servicio de recomendaciones
            from src.study_plans.services import ContentRecommendationService
            
            recommendation_service = ContentRecommendationService()
            topic_recommendations = recommendation_service.get_content_recommendations(topic_id)
            
            # Añadir recursos recomendados para el tema
            recommendations["resources"] = {
                "from_topic": topic_id,
                "pdfs": topic_recommendations.get("pdfs", [])[:3],
                "web_resources": topic_recommendations.get("web_resources", [])[:3],
                "diagrams": topic_recommendations.get("diagrams", {}).get("existing_diagrams", [])[:2],
                "suggested_templates": topic_recommendations.get("diagrams", {}).get("suggested_templates", [])[:2]
            }
        elif module_id:
            # Si se proporciona módulo, obtener sus temas
            topics = list(get_db().topics.find({"module_id": ObjectId(module_id)}))
            
            if topics:
                # Usar el primer tema para recomendaciones
                sample_topic = str(topics[0]["_id"])
                
                # Importar servicio de recomendaciones
                from src.study_plans.services import ContentRecommendationService
                
                recommendation_service = ContentRecommendationService()
                topic_recommendations = recommendation_service.get_content_recommendations(sample_topic)
                
                # Añadir recursos recomendados para el tema
                recommendations["resources"] = {
                    "from_module": module_id,
                    "pdfs": topic_recommendations.get("pdfs", [])[:3],
                    "web_resources": topic_recommendations.get("web_resources", [])[:3],
                    "diagrams": topic_recommendations.get("diagrams", {}).get("existing_diagrams", [])[:2],
                    "suggested_templates": topic_recommendations.get("diagrams", {}).get("suggested_templates", [])[:2]
                }
        
        return APIRoute.success(data=recommendations)
    except Exception as e:
        logging.error(f"Error al obtener recomendaciones personalizadas: {str(e)}")
        return APIRoute.error(
            ErrorCodes.SERVER_ERROR,
            str(e),
            status_code=500
        )

def generate_virtual_topics(module_id: str, student_id: str, virtual_module_id: str, cognitive_profile: dict, preferences: dict):
    """
    Genera temas virtuales para un módulo. Función auxiliar separada para procesamiento asincrónico.
    """
    try:
        # Obtener temas del módulo
        topics = list(get_db().topics.find({"module_id": ObjectId(module_id)}))
        
        for topic in topics:
            topic_id = str(topic["_id"])
            
            # Verificar si ya existe un tema virtual para este estudiante y tema
            existing = get_db().virtual_topics.find_one({
                "topic_id": ObjectId(topic_id),
                "student_id": ObjectId(student_id)
            })
            
            # Datos para crear/actualizar
            adaptations = {
                "cognitive_profile": cognitive_profile,
                "preferences": preferences,
                # Adaptaciones específicas por tema
                "difficulty_adjustment": calculate_difficulty_adjustment(topic, cognitive_profile)
            }
            
            if existing:
                # Actualizar tema existente
                get_db().virtual_topics.update_one(
                    {"_id": existing["_id"]},
                    {"$set": {
                        "adaptations": adaptations,
                        "updated_at": datetime.now()
                    }}
                )
                
                virtual_topic_id = existing["_id"]
            else:
                # Crear nuevo tema virtual
                result = get_db().virtual_topics.insert_one({
                    "topic_id": ObjectId(topic_id),
                    "student_id": ObjectId(student_id),
                    "virtual_module_id": ObjectId(virtual_module_id),
                    "name": topic.get("name"),
                    "adaptations": adaptations,
                    "status": "active",
                    "created_at": datetime.now(),
                    "updated_at": datetime.now(),
                    "progress": 0.0,
                    "completion_status": "not_started"
                })
                
                virtual_topic_id = result.inserted_id
                
            # Generar contenido personalizado para el tema
            generate_personalized_content(topic_id, str(virtual_topic_id), cognitive_profile)
            
        return True
    except Exception as e:
        logging.error(f"Error al generar temas virtuales: {str(e)}")
        return False

def calculate_difficulty_adjustment(topic: dict, cognitive_profile: dict) -> dict:
    """
    Calcula ajustes de dificultad según el perfil cognitivo y el tema.
    """
    base_difficulty = topic.get("difficulty", "medium")
    adjustment = 0
    
    # Ajustar según fortalezas/debilidades cognitivas
    if cognitive_profile.get("learning_difficulties", False):
        adjustment -= 1  # Reducir dificultad
    
    if cognitive_profile.get("high_achievement", False):
        adjustment += 1  # Aumentar dificultad
        
    # Mapear ajuste a nivel de dificultad
    difficulty_levels = {"easy": -1, "medium": 0, "hard": 1}
    base_level = difficulty_levels.get(base_difficulty, 0)
    
    # Calcular nuevo nivel
    new_level = max(-1, min(1, base_level + adjustment))
    
    # Convertir nivel a texto
    difficulty_mapping = {-1: "easy", 0: "medium", 1: "hard"}
    adjusted_difficulty = difficulty_mapping.get(new_level)
    
    return {
        "original_difficulty": base_difficulty,
        "adjusted_difficulty": adjusted_difficulty,
        "adjustment_factor": adjustment
    }

def generate_personalized_content(topic_id: str, virtual_topic_id: str, cognitive_profile: dict):
    """
    Genera contenido personalizado para un tema virtual.
    """
    try:
        # Obtener tema original
        topic = get_db().topics.find_one({"_id": ObjectId(topic_id)})
        if not topic:
            return False
            
        # Obtener recomendaciones de tipo de contenido según perfil
        content_types = []
        
        # Determinar tipos de contenido según perfil
        if cognitive_profile.get("visual_strength", 0) > 0.6:
            content_types.extend([ContentTypes.DIAGRAM, ContentTypes.INFOGRAPHIC, ContentTypes.MINDMAP])
            
        if cognitive_profile.get("auditory_strength", 0) > 0.6:
            content_types.extend([ContentTypes.AUDIO, ContentTypes.NARRATED_PRESENTATION])
            
        if cognitive_profile.get("read_write_strength", 0) > 0.6:
            content_types.extend([ContentTypes.TEXT, ContentTypes.SUMMARY, ContentTypes.FEYNMAN])
            
        if cognitive_profile.get("kinesthetic_strength", 0) > 0.6:
            content_types.extend([ContentTypes.SIMULATION, ContentTypes.GAME, ContentTypes.INTERACTIVE_EXERCISE])
            
        # Adaptaciones específicas
        if cognitive_profile.get("adhd", False):
            content_types.extend([ContentTypes.INTERACTIVE_EXERCISE, ContentTypes.GAME, ContentTypes.MINDMAP])
            
        if cognitive_profile.get("dyslexia", False):
            content_types.extend([ContentTypes.AUDIO, ContentTypes.DIAGRAM, ContentTypes.MINDMAP])
            
        # Seleccionar tipos de contenido (eliminar duplicados)
        content_types = list(set(content_types))
        
        # Si no hay suficientes tipos, añadir los básicos
        if len(content_types) < 3:
            content_types.extend([ContentTypes.TEXT, ContentTypes.DIAGRAM, ContentTypes.SUMMARY])
            content_types = list(set(content_types))
            
        # Obtener contenido existente para este tema
        existing_contents = list(get_db().topic_contents.find({
            "topic_id": ObjectId(topic_id),
            "status": {"$in": ["active", "published"]}
        }))
        
        # Usar contenido existente o generar nuevo
        for content_type in content_types[:3]:  # Limitamos a 3 tipos principales
            # Buscar si ya existe este tipo de contenido
            matching_content = next((c for c in existing_contents if c.get("content_type") == content_type), None)
            
            if matching_content:
                # Vincular contenido existente al tema virtual
                get_db().virtual_topic_contents.insert_one({
                    "virtual_topic_id": ObjectId(virtual_topic_id),
                    "content_id": matching_content["_id"],
                    "created_at": datetime.now(),
                    "access_count": 0,
                    "last_accessed": None
                })
            else:
                # Crear nuevo contenido para este tipo
                # Esto sería más sofisticado en producción, posiblemente usando IA
                new_content = {
                    "topic_id": ObjectId(topic_id),
                    "content_type": content_type,
                    "content": f"Contenido personalizado generado para {topic.get('name')} usando formato {content_type}",
                    "learning_methodologies": [],
                    "status": "active",
                    "created_at": datetime.now(),
                    "updated_at": datetime.now(),
                    "ai_credits": True
                }
                
                # Insertar nuevo contenido
                content_result = get_db().topic_contents.insert_one(new_content)
                
                # Vincular al tema virtual
                get_db().virtual_topic_contents.insert_one({
                    "virtual_topic_id": ObjectId(virtual_topic_id),
                    "content_id": content_result.inserted_id,
                    "created_at": datetime.now(),
                    "access_count": 0,
                    "last_accessed": None
                })
        
        return True
    except Exception as e:
        logging.error(f"Error al generar contenido personalizado: {str(e)}")
        return False

@virtual_bp.route('/module/<module_id>/progress', methods=['PUT'])
@APIRoute.standard(auth_required_flag=True, required_fields=['progress', 'activity_data'])
def update_module_progress(module_id):
    """Actualiza el progreso de un estudiante en un módulo virtual"""
    try:
        data = request.get_json()
        progress = data.get('progress')  # Porcentaje de progreso (0-100)
        completion_status = data.get('completion_status', None)  # Estado opcional
        activity_data = data.get('activity_data', {})  # Datos de actividad
        
        # Validar datos
        if not isinstance(progress, (int, float)) or progress < 0 or progress > 100:
            return APIRoute.error(
                ErrorCodes.BAD_REQUEST,
                "El progreso debe ser un número entre 0 y 100",
                status_code=400
            )
            
        # Verificar que el módulo virtual existe
        virtual_module = get_db().virtual_modules.find_one({"_id": ObjectId(module_id)})
        if not virtual_module:
            return APIRoute.error(
                ErrorCodes.NOT_FOUND,
                "Módulo virtual no encontrado",
                status_code=404
            )
            
        # Verificar que el usuario es el propietario o un profesor
        student_id = virtual_module.get("student_id")
        if str(student_id) != str(request.user_id) and "TEACHER" not in request.user_roles:
            return APIRoute.error(
                ErrorCodes.UNAUTHORIZED,
                "No tienes permiso para actualizar el progreso de este módulo",
                status_code=403
            )
            
        # Obtener estado actual para comparar
        current_progress = virtual_module.get("progress", 0)
        current_status = virtual_module.get("completion_status", "not_started")
        
        # Determinar el nuevo estado de completado si no se especificó
        if not completion_status:
            if progress >= 100:
                completion_status = "completed"
            elif progress > 0:
                completion_status = "in_progress"
            else:
                completion_status = "not_started"
                
        # Preparar datos para actualizar
        update_data = {
            "progress": progress,
            "completion_status": completion_status,
            "updated_at": datetime.now()
        }
        
        # Añadir registro de actividad
        activity_entry = {
            "timestamp": datetime.now(),
            "progress_change": progress - current_progress,
            "status_change": current_status != completion_status,
            "activity_data": activity_data,
            "user_id": request.user_id
        }
        
        # Actualizar módulo y añadir a historial de actividad
        get_db().virtual_modules.update_one(
            {"_id": ObjectId(module_id)},
            {
                "$set": update_data,
                "$push": {"activity_history": activity_entry}
            }
        )
        
        # Verificar si hay temas en este módulo para actualizar
        virtual_topics = list(get_db().virtual_topics.find(
            {"virtual_module_id": ObjectId(module_id)}
        ))
        
        # Si hay datos específicos de temas, actualizar cada tema
        if "topics_progress" in activity_data and virtual_topics:
            for topic_data in activity_data.get("topics_progress", []):
                topic_id = topic_data.get("id")
                topic_progress = topic_data.get("progress")
                
                if topic_id and isinstance(topic_progress, (int, float)):
                    try:
                        # Determinar estado de completado del tema
                        topic_status = "completed" if topic_progress >= 100 else "in_progress" if topic_progress > 0 else "not_started"
                        
                        # Actualizar tema virtual
                        get_db().virtual_topics.update_one(
                            {"_id": ObjectId(topic_id), "virtual_module_id": ObjectId(module_id)},
                            {
                                "$set": {
                                    "progress": topic_progress,
                                    "completion_status": topic_status,
                                    "updated_at": datetime.now()
                                }
                            }
                        )
                    except Exception as topic_error:
                        logging.warning(f"Error al actualizar tema {topic_id}: {str(topic_error)}")
        
        # Calcular métricas adicionales
        metrics = {
            "total_study_time": activity_data.get("study_time", 0),
            "resources_viewed": activity_data.get("resources_viewed", 0),
            "activities_completed": activity_data.get("activities_completed", 0)
        }
        
        return APIRoute.success(
            data={
                "module_id": module_id,
                "new_progress": progress,
                "new_status": completion_status,
                "metrics": metrics
            },
            message="Progreso actualizado exitosamente"
        )
    except Exception as e:
        logging.error(f"Error al actualizar progreso del módulo: {str(e)}")
        return APIRoute.error(
            ErrorCodes.SERVER_ERROR,
            str(e),
            status_code=500
        ) 