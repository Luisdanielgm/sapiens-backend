from datetime import datetime
from typing import Dict, List, Optional, Tuple
from bson import ObjectId
from src.shared.database import get_db
from src.shared.constants import STATUS
import logging

logger = logging.getLogger(__name__)

class WeightedGradingService:
    """
    Servicio para el cálculo automático de calificaciones ponderadas
    basado en ContentResults y evaluaciones multi-tema.
    """
    
    def __init__(self):
        self.db = get_db()
        self.evaluations_collection = self.db.evaluations
        self.content_results_collection = self.db.content_results
        self.evaluation_submissions_collection = self.db.evaluation_submissions
        self.topics_collection = self.db.topics
    
    def calculate_weighted_grade_for_student(self, 
                                           evaluation_id: str, 
                                           student_id: str) -> Dict:
        """
        Calcula la calificación ponderada para un estudiante en una evaluación multi-tema.
        
        Args:
            evaluation_id: ID de la evaluación
            student_id: ID del estudiante
            
        Returns:
            Diccionario con el resultado del cálculo
        """
        try:
            # Obtener la evaluación
            evaluation = self.evaluations_collection.find_one({
                "_id": ObjectId(evaluation_id)
            })
            
            if not evaluation:
                return {"error": "Evaluación no encontrada"}
            
            # Verificar que sea una evaluación multi-tema
            if not evaluation.get("topic_ids") or len(evaluation["topic_ids"]) <= 1:
                return {"error": "Esta evaluación no es multi-tema"}
            
            # Obtener pesos de los temas
            topic_weights = evaluation.get("topic_weights", {})
            
            if not topic_weights:
                # Si no hay pesos definidos, usar pesos iguales
                num_topics = len(evaluation["topic_ids"])
                equal_weight = 1.0 / num_topics
                topic_weights = {str(topic_id): equal_weight for topic_id in evaluation["topic_ids"]}
            
            # Validar que los pesos sumen 1.0
            total_weight = sum(topic_weights.values())
            if abs(total_weight - 1.0) > 0.01:  # Tolerancia para errores de punto flotante
                return {"error": f"Los pesos de los temas deben sumar 1.0, actual: {total_weight}"}
            
            # Obtener ContentResults para cada tema
            topic_scores = {}
            detailed_results = []
            
            for topic_id in evaluation["topic_ids"]:
                topic_id_str = str(topic_id)
                
                # Obtener información del tema
                topic = self.topics_collection.find_one({"_id": topic_id})
                topic_name = topic.get("name", f"Tema {topic_id_str}") if topic else f"Tema {topic_id_str}"
                
                # Obtener ContentResults para este tema y estudiante
                content_results = list(self.content_results_collection.find({
                    "topic_id": topic_id,
                    "student_id": student_id,
                    "status": STATUS["ACTIVE"]
                }).sort("created_at", -1))  # Más recientes primero
                
                if content_results:
                    # Usar el resultado más reciente
                    latest_result = content_results[0]
                    topic_score = latest_result.get("score", 0)
                    
                    # Normalizar score a escala 0-100 si es necesario
                    if topic_score > 1.0:
                        # Asumir que ya está en escala 0-100
                        normalized_score = min(topic_score, 100)
                    else:
                        # Convertir de escala 0-1 a 0-100
                        normalized_score = topic_score * 100
                    
                    topic_scores[topic_id_str] = normalized_score
                    
                    detailed_results.append({
                        "topic_id": topic_id_str,
                        "topic_name": topic_name,
                        "score": normalized_score,
                        "weight": topic_weights.get(topic_id_str, 0),
                        "weighted_score": normalized_score * topic_weights.get(topic_id_str, 0),
                        "content_result_id": str(latest_result["_id"]),
                        "last_updated": latest_result.get("created_at")
                    })
                else:
                    # No hay ContentResults para este tema
                    topic_scores[topic_id_str] = 0
                    detailed_results.append({
                        "topic_id": topic_id_str,
                        "topic_name": topic_name,
                        "score": 0,
                        "weight": topic_weights.get(topic_id_str, 0),
                        "weighted_score": 0,
                        "content_result_id": None,
                        "last_updated": None,
                        "note": "Sin resultados de contenido disponibles"
                    })
            
            # Calcular calificación final ponderada
            final_weighted_score = sum(
                topic_scores.get(str(topic_id), 0) * topic_weights.get(str(topic_id), 0)
                for topic_id in evaluation["topic_ids"]
            )
            
            # Preparar resultado
            result = {
                "evaluation_id": evaluation_id,
                "student_id": student_id,
                "final_weighted_score": round(final_weighted_score, 2),
                "topic_scores": topic_scores,
                "topic_weights": topic_weights,
                "detailed_results": detailed_results,
                "calculation_date": datetime.now(),
                "total_topics": len(evaluation["topic_ids"]),
                "topics_with_results": len([r for r in detailed_results if r.get("content_result_id")])
            }
            
            return result
            
        except Exception as e:
            logger.error(f"Error calculando calificación ponderada: {str(e)}")
            return {"error": f"Error interno: {str(e)}"}
    
    def update_evaluation_submission_grade(self, 
                                         evaluation_id: str, 
                                         student_id: str) -> bool:
        """
        Actualiza la calificación de una EvaluationSubmission basada en el cálculo ponderado.
        
        Args:
            evaluation_id: ID de la evaluación
            student_id: ID del estudiante
            
        Returns:
            True si se actualizó exitosamente, False en caso contrario
        """
        try:
            # Calcular calificación ponderada
            weighted_result = self.calculate_weighted_grade_for_student(evaluation_id, student_id)
            
            if "error" in weighted_result:
                logger.error(f"Error en cálculo ponderado: {weighted_result['error']}")
                return False
            
            # Buscar la submission existente
            submission = self.evaluation_submissions_collection.find_one({
                "evaluation_id": ObjectId(evaluation_id),
                "student_id": student_id
            })
            
            if not submission:
                # Crear nueva submission si no existe
                submission_data = {
                    "evaluation_id": ObjectId(evaluation_id),
                    "student_id": student_id,
                    "submission_type": "auto_calculated",
                    "grade": weighted_result["final_weighted_score"],
                    "topic_scores": weighted_result["topic_scores"],
                    "ai_score": weighted_result["final_weighted_score"],
                    "ai_feedback": f"Calificación calculada automáticamente basada en {weighted_result['topics_with_results']} de {weighted_result['total_topics']} temas.",
                    "ai_corrected_at": datetime.now(),
                    "status": "auto_graded",
                    "created_at": datetime.now(),
                    "updated_at": datetime.now()
                }
                
                result = self.evaluation_submissions_collection.insert_one(submission_data)
                logger.info(f"Nueva submission creada con ID: {result.inserted_id}")
            else:
                # Actualizar submission existente
                update_data = {
                    "grade": weighted_result["final_weighted_score"],
                    "topic_scores": weighted_result["topic_scores"],
                    "ai_score": weighted_result["final_weighted_score"],
                    "ai_feedback": f"Calificación actualizada automáticamente basada en {weighted_result['topics_with_results']} de {weighted_result['total_topics']} temas.",
                    "ai_corrected_at": datetime.now(),
                    "updated_at": datetime.now()
                }
                
                self.evaluation_submissions_collection.update_one(
                    {"_id": submission["_id"]},
                    {"$set": update_data}
                )
                logger.info(f"Submission actualizada: {submission['_id']}")
            
            return True
            
        except Exception as e:
            logger.error(f"Error actualizando submission: {str(e)}")
            return False
    
    def recalculate_all_students_for_evaluation(self, evaluation_id: str) -> Dict:
        """
        Recalcula las calificaciones ponderadas para todos los estudiantes de una evaluación.
        
        Args:
            evaluation_id: ID de la evaluación
            
        Returns:
            Diccionario con el resumen del proceso
        """
        try:
            # Obtener todos los estudiantes que tienen ContentResults para los temas de esta evaluación
            evaluation = self.evaluations_collection.find_one({"_id": ObjectId(evaluation_id)})
            
            if not evaluation:
                return {"error": "Evaluación no encontrada"}
            
            # Obtener estudiantes únicos con ContentResults para los temas de la evaluación
            students = self.content_results_collection.distinct(
                "student_id",
                {
                    "topic_id": {"$in": evaluation["topic_ids"]},
                    "status": STATUS["ACTIVE"]
                }
            )
            
            successful_updates = 0
            failed_updates = 0
            results = []
            
            for student_id in students:
                success = self.update_evaluation_submission_grade(evaluation_id, student_id)
                
                if success:
                    successful_updates += 1
                    # Obtener el resultado del cálculo para incluir en el resumen
                    weighted_result = self.calculate_weighted_grade_for_student(evaluation_id, student_id)
                    results.append({
                        "student_id": student_id,
                        "final_score": weighted_result.get("final_weighted_score", 0),
                        "topics_with_results": weighted_result.get("topics_with_results", 0)
                    })
                else:
                    failed_updates += 1
            
            return {
                "evaluation_id": evaluation_id,
                "total_students": len(students),
                "successful_updates": successful_updates,
                "failed_updates": failed_updates,
                "results": results,
                "recalculation_date": datetime.now()
            }
            
        except Exception as e:
            logger.error(f"Error en recálculo masivo: {str(e)}")
            return {"error": f"Error interno: {str(e)}"}
    
    def validate_topic_weights(self, topic_weights: Dict[str, float]) -> Tuple[bool, str]:
        """
        Valida que los pesos de los temas sean correctos.
        
        Args:
            topic_weights: Diccionario con pesos por tema
            
        Returns:
            Tupla (es_válido, mensaje_error)
        """
        try:
            if not topic_weights:
                return False, "Los pesos de los temas no pueden estar vacíos"
            
            # Verificar que todos los pesos sean números positivos
            for topic_id, weight in topic_weights.items():
                if not isinstance(weight, (int, float)):
                    return False, f"El peso para el tema {topic_id} debe ser un número"
                
                if weight < 0:
                    return False, f"El peso para el tema {topic_id} no puede ser negativo"
                
                if weight > 1:
                    return False, f"El peso para el tema {topic_id} no puede ser mayor a 1"
            
            # Verificar que la suma sea aproximadamente 1.0
            total_weight = sum(topic_weights.values())
            if abs(total_weight - 1.0) > 0.01:
                return False, f"Los pesos deben sumar 1.0, suma actual: {total_weight}"
            
            return True, "Pesos válidos"
            
        except Exception as e:
            return False, f"Error validando pesos: {str(e)}"
    
    def get_topic_performance_summary(self, topic_id: str, limit: int = 50) -> Dict:
        """
        Obtiene un resumen del rendimiento de los estudiantes en un tema específico.
        
        Args:
            topic_id: ID del tema
            limit: Número máximo de resultados a incluir
            
        Returns:
            Diccionario con el resumen del rendimiento
        """
        try:
            # Obtener ContentResults para el tema
            content_results = list(self.content_results_collection.find({
                "topic_id": ObjectId(topic_id),
                "status": STATUS["ACTIVE"]
            }).sort("created_at", -1).limit(limit))
            
            if not content_results:
                return {
                    "topic_id": topic_id,
                    "total_students": 0,
                    "average_score": 0,
                    "message": "No hay resultados disponibles para este tema"
                }
            
            # Calcular estadísticas
            scores = [result.get("score", 0) for result in content_results]
            
            # Normalizar scores si es necesario
            normalized_scores = []
            for score in scores:
                if score > 1.0:
                    normalized_scores.append(min(score, 100))
                else:
                    normalized_scores.append(score * 100)
            
            average_score = sum(normalized_scores) / len(normalized_scores)
            max_score = max(normalized_scores)
            min_score = min(normalized_scores)
            
            # Contar estudiantes por rango de calificación
            excellent = len([s for s in normalized_scores if s >= 90])
            good = len([s for s in normalized_scores if 80 <= s < 90])
            satisfactory = len([s for s in normalized_scores if 70 <= s < 80])
            needs_improvement = len([s for s in normalized_scores if s < 70])
            
            return {
                "topic_id": topic_id,
                "total_students": len(content_results),
                "average_score": round(average_score, 2),
                "max_score": round(max_score, 2),
                "min_score": round(min_score, 2),
                "performance_distribution": {
                    "excellent": excellent,  # 90-100
                    "good": good,           # 80-89
                    "satisfactory": satisfactory,  # 70-79
                    "needs_improvement": needs_improvement  # <70
                },
                "last_updated": max(result.get("created_at") for result in content_results) if content_results else None
            }
            
        except Exception as e:
            logger.error(f"Error obteniendo resumen de rendimiento: {str(e)}")
            return {"error": f"Error interno: {str(e)}"}

# Instancia global del servicio
weighted_grading_service = WeightedGradingService()