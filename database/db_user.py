from database.mongodb import get_db
from datetime import datetime
import re
from database.cognitive_profile import create_cognitive_profile

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

def register_user(email, name, picture, birth_date, role, classroom_name):
    db = get_db()
    classroom_members_collection = db.classroom_members
    classroom_collection = db.classrooms
    users_collection = db.users

    # Crear nuevo usuario
    new_user = {
        'email': email,
        'name': name,
        'picture': picture,
        'birthDate': birth_date,
        'role': role,
        'created_at': datetime.now()
    }
    user_result = users_collection.insert_one(new_user)
    user_id = user_result.inserted_id

    if role == 'teacher':
        new_classroom = {
            'name': classroom_name,
            'created_at': datetime.now()
        }
        classroom_result = classroom_collection.insert_one(new_classroom)
        classroom_id = classroom_result.inserted_id

        # Asignar al usuario como administrador del proyecto
        new_member = {
            'user_id': user_id,
            'classroom_id': classroom_id,
            'role': 'teacher',
            'joined_at': datetime.now()
        }
        classroom_members_collection.insert_one(new_member)

    if role == 'student':
        create_cognitive_profile(email)

    return user_id

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
    invitations_collection = db.invitations

    try:
        # Obtener el usuario y verificar que sea estudiante
        user = users_collection.find_one({'email': email})
        if not user or user.get('role') != 'student':
            return False, "Usuario no encontrado o no es estudiante"

        user_id = user['_id']

        # Eliminar membresías de clase
        classroom_members_collection.delete_many({'user_id': user_id})

        # Eliminar invitaciones pendientes
        invitations_collection.delete_many({
            '$or': [
                {'invitee_email': email},
                {'inviter_email': email}
            ]
        })

        # Eliminar perfil cognitivo
        cognitive_profiles_collection.delete_one({'user_id': user_id})

        # Eliminar el usuario
        users_collection.delete_one({'_id': user_id})

        return True, "Estudiante y datos asociados eliminados exitosamente"

    except Exception as e:
        return False, f"Error al eliminar estudiante: {str(e)}"
