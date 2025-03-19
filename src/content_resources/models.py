from datetime import datetime
from bson import ObjectId
from typing import Dict, List, Optional

class ProcessedPDF:
    """
    Representa un PDF procesado con su contenido extraído y analizado.
    """
    def __init__(self,
                 title: str,
                 file_path: str,
                 file_size: int,
                 original_filename: str,
                 extracted_text: str,
                 extracted_images: List[Dict] = None,
                 extracted_tables: List[Dict] = None,
                 metadata: Dict = None,
                 creator_id: str = None,
                 tags: List[str] = None):
        self.title = title
        self.file_path = file_path
        self.file_size = file_size
        self.original_filename = original_filename
        self.extracted_text = extracted_text
        self.extracted_images = extracted_images or []
        self.extracted_tables = extracted_tables or []
        self.metadata = metadata or {}
        self.creator_id = ObjectId(creator_id) if creator_id else None
        self.tags = tags or []
        self.created_at = datetime.now()
        self.last_accessed = None
        self.access_count = 0
        self.status = "active"
        
    def to_dict(self) -> dict:
        return {
            "title": self.title,
            "file_path": self.file_path,
            "file_size": self.file_size,
            "original_filename": self.original_filename,
            "extracted_text": self.extracted_text,
            "extracted_images": self.extracted_images,
            "extracted_tables": self.extracted_tables,
            "metadata": self.metadata,
            "creator_id": self.creator_id,
            "tags": self.tags,
            "created_at": self.created_at,
            "last_accessed": self.last_accessed,
            "access_count": self.access_count,
            "status": self.status
        }

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

class DiagramTemplate:
    """
    Plantilla para generación de diagramas.
    """
    def __init__(self,
                 name: str,
                 template_type: str,  # flowchart, mindmap, sequence, etc.
                 template_schema: Dict,
                 sample_code: str,
                 preview_image_url: str = None,
                 description: str = None):
        self.name = name
        self.template_type = template_type
        self.template_schema = template_schema
        self.sample_code = sample_code
        self.preview_image_url = preview_image_url
        self.description = description
        self.created_at = datetime.now()
        self.status = "active"
        
    def to_dict(self) -> dict:
        return {
            "name": self.name,
            "template_type": self.template_type,
            "template_schema": self.template_schema,
            "sample_code": self.sample_code,
            "preview_image_url": self.preview_image_url,
            "description": self.description,
            "created_at": self.created_at,
            "status": self.status
        }

class GeneratedDiagram:
    """
    Diagrama generado a partir de una plantilla o directamente.
    """
    def __init__(self,
                 title: str,
                 diagram_type: str,  # flowchart, mindmap, sequence, etc.
                 content: str,
                 image_url: str = None,
                 topic_id: str = None,
                 template_id: str = None,
                 creator_id: str = None,
                 metadata: Dict = None):
        self.title = title
        self.diagram_type = diagram_type
        self.content = content
        self.image_url = image_url
        self.topic_id = ObjectId(topic_id) if topic_id else None
        self.template_id = ObjectId(template_id) if template_id else None
        self.creator_id = ObjectId(creator_id) if creator_id else None
        self.metadata = metadata or {}
        self.created_at = datetime.now()
        self.updated_at = datetime.now()
        self.status = "active"
        
    def to_dict(self) -> dict:
        return {
            "title": self.title,
            "diagram_type": self.diagram_type,
            "content": self.content,
            "image_url": self.image_url,
            "topic_id": self.topic_id,
            "template_id": self.template_id,
            "creator_id": self.creator_id,
            "metadata": self.metadata,
            "created_at": self.created_at,
            "updated_at": self.updated_at,
            "status": self.status
        }

class SearchProvider:
    """
    Configuración de un proveedor de búsqueda web.
    """
    def __init__(self,
                 name: str,
                 provider_type: str,  # google_cse, serp_api
                 api_key: str = None,
                 search_engine_id: str = None,
                 config: Dict = None,
                 status: str = "active"):
        self.name = name
        self.provider_type = provider_type
        self.api_key = api_key
        self.search_engine_id = search_engine_id  # Solo para Google CSE
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
            "search_engine_id": self.search_engine_id,
            "config": self.config,
            "status": self.status,
            "created_at": self.created_at,
            "updated_at": self.updated_at,
            "last_used": self.last_used,
            "usage_count": self.usage_count
        } 