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
        query = {"student_id": ObjectId(student_id)}
        if period_id:
            query["period_id"] = ObjectId(period_id)
            
        stats = {
            # Resumen académico actual
            "current_period": {
                "grade_average": 0.0,
                "subjects": [],  # Lista de materias con sus promedios
                "attendance_rate": 0.0
            },
            
            # Actividades pendientes
            "pending_activities": {
                "evaluations": [],  # Próximas evaluaciones
                "assignments": [],  # Tareas pendientes
                "study_content": []  # Contenido por revisar
            },
            
            # Progreso personal
            "progress": {
                "completed_activities": 0,
                "total_activities": 0,
                "completion_percentage": 0
            }
        }
        
        # Calcular promedios por materia
        subject_grades = db.grades.aggregate([
            {"$match": query},
            {"$group": {
                "_id": "$subject_id",
                "average": {"$avg": "$score"},
                "evaluations_count": {"$sum": 1}
            }}
        ])
        
        total_average = 0
        subjects_count = 0
        
        for subject in subject_grades:
            subject_info = db.subjects.find_one({"_id": subject["_id"]})
            if subject_info:
                subjects_count += 1
                total_average += subject["average"]
                stats["current_period"]["subjects"].append({
                    "name": subject_info["name"],
                    "average": round(subject["average"], 2),
                    "evaluations": subject["evaluations_count"]
                })
        
        if subjects_count > 0:
            stats["current_period"]["grade_average"] = round(total_average / subjects_count, 2)
            
        # Obtener próximas evaluaciones (próximos 7 días)
        next_week = datetime.now() + timedelta(days=7)
        pending_evaluations = db.evaluations.find({
            **query,
            "date": {"$gte": datetime.now(), "$lte": next_week},
            "status": "pending"
        }).limit(5)
        
        for eval in pending_evaluations:
            subject = db.subjects.find_one({"_id": eval["subject_id"]})
            stats["pending_activities"]["evaluations"].append({
                "subject": subject["name"] if subject else "Sin materia",
                "title": eval["title"],
                "date": eval["date"],
                "type": eval["type"]  # parcial, quiz, etc.
            })
            
        # Obtener tareas pendientes
        pending_assignments = db.assignments.find({
            **query,
            "due_date": {"$gte": datetime.now()},
            "status": "pending"
        }).limit(5)
        
        for assignment in pending_assignments:
            subject = db.subjects.find_one({"_id": assignment["subject_id"]})
            stats["pending_activities"]["assignments"].append({
                "subject": subject["name"] if subject else "Sin materia",
                "title": assignment["title"],
                "due_date": assignment["due_date"]
            })
            
        # Calcular progreso general
        total_activities = db.study_plan_progress.count_documents(query)
        completed_activities = db.study_plan_progress.count_documents({
            **query,
            "status": "completed"
        })
        
        stats["progress"]["total_activities"] = total_activities
        stats["progress"]["completed_activities"] = completed_activities
        if total_activities > 0:
            stats["progress"]["completion_percentage"] = round(
                (completed_activities / total_activities) * 100, 1
            )
            
        return stats
        
    except Exception as e:
        print(f"Error al obtener estadísticas del estudiante: {str(e)}")
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