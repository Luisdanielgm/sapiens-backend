from datetime import datetime
from bson import ObjectId
from typing import Optional

class Invitation:
    """
    Clase base abstracta para invitaciones
    """
    def __init__(self,
                 inviter_id: str,
                 invitee_email: str,
                 role: str,
                 message: Optional[str] = None,
                 status: str = "pending"):
        self.inviter_id = ObjectId(inviter_id)
        self.invitee_email = invitee_email
        self.role = role
        self.message = message
        self.status = status
        self.created_at = datetime.now()
        self.updated_at = datetime.now()

    def to_dict(self) -> dict:
        return {
            "inviter_id": self.inviter_id,
            "invitee_email": self.invitee_email,
            "role": self.role,
            "message": self.message,
            "status": self.status,
            "created_at": self.created_at,
            "updated_at": self.updated_at
        }

class InstituteInvitation(Invitation):
    """
    Invitación para unirse a un instituto
    """
    def __init__(self,
                 institute_id: str,
                 inviter_id: str,
                 invitee_email: str,
                 role: str,
                 message: Optional[str] = None,
                 status: str = "pending"):
        super().__init__(inviter_id, invitee_email, role, message, status)
        self.institute_id = ObjectId(institute_id)

    def to_dict(self) -> dict:
        base_dict = super().to_dict()
        base_dict.update({
            "institute_id": self.institute_id
        })
        return base_dict

class ClassInvitation(Invitation):
    """
    Invitación para unirse a una clase
    """
    def __init__(self,
                 class_id: str,
                 inviter_id: str,
                 invitee_email: str,
                 role: str = "STUDENT",
                 message: Optional[str] = None,
                 status: str = "pending"):
        super().__init__(inviter_id, invitee_email, role, message, status)
        self.class_id = ObjectId(class_id)

    def to_dict(self) -> dict:
        base_dict = super().to_dict()
        base_dict.update({
            "class_id": self.class_id
        })
        return base_dict

class MembershipRequest:
    """
    Solicitud de membresía iniciada por un usuario
    """
    def __init__(self,
                 institute_id: str,
                 user_id: str,
                 role: str,
                 message: Optional[str] = None,
                 status: str = "pending"):
        self.institute_id = ObjectId(institute_id)
        self.user_id = ObjectId(user_id)
        self.role = role
        self.message = message
        self.status = status
        self.created_at = datetime.now()
        self.updated_at = datetime.now()

    def to_dict(self) -> dict:
        return {
            "institute_id": self.institute_id,
            "user_id": self.user_id,
            "role": self.role,
            "message": self.message,
            "status": self.status,
            "created_at": self.created_at,
            "updated_at": self.updated_at
        } 