from datetime import datetime
from bson import ObjectId
from typing import List, Dict, Optional, Any, Tuple

class TopicResource:
    """
    Modelo para relacionar temas con recursos.
    Permite asociar recursos a temas con metadatos específicos de la relación.
    """
    def __init__(self,
                 topic_id: str,
                 resource_id: str,
                 relevance_score: float = 0.5,
                 recommended_for: List[str] = None,
                 usage_context: str = "supplementary",
                 content_types: List[str] = None,
                 created_by: str = None,
                 status: str = "active"):
        self.topic_id = ObjectId(topic_id)
        self.resource_id = ObjectId(resource_id)
        self.relevance_score = relevance_score
        self.recommended_for = recommended_for or []
        self.usage_context = usage_context
        self.content_types = content_types or []
        self.created_by = ObjectId(created_by) if created_by else None
        self.created_at = datetime.now()
        self.status = status

    def to_dict(self) -> dict:
        """Convierte el objeto a un diccionario para almacenamiento en MongoDB"""
        result = {
            "topic_id": self.topic_id,
            "resource_id": self.resource_id,
            "relevance_score": self.relevance_score,
            "recommended_for": self.recommended_for,
            "usage_context": self.usage_context,
            "content_types": self.content_types,
            "created_at": self.created_at,
            "status": self.status
        }
        
        if self.created_by:
            result["created_by"] = self.created_by
            
        return result 