from typing import Tuple, List, Dict, Optional
from bson import ObjectId
from datetime import datetime
import logging

from src.shared.database import get_db
from src.shared.constants import STATUS, COLLECTIONS
from src.shared.standardization import BaseService, VerificationBaseService
from src.shared.exceptions import AppException
from .models import (
    VirtualModule,
    VirtualTopic,
    Quiz,
    QuizResult
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
                
            # Convertir ObjectId a string y preparar module_id
            module["_id"] = str(module["_id"])
            # Campo module_id siempre presente
            module["module_id"] = str(module.get("module_id"))

            # Manejar study_plan_id faltante (módulos creados antes del parche)
            orig_plan_oid = module.get("study_plan_id")
            if orig_plan_oid:
                module["study_plan_id"] = str(orig_plan_oid)
            else:
                # Obtener study_plan_id desde colección de módulos originales
                orig = self.db.modules.find_one({"_id": ObjectId(module["module_id"])})
                if orig and orig.get("study_plan_id"):
                    module["study_plan_id"] = str(orig.get("study_plan_id"))

            # Manejar description faltante
            if not module.get("description"):
                # Tratamiento para módulos antiguos sin campo description
                orig = orig if 'orig' in locals() else self.db.modules.find_one({"_id": ObjectId(module["module_id"])})
                module["description"] = orig.get("description", "") if orig else ""

            # Obtener información del plan de estudios si existe study_plan_id
            # Obtener información del plan de estudios
            study_plan = None
            if module.get("study_plan_id"):
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
            logging.error(f"Error al obtener detalles del módulo: {str(e)}")
            return None

    def get_student_modules(self, study_plan_id: str, student_id: str) -> List[Dict]:
        """
        Obtiene todos los módulos virtuales de un estudiante para un plan de estudios dado.
        """
        try:
            # Obtener IDs de módulos del plan de estudios
            module_objs = self.db.modules.find({"study_plan_id": ObjectId(study_plan_id)}, {"_id": 1})
            module_ids = [m["_id"] for m in module_objs]
            # Buscar módulos virtuales del estudiante para esos módulos
            vmods = list(self.collection.find({
                "student_id": ObjectId(student_id),
                "module_id": {"$in": module_ids}
            }))
            # Convertir ObjectId a string
            for vm in vmods:
                vm["_id"] = str(vm["_id"])
                vm["module_id"] = str(vm["module_id"])
                vm["student_id"] = str(vm["student_id"])
            return vmods
        except Exception as e:
            logging.error(f"Error al listar módulos virtuales: {str(e)}")
            return []

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

class QuizService(VerificationBaseService):
    """
    Servicio para gestionar quizzes (evaluaciones formativas interactivas).
    """
    def __init__(self):
        super().__init__(collection_name=COLLECTIONS["QUIZZES"])
        self.results_collection = self.db[COLLECTIONS["QUIZ_RESULTS"]]

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
            
    def check_quiz_exists(self, quiz_id: str) -> bool:
        """
        Verifica si un quiz existe.
        
        Args:
            quiz_id: ID del quiz a verificar
            
        Returns:
            bool: True si el quiz existe, False en caso contrario
        """
        try:
            quiz = self.collection.find_one({"_id": ObjectId(quiz_id)})
            return quiz is not None
        except Exception:
            return False
    
    def create_quiz(self, quiz_data: dict) -> Tuple[bool, str]:
        """
        Crea un nuevo quiz para un módulo virtual.
        
        Args:
            quiz_data: Datos del quiz a crear
            
        Returns:
            Tuple[bool, str]: (Éxito, mensaje o ID)
        """
        try:
            # Verificar que el módulo existe
            if not self.check_module_exists(quiz_data.get('virtual_module_id')):
                return False, "Módulo virtual no encontrado"
            
            # Validar estructura básica de preguntas
            questions = quiz_data.get('questions', [])
            if not isinstance(questions, list):
                return False, "El campo 'questions' debe ser una lista."
            for i, q in enumerate(questions):
                if not isinstance(q, dict):
                     return False, f"Cada elemento en 'questions' debe ser un diccionario (índice {i})."
                if not all(k in q for k in ["id", "type", "text", "points"]):
                     return False, f"Pregunta inválida en índice {i}. Faltan campos requeridos ('id', 'type', 'text', 'points')."
                # Add more specific validation per type if needed here
                
            quiz = Quiz(**quiz_data)
            result = self.collection.insert_one(quiz.to_dict())
            return True, str(result.inserted_id)
        except Exception as e:
            return False, str(e)

    def submit_quiz(self, result_data: dict) -> Tuple[bool, str]:
        """
        Registra las respuestas de un estudiante a un quiz y calcula la puntuación.
        """
        try:
            quiz_id = result_data.get('quiz_id')
            # Verificar que el quiz existe
            quiz = self.collection.find_one(
                {"_id": ObjectId(quiz_id)}
            )
            if not quiz:
                return False, "Quiz no encontrado"
            
            # Verificar que el estudiante existe
            student = self.db.users.find_one(
                {"_id": ObjectId(result_data['student_id']), "role": "STUDENT"}
            )
            if not student:
                return False, "Estudiante no encontrado"
                
            # Calcular puntuación
            score = self._calculate_score(quiz, result_data['answers'])
            
            # Crear resultado de quiz
            result_model = QuizResult(
                quiz_id=quiz_id,
                student_id=result_data['student_id'],
                answers=result_data['answers'],
                score=score,
                submission_time=datetime.now()
            )
            
            result_id = self.results_collection.insert_one(result_model.to_dict()).inserted_id
            return True, str(result_id)
        except Exception as e:
            return False, str(e)

    def get_student_results(self, student_id: str, module_id: Optional[str] = None) -> List[Dict]:
        try:
            # Construir la consulta base
            query = {"student_id": ObjectId(student_id)}
            
            # Si se especifica un módulo, filtrar por los quizzes de ese módulo
            quiz_filter = {}
            if module_id:
                # Obtener todos los quizzes del módulo
                quizzes = list(self.collection.find(
                    {"virtual_module_id": ObjectId(module_id)}
                ))
                quiz_ids = [quiz["_id"] for quiz in quizzes]
                
                # Filtrar resultados por esos quizzes
                if quiz_ids:
                    quiz_filter = {"quiz_id": {"$in": quiz_ids}}
                else:
                    # Si no hay quizzes, devolver lista vacía
                    return []
            
            # Combinar filtros
            if quiz_filter:
                query.update(quiz_filter)
                
            # Obtener resultados
            results = list(self.results_collection.find(query))
            
            # Procesar resultados (convertir ObjectId a string, obtener detalles del quiz, etc.)
            processed_results = []
            for result in results:
                result["_id"] = str(result["_id"])
                result["quiz_id"] = str(result["quiz_id"])
                result["student_id"] = str(result["student_id"])
                
                # Obtener detalles del quiz
                quiz = self.collection.find_one({"_id": ObjectId(result["quiz_id"])})
                if quiz:
                    result["quiz_title"] = quiz.get("title", "")
                    result["total_points"] = quiz.get("total_points", 0)
                    result["module_id"] = str(quiz.get("virtual_module_id", ""))
                
                processed_results.append(result)
                
            return processed_results
        except Exception as e:
            print(f"Error al obtener resultados de quizzes del estudiante: {str(e)}")
            return []

    def _calculate_score(self, quiz: Dict, answers: List[Dict]) -> float:
        """Calcula la puntuación de un quiz en base a las respuestas proporcionadas"""
        questions = quiz.get("questions", [])
        max_points = quiz.get("total_points", 100)
        
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
