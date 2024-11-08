from database.mongodb import get_db
from datetime import datetime
from bson import ObjectId

def create_educational_program(institute_id, name, program_type):
    """Crea un nuevo programa educativo"""
    db = get_db()
    programs_collection = db.educational_programs

    new_program = {
        "institute_id": ObjectId(institute_id),
        "name": name,
        "type": program_type,
        "created_at": datetime.now()
    }

    try:
        result = programs_collection.insert_one(new_program)
        return True, str(result.inserted_id)
    except Exception as e:
        return False, str(e)

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
    """Elimina un programa educativo y sus datos asociados"""
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

def get_institute_programs(institute_id):
    """Obtiene todos los programas de un instituto"""
    db = get_db()
    programs_collection = db.educational_programs

    try:
        programs = programs_collection.find({
            "institute_id": ObjectId(institute_id)
        })
        return list(programs)
    except Exception as e:
        print(f"Error al obtener programas: {str(e)}")
        return []