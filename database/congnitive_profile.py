from database.mongodb import get_db
from datetime import datetime
import re

profile = {
    "user_id": str,
    "profile": str,
    "status": str
}

def register_user(email, name, picture, birth_date, role):
    db = get_db()
    users_collection = db.users
    project_members_collection = db.project_members
    classrooms_collection = db.classrooms
    cognitive_profiles_collection = db.cognitive_profiles
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

    # create classroom
    new_classroom = {
        'name': name,
        'created_at': datetime.now()
    }
    classrooms_collection.insert_one(new_classroom)

    return user_id


def get_user_id_by_email(email):
    db = get_db()
    users_collection = db.users

    user = users_collection.find_one({"email": email}, {"_id": 1})
    if not user:
        print(f"No se encontró usuario con el email: {email}")
        return None
    user_id = user["_id"]
    return user_id

def get_cognitive_profile(email):
    db = get_db()
    cognitive_profiles_collection = db.cognitive_profiles

    user_id = get_user_id_by_email(email)

    profile = cognitive_profiles_collection.find_one({"user_id": user_id})
    return profile

def update_cognitive_profile(email, profile):
    db = get_db()
    cognitive_profiles_collection = db.cognitive_profiles

    user_id = get_user_id_by_email(email)

    cognitive_profiles_collection.update_one({"user_id": user_id}, {"$set": profile})

def create_cognitive_profile(email, profile, status):
    db = get_db()
    cognitive_profiles_collection = db.cognitive_profiles

    user_id = get_user_id_by_email(email)

    new_profile = {
        "user_id": user_id, 
        "status": status,
        "profile": profile,
        "date": datetime.now()
    }

    cognitive_profiles_collection.insert_one(new_profile)

def delete_cognitive_profile(email):
    db = get_db()
    cognitive_profiles_collection = db.cognitive_profiles

    user_id = get_user_id_by_email(email)

    cognitive_profiles_collection.delete_one({"user_id": user_id})
