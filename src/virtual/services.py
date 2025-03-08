from typing import Tuple, List, Dict, Optional
from bson import ObjectId
from datetime import datetime

from src.shared.database import get_db
from src.shared.constants import STATUS
from src.shared.standardization import BaseService, ErrorCodes
from src.shared.exceptions import AppException
from .models import (
    VirtualModule,
    VirtualTopic,
    VirtualEvaluation,
    VirtualEvaluationResult
)

class VirtualModuleService(BaseService):
    def __init__(self):
        super().__init__(collection_name="virtual_modules")
        self.db = get_db()

    def create_module(self, module_data: dict) -> Tuple[bool, str]:
        try:
            # Verificar que el plan de estudio existe
            study_plan = self.db.study_plans_per_subject.find_one(
                {"_id": ObjectId(module_data['study_plan_id'])}
            )
            if not study_plan:
                return False, "Plan de estudios no encontrado"

            module = VirtualModule(**module_data)
            result = self.collection.insert_one(module.to_dict())
            return True, str(result.inserted_id)
        except Exception as e:
            return False, str(e)

    def get_module_details(self, module_id: str) -> Optional[Dict]:
        try:
            module = self.collection.find_one({"_id": ObjectId(module_id)})
            if not module:
                return None

            # Obtener temas y evaluaciones asociados
            topics = list(self.db.virtual_topics.find(
                {"virtual_module_id": module["_id"]}
            ).sort("order", 1))

            evaluations = list(self.db.virtual_evaluations.find(
                {"virtual_module_id": module["_id"]}
            ))

            # Convertir ObjectIds a strings
            module["_id"] = str(module["_id"])
            module["study_plan_id"] = str(module["study_plan_id"])
            
            # Procesamos los objetos anidados (temas)
            topics_data = []
            for topic in topics:
                topic["_id"] = str(topic["_id"])
                topic["virtual_module_id"] = str(topic["virtual_module_id"])
                topics_data.append(topic)
            
            # Procesamos las evaluaciones
            evaluations_data = []
            for evaluation in evaluations:
                evaluation["_id"] = str(evaluation["_id"])
                evaluation["virtual_module_id"] = str(evaluation["virtual_module_id"])
                evaluations_data.append(evaluation)
            
            # Agregamos los datos procesados a la respuesta
            module["topics"] = topics_data
            module["evaluations"] = evaluations_data
            
            return module
        except Exception as e:
            print(f"Error al obtener detalles del módulo virtual: {str(e)}")
            return None

class VirtualTopicService(BaseService):
    def __init__(self):
        super().__init__(collection_name="virtual_topics")
        self.db = get_db()

    def create_topic(self, topic_data: dict) -> Tuple[bool, str]:
        try:
            # Verificar que el módulo virtual existe
            module = self.db.virtual_modules.find_one(
                {"_id": ObjectId(topic_data['virtual_module_id'])}
            )
            if not module:
                return False, "Módulo virtual no encontrado"

            topic = VirtualTopic(**topic_data)
            result = self.collection.insert_one(topic.to_dict())
            return True, str(result.inserted_id)
        except Exception as e:
            return False, str(e)

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

class VirtualEvaluationService(BaseService):
    def __init__(self):
        super().__init__(collection_name="virtual_evaluations")
        self.db = get_db()

    def create_evaluation(self, evaluation_data: dict) -> Tuple[bool, str]:
        try:
            # Verificar que el módulo virtual existe
            module = self.db.virtual_modules.find_one(
                {"_id": ObjectId(evaluation_data['virtual_module_id'])}
            )
            if not module:
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