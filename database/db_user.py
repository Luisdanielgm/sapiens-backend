from database.mongodb import get_db
from datetime import datetime
import re

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

    return user_id

def get_user_by_email(email):
    db = get_db()
    users_collection = db.users

    user = users_collection.find_one({'email': email})
    return user

def get_user_id_by_email(email):
    db = get_db()
    users_collection = db.users

    user = users_collection.find_one({"email": email}, {"_id": 1})
    if not user:
        print(f"No se encontró usuario con el email: {email}")
        return None
    user_id = user["_id"]
    return user_id

def search_users_by_partial_email(partial_email):
    db = get_db()
    users_collection = db.users

    regex_pattern = f'^{re.escape(partial_email)}'
    users = users_collection.find(
        {"email": {"$regex": regex_pattern, "$options": "i"}},
        {"email": 1, "_id": 0}
    ).limit(5)

    return [user['email'] for user in users]