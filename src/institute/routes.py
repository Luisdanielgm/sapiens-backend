from flask import request, jsonify
from bson import ObjectId

from src.shared.standardization import APIBlueprint, APIRoute, ErrorCodes
from src.shared.constants import ROLES
from .services import InstituteService, ProgramService, LevelService

institute_bp = APIBlueprint('institute', __name__)
institute_service = InstituteService()
program_service = ProgramService()
level_service = LevelService()

@institute_bp.route('/create', methods=['POST'])
@APIRoute.standard(auth_required_flag=True, roles=[ROLES["ADMIN"]])
def create_institute():
    """
    Crea un nuevo instituto con los parámetros especificados.
    """
    try:
        # Validar que vienen los campos requeridos
        required_fields = ['name', 'address', 'email']
        for field in required_fields:
            if field not in request.json:
                return APIRoute.error(ErrorCodes.MISSING_FIELD, f"Campo requerido: {field}")
                
        success, result = institute_service.create_institute(request.json)
        
        if success:
            return APIRoute.success({"id": result}, message="Instituto creado exitosamente", status_code=201)
        else:
            return APIRoute.error(ErrorCodes.CREATION_ERROR, result)
    except Exception as e:
        return APIRoute.error(ErrorCodes.SERVER_ERROR, str(e), status_code=500)

@institute_bp.route('/<institute_id>', methods=['GET'])
@APIRoute.standard(auth_required_flag=True, roles=[ROLES["ADMIN"]])
def get_institute(institute_id):
    """
    Obtiene los detalles de un instituto específico por su ID.
    """
    try:
        institute = institute_service.get_institute(institute_id)
        if institute:
            return APIRoute.success(institute)
        else:
            return APIRoute.error(ErrorCodes.NOT_FOUND, "Instituto no encontrado", status_code=404)
    except Exception as e:
        return APIRoute.error(ErrorCodes.SERVER_ERROR, str(e), status_code=500)

@institute_bp.route('/<institute_id>/update', methods=['PUT'])
@APIRoute.standard(auth_required_flag=True, roles=[ROLES["ADMIN"], ROLES["INSTITUTE_ADMIN"]])
def update_institute(institute_id):
    """
    Actualiza un instituto existente con los parámetros proporcionados.
    """
    try:
        # Validar que viene al menos un campo para actualizar
        if not request.json:
            return APIRoute.error("No se proporcionaron datos para actualizar", 400)
            
        # Campos permitidos para actualización
        allowed_fields = ['name', 'address', 'phone', 'email', 'website', 'status']
        updates = {}
        
        for field in allowed_fields:
            if field in request.json:
                updates[field] = request.json[field]
                
        if not updates:
            return APIRoute.error("No se proporcionaron campos válidos para actualizar", 400)
            
        success, result = institute_service.update_institute(institute_id, updates)
        
        if success:
            return APIRoute.success({"message": result})
        else:
            return APIRoute.error(result, 400)
    except Exception as e:
        return APIRoute.error(str(e), 500)

@institute_bp.route('/<institute_id>/delete', methods=['DELETE'])
@APIRoute.standard(auth_required_flag=True, roles=[ROLES["ADMIN"]])
def delete_institute(institute_id):
    """
    Elimina un instituto específico por su ID.
    """
    try:
        admin_email = request.user.get("email", "")
        if not admin_email:
            return APIRoute.error("No se pudo identificar el correo del administrador", 400)
            
        success, result = institute_service.delete_institute(institute_id, admin_email)
        
        if success:
            return APIRoute.success({"message": result})
        else:
            return APIRoute.error(result, 400)
    except Exception as e:
        return APIRoute.error(str(e), 500)

@institute_bp.route('/<institute_id>/activate', methods=['PUT'])
@APIRoute.standard(auth_required_flag=True, roles=[ROLES["ADMIN"]])
def activate_institute(institute_id):
    """
    Activa un instituto específico cambiando su estado a 'active'.
    """
    try:
        success, result = institute_service.activate_institute(institute_id)
        
        if success:
            return APIRoute.success({"message": result})
        else:
            return APIRoute.error(result, 400)
    except Exception as e:
        return APIRoute.error(ErrorCodes.SERVER_ERROR, str(e), status_code=500)

@institute_bp.route('/<institute_id>/statistics', methods=['GET'])
@APIRoute.standard(auth_required_flag=True, roles=[ROLES["ADMIN"], ROLES["INSTITUTE_ADMIN"]])
def get_institute_statistics(institute_id):
    """
    Obtiene estadísticas de un instituto específico.
    """
    try:
        statistics = institute_service.get_institute_statistics(institute_id)
        if statistics:
            return APIRoute.success(statistics)
        else:
            return APIRoute.error("No se pudieron obtener las estadísticas del instituto", 404)
    except Exception as e:
        return APIRoute.error(str(e), 500)

@institute_bp.route('/admin/current', methods=['GET'])
@APIRoute.standard(auth_required_flag=True, roles=[ROLES["ADMIN"], ROLES["INSTITUTE_ADMIN"]])
def get_institute_by_admin():
    """
    Obtiene el instituto asociado al administrador actual.
    """
    try:
        # Obtener el ID del usuario autenticado
        user_id = request.user_id
        if not user_id:
            return APIRoute.error(ErrorCodes.MISSING_FIELD, "No se pudo identificar el ID del administrador", status_code=400)
            
        # Consultar el usuario en la base de datos para obtener su email
        from src.shared.database import get_db
        db = get_db()
        user = db.users.find_one({"_id": ObjectId(user_id)})
        
        if not user or "email" not in user:
            return APIRoute.error(ErrorCodes.NOT_FOUND, "No se pudo obtener la información del administrador", status_code=400)
            
        admin_email = user.get("email", "")
        if not admin_email:
            return APIRoute.error(ErrorCodes.MISSING_FIELD, "No se pudo identificar el correo del administrador", status_code=400)
            
        institute = institute_service.get_institute_by_admin(admin_email)
        if institute:
            return APIRoute.success(institute)
        else:
            return APIRoute.error(ErrorCodes.NOT_FOUND, "No se encontró un instituto asociado a este administrador", status_code=404)
    except Exception as e:
        return APIRoute.error(ErrorCodes.SERVER_ERROR, str(e), status_code=500)

@institute_bp.route('/all', methods=['GET'])
@APIRoute.standard(auth_required_flag=True, roles=[ROLES["ADMIN"]])
def get_all_institutes():
    """
    Obtiene todos los institutos registrados en el sistema.
    Accesible solo para administradores globales.
    """
    try:
        institutes = institute_service.get_all_institutes()
        return APIRoute.success(institutes)
    except Exception as e:
        return APIRoute.error(ErrorCodes.SERVER_ERROR, str(e), status_code=500)

@institute_bp.route('/<institute_id>/programs', methods=['GET'])
@APIRoute.standard(auth_required_flag=True)
def get_institute_programs(institute_id):
    """
    Obtiene todos los programas educativos de un instituto específico.
    """
    try:
        programs = program_service.get_institute_programs(institute_id)
        return APIRoute.success(programs)
    except Exception as e:
        return APIRoute.error(str(e), 500)

@institute_bp.route('/program/create', methods=['POST'])
@APIRoute.standard(auth_required_flag=True, roles=[ROLES["ADMIN"], ROLES["INSTITUTE_ADMIN"]])
def create_program():
    """
    Crea un nuevo programa educativo con los parámetros especificados.
    """
    try:
        # Validar que vienen los campos requeridos
        required_fields = ['name', 'institute_id', 'type', 'modality']
        for field in required_fields:
            if field not in request.json:
                return APIRoute.error(f"Campo requerido: {field}", 400)
                
        success, result = program_service.create_program(request.json)
        
        if success:
            return APIRoute.success({"id": result}, 201)
        else:
            return APIRoute.error(result, 400)
    except Exception as e:
        return APIRoute.error(str(e), 500)

@institute_bp.route('/program/<program_id>', methods=['GET'])
@APIRoute.standard(auth_required_flag=True)
def get_program(program_id):
    """
    Obtiene los detalles de un programa educativo específico por su ID.
    """
    try:
        program = program_service.get_program_by_id(program_id)
        if program:
            return APIRoute.success(program)
        else:
            return APIRoute.error("Programa no encontrado", 404)
    except Exception as e:
        return APIRoute.error(str(e), 500)

@institute_bp.route('/program/<program_id>/update', methods=['PUT'])
@APIRoute.standard(auth_required_flag=True, roles=[ROLES["ADMIN"], ROLES["INSTITUTE_ADMIN"]])
def update_program(program_id):
    """
    Actualiza un programa educativo existente con los parámetros proporcionados.
    """
    try:
        # Validar que viene al menos un campo para actualizar
        if not request.json:
            return APIRoute.error("No se proporcionaron datos para actualizar", 400)
            
        # Campos permitidos para actualización
        allowed_fields = ['name', 'type', 'modality', 'description', 'duration', 'institute_id']
        updates = {}
        
        for field in allowed_fields:
            if field in request.json:
                updates[field] = request.json[field]
                
        if not updates:
            return APIRoute.error("No se proporcionaron campos válidos para actualizar", 400)
            
        success, result = program_service.update_program(program_id, updates)
        
        if success:
            return APIRoute.success({"message": result})
        else:
            return APIRoute.error(result, 400)
    except Exception as e:
        return APIRoute.error(str(e), 500)

@institute_bp.route('/program/<program_id>/delete', methods=['DELETE'])
@APIRoute.standard(auth_required_flag=True, roles=[ROLES["ADMIN"], ROLES["INSTITUTE_ADMIN"]])
def delete_program(program_id):
    """
    Elimina un programa educativo específico por su ID.
    """
    try:
        success, result = program_service.delete_program(program_id)
        
        if success:
            return APIRoute.success({"message": result})
        else:
            return APIRoute.error(result, 400)
    except Exception as e:
        return APIRoute.error(str(e), 500)

@institute_bp.route('/level/create', methods=['POST'])
@APIRoute.standard(auth_required_flag=True, roles=[ROLES["ADMIN"], ROLES["INSTITUTE_ADMIN"]])
def create_level():
    """
    Crea un nuevo nivel con los parámetros especificados.
    """
    try:
        # Validar que vienen los campos requeridos
        required_fields = ['program_id', 'name', 'description', 'order']
        for field in required_fields:
            if field not in request.json:
                return APIRoute.error(f"Campo requerido: {field}", 400)
                
        success, result = level_service.create_level(request.json)
        
        if success:
            return APIRoute.success({"id": result}, 201)
        else:
            return APIRoute.error(result, 400)
    except Exception as e:
        return APIRoute.error(str(e), 500)

@institute_bp.route('/program/<program_id>/levels', methods=['GET'])
@APIRoute.standard(auth_required_flag=True)
def get_program_levels(program_id):
    """
    Obtiene todos los niveles de un programa educativo específico.
    """
    try:
        levels = level_service.get_program_levels(program_id)
        return APIRoute.success(levels)
    except Exception as e:
        return APIRoute.error(str(e), 500)

@institute_bp.route('/level/<level_id>', methods=['GET'])
@APIRoute.standard(auth_required_flag=True)
def get_level(level_id):
    """
    Obtiene los detalles de un nivel específico por su ID.
    """
    try:
        level = level_service.get_level_by_id(level_id)
        if level:
            return APIRoute.success(level)
        else:
            return APIRoute.error("Nivel no encontrado", 404)
    except Exception as e:
        return APIRoute.error(str(e), 500)

@institute_bp.route('/level/<level_id>/update', methods=['PUT'])
@APIRoute.standard(auth_required_flag=True, roles=[ROLES["ADMIN"], ROLES["INSTITUTE_ADMIN"]])
def update_level(level_id):
    """
    Actualiza un nivel existente con los parámetros proporcionados.
    """
    try:
        # Validar que viene al menos un campo para actualizar
        if not request.json:
            return APIRoute.error("No se proporcionaron datos para actualizar", 400)
            
        # Campos permitidos para actualización
        allowed_fields = ['name', 'description', 'order', 'program_id']
        updates = {}
        
        for field in allowed_fields:
            if field in request.json:
                updates[field] = request.json[field]
                
        if not updates:
            return APIRoute.error("No se proporcionaron campos válidos para actualizar", 400)
            
        success, result = level_service.update_level(level_id, updates)
        
        if success:
            return APIRoute.success({"message": result})
        else:
            return APIRoute.error(result, 400)
    except Exception as e:
        return APIRoute.error(str(e), 500)

@institute_bp.route('/level/<level_id>/delete', methods=['DELETE'])
@APIRoute.standard(auth_required_flag=True, roles=[ROLES["ADMIN"], ROLES["INSTITUTE_ADMIN"]])
def delete_level(level_id):
    """
    Elimina un nivel específico por su ID.
    """
    try:
        success, result = level_service.delete_level(level_id)
        
        if success:
            return APIRoute.success({"message": result})
        else:
            return APIRoute.error(result, 400)
    except Exception as e:
        return APIRoute.error(str(e), 500)