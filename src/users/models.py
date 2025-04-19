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
                password: Optional[str] = None,
                picture: str = "",
                status: str = "active",
                provider: str = "local",
                email_verified: bool = False):
        self.email = email
        self.name = name
        self.password = password
        self.picture = picture
        self.role = role
        self.status = status
        self.provider = provider
        self.email_verified = email_verified
        self.created_at = datetime.now()
        self.updated_at = datetime.now()
        
    def to_dict(self) -> dict:
        return {
            "email": self.email,
            "name": self.name,
            "password": self.password,
            "picture": self.picture,
            "role": self.role,
            "status": self.status,
            "provider": self.provider,
            "email_verified": self.email_verified,
            "created_at": self.created_at,
            "updated_at": self.updated_at
        }