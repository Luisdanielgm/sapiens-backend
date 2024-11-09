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

    # Verificar permisos del admin
    admin_member = institute_members_collection.find_one({
        "institute_id": ObjectId(institute_id),
        "user_id": admin["_id"],
        "role": "institute_admin"
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

    # Crear invitación
    new_invitation = {
        "institute_id": ObjectId(institute_id),
        "inviter_id": admin["_id"],
        "invitee_id": invitee["_id"],
        "role": role,
        "status": "pending",
        "created_at": datetime.now()
    }

    try:
        institute_invitations_collection.insert_one(new_invitation)
        return True, "Invitación enviada exitosamente"
    except Exception as e:
        return False, str(e)

def get_institute_programs(institute_id):
    """Obtiene todos los programas de un instituto"""
    db = get_db()
    programs_collection = db.educational_programs

    programs = programs_collection.find({
        "institute_id": ObjectId(institute_id)
    })

    return list(programs)

def create_educational_program(institute_id, name, program_type, description):
    """Crea un nuevo programa educativo"""
    db = get_db()
    programs_collection = db.educational_programs

    new_program = {
        "institute_id": ObjectId(institute_id),
        "name": name,
        "type": program_type,
        "description": description,
        "created_at": datetime.now()
    }

    try:
        result = programs_collection.insert_one(new_program)
        return True, str(result.inserted_id)
    except Exception as e:
        return False, str(e)

def create_academic_period(program_id, name, period_type):
    """Crea un nuevo periodo académico"""
    db = get_db()
    periods_collection = db.academic_periods

    new_period = {
        "program_id": ObjectId(program_id),
        "name": name,
        "type": period_type,
        "created_at": datetime.now()
    }

    try:
        result = periods_collection.insert_one(new_period)
        return True, str(result.inserted_id)
    except Exception as e:
        return False, str(e)

def create_section(program_id, period_id, name):
    """Crea una nueva sección"""
    db = get_db()
    sections_collection = db.sections

    new_section = {
        "program_id": ObjectId(program_id),
        "period_id": ObjectId(period_id),
        "name": name,
        "created_at": datetime.now()
    }

    try:
        result = sections_collection.insert_one(new_section)
        return True, str(result.inserted_id)
    except Exception as e:
        return False, str(e)

def create_subject(program_id, period_id, name):
    """Crea una nueva materia"""
    db = get_db()
    subjects_collection = db.subjects

    new_subject = {
        "program_id": ObjectId(program_id),
        "period_id": ObjectId(period_id),
        "name": name,
        "created_at": datetime.now()
    }

    try:
        result = subjects_collection.insert_one(new_subject)
        return True, str(result.inserted_id)
    except Exception as e:
        return False, str(e)

def get_institute_periods(program_id):
    """Obtiene todos los periodos de un programa"""
    db = get_db()
    periods_collection = db.academic_periods

    periods = periods_collection.find({
        "program_id": ObjectId(program_id)
    }).sort("name", 1)

    return list(periods)

def get_period_sections(period_id):
    """Obtiene todas las secciones de un periodo"""
    db = get_db()
    sections_collection = db.sections

    sections = sections_collection.find({
        "period_id": ObjectId(period_id)
    }).sort("name", 1)

    return list(sections)

def get_period_subjects(period_id):
    """Obtiene todas las materias de un periodo"""
    db = get_db()
    subjects_collection = db.subjects

    subjects = subjects_collection.find({
        "period_id": ObjectId(period_id)
    }).sort("name", 1)

    return list(subjects)

def verify_institute_admin(user_id, institute_id):
    """Verifica si un usuario es administrador del instituto"""
    db = get_db()
    institute_members_collection = db.institute_members

    admin = institute_members_collection.find_one({
        "institute_id": ObjectId(institute_id),
        "user_id": ObjectId(user_id),
        "role": "institute_admin"
    })

    return bool(admin)

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
        # Eliminar campos None
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

        # Obtener programas
        programs = list(programs_collection.find({"institute_id": ObjectId(institute_id)}))

        # Obtener miembros
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

def update_educational_program(program_id, data, admin_email):
    """Actualiza un programa educativo"""
    db = get_db()
    programs_collection = db.educational_programs
    users_collection = db.users

    # Verificar permisos
    admin = users_collection.find_one({"email": admin_email})
    if not admin or admin.get('role') not in ['admin', 'institute_admin']:
        return False, "No tienes permisos para actualizar programas"

    try:
        update_data = {
            "name": data.get("name"),
            "type": data.get("type"),
            "description": data.get("description"),
            "updated_at": datetime.now()
        }
        update_data = {k: v for k, v in update_data.items() if v is not None}

        result = programs_collection.update_one(
            {"_id": ObjectId(program_id)},
            {"$set": update_data}
        )
        return True, "Programa actualizado exitosamente"
    except Exception as e:
        return False, str(e)

def delete_educational_program(program_id, admin_email):
    """Elimina un programa educativo"""
    db = get_db()
    programs_collection = db.educational_programs
    periods_collection = db.academic_periods
    sections_collection = db.sections
    subjects_collection = db.subjects
    users_collection = db.users

    # Verificar permisos
    admin = users_collection.find_one({"email": admin_email})
    if not admin or admin.get('role') not in ['admin', 'institute_admin']:
        return False, "No tienes permisos para eliminar programas"

    try:
        # Eliminar secciones y materias asociadas
        periods = periods_collection.find({"program_id": ObjectId(program_id)})
        for period in periods:
            sections_collection.delete_many({"period_id": period["_id"]})
            subjects_collection.delete_many({"period_id": period["_id"]})

        # Eliminar periodos
        periods_collection.delete_many({"program_id": ObjectId(program_id)})

        # Eliminar programa
        programs_collection.delete_one({"_id": ObjectId(program_id)})
        
        return True, "Programa y datos asociados eliminados exitosamente"
    except Exception as e:
        return False, str(e)

def update_academic_period(period_id, data, admin_email):
    """Actualiza un periodo académico"""
    db = get_db()
    periods_collection = db.academic_periods
    users_collection = db.users

    # Verificar permisos
    admin = users_collection.find_one({"email": admin_email})
    if not admin or admin.get('role') not in ['admin', 'institute_admin']:
        return False, "No tienes permisos para actualizar periodos"

    try:
        update_data = {
            "name": data.get("name"),
            "type": data.get("type"),
            "updated_at": datetime.now()
        }
        update_data = {k: v for k, v in update_data.items() if v is not None}

        result = periods_collection.update_one(
            {"_id": ObjectId(period_id)},
            {"$set": update_data}
        )
        return True, "Periodo actualizado exitosamente"
    except Exception as e:
        return False, str(e)

def delete_academic_period(period_id, admin_email):
    """Elimina un periodo académico y sus datos asociados"""
    db = get_db()
    periods_collection = db.academic_periods
    sections_collection = db.sections
    subjects_collection = db.subjects
    classrooms_collection = db.classrooms
    users_collection = db.users

    # Verificar permisos
    admin = users_collection.find_one({"email": admin_email})
    if not admin or admin.get('role') not in ['admin', 'institute_admin']:
        return False, "No tienes permisos para eliminar periodos"

    try:
        # Eliminar classrooms asociados
        classrooms = classrooms_collection.find({"period_id": ObjectId(period_id)})
        for classroom in classrooms:
            # Eliminar membresías y contenidos de los classrooms
            db.classroom_members.delete_many({"classroom_id": classroom["_id"]})
            db.content.delete_many({"classroom_id": classroom["_id"]})

        classrooms_collection.delete_many({"period_id": ObjectId(period_id)})

        # Eliminar secciones y materias
        sections_collection.delete_many({"period_id": ObjectId(period_id)})
        subjects_collection.delete_many({"period_id": ObjectId(period_id)})

        # Eliminar periodo
        periods_collection.delete_one({"_id": ObjectId(period_id)})
        
        return True, "Periodo y datos asociados eliminados exitosamente"
    except Exception as e:
        return False, str(e)

def update_section(section_id, name, admin_email):
    """Actualiza una sección"""
    db = get_db()
    sections_collection = db.sections
    users_collection = db.users

    # Verificar permisos
    admin = users_collection.find_one({"email": admin_email})
    if not admin or admin.get('role') not in ['admin', 'institute_admin']:
        return False, "No tienes permisos para actualizar secciones"

    try:
        result = sections_collection.update_one(
            {"_id": ObjectId(section_id)},
            {"$set": {
                "name": name,
                "updated_at": datetime.now()
            }}
        )
        return True, "Sección actualizada exitosamente"
    except Exception as e:
        return False, str(e)

def update_subject(subject_id, name, admin_email):
    """Actualiza una materia"""
    db = get_db()
    subjects_collection = db.subjects
    users_collection = db.users

    # Verificar permisos
    admin = users_collection.find_one({"email": admin_email})
    if not admin or admin.get('role') not in ['admin', 'institute_admin']:
        return False, "No tienes permisos para actualizar materias"

    try:
        result = subjects_collection.update_one(
            {"_id": ObjectId(subject_id)},
            {"$set": {
                "name": name,
                "updated_at": datetime.now()
            }}
        )
        return True, "Materia actualizada exitosamente"
    except Exception as e:
        return False, str(e)

def invite_user_to_institute(admin_email, invitee_email, institute_id, role):
    """Invita a un usuario a un instituto"""
    db = get_db()
    users_collection = db.users
    institutes_collection = db.institutes
    institute_invitations_collection = db.institute_invitations

    # Verificar admin
    admin = users_collection.find_one({"email": admin_email})
    if not admin or admin.get('role') not in ['admin', 'institute_admin']:
        return False, "No tienes permisos para enviar invitaciones"

    # Verificar instituto
    institute = institutes_collection.find_one({"_id": ObjectId(institute_id)})
    if not institute:
        return False, "Instituto no encontrado"

    # Verificar usuario invitado
    invitee = users_collection.find_one({"email": invitee_email})
    if not invitee:
        return False, "Usuario invitado no encontrado"

    # Verificar si ya existe una invitación pendiente
    existing_invitation = institute_invitations_collection.find_one({
        "institute_id": ObjectId(institute_id),
        "invitee_id": invitee["_id"],
        "status": "pending"
    })
    if existing_invitation:
        return False, "Ya existe una invitación pendiente"

    new_invitation = {
        "institute_id": ObjectId(institute_id),
        "inviter_id": admin["_id"],
        "invitee_id": invitee["_id"],
        "role": role,
        "status": "pending",
        "created_at": datetime.now()
    }

    try:
        result = institute_invitations_collection.insert_one(new_invitation)
        return True, "Invitación enviada exitosamente"
    except Exception as e:
        return False, f"Error al enviar la invitación: {str(e)}"

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

        invitations.append({
            "id": str(invitation["_id"]),
            "institute_name": institute["name"],
            "institute_id": str(institute["_id"]),
            "role": invitation["role"],
            "inviter_name": inviter["name"],
            "inviter_email": inviter["email"],
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
        return False, "Invitación no encontrada"

    try:
        # Actualizar estado de la invitación
        institute_invitations_collection.update_one(
            {"_id": invitation["_id"]},
            {"$set": {
                "status": "accepted",
                "accepted_at": datetime.now()
            }}
        )

        # Crear membresía en el instituto
        new_member = {
            "institute_id": invitation["institute_id"],
            "user_id": user["_id"],
            "role": invitation["role"],
            "joined_at": datetime.now()
        }
        institute_members_collection.insert_one(new_member)

        # Actualizar rol del usuario si es necesario
        if invitation["role"] == "institute_admin":
            users_collection.update_one(
                {"_id": user["_id"]},
                {"$set": {"role": "institute_admin"}}
            )

        return True, "Invitación aceptada exitosamente"
    except Exception as e:
        return False, f"Error al aceptar la invitación: {str(e)}"

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
        return False, "Invitación no encontrada"

    try:
        result = institute_invitations_collection.update_one(
            {"_id": invitation["_id"]},
            {"$set": {
                "status": "rejected",
                "rejected_at": datetime.now()
            }}
        )
        return True, "Invitación rechazada exitosamente"
    except Exception as e:
        return False, f"Error al rechazar la invitación: {str(e)}"

def get_institute_by_email(email):
    """Obtiene la información del instituto asociado al email del usuario"""
    db = get_db()
    users_collection = db.users
    institute_members_collection = db.institute_members
    institutes_collection = db.institutes
    programs_collection = db.educational_programs

    try:
        # Buscar el usuario por email
        user = users_collection.find_one({"email": email})
        if not user:
            return None

        # Buscar la membresía del usuario en algún instituto
        member = institute_members_collection.find_one({"user_id": user["_id"]})
        if not member:
            return None

        # Obtener información del instituto
        institute = institutes_collection.find_one({"_id": member["institute_id"]})
        if not institute:
            return None

        # Obtener programas del instituto (si existen)
        programs = []
        if programs_collection.count_documents({"institute_id": institute["_id"]}) > 0:
            programs = list(programs_collection.find({"institute_id": institute["_id"]}))
            # Convertir ObjectId a string para todos los programas
            for program in programs:
                program["_id"] = str(program["_id"])
                program["institute_id"] = str(program["institute_id"])

        # Obtener miembros del instituto
        members = institute_members_collection.find({"institute_id": institute["_id"]})
        member_details = []
        for member in members:
            user_info = users_collection.find_one({"_id": member["user_id"]})
            if user_info:
                member_details.append({
                    "id": str(user_info["_id"]),
                    "name": user_info.get("name", ""),
                    "email": user_info.get("email", ""),
                    "role": member.get("role", ""),
                    "joined_at": member.get("joined_at", datetime.now())
                })

        # Preparar respuesta con campos opcionales
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

        # Agregar listas solo si tienen elementos
        if programs:
            institute_data["programs"] = programs
        if member_details:
            institute_data["members"] = member_details

        return institute_data

    except Exception as e:
        print(f"Error al obtener instituto por email: {str(e)}")
        return None