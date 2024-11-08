from database.mongodb import get_db
from datetime import datetime
import re
from database.cognitive_profile import create_cognitive_profile
from bson.objectid import ObjectId

def verify_user_exists(email):
    db = get_db()
    users_collection = db.users

    existing_user = users_collection.find_one({'email': email})
    if existing_user:
        return {
            'exists': True,
            'role': existing_user.get('role', 'student')  # valor por defecto 'student'
        }
    return {
        'exists': False,
        'role': None
    }

def register_user(email, name, picture, birth_date, role, institute_id=None):
    db = get_db()
    users_collection = db.users
    institute_members_collection = db.institute_members

    # Validar rol
    valid_roles = ['admin', 'institute_admin', 'teacher', 'student']
    if role not in valid_roles:
        return False, "Rol inválido"

    # Verificar si ya existe el email
    if users_collection.find_one({'email': email}):
        return False, "El email ya está registrado"

    new_user = {
        'email': email,
        'name': name,
        'picture': picture,
        'birthdate': birth_date,
        'role': role,
        'created_at': datetime.now(),
        'status': 'active'
    }

    try:
        user_result = users_collection.insert_one(new_user)
        user_id = user_result.inserted_id

        # Si es profesor o admin de instituto, crear relación con el instituto
        if role in ['teacher', 'institute_admin'] and institute_id:
            new_member = {
                'institute_id': ObjectId(institute_id),
                'user_id': user_id,
                'role': role,
                'joined_at': datetime.now()
            }
            institute_members_collection.insert_one(new_member)

        if role == 'student':
            create_cognitive_profile(user_id)

        return True, str(user_id)
    except Exception as e:
        return False, str(e)

def get_user_by_email(email):
    db = get_db()
    users_collection = db.users

    user = users_collection.find_one({'email': email})
    return user

def search_users_by_partial_email(partial_email):
    db = get_db()
    users_collection = db.users

    regex_pattern = f'^{re.escape(partial_email)}'
    users = users_collection.find(
        {"email": {"$regex": regex_pattern, "$options": "i"}},
        {"email": 1, "_id": 0}
    ).limit(5)

    return [user['email'] for user in users]

def delete_student(email):
    db = get_db()
    users_collection = db.users
    classroom_members_collection = db.classroom_members
    cognitive_profiles_collection = db.cognitive_profiles
    classroom_invitations_collection = db.classroom_invitations
    contents_collection = db.contents

    try:
        # Obtener el usuario y verificar que sea estudiante
        user = users_collection.find_one({'email': email})
        if not user or user.get('role') != 'student':
            return False, "Usuario no encontrado o no es estudiante"

        user_id = user['_id']

        # Eliminar membresías de clase
        classroom_members_collection.delete_many({'user_id': user_id})

        # Eliminar invitaciones pendientes
        classroom_invitations_collection.delete_many({
            '$or': [
                {'invitee_id': user_id},
                {'inviter_id': user_id}
            ]
        })

        # Eliminar contenidos del estudiante
        contents_collection.delete_many({'student_id': user_id})

        # Eliminar perfil cognitivo
        cognitive_profiles_collection.delete_one({'student_id': user_id})  # Cambiado de user_id a student_id

        # Eliminar el usuario
        users_collection.delete_one({'_id': user_id})

        return True, "Estudiante y datos asociados eliminados exitosamente"

    except Exception as e:
        return False, f"Error al eliminar estudiante: {str(e)}"
