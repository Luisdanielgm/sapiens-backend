from database.mongodb import get_db
from datetime import datetime
from bson import ObjectId

def create_institute(name, address, phone, email, website, admin_email):
    """Crea un nuevo instituto y asigna un administrador"""
    db = get_db()
    institutes_collection = db.institutes
    users_collection = db.users
    institute_members_collection = db.institute_members

    # Verificar si el admin existe
    admin = users_collection.find_one({"email": admin_email})
    if not admin:
        return False, "Administrador no encontrado"

    # Crear instituto
    new_institute = {
        "name": name,
        "address": address,
        "phone": phone,
        "email": email,
        "website": website,
        "created_at": datetime.now(),
        "status": "pending"
    }

    try:
        institute_result = institutes_collection.insert_one(new_institute)
        institute_id = institute_result.inserted_id

        # Crear relación admin-instituto
        new_member = {
            "institute_id": institute_id,
            "user_id": admin["_id"],
            "role": "institute_admin",
            "joined_at": datetime.now()
        }
        institute_members_collection.insert_one(new_member)

        return True, str(institute_id)
    except Exception as e:
        return False, str(e)

def update_institute(institute_id, data, admin_email):
    """Actualiza información del instituto"""
    db = get_db()
    institutes_collection = db.institutes
    users_collection = db.users

    # Verificar permisos
    admin = users_collection.find_one({"email": admin_email})
    if not admin or admin.get('role') not in ['admin', 'institute_admin']:
        return False, "No tienes permisos para actualizar el instituto"

    try:
        update_data = {
            "name": data.get("name"),
            "address": data.get("address"),
            "phone": data.get("phone"),
            "email": data.get("email"),
            "website": data.get("website"),
            "updated_at": datetime.now()
        }
        update_data = {k: v for k, v in update_data.items() if v is not None}

        result = institutes_collection.update_one(
            {"_id": ObjectId(institute_id)},
            {"$set": update_data}
        )
        return True, "Instituto actualizado exitosamente"
    except Exception as e:
        return False, str(e)

def delete_institute(institute_id, admin_email):
    """Desactiva un instituto (no lo elimina físicamente)"""
    db = get_db()
    institutes_collection = db.institutes
    users_collection = db.users

    # Verificar permisos
    admin = users_collection.find_one({"email": admin_email})
    if not admin or admin.get('role') != 'admin':
        return False, "No tienes permisos para eliminar institutos"

    try:
        result = institutes_collection.update_one(
            {"_id": ObjectId(institute_id)},
            {"$set": {
                "status": "inactive",
                "updated_at": datetime.now()
            }}
        )
        return True, "Instituto desactivado exitosamente"
    except Exception as e:
        return False, str(e)

def get_institute_details(institute_id):
    """Obtiene detalles completos del instituto"""
    db = get_db()
    institutes_collection = db.institutes
    programs_collection = db.educational_programs
    institute_members_collection = db.institute_members
    users_collection = db.users

    try:
        institute = institutes_collection.find_one({"_id": ObjectId(institute_id)})
        if not institute:
            return None

        # Obtener programas y miembros
        programs = list(programs_collection.find({"institute_id": ObjectId(institute_id)}))
        members = institute_members_collection.find({"institute_id": ObjectId(institute_id)})
        
        member_details = []
        for member in members:
            user = users_collection.find_one({"_id": member["user_id"]})
            if user:
                member_details.append({
                    "id": str(user["_id"]),
                    "name": user["name"],
                    "email": user["email"],
                    "role": member["role"],
                    "joined_at": member["joined_at"]
                })

        return {
            "id": str(institute["_id"]),
            "name": institute["name"],
            "address": institute["address"],
            "phone": institute["phone"],
            "email": institute["email"],
            "website": institute["website"],
            "status": institute["status"],
            "created_at": institute["created_at"],
            "programs": programs,
            "members": member_details
        }
    except Exception as e:
        print(f"Error al obtener detalles del instituto: {str(e)}")
        return None

def get_institute_statistics(institute_id):
    """Obtiene estadísticas del instituto"""
    db = get_db()
    institutes_collection = db.institutes
    programs_collection = db.educational_programs
    institute_members_collection = db.institute_members
    students_collection = db.students

    try:
        # Verificar si el instituto existe
        institute = institutes_collection.find_one({"_id": ObjectId(institute_id)})
        if not institute:
            return None

        # Contar programas activos
        total_programs = programs_collection.count_documents({
            "institute_id": ObjectId(institute_id),
            "status": "active"
        })

        # Contar miembros por rol
        members = institute_members_collection.find({"institute_id": ObjectId(institute_id)})
        members_by_role = {}
        for member in members:
            role = member["role"]
            members_by_role[role] = members_by_role.get(role, 0) + 1

        # Contar estudiantes activos
        total_students = students_collection.count_documents({
            "institute_id": ObjectId(institute_id),
            "status": "active"
        })

        return {
            "total_programs": total_programs,
            "total_students": total_students,
            "members_by_role": members_by_role,
            "institute_status": institute["status"]
        }
    except Exception as e:
        print(f"Error al obtener estadísticas del instituto: {str(e)}")
        return None