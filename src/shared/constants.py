# Estados generales
STATUS = {
    "ACTIVE": "active",
    "PENDING": "pending",
    "INACTIVE": "inactive",
    "DRAFT": "draft",
    "APPROVED": "approved",
    "RETIRED": "retired"
}

# Roles de usuario
ROLES = {
    "ADMIN": "ADMIN",               # Administrador de toda la plataforma
    "INSTITUTE_ADMIN": "INSTITUTE_ADMIN",  # Administrador de instituto
    "TEACHER": "TEACHER",           # Profesor
    "STUDENT": "STUDENT"            # Estudiante
}

# Niveles de dificultad
DIFFICULTY_LEVELS = {
    "BASIC": "básico",
    "INTERMEDIATE": "intermedio",
    "ADVANCED": "avanzado"
}

# Estados de invitación
INVITATION_STATUS = {
    "PENDING": "pending",
    "ACCEPTED": "accepted",
    "REJECTED": "rejected"
}

# Estados de membresía
MEMBER_STATUS = {
    "ACTIVE": "active",
    "INACTIVE": "inactive",
    "SUSPENDED": "suspended"
}

# Tipos de contenido de clase
CONTENT_TYPES = {
    "ANNOUNCEMENT": "announcement",
    "MATERIAL": "material",
    "ASSIGNMENT": "assignment",
    "QUIZ": "quiz"
}

# Tipos de período académico
PERIOD_TYPES = {
    "YEAR": "year",
    "SEMESTER": "semester",
    "TRIMESTER": "trimester",
    "QUARTER": "quarter"
}

# Configuración de paginación
PAGINATION = {
    "DEFAULT_PAGE": 1,
    "DEFAULT_PER_PAGE": 10,
    "MAX_PER_PAGE": 100
}

# Mensajes de error comunes
ERROR_MESSAGES = {
    "NOT_FOUND": "Recurso no encontrado",
    "UNAUTHORIZED": "No autorizado",
    "FORBIDDEN": "Acceso denegado",
    "INVALID_INPUT": "Datos de entrada inválidos",
    "INTERNAL_ERROR": "Error interno del servidor"
}

# Nombres de colecciones MongoDB
COLLECTIONS = {
    # Institutos y Programas
    "INSTITUTES": "institutes",
    "INSTITUTE_MEMBERS": "institute_members",
    "EDUCATIONAL_PROGRAMS": "educational_programs",
    
    # Académico
    "ACADEMIC_PERIODS": "academic_periods",
    "SUBPERIODS": "subperiods",
    "SECTIONS": "sections",
    "SUBJECTS": "subjects",
    
    # Invitaciones
    "INSTITUTE_INVITATIONS": "institute_invitations",
    "CLASS_INVITATIONS": "class_invitations",
    "MEMBERSHIP_REQUESTS": "membership_requests",
    
    # Usuarios
    "USERS": "users",
    "COGNITIVE_PROFILES": "cognitive_profiles",
    
    # Clases
    "CLASSES": "classes",
    "CLASS_MEMBERS": "class_members",
    "STUDENT_INDIVIDUAL_CONTENT": "student_individual_content",
    "ATTENDANCE": "attendance",
    
    # Evaluaciones
    "EVALUATIONS": "evaluations",
    "EVALUATION_RESULTS": "evaluation_results",
    
    # Planes de estudio
    "STUDY_PLANS": "study_plans_per_subject",
    "MODULES": "modules",
    "TOPICS": "topics",
    
    # Virtual
    "VIRTUAL_MODULES": "virtual_modules",
    "VIRTUAL_TOPICS": "virtual_topics",
    "VIRTUAL_EVALUATIONS": "virtual_evaluations",
    "VIRTUAL_EVALUATION_RESULTS": "virtual_evaluation_results",
    
    # Analíticas
    "STUDENT_PERFORMANCE": "student_performance",
    "CLASS_STATISTICS": "class_statistics",
    "INSTITUTE_STATISTICS": "institute_statistics"
}