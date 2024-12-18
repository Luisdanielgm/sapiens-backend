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
            'role': existing_user.get('role', 'STUDENT')  # valor por defecto 'student'
        }
    return {
        'exists': False,
        'role': None
    }

def register_user(email, name, picture, birth_date, role, institute_name=None):
    db = get_db()
    users_collection = db.users
    institutes_collection = db.institutes
    institute_members_collection = db.institute_members

    try:
        # Validar rol
        valid_roles = ['ADMIN', 'INSTITUTE_ADMIN', 'TEACHER', 'STUDENT']
        if role.upper() not in valid_roles:
            return False, "Rol inválido"

        # Verificar si ya existe el email
        if users_collection.find_one({'email': email}):
            return False, "El email ya está registrado"

        # Validar que si es institute_admin venga el institute_name
        if role.upper() == 'INSTITUTE_ADMIN' and not institute_name:
            return False, "Se requiere el nombre del instituto para administradores de instituto"
        
        role = role.upper()

        # Crear el documento del usuario
        new_user = {
            'email': email,
            'name': name,
            'picture': picture,
            'birthdate': birth_date,
            'role': role,
            'created_at': datetime.now(),
            'status': 'active'
        }

        print(f"Intentando crear usuario: {new_user}")  # Debug log

        # Crear usuario
        user_result = users_collection.insert_one(new_user)
        if not user_result.inserted_id:
            return False, "Error al crear el usuario en la base de datos"

        user_id = user_result.inserted_id
        print(f"Usuario creado con ID: {user_id}")  # Debug log

        # Si es institute_admin, crear instituto y relación
        if role == 'INSTITUTE_ADMIN':
            new_institute = {
                'name': institute_name,
                'created_at': datetime.now(),
                'status': 'pending'
            }
            institute_result = institutes_collection.insert_one(new_institute)
            institute_id = institute_result.inserted_id

            # Crear relación en institute_members
            new_member = {
                'institute_id': institute_id,
                'user_id': user_id,
                'role': role,
                'joined_at': datetime.now()
            }
            institute_members_collection.insert_one(new_member)

        # Solo crear perfil cognitivo si es estudiante
        if role == 'STUDENT':
            print(f"Creando perfil cognitivo para estudiante ID: {user_id}")
            profile_created = create_cognitive_profile(user_id)
            if not profile_created:
                # Si falla la creación del perfil, eliminamos el usuario
                users_collection.delete_one({'_id': user_id})
                return False, "Error al crear el perfil cognitivo"
            print("Perfil cognitivo creado exitosamente")

        return True, str(user_id)

    except Exception as e:
        print(f"Error en register_user: {str(e)}")
        # Intentar limpiar si algo falló
        if 'user_id' in locals():
            try:
                users_collection.delete_one({'_id': user_id})
            except:
                pass
        return False, f"Error al registrar usuario: {str(e)}"

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
        if not user or user.get('role') != 'STUDENT':
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
