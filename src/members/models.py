from datetime import datetime
from bson import ObjectId
from typing import Dict, Optional

class Member:
    """
    Clase base abstracta para miembros de cualquier entidad
    """
    def __init__(self,
                 user_id: str,
                 role: str,
                 status: str = "active"):
        self.user_id = ObjectId(user_id)
        self.role = role
        self.status = status
        self.joined_at = datetime.now()
        self.last_access = datetime.now()

    def to_dict(self) -> dict:
        return {
            "user_id": self.user_id,
            "role": self.role,
            "status": self.status,
            "joined_at": self.joined_at,
            "last_access": self.last_access
        }

class InstituteMember(Member):
    """
    Miembro de un instituto (admin, profesor o estudiante)
    """
    def __init__(self,
                 institute_id: str,
                 user_id: str,
                 role: str,
                 permissions: Optional[Dict] = None,
                 workspace_type: str = "INSTITUTE",
                 workspace_name: Optional[str] = None,
                 class_id: Optional[str] = None,
                 status: str = "active"):
        super().__init__(user_id, role, status)
        self.institute_id = ObjectId(institute_id)
        self.permissions = permissions or {
            "academic": True,
            "financial": False,
            "admin": role == "INSTITUTE_ADMIN"
        }
        self.workspace_type = workspace_type
        self.workspace_name = workspace_name
        self.class_id = ObjectId(class_id) if class_id else None

    def to_dict(self) -> dict:
        base_dict = super().to_dict()
        base_dict.update({
            "institute_id": self.institute_id,
            "permissions": self.permissions,
            "workspace_type": self.workspace_type,
            "workspace_name": self.workspace_name,
        })
        if self.class_id:
            base_dict["class_id"] = self.class_id
        return base_dict

class ClassMember(Member):
    """
    Miembro de una clase (profesor o estudiante)
    """
    def __init__(self,
                 class_id: str,
                 user_id: str,
                 role: str,
                 status: str = "active"):
        super().__init__(user_id, role, status)
        self.class_id = ObjectId(class_id)

    def to_dict(self) -> dict:
        base_dict = super().to_dict()
        base_dict.update({
            "class_id": self.class_id,
        })
        return base_dict 