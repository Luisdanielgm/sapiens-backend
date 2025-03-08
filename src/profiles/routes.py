from flask import request
from typing import Dict

from src.shared.standardization import APIBlueprint, APIRoute, ErrorCodes
from src.shared.constants import ROLES
from src.profiles.services import ProfileService

profiles_bp = APIBlueprint('profiles', __name__)
profile_service = ProfileService()


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
            ErrorCodes.NOT_FOUND,
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
@APIRoute.standard(
    auth_required_flag=True,
    required_fields=['user_id_or_email', 'profile_data']
)
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
    
    # El servicio ahora lanza excepciones que son manejadas por APIRoute.standard
    profile_service.update_teacher_profile(user_id_or_email, profile_data)
    
    return APIRoute.success(message="Perfil de profesor actualizado correctamente")


@profiles_bp.route('/student/<user_id_or_email>', methods=['GET'])
@APIRoute.standard(auth_required_flag=True)
def get_student_profile(user_id_or_email):
    """
    Obtiene el perfil de estudiante para un usuario específico.
    
    Args:
        user_id_or_email: ID o email del usuario estudiante
    """
    try:
        profile = profile_service.get_student_profile(user_id_or_email)
        
        if profile:
            return APIRoute.success(data={"profile": profile})
        return APIRoute.error(
            ErrorCodes.NOT_FOUND,
            "Perfil de estudiante no encontrado",
            status_code=404
        )
    except Exception as e:
        return APIRoute.error(
            ErrorCodes.SERVER_ERROR,
            str(e),
            status_code=500
        )


@profiles_bp.route('/student', methods=['PUT'])
@APIRoute.standard(
    auth_required_flag=True,
    required_fields=['user_id_or_email', 'profile_data']
)
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
    
    # El servicio ahora lanza excepciones que son manejadas por APIRoute.standard
    profile_service.update_student_profile(user_id_or_email, profile_data)
    
    return APIRoute.success(message="Perfil de estudiante actualizado correctamente")


@profiles_bp.route('/admin/<user_id_or_email>', methods=['GET'])
@APIRoute.standard(
    auth_required_flag=True,
    roles=[ROLES["ADMIN"], ROLES["INSTITUTE_ADMIN"]]
)
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
            ErrorCodes.NOT_FOUND,
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
@APIRoute.standard(
    auth_required_flag=True,
    roles=[ROLES["ADMIN"], ROLES["INSTITUTE_ADMIN"]],
    required_fields=['user_id_or_email', 'profile_data']
)
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
    
    # El servicio ahora lanza excepciones que son manejadas por APIRoute.standard
    profile_service.update_admin_profile(user_id_or_email, profile_data)
    
    return APIRoute.success(message="Perfil de administrador actualizado correctamente") 