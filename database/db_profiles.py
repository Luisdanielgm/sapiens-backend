from database.mongodb import get_db
from datetime import datetime

def get_teacher_profile(email):
    """Obtiene el perfil del profesor"""
    db = get_db()
    users_collection = db.users
    teacher_profiles_collection = db.teacher_profiles

    user = users_collection.find_one({"email": email, "role": "teacher"})
    if not user:
        return None, "Usuario no encontrado o no es profesor"

    profile = teacher_profiles_collection.find_one({"user_id": user["_id"]})
    if not profile:
        return None, "Perfil no encontrado"

    return {
        "id": str(profile["_id"]),
        "specialties": profile.get("specialties", []),
        "education": profile.get("education", []),
        "teaching_experience": profile.get("teaching_experience", 0),
        "certifications": profile.get("certifications", []),
        "biography": profile.get("biography", ""),
        "teaching_philosophy": profile.get("teaching_philosophy", "")
    }, None

def update_teacher_profile(email, profile_data):
    """Actualiza el perfil del profesor"""
    db = get_db()
    users_collection = db.users
    teacher_profiles_collection = db.teacher_profiles

    user = users_collection.find_one({"email": email, "role": "teacher"})
    if not user:
        return False, "Usuario no encontrado o no es profesor"

    update_data = {
        "specialties": profile_data.get("specialties"),
        "education": profile_data.get("education"),
        "teaching_experience": profile_data.get("teaching_experience"),
        "certifications": profile_data.get("certifications"),
        "biography": profile_data.get("biography"),
        "teaching_philosophy": profile_data.get("teaching_philosophy"),
        "updated_at": datetime.now()
    }
    # Eliminar campos None
    update_data = {k: v for k, v in update_data.items() if v is not None}

    try:
        result = teacher_profiles_collection.update_one(
            {"user_id": user["_id"]},
            {"$set": update_data},
            upsert=True
        )
        return True, "Perfil actualizado exitosamente"
    except Exception as e:
        return False, str(e)

def get_student_profile(email):
    """Obtiene el perfil del estudiante"""
    db = get_db()
    users_collection = db.users
    student_profiles_collection = db.student_profiles

    user = users_collection.find_one({"email": email, "role": "student"})
    if not user:
        return None, "Usuario no encontrado o no es estudiante"

    profile = student_profiles_collection.find_one({"user_id": user["_id"]})
    if not profile:
        return None, "Perfil no encontrado"

    return {
        "id": str(profile["_id"]),
        "academic_level": profile.get("academic_level", ""),
        "grade_average": profile.get("grade_average", 0.0),
        "interests": profile.get("interests", []),
        "learning_style": profile.get("learning_style", ""),
        "preferred_subjects": profile.get("preferred_subjects", []),
        "extracurricular_activities": profile.get("extracurricular_activities", []),
        "parent_contact": profile.get("parent_contact", {})
    }, None

def update_student_profile(email, profile_data):
    """Actualiza el perfil del estudiante"""
    db = get_db()
    users_collection = db.users
    student_profiles_collection = db.student_profiles

    user = users_collection.find_one({"email": email, "role": "student"})
    if not user:
        return False, "Usuario no encontrado o no es estudiante"

    update_data = {
        "academic_level": profile_data.get("academic_level"),
        "grade_average": profile_data.get("grade_average"),
        "interests": profile_data.get("interests"),
        "learning_style": profile_data.get("learning_style"),
        "preferred_subjects": profile_data.get("preferred_subjects"),
        "extracurricular_activities": profile_data.get("extracurricular_activities"),
        "parent_contact": profile_data.get("parent_contact"),
        "updated_at": datetime.now()
    }
    # Eliminar campos None
    update_data = {k: v for k, v in update_data.items() if v is not None}

    try:
        result = student_profiles_collection.update_one(
            {"user_id": user["_id"]},
            {"$set": update_data},
            upsert=True
        )
        return True, "Perfil actualizado exitosamente"
    except Exception as e:
        return False, str(e) 