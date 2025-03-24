from datetime import datetime
from bson import ObjectId
from typing import Dict, List, Optional

class WebSearchResult:
    """
    Representa un resultado de búsqueda web de ValueSerp.
    """
    def __init__(self,
                 title: str,
                 url: str,
                 snippet: str,
                 position: int = None,
                 domain: str = None,
                 metadata: Dict = None,
                 knowledge_graph: Dict = None,
                 videos: List[Dict] = None,
                 related_searches: List[Dict] = None):
        self.title = title
        self.url = url
        self.snippet = snippet
        self.position = position
        self.domain = domain
        self.metadata = metadata or {}
        self.knowledge_graph = knowledge_graph
        self.videos = videos
        self.related_searches = related_searches
        self.created_at = datetime.now()
        
    def to_dict(self) -> dict:
        return {
            "title": self.title,
            "url": self.url,
            "snippet": self.snippet,
            "position": self.position,
            "domain": self.domain,
            "metadata": self.metadata,
            "knowledge_graph": self.knowledge_graph,
            "videos": self.videos,
            "related_searches": self.related_searches,
            "created_at": self.created_at
        }

class SearchProvider:
    """
    Configuración de un proveedor de búsqueda.
    """
    def __init__(self,
                 name: str,
                 provider_type: str = "valueserp",
                 api_key: str = None,
                 config: Dict = None,
                 status: str = "active"):
        self.name = name
        self.provider_type = provider_type
        self.api_key = api_key
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
            "api_key": self.api_key,
            "config": self.config,
            "status": self.status,
            "created_at": self.created_at,
            "updated_at": self.updated_at,
            "last_used": self.last_used,
            "usage_count": self.usage_count
        } 