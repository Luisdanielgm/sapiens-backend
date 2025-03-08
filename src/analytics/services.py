from typing import Tuple, List, Dict, Optional
from bson import ObjectId
from datetime import datetime, timedelta

from src.shared.database import get_db
from src.shared.constants import COLLECTIONS, ROLES
from src.shared.standardization import BaseService, ErrorCodes
from src.shared.exceptions import AppException
from .models import (
    StudentPerformance,
    ClassStatistics,
    EvaluationAnalytics,
    TeacherAnalytics,
    InstituteDashboard
)

class StudentAnalyticsService(BaseService):
    def __init__(self):
        super().__init__(collection_name="analytics_student_performance")
        self.db = get_db()

    def calculate_student_performance(self, student_id: str, class_id: str, period_id: str) -> Optional[Dict]:
        try:
            # Obtener todas las evaluaciones del estudiante
            evaluations = list(self.db.evaluation_results.find({
                "student_id": ObjectId(student_id),
                "class_id": ObjectId(class_id)
            }))

            # Obtener asistencia
            attendance = list(self.db.attendance.find({
                "student_id": ObjectId(student_id),
                "class_id": ObjectId(class_id)
            }))

            # Calcular métricas
            metrics = {
                "attendance_rate": self._calculate_attendance_rate(attendance),
                "avg_score": self._calculate_average_score(evaluations),
                "completion_rate": self._calculate_completion_rate(evaluations)
            }

            # Detalles por evaluación
            details = {
                "evaluations": self._process_evaluation_details(evaluations),
                "attendance": self._process_attendance_details(attendance)
            }

            performance = StudentPerformance(
                student_id=student_id,
                class_id=class_id,
                period_id=period_id,
                metrics=metrics,
                details=details,
                timestamp=datetime.now()
            )

            # Guardar los resultados para referencia futura
            self.collection.update_one(
                {
                    "student_id": ObjectId(student_id),
                    "class_id": ObjectId(class_id),
                    "period_id": ObjectId(period_id)
                },
                {"$set": performance.to_dict()},
                upsert=True
            )

            return performance.to_dict()
        except Exception as e:
            print(f"Error al calcular rendimiento del estudiante: {str(e)}")
            return None

    def _calculate_attendance_rate(self, attendance: List[Dict]) -> float:
        if not attendance:
            return 0.0
        attended = sum(1 for a in attendance if a.get("status") == "present")
        return round(attended / len(attendance) * 100, 2) if len(attendance) > 0 else 0

    def _calculate_average_score(self, evaluations: List[Dict]) -> float:
        if not evaluations:
            return 0.0
        scores = [e.get("score", 0) for e in evaluations if e.get("status") == "completed"]
        return round(sum(scores) / len(scores), 2) if scores else 0

    def _calculate_completion_rate(self, evaluations: List[Dict]) -> float:
        if not evaluations:
            return 0.0
        completed = sum(1 for e in evaluations if e.get("status") == "completed")
        return round(completed / len(evaluations) * 100, 2) if len(evaluations) > 0 else 0

    def _process_evaluation_details(self, evaluations: List[Dict]) -> List[Dict]:
        # Implementar procesamiento de detalles de evaluación
        return [{"id": str(e["_id"]), "title": e.get("title", ""), "score": e.get("score", 0)} 
                for e in evaluations]

    def _process_attendance_details(self, attendance: List[Dict]) -> List[Dict]:
        # Implementar procesamiento de detalles de asistencia
        return [{"date": a.get("date", ""), "status": a.get("status", "")} for a in attendance]

class ClassAnalyticsService(BaseService):
    """
    Servicio para analizar estadísticas y métricas de una clase
    """
    def __init__(self):
        super().__init__(collection_name="analytics_class_statistics")
        self.db = get_db()

    def get_class_analytics(self, class_id: str) -> Optional[Dict]:
        try:
            # Verificar si existe la clase
            class_data = self.db.classes.find_one({"_id": ObjectId(class_id)})
            if not class_data:
                return None

            # Obtener todos los estudiantes de la clase
            students = list(self.db.classroom_members.find({
                "class_id": ObjectId(class_id),
                "role": "student"
            }))
            student_ids = [s["user_id"] for s in students]

            # Si no hay estudiantes, retornar estadísticas vacías
            if not student_ids:
                return ClassStatistics(
                    class_id=class_id,
                    student_count=0,
                    attendance_stats={},
                    evaluation_stats={},
                    participation_stats={},
                    time_trends={},
                    improvement_areas=[],
                    strength_areas=[],
                    timestamp=datetime.now()
                ).to_dict()

            # Obtener todas las evaluaciones
            evaluations = list(self.db.evaluations.find({"class_id": ObjectId(class_id)}))
            evaluation_ids = [e["_id"] for e in evaluations]

            # Obtener resultados de evaluaciones
            evaluation_results = list(self.db.evaluation_results.find({
                "evaluation_id": {"$in": evaluation_ids}
            }))

            # Calcular estadísticas
            attendance_stats = self._calculate_attendance_stats(class_id, student_ids)
            evaluation_stats = self._calculate_evaluation_stats(evaluation_results, evaluations)
            participation_stats = self._calculate_participation_stats(class_id, student_ids)
            time_trends = self._calculate_time_trends(class_id, student_ids)

            # Identificar áreas de mejora y fortalezas
            improvement_areas, strength_areas = self._identify_areas(
                evaluation_stats, attendance_stats, participation_stats
            )

            # Crear y almacenar las estadísticas
            stats = ClassStatistics(
                class_id=class_id,
                student_count=len(student_ids),
                attendance_stats=attendance_stats,
                evaluation_stats=evaluation_stats,
                participation_stats=participation_stats,
                time_trends=time_trends,
                improvement_areas=improvement_areas,
                strength_areas=strength_areas,
                timestamp=datetime.now()
            )

            # Actualizar o insertar en la base de datos
            self.collection.update_one(
                {"class_id": ObjectId(class_id)},
                {"$set": stats.to_dict()},
                upsert=True
            )

            return stats.to_dict()
        except Exception as e:
            print(f"Error al calcular analíticas de clase: {str(e)}")
            return None

    def _calculate_attendance_stats(self, class_id: str, student_ids: List[ObjectId]) -> Dict:
        """
        Calcula estadísticas de asistencia para la clase.
        
        Args:
            class_id: ID de la clase
            student_ids: Lista de IDs de estudiantes
            
        Returns:
            Dict: Estadísticas de asistencia
        """
        try:
            # Obtener registros de asistencia
            attendance_records = list(self.db.attendance.find({
                "class_id": ObjectId(class_id)
            }))
            
            if not attendance_records:
                return {
                    "average_rate": 0,
                    "distribution": {},
                    "trend": []
                }
                
            # Calcular tasa promedio de asistencia
            total_sessions = len(attendance_records)
            total_attendance = sum(len(record.get("present_students", [])) for record in attendance_records)
            total_possible = total_sessions * len(student_ids) if student_ids else 1
            
            average_rate = (total_attendance / total_possible) * 100 if total_possible > 0 else 0
            
            # Calcular distribución de asistencia
            distribution = {}
            for record in attendance_records:
                present_count = len(record.get("present_students", []))
                attendance_rate = (present_count / len(student_ids)) * 100 if student_ids else 0
                range_key = f"{int(attendance_rate // 10) * 10}-{int(attendance_rate // 10) * 10 + 9}"
                
                if range_key in distribution:
                    distribution[range_key] += 1
                else:
                    distribution[range_key] = 1
                    
            # Calcular tendencia temporal
            trend = []
            sorted_records = sorted(attendance_records, key=lambda x: x.get("date", datetime.min))
            
            for record in sorted_records[-10:]:  # Últimas 10 sesiones
                present_count = len(record.get("present_students", []))
                attendance_rate = (present_count / len(student_ids)) * 100 if student_ids else 0
                
                trend.append({
                    "date": record.get("date", datetime.now()),
                    "rate": attendance_rate
                })
                
            return {
                "average_rate": average_rate,
                "distribution": distribution,
                "trend": trend
            }
            
        except Exception as e:
            print(f"Error al calcular estadísticas de asistencia: {str(e)}")
            return {
                "average_rate": 0,
                "distribution": {},
                "trend": []
            }
            
    def _calculate_participation_stats(self, class_id: str, student_ids: List[ObjectId]) -> Dict:
        """
        Calcula estadísticas de participación para la clase.
        
        Args:
            class_id: ID de la clase
            student_ids: Lista de IDs de estudiantes
            
        Returns:
            Dict: Estadísticas de participación
        """
        try:
            # Aquí se implementaría la lógica para calcular la participación
            # basada en interacciones, comentarios, entregas, etc.
            
            # Ejemplo simplificado:
            participation_data = {
                "average_rate": 65.5,  # Porcentaje promedio de participación
                "distribution": {
                    "Alta": 40,  # 40% de estudiantes con alta participación
                    "Media": 35,  # 35% de estudiantes con participación media
                    "Baja": 25    # 25% de estudiantes con baja participación
                },
                "per_activity_type": {
                    "Comentarios": 72.3,
                    "Entregas": 85.1,
                    "Preguntas": 45.8,
                    "Trabajo colaborativo": 58.7
                }
            }
            
            return participation_data
            
        except Exception as e:
            print(f"Error al calcular estadísticas de participación: {str(e)}")
            return {
                "average_rate": 0,
                "distribution": {},
                "per_activity_type": {}
            }
            
    def _calculate_evaluation_stats(self, evaluation_results: List[Dict], evaluations: List[Dict]) -> Dict:
        """
        Calcula estadísticas de evaluaciones para la clase.
        
        Args:
            evaluation_results: Lista de resultados de evaluaciones
            evaluations: Lista de evaluaciones
            
        Returns:
            Dict: Estadísticas de evaluaciones
        """
        try:
            if not evaluation_results or not evaluations:
                return {
                    "average_score": 0,
                    "distribution": {},
                    "per_evaluation": [],
                    "passing_rate": 0
                }
                
            # Calcular promedio general
            total_score = sum(result.get("score", 0) for result in evaluation_results)
            average_score = total_score / len(evaluation_results) if evaluation_results else 0
            
            # Calcular distribución de calificaciones
            distribution = {}
            for result in evaluation_results:
                score = result.get("score", 0)
                range_key = f"{int(score // 10) * 10}-{int(score // 10) * 10 + 9}"
                
                if range_key in distribution:
                    distribution[range_key] += 1
                else:
                    distribution[range_key] = 1
                    
            # Calcular estadísticas por evaluación
            per_evaluation = []
            for evaluation in evaluations:
                eval_id = evaluation["_id"]
                eval_results = [r for r in evaluation_results if r.get("evaluation_id") == eval_id]
                
                if eval_results:
                    eval_avg = sum(r.get("score", 0) for r in eval_results) / len(eval_results)
                    passing_count = sum(1 for r in eval_results if r.get("score", 0) >= 60)  # Umbral de aprobación
                    passing_rate = (passing_count / len(eval_results)) * 100 if eval_results else 0
                    
                    per_evaluation.append({
                        "evaluation_id": str(eval_id),
                        "title": evaluation.get("title", ""),
                        "average_score": eval_avg,
                        "passing_rate": passing_rate,
                        "submission_rate": (len(eval_results) / len(evaluation.get("students", []))) * 100 if evaluation.get("students") else 0
                    })
                    
            # Calcular tasa de aprobación general
            passing_count = sum(1 for r in evaluation_results if r.get("score", 0) >= 60)  # Umbral de aprobación
            passing_rate = (passing_count / len(evaluation_results)) * 100 if evaluation_results else 0
            
            return {
                "average_score": average_score,
                "distribution": distribution,
                "per_evaluation": per_evaluation,
                "passing_rate": passing_rate
            }
            
        except Exception as e:
            print(f"Error al calcular estadísticas de evaluaciones: {str(e)}")
            return {
                "average_score": 0,
                "distribution": {},
                "per_evaluation": [],
                "passing_rate": 0
            }
            
    def _calculate_time_trends(self, class_id: str, student_ids: List[ObjectId]) -> Dict:
        """
        Calcula tendencias temporales para la clase.
        
        Args:
            class_id: ID de la clase
            student_ids: Lista de IDs de estudiantes
            
        Returns:
            Dict: Tendencias temporales
        """
        try:
            # Aquí se implementaría la lógica para calcular tendencias temporales
            # basadas en diferentes métricas a lo largo del tiempo
            
            # Ejemplo simplificado:
            time_trends = {
                "weekly_engagement": [
                    {"week": "2023-W01", "value": 72.5},
                    {"week": "2023-W02", "value": 68.3},
                    {"week": "2023-W03", "value": 75.1},
                    {"week": "2023-W04", "value": 79.4}
                ],
                "monthly_performance": [
                    {"month": "2023-01", "value": 70.2},
                    {"month": "2023-02", "value": 72.8},
                    {"month": "2023-03", "value": 74.5}
                ]
            }
            
            return time_trends
            
        except Exception as e:
            print(f"Error al calcular tendencias temporales: {str(e)}")
            return {
                "weekly_engagement": [],
                "monthly_performance": []
            }
            
    def _identify_areas(self, evaluation_stats: Dict, attendance_stats: Dict, participation_stats: Dict) -> Tuple[List[Dict], List[Dict]]:
        """
        Identifica áreas de mejora y fortalezas basadas en las estadísticas.
        
        Args:
            evaluation_stats: Estadísticas de evaluaciones
            attendance_stats: Estadísticas de asistencia
            participation_stats: Estadísticas de participación
            
        Returns:
            Tuple[List[Dict], List[Dict]]: Áreas de mejora y fortalezas
        """
        improvement_areas = []
        strengths = []
        
        # Análisis de evaluaciones
        avg_score = evaluation_stats.get("average_score", 0)
        if avg_score < 70:
            improvement_areas.append({
                "area": "performance",
                "metric": "average_score",
                "value": avg_score,
                "description": "El promedio general de calificaciones está por debajo del 70%"
            })
        else:
            strengths.append({
                "area": "performance",
                "metric": "average_score",
                "value": avg_score,
                "description": "Buen rendimiento académico general con promedio superior al 70%"
            })
            
        # Análisis de asistencia
        attendance_rate = attendance_stats.get("average_rate", 0)
        if attendance_rate < 80:
            improvement_areas.append({
                "area": "attendance",
                "metric": "average_rate",
                "value": attendance_rate,
                "description": "La asistencia promedio está por debajo del 80%"
            })
        else:
            strengths.append({
                "area": "attendance",
                "metric": "average_rate",
                "value": attendance_rate,
                "description": "Excelente tasa de asistencia superior al 80%"
            })
            
        # Análisis de participación
        participation_rate = participation_stats.get("average_rate", 0)
        if participation_rate < 60:
            improvement_areas.append({
                "area": "participation",
                "metric": "average_rate",
                "value": participation_rate,
                "description": "La participación promedio está por debajo del 60%"
            })
        else:
            strengths.append({
                "area": "participation",
                "metric": "average_rate",
                "value": participation_rate,
                "description": "Buena participación general superior al 60%"
            })
            
        return improvement_areas, strengths

class EvaluationAnalyticsService(BaseService):
    def __init__(self):
        super().__init__(collection_name="analytics_evaluations")
        self.db = get_db()

    def analyze_evaluation(self, evaluation_id: str) -> Optional[Dict]:
        try:
            # Obtener resultados de la evaluación
            results = list(self.db.evaluation_results.find({
                "evaluation_id": ObjectId(evaluation_id)
            }))

            if not results:
                return None

            # Calcular métricas básicas
            metrics = {
                "avg_score": sum(r.get("score", 0) for r in results) / len(results),
                "completion_rate": len([r for r in results if r.get("status") == "completed"]) / len(results),
                "passing_rate": len([r for r in results if r.get("score", 0) >= 60]) / len(results)
            }

            # Analizar estadísticas por pregunta
            question_stats = self._analyze_questions(results)

            # Calcular estadísticas de tiempo
            time_stats = self._calculate_time_stats(results)

            analytics = EvaluationAnalytics(
                evaluation_id=evaluation_id,
                class_id=str(results[0]["class_id"]),
                metrics=metrics,
                question_stats=question_stats,
                time_stats=time_stats
            )

            return analytics.to_dict()
        except Exception as e:
            print(f"Error al analizar evaluación: {str(e)}")
            return None

    def _analyze_questions(self, results: List[Dict]) -> List[Dict]:
        # Implementar análisis detallado por pregunta
        return []

    def _calculate_time_stats(self, results: List[Dict]) -> Dict[str, float]:
        # Implementar cálculos de tiempo
        return {
            "avg_completion_time": 0.0,
            "min_completion_time": 0.0,
            "max_completion_time": 0.0
        }

class InstituteAnalyticsService(BaseService):
    def __init__(self):
        super().__init__(collection_name="analytics_institutes")
        self.db = get_db()
        
    def get_institute_statistics(self, institute_id: str) -> Optional[Dict]:
        """Obtiene estadísticas del instituto"""
        try:
            # Verificar si el instituto existe
            institute = self.db[COLLECTIONS["INSTITUTES"]].find_one({"_id": ObjectId(institute_id)})
            if not institute:
                return None

            # Contar programas activos
            total_programs = self.db[COLLECTIONS["EDUCATIONAL_PROGRAMS"]].count_documents({
                "institute_id": ObjectId(institute_id)
            })

            # Contar miembros por rol
            members = self.db[COLLECTIONS["INSTITUTE_MEMBERS"]].find({"institute_id": ObjectId(institute_id)})
            members_by_role = {}
            for member in members:
                role = member["role"]
                members_by_role[role] = members_by_role.get(role, 0) + 1

            # Obtener períodos académicos
            programs = self.db[COLLECTIONS["EDUCATIONAL_PROGRAMS"]].find({"institute_id": ObjectId(institute_id)})
            program_ids = [program["_id"] for program in programs]
            
            total_periods = self.db[COLLECTIONS["ACADEMIC_PERIODS"]].count_documents({
                "program_id": {"$in": program_ids}
            })

            # Contar usuarios totales
            total_users = members_by_role.get("teacher", 0) + members_by_role.get("institute_admin", 0)
            
            # Obtener clases activas
            total_classes = self.db[COLLECTIONS["CLASSES"]].count_documents({
                "institute_id": ObjectId(institute_id),
                "status": "active"
            })
            
            # Guardar los resultados en la colección de estadísticas
            statistics = {
                "institute_id": ObjectId(institute_id),
                "total_programs": total_programs,
                "total_periods": total_periods,
                "total_users": total_users,
                "total_classes": total_classes,
                "members_by_role": members_by_role,
                "institute_status": institute["status"],
                "generated_at": datetime.now()
            }
            
            # Almacenar para histórico
            self.collection.insert_one(statistics)
            
            # Convertir ObjectId a string para la respuesta
            statistics["institute_id"] = str(statistics["institute_id"])
            
            return statistics
        except Exception as e:
            print(f"Error al obtener estadísticas del instituto: {str(e)}")
            return None
            
    def get_institute_statistics_history(self, institute_id: str, days: int = 30) -> List[Dict]:
        """Obtiene el historial de estadísticas de un instituto"""
        try:
            cutoff_date = datetime.now() - timedelta(days=days)
            
            # Obtener estadísticas históricas
            stats = list(self.collection.find({
                "institute_id": ObjectId(institute_id),
                "generated_at": {"$gte": cutoff_date}
            }).sort("generated_at", -1))
            
            # Convertir ObjectId a string
            for stat in stats:
                stat["institute_id"] = str(stat["institute_id"])
                stat["_id"] = str(stat["_id"])
                
            return stats
        except Exception as e:
            print(f"Error al obtener historial de estadísticas: {str(e)}")
            return []
            
    def get_comparative_statistics(self, institute_ids: List[str]) -> Dict[str, List[Dict]]:
        """Obtiene estadísticas comparativas entre varios institutos"""
        try:
            result = {}
            
            for institute_id in institute_ids:
                stats = self.get_institute_statistics(institute_id)
                if stats:
                    result[institute_id] = stats
                    
            return result
        except Exception as e:
            print(f"Error al obtener estadísticas comparativas: {str(e)}")
            return {}

class StudentSubjectsAnalyticsService(BaseService):
    """
    Servicio para analizar el rendimiento de un estudiante por materias
    """
    def __init__(self):
        super().__init__(collection_name="analytics_student_subjects")
        self.db = get_db()
        
    def get_student_subjects_analytics(self, student_id: str, period_id: Optional[str] = None) -> List[Dict]:
        """
        Obtiene análisis detallados de las materias de un estudiante, opcionalmente filtrado por periodo.
        
        Args:
            student_id: ID del estudiante
            period_id: ID del periodo académico (opcional)
            
        Returns:
            List[Dict]: Lista de análisis por materia
        """
        try:
            if not ObjectId.is_valid(student_id):
                return []
                
            # Verificar que el estudiante existe
            student = self.db.users.find_one({"_id": ObjectId(student_id), "role": "STUDENT"})
            if not student:
                return []
                
            # Obtener todas las clases en las que está inscrito el estudiante
            class_memberships = list(self.db.class_members.find({
                "user_id": ObjectId(student_id),
                "role": "STUDENT"
            }))
            
            if not class_memberships:
                return []
                
            class_ids = [membership["class_id"] for membership in class_memberships]
            
            # Filtro para clases basado en el periodo si se proporciona
            class_filter = {"_id": {"$in": class_ids}}
            if period_id and ObjectId.is_valid(period_id):
                classes_in_period = list(self.db.classes.find({
                    "_id": {"$in": class_ids},
                    "period_id": ObjectId(period_id)
                }))
                class_ids = [class_data["_id"] for class_data in classes_in_period]
                class_filter = {"_id": {"$in": class_ids}}
            
            # Obtener información de las clases
            classes = list(self.db.classes.find(class_filter))
            
            # Procesar cada clase/materia
            subjects_analytics = []
            for class_data in classes:
                # Obtener la materia asociada a la clase
                subject = self.db.subjects.find_one({"_id": class_data.get("subject_id")}) if class_data.get("subject_id") else None
                
                if not subject:
                    continue
                    
                # Obtener evaluaciones de la clase
                evaluations = list(self.db.evaluations.find({
                    "class_id": class_data["_id"]
                }))
                
                evaluation_ids = [evaluation["_id"] for evaluation in evaluations]
                
                # Obtener resultados de evaluaciones del estudiante
                evaluation_results = list(self.db.evaluation_results.find({
                    "evaluation_id": {"$in": evaluation_ids},
                    "student_id": ObjectId(student_id)
                }))
                
                # Calcular métricas de rendimiento
                performance_metrics = self._calculate_performance_metrics(evaluation_results, evaluations)
                
                # Calcular asistencia
                attendance_metrics = self._calculate_attendance_metrics(student_id, class_data["_id"])
                
                # Calcular progreso en el curso
                progress_metrics = self._calculate_progress_metrics(student_id, class_data["_id"], evaluations)
                
                # Crear el análisis para esta materia
                subject_analytics = {
                    "class_id": str(class_data["_id"]),
                    "subject_id": str(subject["_id"]),
                    "subject_name": subject.get("name", ""),
                    "subject_code": subject.get("code", ""),
                    "credits": subject.get("credits", 0),
                    "performance": performance_metrics,
                    "attendance": attendance_metrics,
                    "progress": progress_metrics,
                    "overall_grade": self._calculate_overall_grade(performance_metrics, attendance_metrics, progress_metrics),
                    "compared_to_class_average": self._compare_to_class_average(student_id, class_data["_id"])
                }
                
                subjects_analytics.append(subject_analytics)
                
            return subjects_analytics
            
        except Exception as e:
            print(f"Error al generar analíticas de materias del estudiante: {str(e)}")
            return []
            
    def _calculate_performance_metrics(self, evaluation_results: List[Dict], evaluations: List[Dict]) -> Dict:
        """
        Calcula métricas de rendimiento basadas en los resultados de evaluaciones.
        
        Args:
            evaluation_results: Lista de resultados de evaluaciones
            evaluations: Lista de evaluaciones
            
        Returns:
            Dict: Métricas de rendimiento
        """
        try:
            if not evaluation_results:
                return {
                    "average_score": 0,
                    "highest_score": 0,
                    "lowest_score": 0,
                    "completion_rate": 0,
                    "per_evaluation": []
                }
                
            # Calcular promedio, máximo y mínimo
            scores = [result.get("score", 0) for result in evaluation_results]
            average_score = sum(scores) / len(scores) if scores else 0
            highest_score = max(scores) if scores else 0
            lowest_score = min(scores) if scores else 0
            
            # Calcular tasa de completitud
            total_evaluations = len(evaluations)
            completed_evaluations = len(evaluation_results)
            completion_rate = (completed_evaluations / total_evaluations) * 100 if total_evaluations > 0 else 0
            
            # Detalles por evaluación
            per_evaluation = []
            for evaluation in evaluations:
                eval_id = evaluation["_id"]
                result = next((r for r in evaluation_results if r.get("evaluation_id") == eval_id), None)
                
                per_evaluation.append({
                    "evaluation_id": str(eval_id),
                    "title": evaluation.get("title", ""),
                    "weight": evaluation.get("weight", 0),
                    "score": result.get("score", 0) if result else None,
                    "completed": result is not None,
                    "due_date": evaluation.get("due_date")
                })
                
            return {
                "average_score": average_score,
                "highest_score": highest_score,
                "lowest_score": lowest_score,
                "completion_rate": completion_rate,
                "per_evaluation": per_evaluation
            }
            
        except Exception as e:
            print(f"Error al calcular métricas de rendimiento: {str(e)}")
            return {
                "average_score": 0,
                "highest_score": 0,
                "lowest_score": 0,
                "completion_rate": 0,
                "per_evaluation": []
            }
            
    def _calculate_attendance_metrics(self, student_id: str, class_id: ObjectId) -> Dict:
        """
        Calcula métricas de asistencia para un estudiante en una clase.
        
        Args:
            student_id: ID del estudiante
            class_id: ID de la clase
            
        Returns:
            Dict: Métricas de asistencia
        """
        try:
            # Convertir student_id a ObjectId si es necesario
            student_oid = ObjectId(student_id) if ObjectId.is_valid(student_id) else student_id
            
            # Obtener registros de asistencia de la clase
            attendance_records = list(self.db.attendance.find({
                "class_id": class_id
            }))
            
            if not attendance_records:
                return {
                    "attendance_rate": 0,
                    "attended_sessions": 0,
                    "total_sessions": 0,
                    "trend": []
                }
                
            # Contar sesiones asistidas
            total_sessions = len(attendance_records)
            attended_sessions = sum(1 for record in attendance_records if student_oid in record.get("present_students", []))
            
            # Calcular tasa de asistencia
            attendance_rate = (attended_sessions / total_sessions) * 100 if total_sessions > 0 else 0
            
            # Calcular tendencia
            trend = []
            sorted_records = sorted(attendance_records, key=lambda x: x.get("date", datetime.min))
            
            for record in sorted_records[-10:]:  # Últimas 10 sesiones
                trend.append({
                    "date": record.get("date", datetime.now()),
                    "present": student_oid in record.get("present_students", [])
                })
                
            return {
                "attendance_rate": attendance_rate,
                "attended_sessions": attended_sessions,
                "total_sessions": total_sessions,
                "trend": trend
            }
            
        except Exception as e:
            print(f"Error al calcular métricas de asistencia: {str(e)}")
            return {
                "attendance_rate": 0,
                "attended_sessions": 0,
                "total_sessions": 0,
                "trend": []
            }
            
    def _calculate_progress_metrics(self, student_id: str, class_id: ObjectId, evaluations: List[Dict]) -> Dict:
        """
        Calcula métricas de progreso para un estudiante en una clase.
        
        Args:
            student_id: ID del estudiante
            class_id: ID de la clase
            evaluations: Lista de evaluaciones
            
        Returns:
            Dict: Métricas de progreso
        """
        try:
            # Aquí se implementaría la lógica para calcular el progreso del estudiante
            # basado en tópicos cubiertos, evaluaciones completadas, etc.
            
            # Ejemplo simplificado:
            total_topics = 10
            covered_topics = 7
            
            return {
                "completion_percentage": (covered_topics / total_topics) * 100 if total_topics > 0 else 0,
                "completed_topics": covered_topics,
                "total_topics": total_topics,
                "pending_evaluations": 2,
                "overall_progress": 70.5  # Porcentaje general de progreso
            }
            
        except Exception as e:
            print(f"Error al calcular métricas de progreso: {str(e)}")
            return {
                "completion_percentage": 0,
                "completed_topics": 0,
                "total_topics": 0,
                "pending_evaluations": 0,
                "overall_progress": 0
            }
            
    def _calculate_overall_grade(self, performance_metrics: Dict, attendance_metrics: Dict, progress_metrics: Dict) -> float:
        """
        Calcula la calificación general basada en todas las métricas.
        
        Args:
            performance_metrics: Métricas de rendimiento
            attendance_metrics: Métricas de asistencia
            progress_metrics: Métricas de progreso
            
        Returns:
            float: Calificación general
        """
        try:
            # Aquí se implementaría la lógica para calcular una calificación general
            # ponderando las diferentes métricas
            
            # Ejemplo simplificado:
            performance_weight = 0.7
            attendance_weight = 0.2
            progress_weight = 0.1
            
            performance_score = performance_metrics.get("average_score", 0)
            attendance_score = attendance_metrics.get("attendance_rate", 0)
            progress_score = progress_metrics.get("overall_progress", 0)
            
            overall_grade = (
                performance_score * performance_weight +
                attendance_score * attendance_weight +
                progress_score * progress_weight
            )
            
            return round(overall_grade, 1)
            
        except Exception as e:
            print(f"Error al calcular calificación general: {str(e)}")
            return 0.0
            
    def _compare_to_class_average(self, student_id: str, class_id: ObjectId) -> Dict:
        """
        Compara el rendimiento del estudiante con el promedio de la clase.
        
        Args:
            student_id: ID del estudiante
            class_id: ID de la clase
            
        Returns:
            Dict: Comparativa con el promedio de la clase
        """
        try:
            # Aquí se implementaría la lógica para comparar el rendimiento
            # del estudiante con el promedio de la clase
            
            # Ejemplo simplificado:
            return {
                "performance_difference": 5.2,  # Puntos porcentuales por encima del promedio
                "attendance_difference": -2.1,  # Puntos porcentuales por debajo del promedio
                "overall_difference": 3.5,      # Diferencia general
                "percentile": 75                # Percentil del estudiante en la clase
            }
            
        except Exception as e:
            print(f"Error al comparar con el promedio de la clase: {str(e)}")
            return {
                "performance_difference": 0,
                "attendance_difference": 0,
                "overall_difference": 0,
                "percentile": 0
            }

class InstituteDashboardService(BaseService):
    def __init__(self):
        super().__init__(collection_name="institute_dashboards")
        self.db = get_db()

    def generate_institute_dashboard(self, institute_id: str) -> Optional[Dict]:
        """Genera un dashboard completo para un instituto con todas sus métricas clave"""
        try:
            # Verificar si el instituto existe
            institute = self.db.institutes.find_one({"_id": ObjectId(institute_id)})
            if not institute:
                return None

            # Obtener datos básicos del instituto
            overview_metrics = self._get_overview_metrics(institute_id)
            
            # Obtener estadísticas de programas educativos
            programs_stats = self._get_programs_stats(institute_id)
            
            # Obtener estadísticas de niveles educativos
            levels_stats = self._get_levels_stats(institute_id)
            
            # Obtener estadísticas de secciones
            sections_stats = self._get_sections_stats(institute_id)
            
            # Obtener estadísticas de materias
            subjects_stats = self._get_subjects_stats(institute_id)
            
            # Obtener estadísticas de períodos académicos
            periods_stats = self._get_periods_stats(institute_id)
            
            # Obtener estadísticas de clases
            classes_stats = self._get_classes_stats(institute_id)
            
            # Obtener estadísticas de profesores
            teachers_stats = self._get_teachers_stats(institute_id)
            
            # Obtener estadísticas de estudiantes
            students_stats = self._get_students_stats(institute_id)
            
            # Crear el modelo de dashboard
            dashboard = InstituteDashboard(
                institute_id=institute_id,
                overview_metrics=overview_metrics,
                programs_stats=programs_stats,
                levels_stats=levels_stats,
                sections_stats=sections_stats,
                subjects_stats=subjects_stats,
                periods_stats=periods_stats,
                classes_stats=classes_stats,
                teachers_stats=teachers_stats,
                students_stats=students_stats
            )
            
            # Guardar el dashboard en la base de datos para futuras consultas
            self.collection.update_one(
                {"institute_id": ObjectId(institute_id)},
                {"$set": dashboard.to_dict()},
                upsert=True
            )
            
            return dashboard.to_dict()
            
        except Exception as e:
            print(f"Error al generar dashboard del instituto: {str(e)}")
            return None
    
    def _get_overview_metrics(self, institute_id: str) -> Dict[str, int]:
        """Obtiene métricas generales del instituto"""
        try:
            # Contar programas educativos
            total_programs = self.db.educational_programs.count_documents({
                "institute_id": ObjectId(institute_id)
            })
            
            # Contar niveles educativos
            programs = list(self.db.educational_programs.find({"institute_id": ObjectId(institute_id)}))
            program_ids = [p["_id"] for p in programs]
            
            total_levels = self.db.levels.count_documents({
                "program_id": {"$in": program_ids}
            })
            
            # Contar secciones
            levels = list(self.db.levels.find({"program_id": {"$in": program_ids}}))
            level_ids = [l["_id"] for l in levels]
            
            total_sections = self.db.sections.count_documents({
                "level_id": {"$in": level_ids}
            })
            
            # Contar materias
            total_subjects = self.db.subjects.count_documents({
                "level_id": {"$in": level_ids}
            })
            
            # Contar períodos académicos
            total_periods = self.db.academic_periods.count_documents({
                "level_id": {"$in": level_ids}
            })
            
            # Contar clases
            total_classes = self.db.classes.count_documents({
                "level_id": {"$in": level_ids}
            })
            
            # Contar miembros (profesores y estudiantes)
            institute_members = list(self.db.institute_members.find({
                "institute_id": ObjectId(institute_id)
            }))
            
            total_teachers = sum(1 for m in institute_members if m.get("role") == "teacher")
            total_admins = sum(1 for m in institute_members if m.get("role") == "institute_admin")
            
            # Contar estudiantes (estudiantes matriculados en clases)
            class_ids = [c["_id"] for c in self.db.classes.find({"level_id": {"$in": level_ids}})]
            
            class_members = list(self.db.class_members.find({
                "class_id": {"$in": class_ids},
                "role": "student"
            }))
            
            # Obtener IDs únicos de estudiantes
            student_ids = set(str(m["user_id"]) for m in class_members)
            total_students = len(student_ids)
            
            # Obtener métricas de actividad
            active_classes = self.db.classes.count_documents({
                "level_id": {"$in": level_ids},
                "status": "active"
            })
            
            return {
                "total_programs": total_programs,
                "total_levels": total_levels,
                "total_sections": total_sections,
                "total_subjects": total_subjects,
                "total_periods": total_periods,
                "total_classes": total_classes,
                "active_classes": active_classes,
                "total_teachers": total_teachers,
                "total_admins": total_admins,
                "total_students": total_students
            }
            
        except Exception as e:
            print(f"Error al obtener métricas generales: {str(e)}")
            return {}
    
    def _get_programs_stats(self, institute_id: str) -> List[Dict]:
        """Obtiene estadísticas de programas educativos"""
        try:
            programs = list(self.db.educational_programs.find({
                "institute_id": ObjectId(institute_id)
            }))
            
            result = []
            for program in programs:
                program_id = program["_id"]
                
                # Contar niveles por programa
                levels_count = self.db.levels.count_documents({
                    "program_id": program_id
                })
                
                # Contar estudiantes por programa (a través de niveles y clases)
                levels = list(self.db.levels.find({"program_id": program_id}))
                level_ids = [l["_id"] for l in levels]
                
                classes = list(self.db.classes.find({"level_id": {"$in": level_ids}}))
                class_ids = [c["_id"] for c in classes]
                
                student_members = list(self.db.class_members.find({
                    "class_id": {"$in": class_ids},
                    "role": "student"
                }))
                
                unique_students = set(str(m["user_id"]) for m in student_members)
                
                program_stats = {
                    "program_id": str(program_id),
                    "name": program.get("name", ""),
                    "levels_count": levels_count,
                    "students_count": len(unique_students),
                    "active": program.get("status") == "active"
                }
                
                result.append(program_stats)
                
            return result
            
        except Exception as e:
            print(f"Error al obtener estadísticas de programas: {str(e)}")
            return []
    
    def _get_levels_stats(self, institute_id: str) -> List[Dict]:
        """Obtiene estadísticas de niveles educativos"""
        try:
            # Obtener todos los programas del instituto
            programs = list(self.db.educational_programs.find({
                "institute_id": ObjectId(institute_id)
            }))
            
            program_ids = [p["_id"] for p in programs]
            
            # Obtener todos los niveles de esos programas
            levels = list(self.db.levels.find({
                "program_id": {"$in": program_ids}
            }))
            
            result = []
            for level in levels:
                level_id = level["_id"]
                
                # Obtener conteo de secciones, materias y períodos
                sections_count = self.db.sections.count_documents({
                    "level_id": level_id
                })
                
                subjects_count = self.db.subjects.count_documents({
                    "level_id": level_id
                })
                
                periods_count = self.db.academic_periods.count_documents({
                    "level_id": level_id
                })
                
                # Obtener clases y estudiantes
                classes = list(self.db.classes.find({"level_id": level_id}))
                class_ids = [c["_id"] for c in classes]
                
                classes_count = len(classes)
                
                student_members = list(self.db.class_members.find({
                    "class_id": {"$in": class_ids},
                    "role": "student"
                }))
                
                unique_students = set(str(m["user_id"]) for m in student_members)
                
                # Encontrar el nombre del programa
                program = next((p for p in programs if p["_id"] == level.get("program_id")), {})
                
                level_stats = {
                    "level_id": str(level_id),
                    "name": level.get("name", ""),
                    "program_id": str(level.get("program_id", "")),
                    "program_name": program.get("name", ""),
                    "sections_count": sections_count,
                    "subjects_count": subjects_count,
                    "periods_count": periods_count,
                    "classes_count": classes_count,
                    "students_count": len(unique_students)
                }
                
                result.append(level_stats)
                
            return result
            
        except Exception as e:
            print(f"Error al obtener estadísticas de niveles: {str(e)}")
            return []
    
    def _get_sections_stats(self, institute_id: str) -> Dict[str, any]:
        """Obtiene estadísticas de secciones"""
        try:
            # Obtener todos los programas y niveles del instituto
            programs = list(self.db.educational_programs.find({
                "institute_id": ObjectId(institute_id)
            }))
            
            program_ids = [p["_id"] for p in programs]
            
            levels = list(self.db.levels.find({
                "program_id": {"$in": program_ids}
            }))
            
            level_ids = [l["_id"] for l in levels]
            
            # Obtener todas las secciones
            sections = list(self.db.sections.find({
                "level_id": {"$in": level_ids}
            }))
            
            # Estadísticas generales
            total_sections = len(sections)
            
            # Calcular capacidad promedio
            avg_capacity = 0
            if total_sections > 0:
                avg_capacity = sum(s.get("capacity", 0) for s in sections) / total_sections
            
            # Secciones por nivel
            sections_by_level = {}
            for level in levels:
                level_id = str(level["_id"])
                sections_by_level[level_id] = sum(1 for s in sections if str(s.get("level_id")) == level_id)
            
            # Calcular clases por sección
            section_ids = [s["_id"] for s in sections]
            
            classes_by_section = {}
            for section_id in section_ids:
                classes_count = self.db.classes.count_documents({
                    "section_id": section_id
                })
                classes_by_section[str(section_id)] = classes_count
            
            return {
                "total_sections": total_sections,
                "avg_capacity": avg_capacity,
                "sections_by_level": sections_by_level,
                "classes_by_section": classes_by_section
            }
            
        except Exception as e:
            print(f"Error al obtener estadísticas de secciones: {str(e)}")
            return {}
    
    def _get_subjects_stats(self, institute_id: str) -> Dict[str, any]:
        """Obtiene estadísticas de materias"""
        try:
            # Obtener todos los programas y niveles del instituto
            programs = list(self.db.educational_programs.find({
                "institute_id": ObjectId(institute_id)
            }))
            
            program_ids = [p["_id"] for p in programs]
            
            levels = list(self.db.levels.find({
                "program_id": {"$in": program_ids}
            }))
            
            level_ids = [l["_id"] for l in levels]
            
            # Obtener todas las materias
            subjects = list(self.db.subjects.find({
                "level_id": {"$in": level_ids}
            }))
            
            # Estadísticas generales
            total_subjects = len(subjects)
            
            # Materias por nivel
            subjects_by_level = {}
            for level in levels:
                level_id = str(level["_id"])
                subjects_by_level[level_id] = sum(1 for s in subjects if str(s.get("level_id")) == level_id)
            
            # Promedio de créditos por materia
            avg_credits = 0
            if total_subjects > 0:
                avg_credits = sum(s.get("credits", 0) for s in subjects) / total_subjects
            
            # Materias obligatorias vs opcionales
            required_subjects = sum(1 for s in subjects if s.get("required", True) is True)
            optional_subjects = total_subjects - required_subjects
            
            # Calcular clases por materia
            subject_ids = [s["_id"] for s in subjects]
            
            classes_by_subject = {}
            for subject_id in subject_ids:
                classes_count = self.db.classes.count_documents({
                    "subject_id": subject_id
                })
                classes_by_subject[str(subject_id)] = classes_count
            
            return {
                "total_subjects": total_subjects,
                "subjects_by_level": subjects_by_level,
                "avg_credits": avg_credits,
                "required_subjects": required_subjects,
                "optional_subjects": optional_subjects,
                "classes_by_subject": classes_by_subject
            }
            
        except Exception as e:
            print(f"Error al obtener estadísticas de materias: {str(e)}")
            return {}
    
    def _get_periods_stats(self, institute_id: str) -> Dict[str, any]:
        """Obtiene estadísticas de períodos académicos"""
        try:
            # Obtener todos los programas y niveles del instituto
            programs = list(self.db.educational_programs.find({
                "institute_id": ObjectId(institute_id)
            }))
            
            program_ids = [p["_id"] for p in programs]
            
            levels = list(self.db.levels.find({
                "program_id": {"$in": program_ids}
            }))
            
            level_ids = [l["_id"] for l in levels]
            
            # Obtener todos los períodos
            periods = list(self.db.academic_periods.find({
                "level_id": {"$in": level_ids}
            }))
            
            # Estadísticas generales
            total_periods = len(periods)
            
            # Períodos por nivel
            periods_by_level = {}
            for level in levels:
                level_id = str(level["_id"])
                periods_by_level[level_id] = sum(1 for p in periods if str(p.get("level_id")) == level_id)
            
            # Períodos por tipo
            periods_by_type = {}
            for period in periods:
                period_type = period.get("type", "unknown")
                periods_by_type[period_type] = periods_by_type.get(period_type, 0) + 1
            
            # Períodos activos vs inactivos
            now = datetime.now()
            active_periods = sum(1 for p in periods if p.get("start_date") <= now <= p.get("end_date", now))
            
            # Calcular clases por período
            period_ids = [p["_id"] for p in periods]
            
            classes_by_period = {}
            for period_id in period_ids:
                classes_count = self.db.classes.count_documents({
                    "academic_period_id": period_id
                })
                classes_by_period[str(period_id)] = classes_count
            
            return {
                "total_periods": total_periods,
                "periods_by_level": periods_by_level,
                "periods_by_type": periods_by_type,
                "active_periods": active_periods,
                "classes_by_period": classes_by_period
            }
            
        except Exception as e:
            print(f"Error al obtener estadísticas de períodos: {str(e)}")
            return {}
    
    def _get_classes_stats(self, institute_id: str) -> Dict[str, any]:
        """Obtiene estadísticas de clases"""
        try:
            # Obtener todos los programas y niveles del instituto
            programs = list(self.db.educational_programs.find({
                "institute_id": ObjectId(institute_id)
            }))
            
            program_ids = [p["_id"] for p in programs]
            
            levels = list(self.db.levels.find({
                "program_id": {"$in": program_ids}
            }))
            
            level_ids = [l["_id"] for l in levels]
            
            # Obtener todas las clases
            classes = list(self.db.classes.find({
                "level_id": {"$in": level_ids}
            }))
            
            # Estadísticas generales
            total_classes = len(classes)
            
            # Clases por nivel
            classes_by_level = {}
            for level in levels:
                level_id = str(level["_id"])
                classes_by_level[level_id] = sum(1 for c in classes if str(c.get("level_id")) == level_id)
            
            # Clases por estado
            classes_by_status = {}
            for cls in classes:
                status = cls.get("status", "unknown")
                classes_by_status[status] = classes_by_status.get(status, 0) + 1
            
            # Obtener todos los miembros de las clases
            class_ids = [c["_id"] for c in classes]
            
            class_members = list(self.db.class_members.find({
                "class_id": {"$in": class_ids}
            }))
            
            # Promedio de estudiantes por clase
            students_by_class = {}
            for class_id in class_ids:
                student_count = sum(1 for m in class_members if m.get("class_id") == class_id and m.get("role") == "student")
                students_by_class[str(class_id)] = student_count
            
            avg_students_per_class = 0
            if total_classes > 0:
                avg_students_per_class = sum(students_by_class.values()) / total_classes
            
            # Clases con más y menos estudiantes
            most_students_class = max(students_by_class.items(), key=lambda x: x[1]) if students_by_class else ("", 0)
            least_students_class = min(students_by_class.items(), key=lambda x: x[1]) if students_by_class else ("", 0)
            
            return {
                "total_classes": total_classes,
                "classes_by_level": classes_by_level,
                "classes_by_status": classes_by_status,
                "avg_students_per_class": avg_students_per_class,
                "most_students_class": {
                    "class_id": most_students_class[0],
                    "students_count": most_students_class[1]
                },
                "least_students_class": {
                    "class_id": least_students_class[0],
                    "students_count": least_students_class[1]
                }
            }
            
        except Exception as e:
            print(f"Error al obtener estadísticas de clases: {str(e)}")
            return {}
    
    def _get_teachers_stats(self, institute_id: str) -> Dict[str, any]:
        """Obtiene estadísticas de profesores"""
        try:
            # Obtener todos los miembros del instituto con rol de profesor
            teacher_members = list(self.db.institute_members.find({
                "institute_id": ObjectId(institute_id),
                "role": "teacher"
            }))
            
            total_teachers = len(teacher_members)
            
            # Obtener todos los programas y niveles del instituto
            programs = list(self.db.educational_programs.find({
                "institute_id": ObjectId(institute_id)
            }))
            
            program_ids = [p["_id"] for p in programs]
            
            levels = list(self.db.levels.find({
                "program_id": {"$in": program_ids}
            }))
            
            level_ids = [l["_id"] for l in levels]
            
            # Obtener todas las clases
            classes = list(self.db.classes.find({
                "level_id": {"$in": level_ids}
            }))
            
            class_ids = [c["_id"] for c in classes]
            
            # Obtener miembros de clase que son profesores
            teacher_class_members = list(self.db.class_members.find({
                "class_id": {"$in": class_ids},
                "role": "teacher"
            }))
            
            # Contar clases por profesor
            classes_by_teacher = {}
            for member in teacher_class_members:
                teacher_id = str(member.get("user_id"))
                classes_by_teacher[teacher_id] = classes_by_teacher.get(teacher_id, 0) + 1
            
            # Calcular promedio de clases por profesor
            avg_classes_per_teacher = 0
            if total_teachers > 0:
                total_teacher_classes = sum(classes_by_teacher.values())
                avg_classes_per_teacher = total_teacher_classes / total_teachers
            
            # Identificar profesores con más y menos clases
            teachers_by_classes = sorted(classes_by_teacher.items(), key=lambda x: x[1], reverse=True)
            top_teachers = teachers_by_classes[:5] if teachers_by_classes else []
            
            # Profesores activos (que tienen al menos una clase)
            active_teachers = len(classes_by_teacher)
            
            return {
                "total_teachers": total_teachers,
                "active_teachers": active_teachers,
                "avg_classes_per_teacher": avg_classes_per_teacher,
                "top_teachers": [{"teacher_id": t[0], "classes_count": t[1]} for t in top_teachers]
            }
            
        except Exception as e:
            print(f"Error al obtener estadísticas de profesores: {str(e)}")
            return {}
    
    def _get_students_stats(self, institute_id: str) -> Dict[str, any]:
        """Obtiene estadísticas de estudiantes"""
        try:
            # Obtener todos los programas y niveles del instituto
            programs = list(self.db.educational_programs.find({
                "institute_id": ObjectId(institute_id)
            }))
            
            program_ids = [p["_id"] for p in programs]
            
            levels = list(self.db.levels.find({
                "program_id": {"$in": program_ids}
            }))
            
            level_ids = [l["_id"] for l in levels]
            
            # Obtener todas las clases
            classes = list(self.db.classes.find({
                "level_id": {"$in": level_ids}
            }))
            
            class_ids = [c["_id"] for c in classes]
            
            # Obtener miembros de clase que son estudiantes
            student_class_members = list(self.db.class_members.find({
                "class_id": {"$in": class_ids},
                "role": "student"
            }))
            
            # Identificar estudiantes únicos
            unique_student_ids = set(str(m.get("user_id")) for m in student_class_members)
            total_students = len(unique_student_ids)
            
            # Estudiantes por nivel
            students_by_level = {}
            for level in levels:
                level_id = level["_id"]
                level_classes = [c["_id"] for c in classes if c.get("level_id") == level_id]
                
                level_students = set()
                for member in student_class_members:
                    if member.get("class_id") in level_classes:
                        level_students.add(str(member.get("user_id")))
                
                students_by_level[str(level_id)] = len(level_students)
            
            # Estudiantes por programa
            students_by_program = {}
            for program in programs:
                program_id = program["_id"]
                program_levels = [l["_id"] for l in levels if l.get("program_id") == program_id]
                
                program_classes = [c["_id"] for c in classes if c.get("level_id") in program_levels]
                
                program_students = set()
                for member in student_class_members:
                    if member.get("class_id") in program_classes:
                        program_students.add(str(member.get("user_id")))
                
                students_by_program[str(program_id)] = len(program_students)
            
            # Calcular número de clases por estudiante
            classes_by_student = {}
            for member in student_class_members:
                student_id = str(member.get("user_id"))
                classes_by_student[student_id] = classes_by_student.get(student_id, 0) + 1
            
            # Promedio de clases por estudiante
            avg_classes_per_student = 0
            if total_students > 0:
                avg_classes_per_student = sum(classes_by_student.values()) / total_students
            
            return {
                "total_students": total_students,
                "students_by_level": students_by_level,
                "students_by_program": students_by_program,
                "avg_classes_per_student": avg_classes_per_student
            }
            
        except Exception as e:
            print(f"Error al obtener estadísticas de estudiantes: {str(e)}")
            return {} 