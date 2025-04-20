from datetime import datetime
from bson import ObjectId
from typing import List, Dict, Optional, Any

class ResourceFolder:
    """
    Modelo para representar una carpeta de recursos.
    Una carpeta puede contener recursos y puede tener una carpeta padre.
    """
    def __init__(
        self,
        name: str,
        created_by: str,
        description: Optional[str] = None,
        parent_id: Optional[str] = None,
        metadata: Optional[Dict[str, Any]] = None,
        created_at: Optional[datetime] = None,
        updated_at: Optional[datetime] = None,
        _id: Optional[ObjectId] = None
    ):
        self._id = _id or ObjectId()
        self.name = name
        self.description = description
        self.created_by = ObjectId(created_by)
        self.parent_id = ObjectId(parent_id) if parent_id else None
        self.metadata = metadata or {}
        self.created_at = created_at or datetime.now()
        self.updated_at = updated_at or datetime.now()

    def to_dict(self) -> Dict[str, Any]:
        """Convierte el objeto a un diccionario para almacenamiento en MongoDB"""
        result = {
            "_id": self._id,
            "name": self.name,
            "created_by": self.created_by,
            "created_at": self.created_at,
            "updated_at": self.updated_at
        }
        
        if self.description:
            result["description"] = self.description
            
        if self.parent_id:
            result["parent_id"] = self.parent_id
            
        if self.metadata:
            result["metadata"] = self.metadata
            
        return result

class Resource:
    """
    Modelo para representar un recurso educativo.
    Un recurso puede estar en una carpeta y tiene un tipo (pdf, video, audio, etc.)
    """
    def __init__(
        self,
        name: str,
        type: str,
        url: str,
        created_by: str,
        description: Optional[str] = None,
        folder_id: Optional[str] = None,
        tags: Optional[List[str]] = None,
        size: Optional[int] = None,
        duration: Optional[int] = None,
        thumbnail_url: Optional[str] = None,
        is_external: bool = False,
        metadata: Optional[Dict[str, Any]] = None,
        created_at: Optional[datetime] = None,
        updated_at: Optional[datetime] = None,
        _id: Optional[ObjectId] = None
    ):
        self._id = _id or ObjectId()
        self.name = name
        self.type = type
        self.url = url
        self.description = description
        self.created_by = ObjectId(created_by)
        self.folder_id = ObjectId(folder_id) if folder_id else None
        self.tags = tags or []
        self.size = size
        self.duration = duration
        self.thumbnail_url = thumbnail_url
        self.is_external = is_external
        self.metadata = metadata or {}
        self.created_at = created_at or datetime.now()
        self.updated_at = updated_at or datetime.now()

    def to_dict(self) -> Dict[str, Any]:
        """Convierte el objeto a un diccionario para almacenamiento en MongoDB"""
        result = {
            "_id": self._id,
            "name": self.name,
            "type": self.type,
            "url": self.url,
            "created_by": self.created_by,
            "tags": self.tags,
            "is_external": self.is_external,
            "created_at": self.created_at,
            "updated_at": self.updated_at
        }
        
        if self.description:
            result["description"] = self.description
            
        if self.folder_id:
            result["folder_id"] = self.folder_id
            
        if self.size is not None:
            result["size"] = self.size
            
        if self.duration is not None:
            result["duration"] = self.duration
            
        if self.thumbnail_url:
            result["thumbnail_url"] = self.thumbnail_url
            
        if self.metadata:
            result["metadata"] = self.metadata
            
        return result 