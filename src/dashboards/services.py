from typing import Dict, List, Optional
from bson import ObjectId
from datetime import datetime, timedelta
import logging

from src.shared.database import get_db
from src.shared.constants import ROLES
from src.shared.standardization import BaseService
from src.analytics.services import (
    StudentAnalyticsService, 
    ClassAnalyticsService,
    StudentSubjectsAnalyticsService
)
from .models import (
    AdminDashboard,
    TeacherDashboard,
    StudentDashboard,
    InstituteDashboard
)

class AdminDashboardService(BaseService):
    """Servicio para generar dashboard del administrador"""
    
    def __init__(self):
        super().__init__(collection_name="dashboards_admin")
        self.db = get_db()
        
    def generate_admin_dashboard(self) -> Dict:
        """Genera un dashboard completo para el administrador del sistema"""
        try:
            # Total de institutos
            institutes_count = self.db.institutes.count_documents({})
            
            # Total de usuarios por rol
            users_by_role = {}
            for role_name, role_value in ROLES.items():
                count = self.db.users.count_documents({"role": role_value})
                users_by_role[role_name] = count
            
            total_users = sum(users_by_role.values())
            
            # Total de clases
            classes_count = self.db.classes.count_documents({})
            
            # Total de estudiantes activos (miembros de al menos una clase)
            active_students = len(list(self.db.class_members.distinct("user_id", {"role": "STUDENT"})))
            
            # Institutos con más clases
            top_institutes = list(self.db.classes.aggregate([
                {"$group": {"_id": "$institute_id", "count": {"$sum": 1}}},
                {"$sort": {"count": -1}},
                {"$limit": 5},
                {"$lookup": {
                    "from": "institutes",
                    "localField": "_id",
                    "foreignField": "_id",
                    "as": "institute_info"
                }},
                {"$unwind": "$institute_info"},  # Desestructurar el array para acceder a sus elementos directamente
                {"$project": {
                    "institute_id": "$_id",
                    "name": "$institute_info.name",  # Ahora podemos acceder directamente al nombre
                    "classes_count": "$count"
                }}
            ]))
            
            # Si por alguna razón hay menos de 5 institutos con clases, completar información
            if len(top_institutes) > 0:
                # Verificar que todos los institutos tengan nombre
                for institute in top_institutes:
                    if "name" not in institute or not institute["name"]:
                        # Buscar el nombre del instituto en la colección
                        institute_info = self.db.institutes.find_one({"_id": institute["institute_id"]})
                        if institute_info:
                            institute["name"] = institute_info.get("name", "Sin nombre")
            
            # Métricas de rendimiento promedio por instituto
            institutes_performance = list(self.db.institutes.aggregate([
                {"$lookup": {
                    "from": "classes",
                    "localField": "_id",
                    "foreignField": "institute_id",
                    "as": "classes"
                }},
                {"$project": {
                    "institute_id": "$_id",
                    "name": "$name",
                    "classes_count": {"$size": "$classes"},
                }}
            ]))
            
            # Estadísticas del sistema
            system_stats = {
                "total_institutes": institutes_count,
                "total_users": total_users,
                "users_by_role": users_by_role,
                "total_classes": classes_count,
                "active_students": active_students
            }
            
            # Datos recientes (últimos 30 días)
            thirty_days_ago = datetime.now() - timedelta(days=30)
            
            new_users = self.db.users.count_documents({
                "created_at": {"$gte": thirty_days_ago}
            })
            
            new_classes = self.db.classes.count_documents({
                "created_at": {"$gte": thirty_days_ago}
            })
            
            recent_stats = {
                "new_users_last_30_days": new_users,
                "new_classes_last_30_days": new_classes
            }
            
            dashboard = AdminDashboard(
                system_stats=system_stats,
                top_institutes=top_institutes,
                institutes_performance=institutes_performance,
                recent_stats=recent_stats,
                generated_at=datetime.now()
            )
            
            # Guardar dashboard para historial/referencia
            self.collection.insert_one(dashboard.to_dict())
            
            return dashboard.to_dict()
        except Exception as e:
            logging.getLogger(__name__).error(f"Error generando dashboard de admin: {str(e)}")
            return None


class TeacherDashboardService(BaseService):
    """Servicio para generar dashboard de profesores"""
    
    def __init__(self):
        super().__init__(collection_name="dashboards_teacher")
        self.db = get_db()
        self.class_analytics_service = ClassAnalyticsService()
        
    def generate_teacher_dashboard(self, teacher_id: str) -> Dict:
        """Genera un dashboard para un profesor con métricas relevantes"""
        try:
            logger = logging.getLogger(__name__)
            
            # Obtener clases del profesor a través de class_members
            memberships = list(self.db.class_members.find({
                "user_id": ObjectId(teacher_id),
                "role": "TEACHER"
            }))
            
            logger.info(f"Encontradas {len(memberships)} membresías para el profesor")
            
            if not memberships:
                return TeacherDashboard(
                    teacher_id=teacher_id,
                    classes=[],
                    overall_metrics={
                        "total_classes": 0,
                        "total_students": 0,
                        "average_attendance": 0,
                        "average_evaluation_score": 0
                    }
                ).to_dict()
            
            # Extraer IDs de clases donde el profesor es miembro
            class_ids = [m["class_id"] for m in memberships]
            
            # Obtener información de las clases
            classes = list(self.db.classes.find({
                "_id": {"$in": class_ids}
            }))
            
            logger.info(f"Encontradas {len(classes)} clases para el profesor")
            logger.info(f"IDs de las clases encontradas: {[str(cls['_id']) for cls in classes]}")
                
            # Métricas por clase
            class_metrics = []
            
            # Conjunto para almacenar IDs únicos de estudiantes en todas las clases
            unique_student_ids = set()
            
            # Procesar cada clase
            for cls in classes:
                class_id = str(cls["_id"])
                class_name = cls.get("name", "Sin nombre")
                logger.info(f"Procesando clase con ID: {class_id}, nombre: {class_name}")
                
                # Siempre añadir la clase al dashboard con información básica
                class_data = {
                    "class_id": class_id,
                    "class_name": class_name,
                    "metrics": {
                        "student_count": 0,
                        "attendance_stats": {"average_rate": 0},
                        "evaluation_stats": {"average_score": 0}
                    }
                }
                
                # Intentar obtener estadísticas más detalladas
                try:
                    stats = self.class_analytics_service.get_class_analytics(class_id)
                    if stats and isinstance(stats, dict):
                        logger.info(f"Estadísticas obtenidas para la clase {class_id}")
                        class_data["metrics"] = stats
                    else:
                        logger.warning(f"No se pudieron obtener estadísticas completas para la clase {class_id}")
                except Exception as e:
                    logger.error(f"Error obteniendo estadísticas para la clase {class_id}: {str(e)}")
                
                # Añadir la clase al dashboard
                class_metrics.append(class_data)
                logger.info(f"Añadida clase al dashboard: {class_name}")
                
                # Recopilar IDs de estudiantes en esta clase para conteo preciso
                try:
                    class_members = list(self.db.class_members.find({
                        "class_id": ObjectId(class_id),
                        "role": "STUDENT"
                    }))
                    class_student_ids = {str(member["user_id"]) for member in class_members}
                    unique_student_ids.update(class_student_ids)
                    logger.info(f"Clase {class_name} tiene {len(class_student_ids)} estudiantes")
                except Exception as e:
                    logger.error(f"Error obteniendo estudiantes para clase {class_id}: {str(e)}")
            
            logger.info(f"Total de clases procesadas para el dashboard: {len(class_metrics)}")
            logger.info(f"Total de estudiantes únicos encontrados: {len(unique_student_ids)}")
            
            # Métricas generales
            average_attendance = 0
            average_score = 0
            
            if class_metrics:
                try:
                    # Calcular promedios
                    attendance_values = []
                    score_values = []
                    
                    for m in class_metrics:
                        metrics = m.get("metrics", {})
                        
                        # Obtener tasa de asistencia
                        attendance_rate = metrics.get("attendance_stats", {}).get("average_rate", 0)
                        if attendance_rate > 0:
                            attendance_values.append(attendance_rate)
                        
                        # Obtener puntaje promedio
                        avg_score = metrics.get("evaluation_stats", {}).get("average_score", 0)
                        if avg_score > 0:
                            score_values.append(avg_score)
                    
                    # Calcular promedio general
                    if attendance_values:
                        average_attendance = round(sum(attendance_values) / len(attendance_values), 2)
                    
                    if score_values:
                        average_score = round(sum(score_values) / len(score_values), 2)
                except Exception as e:
                    logger.error(f"Error calculando métricas generales: {str(e)}")
            
            overall_metrics = {
                "total_classes": len(classes),
                "total_students": len(unique_student_ids),  # Ahora usamos el conteo de estudiantes únicos
                "average_attendance": average_attendance,
                "average_evaluation_score": average_score
            }
            
            logger.info(f"Métricas generales calculadas: {overall_metrics}")
                
            dashboard = TeacherDashboard(
                teacher_id=teacher_id,
                classes=class_metrics,
                overall_metrics=overall_metrics
            )
            
            # Guardar dashboard para historial/referencia
            dashboard_dict = dashboard.to_dict()
            
            # Verificación final para asegurar que las clases están incluidas
            if len(dashboard_dict.get("classes", [])) != len(class_metrics):
                logger.warning(f"Discrepancia en el número de clases. Esperadas: {len(class_metrics)}, Obtenidas: {len(dashboard_dict.get('classes', []))}")
                # Forzar la inclusión si hay discrepancia
                dashboard_dict["classes"] = class_metrics
            
            self.collection.insert_one(dashboard_dict)
            
            logger.info(f"Dashboard generado con {len(dashboard_dict.get('classes', []))} clases")
                
            return dashboard_dict
        except Exception as e:
            logger = logging.getLogger(__name__)
            logger.error(f"Error generando dashboard de profesor: {str(e)}", exc_info=True)
            # Devolver un dashboard mínimo para evitar errores
            return {
                "teacher_id": str(teacher_id),
                "classes": [],
                "overall_metrics": {
                    "total_classes": 0,
                    "total_students": 0,
                    "average_attendance": 0,
                    "average_evaluation_score": 0
                },
                "created_at": datetime.now()
            }

    def generate_individual_teacher_dashboard(self, teacher_id: str, workspace_info: Dict) -> Dict:
        """Genera un dashboard individual para un profesor en workspace individual"""
        # Para workspaces individuales, simplemente llamar al método principal
        # ya que la lógica es la misma, solo cambia el contexto de workspace
        return self.generate_teacher_dashboard(teacher_id)


class StudentDashboardService(BaseService):
    """Servicio para generar dashboard de estudiantes"""
    
    def __init__(self):
        super().__init__(collection_name="dashboards_student")
        self.db = get_db()
        self.student_analytics_service = StudentAnalyticsService()
        self.student_subjects_analytics_service = StudentSubjectsAnalyticsService()
        
    def generate_student_dashboard(self, student_id: str, period_id: Optional[str] = None) -> Dict:
        """Genera un dashboard para un estudiante con su progreso académico"""
        try:
            # Obtener clases del estudiante
            memberships = list(self.db.class_members.find({
                "user_id": ObjectId(student_id),
                "role": "STUDENT"
            }))
            
            if not memberships:
                dashboard = StudentDashboard(
                    student_id=student_id,
                    classes=[],
                    subjects=[]
                ).to_dict()
                dashboard["virtual_content"] = self._get_virtual_content_summary(student_id)
                return dashboard
                
            class_ids = [str(m["class_id"]) for m in memberships]
            
            # Obtener rendimiento por clase
            class_performances = []
            
            for class_id in class_ids:
                cls_info = self.db.classes.find_one({"_id": ObjectId(class_id)})
                if cls_info:
                    # Crear estructura básica para la clase que siempre se añadirá
                    class_data = {
                        "class_id": class_id,
                        "class_name": cls_info.get("name", "Sin nombre"),
                        "performance": {
                            "metrics": {
                                "attendance_rate": 0,
                                "avg_score": 0,
                                "completion_rate": 0
                            },
                            "details": {
                                "evaluations": [],
                                "attendance": []
                            }
                        }
                    }
                    
                    # Intentar obtener datos de rendimiento detallados
                    performance = self.student_analytics_service.calculate_student_performance(
                        student_id, class_id, period_id
                    )
                    
                    # Si hay datos de rendimiento, actualizar la estructura básica
                    if performance:
                        class_data["performance"] = performance
                        
                    # Añadir la clase al array, con o sin datos de rendimiento
                    class_performances.append(class_data)
                
            # Obtener análisis por materias
            subjects_analytics = self.student_subjects_analytics_service.get_student_subjects_analytics(
                student_id, period_id
            )
                
            dashboard = StudentDashboard(
                student_id=student_id,
                classes=class_performances,
                subjects=subjects_analytics
            )
            
            dashboard_dict = dashboard.to_dict()
            dashboard_dict["virtual_content"] = self._get_virtual_content_summary(student_id)
            
            # Guardar dashboard para historial/referencia
            self.collection.insert_one(dashboard_dict)
            
            return dashboard_dict
        except Exception as e:
            logging.getLogger(__name__).error(f"Error generando dashboard de estudiante: {str(e)}")
            return None

    def _get_virtual_content_summary(self, student_id: str) -> Dict:
        try:
            if not ObjectId.is_valid(student_id):
                return self._empty_virtual_content_summary()

            records = list(
                self.db.content_results.find({"student_id": ObjectId(student_id)}).sort("created_at", -1)
            )

            if not records:
                return self._empty_virtual_content_summary()

            score_values = [r.get("score") for r in records if isinstance(r.get("score"), (int, float))]
            completion_values = [
                r.get("completion_percentage") for r in records if isinstance(r.get("completion_percentage"), (int, float))
            ]
            average_score = round(sum(score_values) / len(score_values), 1) if score_values else 0.0
            completion_rate = round(sum(completion_values) / len(completion_values), 1) if completion_values else 0.0

            by_type: Dict[str, int] = {}
            for record in records:
                ctype = record.get("content_type") or "unknown"
                by_type[ctype] = by_type.get(ctype, 0) + 1

            recent = []
            for record in records[:5]:
                completed_at = record.get("completed_at") or record.get("created_at")
                if isinstance(completed_at, datetime):
                    completed_at = completed_at.isoformat()
                recent.append({
                    "content_type": record.get("content_type") or "unknown",
                    "score": record.get("score"),
                    "completion_percentage": record.get("completion_percentage"),
                    "completed_at": completed_at,
                    "title": (record.get("content_info") or {}).get("title"),
                    "template_usage_id": record.get("template_usage_id"),
                    "virtual_content_id": record.get("virtual_content_id"),
                })

            return {
                "average_score": average_score,
                "completion_rate": completion_rate,
                "total_activities": len(records),
                "by_content_type": by_type,
                "recent_results": recent,
            }
        except Exception as e:
            logging.getLogger(__name__).warning(f"Error obteniendo resumen de contenido virtual: {e}")
            return self._empty_virtual_content_summary()

    @staticmethod
    def _empty_virtual_content_summary() -> Dict:
        return {
            "average_score": 0.0,
            "completion_rate": 0.0,
            "total_activities": 0,
            "by_content_type": {},
            "recent_results": []
        }
    def generate_individual_student_dashboard(self, student_id: str, workspace_info: Dict, period_id: Optional[str] = None) -> Dict:
        """Genera un dashboard individual para un estudiante en workspace individual"""
        # Para workspaces individuales, simplemente llamar al método principal
        # ya que la lógica es la misma, solo cambia el contexto de workspace
        return self.generate_student_dashboard(student_id, period_id)


class InstituteDashboardService(BaseService):
    """Servicio para generar dashboard de institutos"""
    
    def __init__(self):
        super().__init__(collection_name="dashboards_institute")
        self.db = get_db()
    
    def generate_institute_dashboard(self, institute_id: str) -> Optional[Dict]:
        """Genera un dashboard completo para un instituto educativo"""
        logger = logging.getLogger(__name__)
        try:
            # Validar que el ID sea válido
            try:
                ObjectId(institute_id)
            except Exception as e:
                logger.error(f"ID de instituto inválido: {institute_id}, error: {str(e)}")
                return None
            
            # Verificar si el instituto existe
            institute = self.db.institutes.find_one({"_id": ObjectId(institute_id)})
            if not institute:
                logger.warning(f"Instituto no encontrado: {institute_id}")
                return None

            logger.info(f"Generando dashboard para instituto: {institute_id}")

            # Obtener métricas generales
            overview_metrics = self._get_overview_metrics(institute_id)
            
            # Estadísticas por programa educativo
            programs_stats = self._get_programs_stats(institute_id)
            
            # Estadísticas por nivel educativo
            levels_stats = self._get_levels_stats(institute_id)
            
            # Estadísticas por sección
            sections_stats = self._get_sections_stats(institute_id)
            
            # Estadísticas por materia
            subjects_stats = self._get_subjects_stats(institute_id)
            
            # Estadísticas por período académico
            periods_stats = self._get_periods_stats(institute_id)
            
            # Estadísticas de clases
            classes_stats = self._get_classes_stats(institute_id)
            
            # Estadísticas de profesores
            teachers_stats = self._get_teachers_stats(institute_id)
            
            # Estadísticas de estudiantes
            students_stats = self._get_students_stats(institute_id)
            
            # Crear objeto dashboard
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
            
            # Guardar dashboard para historial/referencia
            dashboard_dict = dashboard.to_dict()
            try:
                self.collection.insert_one(dashboard_dict)
            except Exception as save_error:
                # Si falla el guardado, loguear pero no fallar - el dashboard se devuelve de todos modos
                logger.warning(f"Error al guardar dashboard en historial: {str(save_error)}")
            
            logger.info(f"Dashboard generado exitosamente para instituto: {institute_id}")
            return dashboard_dict
        except Exception as e:
            import traceback
            logger.error(f"Error generando dashboard de instituto {institute_id}: {str(e)}\n{traceback.format_exc()}")
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
            
            total_teachers = sum(1 for m in institute_members if m.get("role") == "TEACHER")
            total_admins = sum(1 for m in institute_members if m.get("role") == "INSTITUTE_ADMIN")
            
            # Contar estudiantes (estudiantes matriculados en clases)
            class_ids = [c["_id"] for c in self.db.classes.find({"level_id": {"$in": level_ids}})]
            
            class_members = list(self.db.class_members.find({
                "class_id": {"$in": class_ids},
                "role": "STUDENT"
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
            logging.getLogger(__name__).error(f"Error al obtener métricas generales: {str(e)}")
            return {}
    
    def _get_programs_stats(self, institute_id: str) -> List[Dict]:
        """Obtiene estadísticas por programa educativo"""
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
                    "role": "STUDENT"
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
            logging.getLogger(__name__).error(f"Error al obtener estadísticas de programas: {str(e)}")
            return []
    
    def _get_levels_stats(self, institute_id: str) -> List[Dict]:
        """Obtiene estadísticas por nivel educativo"""
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
                    "role": "STUDENT"
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
            logging.getLogger(__name__).error(f"Error al obtener estadísticas de niveles: {str(e)}")
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
            logging.getLogger(__name__).error(f"Error al obtener estadísticas de secciones: {str(e)}")
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
            logging.getLogger(__name__).error(f"Error al obtener estadísticas de materias: {str(e)}")
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
            logging.getLogger(__name__).error(f"Error al obtener estadísticas de períodos: {str(e)}")
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
                student_count = sum(1 for m in class_members if m.get("class_id") == class_id and m.get("role") == "STUDENT")
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
            logging.getLogger(__name__).error(f"Error al obtener estadísticas de clases: {str(e)}")
            return {}
    
    def _get_teachers_stats(self, institute_id: str) -> Dict[str, any]:
        """Obtiene estadísticas de profesores"""
        try:
            # Obtener todos los miembros del instituto con rol de profesor
            teacher_members = list(self.db.institute_members.find({
                "institute_id": ObjectId(institute_id),
                "role": "TEACHER"
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
                "role": "TEACHER"
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
            logging.getLogger(__name__).error(f"Error al obtener estadísticas de profesores: {str(e)}")
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
                "role": "STUDENT"
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
            logging.getLogger(__name__).error(f"Error al obtener estadísticas de estudiantes: {str(e)}")
            return {} 



