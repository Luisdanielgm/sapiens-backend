from flask import request
from typing import Dict

from src.shared.standardization import APIBlueprint, APIRoute, ErrorCodes
from src.shared.constants import ROLES
from src.profiles.services import ProfileService
from src.shared.logging import log_info, log_error

profiles_bp = APIBlueprint('profiles', __name__)
profile_service = ProfileService()

#
# RUTAS PARA PERFILES DE USUARIO GENERALES
#

@profiles_bp.route('/user/<user_id_or_email>', methods=['GET'])
@APIRoute.standard(auth_required_flag=True)
def get_user_profile(user_id_or_email):
    """
    Obtiene el perfil completo de un usuario, incluyendo su perfil específico según el rol.
    
    Args:
        user_id_or_email: ID o email del usuario
    """
    try:
        profile = profile_service.get_user_profile(user_id_or_email)
        
        if profile:
            return APIRoute.success(data={"profile": profile})
        return APIRoute.error(
            ErrorCodes.RESOURCE_NOT_FOUND,
            "Perfil de usuario no encontrado",
            status_code=404
        )
    except Exception as e:
        log_error(f"Error al obtener perfil de usuario: {str(e)}", e, "profiles.routes")
        return APIRoute.error(
            ErrorCodes.SERVER_ERROR,
            str(e),
            status_code=500
        )

@profiles_bp.route('/create/<user_id_or_email>', methods=['POST'])
@APIRoute.standard(auth_required_flag=True, roles=[ROLES["ADMIN"], ROLES["INSTITUTE_ADMIN"]])
def create_user_profile(user_id_or_email):
    """
    Crea el perfil adecuado según el rol del usuario.
    
    Args:
        user_id_or_email: ID o email del usuario
    """
    try:
        data = request.get_json() or {}
        user_role = data.get('role')  # Opcional, si no se proporciona se obtiene de la base de datos
        
        success, message = profile_service.create_profile_for_user(user_id_or_email, user_role)
        
        if success:
            return APIRoute.success(
                data={"id": message},
                message="Perfil creado correctamente"
            )
        return APIRoute.error(
            ErrorCodes.BAD_REQUEST,
            message,
            status_code=400
        )
    except Exception as e:
        log_error(f"Error al crear perfil de usuario: {str(e)}", e, "profiles.routes")
        return APIRoute.error(
            ErrorCodes.SERVER_ERROR,
            str(e),
            status_code=500
        )

#
# RUTAS PARA PERFILES DE PROFESOR
#

@profiles_bp.route('/teacher', methods=['POST'])
@APIRoute.standard(auth_required_flag=True, required_fields=['user_id_or_email', 'profile_data'])
def create_teacher_profile():
    """
    Crea un perfil de profesor para un usuario específico.
    
    Body:
        user_id_or_email: ID o email del usuario profesor
        profile_data: Datos del perfil a crear
    """
    data = request.get_json()
    user_id_or_email = data.get('user_id_or_email')
    profile_data = data.get('profile_data', {})
    
    success, result = profile_service.create_teacher_profile(user_id_or_email, profile_data)
    
    if success:
        return APIRoute.success(
            data={"id": result},
            message="Perfil de profesor creado correctamente"
        )
    return APIRoute.error(
        ErrorCodes.BAD_REQUEST,
        result,
        status_code=400
    )

@profiles_bp.route('/teacher/<user_id_or_email>', methods=['GET'])
@APIRoute.standard(auth_required_flag=True)
def get_teacher_profile(user_id_or_email):
    """
    Obtiene el perfil de profesor para un usuario específico.
    
    Args:
        user_id_or_email: ID o email del usuario profesor
    """
    try:
        profile = profile_service.get_teacher_profile(user_id_or_email)
        
        if profile:
            return APIRoute.success(data={"profile": profile})
        return APIRoute.error(
            ErrorCodes.RESOURCE_NOT_FOUND,
            "Perfil de profesor no encontrado",
            status_code=404
        )
    except Exception as e:
        return APIRoute.error(
            ErrorCodes.SERVER_ERROR,
            str(e),
            status_code=500
        )

@profiles_bp.route('/teacher', methods=['PUT'])
@APIRoute.standard(auth_required_flag=True, required_fields=['user_id_or_email', 'profile_data'])
def update_teacher_profile():
    """
    Actualiza el perfil de profesor para un usuario específico.
    
    Body:
        user_id_or_email: ID o email del usuario profesor
        profile_data: Datos a actualizar en el perfil
    """
    data = request.get_json()
    user_id_or_email = data.get('user_id_or_email')
    profile_data = data.get('profile_data', {})
    
    try:
        success = profile_service.update_teacher_profile(user_id_or_email, profile_data)
        if success:
            return APIRoute.success(data={"message": "Perfil de profesor actualizado correctamente"}, message="Perfil de profesor actualizado correctamente")
        else:
            return APIRoute.error(
                ErrorCodes.BAD_REQUEST,
                "No se pudo actualizar el perfil",
                status_code=400
            )
    except Exception as e:
        log_error(f"Error al actualizar perfil de profesor: {str(e)}", e, "profiles.routes")
        return APIRoute.error(
            ErrorCodes.SERVER_ERROR,
            str(e),
            status_code=500
        )

@profiles_bp.route('/teacher/<user_id_or_email>', methods=['DELETE'])
@APIRoute.standard(auth_required_flag=True, roles=[ROLES["ADMIN"], ROLES["INSTITUTE_ADMIN"]])
def delete_teacher_profile(user_id_or_email):
    """
    Elimina el perfil de profesor para un usuario específico.
    
    Args:
        user_id_or_email: ID o email del usuario profesor
    """
    try:
        success = profile_service.delete_teacher_profile(user_id_or_email)
        
        if success:
            return APIRoute.success(data={"message": "Perfil de profesor eliminado correctamente"}, message="Perfil de profesor eliminado correctamente")
        return APIRoute.error(
            ErrorCodes.RESOURCE_NOT_FOUND,
            "Perfil de profesor no encontrado",
            status_code=404
        )
    except Exception as e:
        log_error(f"Error al eliminar perfil de profesor: {str(e)}", e, "profiles.routes")
        return APIRoute.error(
            ErrorCodes.SERVER_ERROR,
            str(e),
            status_code=500
        )

#
# RUTAS PARA PERFILES DE ESTUDIANTE
#

@profiles_bp.route('/student', methods=['POST'])
@APIRoute.standard(auth_required_flag=True, required_fields=['user_id_or_email', 'profile_data'])
def create_student_profile():
    """
    Crea un perfil de estudiante para un usuario específico.
    
    Body:
        user_id_or_email: ID o email del usuario estudiante
        profile_data: Datos del perfil a crear
    """
    data = request.get_json()
    user_id_or_email = data.get('user_id_or_email')
    profile_data = data.get('profile_data', {})
    
    success, result = profile_service.create_student_profile(user_id_or_email, profile_data)
    
    if success:
        return APIRoute.success(
            data={"id": result},
            message="Perfil de estudiante creado correctamente"
        )
    return APIRoute.error(
        ErrorCodes.BAD_REQUEST,
        result,
        status_code=400
    )

@profiles_bp.route('/student/<user_id_or_email>', methods=['GET'])
@APIRoute.standard(auth_required_flag=True)
def get_student_profile(user_id_or_email):
    """
    Obtiene el perfil de estudiante para un usuario específico.
    
    Args:
        user_id_or_email: ID o email del usuario estudiante
    """
    try:
        log_info(f"Solicitud de perfil estudiante para: {user_id_or_email}", "profiles.routes")
        
        profile = profile_service.get_student_profile(user_id_or_email)
        
        if profile:
            return APIRoute.success(data={"profile": profile})
        return APIRoute.error(
            ErrorCodes.RESOURCE_NOT_FOUND,
            "Perfil de estudiante no encontrado",
            status_code=404
        )
    except Exception as e:
        log_error(f"Error al obtener perfil de estudiante: {str(e)}", e, "profiles.routes")
        return APIRoute.error(
            ErrorCodes.SERVER_ERROR,
            str(e),
            status_code=500
        )

@profiles_bp.route('/student', methods=['PUT'])
@APIRoute.standard(auth_required_flag=True, required_fields=['user_id_or_email', 'profile_data'])
def update_student_profile():
    """
    Actualiza el perfil de estudiante para un usuario específico.
    
    Body:
        user_id_or_email: ID o email del usuario estudiante
        profile_data: Datos a actualizar en el perfil
    """
    data = request.get_json()
    user_id_or_email = data.get('user_id_or_email')
    profile_data = data.get('profile_data', {})
    
    try:
        success = profile_service.update_student_profile(user_id_or_email, profile_data)
        if success:
            return APIRoute.success(data={"message": "Perfil de estudiante actualizado correctamente"}, message="Perfil de estudiante actualizado correctamente")
        else:
            return APIRoute.error(
                ErrorCodes.BAD_REQUEST,
                "No se pudo actualizar el perfil",
                status_code=400
            )
    except Exception as e:
        log_error(f"Error al actualizar perfil de estudiante: {str(e)}", e, "profiles.routes")
        return APIRoute.error(
            ErrorCodes.SERVER_ERROR,
            str(e),
            status_code=500
        )

@profiles_bp.route('/student', methods=['GET'])
@APIRoute.standard(auth_required_flag=True)
def get_student_profile_by_query():
    """
    Obtiene el perfil de estudiante usando el email como parámetro de consulta.
    
    Query params:
        email: Email del usuario estudiante
    """
    try:
        email = request.args.get('email')
        if not email:
            return APIRoute.error(
                ErrorCodes.MISSING_FIELDS,
                "Se requiere el parámetro 'email'",
                status_code=400
            )
            
        log_info(f"Solicitud de perfil estudiante por query param para email: {email}", "profiles.routes")
        
        profile = profile_service.get_student_profile(email)
        
        if profile:
            return APIRoute.success(data={"profile": profile})
        return APIRoute.error(
            ErrorCodes.RESOURCE_NOT_FOUND,
            "Perfil de estudiante no encontrado",
            status_code=404
        )
    except Exception as e:
        log_error(f"Error al obtener perfil de estudiante por query param: {str(e)}", e, "profiles.routes")
        return APIRoute.error(
            ErrorCodes.SERVER_ERROR,
            str(e),
            status_code=500
        )

@profiles_bp.route('/student/<user_id_or_email>', methods=['DELETE'])
@APIRoute.standard(auth_required_flag=True, roles=[ROLES["ADMIN"], ROLES["INSTITUTE_ADMIN"]])
def delete_student_profile(user_id_or_email):
    """
    Elimina el perfil de estudiante para un usuario específico.
    
    Args:
        user_id_or_email: ID o email del usuario estudiante
    """
    try:
        success = profile_service.delete_student_profile(user_id_or_email)
        
        if success:
            return APIRoute.success(data={"message": "Perfil de estudiante eliminado correctamente"}, message="Perfil de estudiante eliminado correctamente")
        return APIRoute.error(
            ErrorCodes.RESOURCE_NOT_FOUND,
            "Perfil de estudiante no encontrado",
            status_code=404
        )
    except Exception as e:
        log_error(f"Error al eliminar perfil de estudiante: {str(e)}", e, "profiles.routes")
        return APIRoute.error(
            ErrorCodes.SERVER_ERROR,
            str(e),
            status_code=500
        )

#
# RUTAS PARA PERFILES DE ADMINISTRADOR
#

@profiles_bp.route('/admin', methods=['POST'])
@APIRoute.standard(auth_required_flag=True, roles=[ROLES["ADMIN"]], required_fields=['user_id_or_email', 'profile_data'])
def create_admin_profile():
    """
    Crea un perfil de administrador para un usuario específico.
    
    Body:
        user_id_or_email: ID o email del usuario administrador
        profile_data: Datos del perfil a crear
    """
    data = request.get_json()
    user_id_or_email = data.get('user_id_or_email')
    profile_data = data.get('profile_data', {})
    
    success, result = profile_service.create_admin_profile(user_id_or_email, profile_data)
    
    if success:
        return APIRoute.success(
            data={"id": result},
            message="Perfil de administrador creado correctamente"
        )
    return APIRoute.error(
        ErrorCodes.BAD_REQUEST,
        result,
        status_code=400
    )

@profiles_bp.route('/admin/<user_id_or_email>', methods=['GET'])
@APIRoute.standard(auth_required_flag=True, roles=[ROLES["ADMIN"], ROLES["INSTITUTE_ADMIN"]])
def get_admin_profile(user_id_or_email):
    """
    Obtiene el perfil de administrador para un usuario específico.
    
    Args:
        user_id_or_email: ID o email del usuario administrador
    """
    try:
        profile = profile_service.get_admin_profile(user_id_or_email)
        
        if profile:
            return APIRoute.success(data={"profile": profile})
        return APIRoute.error(
            ErrorCodes.RESOURCE_NOT_FOUND,
            "Perfil de administrador no encontrado",
            status_code=404
        )
    except Exception as e:
        return APIRoute.error(
            ErrorCodes.SERVER_ERROR,
            str(e),
            status_code=500
        )

@profiles_bp.route('/admin', methods=['PUT'])
@APIRoute.standard(auth_required_flag=True, roles=[ROLES["ADMIN"], ROLES["INSTITUTE_ADMIN"]], required_fields=['user_id_or_email', 'profile_data'])
def update_admin_profile():
    """
    Actualiza el perfil de administrador para un usuario específico.
    
    Body:
        user_id_or_email: ID o email del usuario administrador
        profile_data: Datos a actualizar en el perfil
    """
    data = request.get_json()
    user_id_or_email = data.get('user_id_or_email')
    profile_data = data.get('profile_data', {})
    
    try:
        success = profile_service.update_admin_profile(user_id_or_email, profile_data)
        if success:
            return APIRoute.success(data={"message": "Perfil de administrador actualizado correctamente"}, message="Perfil de administrador actualizado correctamente")
        else:
            return APIRoute.error(
                ErrorCodes.BAD_REQUEST,
                "No se pudo actualizar el perfil",
                status_code=400
            )
    except Exception as e:
        log_error(f"Error al actualizar perfil de administrador: {str(e)}", e, "profiles.routes")
        return APIRoute.error(
            ErrorCodes.SERVER_ERROR,
            str(e),
            status_code=500
        )

@profiles_bp.route('/admin/<user_id_or_email>', methods=['DELETE'])
@APIRoute.standard(auth_required_flag=True, roles=[ROLES["ADMIN"]])
def delete_admin_profile(user_id_or_email):
    """
    Elimina el perfil de administrador para un usuario específico.
    
    Args:
        user_id_or_email: ID o email del usuario administrador
    """
    try:
        success = profile_service.delete_admin_profile(user_id_or_email)
        
        if success:
            return APIRoute.success(data={"message": "Perfil de administrador eliminado correctamente"}, message="Perfil de administrador eliminado correctamente")
        return APIRoute.error(
            ErrorCodes.RESOURCE_NOT_FOUND,
            "Perfil de administrador no encontrado",
            status_code=404
        )
    except Exception as e:
        log_error(f"Error al eliminar perfil de administrador: {str(e)}", e, "profiles.routes")
        return APIRoute.error(
            ErrorCodes.SERVER_ERROR,
            str(e),
            status_code=500
        )

#
# RUTAS PARA PERFILES DE ADMINISTRADOR DE INSTITUTO
#

@profiles_bp.route('/institute-admin', methods=['POST'])
@APIRoute.standard(auth_required_flag=True, roles=[ROLES["ADMIN"]], 
                   required_fields=['user_id_or_email', 'institute_id'])
def create_institute_admin_profile():
    """
    Crea un perfil de administrador de instituto para un usuario específico.
    
    Body:
        user_id_or_email: ID o email del usuario administrador de instituto
        institute_id: ID del instituto que administra
        profile_data: Datos adicionales del perfil (opcional)
    """
    data = request.get_json()
    user_id_or_email = data.get('user_id_or_email')
    institute_id = data.get('institute_id')
    profile_data = data.get('profile_data', {})
    
    success, result = profile_service.create_institute_admin_profile(user_id_or_email, institute_id, profile_data)
    
    if success:
        return APIRoute.success(
            data={"id": result},
            message="Perfil de administrador de instituto creado correctamente"
        )
    return APIRoute.error(
        ErrorCodes.BAD_REQUEST,
        result,
        status_code=400
    )

@profiles_bp.route('/institute-admin/<user_id_or_email>', methods=['GET'])
@APIRoute.standard(auth_required_flag=True, roles=[ROLES["ADMIN"], ROLES["INSTITUTE_ADMIN"]])
def get_institute_admin_profile(user_id_or_email):
    """
    Obtiene el perfil de administrador de instituto para un usuario específico.
    
    Args:
        user_id_or_email: ID o email del usuario administrador de instituto
    """
    try:
        profile = profile_service.get_institute_admin_profile(user_id_or_email)
        
        if profile:
            return APIRoute.success(data={"profile": profile})
        return APIRoute.error(
            ErrorCodes.RESOURCE_NOT_FOUND,
            "Perfil de administrador de instituto no encontrado",
            status_code=404
        )
    except Exception as e:
        log_error(f"Error al obtener perfil de administrador de instituto: {str(e)}", e, "profiles.routes")
        return APIRoute.error(
            ErrorCodes.SERVER_ERROR,
            str(e),
            status_code=500
        )

@profiles_bp.route('/institute-admin', methods=['PUT'])
@APIRoute.standard(auth_required_flag=True, roles=[ROLES["ADMIN"], ROLES["INSTITUTE_ADMIN"]], 
                   required_fields=['user_id_or_email', 'profile_data'])
def update_institute_admin_profile():
    """
    Actualiza el perfil de administrador de instituto para un usuario específico.
    
    Body:
        user_id_or_email: ID o email del usuario administrador de instituto
        profile_data: Datos a actualizar en el perfil
    """
    data = request.get_json()
    user_id_or_email = data.get('user_id_or_email')
    profile_data = data.get('profile_data', {})
    
    # Verificar que el usuario actual tenga permisos para actualizar este perfil
    # Usar request.user_id y request.user_role establecidos por @auth_required
    current_user_id = getattr(request, 'user_id', None)
    current_user_roles_list = getattr(request, 'user_roles', [])
    current_user_role = current_user_roles_list[0] if current_user_roles_list else None
    
    if not current_user_id or not current_user_role:
        # Esto no debería suceder si @auth_required funciona, pero es una comprobación segura
        return APIRoute.error(ErrorCodes.UNAUTHORIZED, "Usuario no autenticado.", status_code=401)

    if current_user_role == ROLES["INSTITUTE_ADMIN"]:
        # Si es INSTITUTE_ADMIN, solo puede actualizar su propio perfil
        target_user_id = profile_service._get_user_id(user_id_or_email)
        if not target_user_id or str(current_user_id) != str(target_user_id):
            return APIRoute.error(
                ErrorCodes.FORBIDDEN,
                "No tiene permisos para actualizar este perfil",
                status_code=403
            )
    
    success = profile_service.update_institute_admin_profile(user_id_or_email, profile_data)
    
    if success:
        return APIRoute.success(data={"message": "Perfil de administrador de instituto actualizado correctamente"}, message="Perfil de administrador de instituto actualizado correctamente")
    return APIRoute.error(
        ErrorCodes.BAD_REQUEST,
        "No se pudo actualizar el perfil de administrador de instituto",
        status_code=400
    )

@profiles_bp.route('/institute-admin/<user_id_or_email>', methods=['DELETE'])
@APIRoute.standard(auth_required_flag=True, roles=[ROLES["ADMIN"]])
def delete_institute_admin_profile(user_id_or_email):
    """
    Elimina el perfil de administrador de instituto para un usuario específico.
    
    Args:
        user_id_or_email: ID o email del usuario administrador de instituto
    """
    try:
        success = profile_service.delete_institute_admin_profile(user_id_or_email)
        
        if success:
            return APIRoute.success(data={"message": "Perfil de administrador de instituto eliminado correctamente"}, message="Perfil de administrador de instituto eliminado correctamente")
        return APIRoute.error(
            ErrorCodes.RESOURCE_NOT_FOUND,
            "Perfil de administrador de instituto no encontrado",
            status_code=404
        )
    except Exception as e:
        log_error(f"Error al eliminar perfil de administrador de instituto: {str(e)}", e, "profiles.routes")
        return APIRoute.error(
            ErrorCodes.SERVER_ERROR,
            str(e),
            status_code=500
        )

#
# RUTAS PARA PERFILES DE INSTITUTO
#

@profiles_bp.route('/institute', methods=['POST'])
@APIRoute.standard(auth_required_flag=True, roles=[ROLES["ADMIN"], ROLES["INSTITUTE_ADMIN"]], 
                   required_fields=['institute_id', 'name'])
def create_institute_profile(): 
    """
    Crea un perfil para un instituto específico.
    
    Body:
        institute_id: ID del instituto
        name: Nombre del instituto
        profile_data: Datos adicionales del perfil (opcional)
    """
    data = request.get_json()
    institute_id = data.get('institute_id')
    name = data.get('name')
    profile_data = data.get('profile_data', {})
    
    # Si es INSTITUTE_ADMIN, verificar que pertenezca al instituto
    # Usar request.user_id y request.user_role establecidos por @auth_required
    current_user_id = getattr(request, 'user_id', None)
    current_user_roles_list = getattr(request, 'user_roles', [])
    current_user_role = current_user_roles_list[0] if current_user_roles_list else None

    if not current_user_id or not current_user_role:
        return APIRoute.error(ErrorCodes.UNAUTHORIZED, "Usuario no autenticado.", status_code=401)

    if current_user_role == ROLES["INSTITUTE_ADMIN"]:
        try:
            user_obj_id = ObjectId(current_user_id)
            institute_obj_id = ObjectId(institute_id)
            institute_member = profile_service.db.institute_members.find_one({
                "user_id": user_obj_id,
                "institute_id": institute_obj_id,
                "role": ROLES["INSTITUTE_ADMIN"] # Asegurar que verificamos el rol correcto
            })
            
            if not institute_member:
                return APIRoute.error(
                    ErrorCodes.FORBIDDEN,
                    "No tiene permisos para crear un perfil para este instituto",
                    status_code=403
                )
        except Exception as e:
             log_error(f"Error al verificar membresía de instituto para {current_user_id}: {str(e)}", e, "profiles.routes")
             return APIRoute.error(ErrorCodes.BAD_REQUEST, f"Error al verificar instituto: {str(e)}", status_code=400)

    success, result = profile_service.create_institute_profile(institute_id, name, profile_data)
    
    if success:
        return APIRoute.success(
            data={"id": result},
            message="Perfil de instituto creado correctamente"
        )
    return APIRoute.error(
        ErrorCodes.BAD_REQUEST,
        result,
        status_code=400
    )

@profiles_bp.route('/institute/<institute_id>', methods=['GET'])
@APIRoute.standard(auth_required_flag=True)
def get_institute_profile(institute_id):
    """
    Obtiene el perfil de un instituto específico.
    
    Args:
        institute_id: ID del instituto
    """
    try:
        profile = profile_service.get_institute_profile(institute_id)
        
        if profile:
            return APIRoute.success(data={"profile": profile})
        return APIRoute.error(
            ErrorCodes.RESOURCE_NOT_FOUND,
            "Perfil de instituto no encontrado",
            status_code=404
        )
    except Exception as e:
        log_error(f"Error al obtener perfil de instituto: {str(e)}", e, "profiles.routes")
        return APIRoute.error(
            ErrorCodes.SERVER_ERROR,
            str(e),
            status_code=500
        )

@profiles_bp.route('/institute/<institute_id>', methods=['PUT'])
@APIRoute.standard(auth_required_flag=True, roles=[ROLES["ADMIN"], ROLES["INSTITUTE_ADMIN"]], 
                   required_fields=['profile_data'])
def update_institute_profile(institute_id):
    """
    Actualiza el perfil de un instituto específico.
    
    Args:
        institute_id: ID del instituto
        
    Body:
        profile_data: Datos a actualizar en el perfil
    """
    data = request.get_json()
    profile_data = data.get('profile_data', {})
    
    # Si es INSTITUTE_ADMIN, verificar que pertenezca al instituto
    # Usar request.user_id y request.user_role establecidos por @auth_required
    current_user_id = getattr(request, 'user_id', None)
    current_user_roles_list = getattr(request, 'user_roles', [])
    current_user_role = current_user_roles_list[0] if current_user_roles_list else None

    if not current_user_id or not current_user_role:
        return APIRoute.error(ErrorCodes.UNAUTHORIZED, "Usuario no autenticado.", status_code=401)

    if current_user_role == ROLES["INSTITUTE_ADMIN"]:
        try:
            user_obj_id = ObjectId(current_user_id)
            institute_obj_id = ObjectId(institute_id)
            institute_member = profile_service.db.institute_members.find_one({
                "user_id": user_obj_id,
                "institute_id": institute_obj_id,
                "role": ROLES["INSTITUTE_ADMIN"] # Asegurar que verificamos el rol correcto
            })
            
            if not institute_member:
                return APIRoute.error(
                    ErrorCodes.FORBIDDEN,
                    "No tiene permisos para actualizar el perfil de este instituto",
                    status_code=403
                )
        except Exception as e:
             log_error(f"Error al verificar membresía de instituto para {current_user_id}: {str(e)}", e, "profiles.routes")
             return APIRoute.error(ErrorCodes.BAD_REQUEST, f"Error al verificar instituto: {str(e)}", status_code=400)

    success = profile_service.update_institute_profile(institute_id, profile_data)
    
    if success:
        return APIRoute.success(data={"message": "Perfil de instituto actualizado correctamente"}, message="Perfil de instituto actualizado correctamente")
    return APIRoute.error(
        ErrorCodes.BAD_REQUEST,
        "No se pudo actualizar el perfil de instituto",
        status_code=400
    )

@profiles_bp.route('/institute/<institute_id>', methods=['DELETE'])
@APIRoute.standard(auth_required_flag=True, roles=[ROLES["ADMIN"]])
def delete_institute_profile(institute_id):
    """
    Elimina el perfil de un instituto específico.
    
    Args:
        institute_id: ID del instituto
    """
    try:
        success = profile_service.delete_institute_profile(institute_id)
        
        if success:
            return APIRoute.success(data={"message": "Perfil de instituto eliminado correctamente"}, message="Perfil de instituto eliminado correctamente")
        return APIRoute.error(
            ErrorCodes.RESOURCE_NOT_FOUND,
            "Perfil de instituto no encontrado",
            status_code=404
        )
    except Exception as e:
        log_error(f"Error al eliminar perfil de instituto: {str(e)}", e, "profiles.routes")
        return APIRoute.error(
            ErrorCodes.SERVER_ERROR,
            str(e),
            status_code=500
        )

#
# RUTAS PARA PERFILES COGNITIVOS
#

@profiles_bp.route('/cognitive', methods=['POST'])
@APIRoute.standard(auth_required_flag=True, required_fields=['user_id_or_email'])
def create_cognitive_profile():
    """
    Crea un perfil cognitivo para un usuario específico.
    
    Body:
        user_id_or_email: ID o email del usuario
        profile_data: Datos del perfil cognitivo (opcional)
    """
    data = request.get_json()
    user_id_or_email = data.get('user_id_or_email')
    profile_data = data.get('profile_data', None)
    
    success, result = profile_service.create_cognitive_profile(user_id_or_email, profile_data)
    
    if success:
        return APIRoute.success(
            data={"id": result},
            message="Perfil cognitivo creado correctamente"
        )
    return APIRoute.error(
        ErrorCodes.BAD_REQUEST,
        result,
        status_code=400
    )

@profiles_bp.route('/cognitive/<user_id_or_email>', methods=['GET'])
@APIRoute.standard(auth_required_flag=True)
def get_cognitive_profile(user_id_or_email):
    """
    Obtiene el perfil cognitivo para un estudiante específico.
    
    Args:
        user_id_or_email: ID o email del usuario estudiante
    """
    try:
        profile = profile_service.get_cognitive_profile(user_id_or_email)
        
        if profile:
            return APIRoute.success(data={"profile": profile})
        return APIRoute.error(
            ErrorCodes.RESOURCE_NOT_FOUND,
            "Perfil cognitivo no encontrado",
            status_code=404
        )
    except Exception as e:
        log_error(f"Error al obtener perfil cognitivo: {str(e)}", e, "profiles.routes")
        return APIRoute.error(
            ErrorCodes.SERVER_ERROR,
            str(e),
            status_code=500
        )

@profiles_bp.route('/cognitive', methods=['PUT'])
@APIRoute.standard(auth_required_flag=True, required_fields=['user_id_or_email', 'profile_data'])
def update_cognitive_profile():
    """
    Actualiza el perfil cognitivo para un estudiante específico.
    
    Body:
        user_id_or_email: ID o email del usuario estudiante
        profile_data: Datos a actualizar en el perfil
    """
    data = request.get_json()
    user_id_or_email = data.get('user_id_or_email')
    profile_data = data.get('profile_data', {})
    
    success = profile_service.update_cognitive_profile(user_id_or_email, profile_data)
    
    if success:
        return APIRoute.success(data={"message": "Perfil cognitivo actualizado correctamente"}, message="Perfil cognitivo actualizado correctamente")
    return APIRoute.error(
        ErrorCodes.BAD_REQUEST,
        "No se pudo actualizar el perfil cognitivo",
        status_code=400
    )

@profiles_bp.route('/cognitive/<user_id_or_email>', methods=['DELETE'])
@APIRoute.standard(auth_required_flag=True, roles=[ROLES["ADMIN"], ROLES["INSTITUTE_ADMIN"]])
def delete_cognitive_profile(user_id_or_email):
    """
    Elimina el perfil cognitivo para un estudiante específico.
    
    Args:
        user_id_or_email: ID o email del usuario estudiante
    """
    try:
        success = profile_service.delete_cognitive_profile(user_id_or_email)
        
        if success:
            return APIRoute.success(data={"message": "Perfil cognitivo eliminado correctamente"}, message="Perfil cognitivo eliminado correctamente")
        return APIRoute.error(
            ErrorCodes.RESOURCE_NOT_FOUND,
            "Perfil cognitivo no encontrado",
            status_code=404
        )
    except Exception as e:
        log_error(f"Error al eliminar perfil cognitivo: {str(e)}", e, "profiles.routes")
        return APIRoute.error(
            ErrorCodes.SERVER_ERROR,
            str(e),
            status_code=500
        ) 