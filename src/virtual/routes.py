from flask import request
from flask_jwt_extended import get_jwt, get_jwt_identity
from src.shared.standardization import APIBlueprint, APIRoute, ErrorCodes
from src.shared.constants import ROLES
from src.shared.database import get_db
from src.shared.decorators import auth_required, role_required, workspace_type_required, workspace_access_required
from src.shared.middleware import apply_workspace_filter, get_current_workspace_info
from bson import ObjectId
from datetime import datetime
import logging

from .services import (
    VirtualModuleService,
    VirtualTopicService,
    ServerlessQueueService,
    FastVirtualModuleGenerator,
    ContentChangeDetector,
    AdaptiveLearningService,
    UIPerformanceMetricsService,
    AdaptiveUIOptimizationService,
)
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
            
            # Calcular progreso del tema automáticamente
            virtual_topic_id = virtual_content.get("virtual_topic_id")
            if virtual_topic_id and completion_percentage >= 100:
                try:
                    # Obtener todos los contenidos del tema
                    topic_contents = list(get_db().virtual_topic_contents.find({
                        "virtual_topic_id": virtual_topic_id
                    }))
                    
                    if topic_contents:
                        # Calcular progreso promedio del tema
                        total_completion = sum(
                            content.get("interaction_tracking", {}).get("completion_percentage", 0)
                            for content in topic_contents
                        )
                        topic_progress = total_completion / len(topic_contents)
                        
                        # Determinar estado del tema
                        topic_status = "completed" if topic_progress >= 100 else "in_progress" if topic_progress > 0 else "not_started"
                        
                        # Actualizar progreso del tema virtual
                        get_db().virtual_topics.update_one(
                            {"_id": virtual_topic_id},
                            {"$set": {
                                "progress": topic_progress,
                                "completion_status": topic_status,
                                "updated_at": datetime.now()
                            }}
                        )
                        
                        # Si el tema se completó al 100%, desbloquear siguiente tema
                        if topic_progress >= 100:
                            virtual_topic = get_db().virtual_topics.find_one({"_id": virtual_topic_id})
                            if virtual_topic:
                                virtual_module_id = virtual_topic.get("virtual_module_id")
                                current_order = virtual_topic.get("order", 0)
                                
                                # Desbloquear siguiente tema
                                get_db().virtual_topics.update_one(
                                    {
                                        "virtual_module_id": virtual_module_id,
                                        "order": current_order + 1
                                    },
                                    {"$set": {"locked": False, "updated_at": datetime.now()}}
                                )
                                
                                # Actualizar progreso del módulo
                                virtual_topic_service._update_module_progress_from_topic(virtual_topic)
                                
                                # Trigger para actualización de perfil adaptativo
                                try:
                                    adaptive_service = AdaptiveLearningService()
                                    adaptive_service.update_profile_from_results(student_id)
                                except Exception as adaptive_err:
                                    logging.warning(f"Error actualizando perfil adaptativo: {adaptive_err}")
                                
                                # Verificar si necesitamos generar siguiente módulo (trigger al 80%)
                                updated_module = get_db().virtual_modules.find_one({"_id": virtual_module_id})
                                if updated_module and updated_module.get("progress", 0) >= 80:
                                    try:
                                        # Obtener información del módulo para generar el siguiente
                                        module_id = updated_module.get("module_id")
                                        study_plan_id = updated_module.get("study_plan_id")
                                        
                                        # Buscar siguiente módulo en el plan de estudios
                                        current_module = get_db().modules.find_one({"_id": module_id})
                                        if current_module:
                                            next_module = get_db().modules.find_one({
                                                "study_plan_id": study_plan_id,
                                                "order": current_module.get("order", 0) + 1
                                            })
                                            
                                            if next_module:
                                                # Verificar si el siguiente módulo virtual ya existe
                                                existing_next = get_db().virtual_modules.find_one({
                                                    "module_id": next_module["_id"],
                                                    "student_id": ObjectId(student_id)
                                                })
                                                
                                                if not existing_next:
                                                    # Encolar generación del siguiente módulo
                                                    queue_service.enqueue_task(
                                                        student_id=student_id,
                                                        module_id=str(next_module["_id"]),
                                                        task_type="generate",
                                                        priority=1,
                                                        payload={
                                                            "trigger_reason": "auto_progress_80",
                                                            "source_module_id": str(module_id)
                                                        }
                                                    )
                                    except Exception as next_module_err:
                                        logging.warning(f"Error generando siguiente módulo: {next_module_err}")
                        
                except Exception as progress_err:
                    logging.warning(f"Error calculando progreso del tema: {progress_err}")
            
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


# Rutas para Métricas de UI y Optimización Automática
@virtual_bp.route('/ui-metrics', methods=['POST'])
@APIRoute.standard(
    auth_required_flag=True,
    roles=[ROLES["STUDENT"]],
    required_fields=['session_data']
)
def record_ui_metrics():
    """Registra métricas de rendimiento de UI para un estudiante."""
    try:
        from src.virtual.services import UIPerformanceMetricsService
        
        data = request.get_json()
        student_id = str(request.user_id)
        session_data = data.get('session_data')
        
        # Validar datos de sesión
        if not isinstance(session_data, dict):
            return APIRoute.error(
                ErrorCodes.BAD_REQUEST,
                "Los datos de sesión deben ser un objeto válido",
                status_code=400
            )
        
        ui_metrics_service = UIPerformanceMetricsService()
        success = ui_metrics_service.record_ui_metrics(student_id, session_data)
        
        if success:
            return APIRoute.success(
                data={"recorded": True},
                message="Métricas de UI registradas exitosamente"
            )
        else:
            return APIRoute.error(
                ErrorCodes.OPERATION_FAILED,
                "Error al registrar métricas de UI",
                status_code=500
            )
            
    except Exception as e:
        logging.error(f"Error registrando métricas de UI: {str(e)}")
        return APIRoute.error(
            ErrorCodes.SERVER_ERROR,
            str(e),
            status_code=500
        )


@virtual_bp.route('/ui-optimizations', methods=['GET'])
@APIRoute.standard(auth_required_flag=True)
def get_ui_optimizations():
    """Obtiene las optimizaciones de UI pendientes para el estudiante actual."""
    try:
        from src.virtual.services import UIPerformanceMetricsService
        
        student_id = str(request.user_id)
        
        ui_metrics_service = UIPerformanceMetricsService()
        optimizations = ui_metrics_service.get_student_optimizations(student_id)
        
        return APIRoute.success(
            data=optimizations,
            message="Optimizaciones obtenidas exitosamente"
        )
        
    except Exception as e:
        logging.error(f"Error obteniendo optimizaciones de UI: {str(e)}")
        return APIRoute.error(
            ErrorCodes.SERVER_ERROR,
            str(e),
            status_code=500
        )


@virtual_bp.route('/ui-config', methods=['GET'])
@APIRoute.standard(auth_required_flag=True)
def get_adaptive_ui_config():
    """Genera configuración de UI adaptativa para el estudiante actual."""
    try:
        from src.virtual.services import AdaptiveUIOptimizationService
        
        student_id = str(request.user_id)
        
        ui_optimization_service = AdaptiveUIOptimizationService()
        ui_config = ui_optimization_service.generate_adaptive_ui_config(student_id)
        
        return APIRoute.success(
            data={"ui_config": ui_config},
            message="Configuración de UI adaptativa generada exitosamente"
        )
        
    except Exception as e:
        logging.error(f"Error generando configuración UI adaptativa: {str(e)}")
        return APIRoute.error(
            ErrorCodes.SERVER_ERROR,
            str(e),
            status_code=500
        )


@virtual_bp.route('/performance-analytics', methods=['GET'])
@APIRoute.standard(auth_required_flag=True)
def get_performance_analytics():
    """Obtiene analíticas de rendimiento de UI para el estudiante actual."""
    try:
        from src.virtual.services import UIPerformanceMetricsService
        
        student_id = str(request.user_id)
        days = request.args.get('days', 7, type=int)
        
        # Validar parámetros
        if days < 1 or days > 365:
            days = 7
        
        ui_metrics_service = UIPerformanceMetricsService()
        analytics = ui_metrics_service.get_performance_analytics(student_id, days)
        
        return APIRoute.success(
            data=analytics,
            message="Analíticas de rendimiento obtenidas exitosamente"
        )
        
    except Exception as e:
        logging.error(f"Error obteniendo analíticas de rendimiento: {str(e)}")
        return APIRoute.error(
            ErrorCodes.SERVER_ERROR,
            str(e),
            status_code=500
        )


@virtual_bp.route('/admin/performance-analytics', methods=['GET'])
@APIRoute.standard(auth_required_flag=True, roles=[ROLES["TEACHER"], ROLES["INSTITUTE_ADMIN"]])
def get_global_performance_analytics():
    """Obtiene analíticas de rendimiento globales (endpoint administrativo)."""
    try:
        from src.virtual.services import UIPerformanceMetricsService
        
        days = request.args.get('days', 30, type=int)
        
        # Validar parámetros
        if days < 1 or days > 365:
            days = 30
        
        ui_metrics_service = UIPerformanceMetricsService()
        analytics = ui_metrics_service.get_performance_analytics(student_id=None, days=days)
        
        return APIRoute.success(
            data=analytics,
            message="Analíticas globales de rendimiento obtenidas exitosamente"
        )
        
    except Exception as e:
        logging.error(f"Error obteniendo analíticas globales de rendimiento: {str(e)}")
        return APIRoute.error(
            ErrorCodes.SERVER_ERROR,
            str(e),
            status_code=500
        )

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
        stored_preferences = {}
        try:
            profile_str = cognitive_profile.get("profile")
            if profile_str and isinstance(profile_str, str):
                import json
                profile_json = json.loads(profile_str)
                stored_preferences = profile_json.get("contentPreferences", {})
        except Exception:
            stored_preferences = {}
        
        # 5. Obtener perfil cognitivo personalizado si existe en opciones adaptativas
        if adaptive_options.get("cognitive_profile"):
            cognitive_profile = {**cognitive_profile, **adaptive_options.get("cognitive_profile")}

        preferences = {**stored_preferences, **preferences}
            
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
                "diagrams": topic_recommendations.get("diagrams", {}).get("existing_diagrams", [])[:2]
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
                    "diagrams": topic_recommendations.get("diagrams", {}).get("existing_diagrams", [])[:2]
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

@virtual_bp.route('/module/<virtual_module_id>/recommendation', methods=['GET'])
@APIRoute.standard(auth_required_flag=True)
def get_module_recommendations(virtual_module_id):
    """Obtiene recomendaciones personalizadas para un módulo virtual específico"""
    try:
        # Obtener student_id de los parámetros de consulta
        student_id = request.args.get('student_id')
        if not student_id:
            return APIRoute.error(
                ErrorCodes.VALIDATION_ERROR,
                "El parámetro student_id es requerido",
                status_code=400
            )
        
        # Verificar que el estudiante existe
        student = get_db().users.find_one({"_id": ObjectId(student_id)})
        if not student:
            return APIRoute.error(
                ErrorCodes.NOT_FOUND,
                "Estudiante no encontrado",
                status_code=404
            )
        
        # Verificar que el módulo virtual existe
        virtual_module = get_db().virtual_modules.find_one({"_id": ObjectId(virtual_module_id)})
        if not virtual_module:
            return APIRoute.error(
                ErrorCodes.NOT_FOUND,
                "Módulo virtual no encontrado",
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
        
        # 3. Recursos específicos del módulo virtual
        # Obtener el módulo original asociado al módulo virtual
        original_module_id = virtual_module.get("module_id")
        if original_module_id:
            # Obtener temas del módulo original
            topics = list(get_db().topics.find({"module_id": ObjectId(original_module_id)}))
            
            if topics:
                # Usar el primer tema para recomendaciones
                sample_topic = str(topics[0]["_id"])
                
                # Importar servicio de recomendaciones
                from src.study_plans.services import ContentRecommendationService
                
                recommendation_service = ContentRecommendationService()
                topic_recommendations = recommendation_service.get_content_recommendations(sample_topic)
                
                # Añadir recursos recomendados para el módulo
                recommendations["resources"] = {
                    "from_virtual_module": virtual_module_id,
                    "pdfs": topic_recommendations.get("pdfs", [])[:3],
                    "web_resources": topic_recommendations.get("web_resources", [])[:3],
                    "diagrams": topic_recommendations.get("diagrams", {}).get("existing_diagrams", [])[:2]
                }
        
        return APIRoute.success(data={
            "virtual_module_id": virtual_module_id,
            "student_id": student_id,
            "learning_methodologies": recommendations["learning_methodologies"],
            "content_types": recommendations["content_types"],
            "resources": recommendations["resources"]
        })
    except Exception as e:
        logging.error(f"Error al obtener recomendaciones del módulo virtual: {str(e)}")
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
    
    # Extraer información de workspace del JWT
    jwt_claims = get_jwt()
    workspace_type = jwt_claims.get('workspace_type')
    workspace_user_id = jwt_claims.get('workspace_user_id')
    class_id = jwt_claims.get('class_id')
    
    modules = virtual_module_service.get_student_modules(
        study_plan_id, student_id, workspace_type, workspace_user_id, class_id
    )
    return APIRoute.success(data={"modules": modules})

def generate_virtual_topics(module_id: str, student_id: str, virtual_module_id: str, cognitive_profile: dict, preferences: dict):
    """
    Genera temas virtuales para un módulo. Función auxiliar separada para procesamiento asincrónico.
    """
    try:
        # Obtener temas del módulo ordenados por 'order' o fecha de creación
        topics = list(get_db().topics.find({
            "module_id": ObjectId(module_id),
            "published": True
        }).sort([("order", 1), ("created_at", 1)]))
        
        if not topics:
            logging.warning(f"No se encontraron temas publicados para el módulo {module_id}. El módulo virtual se generará sin temas.")
            return True
        
        for idx, topic in enumerate(topics):
            topic_id = str(topic["_id"])
            is_locked = idx > 0
            
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
                # Actualizar tema existente con el nuevo orden
                get_db().virtual_topics.update_one(
                    {"_id": existing["_id"]},
                    {"$set": {
                        "adaptations": adaptations,
                        "order": idx,
                        "locked": is_locked,
                        "status": "locked" if is_locked else "active",
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
                    "order": idx,
                    "locked": is_locked,
                    "status": "locked" if is_locked else "active",
                    "created_at": datetime.now(),
                    "updated_at": datetime.now(),
                    "progress": 0.0,
                    "completion_status": "not_started"
                })

                virtual_topic_id = result.inserted_id
                
            # Generar contenido personalizado para el tema
            generate_personalized_content(topic_id, str(virtual_topic_id), cognitive_profile, student_id, preferences)
            
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

def generate_personalized_content(topic_id: str, virtual_topic_id: str, cognitive_profile: dict, student_id: str, preferences: dict = None):
    """
    Genera contenido personalizado para un tema virtual usando el algoritmo avanzado.
    """
    try:
        topic = get_db().topics.find_one({"_id": ObjectId(topic_id)})
        if not topic:
            return False

        virtual_topic = get_db().virtual_topics.find_one({"_id": ObjectId(virtual_topic_id)})
        if not virtual_topic:
            return False

        # Extraer preferencias aprendidas del perfil cognitivo
        learned_preferences = {}
        try:
            profile_str = cognitive_profile.get("profile", "{}")
            if isinstance(profile_str, str):
                import json
                profile_data = json.loads(profile_str)
                content_preferences = profile_data.get("contentPreferences", {})
                learned_preferences = {
                    "avoid_types": content_preferences.get("avoid_types", []),
                    "prefer_types": content_preferences.get("prefer_types", [])
                }
        except (json.JSONDecodeError, Exception) as e:
            logging.warning(f"Error extrayendo preferencias del perfil: {e}")
            learned_preferences = {"avoid_types": [], "prefer_types": []}
        
        # Combinar preferencias aprendidas con preferencias manuales
        combined_preferences = {
            "avoid_types": list(set(learned_preferences.get("avoid_types", []) + (preferences or {}).get("avoid_types", []))),
            "prefer_types": list(set(learned_preferences.get("prefer_types", []) + (preferences or {}).get("prefer_types", [])))
        }
        
        # Agregar otras preferencias manuales
        if preferences:
            for key, value in preferences.items():
                if key not in ["avoid_types", "prefer_types"]:
                    combined_preferences[key] = value

        existing_contents = list(get_db().topic_contents.find({
            "topic_id": ObjectId(topic_id),
            "status": {"$in": ["draft", "active", "published", "approved"]}
        }))

        # Usar el algoritmo avanzado de selección personalizada
        selected_contents = fast_generator._select_personalized_contents(
            existing_contents, 
            cognitive_profile, 
            combined_preferences
        )
        
        # Fallback si no se seleccionó contenido
        if not selected_contents:
            logging.warning(f"Algoritmo avanzado no seleccionó contenidos. Usando fallback.")
            selected_contents = existing_contents[:3]
        
        # Limitar a máximo 6 contenidos según especificación
        selected_contents = selected_contents[:6]
        
        logging.info(f"Seleccionados {len(selected_contents)} contenidos personalizados para tema {virtual_topic_id}")

        for content in selected_contents:
            try:
                # Generar datos de personalización avanzados
                personalization_data = fast_generator._generate_content_personalization(content, cognitive_profile)
                
                get_db().virtual_topic_contents.insert_one({
                    "virtual_topic_id": ObjectId(virtual_topic_id),
                    "content_id": content["_id"],
                    "student_id": ObjectId(student_id),
                    "content_type": content.get("content_type", "unknown"),
                    "content": content.get("content", ""),
                    "personalization_data": personalization_data,
                    "interaction_tracking": {
                        "access_count": 0,
                        "total_time_spent": 0,
                        "last_accessed": None,
                        "completion_status": "not_started",
                        "completion_percentage": 0.0,
                        "sessions": 0,
                        "best_score": None,
                        "avg_score": None,
                        "interactions": []
                    },
                    "status": "active",
                    "created_at": datetime.now(),
                    "updated_at": datetime.now()
                })
                
                logging.debug(f"Contenido virtual creado: {content.get('content_type')} con personalización: {list(personalization_data.keys())}")
                
            except Exception as c_err:
                logging.error(f"Error creando contenido virtual para {content.get('_id')}: {c_err}")

        return True
    except Exception as e:
        logging.error(f"Error al generar contenido personalizado: {str(e)}")
        return False

@virtual_bp.route('/module/<module_id>/progress', methods=['PUT'])
@auth_required
@apply_workspace_filter('virtual_modules')
def update_module_progress(module_id):
    """Actualiza el progreso de un estudiante en un módulo virtual"""
    try:
        data = request.get_json()
        if not data:
            return APIRoute.error(
                ErrorCodes.BAD_REQUEST,
                "Se requieren datos de progreso y actividad",
                status_code=400
            )
        
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
        
        # Obtener información de workspace
        jwt_claims = get_jwt()
        workspace_info = get_current_workspace_info()
        workspace_type = jwt_claims.get('workspace_type')
        current_user_id = get_jwt_identity()
        
        # Construir filtro con workspace
        module_filter = {"_id": ObjectId(module_id)}
        if workspace_info:
            if workspace_type == 'INDIVIDUAL_STUDENT':
                module_filter["workspace_id"] = ObjectId(workspace_info['workspace_id'])
                module_filter["student_id"] = ObjectId(current_user_id)
            elif workspace_type == 'INDIVIDUAL_TEACHER':
                module_filter["workspace_id"] = ObjectId(workspace_info['workspace_id'])
            elif workspace_type == 'INSTITUTE':
                module_filter["institute_id"] = ObjectId(workspace_info['workspace_id'])
        
        # Verificar que el módulo virtual existe
        virtual_module = get_db().virtual_modules.find_one(module_filter)
        if not virtual_module:
            return APIRoute.error(
                ErrorCodes.NOT_FOUND,
                "Módulo virtual no encontrado o sin acceso",
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

                        if topic_progress >= 100:
                            try:
                                from src.virtual.services import OptimizedQueueService
                                OptimizedQueueService().trigger_on_progress(topic_id, 100)
                            except Exception as trigger_error:
                                logging.warning(f"Error al triggear cola para {topic_id}: {str(trigger_error)}")

                            try:
                                updated_topic = get_db().virtual_topics.find_one({"_id": ObjectId(topic_id)})
                                if updated_topic:
                                    virtual_topic_service._update_module_progress_from_topic(updated_topic)
                            except Exception as update_err:
                                logging.warning(f"Error recalculando progreso de módulo: {str(update_err)}")
                    except Exception as topic_error:
                        logging.warning(f"Error al actualizar tema {topic_id}: {str(topic_error)}")

            # Obtener progreso actualizado del módulo tras procesar los temas
            refreshed = get_db().virtual_modules.find_one({"_id": ObjectId(module_id)})
            if refreshed:
                progress = refreshed.get("progress", progress)
                completion_status = refreshed.get("completion_status", completion_status)
        
        # Calcular métricas adicionales
        metrics = {
            "total_study_time": activity_data.get("study_time", 0),
            "resources_viewed": activity_data.get("resources_viewed", 0),
            "activities_completed": activity_data.get("activities_completed", 0)
        }

        if completion_status == "completed":
            try:
                from src.virtual.services import AdaptiveLearningService
                AdaptiveLearningService().update_profile_from_results(str(student_id))
            except Exception as profile_err:
                logging.warning(f"Error actualizando perfil adaptativo: {profile_err}")

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

@virtual_bp.route('/trigger-next-topic', methods=['POST'])
@APIRoute.standard(auth_required_flag=True, required_fields=['current_topic_id', 'student_id', 'progress'])
def trigger_next_topic():
    """
    Disparado cuando el progreso de un tema supera el 80%.
    Genera el siguiente lote de temas disponibles para el estudiante.
    """
    try:
        data = request.get_json()
        current_topic_id = data.get('current_topic_id')
        student_id = data.get('student_id')
        progress = data.get('progress', 0)
        
        # 1. Validar progreso mínimo
        if progress < 80:
            return APIRoute.error(
                ErrorCodes.BAD_REQUEST,
                "El progreso debe ser mayor al 80% para activar siguiente generación de temas",
                status_code=400
            )
        
        # 2. Llamar al servicio de generación de temas
        success, result = virtual_topic_service.trigger_next_topic_generation(
            student_id=student_id,
            current_topic_id=current_topic_id,
            progress=progress
        )
        
        if not success:
            return APIRoute.error(
                ErrorCodes.OPERATION_FAILED,
                result.get("message", "Error desconocido"),
                status_code=400
            )
        
        return APIRoute.success(
            data={
                "generated_topics": result.get("generated_topics", []),
                "has_next": result.get("has_next", False),
                "message": result.get("message", "")
            },
            message=f"Generación de temas completada: {len(result.get('generated_topics', []))} nuevos temas"
        )
        
    except Exception as e:
        logging.error(f"Error al activar siguiente generación de temas: {str(e)}")
        return APIRoute.error(
            ErrorCodes.SERVER_ERROR,
            str(e),
            status_code=500
        )

@virtual_bp.route('/process-queue', methods=['POST'])
@APIRoute.standard(auth_required_flag=True, roles=[ROLES["ADMIN"]])
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

                    success, result = virtual_topic_service.synchronize_module_content(virtual_module_id)
                    
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

# ===== ENDPOINTS PARA CONTENTRESULT AUTOMÁTICO =====

@virtual_bp.route('/content/<virtual_content_id>/complete-auto', methods=['POST'])
@virtual_bp.route('/contents/<virtual_content_id>/auto-complete', methods=['POST'])
@APIRoute.standard(auth_required_flag=True, roles=[ROLES["STUDENT"]])
def auto_complete_content(virtual_content_id):
    """
    Completa automáticamente un contenido virtual y crea ContentResult.
    Para contenidos de lectura, visualización, etc.
    """
    try:
        from flask_jwt_extended import get_jwt_identity
        from .services import VirtualContentProgressService
        
        student_id = get_jwt_identity()
        data = request.get_json() or {}
        
        # Datos de completación opcionales
        completion_data = {
            "session_data": {
                "time_spent": data.get("time_spent", 0),
                "scroll_percentage": data.get("scroll_percentage", 100),
                "interactions": data.get("interactions", 1),
                "completion_method": data.get("completion_method", "auto")
            }
        }
        
        # Si se proporciona un score específico, usarlo
        if "score" in data:
            completion_data["score"] = data["score"]
        
        progress_service = VirtualContentProgressService()
        success, result = progress_service.complete_content_automatically(
            virtual_content_id, student_id, completion_data
        )
        
        if success:
            return APIRoute.success(
                data={
                    "content_result_id": result,
                    "status": "completed",
                    "auto_generated": True
                },
                message="Contenido completado automáticamente",
                status_code=200
            )
        else:
            return APIRoute.error(
                ErrorCodes.OPERATION_FAILED,
                result,
                status_code=400
            )
            
    except Exception as e:
        logging.error(f"Error en auto-complete: {str(e)}")
        return APIRoute.error(
            ErrorCodes.SERVER_ERROR,
            str(e),
            status_code=500
        )

@virtual_bp.route('/content/<virtual_content_id>/complete-reading', methods=['POST'])
@virtual_bp.route('/contents/<virtual_content_id>/auto-complete-reading', methods=['POST'])
@APIRoute.standard(auth_required_flag=True, roles=[ROLES["STUDENT"]])
def auto_complete_reading_content(virtual_content_id):
    """
    Completa automáticamente contenidos de lectura (texto, slides, videos).
    Optimizado para contenidos que solo requieren visualización.
    """
    try:
        from flask_jwt_extended import get_jwt_identity
        from .services import VirtualContentProgressService
        
        student_id = get_jwt_identity()
        data = request.get_json() or {}
        
        # Datos específicos de lectura
        reading_data = {
            "time_spent": data.get("time_spent", 0),
            "scroll_percentage": data.get("scroll_percentage", 100),
            "reading_speed": data.get("reading_speed", 0),  # palabras por minuto
            "pauses": data.get("pauses", 0),  # número de pausas
            "interactions": data.get("interactions", 1)
        }
        
        progress_service = VirtualContentProgressService()
        success, result = progress_service.auto_complete_reading_content(
            virtual_content_id, student_id, reading_data
        )
        
        if success:
            return APIRoute.success(
                data={
                    "content_result_id": result,
                    "status": "completed",
                    "completion_method": "reading"
                },
                message="Contenido de lectura completado automáticamente",
                status_code=200
            )
        else:
            return APIRoute.error(
                ErrorCodes.OPERATION_FAILED,
                result,
                status_code=400
            )
            
    except Exception as e:
        logging.error(f"Error en auto-complete reading: {str(e)}")
        return APIRoute.error(
            ErrorCodes.SERVER_ERROR,
            str(e),
            status_code=500
        )

@virtual_bp.route('/student/progress', methods=['GET'])
@auth_required
@role_required([ROLES["STUDENT"], ROLES["TEACHER"]])
@apply_workspace_filter('virtual_modules')
def get_student_progress():
    """
    Obtiene resumen completo del progreso del estudiante.
    Los estudiantes ven su propio progreso, los profesores pueden especificar student_id.
    """
    try:
        from .services import VirtualContentProgressService
        
        current_user_id = get_jwt_identity()
        jwt_claims = get_jwt()
        workspace_info = get_current_workspace_info()
        workspace_type = jwt_claims.get('workspace_type')
        user_roles = getattr(request, 'user_roles', [])
        
        # Determinar student_id con restricciones de workspace
        if ROLES["TEACHER"] in user_roles:
            # Profesores pueden ver progreso de cualquier estudiante
            student_id = request.args.get('student_id', current_user_id)
        else:
            # Estudiantes solo ven su propio progreso
            student_id = current_user_id
        
        # En workspaces individuales, restringir acceso
        if workspace_type in ['INDIVIDUAL_TEACHER', 'INDIVIDUAL_STUDENT']:
            if student_id != current_user_id:
                return APIRoute.error(
                    ErrorCodes.PERMISSION_DENIED,
                    "En workspaces individuales solo puedes ver tu propio progreso",
                    status_code=403
                )
        
        # Filtro opcional por módulo
        virtual_module_id = request.args.get('virtual_module_id')
        
        progress_service = VirtualContentProgressService()
        progress_summary = progress_service.get_student_progress_summary(
            student_id, virtual_module_id, workspace_info
        )
        
        # Enriquecer con información adicional si es necesario
        if virtual_module_id:
            # Obtener información del módulo virtual con filtro de workspace
            module_filter = {"_id": ObjectId(virtual_module_id)}
            if workspace_info:
                if workspace_type == 'INDIVIDUAL_STUDENT':
                    module_filter["workspace_id"] = ObjectId(workspace_info['workspace_id'])
                elif workspace_type == 'INSTITUTE':
                    module_filter["institute_id"] = ObjectId(workspace_info['workspace_id'])
            
            virtual_module = get_db().virtual_modules.find_one(module_filter)
            if virtual_module:
                progress_summary["module_info"] = {
                    "name": virtual_module.get("name", ""),
                    "status": virtual_module.get("completion_status", "not_started"),
                    "overall_progress": virtual_module.get("progress", 0)
                }
        
        # Agregar contexto de workspace
        if workspace_info:
            progress_summary["workspace_context"] = {
                "workspace_type": workspace_type,
                "workspace_name": workspace_info.get('name', '')
            }
        
        return APIRoute.success(data=progress_summary)
        
    except Exception as e:
        logging.error(f"Error obteniendo progreso del estudiante: {str(e)}")
        return APIRoute.error(
            ErrorCodes.SERVER_ERROR,
            str(e),
            status_code=500
        )

@virtual_bp.route('/content/<virtual_content_id>/trigger-next', methods=['POST'])
@APIRoute.standard(auth_required_flag=True, roles=[ROLES["STUDENT"]])
def trigger_next_topic_generation(virtual_content_id):
    """
    Endpoint manual para activar la generación del siguiente tema.
    Útil para testing y casos especiales.
    """
    try:
        from .services import VirtualContentProgressService
        
        # Obtener contenido virtual
        virtual_content = get_db().virtual_topic_contents.find_one({
            "_id": ObjectId(virtual_content_id)
        })
        
        if not virtual_content:
            return APIRoute.error(
                ErrorCodes.NOT_FOUND,
                "Contenido virtual no encontrado",
                status_code=404
            )
        
        # Usar el servicio para trigger
        progress_service = VirtualContentProgressService()
        progress_service._trigger_next_topic_generation(virtual_content)
        
        return APIRoute.success(
            data={"status": "triggered"},
            message="Generación del siguiente tema activada"
        )
        
    except Exception as e:
        logging.error(f"Error activando generación siguiente tema: {str(e)}")
        return APIRoute.error(
            ErrorCodes.SERVER_ERROR,
            str(e),
            status_code=500
        )

# ===== ENDPOINT DE COMPLETACIÓN DE MÓDULO =====

@virtual_bp.route('/module/<module_id>/complete', methods=['POST'])
@auth_required
@role_required([ROLES["STUDENT"]])
@apply_workspace_filter('virtual_modules')
def complete_virtual_module(module_id):
    """
    Marca un módulo como completado y activa aprendizaje adaptativo.
    Endpoint crítico para Fase 2B - activación automática de actualización de perfil.
    """
    try:
        student_id = get_jwt_identity()
        jwt_claims = get_jwt()
        workspace_info = get_current_workspace_info()
        workspace_type = jwt_claims.get('workspace_type')
        data = request.get_json() or {}
        
        # Construir filtro con workspace
        module_filter = {
            "_id": ObjectId(module_id),
            "student_id": ObjectId(student_id)
        }
        if workspace_info:
            if workspace_type == 'INDIVIDUAL_STUDENT':
                module_filter["workspace_id"] = ObjectId(workspace_info['workspace_id'])
            elif workspace_type == 'INSTITUTE':
                module_filter["institute_id"] = ObjectId(workspace_info['workspace_id'])
        
        # Verificar que el módulo virtual existe y pertenece al estudiante
        virtual_module = get_db().virtual_modules.find_one(module_filter)
        
        if not virtual_module:
            return APIRoute.error(
                ErrorCodes.NOT_FOUND,
                "Módulo virtual no encontrado o no tienes acceso",
                status_code=404
            )
        
        # Verificar que el módulo no esté ya completado
        if virtual_module.get("completion_status") == "completed":
            return APIRoute.error(
                ErrorCodes.BAD_REQUEST,
                "El módulo ya está marcado como completado",
                status_code=400
            )
        
        # Obtener progreso actual de todos los temas del módulo
        virtual_topics = list(get_db().virtual_topics.find({
            "virtual_module_id": ObjectId(module_id)
        }))
        
        if not virtual_topics:
            return APIRoute.error(
                ErrorCodes.BAD_REQUEST,
                "No se encontraron temas en este módulo",
                status_code=400
            )
        
        # Calcular progreso real del módulo
        total_progress = sum(topic.get("progress", 0) for topic in virtual_topics)
        module_progress = total_progress / len(virtual_topics) if virtual_topics else 0
        
        # Permitir completación manual si el progreso es >= 80%
        min_progress_required = data.get("min_progress", 80)
        if module_progress < min_progress_required:
            return APIRoute.error(
                ErrorCodes.BAD_REQUEST,
                f"El módulo debe tener al menos {min_progress_required}% de progreso para completarse. Progreso actual: {module_progress:.1f}%",
                status_code=400
            )
        
        # Marcar módulo como completado
        completion_time = datetime.now()
        get_db().virtual_modules.update_one(
            {"_id": ObjectId(module_id)},
            {"$set": {
                "completion_status": "completed",
                "progress": 100.0,
                "completed_at": completion_time,
                "updated_at": completion_time
            }}
        )
        
        # Activar aprendizaje adaptativo - FUNCIONALIDAD CRÍTICA FASE 2B
        adaptive_service = AdaptiveLearningService()
        profile_updated = False
        
        try:
            profile_updated = adaptive_service.update_profile_from_results(student_id)
            logging.info(f"Perfil adaptativo actualizado para estudiante {student_id}: {profile_updated}")
        except Exception as adaptive_err:
            logging.error(f"Error actualizando perfil adaptativo: {adaptive_err}")
            # No fallar la completación por error en perfil adaptativo
        
        # Trigger para generar siguiente módulo si existe
        next_module_generated = False
        try:
            # Obtener información del módulo original
            original_module = get_db().modules.find_one({"_id": virtual_module["module_id"]})
            if original_module:
                study_plan_id = virtual_module["study_plan_id"]
                current_order = original_module.get("order", 0)
                
                # Buscar siguiente módulo en el plan de estudios
                next_module = get_db().modules.find_one({
                    "study_plan_id": ObjectId(study_plan_id),
                    "order": current_order + 1,
                    "published": True
                })
                
                if next_module:
                    # Verificar si el siguiente módulo virtual ya existe
                    existing_next = get_db().virtual_modules.find_one({
                        "module_id": next_module["_id"],
                        "student_id": ObjectId(student_id)
                    })
                    
                    if not existing_next:
                        # Encolar generación del siguiente módulo
                        queue_service.enqueue_task(
                            student_id=student_id,
                            module_id=str(next_module["_id"]),
                            task_type="generate",
                            priority=1,
                            payload={
                                "trigger_reason": "module_completion",
                                "source_module_id": str(virtual_module["module_id"]),
                                "completion_time": completion_time.isoformat()
                            }
                        )
                        next_module_generated = True
                        logging.info(f"Siguiente módulo encolado para generación: {next_module['_id']}")
        
        except Exception as next_module_err:
            logging.warning(f"Error generando siguiente módulo: {next_module_err}")
        
        # Respuesta de éxito
        return APIRoute.success(
            data={
                "module_id": module_id,
                "completion_status": "completed",
                "progress": 100.0,
                "completed_at": completion_time.isoformat(),
                "adaptive_learning": {
                    "profile_updated": profile_updated,
                    "update_triggered": True
                },
                "next_module": {
                    "generation_triggered": next_module_generated
                },
                "module_progress": module_progress
            },
            message="Módulo completado exitosamente y perfil adaptativo actualizado",
            status_code=200
        )
        
    except Exception as e:
        logging.error(f"Error completando módulo virtual: {str(e)}")
        return APIRoute.error(
            ErrorCodes.SERVER_ERROR,
            f"Error interno al completar módulo: {str(e)}",
            status_code=500
        )

# ===== ENDPOINTS DE BULK OPERATIONS =====

@virtual_bp.route('/student/<student_id>/complete-reading-contents', methods=['POST'])
@APIRoute.standard(auth_required_flag=True, roles=[ROLES["TEACHER"]])
def bulk_complete_reading_contents(student_id):
    """
    Completa en lote todos los contenidos de lectura pendientes de un estudiante.
    Útil para migración de datos o casos especiales.
    """
    try:
        from .services import VirtualContentProgressService
        data = request.get_json() or {}
        
        # Obtener filtros opcionales
        virtual_module_id = data.get("virtual_module_id")
        content_types = data.get("content_types", ["text", "slides", "video", "audio", "diagram"])
        
        # Construir filtro
        content_filter = {
            "student_id": ObjectId(student_id),
            "content_type": {"$in": content_types},
            "interaction_tracking.completion_status": {"$ne": "completed"}
        }
        
        if virtual_module_id:
            # Obtener temas del módulo específico
            virtual_topics = list(get_db().virtual_topics.find({
                "virtual_module_id": ObjectId(virtual_module_id)
            }))
            topic_ids = [vt["_id"] for vt in virtual_topics]
            content_filter["virtual_topic_id"] = {"$in": topic_ids}
        
        # Obtener contenidos pendientes
        pending_contents = list(get_db().virtual_topic_contents.find(content_filter))
        
        # Completar cada contenido
        progress_service = VirtualContentProgressService()
        completed_count = 0
        errors = []
        
        for content in pending_contents:
            try:
                success, result = progress_service.auto_complete_reading_content(
                    str(content["_id"]), student_id
                )
                if success:
                    completed_count += 1
                else:
                    errors.append(f"Contenido {content['_id']}: {result}")
            except Exception as content_error:
                errors.append(f"Contenido {content['_id']}: {str(content_error)}")
        
        return APIRoute.success(
            data={
                "total_processed": len(pending_contents),
                "completed_count": completed_count,
                "errors_count": len(errors),
                "errors": errors[:10]  # Solo primeros 10 errores
            },
            message=f"Procesados {len(pending_contents)} contenidos, {completed_count} completados"
        )
        
    except Exception as e:
        logging.error(f"Error en bulk complete: {str(e)}")
        return APIRoute.error(
            ErrorCodes.SERVER_ERROR,
            str(e),
            status_code=500
        )

# ===== ENDPOINTS PARA SINCRONIZACIÓN AUTOMÁTICA =====

@virtual_bp.route('/module/<virtual_module_id>/sync-auto', methods=['POST'])
@APIRoute.standard(auth_required_flag=True, roles=[ROLES["TEACHER"]])
def auto_sync_module(virtual_module_id):
    """
    Sincroniza automáticamente un módulo virtual si es necesario.
    Detecta cambios y solo sincroniza cuando es apropiado.
    """
    try:
        from src.virtual.services import AutoSyncService
        
        data = request.get_json() or {}
        force = data.get("force", False)
        
        auto_sync_service = AutoSyncService()
        synced, report = auto_sync_service.check_and_sync_if_needed(virtual_module_id, force)
        
        if synced:
            return APIRoute.success(
                data={
                    "synchronized": True,
                    "report": report,
                    "timestamp": datetime.now()
                },
                message="Módulo sincronizado exitosamente"
            )
        elif report.get("skipped"):
            return APIRoute.success(
                data={
                    "synchronized": False,
                    "skipped": True,
                    "reason": report.get("reason"),
                    "details": report
                },
                message="Sincronización omitida"
            )
        else:
            return APIRoute.error(
                ErrorCodes.OPERATION_FAILED,
                report.get("error", "Error desconocido en sincronización"),
                status_code=400
            )
            
    except Exception as e:
        logging.error(f"Error en auto-sync: {str(e)}")
        return APIRoute.error(
            ErrorCodes.SERVER_ERROR,
            str(e),
            status_code=500
        )

@virtual_bp.route('/sync/bulk', methods=['POST'])
@APIRoute.standard(auth_required_flag=True, roles=[ROLES["TEACHER"], ROLES["INSTITUTE_ADMIN"]])
def bulk_auto_sync():
    """
    Sincroniza múltiples módulos virtuales en lote.
    Permite filtrar por estudiante o módulo específico.
    """
    try:
        from src.virtual.services import AutoSyncService
        
        data = request.get_json() or {}
        student_id = data.get("student_id")
        module_id = data.get("module_id") 
        max_modules = data.get("max_modules", 50)
        
        # Validaciones
        if max_modules > 200:
            max_modules = 200  # Límite máximo de seguridad
        
        auto_sync_service = AutoSyncService()
        stats = auto_sync_service.bulk_check_and_sync(
            student_id=student_id,
            module_id=module_id,
            max_modules=max_modules
        )
        
        return APIRoute.success(
            data=stats,
            message=f"Procesados {stats['processed']} módulos, {stats['synchronized']} sincronizados"
        )
        
    except Exception as e:
        logging.error(f"Error en bulk sync: {str(e)}")
        return APIRoute.error(
            ErrorCodes.SERVER_ERROR,
            str(e),
            status_code=500
        )

@virtual_bp.route('/sync/schedule', methods=['POST'])
@APIRoute.standard(auth_required_flag=True, roles=[ROLES["INSTITUTE_ADMIN"]])
def schedule_auto_sync():
    """
    Programa sincronización automática periódica.
    Ejecuta un ciclo de sincronización de todos los módulos que lo necesiten.
    """
    try:
        from src.virtual.services import AutoSyncService
        
        data = request.get_json() or {}
        interval_hours = data.get("interval_hours", 6)
        
        # Validar intervalo
        if interval_hours < 1:
            interval_hours = 1
        elif interval_hours > 24:
            interval_hours = 24
        
        auto_sync_service = AutoSyncService()
        result = auto_sync_service.schedule_auto_sync(interval_hours)
        
        if result.get("scheduled"):
            return APIRoute.success(
                data=result,
                message=f"Sincronización automática programada cada {interval_hours} horas"
            )
        else:
            return APIRoute.success(
                data=result,
                message=result.get("reason", "No se programó sincronización")
            )
            
    except Exception as e:
        logging.error(f"Error en schedule sync: {str(e)}")
        return APIRoute.error(
            ErrorCodes.SERVER_ERROR,
            str(e),
            status_code=500
        )

@virtual_bp.route('/module/<virtual_module_id>/sync-status', methods=['GET'])
@APIRoute.standard(auth_required_flag=True)
def get_sync_status(virtual_module_id):
    """
    Obtiene el estado de sincronización de un módulo virtual.
    """
    try:
        from src.virtual.services import ContentChangeDetector
        
        # Obtener módulo virtual
        virtual_module = get_db().virtual_modules.find_one({
            "_id": ObjectId(virtual_module_id)
        })
        
        if not virtual_module:
            return APIRoute.error(
                ErrorCodes.NOT_FOUND,
                "Módulo virtual no encontrado",
                status_code=404
            )
        
        # Obtener información de sincronización
        module_id = str(virtual_module["module_id"])
        change_detector = ContentChangeDetector()
        change_report = change_detector.detect_changes(module_id)
        
        # Preparar respuesta
        sync_status = {
            "virtual_module_id": virtual_module_id,
            "last_sync_date": virtual_module.get("last_sync_date"),
            "sync_count": virtual_module.get("sync_count", 0),
            "last_sync_report": virtual_module.get("last_sync_report", {}),
            "current_module_hash": change_report.get("current_hash"),
            "has_changes": change_report.get("has_changes", False),
            "needs_sync": False
        }
        
        # Determinar si necesita sincronización
        from src.virtual.services import AutoSyncService
        auto_sync = AutoSyncService()
        sync_status["needs_sync"] = auto_sync._needs_synchronization(virtual_module, change_report)
        
        # Información adicional
        if change_report.get("has_changes"):
            sync_status["change_details"] = {
                "previous_hash": change_report.get("previous_hash"),
                "change_timestamp": change_report.get("change_timestamp")
            }
        
        return APIRoute.success(data=sync_status)
        
    except Exception as e:
        logging.error(f"Error obteniendo estado de sync: {str(e)}")
        return APIRoute.error(
            ErrorCodes.SERVER_ERROR,
            str(e),
            status_code=500
        )

@virtual_bp.route('/sync/detect-changes/<module_id>', methods=['POST'])
@APIRoute.standard(auth_required_flag=True, roles=[ROLES["TEACHER"]])
def detect_module_changes(module_id):
    """
    Detecta cambios en un módulo original específico.
    Útil para verificar qué módulos virtuales necesitarían sincronización.
    """
    try:
        from src.virtual.services import ContentChangeDetector
        
        change_detector = ContentChangeDetector()
        change_report = change_detector.detect_changes(module_id)
        
        # Obtener módulos virtuales afectados
        affected_modules = list(get_db().virtual_modules.find({
            "module_id": ObjectId(module_id),
            "completion_status": {"$ne": "completed"}
        }))
        
        # Preparar información de módulos afectados
        affected_info = []
        for vm in affected_modules:
            affected_info.append({
                "virtual_module_id": str(vm["_id"]),
                "student_id": str(vm["student_id"]),
                "progress": vm.get("progress", 0),
                "last_sync": vm.get("last_sync_date"),
                "sync_count": vm.get("sync_count", 0)
            })
        
        return APIRoute.success(
            data={
                "module_id": module_id,
                "change_report": change_report,
                "affected_virtual_modules": len(affected_modules),
                "modules_info": affected_info
            },
            message=f"{'Cambios detectados' if change_report.get('has_changes') else 'Sin cambios'} en módulo {module_id}"
        )
        
    except Exception as e:
        logging.error(f"Error detectando cambios: {str(e)}")
        return APIRoute.error(
            ErrorCodes.SERVER_ERROR,
            str(e),
            status_code=500
        )

# ===== ENDPOINTS PARA COLA OPTIMIZADA =====

@virtual_bp.route('/module/<virtual_module_id>/queue/maintain', methods=['POST'])
@APIRoute.standard(auth_required_flag=True, roles=[ROLES["STUDENT"], ROLES["TEACHER"]])
def maintain_topic_queue(virtual_module_id):
    """
    Mantiene la cola de temas virtuales asegurando que siempre haya 2 temas disponibles.
    """
    try:
        from src.virtual.services import OptimizedQueueService
        
        data = request.get_json() or {}
        current_progress = data.get("current_progress", 0)
        
        queue_service = OptimizedQueueService()
        result = queue_service.maintain_topic_queue(virtual_module_id, current_progress)
        
        if result.get("error"):
            return APIRoute.error(
                ErrorCodes.OPERATION_FAILED,
                result["error"],
                status_code=400
            )
        
        return APIRoute.success(
            data=result,
            message=f"Cola mantenida: {result.get('generated_topics', 0)} temas generados"
        )
        
    except Exception as e:
        logging.error(f"Error manteniendo cola: {str(e)}")
        return APIRoute.error(
            ErrorCodes.SERVER_ERROR,
            str(e),
            status_code=500
        )

@virtual_bp.route('/topic/<virtual_topic_id>/trigger-progress', methods=['POST'])
@auth_required
@role_required([ROLES["STUDENT"]])
@apply_workspace_filter('virtual_topics')
def trigger_progress(virtual_topic_id):
    """
    Activa el trigger de progreso para un tema específico.
    Usado cuando el tema alcanza 80% o 100% de progreso.
    """
    try:
        from src.virtual.services import OptimizedQueueService
        
        data = request.get_json()
        if not data or "progress_percentage" not in data:
            return APIRoute.error(
                ErrorCodes.BAD_REQUEST,
                "Se requiere progress_percentage",
                status_code=400
            )
        
        progress_percentage = data["progress_percentage"]
        
        # Validar progreso
        if not (0 <= progress_percentage <= 100):
            return APIRoute.error(
                ErrorCodes.BAD_REQUEST,
                "progress_percentage debe estar entre 0 y 100",
                status_code=400
            )
        
        # Obtener información de workspace
        jwt_claims = get_jwt()
        workspace_info = get_current_workspace_info()
        workspace_type = jwt_claims.get('workspace_type')
        current_user_id = get_jwt_identity()
        
        # Verificar acceso al tema virtual con filtro de workspace
        topic_filter = {"_id": ObjectId(virtual_topic_id)}
        if workspace_info:
            # Obtener el módulo virtual asociado para verificar workspace
            virtual_topic = get_db().virtual_topics.find_one(topic_filter)
            if virtual_topic:
                virtual_module_id = virtual_topic.get("virtual_module_id")
                if virtual_module_id:
                    module_filter = {"_id": ObjectId(virtual_module_id)}
                    if workspace_type == 'INDIVIDUAL_STUDENT':
                        module_filter["workspace_id"] = ObjectId(workspace_info['workspace_id'])
                        module_filter["student_id"] = ObjectId(current_user_id)
                    elif workspace_type == 'INSTITUTE':
                        module_filter["institute_id"] = ObjectId(workspace_info['workspace_id'])
                    
                    # Verificar que el módulo existe en el workspace
                    virtual_module = get_db().virtual_modules.find_one(module_filter)
                    if not virtual_module:
                        return APIRoute.error(
                            ErrorCodes.PERMISSION_DENIED,
                            "No tienes acceso a este tema virtual",
                            status_code=403
                        )
        
        queue_service = OptimizedQueueService()
        result = queue_service.trigger_on_progress(virtual_topic_id, progress_percentage)
        
        if result.get("error"):
            return APIRoute.error(
                ErrorCodes.OPERATION_FAILED,
                result["error"],
                status_code=400
            )
        
        return APIRoute.success(
            data=result,
            message=f"Trigger {'ejecutado' if result.get('triggered') else 'no ejecutado'}: {progress_percentage}%"
        )
        
    except Exception as e:
        logging.error(f"Error en trigger de progreso: {str(e)}")
        return APIRoute.error(
            ErrorCodes.SERVER_ERROR,
            str(e),
            status_code=500
        )

@virtual_bp.route('/module/<virtual_module_id>/queue/status', methods=['GET'])
@APIRoute.standard(auth_required_flag=True)
def get_queue_status(virtual_module_id):
    """
    Obtiene el estado actual de la cola de temas virtuales.
    """
    try:
        from src.virtual.services import OptimizedQueueService
        
        queue_service = OptimizedQueueService()
        status = queue_service.get_queue_status(virtual_module_id)
        
        if status.get("error"):
            return APIRoute.error(
                ErrorCodes.NOT_FOUND,
                status["error"],
                status_code=404
            )
        
        return APIRoute.success(data=status)
        
    except Exception as e:
        logging.error(f"Error obteniendo estado de cola: {str(e)}")
        return APIRoute.error(
            ErrorCodes.SERVER_ERROR,
            str(e),
            status_code=500
        )

@virtual_bp.route('/queue/bulk-initialize', methods=['POST'])
@APIRoute.standard(auth_required_flag=True, roles=[ROLES["TEACHER"], ROLES["INSTITUTE_ADMIN"]])
def bulk_initialize_queues():
    """
    Inicializa colas para múltiples módulos virtuales en lote.
    Útil para setup masivo o mantenimiento del sistema.
    """
    try:
        from src.virtual.services import OptimizedQueueService
        
        data = request.get_json() or {}
        max_modules = data.get("max_modules", 100)
        
        # Validar límites
        if max_modules > 500:
            max_modules = 500  # Límite de seguridad
        
        queue_service = OptimizedQueueService()
        stats = queue_service.bulk_initialize_queues(max_modules)
        
        if stats.get("error"):
            return APIRoute.error(
                ErrorCodes.OPERATION_FAILED,
                stats["error"],
                status_code=500
            )
        
        return APIRoute.success(
            data=stats,
            message=f"Procesados {stats['processed']} módulos, {stats['initialized']} inicializados"
        )
        
    except Exception as e:
        logging.error(f"Error en inicialización bulk: {str(e)}")
        return APIRoute.error(
            ErrorCodes.SERVER_ERROR,
            str(e),
            status_code=500
        )

@virtual_bp.route('/topic/<virtual_topic_id>/unlock', methods=['POST'])
@APIRoute.standard(auth_required_flag=True, roles=[ROLES["TEACHER"]])
def unlock_topic_manual(virtual_topic_id):
    """
    Desbloquea manualmente un tema virtual.
    Útil para casos especiales o resolución de problemas.
    """
    try:
        # Verificar que el tema existe
        virtual_topic = get_db().virtual_topics.find_one({
            "_id": ObjectId(virtual_topic_id)
        })
        
        if not virtual_topic:
            return APIRoute.error(
                ErrorCodes.NOT_FOUND,
                "Tema virtual no encontrado",
                status_code=404
            )
        
        # Desbloquear tema
        get_db().virtual_topics.update_one(
            {"_id": ObjectId(virtual_topic_id)},
            {"$set": {
                "locked": False,
                "status": "active",
                "updated_at": datetime.now()
            }}
        )
        
        return APIRoute.success(
            data={
                "virtual_topic_id": virtual_topic_id,
                "unlocked": True,
                "timestamp": datetime.now()
            },
            message="Tema desbloqueado exitosamente"
        )
        
    except Exception as e:
        logging.error(f"Error desbloqueando tema manual: {str(e)}")
        return APIRoute.error(
            ErrorCodes.SERVER_ERROR,
            str(e),
            status_code=500
        )

@virtual_bp.route('/queue/health-check', methods=['GET'])
@APIRoute.standard(auth_required_flag=True, roles=[ROLES["INSTITUTE_ADMIN"]])
def queue_health_check():
    """
    Verifica el estado de salud del sistema de colas.
    Proporciona métricas y estadísticas del sistema.
    """
    try:
        # Estadísticas de módulos virtuales
        total_modules = get_db().virtual_modules.count_documents({})
        active_modules = get_db().virtual_modules.count_documents({
            "completion_status": {"$in": ["not_started", "in_progress"]}
        })
        completed_modules = get_db().virtual_modules.count_documents({
            "completion_status": "completed"
        })
        
        # Estadísticas de temas virtuales
        total_topics = get_db().virtual_topics.count_documents({})
        locked_topics = get_db().virtual_topics.count_documents({"locked": True})
        completed_topics = get_db().virtual_topics.count_documents({
            "completion_status": "completed"
        })
        
        # Estadísticas de contenidos virtuales
        total_contents = get_db().virtual_topic_contents.count_documents({})
        completed_contents = get_db().virtual_topic_contents.count_documents({
            "interaction_tracking.completion_status": "completed"
        })
        
        # Módulos que necesitan mantenimiento de cola
        modules_needing_queue = get_db().virtual_modules.aggregate([
            {"$match": {"completion_status": {"$ne": "completed"}}},
            {"$lookup": {
                "from": "virtual_topics",
                "localField": "_id",
                "foreignField": "virtual_module_id",
                "as": "topics"
            }},
            {"$match": {"$expr": {"$lt": [{"$size": "$topics"}, 3]}}},
            {"$count": "modules_needing_queue"}
        ])
        
        modules_needing_queue_count = list(modules_needing_queue)
        modules_needing_queue_count = modules_needing_queue_count[0].get("modules_needing_queue", 0) if modules_needing_queue_count else 0
        
        health_status = {
            "system_health": "healthy" if modules_needing_queue_count < (active_modules * 0.1) else "needs_attention",
            "modules": {
                "total": total_modules,
                "active": active_modules,
                "completed": completed_modules,
                "needing_queue_maintenance": modules_needing_queue_count
            },
            "topics": {
                "total": total_topics,
                "locked": locked_topics,
                "completed": completed_topics,
                "completion_rate": round((completed_topics / total_topics) * 100, 2) if total_topics > 0 else 0
            },
            "contents": {
                "total": total_contents,
                "completed": completed_contents,
                "completion_rate": round((completed_contents / total_contents) * 100, 2) if total_contents > 0 else 0
            },
            "recommendations": []
        }
        
        # Generar recomendaciones
        if modules_needing_queue_count > 0:
            health_status["recommendations"].append(
                f"Ejecutar bulk_initialize_queues para {modules_needing_queue_count} módulos"
            )
        
        if locked_topics > (total_topics * 0.8):
            health_status["recommendations"].append(
                "Alto número de temas bloqueados - verificar triggers de progreso"
            )
        
        return APIRoute.success(data=health_status)
        
    except Exception as e:
        logging.error(f"Error en health check: {str(e)}")
        return APIRoute.error(
            ErrorCodes.SERVER_ERROR,
            str(e),
            status_code=500
        )


# ========== NUEVOS ENDPOINTS OPTIMIZADOS PARA GESTIÓN DE COLA ==========

@virtual_bp.route('/module/<module_id>/queue/status', methods=['GET'])
@APIRoute.standard(auth_required_flag=True)
def get_module_queue_status(module_id):
    """Obtiene el estado actual de la cola de temas de un módulo virtual específico."""
    try:
        from src.virtual.services import OptimizedQueueService
        
        # Verificar que el módulo virtual existe
        virtual_module = get_db().virtual_modules.find_one({"_id": ObjectId(module_id)})
        if not virtual_module:
            return APIRoute.error(
                ErrorCodes.NOT_FOUND,
                "Módulo virtual no encontrado",
                status_code=404
            )
        
        # Verificar permisos
        student_id = virtual_module.get("student_id")
        if str(student_id) != str(request.user_id) and "TEACHER" not in request.user_roles:
            return APIRoute.error(
                ErrorCodes.PERMISSION_DENIED,
                "No tienes permiso para ver el estado de este módulo",
                status_code=403
            )
        
        queue_service = OptimizedQueueService()
        status = queue_service.get_queue_status(module_id)
        
        if "error" in status:
            return APIRoute.error(
                ErrorCodes.OPERATION_FAILED,
                status["error"],
                status_code=400
            )
        
        return APIRoute.success(
            data=status,
            message="Estado de cola obtenido exitosamente"
        )
        
    except Exception as e:
        logging.error(f"Error obteniendo estado de cola del módulo {module_id}: {str(e)}")
        return APIRoute.error(
            ErrorCodes.SERVER_ERROR,
            str(e),
            status_code=500
        )


@virtual_bp.route('/module/<module_id>/queue/optimize', methods=['POST'])
@APIRoute.standard(auth_required_flag=True)
def optimize_module_queue(module_id):
    """Optimiza manualmente la cola de temas de un módulo virtual específico."""
    try:
        from src.virtual.services import OptimizedQueueService
        
        data = request.get_json() or {}
        current_progress = data.get('current_progress', 0)
        
        # Verificar que el módulo virtual existe
        virtual_module = get_db().virtual_modules.find_one({"_id": ObjectId(module_id)})
        if not virtual_module:
            return APIRoute.error(
                ErrorCodes.NOT_FOUND,
                "Módulo virtual no encontrado",
                status_code=404
            )
        
        # Verificar permisos
        student_id = virtual_module.get("student_id")
        if str(student_id) != str(request.user_id) and "TEACHER" not in request.user_roles:
            return APIRoute.error(
                ErrorCodes.PERMISSION_DENIED,
                "No tienes permiso para optimizar este módulo",
                status_code=403
            )
        
        queue_service = OptimizedQueueService()
        result = queue_service.maintain_topic_queue(module_id, current_progress)
        
        if "error" in result:
            return APIRoute.error(
                ErrorCodes.OPERATION_FAILED,
                result["error"],
                status_code=400
            )
        
        return APIRoute.success(
            data=result,
            message="Cola optimizada exitosamente"
        )
        
    except Exception as e:
        logging.error(f"Error optimizando cola del módulo {module_id}: {str(e)}")
        return APIRoute.error(
            ErrorCodes.SERVER_ERROR,
            str(e),
            status_code=500
        )


@virtual_bp.route('/admin/queues/bulk-optimize', methods=['POST'])
@APIRoute.standard(auth_required_flag=True, roles=[ROLES["TEACHER"], ROLES["INSTITUTE_ADMIN"]])
def bulk_optimize_all_queues():
    """Optimiza múltiples colas de módulos virtuales en lote (endpoint administrativo)."""
    try:
        from src.virtual.services import OptimizedQueueService
        
        data = request.get_json() or {}
        max_modules = data.get('max_modules', 50)
        
        # Validar límites de seguridad
        if max_modules > 200:
            max_modules = 200
        
        queue_service = OptimizedQueueService()
        result = queue_service.bulk_initialize_queues(max_modules)
        
        if "error" in result:
            return APIRoute.error(
                ErrorCodes.OPERATION_FAILED,
                result["error"],
                status_code=500
            )
        
        return APIRoute.success(
            data=result,
            message=f"Optimización masiva completada: {result.get('processed', 0)} módulos procesados"
        )
        
    except Exception as e:
        logging.error(f"Error en optimización masiva de colas: {str(e)}")
        return APIRoute.error(
            ErrorCodes.SERVER_ERROR,
            str(e),
            status_code=500
        )


@virtual_bp.route('/topic/<topic_id>/trigger-progress', methods=['POST'])
@APIRoute.standard(auth_required_flag=True)
def trigger_topic_progress(topic_id):
    """Trigger manual para actualizar progreso de un tema y mantener la cola."""
    try:
        from src.virtual.services import OptimizedQueueService
        
        data = request.get_json() or {}
        progress_percentage = data.get('progress_percentage', 100)
        
        # Validar progreso
        if not isinstance(progress_percentage, (int, float)) or progress_percentage < 0 or progress_percentage > 100:
            return APIRoute.error(
                ErrorCodes.BAD_REQUEST,
                "El progreso debe ser un número entre 0 y 100",
                status_code=400
            )
        
        # Verificar que el tema virtual existe
        virtual_topic = get_db().virtual_topics.find_one({"_id": ObjectId(topic_id)})
        if not virtual_topic:
            return APIRoute.error(
                ErrorCodes.NOT_FOUND,
                "Tema virtual no encontrado",
                status_code=404
            )
        
        # Verificar permisos
        virtual_module = get_db().virtual_modules.find_one({"_id": virtual_topic["virtual_module_id"]})
        if virtual_module:
            student_id = virtual_module.get("student_id")
            if str(student_id) != str(request.user_id) and "TEACHER" not in request.user_roles:
                return APIRoute.error(
                    ErrorCodes.PERMISSION_DENIED,
                    "No tienes permiso para actualizar este tema",
                    status_code=403
                )
        
        queue_service = OptimizedQueueService()
        result = queue_service.trigger_on_progress(topic_id, progress_percentage)
        
        if "error" in result:
            return APIRoute.error(
                ErrorCodes.OPERATION_FAILED,
                result["error"],
                status_code=400
            )
        
        return APIRoute.success(
            data=result,
            message=f"Trigger ejecutado exitosamente para progreso {progress_percentage}%"
        )
        
    except Exception as e:
        logging.error(f"Error en trigger de progreso del tema {topic_id}: {str(e)}")
        return APIRoute.error(
            ErrorCodes.SERVER_ERROR,
            str(e),
            status_code=500
        )
