from datetime import datetime
from bson import ObjectId
from typing import Dict, Optional, List

class User:
    def __init__(self,
                 email: str,
                 name: str,
                 picture: str,
                 role: str,
                 birth_date: Optional[str] = None,
                 status: str = "active",
                 institute_name: Optional[str] = None):
        self.email = email
        self.name = name
        self.picture = picture
        self.role = role.upper()
        self.birth_date = birth_date
        self.status = status
        self.institute_name = institute_name
        self.created_at = datetime.now()

    def to_dict(self) -> dict:
        return {
            "email": self.email,
            "name": self.name,
            "picture": self.picture,
            "role": self.role,
            "birth_date": self.birth_date,
            "status": self.status,
            "created_at": self.created_at
        }

class CognitiveProfile:
    def __init__(self,
                 user_id: str,
                 learning_style: Dict[str, int] = None,
                 diagnosis: str = "",
                 cognitive_strengths: List[str] = None,
                 cognitive_difficulties: List[str] = None,
                 personal_context: str = "",
                 recommended_strategies: List[str] = None):
        self.user_id = ObjectId(user_id)
        self.learning_style = learning_style or {
            "visual": 0,
            "kinesthetic": 0,
            "auditory": 0,
            "readingWriting": 0
        }
        self.diagnosis = diagnosis
        self.cognitive_strengths = cognitive_strengths or []
        self.cognitive_difficulties = cognitive_difficulties or []
        self.personal_context = personal_context
        self.recommended_strategies = recommended_strategies or []
        self.created_at = datetime.now()

    def to_dict(self) -> dict:
        return {
            "user_id": self.user_id,
            "learning_style": self.learning_style,
            "diagnosis": self.diagnosis,
            "cognitive_strengths": self.cognitive_strengths,
            "cognitive_difficulties": self.cognitive_difficulties,
            "personal_context": self.personal_context,
            "recommended_strategies": self.recommended_strategies,
            "created_at": self.created_at
        }