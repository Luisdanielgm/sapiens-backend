from database.mongodb import get_db

def get_user_id_by_email(email):
    """
    Obtiene el ID de usuario por email.
    """
    db = get_db()
    users_collection = db.users

    user = users_collection.find_one({"email": email}, {"_id": 1})
    if not user:
        print(f"No se encontró usuario con el email: {email}")
        return None
    return user["_id"]
