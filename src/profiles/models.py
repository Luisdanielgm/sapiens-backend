from datetime import datetime
from typing import Dict, List, Optional
from bson import ObjectId


class TeacherProfile:
    """
    Modelo que representa el perfil específico de un profesor.
    Contiene información detallada sobre sus especialidades, educación y experiencia.
    """
    def __init__(self,
                user_id: str,
                specialties: List[str] = None,
                education: List[Dict] = None,
                teaching_experience: int = 0,
                bio: str = "",
                created_at: datetime = None,
                updated_at: datetime = None):
        self.user_id = ObjectId(user_id) if isinstance(user_id, str) else user_id
        self.specialties = specialties or []
        self.education = education or []
        self.teaching_experience = teaching_experience
        self.bio = bio
        self.created_at = created_at or datetime.now()
        self.updated_at = updated_at or datetime.now()
        
    def to_dict(self) -> dict:
        return {
            "user_id": self.user_id,
            "specialties": self.specialties,
            "education": self.education,
            "teaching_experience": self.teaching_experience,
            "bio": self.bio,
            "created_at": self.created_at,
            "updated_at": self.updated_at
        }


class StudentProfile:
    """
    Modelo que representa el perfil específico de un estudiante.
    Contiene información detallada sobre su formación, intereses y estilo de aprendizaje.
    """
    def __init__(self,
                user_id: str,
                educational_background: str = "",
                interests: List[str] = None,
                preferred_learning_style: str = "",
                created_at: datetime = None,
                updated_at: datetime = None):
        self.user_id = ObjectId(user_id) if isinstance(user_id, str) else user_id
        self.educational_background = educational_background
        self.interests = interests or []
        self.preferred_learning_style = preferred_learning_style
        self.created_at = created_at or datetime.now()
        self.updated_at = updated_at or datetime.now()
        
    def to_dict(self) -> dict:
        return {
            "user_id": self.user_id,
            "educational_background": self.educational_background,
            "interests": self.interests,
            "preferred_learning_style": self.preferred_learning_style,
            "created_at": self.created_at,
            "updated_at": self.updated_at
        }


class AdminProfile:
    """
    Modelo que representa el perfil específico de un administrador general del sistema.
    Contiene información sobre sus responsabilidades y áreas de supervisión para toda la aplicación.
    """
    def __init__(self,
                user_id: str,
                responsibilities: List[str] = None,
                supervised_areas: List[str] = None,
                created_at: datetime = None,
                updated_at: datetime = None):
        self.user_id = ObjectId(user_id) if isinstance(user_id, str) else user_id
        self.responsibilities = responsibilities or []
        self.supervised_areas = supervised_areas or []
        self.created_at = created_at or datetime.now()
        self.updated_at = updated_at or datetime.now()
        
    def to_dict(self) -> dict:
        return {
            "user_id": self.user_id,
            "responsibilities": self.responsibilities,
            "supervised_areas": self.supervised_areas,
            "created_at": self.created_at,
            "updated_at": self.updated_at
        }


class InstituteAdminProfile:
    """
    Modelo que representa el perfil específico de un administrador de instituto.
    Contiene información sobre responsabilidades y permisos específicos para administrar un instituto.
    """
    def __init__(self,
                user_id: str,
                institute_id: str,
                role_in_institute: str = "INSTITUTE_ADMIN",
                institute_permissions: List[str] = None,
                responsibilities: List[str] = None,
                created_at: datetime = None,
                updated_at: datetime = None):
        self.user_id = ObjectId(user_id) if isinstance(user_id, str) else user_id
        self.institute_id = ObjectId(institute_id) if isinstance(institute_id, str) else institute_id
        self.role_in_institute = role_in_institute
        self.institute_permissions = institute_permissions or ["manage_members", "manage_courses", "view_reports"]
        self.responsibilities = responsibilities or []
        self.created_at = created_at or datetime.now()
        self.updated_at = updated_at or datetime.now()
        
    def to_dict(self) -> dict:
        return {
            "user_id": self.user_id,
            "institute_id": self.institute_id,
            "role_in_institute": self.role_in_institute,
            "institute_permissions": self.institute_permissions,
            "responsibilities": self.responsibilities,
            "created_at": self.created_at,
            "updated_at": self.updated_at
        }


class InstituteProfile:
    """
    Modelo que representa el perfil de un instituto educativo.
    Contiene información sobre el instituto en sí, no sobre un usuario.
    """
    def __init__(self,
                institute_id: str,
                name: str,
                address: str = "",
                contact_email: str = "",
                contact_phone: str = "",
                description: str = "",
                foundation_date: datetime = None,
                website: str = "",
                social_media: Dict[str, str] = None,
                educational_levels: List[str] = None,
                number_of_students: int = 0,
                number_of_teachers: int = 0,
                status: str = "active",
                created_at: datetime = None,
                updated_at: datetime = None):
        self.institute_id = ObjectId(institute_id) if isinstance(institute_id, str) else institute_id
        self.name = name
        self.address = address
        self.contact_email = contact_email
        self.contact_phone = contact_phone
        self.description = description
        self.foundation_date = foundation_date
        self.website = website
        self.social_media = social_media or {}
        self.educational_levels = educational_levels or []
        self.number_of_students = number_of_students
        self.number_of_teachers = number_of_teachers
        self.status = status
        self.created_at = created_at or datetime.now()
        self.updated_at = updated_at or datetime.now()
        
    def to_dict(self) -> dict:
        return {
            "institute_id": self.institute_id,
            "name": self.name,
            "address": self.address,
            "contact_email": self.contact_email,
            "contact_phone": self.contact_phone,
            "description": self.description,
            "foundation_date": self.foundation_date,
            "website": self.website,
            "social_media": self.social_media,
            "educational_levels": self.educational_levels,
            "number_of_students": self.number_of_students,
            "number_of_teachers": self.number_of_teachers,
            "status": self.status,
            "created_at": self.created_at,
            "updated_at": self.updated_at
        }


class CognitiveProfile:
    """
    Modelo que representa el perfil cognitivo de un estudiante.
    Contiene información sobre su estilo de aprendizaje, fortalezas y dificultades cognitivas.
    """
    def __init__(self,
                user_id: str,
                learning_style: Dict = None,
                diagnosis: List[str] = None,
                cognitive_strengths: List[str] = None,
                cognitive_difficulties: List[str] = None,
                personal_context: Dict = None,
                recommended_strategies: List[Dict] = None,
                created_at: datetime = None,
                updated_at: datetime = None,
                profile: Dict = None):
        self.user_id = ObjectId(user_id) if isinstance(user_id, str) else user_id
        self.learning_style = learning_style or {
            "visual": 0,
            "auditory": 0,
            "reading_writing": 0,
            "kinesthetic": 0
        }
        self.diagnosis = diagnosis or []
        self.cognitive_strengths = cognitive_strengths or []
        self.cognitive_difficulties = cognitive_difficulties or []
        self.personal_context = personal_context or {}
        self.recommended_strategies = recommended_strategies or []
        self.created_at = created_at or datetime.now()
        self.updated_at = updated_at or datetime.now()
        self.profile = profile or {}  # Campo para almacenar la representación JSON completa
        
    def to_dict(self) -> dict:
        return {
            "user_id": self.user_id,
            "learning_style": self.learning_style,
            "diagnosis": self.diagnosis,
            "cognitive_strengths": self.cognitive_strengths,
            "cognitive_difficulties": self.cognitive_difficulties,
            "personal_context": self.personal_context,
            "recommended_strategies": self.recommended_strategies,
            "created_at": self.created_at,
            "updated_at": self.updated_at,
            "profile": self.profile
        } 