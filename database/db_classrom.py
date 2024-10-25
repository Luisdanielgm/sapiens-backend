from database.mongodb import get_db
from datetime import datetime
from bson import ObjectId
from datetime import datetime

def invite_user_to_classroom(admin_email, classroom_id, invitee_email):
    db = get_db()
    users_collection = db.users
    classrooms_collection = db.classrooms
    classroom_members_collection = db.classroom_members
    classroom_invitations_collection = db.classroom_invitations

    # Verificar si el admin está intentando invitarse a sí mismo
    if admin_email == invitee_email:
        return False, "No puedes invitarte a ti mismo a la clase"

    admin = users_collection.find_one({"email": admin_email})
    invitee = users_collection.find_one({"email": invitee_email})
    classroom = classrooms_collection.find_one({"_id": ObjectId(classroom_id)})

    if not admin:
        return False, "Profesor no encontrado"
    if not invitee:
        return False, "Usuario invitado no encontrado"
    if not classroom:
        return False, "Clase no encontrada"

    # Verificar si el admin tiene permisos para invitar
    teacher_member = classroom_members_collection.find_one({
        "classroom_id": ObjectId(classroom_id),
        "user_id": admin["_id"],
        "role": "teacher"
    })

    if not teacher_member:
        return False, "No tienes permisos para invitar usuarios a esta clase"

    # Verificar si el usuario invitado ya es miembro de la clase
    existing_member = classroom_members_collection.find_one({
        "classroom_id": ObjectId(classroom_id),
        "user_id": invitee["_id"]
    })

    if existing_member:
        return False, "El usuario ya es miembro de esta clase"

    # Verificar si ya existe una invitación pendiente
    existing_invitation = classroom_invitations_collection.find_one({
        "classroom_id": ObjectId(classroom_id),
        "invitee_id": invitee["_id"],
        "status": "pending"
    })

    if existing_invitation:
        return False, "Ya existe una invitación pendiente para este usuario"

    # Crear nueva invitación
    new_invitation = {
        "classroom_id": ObjectId(classroom_id),
        "inviter_id": admin["_id"],
        "invitee_id": invitee["_id"],
        "status": "pending",
        "created_at": datetime.now()
    }

    try:
        result = classroom_invitations_collection.insert_one(new_invitation)
        if result.inserted_id:
            return True, "Invitación enviada exitosamente"
        else:
            return False, "Error al crear la invitación"
    except Exception as e:
        return False, f"Error al enviar la invitación: {str(e)}"
    
def get_user_pending_invitations(email):
    db = get_db()
    users_collection = db.users
    classrooms_collection = db.classrooms
    classroom_invitations_collection = db.classroom_invitations

    user = users_collection.find_one({"email": email})
    if not user:
        return []

    pending_invitations = classroom_invitations_collection.find({
        "invitee_id": user["_id"],
        "status": "pending"
    })

    invitations = []
    for invitation in pending_invitations:
        classroom = classrooms_collection.find_one({"_id": invitation["classroom_id"]})
        inviter = users_collection.find_one({"_id": invitation["inviter_id"]})
        if classroom and inviter:
            invitations.append({
                "id": str(invitation["_id"]),
                "className": classroom["name"],
                "inviterName": inviter["name"],
                "created_at": invitation["created_at"]
            })

    print("invitations encontradas: ", invitations)
    return invitations

def reject_invitation(email, invitation_id):
    db = get_db()
    users_collection = db.users
    classroom_invitations_collection = db.classroom_invitations

    user = users_collection.find_one({"email": email})
    if not user:
        return False

    invitation = classroom_invitations_collection.find_one({
        "_id": ObjectId(invitation_id),
        "invitee_id": user["_id"],
        "status": "pending"
    })

    if not invitation:
        return False

    # Actualizar el estado de la invitación a rechazada
    result = classroom_invitations_collection.update_one(
        {"_id": invitation["_id"]},
        {"$set": {"status": "rejected", "rejected_at": datetime.now()}}
    )

    return result.modified_count > 0

def accept_invitation(email, invitation_id):
    db = get_db()
    users_collection = db.users
    classroom_invitations_collection = db.classroom_invitations
    classroom_members_collection = db.classroom_members

    user = users_collection.find_one({"email": email})
    if not user:
        return False

    invitation = classroom_invitations_collection.find_one({
        "_id": ObjectId(invitation_id),
        "invitee_id": user["_id"],
        "status": "pending"
    })

    if not invitation:
        return False

    # Actualizar el estado de la invitación
    classroom_invitations_collection.update_one(
        {"_id": invitation["_id"]},
        {"$set": {"status": "accepted"}}
    )

    # Agregar al usuario como miembro del proyecto
    new_member = {
        "user_id": user["_id"],
        "classroom_id": invitation["classroom_id"],
        "role": "student",
        "joined_at": datetime.now()
    }
    classroom_members_collection.insert_one(new_member)

    return True

def get_teacher_classrooms(email):
    db = get_db()
    users_collection = db.users
    classrooms_collection = db.classrooms
    classroom_members_collection = db.classroom_members

    # Verificar si el usuario existe y es profesor
    user = users_collection.find_one({"email": email})
    if not user or user.get('role') != 'teacher':
        return []

    # Buscar todas las membresías del profesor
    teacher_memberships = classroom_members_collection.find({
        "user_id": user["_id"],
        "role": "teacher"
    })

    # Obtener los IDs de los salones
    classroom_ids = [membership["classroom_id"] for membership in teacher_memberships]

    # Buscar los detalles de los salones
    classrooms = []
    for classroom_id in classroom_ids:
        classroom = classrooms_collection.find_one({"_id": classroom_id})
        if classroom:
            # Contar estudiantes en este classroom
            student_count = classroom_members_collection.count_documents({
                "classroom_id": classroom_id,
                "role": "student"
            })

            classrooms.append({
                "id": str(classroom["_id"]),
                "name": classroom["name"],
                "created_at": classroom["created_at"],
                "student_count": student_count,  # Agregamos el contador de estudiantes
            })

    return classrooms
