"""
Servicios para personalización adaptativa basada en modelo RL y estadísticas V-A-K-R
"""

import logging
import json
import requests
from datetime import datetime, timedelta
from typing import Dict, List, Optional, Any, Tuple
from bson import ObjectId

from src.shared.database import get_db
from .models import (
    AdaptiveRecommendation,
    VAKRStatistics,
    RLModelRequest,
    RLModelResponse,
    LearningFeedback
)


class AdaptivePersonalizationService:
    """
    Servicio principal para personalización adaptativa
    """

    def __init__(self):
        self.db = get_db()
        self.rl_api_url = "http://149.50.139.104:8000/api/tools/msp/execute"
        self.content_results_collection = self.db.content_results
        self.cognitive_profiles_collection = self.db.cognitive_profiles
        self.recommendations_collection = self.db.adaptive_recommendations
        self.vakr_stats_collection = self.db.vakr_statistics
        self.feedback_collection = self.db.learning_feedback

    def get_adaptive_recommendations(self, student_id: str, topic_id: str,
                                   context_data: Dict = None) -> Tuple[bool, Dict]:
        """
        Obtiene recomendaciones adaptativas usando el modelo RL

        Args:
            student_id: ID del estudiante
            topic_id: ID del tema actual
            context_data: Datos adicionales de contexto

        Returns:
            Tuple[bool, Dict]: (éxito, datos de recomendación o error)
        """
        try:
            # Validar que student_id sea un ObjectId válido
            try:
                ObjectId(student_id)
            except Exception:
                logging.error(f"student_id inválido: {student_id}")
                return False, {"error": "student_id debe ser un ObjectId válido", "message": f"Valor recibido: {student_id}"}
            
            # Validar que topic_id sea un ObjectId válido
            try:
                ObjectId(topic_id)
            except Exception:
                logging.error(f"topic_id inválido: {topic_id}")
                return False, {"error": "topic_id debe ser un ObjectId válido", "message": f"Valor recibido: {topic_id}"}
            # 1. Preparar datos para el modelo RL
            rl_context = self._prepare_rl_context(student_id, topic_id, context_data or {})

            # 2. Crear solicitud para el modelo RL
            rl_request = RLModelRequest(
                student_id=student_id,
                context_data=rl_context,
                action_type="get_recommendation",
                additional_params={"topic_id": topic_id}
            )

            # 3. Llamar al modelo RL
            rl_response = self._call_rl_model(rl_request)

            if not rl_response.success:
                # Implementar fallback cuando el servicio RL no esté disponible
                logging.warning(f"Servicio RL no disponible, usando fallback: {rl_response.error_message}")
                recommendations = self._generate_fallback_recommendations(student_id, topic_id, rl_context)
                
                return True, {
                    "recommendations": recommendations["content_recommendations"],
                    "learning_path_adjustment": recommendations["learning_path_adjustment"],
                    "confidence_score": recommendations["confidence_score"],
                    "reasoning": recommendations["reasoning"],
                    "fallback_mode": True,
                    "rl_error": rl_response.error_message
                }

            # 4. Procesar recomendaciones del RL
            recommendations = self._process_rl_recommendations(
                student_id, topic_id, rl_response.recommendations
            )

            # 5. Guardar recomendación para auditoría
            recommendation_doc = AdaptiveRecommendation(
                student_id=student_id,
                topic_id=topic_id,
                content_recommendations=recommendations["content_recommendations"],
                learning_path_adjustment=recommendations["learning_path_adjustment"],
                confidence_score=recommendations["confidence_score"],
                reasoning=recommendations["reasoning"],
                rl_model_response=rl_response.raw_response
            )

            self.recommendations_collection.insert_one(recommendation_doc.to_dict())

            return True, {
                "recommendations": recommendations["content_recommendations"],
                "learning_path_adjustment": recommendations["learning_path_adjustment"],
                "confidence_score": recommendations["confidence_score"],
                "reasoning": recommendations["reasoning"],
                "recommendation_id": str(recommendation_doc._id)
            }

        except Exception as e:
            logging.error(f"Error obteniendo recomendaciones adaptativas: {str(e)}")
            return False, {"error": "Error interno del servidor", "message": str(e)}

    def _generate_fallback_recommendations(self, student_id: str, topic_id: str, rl_context: Dict) -> Dict:
        """
        Genera recomendaciones básicas cuando el servicio RL externo no está disponible
        """
        try:
            # Obtener perfil cognitivo del contexto
            cognitive_profile = rl_context.get("student_profile", {})
            recent_interactions = rl_context.get("recent_interactions", [])
            vakr_stats = rl_context.get("vakr_statistics", {})
            
            # Recomendaciones básicas basadas en perfil cognitivo
            content_recommendations = []
            
            # Si hay perfil cognitivo, usar esa información
            if cognitive_profile:
                learning_style = cognitive_profile.get("learning_style", {})
                
                # Recomendaciones basadas en estilo de aprendizaje
                if learning_style.get("visual", 0) > 60:
                    content_recommendations.extend([
                        {
                            "content_type": "diagram",
                            "priority": 1,
                            "reasoning": "Perfil visual dominante",
                            "estimated_effectiveness": 0.8
                        },
                        {
                            "content_type": "image",
                            "priority": 2,
                            "reasoning": "Apoyo visual",
                            "estimated_effectiveness": 0.7
                        }
                    ])
                
                if learning_style.get("auditory", 0) > 60:
                    content_recommendations.append({
                        "content_type": "audio",
                        "priority": 1,
                        "reasoning": "Perfil auditivo dominante",
                        "estimated_effectiveness": 0.8
                    })
                
                if learning_style.get("kinesthetic", 0) > 60:
                    content_recommendations.append({
                        "content_type": "interactive_exercise",
                        "priority": 1,
                        "reasoning": "Perfil kinestésico dominante",
                        "estimated_effectiveness": 0.8
                    })
                
                if learning_style.get("reading_writing", 0) > 60:
                    content_recommendations.append({
                        "content_type": "text",
                        "priority": 1,
                        "reasoning": "Perfil lectura/escritura dominante",
                        "estimated_effectiveness": 0.8
                    })
            
            # Si no hay recomendaciones específicas, usar recomendaciones generales
            if not content_recommendations:
                content_recommendations = [
                    {
                        "content_type": "video",
                        "priority": 1,
                        "reasoning": "Contenido multimedia general",
                        "estimated_effectiveness": 0.6
                    },
                    {
                        "content_type": "text",
                        "priority": 2,
                        "reasoning": "Material de lectura complementario",
                        "estimated_effectiveness": 0.5
                    }
                ]
            
            # Ajustes básicos del plan de aprendizaje
            learning_path_adjustment = {
                "difficulty_adjustment": 0,  # Sin cambios por defecto
                "pace_adjustment": 0,        # Sin cambios por defecto
                "focus_areas": [],           # Sin áreas específicas
                "recommended_duration": 30   # 30 minutos por defecto
            }
            
            # Analizar rendimiento reciente si está disponible
            if recent_interactions:
                avg_score = sum(interaction.get("score", 0) for interaction in recent_interactions) / len(recent_interactions)
                
                if avg_score < 60:
                    learning_path_adjustment["difficulty_adjustment"] = -1
                    learning_path_adjustment["recommended_duration"] = 45
                elif avg_score > 85:
                    learning_path_adjustment["difficulty_adjustment"] = 1
                    learning_path_adjustment["recommended_duration"] = 25
            
            # Confianza baja para fallback
            confidence_score = 0.4
            
            # Explicación del fallback
            reasoning = "Recomendaciones generadas por sistema de fallback debido a indisponibilidad del servicio RL. "
            if cognitive_profile:
                reasoning += "Basadas en perfil cognitivo del estudiante."
            else:
                reasoning += "Recomendaciones generales aplicadas."
            
            return {
                "content_recommendations": content_recommendations,
                "learning_path_adjustment": learning_path_adjustment,
                "confidence_score": confidence_score,
                "reasoning": reasoning
            }
            
        except Exception as e:
            logging.error(f"Error generando recomendaciones de fallback: {str(e)}")
            # Fallback del fallback - recomendaciones mínimas
            return {
                "content_recommendations": [
                    {
                        "content_type": "video",
                        "priority": 1,
                        "reasoning": "Contenido por defecto",
                        "estimated_effectiveness": 0.5
                    }
                ],
                "learning_path_adjustment": {
                    "difficulty_adjustment": 0,
                    "pace_adjustment": 0,
                    "focus_areas": [],
                    "recommended_duration": 30
                },
                "confidence_score": 0.3,
                "reasoning": "Recomendaciones mínimas por error en sistema de fallback"
            }

    def submit_learning_feedback(self, feedback_data: Dict) -> Tuple[bool, str]:
        """
        Envía feedback de aprendizaje al modelo RL

        Args:
            feedback_data: Datos del feedback

        Returns:
            Tuple[bool, str]: (éxito, mensaje)
        """
        try:
            # 1. Crear objeto de feedback
            feedback = LearningFeedback(
                student_id=feedback_data["student_id"],
                content_id=feedback_data["content_id"],
                interaction_type=feedback_data["interaction_type"],
                performance_score=feedback_data["performance_score"],
                engagement_metrics=feedback_data.get("engagement_metrics", {}),
                context_data=feedback_data.get("context_data", {})
            )

            # 2. Guardar feedback localmente
            self.feedback_collection.insert_one(feedback.to_dict())

            # 3. Preparar datos para RL
            rl_request = RLModelRequest(
                student_id=feedback_data["student_id"],
                context_data={
                    "feedback_type": feedback_data["interaction_type"],
                    "performance_score": feedback_data["performance_score"],
                    "engagement_metrics": feedback_data.get("engagement_metrics", {}),
                    "content_id": feedback_data["content_id"]
                },
                action_type="submit_feedback",
                additional_params={"feedback_id": str(feedback._id)}
            )

            # 4. Enviar a modelo RL (sin bloquear la respuesta)
            try:
                self._call_rl_model_async(rl_request)
                logging.info(f"Feedback enviado al modelo RL: {str(feedback._id)}")
            except Exception as e:
                logging.warning(f"Error enviando feedback al RL (continuando): {str(e)}")

            return True, str(feedback._id)

        except Exception as e:
            logging.error(f"Error procesando feedback de aprendizaje: {str(e)}")
            return False, str(e)

    def get_vakr_statistics(self, student_id: str, force_refresh: bool = False) -> Tuple[bool, Dict]:
        """
        Obtiene estadísticas V-A-K-R del estudiante

        Args:
            student_id: ID del estudiante
            force_refresh: Si True, recalcula estadísticas aunque existan recientes

        Returns:
            Tuple[bool, Dict]: (éxito, estadísticas o error)
        """
        try:
            # Validar que student_id sea un ObjectId válido
            try:
                ObjectId(student_id)
            except Exception:
                logging.error(f"student_id inválido en get_vakr_statistics: {student_id}")
                return False, {"error": "student_id debe ser un ObjectId válido", "message": f"Valor recibido: {student_id}"}
            # 1. Buscar estadísticas recientes (últimas 24 horas)
            if not force_refresh:
                recent_stats = self.vakr_stats_collection.find_one({
                    "student_id": ObjectId(student_id),
                    "created_at": {"$gte": datetime.now() - timedelta(hours=24)}
                })

                if recent_stats:
                    return True, recent_stats

            # 2. Calcular estadísticas desde cero
            statistics = self._calculate_vakr_statistics(student_id)

            # 3. Guardar estadísticas
            stats_doc = VAKRStatistics(
                student_id=student_id,
                content_performance=statistics["content_performance"],
                vakr_scores=statistics["vakr_scores"],
                dominant_styles=statistics["dominant_styles"],
                content_type_effectiveness=statistics["content_type_effectiveness"],
                learning_patterns=statistics["learning_patterns"],
                recommendations=statistics["recommendations"]
            )

            self.vakr_stats_collection.insert_one(stats_doc.to_dict())

            return True, stats_doc.to_dict()

        except Exception as e:
            logging.error(f"Error obteniendo estadísticas V-A-K-R: {str(e)}")
            return False, {"error": "Error interno del servidor", "message": str(e)}

    def _prepare_rl_context(self, student_id: str, topic_id: str, context_data: Dict) -> Dict:
        """
        Prepara el contexto para el modelo RL
        """
        try:
            # Obtener perfil cognitivo
            cognitive_profile = self.cognitive_profiles_collection.find_one({
                "user_id": ObjectId(student_id),
                "status": "completed"
            })

            # Obtener historial reciente de interacciones
            recent_interactions = list(self.content_results_collection.find({
                "student_id": ObjectId(student_id),
                "recorded_at": {"$gte": datetime.now() - timedelta(days=7)}
            }).sort("recorded_at", -1).limit(20))

            # Obtener estadísticas V-A-K-R recientes
            vakr_stats = self.vakr_stats_collection.find_one({
                "student_id": ObjectId(student_id)
            }, sort=[("created_at", -1)])

            return {
                "student_profile": cognitive_profile or {},
                "recent_interactions": recent_interactions,
                "vakr_statistics": vakr_stats or {},
                "current_topic": topic_id,
                "context_data": context_data,
                "timestamp": datetime.now().isoformat()
            }

        except Exception as e:
            logging.error(f"Error preparando contexto RL: {str(e)}")
            return {
                "student_profile": {},
                "recent_interactions": [],
                "vakr_statistics": {},
                "current_topic": topic_id,
                "context_data": context_data,
                "timestamp": datetime.now().isoformat()
            }

    def _call_rl_model(self, rl_request: RLModelRequest) -> RLModelResponse:
        """
        Llama al modelo RL externo
        """
        try:
            payload = rl_request.to_rl_payload()

            response = requests.post(
                self.rl_api_url,
                json=payload,
                timeout=10  # 10 segundos timeout
            )

            if response.status_code == 200:
                response_data = response.json()
                return RLModelResponse(
                    success=True,
                    recommendations=response_data.get("recommendations", []),
                    raw_response=response_data
                )
            else:
                return RLModelResponse(
                    success=False,
                    error_message=f"Error HTTP {response.status_code}: {response.text}"
                )

        except requests.exceptions.Timeout:
            return RLModelResponse(
                success=False,
                error_message="Timeout en la comunicación con el modelo RL"
            )
        except requests.exceptions.RequestException as e:
            return RLModelResponse(
                success=False,
                error_message=f"Error de conexión con el modelo RL: {str(e)}"
            )
        except Exception as e:
            return RLModelResponse(
                success=False,
                error_message=f"Error interno en llamada RL: {str(e)}"
            )

    def _call_rl_model_async(self, rl_request: RLModelRequest) -> None:
        """
        Llama al modelo RL de forma asíncrona (sin esperar respuesta)
        """
        import threading

        def async_call():
            try:
                self._call_rl_model(rl_request)
            except Exception as e:
                logging.error(f"Error en llamada RL asíncrona: {str(e)}")

        thread = threading.Thread(target=async_call, daemon=True)
        thread.start()

    def _process_rl_recommendations(self, student_id: str, topic_id: str,
                                   rl_recommendations: List[Dict]) -> Dict:
        """
        Procesa las recomendaciones del modelo RL para adaptarlas al formato del sistema
        """
        try:
            # Adaptar recomendaciones del RL al formato esperado
            content_recommendations = []
            learning_path_adjustment = {}

            for rec in rl_recommendations:
                if rec.get("type") == "content":
                    content_recommendations.append({
                        "content_type": rec.get("content_type"),
                        "priority": rec.get("priority", 1),
                        "reasoning": rec.get("reasoning", ""),
                        "estimated_effectiveness": rec.get("estimated_effectiveness", 0.5)
                    })
                elif rec.get("type") == "learning_path":
                    learning_path_adjustment = rec

            # Calcular confianza basada en consistencia de recomendaciones
            confidence_score = min(1.0, len(content_recommendations) * 0.2)

            # Generar explicación
            reasoning = self._generate_recommendation_reasoning(
                content_recommendations, learning_path_adjustment
            )

            return {
                "content_recommendations": content_recommendations,
                "learning_path_adjustment": learning_path_adjustment,
                "confidence_score": confidence_score,
                "reasoning": reasoning
            }

        except Exception as e:
            logging.error(f"Error procesando recomendaciones RL: {str(e)}")
            return {
                "content_recommendations": [],
                "learning_path_adjustment": {},
                "confidence_score": 0.0,
                "reasoning": "Error procesando recomendaciones del modelo"
            }

    def _calculate_vakr_statistics(self, student_id: str) -> Dict:
        """
        Calcula estadísticas V-A-K-R basadas en el historial del estudiante
        """
        try:
            # Obtener interacciones recientes (últimos 30 días)
            thirty_days_ago = datetime.now() - timedelta(days=30)

            interactions = list(self.content_results_collection.find({
                "student_id": ObjectId(student_id),
                "recorded_at": {"$gte": thirty_days_ago}
            }))

            # Definir mapeo de tipos de contenido a estilos VAKR
            content_to_vakr = {
                "video": {"V": 0.7, "A": 0.3, "K": 0.0, "R": 0.0},
                "diagram": {"V": 0.8, "A": 0.0, "K": 0.0, "R": 0.2},
                "image": {"V": 0.9, "A": 0.0, "K": 0.0, "R": 0.1},
                "text": {"V": 0.1, "A": 0.0, "K": 0.0, "R": 0.9},
                "audio": {"V": 0.0, "A": 0.9, "K": 0.0, "R": 0.1},
                "music": {"V": 0.0, "A": 0.8, "K": 0.2, "R": 0.0},
                "game": {"V": 0.4, "A": 0.1, "K": 0.5, "R": 0.0},
                "simulation": {"V": 0.5, "A": 0.1, "K": 0.4, "R": 0.0},
                "interactive_exercise": {"V": 0.3, "A": 0.1, "K": 0.6, "R": 0.0},
                "quiz": {"V": 0.2, "A": 0.0, "K": 0.1, "R": 0.7}
            }

            # Calcular rendimiento por tipo de contenido
            content_performance = {}
            vakr_totals = {"V": 0, "A": 0, "K": 0, "R": 0}
            vakr_counts = {"V": 0, "A": 0, "K": 0, "R": 0}

            for interaction in interactions:
                content_type = interaction.get("content_type", "unknown")
                score = interaction.get("score", 0)

                if content_type not in content_performance:
                    content_performance[content_type] = {
                        "total_interactions": 0,
                        "total_score": 0,
                        "avg_score": 0,
                        "completion_rate": 0
                    }

                perf = content_performance[content_type]
                perf["total_interactions"] += 1
                perf["total_score"] += score

                # Si el contenido tiene mapeo VAKR, acumular estadísticas
                if content_type in content_to_vakr:
                    vakr_mapping = content_to_vakr[content_type]
                    for style, weight in vakr_mapping.items():
                        if weight > 0:
                            vakr_totals[style] += score * weight
                            vakr_counts[style] += weight

            # Calcular promedios
            for content_type, perf in content_performance.items():
                if perf["total_interactions"] > 0:
                    perf["avg_score"] = perf["total_score"] / perf["total_interactions"]
                    perf["completion_rate"] = sum(1 for i in interactions
                                                if i.get("content_type") == content_type and i.get("score", 0) >= 70) / perf["total_interactions"]

            # Calcular puntajes VAKR normalizados
            vakr_scores = {}
            for style in ["V", "A", "K", "R"]:
                if vakr_counts[style] > 0:
                    vakr_scores[style] = min(1.0, vakr_totals[style] / (vakr_counts[style] * 100))
                else:
                    vakr_scores[style] = 0.25  # Valor por defecto si no hay datos

            # Determinar estilos dominantes
            dominant_styles = sorted(vakr_scores.keys(), key=lambda x: vakr_scores[x], reverse=True)

            # Calcular efectividad por tipo de contenido
            content_type_effectiveness = {}
            for content_type, perf in content_performance.items():
                if perf["total_interactions"] >= 3:  # Solo tipos con suficientes datos
                    content_type_effectiveness[content_type] = perf["avg_score"] / 100.0

            # Identificar patrones de aprendizaje
            learning_patterns = self._identify_learning_patterns(interactions, vakr_scores)

            # Generar recomendaciones
            recommendations = self._generate_vakr_recommendations(
                vakr_scores, dominant_styles, content_performance
            )

            return {
                "content_performance": content_performance,
                "vakr_scores": vakr_scores,
                "dominant_styles": dominant_styles,
                "content_type_effectiveness": content_type_effectiveness,
                "learning_patterns": learning_patterns,
                "recommendations": recommendations
            }

        except Exception as e:
            logging.error(f"Error calculando estadísticas V-A-K-R: {str(e)}")
            return {
                "content_performance": {},
                "vakr_scores": {"V": 0.25, "A": 0.25, "K": 0.25, "R": 0.25},
                "dominant_styles": ["V", "A", "K", "R"],
                "content_type_effectiveness": {},
                "learning_patterns": {},
                "recommendations": ["Se necesitan más datos para generar recomendaciones personalizadas"]
            }

    def _identify_learning_patterns(self, interactions: List[Dict], vakr_scores: Dict) -> Dict:
        """
        Identifica patrones de aprendizaje basados en las interacciones
        """
        try:
            patterns = {
                "best_learning_time": self._identify_best_learning_time(interactions),
                "preferred_content_sequence": self._identify_preferred_sequence(interactions),
                "attention_span": self._calculate_attention_span(interactions),
                "consistency_score": self._calculate_consistency_score(interactions),
                "improvement_trend": self._calculate_improvement_trend(interactions)
            }

            return patterns

        except Exception as e:
            logging.error(f"Error identificando patrones de aprendizaje: {str(e)}")
            return {}

    def _identify_best_learning_time(self, interactions: List[Dict]) -> str:
        """Identifica la mejor hora del día para el aprendizaje"""
        try:
            hour_performance = {}
            for interaction in interactions:
                recorded_at = interaction.get("recorded_at")
                if recorded_at:
                    hour = recorded_at.hour
                    score = interaction.get("score", 0)

                    if hour not in hour_performance:
                        hour_performance[hour] = {"total_score": 0, "count": 0}

                    hour_performance[hour]["total_score"] += score
                    hour_performance[hour]["count"] += 1

            if hour_performance:
                best_hour = max(hour_performance.keys(),
                              key=lambda h: hour_performance[h]["total_score"] / hour_performance[h]["count"])
                return f"{best_hour:02d}:00"

            return "No determinado"

        except Exception:
            return "No determinado"

    def _identify_preferred_sequence(self, interactions: List[Dict]) -> List[str]:
        """Identifica la secuencia preferida de tipos de contenido"""
        try:
            # Análisis simple: tipos de contenido por orden de mejor rendimiento
            type_performance = {}
            for interaction in interactions:
                content_type = interaction.get("content_type", "")
                score = interaction.get("score", 0)

                if content_type not in type_performance:
                    type_performance[content_type] = {"scores": [], "avg": 0}

                type_performance[content_type]["scores"].append(score)

            # Calcular promedios y ordenar
            for content_type, perf in type_performance.items():
                if perf["scores"]:
                    perf["avg"] = sum(perf["scores"]) / len(perf["scores"])

            sorted_types = sorted(type_performance.keys(),
                                key=lambda x: type_performance[x]["avg"], reverse=True)

            return sorted_types[:5]  # Top 5

        except Exception:
            return []

    def _calculate_attention_span(self, interactions: List[Dict]) -> float:
        """Calcula el promedio de tiempo de atención"""
        try:
            durations = []
            for interaction in interactions:
                metrics = interaction.get("metrics", {})
                duration = metrics.get("duration_seconds", 0)
                if duration > 0:
                    durations.append(duration)

            return sum(durations) / len(durations) if durations else 0.0

        except Exception:
            return 0.0

    def _calculate_consistency_score(self, interactions: List[Dict]) -> float:
        """Calcula la consistencia en el rendimiento"""
        try:
            if len(interactions) < 5:
                return 0.5

            scores = [i.get("score", 0) for i in interactions]
            avg_score = sum(scores) / len(scores)
            variance = sum((s - avg_score) ** 2 for s in scores) / len(scores)
            std_dev = variance ** 0.5

            # Convertir a puntaje de consistencia (menor desviación = mayor consistencia)
            consistency = max(0, 1 - (std_dev / 50))  # Normalizar por puntaje máximo

            return consistency

        except Exception:
            return 0.5

    def _calculate_improvement_trend(self, interactions: List[Dict]) -> str:
        """Calcula la tendencia de mejora"""
        try:
            if len(interactions) < 10:
                return "Insuficientes datos"

            # Ordenar por fecha y tomar últimas 10 interacciones
            recent_scores = sorted(interactions, key=lambda x: x.get("recorded_at", datetime.min), reverse=True)[:10]
            recent_scores = [i.get("score", 0) for i in recent_scores]

            # Calcular tendencia simple
            if len(recent_scores) >= 2:
                first_half = sum(recent_scores[:len(recent_scores)//2]) / (len(recent_scores)//2)
                second_half = sum(recent_scores[len(recent_scores)//2:]) / (len(recent_scores) - len(recent_scores)//2)

                if second_half > first_half + 5:
                    return "Mejorando"
                elif first_half > second_half + 5:
                    return "Disminuyendo"
                else:
                    return "Estable"

            return "Estable"

        except Exception:
            return "No determinado"

    def _generate_vakr_recommendations(self, vakr_scores: Dict, dominant_styles: List[str],
                                     content_performance: Dict) -> List[str]:
        """
        Genera recomendaciones basadas en las estadísticas V-A-K-R
        """
        try:
            recommendations = []

            # Recomendación basada en estilo dominante
            primary_style = dominant_styles[0]
            style_recommendations = {
                "V": "Enfatizar contenidos visuales como diagramas, videos e infografías",
                "A": "Incluir más contenidos auditivos como podcasts y narraciones",
                "K": "Priorizar actividades prácticas como simulaciones y ejercicios interactivos",
                "R": "Enfocarse en contenidos textuales y ejercicios de escritura"
            }

            if primary_style in style_recommendations:
                recommendations.append(style_recommendations[primary_style])

            # Recomendaciones basadas en rendimiento
            low_performance_types = [
                content_type for content_type, perf in content_performance.items()
                if perf["total_interactions"] >= 3 and perf["avg_score"] < 60
            ]

            if low_performance_types:
                recommendations.append(f"Considerar reducir el uso de: {', '.join(low_performance_types[:3])}")

            # Recomendaciones de variedad
            total_interactions = sum(perf["total_interactions"] for perf in content_performance.values())
            if total_interactions > 20:
                type_diversity = len([t for t, p in content_performance.items() if p["total_interactions"] > 0])
                if type_diversity < 4:
                    recommendations.append("Aumentar la variedad de tipos de contenido para mejorar el engagement")

            # Recomendaciones de tiempo de sesión
            avg_score = sum(perf["avg_score"] for perf in content_performance.values()) / len(content_performance) if content_performance else 0
            if avg_score > 80:
                recommendations.append("El estudiante muestra excelente rendimiento - mantener la estrategia actual")
            elif avg_score < 60:
                recommendations.append("Considerar sesiones más cortas o contenidos más simples")

            return recommendations[:5]  # Máximo 5 recomendaciones

        except Exception as e:
            logging.error(f"Error generando recomendaciones V-A-K-R: {str(e)}")
            return ["Se necesitan más datos para generar recomendaciones específicas"]

    def _generate_recommendation_reasoning(self, content_recommendations: List[Dict],
                                         learning_path_adjustment: Dict) -> str:
        """
        Genera una explicación de las recomendaciones
        """
        try:
            reasoning_parts = []

            if content_recommendations:
                top_recommendation = content_recommendations[0]
                reasoning_parts.append(f"Se recomienda priorizar contenidos de tipo '{top_recommendation.get('content_type', 'desconocido')}'")

                if top_recommendation.get("reasoning"):
                    reasoning_parts.append(f"porque {top_recommendation['reasoning'].lower()}")

            if learning_path_adjustment:
                adjustment_type = learning_path_adjustment.get("type", "")
                if adjustment_type == "accelerate":
                    reasoning_parts.append("y acelerar el ritmo de aprendizaje")
                elif adjustment_type == "slow_down":
                    reasoning_parts.append("y reducir la velocidad para mejorar la comprensión")

            if reasoning_parts:
                return ". ".join(reasoning_parts) + "."
            else:
                return "Recomendaciones generadas por el sistema de aprendizaje adaptativo."

        except Exception as e:
            logging.error(f"Error generando explicación de recomendaciones: {str(e)}")
            return "Recomendaciones generadas por el sistema de aprendizaje adaptativo."
