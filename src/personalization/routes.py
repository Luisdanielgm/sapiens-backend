"""
Rutas para el sistema de personalización adaptativa
"""

from flask import Blueprint, request
from flask_jwt_extended import get_jwt_identity
import logging

from src.shared.standardization import APIRoute, ErrorCodes
from .services import AdaptivePersonalizationService

personalization_bp = Blueprint('personalization', __name__, url_prefix='/api/personalization')
personalization_service = AdaptivePersonalizationService()


@personalization_bp.route('/adaptive', methods=['POST'])
@APIRoute.standard(auth_required_flag=True, required_fields=['topic_id'])
def get_adaptive_recommendations():
    """
    Obtiene recomendaciones adaptativas para un estudiante basado en el modelo RL.

    Body:
    {
        "topic_id": "ObjectId del tema actual",
        "context_data": {
            "current_progress": 0.5,
            "time_spent": 1200,
            "session_context": "repaso" | "aprendizaje_inicial" | "evaluacion"
        }
    }

    Returns:
    {
        "recommendations": [
            {
                "content_type": "video",
                "priority": 1,
                "reasoning": "Mejor rendimiento histórico",
                "estimated_effectiveness": 0.85
            }
        ],
        "learning_path_adjustment": {
            "type": "accelerate" | "maintain" | "slow_down",
            "new_pace": 1.2,
            "reasoning": "Explicación del ajuste"
        },
        "confidence_score": 0.85,
        "reasoning": "Explicación completa de las recomendaciones",
        "recommendation_id": "ID para seguimiento"
    }
    """
    try:
        user_id = get_jwt_identity()
        data = request.get_json()

        topic_id = data.get('topic_id')
        context_data = data.get('context_data', {})

        # Obtener recomendaciones adaptativas
        success, result = personalization_service.get_adaptive_recommendations(
            student_id=user_id,
            topic_id=topic_id,
            context_data=context_data
        )

        if success:
            logging.info(f"Recomendaciones adaptativas generadas para estudiante {user_id}, tema {topic_id}")
            return APIRoute.success(
                data=result,
                message="Recomendaciones adaptativas generadas exitosamente"
            )
        else:
            logging.warning(f"Error generando recomendaciones adaptativas: {result.get('error', 'Error desconocido')}")
            return APIRoute.error(
                ErrorCodes.SERVER_ERROR,
                result.get('message', 'Error generando recomendaciones adaptativas'),
                status_code=500
            )

    except Exception as e:
        logging.error(f"Error en endpoint de recomendaciones adaptativas: {str(e)}")
        return APIRoute.error(
            ErrorCodes.SERVER_ERROR,
            "Error interno del servidor",
            status_code=500
        )


@personalization_bp.route('/feedback', methods=['POST'])
@APIRoute.standard(auth_required_flag=True, required_fields=['content_id', 'interaction_type', 'performance_score'])
def submit_learning_feedback():
    """
    Envía feedback de aprendizaje al sistema RL para mejorar futuras recomendaciones.

    Body:
    {
        "content_id": "ObjectId del contenido interactuado",
        "interaction_type": "content_view" | "content_complete" | "quiz_attempt" | "exercise_complete",
        "performance_score": 85,  // 0-100
        "engagement_metrics": {
            "time_spent_seconds": 1200,
            "clicks_count": 45,
            "scroll_percentage": 85,
            "completion_rate": 100
        },
        "context_data": {
            "session_type": "learning" | "review" | "assessment",
            "difficulty_level": "easy" | "medium" | "hard",
            "topic_context": "ObjectId del tema"
        }
    }

    Returns:
    {
        "feedback_id": "ID del feedback registrado",
        "message": "Feedback procesado exitosamente"
    }
    """
    try:
        user_id = get_jwt_identity()
        data = request.get_json()

        feedback_data = {
            "student_id": user_id,
            "content_id": data.get('content_id'),
            "interaction_type": data.get('interaction_type'),
            "performance_score": data.get('performance_score'),
            "engagement_metrics": data.get('engagement_metrics', {}),
            "context_data": data.get('context_data', {})
        }

        # Enviar feedback al sistema RL
        success, feedback_id = personalization_service.submit_learning_feedback(feedback_data)

        if success:
            logging.info(f"Feedback de aprendizaje enviado: estudiante {user_id}, contenido {data.get('content_id')}")
            return APIRoute.success(
                data={"feedback_id": feedback_id},
                message="Feedback de aprendizaje procesado exitosamente"
            )
        else:
            logging.warning(f"Error procesando feedback de aprendizaje: {feedback_id}")
            return APIRoute.error(
                ErrorCodes.SERVER_ERROR,
                f"Error procesando feedback: {feedback_id}",
                status_code=500
            )

    except Exception as e:
        logging.error(f"Error en endpoint de feedback de aprendizaje: {str(e)}")
        return APIRoute.error(
            ErrorCodes.SERVER_ERROR,
            "Error interno del servidor",
            status_code=500
        )


@personalization_bp.route('/analytics/vakr/<student_id>', methods=['GET'])
@APIRoute.standard(auth_required_flag=True)
def get_vakr_statistics(student_id):
    """
    Obtiene estadísticas V-A-K-R (Visual, Auditivo, Kinestésico, Lectura/Escritura) del estudiante.

    Query params:
        force_refresh: true/false - Si true, recalcula estadísticas aunque existan recientes

    Returns:
    {
        "content_performance": {
            "video": {
                "total_interactions": 15,
                "avg_score": 82.5,
                "completion_rate": 0.87
            },
            "text": {
                "total_interactions": 23,
                "avg_score": 76.2,
                "completion_rate": 0.91
            }
        },
        "vakr_scores": {
            "V": 0.85,    // Visual
            "A": 0.62,    // Auditivo
            "K": 0.73,    // Kinestésico
            "R": 0.79     // Lectura/Escritura
        },
        "dominant_styles": ["V", "R", "K", "A"],  // Ordenados por preferencia
        "content_type_effectiveness": {
            "video": 0.82,
            "diagram": 0.91,
            "text": 0.76
        },
        "learning_patterns": {
            "best_learning_time": "14:00",
            "preferred_content_sequence": ["text", "video", "quiz", "diagram"],
            "attention_span": 1850.5,  // segundos promedio
            "consistency_score": 0.78,
            "improvement_trend": "Mejorando"
        },
        "recommendations": [
            "Enfatizar contenidos visuales como diagramas, videos e infografías",
            "Aumentar la variedad de tipos de contenido para mejorar el engagement",
            "El estudiante muestra excelente rendimiento - mantener la estrategia actual"
        ]
    }
    """
    try:
        # Verificar permisos (solo el propio estudiante o profesores/administradores pueden ver sus estadísticas)
        current_user_id = get_jwt_identity()

        # TODO: Implementar verificación de permisos más sofisticada
        # Por ahora, solo permitir que el propio estudiante vea sus estadísticas
        if current_user_id != student_id:
            return APIRoute.error(
                ErrorCodes.PERMISSION_DENIED,
                "No tienes permisos para ver las estadísticas de este estudiante",
                status_code=403
            )

        force_refresh = request.args.get('force_refresh', 'false').lower() == 'true'

        # Obtener estadísticas V-A-K-R
        success, result = personalization_service.get_vakr_statistics(
            student_id=student_id,
            force_refresh=force_refresh
        )

        if success:
            logging.info(f"Estadísticas V-A-K-R obtenidas para estudiante {student_id}")
            return APIRoute.success(
                data=result,
                message="Estadísticas V-A-K-R obtenidas exitosamente"
            )
        else:
            logging.warning(f"Error obteniendo estadísticas V-A-K-R: {result.get('error', 'Error desconocido')}")
            return APIRoute.error(
                ErrorCodes.SERVER_ERROR,
                result.get('message', 'Error obteniendo estadísticas V-A-K-R'),
                status_code=500
            )

    except Exception as e:
        logging.error(f"Error en endpoint de estadísticas V-A-K-R: {str(e)}")
        return APIRoute.error(
            ErrorCodes.SERVER_ERROR,
            "Error interno del servidor",
            status_code=500
        )


@personalization_bp.route('/health', methods=['GET'])
@APIRoute.standard(auth_required_flag=False)
def get_personalization_health():
    """Devuelve el estado del servicio de personalización/RL."""
    try:
        health = personalization_service.get_service_health()
        return APIRoute.success(data=health)
    except Exception as e:
        logging.error(f"Error en endpoint de salud de personalización: {str(e)}")
        return APIRoute.error(
            ErrorCodes.SERVER_ERROR,
            "No se pudo obtener el estado de personalización",
            status_code=500
        )


@personalization_bp.route('/statistics/vakr/<student_id>', methods=['GET'])
@APIRoute.standard(auth_required_flag=True)
def get_vakr_statistics_legacy(student_id):
    """
    Endpoint legacy para obtener estadísticas V-A-K-R (redirige a /analytics/vakr)
    """
    from flask import redirect, url_for
    return redirect(url_for('personalization.get_vakr_statistics', student_id=student_id))


@personalization_bp.route('/analytics/compare/<student_id>', methods=['GET'])
@APIRoute.standard(auth_required_flag=True)
def compare_student_analytics(student_id):
    """
    Compara las estadísticas del estudiante con benchmarks o grupos similares.

    Query params:
        comparison_type: "benchmark" | "class_average" | "similar_students"
        class_id: ObjectId de la clase (requerido para class_average)
        subject_filter: filtro por asignatura específica

    Returns:
    {
        "comparison_type": "benchmark",
        "student_stats": {...},
        "benchmark_stats": {...},
        "percentile_ranking": {
            "V": 78,      // Percentil 78 en estilo Visual
            "A": 62,      // Percentil 62 en estilo Auditivo
            "K": 85,      // Percentil 85 en estilo Kinestésico
            "R": 71       // Percentil 71 en estilo Lectura
        },
        "insights": [
            "El estudiante está por encima del promedio en estilos Kinestésicos",
            "Área de oportunidad: mejorar en estilo Auditivo"
        ]
    }
    """
    try:
        current_user_id = get_jwt_identity()
        comparison_type = request.args.get('comparison_type')
        class_id = request.args.get('class_id')
        subject_filter = request.args.get('subject_filter')
        
        # Validar que comparison_type está presente (es query param, no JSON body)
        if not comparison_type:
            return APIRoute.error(
                ErrorCodes.VALIDATION_ERROR,
                "El parámetro 'comparison_type' es requerido",
                status_code=400
            )

        # Verificar permisos
        if current_user_id != student_id:
            return APIRoute.error(
                ErrorCodes.PERMISSION_DENIED,
                "No tienes permisos para comparar las estadísticas de este estudiante",
                status_code=403
            )

        # Obtener estadísticas del estudiante
        success, student_stats = personalization_service.get_vakr_statistics(student_id)
        if not success:
            return APIRoute.error(
                ErrorCodes.NOT_FOUND,
                "No se pudieron obtener las estadísticas del estudiante",
                status_code=404
            )

        comparison_result = {}

        if comparison_type == "benchmark":
            # Comparar con benchmarks generales del sistema
            comparison_result = {
                "comparison_type": "benchmark",
                "student_stats": student_stats,
                "benchmark_stats": {
                    "vakr_scores": {"V": 0.65, "A": 0.58, "K": 0.62, "R": 0.71},
                    "description": "Promedio del sistema educativo"
                },
                "percentile_ranking": _calculate_percentile_ranking(student_stats),
                "insights": _generate_comparison_insights(student_stats, "benchmark")
            }

        elif comparison_type == "class_average":
            if not class_id:
                return APIRoute.error(
                    ErrorCodes.VALIDATION_ERROR,
                    "class_id es requerido para comparación con promedio de clase",
                    status_code=400
                )

            # TODO: Implementar comparación con promedio de clase
            comparison_result = {
                "comparison_type": "class_average",
                "student_stats": student_stats,
                "message": "Comparación con promedio de clase - funcionalidad pendiente"
            }

        elif comparison_type == "similar_students":
            # TODO: Implementar comparación con estudiantes similares
            comparison_result = {
                "comparison_type": "similar_students",
                "student_stats": student_stats,
                "message": "Comparación con estudiantes similares - funcionalidad pendiente"
            }

        else:
            return APIRoute.error(
                ErrorCodes.VALIDATION_ERROR,
                "Tipo de comparación no válido. Use: benchmark, class_average, similar_students",
                status_code=400
            )

        return APIRoute.success(
            data=comparison_result,
            message="Comparación analítica completada exitosamente"
        )

    except Exception as e:
        logging.error(f"Error en comparación analítica: {str(e)}")
        return APIRoute.error(
            ErrorCodes.SERVER_ERROR,
            "Error interno del servidor",
            status_code=500
        )


@personalization_bp.route('/analytics/selection-strategy', methods=['GET'])
@APIRoute.standard(auth_required_flag=True)
def get_selection_strategy_metrics():
    """
    Devuelve métricas agregadas reales de selección (sin mocks) para los dashboards.
    """
    try:
        since_hours = int(request.args.get('since_hours', 168))
        if since_hours <= 0:
            return APIRoute.error(
                ErrorCodes.VALIDATION_ERROR,
                "since_hours debe ser un entero positivo",
                status_code=400
            )
        student_id = request.args.get('student_id') or get_jwt_identity()
        current_user_id = get_jwt_identity()
        if current_user_id != student_id:
            return APIRoute.error(
                ErrorCodes.PERMISSION_DENIED,
                "No tienes permisos para ver las métricas de este estudiante",
                status_code=403
            )
        topic_id = request.args.get('topic_id')

        metrics = personalization_service.get_selection_strategy_metrics(
            student_id=student_id,
            topic_id=topic_id,
            since_hours=since_hours
        )

        return APIRoute.success(data=metrics, message="Métricas de selección obtenidas")
    except ValueError:
        return APIRoute.error(
            ErrorCodes.VALIDATION_ERROR,
            "since_hours debe ser un entero positivo",
            status_code=400
        )
    except Exception as e:
        logging.error(f"Error obteniendo métricas de selección: {str(e)}")
        return APIRoute.error(
            ErrorCodes.SERVER_ERROR,
            "Error interno al calcular métricas",
            status_code=500
        )


@personalization_bp.route('/analytics/recent-interactions', methods=['GET'])
@APIRoute.standard(auth_required_flag=True)
def get_recent_interactions():
    """
    Devuelve interacciones reales recientes para alimentar dashboards sin mocks.
    """
    try:
        since_hours = int(request.args.get('since_hours', 168))
        limit = int(request.args.get('limit', 20))
        if since_hours <= 0 or limit <= 0:
            return APIRoute.error(
                ErrorCodes.VALIDATION_ERROR,
                "limit y since_hours deben ser enteros positivos",
                status_code=400
            )
        limit = min(max(limit, 1), 100)
        student_id = request.args.get('student_id') or get_jwt_identity()
        current_user_id = get_jwt_identity()
        if current_user_id != student_id:
            return APIRoute.error(
                ErrorCodes.PERMISSION_DENIED,
                "No tienes permisos para ver las interacciones de este estudiante",
                status_code=403
            )
        topic_id = request.args.get('topic_id')

        interactions = personalization_service.get_recent_interactions(
            student_id=student_id,
            topic_id=topic_id,
            limit=limit,
            since_hours=since_hours
        )

        return APIRoute.success(
            data={
                "limit": min(max(limit, 1), 100),
                "since_hours": since_hours,
                "interactions": interactions
            },
            message="Interacciones recientes obtenidas"
        )
    except ValueError:
        return APIRoute.error(
            ErrorCodes.VALIDATION_ERROR,
            "limit y since_hours deben ser enteros positivos",
            status_code=400
        )
    except Exception as e:
        logging.error(f"Error obteniendo interacciones recientes: {str(e)}")
        return APIRoute.error(
            ErrorCodes.SERVER_ERROR,
            "Error interno al recuperar interacciones",
            status_code=500
        )


@personalization_bp.route('/analytics/rl-result', methods=['GET'])
@APIRoute.standard(auth_required_flag=True)
def get_rl_result():
    """
    Devuelve la última respuesta completa del modelo RL para auditoría.
    """
    try:
        student_id = request.args.get('student_id') or get_jwt_identity()
        topic_id = request.args.get('topic_id')
        current_user_id = get_jwt_identity()
        if current_user_id != student_id:
            return APIRoute.error(
                ErrorCodes.PERMISSION_DENIED,
                "No tienes permisos para ver los resultados RL de este estudiante",
                status_code=403
            )

        result = personalization_service.get_latest_rl_model_response(student_id, topic_id)
        if not result:
            return APIRoute.error(ErrorCodes.NOT_FOUND, "No se encontraron recomendaciones RL", status_code=404)

        return APIRoute.success(data=result, message="Respuesta RL más reciente")
    except Exception as e:
        logging.error(f"Error recuperando resultado RL: {str(e)}")
        return APIRoute.error(ErrorCodes.SERVER_ERROR, "Error interno al recuperar respuesta RL", status_code=500)


def _calculate_percentile_ranking(student_stats):
    """
    Calcula el ranking percentil del estudiante comparado con benchmarks
    """
    try:
        vakr_scores = student_stats.get("vakr_scores", {})
        benchmark_scores = {"V": 0.65, "A": 0.58, "K": 0.62, "R": 0.71}

        percentiles = {}
        for style in ["V", "A", "K", "R"]:
            student_score = vakr_scores.get(style, 0)
            benchmark_score = benchmark_scores.get(style, 0.5)

            # Cálculo simplificado de percentil (en producción usar distribución real)
            if student_score >= benchmark_score + 0.2:
                percentiles[style] = 85
            elif student_score >= benchmark_score + 0.1:
                percentiles[style] = 70
            elif student_score >= benchmark_score - 0.1:
                percentiles[style] = 55
            elif student_score >= benchmark_score - 0.2:
                percentiles[style] = 35
            else:
                percentiles[style] = 20

        return percentiles

    except Exception as e:
        logging.error(f"Error calculando ranking percentil: {str(e)}")
        return {"V": 50, "A": 50, "K": 50, "R": 50}


def _generate_comparison_insights(student_stats, comparison_type):
    """
    Genera insights basados en la comparación
    """
    try:
        insights = []
        vakr_scores = student_stats.get("vakr_scores", {})
        dominant_styles = student_stats.get("dominant_styles", [])

        # Insights sobre fortalezas
        if len(dominant_styles) >= 2:
            primary, secondary = dominant_styles[:2]
            insights.append(f"El estudiante muestra mayor afinidad por los estilos {primary} y {secondary}")

        # Insights sobre áreas de oportunidad
        low_styles = [style for style, score in vakr_scores.items() if score < 0.5]
        if low_styles:
            insights.append(f"Área de oportunidad: desarrollar estilos {', '.join(low_styles)}")

        # Insights sobre balance
        score_range = max(vakr_scores.values()) - min(vakr_scores.values())
        if score_range > 0.4:
            insights.append("Se recomienda equilibrar los estilos de aprendizaje para mejorar la adaptabilidad")
        elif score_range < 0.2:
            insights.append("Buen balance general en estilos de aprendizaje")

        return insights

    except Exception as e:
        logging.error(f"Error generando insights de comparación: {str(e)}")
        return ["Error generando insights específicos"]
