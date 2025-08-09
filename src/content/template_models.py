import logging
from datetime import datetime
from bson import ObjectId
from typing import Dict, List, Optional, Union
from pydantic import BaseModel, Field

class Template:
    """
    Modelo para plantillas globales de contenido educativo HTML.
    Representa una plantilla reutilizable que puede ser instanciada para diferentes temas.
    """
    def __init__(self,
                 name: str,
                 owner_id: str,
                 html: str = "",
                 engine: str = "html",
                 version: str = "1.0.0",
                 scope: str = "private",  # private, org, public
                 status: str = "draft",   # draft, usable, certified
                 fork_of: Optional[str] = None,
                 props_schema: Optional[Dict] = None,
                 defaults: Optional[Dict] = None,
                 baseline_mix: Optional[Dict] = None,  # Mix VARK base: {V:60,A:10,K:20,R:10}
                 capabilities: Optional[Dict] = None,  # {audio: bool, microphone: bool, camera: bool, etc.}
                 style_tags: List[str] = None,
                 subject_tags: List[str] = None,
                 description: str = "",
                 _id: Optional[ObjectId] = None,
                 created_at: Optional[datetime] = None,
                 updated_at: Optional[datetime] = None,
                 **kwargs):
        self._id = _id or ObjectId()
        self.name = name
        self.owner_id = ObjectId(owner_id)
        self.html = html
        self.engine = engine
        self.version = version
        self.scope = scope
        self.status = status
        self.fork_of = ObjectId(fork_of) if fork_of else None
        self.props_schema = props_schema or {}
        self.defaults = defaults or {}
        self.baseline_mix = baseline_mix or {"V": 25, "A": 25, "K": 25, "R": 25}
        self.capabilities = capabilities or {}
        self.style_tags = style_tags or []
        self.subject_tags = subject_tags or []
        self.description = description
        self.created_at = created_at or datetime.now()
        self.updated_at = updated_at or datetime.now()
        
        # Campos adicionales para tracking
        self.personalization = {
            "is_extracted": False,  # Si ya se extrajeron los marcadores
            "last_extraction": None,
            "extraction_version": None
        }
        
        if kwargs:
            logging.warning(f"Template received unexpected arguments, which were ignored: {list(kwargs.keys())}")

    def to_dict(self) -> dict:
        data = {
            "_id": self._id,
            "name": self.name,
            "owner_id": self.owner_id,
            "html": self.html,
            "engine": self.engine,
            "version": self.version,
            "scope": self.scope,
            "status": self.status,
            "props_schema": self.props_schema,
            "defaults": self.defaults,
            "baseline_mix": self.baseline_mix,
            "capabilities": self.capabilities,
            "style_tags": self.style_tags,
            "subject_tags": self.subject_tags,
            "description": self.description,
            "created_at": self.created_at,
            "updated_at": self.updated_at,
            "personalization": self.personalization
        }
        if self.fork_of:
            data["fork_of"] = self.fork_of
        return data

    def update_extraction_info(self):
        """Actualiza la información de extracción de marcadores"""
        self.personalization["is_extracted"] = True
        self.personalization["last_extraction"] = datetime.now()
        self.personalization["extraction_version"] = self.version
        self.updated_at = datetime.now()

class TemplateInstance:
    """
    Instancia de una plantilla ligada a un Topic específico.
    Contiene los valores concretos de los parámetros de la plantilla.
    """
    def __init__(self,
                 template_id: str,
                 template_version: str,
                 topic_id: str,
                 props: Optional[Dict] = None,
                 assets: List[Dict] = None,
                 learning_mix: Optional[Dict] = None,
                 status: str = "draft",  # draft, active
                 _id: Optional[ObjectId] = None,
                 created_at: Optional[datetime] = None,
                 updated_at: Optional[datetime] = None,
                 **kwargs):
        self._id = _id or ObjectId()
        self.template_id = ObjectId(template_id)
        self.template_version = template_version
        self.topic_id = ObjectId(topic_id)
        self.props = props or {}
        self.assets = assets or []  # Lista de {id, name, url, type}
        
        # Learning mix puede ser automático o manual
        if learning_mix and "mode" in learning_mix:
            self.learning_mix = learning_mix
        else:
            self.learning_mix = {
                "mode": "auto",  # auto | manual
                "values": learning_mix or {"V": 25, "A": 25, "K": 25, "R": 25}
            }
        
        self.status = status
        self.created_at = created_at or datetime.now()
        self.updated_at = updated_at or datetime.now()
        
        if kwargs:
            logging.warning(f"TemplateInstance received unexpected arguments, which were ignored: {list(kwargs.keys())}")

    def to_dict(self) -> dict:
        return {
            "_id": self._id,
            "template_id": self.template_id,
            "template_version": self.template_version,
            "topic_id": self.topic_id,
            "props": self.props,
            "assets": self.assets,
            "learning_mix": self.learning_mix,
            "status": self.status,
            "created_at": self.created_at,
            "updated_at": self.updated_at
        }

    def update_props(self, new_props: Dict):
        """Actualiza las propiedades de la instancia"""
        self.props.update(new_props)
        self.updated_at = datetime.now()

    def add_asset(self, asset: Dict):
        """Añade un asset a la instancia"""
        if "id" not in asset:
            asset["id"] = str(ObjectId())
        self.assets.append(asset)
        self.updated_at = datetime.now()

    def remove_asset(self, asset_id: str):
        """Elimina un asset de la instancia"""
        self.assets = [asset for asset in self.assets if asset.get("id") != asset_id]
        self.updated_at = datetime.now()