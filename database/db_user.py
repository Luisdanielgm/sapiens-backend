from database.mongodb import get_db
from datetime import datetime
import re

def verify_user_exists(email):  # Función simplificada para verificar si el usuario existe
    db = get_db()
    users_collection = db.users

    existing_user = users_collection.find_one({'email': email})
    return bool(existing_user)

def register_user(email, name, picture, birth_date, role):
    db = get_db()
    users_collection = db.users
    project_members_collection = db.project_members

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
    user_role = role.lower()

    # Asignar al usuario como administrador del proyecto
    new_member = {
        'user_id': user_id,
        'role': user_role,
        'joined_at': datetime.now()
    }
    project_members_collection.insert_one(new_member)

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