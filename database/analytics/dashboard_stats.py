from database.mongodb import get_db
from datetime import datetime, timedelta
from bson import ObjectId

def get_student_dashboard_stats(student_id, period_id=None):
    """
    Obtiene estadísticas relevantes para el dashboard del estudiante.
    Muestra solo información personal y útil para su seguimiento académico.
    """
    db = get_db()
    
    try:
        # Estructura base de estadísticas
        stats = {
            "current_period": {
                "grade_average": 0.0,
                "subjects": [],  # Aquí guardaremos los classrooms y materias
                "attendance_rate": 0.0
            },
            "pending_activities": {
                "evaluations": [],
                "assignments": [],
                "study_content": []
            },
            "progress": {
                "completed_activities": 0,
                "total_activities": 0,
                "completion_percentage": 0
            }
        }

        # Primero obtenemos los classrooms del estudiante
        classroom_memberships = db.classroom_members.find({
            "user_id": ObjectId(student_id),
            "role": "STUDENT"
        })
        
        # Si no hay memberships, devolvemos las estadísticas vacías
        if not classroom_memberships:
            return stats

        classroom_ids = []
        
        # Obtener información básica de cada classroom y su materia asociada
        for membership in classroom_memberships:
            classroom = db.classrooms.find_one({"_id": membership["classroom_id"]})
            if classroom:
                classroom_ids.append(classroom["_id"])
                
                # Obtener información de la materia
                subject = db.subjects.find_one({"_id": classroom["subject_id"]})
                
                # Agregar información básica del classroom/materia
                classroom_info = {
                    "classroom_id": str(classroom["_id"]),
                    "classroom_name": classroom["name"],
                    "subject_name": subject["name"] if subject else "Sin materia",
                    "subject_id": str(classroom["subject_id"]),
                    "average": 0.0,
                    "evaluations": 0
                }
                
                # Intentar obtener calificaciones si existen
                try:
                    grades = db.grades.aggregate([
                        {
                            "$match": {
                                "classroom_id": classroom["_id"],
                                "student_id": ObjectId(student_id)
                            }
                        },
                        {
                            "$group": {
                                "_id": None,
                                "average": {"$avg": "$score"},
                                "evaluations_count": {"$sum": 1}
                            }
                        }
                    ]).next()
                    
                    if grades:
                        classroom_info["average"] = round(grades["average"], 2)
                        classroom_info["evaluations"] = grades["evaluations_count"]
                except:
                    pass  # Si no hay calificaciones, mantener los valores por defecto
                
                stats["current_period"]["subjects"].append(classroom_info)

        # Si hay classrooms, intentar obtener el resto de información
        if classroom_ids:
            # Próximas evaluaciones
            next_week = datetime.now() + timedelta(days=7)
            pending_evaluations = db.evaluations.find({
                "classroom_id": {"$in": classroom_ids},
                "date": {"$gte": datetime.now(), "$lte": next_week},
                "status": "pending"
            }).limit(5)
            
            for eval in pending_evaluations:
                classroom = db.classrooms.find_one({"_id": eval["classroom_id"]})
                subject = db.subjects.find_one({"_id": classroom["subject_id"]}) if classroom else None
                
                stats["pending_activities"]["evaluations"].append({
                    "subject": subject["name"] if subject else "Sin materia",
                    "classroom": classroom["name"] if classroom else "Sin grupo",
                    "title": eval["title"],
                    "date": eval["date"],
                    "type": eval["type"]
                })

            # Obtener tareas pendientes
            pending_assignments = db.assignments.find({
                "classroom_id": {"$in": classroom_ids},
                "due_date": {"$gte": datetime.now()},
                "status": "pending"
            }).limit(5)
            
            for assignment in pending_assignments:
                classroom = db.classrooms.find_one({"_id": assignment["classroom_id"]})
                subject = db.subjects.find_one({"_id": classroom["subject_id"]}) if classroom else None
                
                stats["pending_activities"]["assignments"].append({
                    "subject": subject["name"] if subject else "Sin materia",
                    "classroom": classroom["name"] if classroom else "Sin grupo",
                    "title": assignment["title"],
                    "due_date": assignment["due_date"]
                })

            # Calcular progreso general
            total_activities = db.study_plan_progress.count_documents({
                "classroom_id": {"$in": classroom_ids}
            })
            
            completed_activities = db.study_plan_progress.count_documents({
                "classroom_id": {"$in": classroom_ids},
                "status": "completed"
            })
            
            stats["progress"]["total_activities"] = total_activities
            stats["progress"]["completed_activities"] = completed_activities
            if total_activities > 0:
                stats["progress"]["completion_percentage"] = round(
                    (completed_activities / total_activities) * 100, 1
                )

        # Calcular promedio general si hay materias con calificaciones
        subjects_with_grades = [s for s in stats["current_period"]["subjects"] if s["average"] > 0]
        if subjects_with_grades:
            total_average = sum(s["average"] for s in subjects_with_grades)
            stats["current_period"]["grade_average"] = round(
                total_average / len(subjects_with_grades), 
                2
            )
            
        return stats
        
    except Exception as e:
        print(f"Error al obtener estadísticas del estudiante: {str(e)}")
        # Aún en caso de error, intentar devolver al menos los classrooms básicos
        try:
            basic_stats = {
                "current_period": {
                    "grade_average": 0.0,
                    "subjects": [],
                    "attendance_rate": 0.0
                },
                "pending_activities": {
                    "evaluations": [],
                    "assignments": [],
                    "study_content": []
                },
                "progress": {
                    "completed_activities": 0,
                    "total_activities": 0,
                    "completion_percentage": 0
                }
            }
            
            memberships = db.classroom_members.find({
                "user_id": ObjectId(student_id),
                "role": "STUDENT"
            })
            
            for membership in memberships:
                classroom = db.classrooms.find_one({"_id": membership["classroom_id"]})
                if classroom:
                    subject = db.subjects.find_one({"_id": classroom["subject_id"]})
                    basic_stats["current_period"]["subjects"].append({
                        "classroom_id": str(classroom["_id"]),
                        "classroom_name": classroom["name"],
                        "subject_name": subject["name"] if subject else "Sin materia",
                        "subject_id": str(classroom["subject_id"]),
                        "average": 0.0,
                        "evaluations": 0
                    })
            
            return basic_stats
            
        except Exception as inner_e:
            print(f"Error al obtener información básica: {str(inner_e)}")
            return None

def get_teacher_dashboard_stats(teacher_id, period_id=None):
    """
    Obtiene estadísticas relevantes para el dashboard del profesor.
    Enfocado en el seguimiento grupal y gestión de clases.
    """
    db = get_db()
    
    try:
        query = {"teacher_id": ObjectId(teacher_id)}
        if period_id:
            query["period_id"] = ObjectId(period_id)
            
        stats = {
            # Resumen de clases
            "classes_overview": {
                "total_students": 0,
                "classes": []  # Lista de materias/grupos con estadísticas básicas
            },
            
            # Actividades pendientes de revisar
            "pending_reviews": {
                "assignments": 0,
                "evaluations": 0,
                "recent_submissions": []  # Últimas entregas pendientes
            },
            
            # Progreso del plan de estudios
            "study_plan_progress": {
                "current_topic": "",
                "completion_percentage": 0,
                "on_schedule": True
            }
        }
        
        # Obtener resumen de clases
        classrooms = db.classrooms.find(query)
        
        for classroom in classrooms:
            # Contar estudiantes
            students_count = db.classroom_members.count_documents({
                "classroom_id": classroom["_id"],
                "role": "student"
            })
            
            # Calcular promedio de la clase
            class_average = db.grades.aggregate([
                {"$match": {"classroom_id": classroom["_id"]}},
                {"$group": {
                    "_id": None,
                    "average": {"$avg": "$score"}
                }}
            ]).next()
            
            stats["classes_overview"]["classes"].append({
                "name": classroom["name"],
                "students": students_count,
                "average": round(class_average["average"], 2) if class_average else 0,
                "last_class": classroom.get("last_class_date")
            })
            
            stats["classes_overview"]["total_students"] += students_count
            
        # Contabilizar entregas pendientes de revisar
        stats["pending_reviews"]["assignments"] = db.assignments.count_documents({
            **query,
            "status": "submitted",
            "reviewed": False
        })
        
        stats["pending_reviews"]["evaluations"] = db.evaluations.count_documents({
            **query,
            "status": "submitted",
            "graded": False
        })
        
        # Obtener últimas entregas pendientes
        recent_submissions = db.assignments.find({
            **query,
            "status": "submitted",
            "reviewed": False
        }).sort("submitted_at", -1).limit(5)
        
        for submission in recent_submissions:
            student = db.users.find_one({"_id": submission["student_id"]})
            stats["pending_reviews"]["recent_submissions"].append({
                "student_name": student["name"] if student else "Estudiante desconocido",
                "title": submission["title"],
                "submitted_at": submission["submitted_at"]
            })
            
        # Verificar progreso del plan de estudios
        study_plan = db.study_plans.find_one(query)
        if study_plan:
            current_topic = db.topics.find_one({
                "study_plan_id": study_plan["_id"],
                "status": "in_progress"
            })
            
            if current_topic:
                stats["study_plan_progress"]["current_topic"] = current_topic["name"]
            
            total_topics = db.topics.count_documents({"study_plan_id": study_plan["_id"]})
            completed_topics = db.topics.count_documents({
                "study_plan_id": study_plan["_id"],
                "status": "completed"
            })
            
            if total_topics > 0:
                completion = (completed_topics / total_topics) * 100
                stats["study_plan_progress"]["completion_percentage"] = round(completion, 1)
                
                # Verificar si está al día según la planificación
                expected_completion = study_plan.get("expected_completion_percentage", 0)
                stats["study_plan_progress"]["on_schedule"] = completion >= expected_completion
            
        return stats
        
    except Exception as e:
        print(f"Error al obtener estadísticas del profesor: {str(e)}")
        return None 