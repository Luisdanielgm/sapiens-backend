from datetime import datetime
from typing import Dict, List, Optional, Tuple
from bson import ObjectId
from pymongo import MongoClient
from src.evaluations.models import (
    Evaluation,
    EvaluationSubmission,
    EvaluationResource,
    EvaluationRubric
)
from src.shared.database import get_db
from src.shared.constants import STATUS

class EvaluationService:
    """
    Servicio para gestión completa de evaluaciones flexibles y multi-tema.
    """
    
    def __init__(self):
        self.db = get_db()
        self.evaluations_collection = self.db.evaluations
        self.submissions_collection = self.db.evaluation_submissions
        self.resources_collection = self.db.evaluation_resources
        self.rubrics_collection = self.db.evaluation_rubrics
        self.topics_collection = self.db.topics
        self.content_results_collection = self.db.content_results

    # ==================== CRUD Operations ====================
    
    def create_evaluation(self, evaluation_data: Dict) -> str:
        """
        Crear una nueva evaluación.
        
        Args:
            evaluation_data: Datos de la evaluación
            
        Returns:
            ID de la evaluación creada
        """
        try:
            evaluation = Evaluation(**evaluation_data)
            
            # Validar que los topic_ids existen
            if not self._validate_topic_ids(evaluation.topic_ids):
                raise ValueError("Uno o más topic_ids no son válidos")
            
            # Validar ponderaciones para evaluaciones multi-tema
            if evaluation.is_multi_topic() and not evaluation.validate_weightings():
                raise ValueError("Las ponderaciones deben sumar 1.0 para evaluaciones multi-tema")
            
            result = self.evaluations_collection.insert_one(evaluation.to_dict())
            return str(result.inserted_id)
            
        except Exception as e:
            raise Exception(f"Error al crear evaluación: {str(e)}")
    
    def create_multi_topic_evaluation(self, 
                                    topic_ids: List[str],
                                    title: str,
                                    description: str,
                                    weights: Dict[str, float],
                                    evaluation_type: str = "assignment",
                                    due_date: datetime = None,
                                    criteria: List[Dict] = None) -> str:
        """
        Crear una evaluación multi-tema con ponderaciones específicas.
        
        Args:
            topic_ids: Lista de IDs de temas
            title: Título de la evaluación
            description: Descripción
            weights: Diccionario de ponderaciones por tema {topic_id: weight}
            evaluation_type: Tipo de evaluación
            due_date: Fecha límite
            criteria: Criterios de evaluación
            
        Returns:
            ID de la evaluación creada
        """
        try:
            # Validar que las ponderaciones suman 1.0
            total_weight = sum(weights.values())
            if abs(total_weight - 1.0) > 0.001:
                raise ValueError(f"Las ponderaciones deben sumar 1.0, actual: {total_weight}")
            
            # Validar que todos los topic_ids tienen ponderación
            for topic_id in topic_ids:
                if topic_id not in weights:
                    raise ValueError(f"Falta ponderación para el tema {topic_id}")
            
            evaluation_data = {
                "topic_ids": topic_ids,
                "title": title,
                "description": description,
                "weight": 1.0,  # Peso total de la evaluación
                "criteria": criteria or [],
                "due_date": due_date or datetime.now(),
                "evaluation_type": evaluation_type,
                "weightings": weights,
                "requires_submission": True,
                "status": "active"
            }
            
            return self.create_evaluation(evaluation_data)
            
        except Exception as e:
            raise Exception(f"Error al crear evaluación multi-tema: {str(e)}")
    
    def get_evaluation(self, evaluation_id: str) -> Optional[Dict]:
        """
        Obtener una evaluación por ID.
        """
        try:
            result = self.evaluations_collection.find_one({"_id": ObjectId(evaluation_id)})
            return result
        except Exception as e:
            raise Exception(f"Error al obtener evaluación: {str(e)}")
    
    def update_evaluation(self, evaluation_id: str, update_data: Dict) -> bool:
        """
        Actualizar una evaluación.
        """
        try:
            update_data["updated_at"] = datetime.now()
            result = self.evaluations_collection.update_one(
                {"_id": ObjectId(evaluation_id)},
                {"$set": update_data}
            )
            return result.modified_count > 0
        except Exception as e:
            raise Exception(f"Error al actualizar evaluación: {str(e)}")
    
    def delete_evaluation(self, evaluation_id: str) -> bool:
        """
        Eliminar una evaluación y sus datos relacionados.
        """
        try:
            # Eliminar submissions relacionadas
            self.submissions_collection.delete_many({"evaluation_id": ObjectId(evaluation_id)})
            
            # Eliminar recursos relacionados
            self.resources_collection.delete_many({"evaluation_id": ObjectId(evaluation_id)})
            
            # Eliminar rúbricas relacionadas
            self.rubrics_collection.delete_many({"evaluation_id": ObjectId(evaluation_id)})
            
            # Eliminar la evaluación
            result = self.evaluations_collection.delete_one({"_id": ObjectId(evaluation_id)})
            return result.deleted_count > 0
            
        except Exception as e:
            raise Exception(f"Error al eliminar evaluación: {str(e)}")
    
    # ==================== Submission Management ====================
    
    def create_submission(self, submission_data: Dict) -> str:
        """
        Crear una nueva entrega de estudiante.
        """
        try:
            submission = EvaluationSubmission(**submission_data)
            result = self.submissions_collection.insert_one(submission.to_dict())
            return str(result.inserted_id)
        except Exception as e:
            raise Exception(f"Error al crear entrega: {str(e)}")
    
    def get_student_submissions(self, evaluation_id: str, student_id: str) -> List[Dict]:
        """
        Obtener todas las entregas de un estudiante para una evaluación.
        """
        try:
            submissions = list(self.submissions_collection.find({
                "evaluation_id": ObjectId(evaluation_id),
                "student_id": student_id
            }).sort("created_at", -1))
            return submissions
        except Exception as e:
            raise Exception(f"Error al obtener entregas: {str(e)}")
    
    def grade_submission(self, 
                        submission_id: str, 
                        grade: float, 
                        feedback: str = "",
                        graded_by: str = None,
                        topic_scores: Dict[str, float] = None) -> bool:
        """
        Calificar una entrega de estudiante.
        
        Args:
            submission_id: ID de la entrega
            grade: Calificación final
            feedback: Retroalimentación
            graded_by: ID del evaluador
            topic_scores: Calificaciones por tema para evaluaciones multi-tema
        """
        try:
            update_data = {
                "grade": grade,
                "feedback": feedback,
                "graded_by": ObjectId(graded_by) if graded_by else None,
                "graded_at": datetime.now(),
                "status": "graded",
                "updated_at": datetime.now()
            }
            
            if topic_scores:
                update_data["topic_scores"] = topic_scores
            
            result = self.submissions_collection.update_one(
                {"_id": ObjectId(submission_id)},
                {"$set": update_data}
            )
            return result.modified_count > 0
            
        except Exception as e:
            raise Exception(f"Error al calificar entrega: {str(e)}")
    
    # ==================== Weighted Grading System ====================
    
    def calculate_weighted_grade(self, evaluation_id: str, student_id: str) -> Dict:
        """
        Calcular calificación ponderada para evaluaciones multi-tema.
        
        Args:
            evaluation_id: ID de la evaluación
            student_id: ID del estudiante
            
        Returns:
            Diccionario con el cálculo detallado
        """
        try:
            # Obtener la evaluación
            evaluation_data = self.get_evaluation(evaluation_id)
            if not evaluation_data:
                raise ValueError("Evaluación no encontrada")
            
            evaluation = Evaluation(**evaluation_data)
            
            # Obtener la entrega del estudiante
            submissions = self.get_student_submissions(evaluation_id, student_id)
            if not submissions:
                return {"error": "No se encontraron entregas para este estudiante"}
            
            latest_submission = submissions[0]  # La más reciente
            submission = EvaluationSubmission(**latest_submission)
            
            # Si no es multi-tema, retornar calificación simple
            if not evaluation.is_multi_topic():
                return {
                    "final_grade": submission.grade or 0.0,
                    "is_multi_topic": False,
                    "submission_id": str(submission._id)
                }
            
            # Calcular calificación ponderada
            weighted_grade = submission.calculate_weighted_grade(evaluation)
            
            # Obtener detalles por tema
            topic_details = []
            for topic_id in evaluation.topic_ids:
                topic_id_str = str(topic_id)
                topic_score = submission.topic_scores.get(topic_id_str, 0.0)
                topic_weight = evaluation.get_topic_weight(topic_id_str)
                
                topic_details.append({
                    "topic_id": topic_id_str,
                    "score": topic_score,
                    "weight": topic_weight,
                    "weighted_score": topic_score * topic_weight
                })
            
            return {
                "final_grade": weighted_grade,
                "is_multi_topic": True,
                "topic_details": topic_details,
                "submission_id": str(submission._id),
                "calculation_date": datetime.now()
            }
            
        except Exception as e:
            raise Exception(f"Error al calcular calificación ponderada: {str(e)}")
    
    def update_evaluation_weights(self, evaluation_id: str, new_weights: Dict[str, float]) -> bool:
        """
        Actualizar las ponderaciones de una evaluación multi-tema.
        
        Args:
            evaluation_id: ID de la evaluación
            new_weights: Nuevas ponderaciones {topic_id: weight}
        """
        try:
            # Validar que las ponderaciones suman 1.0
            total_weight = sum(new_weights.values())
            if abs(total_weight - 1.0) > 0.001:
                raise ValueError(f"Las ponderaciones deben sumar 1.0, actual: {total_weight}")
            
            # Actualizar la evaluación
            result = self.update_evaluation(evaluation_id, {
                "weightings": new_weights
            })
            
            # Recalcular todas las calificaciones existentes
            if result:
                self._recalculate_all_grades(evaluation_id)
            
            return result
            
        except Exception as e:
            raise Exception(f"Error al actualizar ponderaciones: {str(e)}")
    
    # ==================== Content Result Integration ====================
    
    def process_content_result_grading(self, evaluation_id: str, student_id: str) -> Dict:
        """
        Procesar calificación basada en resultados de contenido (ContentResult).
        
        Args:
            evaluation_id: ID de la evaluación
            student_id: ID del estudiante
            
        Returns:
            Resultado del procesamiento
        """
        try:
            # Obtener la evaluación
            evaluation_data = self.get_evaluation(evaluation_id)
            if not evaluation_data:
                raise ValueError("Evaluación no encontrada")
            
            evaluation = Evaluation(**evaluation_data)
            
            # Obtener resultados de contenido para los temas de la evaluación
            content_results = list(self.content_results_collection.find({
                "topic_id": {"$in": evaluation.topic_ids},
                "student_id": student_id
            }))
            
            if not content_results:
                return {"error": "No se encontraron resultados de contenido"}
            
            # Calcular calificaciones por tema
            topic_scores = {}
            total_weighted_score = 0.0
            
            for topic_id in evaluation.topic_ids:
                topic_id_str = str(topic_id)
                
                # Buscar resultados para este tema
                topic_results = [r for r in content_results if str(r["topic_id"]) == topic_id_str]
                
                if topic_results:
                    # Calcular promedio de resultados para el tema
                    avg_score = sum(r.get("score", 0) for r in topic_results) / len(topic_results)
                    topic_scores[topic_id_str] = avg_score
                    
                    # Aplicar ponderación si es multi-tema
                    if evaluation.is_multi_topic():
                        weight = evaluation.get_topic_weight(topic_id_str)
                        total_weighted_score += avg_score * weight
                    else:
                        total_weighted_score = avg_score
                else:
                    topic_scores[topic_id_str] = 0.0
            
            # Crear o actualizar entrega automática
            submission_data = {
                "evaluation_id": evaluation_id,
                "student_id": student_id,
                "submission_type": "content_result",
                "grade": total_weighted_score,
                "topic_scores": topic_scores,
                "status": "auto_graded",
                "ai_score": total_weighted_score,
                "ai_feedback": "Calificación automática basada en resultados de contenido",
                "ai_corrected_at": datetime.now()
            }
            
            # Verificar si ya existe una entrega
            existing_submissions = self.get_student_submissions(evaluation_id, student_id)
            
            if existing_submissions:
                # Actualizar la entrega más reciente
                submission_id = str(existing_submissions[0]["_id"])
                self.submissions_collection.update_one(
                    {"_id": ObjectId(submission_id)},
                    {"$set": submission_data}
                )
            else:
                # Crear nueva entrega
                submission_id = self.create_submission(submission_data)
            
            return {
                "success": True,
                "final_grade": total_weighted_score,
                "topic_scores": topic_scores,
                "submission_id": submission_id,
                "content_results_count": len(content_results)
            }
            
        except Exception as e:
            raise Exception(f"Error al procesar calificación de contenido: {str(e)}")
    
    # ==================== Rubric Management ====================
    
    def create_rubric(self, rubric_data: Dict) -> str:
        """
        Crear una nueva rúbrica de evaluación.
        """
        try:
            rubric = EvaluationRubric(**rubric_data)
            
            # Validar criterios
            if not rubric.validate_criteria():
                raise ValueError("Los criterios no suman el total de puntos especificado")
            
            result = self.rubrics_collection.insert_one(rubric.to_dict())
            return str(result.inserted_id)
            
        except Exception as e:
            raise Exception(f"Error al crear rúbrica: {str(e)}")
    
    def grade_with_rubric(self, 
                         submission_id: str, 
                         rubric_id: str, 
                         criteria_scores: Dict[str, float],
                         graded_by: str = None) -> Dict:
        """
        Calificar una entrega usando una rúbrica específica.
        
        Args:
            submission_id: ID de la entrega
            rubric_id: ID de la rúbrica
            criteria_scores: Puntajes por criterio
            graded_by: ID del evaluador
            
        Returns:
            Resultado de la calificación
        """
        try:
            # Obtener la rúbrica
            rubric_data = self.rubrics_collection.find_one({"_id": ObjectId(rubric_id)})
            if not rubric_data:
                raise ValueError("Rúbrica no encontrada")
            
            rubric = EvaluationRubric(**rubric_data)
            
            # Calcular calificación usando la rúbrica
            grade_result = rubric.calculate_grade(criteria_scores)
            
            if "error" in grade_result:
                return grade_result
            
            # Actualizar la entrega
            final_grade = grade_result["final_percentage"]
            feedback = f"Calificación con rúbrica: {grade_result['grade']} ({final_grade}%)\n"
            feedback += f"Puntaje total: {grade_result['total_score']}/{grade_result['max_possible']}"
            
            self.grade_submission(
                submission_id=submission_id,
                grade=final_grade,
                feedback=feedback,
                graded_by=graded_by
            )
            
            return {
                "success": True,
                "grade_result": grade_result,
                "submission_id": submission_id
            }
            
        except Exception as e:
            raise Exception(f"Error al calificar con rúbrica: {str(e)}")
    
    # ==================== Query and Analytics ====================
    
    def get_evaluations_by_topic(self, topic_id: str) -> List[Dict]:
        """
        Obtener todas las evaluaciones que incluyen un tema específico.
        """
        try:
            evaluations = list(self.evaluations_collection.find({
                "topic_ids": ObjectId(topic_id),
                "status": {"$ne": "deleted"}
            }))
            return evaluations
        except Exception as e:
            raise Exception(f"Error al obtener evaluaciones por tema: {str(e)}")
    
    def get_student_evaluation_summary(self, student_id: str, topic_ids: List[str] = None) -> Dict:
        """
        Obtener resumen de evaluaciones para un estudiante.
        
        Args:
            student_id: ID del estudiante
            topic_ids: Lista opcional de temas para filtrar
            
        Returns:
            Resumen de evaluaciones del estudiante
        """
        try:
            # Construir filtro
            eval_filter = {"status": {"$ne": "deleted"}}
            if topic_ids:
                eval_filter["topic_ids"] = {"$in": [ObjectId(tid) for tid in topic_ids]}
            
            # Obtener evaluaciones
            evaluations = list(self.evaluations_collection.find(eval_filter))
            
            summary = {
                "student_id": student_id,
                "total_evaluations": len(evaluations),
                "completed_evaluations": 0,
                "pending_evaluations": 0,
                "average_grade": 0.0,
                "evaluations_detail": []
            }
            
            total_grade = 0.0
            graded_count = 0
            
            for evaluation in evaluations:
                eval_id = str(evaluation["_id"])
                submissions = self.get_student_submissions(eval_id, student_id)
                
                eval_detail = {
                    "evaluation_id": eval_id,
                    "title": evaluation["title"],
                    "due_date": evaluation["due_date"],
                    "has_submission": len(submissions) > 0,
                    "grade": None,
                    "status": "pending"
                }
                
                if submissions:
                    latest_submission = submissions[0]
                    if latest_submission.get("grade") is not None:
                        eval_detail["grade"] = latest_submission["grade"]
                        eval_detail["status"] = "graded"
                        total_grade += latest_submission["grade"]
                        graded_count += 1
                        summary["completed_evaluations"] += 1
                    else:
                        eval_detail["status"] = "submitted"
                        summary["pending_evaluations"] += 1
                else:
                    summary["pending_evaluations"] += 1
                
                summary["evaluations_detail"].append(eval_detail)
            
            # Calcular promedio
            if graded_count > 0:
                summary["average_grade"] = round(total_grade / graded_count, 2)
            
            return summary
            
        except Exception as e:
            raise Exception(f"Error al obtener resumen de evaluaciones: {str(e)}")
    
    # ==================== Helper Methods ====================
    
    def _validate_topic_ids(self, topic_ids: List[ObjectId]) -> bool:
        """
        Validar que todos los topic_ids existen en la base de datos.
        """
        try:
            count = self.topics_collection.count_documents({
                "_id": {"$in": topic_ids}
            })
            return count == len(topic_ids)
        except:
            return False
    
    def _recalculate_all_grades(self, evaluation_id: str):
        """
        Recalcular todas las calificaciones para una evaluación después de cambiar ponderaciones.
        """
        try:
            # Obtener todas las entregas para esta evaluación
            submissions = list(self.submissions_collection.find({
                "evaluation_id": ObjectId(evaluation_id),
                "grade": {"$ne": None}
            }))
            
            # Recalcular cada una
            for submission in submissions:
                student_id = submission["student_id"]
                self.calculate_weighted_grade(evaluation_id, student_id)
                
        except Exception as e:
            print(f"Error al recalcular calificaciones: {str(e)}")


evaluation_service = EvaluationService()
