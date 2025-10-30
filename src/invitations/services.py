from typing import Tuple, List, Dict, Optional
from bson import ObjectId
from datetime import datetime

from src.shared.database import get_db
from src.shared.constants import ROLES, INVITATION_STATUS
from src.shared.standardization import VerificationBaseService, ErrorCodes
from src.shared.exceptions import AppException
from .models import InstituteInvitation, ClassInvitation, MembershipRequest
from src.members.services import MembershipService
import logging

class InvitationService(VerificationBaseService):
    def __init__(self):
        # No inicializamos con una colección específica porque usamos varias
        super().__init__(collection_name="institute_invitations") 
        self.membership_service = MembershipService()

    # ========== MÉTODOS DE VERIFICACIÓN ESTANDARIZADOS ==========
    def check_institute_exists(self, institute_id: str) -> bool:
        """
        Verifica si un instituto existe.
        
        Args:
            institute_id: ID del instituto a verificar
            
        Returns:
            bool: True si el instituto existe, False en caso contrario
        """
        try:
            institute = self.db.institutes.find_one({"_id": ObjectId(institute_id)})
            return institute is not None
        except Exception:
            return False

    def check_class_exists(self, class_id: str) -> bool:
        """
        Verifica si una clase existe.
        
        Args:
            class_id: ID de la clase a verificar
            
        Returns:
            bool: True si la clase existe, False en caso contrario
        """
        try:
            class_obj = self.db.classes.find_one({"_id": ObjectId(class_id)})
            return class_obj is not None
        except Exception:
            return False

    def check_invitation_exists(self, invitation_id: str, collection_name: str = "institute_invitations") -> bool:
        """
        Verifica si una invitación existe.
        
        Args:
            invitation_id: ID de la invitación a verificar
            collection_name: Nombre de la colección donde buscar
            
        Returns:
            bool: True si la invitación existe, False en caso contrario
        """
        try:
            invitation = self.db[collection_name].find_one({"_id": ObjectId(invitation_id)})
            return invitation is not None
        except Exception:
            return False

    def check_pending_institute_invitation(self, institute_id: str, invitee_email: str) -> bool:
        """
        Verifica si existe una invitación pendiente para un correo y un instituto.
        
        Args:
            institute_id: ID del instituto
            invitee_email: Correo electrónico del invitado
            
        Returns:
            bool: True si existe una invitación pendiente, False en caso contrario
        """
        try:
            existing_invitation = self.db.institute_invitations.find_one({
                "institute_id": ObjectId(institute_id),
                "invitee_email": invitee_email,
                "status": "pending"
            })
            return existing_invitation is not None
        except Exception:
            return False

    def check_pending_class_invitation(self, class_id: str, invitee_email: str) -> bool:
        """
        Verifica si existe una invitación pendiente para un correo y una clase.
        
        Args:
            class_id: ID de la clase
            invitee_email: Correo electrónico del invitado
            
        Returns:
            bool: True si existe una invitación pendiente, False en caso contrario
        """
        try:
            existing_invitation = self.db.class_invitations.find_one({
                "class_id": ObjectId(class_id),
                "invitee_email": invitee_email,
                "status": "pending"
            })
            return existing_invitation is not None
        except Exception:
            return False

    def check_is_institute_member(self, institute_id: str, user_id: str) -> bool:
        """
        Verifica si un usuario es miembro de un instituto.
        
        Args:
            institute_id: ID del instituto
            user_id: ID del usuario
            
        Returns:
            bool: True si el usuario es miembro, False en caso contrario
        """
        try:
            existing_member = self.db.institute_members.find_one({
                "institute_id": ObjectId(institute_id),
                "user_id": ObjectId(user_id)
            })
            return existing_member is not None
        except Exception:
            return False

    def check_pending_membership_request(self, institute_id: str, user_id: str) -> bool:
        """
        Verifica si existe una solicitud de membresía pendiente.
        
        Args:
            institute_id: ID del instituto
            user_id: ID del usuario
            
        Returns:
            bool: True si existe una solicitud pendiente, False en caso contrario
        """
        try:
            existing_request = self.db.membership_requests.find_one({
                "institute_id": ObjectId(institute_id),
                "user_id": ObjectId(user_id),
                "status": "pending"
            })
            return existing_request is not None
        except Exception:
            return False

    # ========== INSTITUTO INVITATIONS ==========
    def create_institute_invitation(self, invitation_data: dict) -> Tuple[bool, str]:
        """
        Crea una invitación para unirse a un instituto
        """
        try:
            # Verificar que el instituto existe
            if not self.check_institute_exists(invitation_data['institute_id']):
                return False, "Instituto no encontrado"

            # Verificar que no exista una invitación pendiente con el mismo email
            if self.check_pending_institute_invitation(invitation_data['institute_id'], invitation_data['invitee_email']):
                return False, "Ya existe una invitación pendiente para este correo electrónico"

            invitation = InstituteInvitation(**invitation_data)
            result = self.db.institute_invitations.insert_one(invitation.to_dict())
            return True, str(result.inserted_id)
        except Exception as e:
            return False, str(e)

    def get_institute_invitations(self, institute_id: str, status: Optional[str] = None) -> List[Dict]:
        """
        Obtiene todas las invitaciones de un instituto, opcionalmente filtradas por estado
        """
        try:
            query = {"institute_id": ObjectId(institute_id)}
            if status:
                query["status"] = status

            invitations = list(self.db.institute_invitations.find(query))
            
            # Convertir ObjectId a string para serialización
            for invitation in invitations:
                invitation["_id"] = str(invitation["_id"])
                invitation["institute_id"] = str(invitation["institute_id"])
                if "created_by" in invitation and invitation["created_by"]:
                    invitation["created_by"] = str(invitation["created_by"])
                
            return invitations
        except Exception as e:
            print(f"Error al obtener invitaciones: {str(e)}")
            return []

    def process_institute_invitation(self, invitation_id: str, user_id: str, action: str, workspace_info: Optional[Dict] = None) -> Tuple[bool, str]:
        """
        Procesa una invitación a un instituto (aceptar/rechazar)
        
        Args:
            invitation_id: ID de la invitación
            user_id: ID del usuario que procesa la invitación
            action: 'accept' o 'reject'
            workspace_info: Información del workspace actual (opcional, para crear membresía con workspace)
        """
        try:
            # Verificar que la invitación existe
            if not self.check_invitation_exists(invitation_id, "institute_invitations"):
                return False, "Invitación no encontrada"
                
            invitation = self.db.institute_invitations.find_one({"_id": ObjectId(invitation_id)})
                
            # Verificar estado
            if invitation["status"] != "pending":
                return False, f"Invitación ya procesada (estado: {invitation['status']})"
                
            # Actualizar estado
            new_status = "accepted" if action == "accept" else "rejected"
            
            self.db.institute_invitations.update_one(
                {"_id": ObjectId(invitation_id)},
                {"$set": {"status": new_status, "processed_at": datetime.now()}}
            )
            
            # Si fue aceptada, añadir al usuario como miembro
            if new_status == "accepted":
                membership_data = {
                    "institute_id": str(invitation["institute_id"]),
                    "user_id": user_id,
                    "role": invitation["role"]
                }
                
                # Agregar información de workspace si está disponible
                # NOTA: workspace_id no se pasa porque el _id del documento será el workspace_id
                # Al aceptar una invitación, el workspace actual puede ser de otro instituto
                # Si el workspace actual coincide con el instituto de la invitación, usamos su workspace_type
                # Si no coincide o no hay workspace, usamos 'INSTITUTE' por defecto
                if workspace_info:
                    workspace_institute_id = str(workspace_info.get('institute_id', ''))
                    invitation_institute_id = str(invitation["institute_id"])
                    
                    # Solo usar workspace_type del workspace actual si es del mismo instituto
                    if workspace_institute_id == invitation_institute_id and workspace_info.get('workspace_type'):
                        membership_data['workspace_type'] = workspace_info['workspace_type']
                    else:
                        # Si el workspace es de otro instituto o no tiene workspace_type, usar 'INSTITUTE' por defecto
                        membership_data['workspace_type'] = 'INSTITUTE'
                else:
                    # Si no hay workspace_info, usar 'INSTITUTE' por defecto
                    membership_data['workspace_type'] = 'INSTITUTE'
                
                try:
                    member_id = self.membership_service.add_institute_member(membership_data)
                    return True, f"Invitación aceptada, miembro creado con ID: {member_id}"
                except AppException as e:
                    # AppException tiene mensaje y código HTTP
                    logging.getLogger(__name__).error(f"Error de aplicación al crear membresía: {e.message}")
                    return False, e.message
                
            return True, "Invitación rechazada"
                
        except Exception as e:
            logging.getLogger(__name__).error(f"Error procesando invitación de instituto: {str(e)}", exc_info=True)
            return False, str(e)

    def get_invitation_by_id(self, invitation_id: str, collection_name: str = "institute_invitations") -> Optional[Dict]:
        """
        Obtiene una invitación por su ID de cualquier colección de invitaciones
        """
        try:
            invitation = self.db[collection_name].find_one({"_id": ObjectId(invitation_id)})
            if invitation:
                invitation["_id"] = str(invitation["_id"])
                # Convertir otros ObjectId a string según sea necesario
                if "institute_id" in invitation:
                    invitation["institute_id"] = str(invitation["institute_id"])
                if "class_id" in invitation:
                    invitation["class_id"] = str(invitation["class_id"])
                if "created_by" in invitation and invitation["created_by"]:
                    invitation["created_by"] = str(invitation["created_by"])
            return invitation
        except Exception as e:
            print(f"Error al obtener invitación: {str(e)}")
            return None

    # ========== CLASS INVITATIONS ==========
    def create_class_invitation(self, invitation_data: dict) -> Tuple[bool, str]:
        """
        Crea una invitación para unirse a una clase
        """
        try:
            # Verificar que la clase existe
            if not self.check_class_exists(invitation_data['class_id']):
                return False, "Clase no encontrada"

            # Verificar que no exista una invitación pendiente con el mismo email
            if self.check_pending_class_invitation(invitation_data['class_id'], invitation_data['invitee_email']):
                return False, "Ya existe una invitación pendiente para este correo electrónico"

            invitation = ClassInvitation(**invitation_data)
            result = self.db.class_invitations.insert_one(invitation.to_dict())
            return True, str(result.inserted_id)
        except Exception as e:
            return False, str(e)

    def get_class_invitations(self, class_id: str, status: Optional[str] = None) -> List[Dict]:
        """
        Obtiene todas las invitaciones de una clase, opcionalmente filtradas por estado
        """
        try:
            query = {"class_id": ObjectId(class_id)}
            if status:
                query["status"] = status

            invitations = list(self.db.class_invitations.find(query))
            
            # Convertir ObjectId a string para serialización
            for invitation in invitations:
                invitation["_id"] = str(invitation["_id"])
                invitation["class_id"] = str(invitation["class_id"])
                if "created_by" in invitation and invitation["created_by"]:
                    invitation["created_by"] = str(invitation["created_by"])
                
            return invitations
        except Exception as e:
            print(f"Error al obtener invitaciones de clase: {str(e)}")
            return []

    def process_class_invitation(self, invitation_id: str, user_id: str, action: str, workspace_info: Optional[Dict] = None) -> Tuple[bool, str]:
        """
        Procesa una invitación a una clase (aceptar/rechazar)
        
        Args:
            invitation_id: ID de la invitación
            user_id: ID del usuario que procesa la invitación
            action: 'accept' o 'reject'
            workspace_info: Información del workspace actual (opcional, para validaciones de membresía)
        """
        try:
            # Verificar que la invitación existe
            if not self.check_invitation_exists(invitation_id, "class_invitations"):
                return False, "Invitación no encontrada"
                
            invitation = self.db.class_invitations.find_one({"_id": ObjectId(invitation_id)})
                
            # Verificar estado
            if invitation["status"] != "pending":
                return False, f"Invitación ya procesada (estado: {invitation['status']})"
                
            # Actualizar estado
            new_status = "accepted" if action == "accept" else "rejected"
            
            self.db.class_invitations.update_one(
                {"_id": ObjectId(invitation_id)},
                {"$set": {"status": new_status, "processed_at": datetime.now()}}
            )
            
            # Si fue aceptada, añadir al usuario como miembro de la clase
            if new_status == "accepted":
                # Verificar que la clase sigue existiendo
                if not self.check_class_exists(str(invitation["class_id"])):
                    return False, "La clase ya no existe"
                    
                membership_data = {
                    "class_id": str(invitation["class_id"]),
                    "user_id": user_id,
                    "role": invitation["role"]
                }
                
                # Agregar información de workspace si está disponible (para futuras validaciones)
                # NOTA: workspace_id no se pasa porque no es un campo del modelo ClassMember
                # El workspace_info se pasa pero add_class_member no lo usa directamente
                # Solo lo incluimos por si en el futuro se necesita para validaciones
                
                try:
                    success, result = self.membership_service.add_class_member(membership_data)
                    if success:
                        return True, f"Invitación aceptada, miembro creado con ID: {result}"
                    else:
                        # result contiene el mensaje de error
                        logging.getLogger(__name__).warning(f"Error al crear membresía de clase: {result}")
                        return False, result
                except AppException as e:
                    # AppException puede ser lanzada por validaciones internas
                    logging.getLogger(__name__).error(f"Error de aplicación al crear membresía de clase: {e.message}")
                    return False, e.message
                
            return True, "Invitación rechazada"
                
        except Exception as e:
            logging.getLogger(__name__).error(f"Error procesando invitación de clase: {str(e)}", exc_info=True)
            return False, str(e)

    # ========== MEMBERSHIP REQUESTS ==========
    def create_membership_request(self, request_data: dict) -> Tuple[bool, str]:
        """
        Crea una solicitud de membresía a un instituto
        """
        try:
            # Verificar que el instituto existe
            if not self.check_institute_exists(request_data['institute_id']):
                return False, "Instituto no encontrado"

            # Verificar que el usuario no sea ya un miembro
            if self.check_is_institute_member(request_data['institute_id'], request_data['user_id']):
                return False, "El usuario ya es miembro de este instituto"
                
            # Verificar que no exista una solicitud pendiente
            if self.check_pending_membership_request(request_data['institute_id'], request_data['user_id']):
                return False, "Ya existe una solicitud pendiente para este usuario"

            request_obj = MembershipRequest(**request_data)
            result = self.db.membership_requests.insert_one(request_obj.to_dict())
            return True, str(result.inserted_id)
        except Exception as e:
            return False, str(e)

    def get_membership_requests(self, institute_id: str, status: Optional[str] = None) -> List[Dict]:
        """
        Obtiene todas las solicitudes de membresía de un instituto, opcionalmente filtradas por estado
        """
        try:
            query = {"institute_id": ObjectId(institute_id)}
            if status:
                query["status"] = status

            requests = list(self.db.membership_requests.find(query))
            
            # Convertir ObjectId a string para serialización
            for request in requests:
                request["_id"] = str(request["_id"])
                request["institute_id"] = str(request["institute_id"])
                request["user_id"] = str(request["user_id"])
                
                # Añadir información del usuario
                user = self.db.users.find_one({"_id": ObjectId(request["user_id"])})
                if user:
                    request["user"] = {
                        "name": user.get("name", ""),
                        "email": user.get("email", ""),
                        "picture": user.get("picture", "")
                    }
                
            return requests
        except Exception as e:
            print(f"Error al obtener solicitudes: {str(e)}")
            return []

    def process_membership_request(self, request_id: str, action: str, workspace_info: Optional[Dict] = None) -> Tuple[bool, str]:
        """
        Procesa una solicitud de membresía (aprobar/rechazar)
        
        Args:
            request_id: ID de la solicitud
            action: 'approve' o 'reject'
            workspace_info: Información del workspace actual (opcional, para crear membresía con workspace)
        """
        try:
            # Verificar que la solicitud existe
            request = self.db.membership_requests.find_one({"_id": ObjectId(request_id)})
            if not request:
                return False, "Solicitud no encontrada"
                
            # Verificar estado
            if request["status"] != "pending":
                return False, f"Solicitud ya procesada (estado: {request['status']})"
                
            # Actualizar estado
            new_status = "approved" if action == "approve" else "rejected"
            
            self.db.membership_requests.update_one(
                {"_id": ObjectId(request_id)},
                {"$set": {"status": new_status, "processed_at": datetime.now()}}
            )
            
            # Si fue aprobada, añadir al usuario como miembro
            if new_status == "approved":
                membership_data = {
                    "institute_id": str(request["institute_id"]),
                    "user_id": str(request["user_id"]),
                    "role": request["requested_role"]
                }
                
                # Agregar información de workspace si está disponible
                # NOTA: workspace_id no se pasa porque el _id del documento será el workspace_id
                # Al aprobar una solicitud, el workspace actual puede ser de otro instituto
                # Si el workspace actual coincide con el instituto de la solicitud, usamos su workspace_type
                # Si no coincide o no hay workspace, usamos 'INSTITUTE' por defecto
                if workspace_info:
                    workspace_institute_id = str(workspace_info.get('institute_id', ''))
                    request_institute_id = str(request["institute_id"])
                    
                    # Solo usar workspace_type del workspace actual si es del mismo instituto
                    if workspace_institute_id == request_institute_id and workspace_info.get('workspace_type'):
                        membership_data['workspace_type'] = workspace_info['workspace_type']
                    else:
                        # Si el workspace es de otro instituto o no tiene workspace_type, usar 'INSTITUTE' por defecto
                        membership_data['workspace_type'] = 'INSTITUTE'
                else:
                    # Si no hay workspace_info, usar 'INSTITUTE' por defecto
                    membership_data['workspace_type'] = 'INSTITUTE'
                
                member_id = self.membership_service.add_institute_member(membership_data)
                return True, f"Solicitud aprobada, miembro creado con ID: {member_id}"
                
            return True, "Solicitud rechazada"
                
        except Exception as e:
            return False, str(e)

    def get_user_invitations(self, email: str) -> Dict[str, List[Dict]]:
        """
        Obtiene todas las invitaciones pendientes para un usuario por su email
        """
        try:
            response = {
                "institute_invitations": [],
                "class_invitations": []
            }
            
            # Invitaciones a institutos
            institute_invitations = list(self.db.institute_invitations.find({
                "invitee_email": email,
                "status": "pending"
            }))
            
            for invitation in institute_invitations:
                invitation["_id"] = str(invitation["_id"])
                invitation["institute_id"] = str(invitation["institute_id"])
                if "created_by" in invitation and invitation["created_by"]:
                    invitation["created_by"] = str(invitation["created_by"])
                    
                # Añadir información del instituto
                institute = self.db.institutes.find_one({"_id": ObjectId(invitation["institute_id"])})
                if institute:
                    invitation["institute_name"] = institute.get("name", "")
                    
            response["institute_invitations"] = institute_invitations
            
            # Invitaciones a clases
            class_invitations = list(self.db.class_invitations.find({
                "invitee_email": email,
                "status": "pending"
            }))
            
            for invitation in class_invitations:
                invitation["_id"] = str(invitation["_id"])
                invitation["class_id"] = str(invitation["class_id"])
                if "created_by" in invitation and invitation["created_by"]:
                    invitation["created_by"] = str(invitation["created_by"])
                    
                # Añadir información de la clase
                class_obj = self.db.classes.find_one({"_id": ObjectId(invitation["class_id"])})
                if class_obj:
                    invitation["class_name"] = class_obj.get("name", "")
                    invitation["subject"] = class_obj.get("subject", "")
                    
            response["class_invitations"] = class_invitations
            
            return response
        except Exception as e:
            print(f"Error al obtener invitaciones del usuario: {str(e)}")
            return {"institute_invitations": [], "class_invitations": []} 