# Estados generales
STATUS = {
    "ACTIVE": "active",
    "PENDING": "pending",
    "INACTIVE": "inactive",
    "DRAFT": "draft",
    "APPROVED": "approved",
    "RETIRED": "retired"
}

# Configuración de la aplicación
APP_NAME = "sapiens-backend"
APP_PREFIX = "/api"

# Roles de usuario
ROLES = {
    "STUDENT": "student",
    "TEACHER": "teacher",
    "INSTITUTE_ADMIN": "institute_admin",
    "ADMIN": "admin"
}

# Types of workspaces
WORKSPACE_TYPES = {
    "INSTITUTE": "INSTITUTE",
    "INDIVIDUAL_TEACHER": "INDIVIDUAL_TEACHER",
    "INDIVIDUAL_STUDENT": "INDIVIDUAL_STUDENT",
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

# Tipos de recursos
RESOURCE_TYPES = {
    "PDF": "pdf",
    "VIDEO": "video",
    "AUDIO": "audio",
    "IMAGE": "image",
    "LINK": "link",
    "DOCUMENT": "document",
    "PRESENTATION": "presentation",
    "SPREADSHEET": "spreadsheet",
    "OTHER": "other"
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
    "TOPIC_CONTENTS": "topic_contents",  # Actualizado para sistema unificado
    
    # Virtual
    "VIRTUAL_MODULES": "virtual_modules",
    "VIRTUAL_TOPICS": "virtual_topics",
    "VIRTUAL_TOPIC_CONTENTS": "virtual_topic_contents",  # Nueva - contenido personalizado
    "QUIZZES": "quizzes",  # Legacy - mantener durante transición
    "QUIZ_RESULTS": "quiz_results",  # Legacy - mantener durante transición
    
    # Sistema de contenido unificado (NUEVO)
    "CONTENT_TYPES_COLL": "content_types",
    "CONTENT_RESULTS": "content_results",
    
    # Analíticas
    "STUDENT_PERFORMANCE": "student_performance",
    "CLASS_STATISTICS": "class_statistics",
    "INSTITUTE_STATISTICS": "institute_statistics",
    
    # Recursos
    "RESOURCES": "resources",
    "RESOURCE_FOLDERS": "resource_folders",
    
    # Sistema de monitoreo de IA
    "AI_API_CALLS": "ai_api_calls",
    "AI_MONITORING_CONFIG": "ai_monitoring_config",
    "AI_MONITORING_ALERTS": "ai_monitoring_alerts"
}
