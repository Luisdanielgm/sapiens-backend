from typing import Tuple, List, Dict, Optional
from bson import ObjectId
from datetime import datetime

from src.shared.database import get_db
from src.shared.constants import STATUS
from src.shared.standardization import BaseService, VerificationBaseService
from src.shared.exceptions import AppException
from .models import (
    VirtualModule,
    VirtualTopic,
    VirtualEvaluation,
    VirtualEvaluationResult
)

class VirtualModuleService(VerificationBaseService):
    """
    Servicio para gestionar módulos virtuales.
    """
    def __init__(self):
        super().__init__(collection_name="virtual_modules")

    def check_study_plan_exists(self, plan_id: str) -> bool:
        """
        Verifica si un plan de estudios existe
        
        Args:
            plan_id: ID del plan de estudios
            
        Returns:
            bool: True si el plan existe, False en caso contrario
        """
        try:
            study_plan = self.db.study_plans_per_subject.find_one({"_id": ObjectId(plan_id)})
            return study_plan is not None
        except Exception:
            return False

    def create_module(self, module_data: dict) -> Tuple[bool, str]:
        try:
            # Verificar que el plan de estudio existe
            if not self.check_study_plan_exists(module_data['study_plan_id']):
                return False, "Plan de estudios no encontrado"

            module = VirtualModule(**module_data)
            result = self.collection.insert_one(module.to_dict())
            return True, str(result.inserted_id)
        except Exception as e:
            return False, str(e)

    def get_module_details(self, module_id: str) -> Optional[Dict]:
        """
        Obtiene los detalles de un módulo virtual.
        
        Args:
            module_id: ID del módulo a obtener
            
        Returns:
            Dict: Detalles del módulo o None si no existe
        """
        try:
            module = self.collection.find_one({"_id": ObjectId(module_id)})
            if not module:
                return None
                
            # Convertir ObjectId a string
            module["_id"] = str(module["_id"])
            module["study_plan_id"] = str(module["study_plan_id"])
            
            # Obtener información del plan de estudios
            study_plan = self.db.study_plans_per_subject.find_one({"_id": ObjectId(module["study_plan_id"])})
            if study_plan:
                module["study_plan"] = {
                    "name": study_plan.get("name", ""),
                    "subject": study_plan.get("subject", "")
                }
                
            # Obtener temas asociados
            topic_service = VirtualTopicService()
            module["topics"] = topic_service.get_module_topics(module_id)
            
            return module
        except Exception as e:
            print(f"Error al obtener detalles del módulo: {str(e)}")
            return None

class VirtualTopicService(VerificationBaseService):
    """
    Servicio para gestionar temas de módulos virtuales.
    """
    def __init__(self):
        super().__init__(collection_name="virtual_topics")
        
    def create_topic(self, topic_data: dict) -> Tuple[bool, str]:
        """
        Crea un nuevo tema para un módulo virtual.
        
        Args:
            topic_data: Datos del tema a crear
            
        Returns:
            Tuple[bool, str]: (Éxito, mensaje o ID)
        """
        try:
            # Verificar que el módulo existe
            if "virtual_module_id" in topic_data and not self.check_module_exists(topic_data["virtual_module_id"]):
                return False, "Módulo virtual no encontrado"
                
            topic = VirtualTopic(**topic_data)
            result = self.collection.insert_one(topic.to_dict())
            return True, str(result.inserted_id)
        except Exception as e:
            return False, str(e)
            
    def check_module_exists(self, module_id: str) -> bool:
        """
        Verifica si un módulo virtual existe.
        
        Args:
            module_id: ID del módulo a verificar
            
        Returns:
            bool: True si el módulo existe, False en caso contrario
        """
        try:
            module = self.db.virtual_modules.find_one({"_id": ObjectId(module_id)})
            return module is not None
        except Exception:
            return False

    def get_module_topics(self, module_id: str) -> List[Dict]:
        try:
            topics = list(self.collection.find(
                {"virtual_module_id": ObjectId(module_id)}
            ).sort("order", 1))
            
            # Convertir ObjectIds a strings
            for topic in topics:
                topic["_id"] = str(topic["_id"])
                topic["virtual_module_id"] = str(topic["virtual_module_id"])
                
            return topics
        except Exception as e:
            print(f"Error al obtener temas del módulo: {str(e)}")
            return []

class VirtualEvaluationService(VerificationBaseService):
    """
    Servicio para gestionar evaluaciones virtuales.
    """
    def __init__(self):
        super().__init__(collection_name="virtual_evaluations")
        
    def check_module_exists(self, module_id: str) -> bool:
        """
        Verifica si un módulo virtual existe.
        
        Args:
            module_id: ID del módulo a verificar
            
        Returns:
            bool: True si el módulo existe, False en caso contrario
        """
        try:
            module = self.db.virtual_modules.find_one({"_id": ObjectId(module_id)})
            return module is not None
        except Exception:
            return False
            
    def check_evaluation_exists(self, evaluation_id: str) -> bool:
        """
        Verifica si una evaluación existe.
        
        Args:
            evaluation_id: ID de la evaluación a verificar
            
        Returns:
            bool: True si la evaluación existe, False en caso contrario
        """
        try:
            evaluation = self.collection.find_one({"_id": ObjectId(evaluation_id)})
            return evaluation is not None
        except Exception:
            return False
    
    def create_evaluation(self, evaluation_data: dict) -> Tuple[bool, str]:
        """
        Crea una nueva evaluación para un módulo virtual.
        
        Args:
            evaluation_data: Datos de la evaluación a crear
            
        Returns:
            Tuple[bool, str]: (Éxito, mensaje o ID)
        """
        try:
            # Verificar que el módulo existe
            if not self.check_module_exists(evaluation_data['virtual_module_id']):
                return False, "Módulo virtual no encontrado"
                
            evaluation = VirtualEvaluation(**evaluation_data)
            result = self.collection.insert_one(evaluation.to_dict())
            return True, str(result.inserted_id)
        except Exception as e:
            return False, str(e)

    def submit_evaluation(self, result_data: dict) -> Tuple[bool, str]:
        try:
            # Verificar que la evaluación existe
            evaluation = self.collection.find_one(
                {"_id": ObjectId(result_data['virtual_evaluation_id'])}
            )
            if not evaluation:
                return False, "Evaluación no encontrada"
            
            # Verificar que el estudiante existe
            student = self.db.users.find_one(
                {"_id": ObjectId(result_data['student_id']), "role": "STUDENT"}
            )
            if not student:
                return False, "Estudiante no encontrado"
                
            # Calcular puntuación
            score = self._calculate_score(evaluation, result_data['answers'])
            
            # Crear resultado de evaluación
            result = VirtualEvaluationResult(
                virtual_evaluation_id=result_data['virtual_evaluation_id'],
                student_id=result_data['student_id'],
                answers=result_data['answers'],
                score=score,
                submission_time=datetime.now()
            )
            
            result_id = self.db.virtual_evaluation_results.insert_one(result.to_dict()).inserted_id
            return True, str(result_id)
        except Exception as e:
            return False, str(e)

    def get_student_results(self, student_id: str, module_id: Optional[str] = None) -> List[Dict]:
        try:
            # Construir la consulta base
            query = {"student_id": ObjectId(student_id)}
            
            # Si se especifica un módulo, filtrar por las evaluaciones de ese módulo
            evaluation_filter = {}
            if module_id:
                # Obtener todas las evaluaciones del módulo
                evaluations = list(self.collection.find(
                    {"virtual_module_id": ObjectId(module_id)}
                ))
                evaluation_ids = [evaluation["_id"] for evaluation in evaluations]
                
                # Filtrar resultados por esas evaluaciones
                if evaluation_ids:
                    evaluation_filter = {"virtual_evaluation_id": {"$in": evaluation_ids}}
                else:
                    # Si no hay evaluaciones, devolver lista vacía
                    return []
            
            # Combinar filtros
            if evaluation_filter:
                query.update(evaluation_filter)
                
            # Obtener resultados
            results = list(self.db.virtual_evaluation_results.find(query))
            
            # Procesar resultados (convertir ObjectId a string, obtener detalles de evaluación, etc.)
            processed_results = []
            for result in results:
                result["_id"] = str(result["_id"])
                result["virtual_evaluation_id"] = str(result["virtual_evaluation_id"])
                result["student_id"] = str(result["student_id"])
                
                # Obtener detalles de la evaluación
                evaluation = self.collection.find_one({"_id": ObjectId(result["virtual_evaluation_id"])})
                if evaluation:
                    result["evaluation_title"] = evaluation.get("title", "")
                    result["total_points"] = evaluation.get("total_points", 0)
                    result["module_id"] = str(evaluation.get("virtual_module_id", ""))
                
                processed_results.append(result)
                
            return processed_results
        except Exception as e:
            print(f"Error al obtener resultados del estudiante: {str(e)}")
            return []

    def _calculate_score(self, evaluation: Dict, answers: List[Dict]) -> float:
        """Calcula la puntuación de una evaluación en base a las respuestas proporcionadas"""
        questions = evaluation.get("questions", [])
        max_points = evaluation.get("total_points", 100)
        
        # Crear un diccionario para acceder rápidamente a las preguntas por ID
        questions_dict = {str(q.get("question_id", i)): q for i, q in enumerate(questions)}
        
        # Inicializar puntuación
        points_earned = 0
        total_question_points = 0
        
        # Revisar cada respuesta
        for answer in answers:
            question_id = str(answer.get("question_id"))
            if question_id in questions_dict:
                question = questions_dict[question_id]
                question_points = question.get("points", 0)
                total_question_points += question_points
                
                # Comparar respuesta con solución
                if question.get("type") == "multiple_choice":
                    # Para preguntas de opción múltiple
                    if answer.get("selected_option") == question.get("correct_option"):
                        points_earned += question_points
                elif question.get("type") == "true_false":
                    # Para preguntas de verdadero/falso
                    if answer.get("selected_value") == question.get("correct_value"):
                        points_earned += question_points
                elif question.get("type") == "short_answer":
                    # Para preguntas de respuesta corta, podría ser más complejo
                    # Aquí se ejemplifica una comparación simple
                    if answer.get("text", "").lower() == question.get("correct_answer", "").lower():
                        points_earned += question_points
        
        # Calcular puntuación final como porcentaje del total
        if total_question_points > 0:
            final_score = (points_earned / total_question_points) * max_points
        else:
            final_score = 0
            
        return round(final_score, 2) 