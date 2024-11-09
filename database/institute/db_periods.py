from database.mongodb import get_db
from datetime import datetime
from bson import ObjectId
import traceback

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
        # Eliminar classrooms asociados y sus datos
        classrooms = classrooms_collection.find({"period_id": ObjectId(period_id)})
        for classroom in classrooms:
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

def get_institute_periods(program_id):
    """Obtiene todos los períodos de un programa"""
    db = get_db()
    periods_collection = db.academic_periods

    try:
        print(f"Buscando períodos para programa: {program_id}")  # Debug
        
        # Validar que el program_id sea un ObjectId válido
        if not ObjectId.is_valid(program_id):
            print(f"ID de programa inválido: {program_id}")
            return []

        # Verificar si la colección existe
        if 'academic_periods' not in db.list_collection_names():
            print("La colección academic_periods no existe")
            return []

        # Buscar períodos
        periods = periods_collection.find({
            "program_id": ObjectId(program_id)
        })
        
        # Convertir cursor a lista y procesar
        periods_list = []
        for period in periods:
            period_data = {
                "id": str(period["_id"]),
                "program_id": str(period["program_id"]),
                "name": period.get("name", ""),
                "start_date": period.get("start_date"),
                "end_date": period.get("end_date"),
                "status": period.get("status", "active"),
                "created_at": period.get("created_at", datetime.now())
            }
            periods_list.append(period_data)
            
        print(f"Períodos encontrados: {len(periods_list)}")  # Debug
        return periods_list
        
    except Exception as e:
        print(f"Error detallado al obtener períodos: {str(e)}")
        traceback.print_exc()  # Imprime el stack trace completo
        return []

def get_period_sections(period_id):
    """Obtiene todas las secciones de un periodo"""
    db = get_db()
    sections_collection = db.sections

    try:
        sections = sections_collection.find({
            "period_id": ObjectId(period_id)
        }).sort("name", 1)
        return list(sections)
    except Exception as e:
        print(f"Error al obtener secciones: {str(e)}")
        return []

def get_period_subjects(period_id):
    """Obtiene todas las materias de un periodo"""
    db = get_db()
    subjects_collection = db.subjects

    try:
        subjects = subjects_collection.find({
            "period_id": ObjectId(period_id)
        }).sort("name", 1)
        return list(subjects)
    except Exception as e:
        print(f"Error al obtener materias: {str(e)}")
        return []

def create_section(program_id, period_id, name):
    """Crea una nueva sección en un periodo académico"""
    db = get_db()
    sections_collection = db.sections
    periods_collection = db.academic_periods

    # Verificar que el periodo existe y pertenece al programa
    period = periods_collection.find_one({
        "_id": ObjectId(period_id),
        "program_id": ObjectId(program_id)
    })
    
    if not period:
        return False, "Periodo no encontrado o no pertenece al programa"

    # Verificar si ya existe una sección con el mismo nombre en el periodo
    existing_section = sections_collection.find_one({
        "period_id": ObjectId(period_id),
        "name": name
    })

    if existing_section:
        return False, "Ya existe una sección con ese nombre en este periodo"

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

def update_section(section_id, name, admin_email):
    """Actualiza el nombre de una sección"""
    db = get_db()
    sections_collection = db.sections
    users_collection = db.users

    # Verificar permisos
    admin = users_collection.find_one({"email": admin_email})
    if not admin or admin.get('role') not in ['admin', 'institute_admin']:
        return False, "No tienes permisos para actualizar secciones"

    # Verificar si ya existe otra sección con el mismo nombre
    section = sections_collection.find_one({"_id": ObjectId(section_id)})
    if not section:
        return False, "Sección no encontrada"

    existing_section = sections_collection.find_one({
        "period_id": section["period_id"],
        "name": name,
        "_id": {"$ne": ObjectId(section_id)}
    })

    if existing_section:
        return False, "Ya existe otra sección con ese nombre en este periodo"

    try:
        result = sections_collection.update_one(
            {"_id": ObjectId(section_id)},
            {
                "$set": {
                    "name": name,
                    "updated_at": datetime.now()
                }
            }
        )
        return True, "Sección actualizada exitosamente"
    except Exception as e:
        return False, str(e)

def create_subject(program_id, period_id, name):
    """Crea una nueva materia en un periodo académico"""
    db = get_db()
    subjects_collection = db.subjects
    periods_collection = db.academic_periods

    # Verificar que el periodo existe y pertenece al programa
    period = periods_collection.find_one({
        "_id": ObjectId(period_id),
        "program_id": ObjectId(program_id)
    })
    
    if not period:
        return False, "Periodo no encontrado o no pertenece al programa"

    # Verificar si ya existe una materia con el mismo nombre en el periodo
    existing_subject = subjects_collection.find_one({
        "period_id": ObjectId(period_id),
        "name": name
    })

    if existing_subject:
        return False, "Ya existe una materia con ese nombre en este periodo"

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

def update_subject(subject_id, name, admin_email):
    """Actualiza el nombre de una materia"""
    db = get_db()
    subjects_collection = db.subjects
    users_collection = db.users

    # Verificar permisos
    admin = users_collection.find_one({"email": admin_email})
    if not admin or admin.get('role') not in ['admin', 'institute_admin']:
        return False, "No tienes permisos para actualizar materias"

    # Verificar si ya existe otra materia con el mismo nombre
    subject = subjects_collection.find_one({"_id": ObjectId(subject_id)})
    if not subject:
        return False, "Materia no encontrada"

    existing_subject = subjects_collection.find_one({
        "period_id": subject["period_id"],
        "name": name,
        "_id": {"$ne": ObjectId(subject_id)}
    })

    if existing_subject:
        return False, "Ya existe otra materia con ese nombre en este periodo"

    try:
        result = subjects_collection.update_one(
            {"_id": ObjectId(subject_id)},
            {
                "$set": {
                    "name": name,
                    "updated_at": datetime.now()
                }
            }
        )
        return True, "Materia actualizada exitosamente"
    except Exception as e:
        return False, str(e)