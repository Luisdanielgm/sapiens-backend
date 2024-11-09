from database.mongodb import get_db
from datetime import datetime
from bson import ObjectId

def invite_to_institute(admin_email, invitee_email, institute_id, role):
    """Invita a un usuario a unirse al instituto"""
    db = get_db()
    users_collection = db.users
    institutes_collection = db.institutes
    institute_invitations_collection = db.institute_invitations
    institute_members_collection = db.institute_members

    # Verificaciones básicas
    admin = users_collection.find_one({"email": admin_email})
    invitee = users_collection.find_one({"email": invitee_email})
    institute = institutes_collection.find_one({"_id": ObjectId(institute_id)})

    if not all([admin, invitee, institute]):
        return False, "Datos de invitación inválidos"

    # Verificar permisos y crear invitación
    admin_member = institute_members_collection.find_one({
        "institute_id": ObjectId(institute_id),
        "user_id": admin["_id"],
        "role": "INSTITUTE_ADMIN"
    })

    if not admin_member:
        return False, "No tienes permisos para invitar usuarios"

    # Verificar si ya es miembro
    existing_member = institute_members_collection.find_one({
        "institute_id": ObjectId(institute_id),
        "user_id": invitee["_id"]
    })

    if existing_member:
        return False, "El usuario ya es miembro del instituto"

    try:
        new_invitation = {
            "institute_id": ObjectId(institute_id),
            "inviter_id": admin["_id"],
            "invitee_id": invitee["_id"],
            "role": role,
            "status": "pending",
            "created_at": datetime.now()
        }
        institute_invitations_collection.insert_one(new_invitation)
        return True, "Invitación enviada exitosamente"
    except Exception as e:
        return False, str(e)

def get_institute_pending_invitations(email):
    """Obtiene las invitaciones pendientes para un usuario"""
    db = get_db()
    users_collection = db.users
    institutes_collection = db.institutes
    institute_invitations_collection = db.institute_invitations

    user = users_collection.find_one({"email": email})
    if not user:
        return []

    pending_invitations = institute_invitations_collection.find({
        "invitee_id": user["_id"],
        "status": "pending"
    })

    invitations = []
    for invitation in pending_invitations:
        institute = institutes_collection.find_one({"_id": invitation["institute_id"]})
        inviter = users_collection.find_one({"_id": invitation["inviter_id"]})
        if institute and inviter:
            invitations.append({
                "id": str(invitation["_id"]),
                "institute_name": institute["name"],
                "inviter_name": inviter["name"],
                "role": invitation["role"],
                "created_at": invitation["created_at"]
            })

    return invitations

def accept_institute_invitation(email, invitation_id):
    """Acepta una invitación a un instituto"""
    db = get_db()
    users_collection = db.users
    institute_invitations_collection = db.institute_invitations
    institute_members_collection = db.institute_members

    user = users_collection.find_one({"email": email})
    if not user:
        return False, "Usuario no encontrado"

    invitation = institute_invitations_collection.find_one({
        "_id": ObjectId(invitation_id),
        "invitee_id": user["_id"],
        "status": "pending"
    })

    if not invitation:
        return False, "Invitación no encontrada o ya procesada"

    try:
        # Actualizar estado de la invitación
        institute_invitations_collection.update_one(
            {"_id": invitation["_id"]},
            {"$set": {
                "status": "accepted",
                "accepted_at": datetime.now()
            }}
        )

        # Crear nuevo miembro
        new_member = {
            "institute_id": invitation["institute_id"],
            "user_id": user["_id"],
            "role": invitation["role"],
            "joined_at": datetime.now()
        }
        institute_members_collection.insert_one(new_member)

        return True, "Invitación aceptada exitosamente"
    except Exception as e:
        return False, str(e)

def reject_institute_invitation(email, invitation_id):
    """Rechaza una invitación a un instituto"""
    db = get_db()
    users_collection = db.users
    institute_invitations_collection = db.institute_invitations

    user = users_collection.find_one({"email": email})
    if not user:
        return False, "Usuario no encontrado"

    invitation = institute_invitations_collection.find_one({
        "_id": ObjectId(invitation_id),
        "invitee_id": user["_id"],
        "status": "pending"
    })

    if not invitation:
        return False, "Invitación no encontrada o ya procesada"

    try:
        institute_invitations_collection.update_one(
            {"_id": invitation["_id"]},
            {"$set": {
                "status": "rejected",
                "rejected_at": datetime.now()
            }}
        )
        return True, "Invitación rechazada exitosamente"
    except Exception as e:
        return False, str(e)

def get_institute_members(institute_id):
    """Obtiene la lista de miembros de un instituto"""
    db = get_db()
    users_collection = db.users
    institute_members_collection = db.institute_members

    try:
        members = institute_members_collection.find({
            "institute_id": ObjectId(institute_id)
        })

        members_list = []
        for member in members:
            user = users_collection.find_one({"_id": member["user_id"]})
            if user:
                members_list.append({
                    "id": str(user["_id"]),
                    "name": user["name"],
                    "email": user["email"],
                    "role": member["role"],
                    "joined_at": member["joined_at"],
                    "picture": user.get("picture")
                })

        return members_list
    except Exception as e:
        print(f"Error al obtener miembros: {str(e)}")
        return []

def get_user_institutes(email):
    """Obtiene los institutos asociados a un usuario"""
    db = get_db()
    users_collection = db.users
    institutes_collection = db.institutes
    institute_members_collection = db.institute_members

    user = users_collection.find_one({"email": email})
    if not user:
        return []

    try:
        memberships = institute_members_collection.find({
            "user_id": user["_id"]
        })

        institutes = []
        for membership in memberships:
            institute = institutes_collection.find_one({
                "_id": membership["institute_id"]
            })
            if institute:
                institutes.append({
                    "id": str(institute["_id"]),
                    "name": institute["name"],
                    "role": membership["role"],
                    "joined_at": membership["joined_at"],
                    "status": institute["status"]
                })

        return institutes
    except Exception as e:
        print(f"Error al obtener institutos: {str(e)}")
        return []