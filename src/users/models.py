from typing import Optional, Dict, List
from bson import ObjectId
from datetime import datetime

class User:
    """
    Modelo de usuario.
    Contiene la información básica de un usuario registrado en el sistema.
    """
    def __init__(self,
                email: str,
                name: str,
                role: str,
                birth_date: Optional[str] = None,
                password: Optional[str] = None,
                picture: str = "",
                status: str = "active",
                provider: str = "local",
                                 email_verified: bool = False,
                 api_keys: Optional[Dict[str, str]] = None):
        self.email = email
        self.name = name
        self.birth_date = birth_date
        self.password = password
        self.picture = picture
        self.role = role
        self.status = status
        self.provider = provider
        self.email_verified = email_verified
        self.api_keys = api_keys or {}
        self.created_at = datetime.now()
        self.updated_at = datetime.now()
        
    def to_dict(self) -> dict:
        return {
            "email": self.email,
            "name": self.name,
            "birth_date": self.birth_date,
            "password": self.password,
            "picture": self.picture,
            "role": self.role,
            "status": self.status,
            "provider": self.provider,
            "email_verified": self.email_verified,
            "api_keys": self.api_keys,
            "created_at": self.created_at,
            "updated_at": self.updated_at
        }