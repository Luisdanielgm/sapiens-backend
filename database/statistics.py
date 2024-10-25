from database.mongodb import get_db
from database.common import get_user_id_by_email
from bson import ObjectId

def get_teacher_statistics(email):
    """
    Obtiene estadísticas para un profesor:
    - Número total de clases
    - Número total de estudiantes
    - Promedio de estudiantes por clase
    - Número de contenidos creados
    """
    db = get_db()
    user_id = get_user_id_by_email(email)
    if not user_id:
        return None

    try:
        # Obtener número de clases
        classroom_members = db.classroom_members.find({
            "user_id": user_id,
            "role": "teacher"
        })
        classroom_ids = [member["classroom_id"] for member in classroom_members]
        total_classrooms = len(classroom_ids)

        # Obtener número total de estudiantes
        total_students = 0
        for classroom_id in classroom_ids:
            students = db.classroom_members.count_documents({
                "classroom_id": classroom_id,
                "role": "student"
            })
            total_students += students

        # Calcular promedio de estudiantes por clase
        avg_students = total_students / total_classrooms if total_classrooms > 0 else 0

        # Obtener número de contenidos creados
        total_content = db.content.count_documents({
            "created_by": user_id
        })

        return {
            "total_classrooms": total_classrooms,
            "total_students": total_students,
            "average_students_per_classroom": round(avg_students, 2),
            "total_content": total_content
        }
    except Exception as e:
        print(f"Error al obtener estadísticas del profesor: {str(e)}")
        return None

def get_student_statistics(email):
    """
    Obtiene estadísticas para un estudiante:
    - Número de clases en las que está inscrito
    - Fecha de inscripción más antigua
    - Perfil cognitivo completado (%)
    """
    db = get_db()
    user_id = get_user_id_by_email(email)
    if not user_id:
        return None

    try:
        # Obtener número de clases
        total_classrooms = db.classroom_members.count_documents({
            "user_id": user_id,
            "role": "student"
        })

        # Obtener fecha de inscripción más antigua
        oldest_membership = db.classroom_members.find_one(
            {"user_id": user_id, "role": "student"},
            sort=[("joined_at", 1)]
        )
        first_joined_date = oldest_membership["joined_at"] if oldest_membership else None

        # Calcular completitud del perfil cognitivo
        cognitive_profile = db.cognitive_profiles.find_one({"user_id": user_id})
        profile_completion = 0
        if cognitive_profile and cognitive_profile.get("profile"):
            profile_data = cognitive_profile["profile"]
            # Aquí puedes implementar la lógica específica para calcular el porcentaje
            # Por ahora usaremos un valor fijo
            profile_completion = 100

        return {
            "total_classrooms": total_classrooms,
            "first_joined_date": first_joined_date,
            "profile_completion": profile_completion
        }
    except Exception as e:
        print(f"Error al obtener estadísticas del estudiante: {str(e)}")
        return None
