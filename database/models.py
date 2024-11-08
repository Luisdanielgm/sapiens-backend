from bson import ObjectId
from datetime import datetime

# Nuevas colecciones necesarias:

# institutes
{
    "_id": ObjectId,
    "name": str,
    "address": str,
    "phone": str,
    "email": str,
    "website": str,
    "created_at": datetime,
    "status": str  # "active", "pending", "inactive"
}

# institute_members
{
    "_id": ObjectId,
    "institute_id": ObjectId,
    "user_id": ObjectId,
    "role": str,  # "institute_admin", "teacher"
    "joined_at": datetime
}

# institute_invitations
{
    "_id": ObjectId,
    "institute_id": ObjectId,
    "inviter_id": ObjectId,  # ID del admin que invita
    "invitee_id": ObjectId,  # ID del usuario invitado
    "status": str,  # "pending", "accepted", "rejected"
    "created_at": datetime
}

# classroom_invitations
{
    "_id": ObjectId,
    "classroom_id": ObjectId,
    "inviter_id": ObjectId,  # ID del profesor que invita
    "invitee_id": ObjectId,  # ID del estudiante invitado
    "status": str,  # "pending", "accepted", "rejected"
    "created_at": datetime
}

# educational_programs
{
    "_id": ObjectId,
    "institute_id": ObjectId,
    "name": str,
    "type": str,  # "primary", "highschool", "undergraduate", "postgraduate", "other"
    "created_at": datetime
}

# academic_periods
{
    "_id": ObjectId,
    "program_id": ObjectId,
    "name": str,  # "5to", "6to", "1er", etc
    "type": str,  # "año", "grado", "semestre"
    "created_at": datetime
}

# sections
{
    "_id": ObjectId,
    "program_id": ObjectId,
    "period_id": ObjectId,
    "name": str,  # "A", "B", "C"
    "created_at": datetime
}

# subjects
{
    "_id": ObjectId,
    "program_id": ObjectId,
    "period_id": ObjectId,
    "name": str,  # "Matemáticas", "Historia", "Química"
    "created_at": datetime
}

# users
{
    "_id": ObjectId,
    "email": str,
    "name": str,
    "picture": str,
    "birthdate": str,
    "role": str,  # "admin", "institute_admin", "teacher", "student"
    "created_at": datetime
}

# classrooms
{
    "_id": ObjectId,
    "name": str,
    "period_id": ObjectId,
    "section_id": ObjectId,
    "subject_id": ObjectId,
    "created_at": datetime
}

# contents
{
    "_id": ObjectId,
    "classroom_id": ObjectId,
    "student_id": ObjectId,
    "content": str,
    "created_at": datetime,
    "updated_at": datetime
}

# cognitive_profiles
{
    "_id": ObjectId,
    "student_id": ObjectId,
    "profile": str,  # JSON string con el perfil cognitivo
    "created_at": datetime,
    "updated_at": datetime
}

# teacher_profiles
{
    "_id": ObjectId,
    "user_id": ObjectId,
    "specialties": [str],  # ["Matemáticas", "Física", etc.]
    "education": [{
        "degree": str,     # "Licenciatura", "Maestría", "Doctorado"
        "field": str,      # "Educación", "Matemáticas", etc.
        "institution": str,
        "year": int
    }],
    "teaching_experience": int,  # años de experiencia
    "certifications": [{
        "name": str,
        "institution": str,
        "year": int
    }],
    "biography": str,
    "teaching_philosophy": str,
    "created_at": datetime,
    "updated_at": datetime
}

# student_profiles
{
    "_id": ObjectId,
    "user_id": ObjectId,
    "academic_level": str,  # "Primaria", "Secundaria", "Universidad"
    "grade_average": float,
    "interests": [str],
    "learning_style": str,  # "Visual", "Auditivo", "Kinestésico"
    "preferred_subjects": [str],
    "extracurricular_activities": [str],
    "parent_contact": {
        "name": str,
        "relationship": str,
        "phone": str,
        "email": str
    },
    "created_at": datetime,
    "updated_at": datetime
}

# study_plans (Plan de estudios/contenido)
{
    "_id": ObjectId,
    "classroom_id": ObjectId,
    "name": str,
    "description": str,
    "document_url": str,  # URL del documento original (PDF/Excel)
    "created_at": datetime,
    "updated_at": datetime
}

# modules (Lapsos o módulos del plan de estudio)
{
    "_id": ObjectId,
    "study_plan_id": ObjectId,
    "name": str,  # "Primer Lapso", "Módulo 1", etc.
    "start_date": datetime,
    "end_date": datetime,
    "objectives": [str],
    "created_at": datetime
}

# topics (Temas específicos por módulo)
{
    "_id": ObjectId,
    "module_id": ObjectId,
    "name": str,
    "description": str,
    "date_range": {
        "start_date": datetime,
        "end_date": datetime
    },
    "class_schedule": [{
        "week_start": datetime,  # Inicio de la semana
        "sessions": [{
            "date": datetime,    # Fecha específica de la clase
            "start_time": str,   # "08:00"
            "end_time": str,     # "09:30"
            "description": str   # "Introducción al tema"
        }]
    }],
    "resources": [{
        "type": str,  # "video", "image", "podcast", "document"
        "url": str,
        "description": str
    }],
    "created_at": datetime
}

# evaluation_plans
{
    "_id": ObjectId,
    "classroom_ids": [ObjectId],  # Puede aplicar a varios salones
    "document_url": str,
    "created_at": datetime,
    "updated_at": datetime
}

# evaluations
{
    "_id": ObjectId,
    "evaluation_plan_id": ObjectId,
    "module_id": ObjectId,
    "topic_ids": [ObjectId],  # Puede evaluar varios temas
    "name": str,
    "description": str,
    "methodology": str,
    "weight": float,  # Ponderación
    "date": datetime,
    "created_at": datetime
}

# student_evaluations
{
    "_id": ObjectId,
    "evaluation_id": ObjectId,
    "student_id": ObjectId,
    "score": float,
    "feedback": str,
    "created_at": datetime
}

# virtual_modules (Módulos virtuales generados)
{
    "_id": ObjectId,
    "module_id": ObjectId,
    "name": str,
    "description": str,
    "created_by": ObjectId,  # ID del profesor
    "content": str,  # Contenido general del módulo
    "created_at": datetime
}

# personalized_modules (Módulos personalizados para cada estudiante)
{
    "_id": ObjectId,
    "virtual_module_id": ObjectId,
    "student_id": ObjectId,
    "status": str,  # "in_progress", "completed"
    "progress": float,  # Porcentaje de progreso
    "adaptive_content": [{
        "type": str,  # "theory", "exercise", "game", "story"
        "content": str,
        "completed": bool,
        "score": float,
        "attempts": int
    }],
    "created_at": datetime,
    "updated_at": datetime
}

# module_resources (Recursos adicionales cargados por el profesor)
{
    "_id": ObjectId,
    "virtual_module_id": ObjectId,
    "type": str,  # "video", "image", "podcast", etc.
    "learning_style": str,  # "visual", "auditivo", etc.
    "url": str,
    "description": str,
    "created_at": datetime
}
