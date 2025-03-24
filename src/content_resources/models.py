from datetime import datetime
from bson import ObjectId
from typing import Dict, List, Optional

class WebSearchResult:
    """
    Representa un resultado de búsqueda web.
    """
    def __init__(self,
                 title: str,
                 url: str,
                 snippet: str,
                 result_type: str,  # webpage, image, video, pdf, audio
                 topic_id: str = None,
                 metadata: Dict = None,
                 tags: List[str] = None,
                 relevance_score: float = 0.0):
        self.title = title
        self.url = url
        self.snippet = snippet
        self.result_type = result_type
        self.topic_id = ObjectId(topic_id) if topic_id else None
        self.metadata = metadata or {}
        self.tags = tags or []
        self.relevance_score = relevance_score
        self.created_at = datetime.now()
        self.is_saved = False
        
    def to_dict(self) -> dict:
        return {
            "title": self.title,
            "url": self.url,
            "snippet": self.snippet,
            "result_type": self.result_type,
            "topic_id": self.topic_id,
            "metadata": self.metadata,
            "tags": self.tags,
            "relevance_score": self.relevance_score,
            "created_at": self.created_at,
            "is_saved": self.is_saved
        }

class SearchProvider:
    """
    Configuración de un proveedor de búsqueda SearXNG.
    """
    def __init__(self,
                 name: str,
                 provider_type: str = "searxng",
                 instances: List[str] = None,
                 config: Dict = None,
                 status: str = "active"):
        self.name = name
        self.provider_type = provider_type
        self.instances = instances or []  # Lista de instancias para SearXNG
        self.config = config or {}
        self.status = status
        self.created_at = datetime.now()
        self.updated_at = datetime.now()
        self.last_used = None
        self.usage_count = 0
        
    def to_dict(self) -> dict:
        return {
            "name": self.name,
            "provider_type": self.provider_type,
            "instances": self.instances,
            "config": self.config,
            "status": self.status,
            "created_at": self.created_at,
            "updated_at": self.updated_at,
            "last_used": self.last_used,
            "usage_count": self.usage_count
        } 