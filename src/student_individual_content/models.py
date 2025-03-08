from datetime import datetime
from typing import Dict, Optional


class StudentIndividualContent:
    """
    Modelo que representa el contenido individual de un estudiante.
    Este contenido puede ser notas, reflexiones, respuestas a preguntas, etc.
    """
    def __init__(self,
                class_id: str,
                student_id: str,
                title: str,
                content: str,
                content_type: str = "text",
                tags: list = None,
                metadata: Optional[Dict] = None,
                status: str = "active"):
        self.class_id = class_id
        self.student_id = student_id
        self.title = title
        self.content = content
        self.content_type = content_type
        self.tags = tags or []
        self.metadata = metadata or {}
        self.status = status
        self.created_at = datetime.now()
        self.updated_at = datetime.now()
        
    def to_dict(self) -> dict:
        return {
            "class_id": self.class_id,
            "student_id": self.student_id,
            "title": self.title,
            "content": self.content,
            "content_type": self.content_type,
            "tags": self.tags,
            "metadata": self.metadata,
            "status": self.status,
            "created_at": self.created_at,
            "updated_at": self.updated_at
        } 