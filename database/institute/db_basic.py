from database.mongodb import get_db
from datetime import datetime
from bson import ObjectId

def get_institute_by_email(email):
    """Obtiene la información del instituto asociado al email del usuario"""
    db = get_db()
    users_collection = db.users
    institute_members_collection = db.institute_members
    institutes_collection = db.institutes
    programs_collection = db.educational_programs

    try:
        # Debug: Imprimir colecciones
        print(f"Colecciones disponibles: {db.list_collection_names()}")
        
        # Buscar el usuario por email
        user = users_collection.find_one({"email": email})
        print(f"Usuario encontrado: {user}")  # Debug
        
        if not user:
            print(f"No se encontró usuario con email: {email}")  # Debug
            return None

        # Convertir _id a string
        user_id = user["_id"]
        
        # Buscar la membresía del usuario en algún instituto
        member = institute_members_collection.find_one({"user_id": user_id})
        print(f"Membresía encontrada: {member}")  # Debug
        
        if not member:
            print(f"No se encontró membresía para el usuario: {user_id}")  # Debug
            return None

        # Obtener información del instituto
        institute = institutes_collection.find_one({"_id": member["institute_id"]})
        print(f"Instituto encontrado: {institute}")  # Debug
        
        if not institute:
            print(f"No se encontró instituto con id: {member['institute_id']}")  # Debug
            return None

        # Preparar respuesta base
        institute_data = {
            "id": str(institute["_id"]),
            "name": institute.get("name", ""),
            "status": institute.get("status", "pending")
        }

        # Agregar campos opcionales solo si existen
        optional_fields = ["address", "phone", "email", "website", "created_at"]
        for field in optional_fields:
            if field in institute and institute[field]:
                institute_data[field] = institute[field]

        # Obtener programas si existen
        if programs_collection.count_documents({"institute_id": institute["_id"]}) > 0:
            programs = list(programs_collection.find({"institute_id": institute["_id"]}))
            institute_data["programs"] = [{
                "id": str(p["_id"]),
                "name": p.get("name", ""),
                "type": p.get("type", ""),
                "institute_id": str(p["institute_id"])
            } for p in programs]

        # Obtener miembros
        members = institute_members_collection.find({"institute_id": institute["_id"]})
        member_details = []
        for m in members:
            user_info = users_collection.find_one({"_id": m["user_id"]})
            if user_info:
                member_details.append({
                    "id": str(user_info["_id"]),
                    "name": user_info.get("name", ""),
                    "email": user_info.get("email", ""),
                    "role": m.get("role", ""),
                    "joined_at": m.get("joined_at", datetime.now())
                })
        
        if member_details:
            institute_data["members"] = member_details

        print(f"Datos del instituto preparados: {institute_data}")  # Debug
        return institute_data

    except Exception as e:
        print(f"Error detallado en get_institute_by_email: {str(e)}")
        import traceback
        traceback.print_exc()
        return None

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