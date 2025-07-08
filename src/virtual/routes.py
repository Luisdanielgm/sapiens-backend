from flask import request
from src.shared.standardization import APIBlueprint, APIRoute, ErrorCodes
from src.shared.constants import ROLES
from src.shared.database import get_db
from bson import ObjectId
from datetime import datetime
import logging

from .services import VirtualModuleService, VirtualTopicService, ServerlessQueueService, FastVirtualModuleGenerator, ContentChangeDetector
from src.content.models import ContentTypes, LearningMethodologyTypes
from src.study_plans.services import TopicService

virtual_bp = APIBlueprint('virtual', __name__)
# quiz_bp eliminado - ahora los quizzes se manejan como TopicContent

virtual_module_service = VirtualModuleService()
virtual_topic_service = VirtualTopicService()
topic_service = TopicService()
# quiz_service eliminado - funcionalidad migrada a ContentService
queue_service = ServerlessQueueService()
fast_generator = FastVirtualModuleGenerator()
change_detector = ContentChangeDetector()

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

@virtual_bp.route('/topic/<virtual_topic_id>/contents', methods=['GET'])
@APIRoute.standard(auth_required_flag=True)
def get_virtual_topic_contents(virtual_topic_id):
    """Obtiene todos los contenidos de un tema virtual específico."""
    contents = virtual_topic_service.get_topic_contents(virtual_topic_id)
    return APIRoute.success(data={"contents": contents})

# Rutas de Quiz eliminadas - ahora se manejan como TopicContent
# Los quizzes se crean con POST /study_plan/topic/content (content_type="quiz")
# Los resultados se envían con POST /virtual/content-result

@virtual_bp.route('/content-result', methods=['POST'])
@APIRoute.standard(
    auth_required_flag=True,
    roles=[ROLES["STUDENT"]],
    required_fields=['virtual_content_id', 'student_id', 'session_data']
)
def submit_content_result():
    """
    Endpoint unificado para enviar resultados de cualquier tipo de contenido interactivo.
    Reemplaza los endpoints específicos de quiz, game, etc.
    """
    try:
        data = request.get_json()
        virtual_content_id = data.get('virtual_content_id')
        student_id = data.get('student_id')
        session_data = data.get('session_data')
        learning_metrics = data.get('learning_metrics', {})
        feedback = data.get('feedback', '')
        session_type = data.get('session_type', 'completion')
        
        # Verificar que el contenido virtual existe
        virtual_content = get_db().virtual_topic_contents.find_one({
            "_id": ObjectId(virtual_content_id)
        })
        
        if not virtual_content:
            return APIRoute.error(
                ErrorCodes.NOT_FOUND,
                "Contenido virtual no encontrado",
                status_code=404
            )
        
        # Verificar que el estudiante coincide
        if str(virtual_content.get("student_id")) != student_id:
            return APIRoute.error(
                ErrorCodes.PERMISSION_DENIED,
                "No tienes permiso para enviar resultados de este contenido",
                status_code=403
            )
        
        # Crear el resultado usando el servicio unificado
        from src.content.services import ContentResultService
        content_result_service = ContentResultService()
        
        result_data = {
            "virtual_content_id": virtual_content_id,
            "student_id": student_id,
            "session_data": session_data,
            "learning_metrics": learning_metrics,
            "feedback": feedback,
            "session_type": session_type
        }
        
        success, result_id = content_result_service.record_result(result_data)
        
        if success:
            # Actualizar tracking del contenido virtual
            completion_percentage = session_data.get('completion_percentage', 100)
            
            update_data = {
                "interaction_tracking.last_accessed": datetime.now(),
                "interaction_tracking.completion_percentage": completion_percentage,
                "updated_at": datetime.now()
            }
            
            # Si completó al 100%, marcar como completado
            if completion_percentage >= 100:
                update_data["interaction_tracking.completion_status"] = "completed"
            elif completion_percentage > 0:
                update_data["interaction_tracking.completion_status"] = "in_progress"
            
            get_db().virtual_topic_contents.update_one(
                {"_id": ObjectId(virtual_content_id)},
                {"$set": update_data, "$inc": {"interaction_tracking.access_count": 1}}
            )
            
            return APIRoute.success(
                data={
                    "result_id": result_id,
                    "completion_percentage": completion_percentage,
                    "status": "submitted"
                },
                message="Resultado registrado exitosamente",
                status_code=201
            )
        else:
            return APIRoute.error(
                ErrorCodes.OPERATION_FAILED,
                result_id,  # El mensaje de error viene en result_id
                status_code=500
            )
        
    except Exception as e:
        logging.error(f"Error al registrar resultado de contenido: {str(e)}")
        return APIRoute.error(
            ErrorCodes.SERVER_ERROR,
            str(e),
            status_code=500
        )


@virtual_bp.route('/contents/<virtual_content_id>/auto-complete', methods=['POST'])
@APIRoute.standard(auth_required_flag=True, roles=[ROLES['STUDENT']])
def auto_complete_content(virtual_content_id):
    """Marca un contenido estático como completado y registra ContentResult."""
    try:
        student_id = request.get_json(silent=True).get('student_id') if request.get_json(silent=True) else request.user_id

        virtual_content = get_db().virtual_topic_contents.find_one({"_id": ObjectId(virtual_content_id)})
        if not virtual_content:
            return APIRoute.error(ErrorCodes.NOT_FOUND, "Contenido virtual no encontrado", status_code=404)

        if str(virtual_content.get("student_id")) != student_id:
            return APIRoute.error(ErrorCodes.PERMISSION_DENIED, "No tienes permiso para modificar este contenido", status_code=403)

        from src.content.services import ContentResultService
        content_result_service = ContentResultService()

        content_result_service.collection.update_one(
            {"student_id": ObjectId(student_id), "virtual_content_id": ObjectId(virtual_content_id)},
            {"$set": {
                "student_id": ObjectId(student_id),
                "virtual_content_id": ObjectId(virtual_content_id),
                "score": 100,
                "session_type": "auto_complete",
                "session_data": {"auto_completed": True},
                "learning_metrics": {},
                "feedback": None,
                "created_at": datetime.now()
            }},
            upsert=True
        )

        get_db().virtual_topic_contents.update_one(
            {"_id": ObjectId(virtual_content_id)},
            {"$set": {
                "interaction_tracking.completion_status": "completed",
                "interaction_tracking.completion_percentage": 100,
                "interaction_tracking.last_accessed": datetime.now(),
                "updated_at": datetime.now()
            }, "$inc": {"interaction_tracking.access_count": 1}}
        )

        return APIRoute.success(data={"status": "completed"}, message="Contenido completado")

    except Exception as e:
        logging.error(f"Error auto-completando contenido: {str(e)}")
        return APIRoute.error(ErrorCodes.SERVER_ERROR, str(e), status_code=500)

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
        
        # 1. Verificar que el usuario está inscrito en la clase a través de class_members
        member = get_db().class_members.find_one({
            "user_id": ObjectId(student_id),
            "class_id": ObjectId(class_id),
            "status": "active"
        })
        if not member:
            return APIRoute.error(
                ErrorCodes.PERMISSION_DENIED,
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
        study_plan = get_db().study_plans_per_subject.find_one({
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
        # Determinar módulos a generar: si viene `module_id`, filtrar solo ese;
        # en caso contrario, generar para todo el plan de estudios
        module_filter = {"study_plan_id": ObjectId(study_plan_id)}
        if data.get("module_id"):
            module_filter["_id"] = ObjectId(data.get("module_id"))
        modules = list(get_db().modules.find(module_filter))
        
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
                
                # Datos para crear/actualizar (se permite override de nombre vía payload)
                module_data = {
                    "module_id": module_id,
                    "student_id": student_id,
                    "name": data.get("name", module.get("name")),
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
                        "study_plan_id": ObjectId(study_plan_id),
                        "module_id": ObjectId(module_id),
                        "student_id": ObjectId(student_id),
                        "name": module.get("name"),
                        "description": module.get("description", ""),
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
                    
                # Para cada módulo, generar temas virtuales inmediatamente
                virtual_module_id = str(existing["_id"]) if existing else str(result.inserted_id)
                generate_virtual_topics(module_id, student_id, virtual_module_id, cognitive_profile, preferences)
                
            except Exception as e:
                errors.append({
                    "module_id": module_id if 'module_id' in locals() else "unknown",
                    "error": str(e)
                })
        
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
        
        return APIRoute.success(data={
            "learning_methodologies": recommendations["learning_methodologies"],
            "content_types": recommendations["content_types"],
            "resources": recommendations["resources"]
        })
    except Exception as e:
        logging.error(f"Error al obtener recomendaciones personalizadas: {str(e)}")
        return APIRoute.error(
            ErrorCodes.SERVER_ERROR,
            str(e),
            status_code=500
        )

# Nuevo endpoint para listar módulos virtuales de un estudiante y plan de estudios
@virtual_bp.route('/modules', methods=['GET'])
@APIRoute.standard(auth_required_flag=True)
def list_virtual_modules():
    """Lista todos los módulos virtuales creados para un estudiante en un plan de estudios"""
    study_plan_id = request.args.get('study_plan_id')
    student_id = request.args.get('student_id')
    if not study_plan_id or not student_id:
        return APIRoute.error(
            ErrorCodes.BAD_REQUEST,
            "Faltan parámetros 'study_plan_id' o 'student_id'",
            status_code=400
        )
    modules = virtual_module_service.get_student_modules(study_plan_id, student_id)
    return APIRoute.success(data={"modules": modules})

def generate_virtual_topics(module_id: str, student_id: str, virtual_module_id: str, cognitive_profile: dict, preferences: dict):
    """
    Genera temas virtuales para un módulo. Función auxiliar separada para procesamiento asincrónico.
    """
    try:
        # Obtener temas del módulo que estén publicados
        topics = list(get_db().topics.find({
            "module_id": ObjectId(module_id),
            "published": True
        }))
        
        if not topics:
            logging.warning(f"No se encontraron temas publicados para el módulo {module_id}. El módulo virtual se generará sin temas.")
            return True
        
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
            "status": {"$in": ["draft", "active", "published"]}
        }))
        
        # Usar contenido existente o generar nuevo
        for content_type in content_types[:5]:  # Limitamos a 5 tipos principales
            # Buscar si ya existe este tipo de contenido
            matching_content = next((c for c in existing_contents if c.get("content_type") == content_type), None)
            
            # Manejo especial para diagramas: solo vincular si existe y no crear nuevos
            if content_type == ContentTypes.DIAGRAM:
                if matching_content:
                    # Vincular contenido existente al tema virtual
                    get_db().virtual_topic_contents.insert_one({
                        "virtual_topic_id": ObjectId(virtual_topic_id),
                        "content_id": matching_content["_id"],
                        "created_at": datetime.now(),
                        "access_count": 0,
                        "last_accessed": None
                    })
                continue

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
                ErrorCodes.PERMISSION_DENIED,
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

# ========== NUEVOS ENDPOINTS PARA GENERACIÓN PROGRESIVA ==========

@virtual_bp.route('/progressive-generation', methods=['POST'])
@APIRoute.standard(auth_required_flag=True, required_fields=['student_id', 'plan_id'])
def initialize_progressive_generation():
    """
    Inicializa la generación progresiva encolando los primeros módulos.
    Optimizado para límites serverless de 1 minuto.
    """
    try:
        data = request.get_json()
        student_id = data.get('student_id')
        plan_id = data.get('plan_id')
        class_id = data.get('class_id')  # Opcional para validaciones adicionales
        
        # 1. Validar que el estudiante existe
        student = get_db().users.find_one({"_id": ObjectId(student_id)})
        if not student:
            return APIRoute.error(
                ErrorCodes.NOT_FOUND,
                "Estudiante no encontrado",
                status_code=404
            )
        
        # 2. Validar que el plan de estudios existe
        study_plan = get_db().study_plans_per_subject.find_one({"_id": ObjectId(plan_id)})
        if not study_plan:
            return APIRoute.error(
                ErrorCodes.NOT_FOUND,
                "Plan de estudios no encontrado",
                status_code=404
            )
        
        # 3. Obtener módulos del plan que tengan al menos un tema publicado
        all_modules = list(get_db().modules.find({"study_plan_id": ObjectId(plan_id)}))
        enabled_modules = []
        for mod in all_modules:
            published_count = get_db().topics.count_documents({
                "module_id": mod["_id"],
                "published": True
            })
            if published_count > 0:
                mod["published_count"] = published_count
                enabled_modules.append(mod)

        if not enabled_modules:
            return APIRoute.error(
                ErrorCodes.BAD_REQUEST,
                "No hay módulos con temas publicados en este plan",
                status_code=400
            )
        
        # 4. Filtrar módulos que no han sido generados
        already_generated = list(get_db().virtual_modules.find({
            "student_id": ObjectId(student_id),
            "module_id": {"$in": [m["_id"] for m in enabled_modules]}
        }))
        
        generated_module_ids = [vm["module_id"] for vm in already_generated]
        pending_modules = [m for m in enabled_modules if m["_id"] not in generated_module_ids]
        
        # 5. Encolar los primeros 2-3 módulos para generación
        batch_size = min(3, len(pending_modules))
        enqueued_tasks = []
        errors = []
        
        for i, module in enumerate(pending_modules[:batch_size]):
            module_id = str(module["_id"])
            priority = i + 1  # Prioridad ascendente
            
            success, task_id = queue_service.enqueue_generation_task(
                student_id=student_id,
                module_id=module_id,
                task_type="generate",
                priority=priority,
                payload={
                    "plan_id": plan_id,
                    "class_id": class_id,
                    "batch_initialization": True
                }
            )
            
            if success:
                enqueued_tasks.append({
                    "task_id": task_id,
                    "module_id": module_id,
                    "module_name": module.get("name", ""),
                    "priority": priority
                })
            else:
                errors.append({
                    "module_id": module_id,
                    "error": task_id
                })
        
        # 6. Procesar inmediatamente la primera tarea si hay tiempo
        immediate_result = None
        if enqueued_tasks:
            first_task = enqueued_tasks[0]
            success, result = fast_generator.generate_single_module(
                student_id=student_id,
                module_id=first_task["module_id"],
                timeout=35  # Dejar margen para el resto de la respuesta
            )
            
            if success:
                # Marcar tarea como completada
                queue_service.complete_task(
                    first_task["task_id"],
                    {"virtual_module_id": result, "generated_immediately": True}
                )
                
                immediate_result = {
                    "virtual_module_id": result,
                    "module_id": first_task["module_id"]
                }
        
        # 7. Obtener estado actual de la cola
        queue_status = queue_service.get_student_queue_status(student_id)
        
        return APIRoute.success(
            data={
                "enqueued_tasks": enqueued_tasks,
                "immediate_result": immediate_result,
                "errors": errors,
                "queue_status": queue_status,
                "total_enabled_modules": len(enabled_modules),
                "total_pending_modules": len(pending_modules),
                "batch_size": batch_size
            },
            message="Generación progresiva inicializada exitosamente",
            status_code=201
        )
        
    except Exception as e:
        logging.error(f"Error en inicialización progresiva: {str(e)}")
        return APIRoute.error(
            ErrorCodes.SERVER_ERROR,
            str(e),
            status_code=500
        )

@virtual_bp.route('/trigger-next-generation', methods=['POST'])
@APIRoute.standard(auth_required_flag=True, required_fields=['current_module_id', 'student_id', 'progress'])
def trigger_next_generation():
    """
    Disparado cuando el progreso de un módulo supera el 80%.
    Encola el siguiente módulo disponible para generación.
    """
    try:
        data = request.get_json()
        current_module_id = data.get('current_module_id')
        student_id = data.get('student_id')
        progress = data.get('progress', 0)
        
        # 1. Validar progreso mínimo
        if progress < 80:
            return APIRoute.error(
                ErrorCodes.BAD_REQUEST,
                "El progreso debe ser mayor al 80% para activar siguiente generación",
                status_code=400
            )
        
        # 2. Obtener información del módulo actual
        current_module = get_db().modules.find_one({"_id": ObjectId(current_module_id)})
        if not current_module:
            return APIRoute.error(
                ErrorCodes.NOT_FOUND,
                "Módulo actual no encontrado",
                status_code=404
            )
        
        plan_id = current_module["study_plan_id"]
        
        # 3. Buscar siguiente módulo con temas publicados no generado
        all_plan_modules = list(get_db().modules.find({"study_plan_id": plan_id}).sort("created_at", 1))
        all_enabled_modules = []
        for m in all_plan_modules:
            if get_db().topics.count_documents({"module_id": m["_id"], "published": True}) > 0:
                all_enabled_modules.append(m)
        
        # Obtener módulos ya generados
        generated_modules = list(get_db().virtual_modules.find({
            "student_id": ObjectId(student_id),
            "module_id": {"$in": [m["_id"] for m in all_enabled_modules]}
        }))
        
        generated_module_ids = [vm["module_id"] for vm in generated_modules]
        
        # Encontrar el siguiente módulo no generado
        next_module = None
        for module in all_enabled_modules:
            if module["_id"] not in generated_module_ids:
                next_module = module
                break
        
        if not next_module:
            return APIRoute.success(
                data={
                    "message": "No hay más módulos disponibles para generar",
                    "has_next": False
                },
                message="Generación progresiva completada"
            )
        
        # 4. Encolar el siguiente módulo
        next_module_id = str(next_module["_id"])
        success, task_id = queue_service.enqueue_generation_task(
            student_id=student_id,
            module_id=next_module_id,
            task_type="generate",
            priority=2,  # Prioridad alta para módulos activados por progreso
            payload={
                "triggered_by_progress": True,
                "trigger_module_id": current_module_id,
                "trigger_progress": progress
            }
        )
        
        if not success:
            return APIRoute.error(
                ErrorCodes.OPERATION_FAILED,
                f"Error al encolar siguiente módulo: {task_id}",
                status_code=500
            )
        
        # 5. Obtener estado actualizado de la cola
        queue_status = queue_service.get_student_queue_status(student_id)
        
        return APIRoute.success(
            data={
                "next_module": {
                    "id": next_module_id,
                    "name": next_module.get("name", ""),
                    "task_id": task_id
                },
                "queue_status": queue_status,
                "has_next": True
            },
            message="Siguiente módulo encolado para generación"
        )
        
    except Exception as e:
        logging.error(f"Error al activar siguiente generación: {str(e)}")
        return APIRoute.error(
            ErrorCodes.SERVER_ERROR,
            str(e),
            status_code=500
        )

@virtual_bp.route('/process-queue', methods=['POST'])
@APIRoute.standard(auth_required_flag=True, roles=[ROLES.get("TEACHER", "TEACHER"), "SYSTEM"])
def process_generation_queue():
    """
    Procesa tareas pendientes de la cola de generación.
    Diseñado para ser llamado por webhooks externos.
    Procesa máximo 1-2 tareas por ejecución para respetar límite de tiempo.
    """
    try:
        # 1. Obtener tareas a procesar
        tasks_to_process = queue_service.get_next_tasks(limit=2, max_duration=45)
        
        if not tasks_to_process:
            return APIRoute.success(
                data={
                    "processed_tasks": 0,
                    "message": "No hay tareas pendientes"
                },
                message="Cola procesada"
            )
        
        processed_tasks = []
        failed_tasks = []
        
        # 2. Procesar cada tarea
        for task in tasks_to_process:
            task_id = task["_id"]
            student_id = task["student_id"]
            module_id = task["module_id"]
            task_type = task["task_type"]
            
            # Marcar como procesando
            if not queue_service.mark_task_processing(task_id):
                continue
            
            try:
                # Procesar según tipo de tarea
                if task_type == "generate":
                    success, result = fast_generator.generate_single_module(
                        student_id=student_id,
                        module_id=module_id,
                        timeout=40
                    )
                    
                    if success:
                        queue_service.complete_task(
                            task_id, 
                            {"virtual_module_id": result}
                        )
                        processed_tasks.append({
                            "task_id": task_id,
                            "module_id": module_id,
                            "virtual_module_id": result,
                            "type": task_type
                        })
                    else:
                        queue_service.fail_task(task_id, result)
                        failed_tasks.append({
                            "task_id": task_id,
                            "module_id": module_id,
                            "error": result
                        })
                
                elif task_type == "update":
                    # Lógica de actualización incremental
                    virtual_module_id = task.get("payload", {}).get("virtual_module_id")
                    if not virtual_module_id:
                        raise ValueError("La tarea de actualización no tiene virtual_module_id en el payload")

                    success, result = fast_generator.synchronize_module_content(virtual_module_id)
                    
                    if success:
                        queue_service.complete_task(
                            task_id,
                            {"update_report": result}
                        )
                        processed_tasks.append({
                            "task_id": task_id,
                            "virtual_module_id": virtual_module_id,
                            "type": task_type,
                            "report": result
                        })
                    else:
                        queue_service.fail_task(task_id, str(result))
                        failed_tasks.append({
                            "task_id": task_id,
                            "virtual_module_id": virtual_module_id,
                            "error": str(result)
                        })
                
            except Exception as task_error:
                logging.error(f"Error procesando tarea {task_id}: {str(task_error)}")
                queue_service.fail_task(task_id, str(task_error))
                failed_tasks.append({
                    "task_id": task_id,
                    "module_id": module_id,
                    "error": str(task_error)
                })
        
        # 3. Limpiar tareas antiguas ocasionalmente
        import random
        if random.randint(1, 10) == 1:  # 10% de probabilidad
            cleaned = queue_service.cleanup_old_tasks(days_old=3)
            logging.info(f"Limpiadas {cleaned} tareas antiguas")
        
        return APIRoute.success(
            data={
                "processed_tasks": len(processed_tasks),
                "failed_tasks": len(failed_tasks),
                "task_details": {
                    "processed": processed_tasks,
                    "failed": failed_tasks
                }
            },
            message=f"Procesadas {len(processed_tasks)} tareas exitosamente"
        )
        
    except Exception as e:
        logging.error(f"Error procesando cola: {str(e)}")
        return APIRoute.error(
            ErrorCodes.SERVER_ERROR,
            str(e),
            status_code=500
        )

@virtual_bp.route('/generation-status/<student_id>', methods=['GET'])
@APIRoute.standard(auth_required_flag=True)
def get_generation_status(student_id):
    """
    Obtiene el estado actual de generación para un estudiante.
    """
    try:
        # 1. Validar estudiante
        student = get_db().users.find_one({"_id": ObjectId(student_id)})
        if not student:
            return APIRoute.error(
                ErrorCodes.NOT_FOUND,
                "Estudiante no encontrado",
                status_code=404
            )
        
        # 2. Obtener estado de la cola
        queue_status = queue_service.get_student_queue_status(student_id)
        
        # 3. Obtener módulos virtuales generados
        generated_modules = list(get_db().virtual_modules.find({
            "student_id": ObjectId(student_id)
        }))
        
        # Procesar información de módulos generados
        modules_info = []
        for vm in generated_modules:
            module_info = {
                "virtual_module_id": str(vm["_id"]),
                "module_id": str(vm.get("module_id", "")),
                "name": vm.get("name", ""),
                "generation_status": vm.get("generation_status", "unknown"),
                "generation_progress": vm.get("generation_progress", 0),
                "created_at": vm.get("created_at")
            }
            
            # Obtener información del módulo original
            if vm.get("module_id"):
                original = get_db().modules.find_one({"_id": vm["module_id"]})
                if original:
                    module_info["original_name"] = original.get("name", "")
                    module_info["study_plan_id"] = str(original.get("study_plan_id", ""))
            
            modules_info.append(module_info)
        
        # 4. Obtener tareas activas
        active_tasks = list(get_db().virtual_generation_tasks.find({
            "student_id": ObjectId(student_id),
            "status": {"$in": ["pending", "processing"]}
        }))
        
        # Procesar información de tareas activas
        tasks_info = []
        for task in active_tasks:
            task_info = {
                "task_id": str(task["_id"]),
                "module_id": str(task["module_id"]),
                "task_type": task.get("task_type", ""),
                "status": task.get("status", ""),
                "priority": task.get("priority", 5),
                "created_at": task.get("created_at"),
                "attempts": task.get("attempts", 0)
            }
            
            # Obtener nombre del módulo
            module = get_db().modules.find_one({"_id": task["module_id"]})
            if module:
                task_info["module_name"] = module.get("name", "")
            
            tasks_info.append(task_info)
        
        return APIRoute.success(
            data={
                "queue_status": queue_status,
                "generated_modules": modules_info,
                "active_tasks": tasks_info,
                "summary": {
                    "total_generated": len(modules_info),
                    "total_pending": queue_status["pending"],
                    "total_processing": queue_status["processing"],
                    "generation_active": queue_status["pending"] > 0 or queue_status["processing"] > 0
                }
            },
            message="Estado de generación obtenido exitosamente"
        )
        
    except Exception as e:
        logging.error(f"Error obteniendo estado de generación: {str(e)}")
        return APIRoute.error(
            ErrorCodes.SERVER_ERROR,
            str(e),
            status_code=500
        )

@virtual_bp.route('/modules/<virtual_module_id>/incremental-update', methods=['PUT'])
@APIRoute.standard(auth_required_flag=True, roles=[ROLES.get("TEACHER", "TEACHER")])
def incremental_update_virtual_module(virtual_module_id):
    """
    Aplica actualización incremental a un módulo virtual.
    Placeholder para lógica de actualización basada en cambios detectados.
    """
    try:
        data = request.get_json()
        update_type = data.get('update_type', 'content')  # content, structure, settings
        changes = data.get('changes', {})
        
        # 1. Verificar que el módulo virtual existe
        virtual_module = get_db().virtual_modules.find_one({
            "_id": ObjectId(virtual_module_id)
        })
        
        if not virtual_module:
            return APIRoute.error(
                ErrorCodes.NOT_FOUND,
                "Módulo virtual no encontrado",
                status_code=404
            )
        
        # 2. Crear registro de actualización
        update_record = {
            "type": update_type,
            "status": "applied",
            "changes": changes,
            "created_at": datetime.now(),
            "updated_at": datetime.now()
        }
        
        # 3. Aplicar actualización al módulo virtual
        result = get_db().virtual_modules.update_one(
            {"_id": ObjectId(virtual_module_id)},
            {
                "$push": {"updates": update_record},
                "$set": {"updated_at": datetime.now()}
            }
        )
        
        if result.modified_count == 0:
            return APIRoute.error(
                ErrorCodes.OPERATION_FAILED,
                "No se pudo aplicar la actualización",
                status_code=500
            )
        
        return APIRoute.success(
            data={
                "virtual_module_id": virtual_module_id,
                "update_type": update_type,
                "update_record": update_record
            },
            message="Actualización incremental aplicada exitosamente"
        )
        
    except Exception as e:
        logging.error(f"Error en actualización incremental: {str(e)}")
        return APIRoute.error(
            ErrorCodes.SERVER_ERROR,
            str(e),
            status_code=500
        )

@virtual_bp.route('/modules/<module_id>/detect-changes', methods=['POST'])
@APIRoute.standard(auth_required_flag=True, roles=[ROLES.get("TEACHER", "TEACHER"), "SYSTEM"])
def detect_module_changes(module_id):
    """
    Detecta cambios en un módulo y programa actualizaciones incrementales.
    Diseñado para ser llamado manualmente o por webhooks.
    """
    try:
        # 1. Detectar cambios en el módulo
        change_info = change_detector.detect_changes(module_id)
        
        if change_info.get("error"):
            return APIRoute.error(
                ErrorCodes.SERVER_ERROR,
                f"Error detectando cambios: {change_info['error']}",
                status_code=500
            )
        
        # 2. Si hay cambios, programar actualizaciones incrementales
        if change_info.get("has_changes"):
            task_ids = change_detector.schedule_incremental_updates(module_id, change_info)
            
            return APIRoute.success(
                data={
                    "changes_detected": True,
                    "change_info": change_info,
                    "scheduled_updates": len(task_ids),
                    "task_ids": task_ids
                },
                message=f"Cambios detectados. {len(task_ids)} actualizaciones programadas."
            )
        else:
            return APIRoute.success(
                data={
                    "changes_detected": False,
                    "change_info": change_info
                },
                message="No se detectaron cambios en el módulo."
            )
        
    except Exception as e:
        logging.error(f"Error en detección de cambios: {str(e)}")
        return APIRoute.error(
            ErrorCodes.SERVER_ERROR,
            str(e),
            status_code=500
        )


@virtual_bp.route('/content-results/student/<student_id>', methods=['GET'])
@APIRoute.standard(auth_required_flag=True)
def get_student_content_results(student_id):
    """
    Obtiene todos los resultados de contenido de un estudiante.
    Reemplaza los endpoints específicos de quiz/game results.
    """
    try:
        from src.content.services import ContentResultService
        content_result_service = ContentResultService()
        
        # Obtener parámetros opcionales
        content_type = request.args.get('content_type')  # Filtrar por tipo de contenido
        module_id = request.args.get('module_id')  # Filtrar por módulo
        
        # Obtener resultados del estudiante
        results = content_result_service.get_student_results(student_id, content_type)
        
        # Si se especifica un módulo, filtrar por módulo
        if module_id and results:
            # Obtener contenidos virtuales del módulo específico
            virtual_module = get_db().virtual_modules.find_one({
                "module_id": ObjectId(module_id),
                "student_id": ObjectId(student_id)
            })
            
            if virtual_module:
                # Obtener contenidos virtuales del módulo
                virtual_topics = list(get_db().virtual_topics.find({
                    "virtual_module_id": virtual_module["_id"]
                }))
                
                virtual_topic_ids = [vt["_id"] for vt in virtual_topics]
                
                # Obtener contenidos de esos temas
                virtual_contents = list(get_db().virtual_topic_contents.find({
                    "virtual_topic_id": {"$in": virtual_topic_ids}
                }))
                
                virtual_content_ids = [str(vc["_id"]) for vc in virtual_contents]
                
                # Filtrar resultados por esos contenidos
                results = [r for r in results if r.get("virtual_content_id") in virtual_content_ids]
        
        # Enriquecer resultados con información adicional
        enriched_results = []
        for result in results:
            # Obtener información del contenido virtual
            virtual_content = get_db().virtual_topic_contents.find_one({
                "_id": ObjectId(result["virtual_content_id"])
            })
            
            if virtual_content:
                # Obtener información del contenido original
                content = get_db().topic_contents.find_one({
                    "_id": virtual_content.get("content_id")
                })
                
                # Obtener información del tema virtual
                virtual_topic = get_db().virtual_topics.find_one({
                    "_id": virtual_content.get("virtual_topic_id")
                })
                
                enriched_result = {
                    **result,
                    "content_info": {
                        "content_type": content.get("content_type") if content else "unknown",
                        "title": content.get("title") if content else "Sin título"
                    },
                    "topic_info": {
                        "topic_name": virtual_topic.get("name") if virtual_topic else "Sin nombre",
                        "virtual_topic_id": str(virtual_topic["_id"]) if virtual_topic else None
                    }
                }
                enriched_results.append(enriched_result)
        
        return APIRoute.success(
            data={
                "results": enriched_results,
                "total_count": len(enriched_results),
                "filters_applied": {
                    "content_type": content_type,
                    "module_id": module_id
                }
            },
            message="Resultados obtenidos exitosamente"
        )
        
    except Exception as e:
        logging.error(f"Error al obtener resultados del estudiante: {str(e)}")
        return APIRoute.error(
            ErrorCodes.SERVER_ERROR,
            str(e),
            status_code=500
        )
