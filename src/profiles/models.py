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
                bio: str = ""):
        self.user_id = ObjectId(user_id) if isinstance(user_id, str) else user_id
        self.specialties = specialties or []
        self.education = education or []
        self.teaching_experience = teaching_experience
        self.bio = bio
        self.created_at = datetime.now()
        self.updated_at = datetime.now()
        
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
                preferred_learning_style: str = ""):
        self.user_id = ObjectId(user_id) if isinstance(user_id, str) else user_id
        self.educational_background = educational_background
        self.interests = interests or []
        self.preferred_learning_style = preferred_learning_style
        self.created_at = datetime.now()
        self.updated_at = datetime.now()
        
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
    Modelo que representa el perfil específico de un administrador.
    Contiene información sobre sus responsabilidades y áreas de supervisión.
    """
    def __init__(self,
                user_id: str,
                responsibilities: List[str] = None,
                supervised_areas: List[str] = None):
        self.user_id = ObjectId(user_id) if isinstance(user_id, str) else user_id
        self.responsibilities = responsibilities or []
        self.supervised_areas = supervised_areas or []
        self.created_at = datetime.now()
        self.updated_at = datetime.now()
        
    def to_dict(self) -> dict:
        return {
            "user_id": self.user_id,
            "responsibilities": self.responsibilities,
            "supervised_areas": self.supervised_areas,
            "created_at": self.created_at,
            "updated_at": self.updated_at
        } 