from flask import request, jsonify
from bson import ObjectId

from src.shared.standardization import APIBlueprint, APIRoute, ErrorCodes
from src.shared.constants import ROLES
from .services import PeriodService, SectionService, SubjectService

academic_bp = APIBlueprint('academic', __name__)

period_service = PeriodService()
section_service = SectionService()
subject_service = SubjectService()


# Rutas para Períodos Académicos
@academic_bp.route('/period/create', methods=['POST'])
@APIRoute.standard(auth_required_flag=True, roles=[ROLES["ADMIN"], ROLES["INSTITUTE_ADMIN"]])
def create_period():
    """
    Crea un nuevo período académico con los parámetros especificados.
    """
    try:
        # Validar que vienen los campos requeridos
        required_fields = ['level_id', 'name', 'type', 'start_date', 'end_date', 'order']
        for field in required_fields:
            if field not in request.json:
                return APIRoute.error(ErrorCodes.MISSING_FIELD, f"Campo requerido: {field}")
                
        success, result = period_service.create_period(request.json)
        
        if success:
            return APIRoute.success(data={"id": result}, message="Período académico creado exitosamente", status_code=201)
        else:
            return APIRoute.error(ErrorCodes.CREATION_ERROR, result)
    except Exception as e:
        return APIRoute.error(ErrorCodes.SERVER_ERROR, str(e), status_code=500)

@academic_bp.route('/level/<level_id>/periods', methods=['GET'])
@APIRoute.standard(auth_required_flag=True)
def get_level_periods(level_id):
    """
    Obtiene todos los períodos académicos para un nivel específico.
    """
    try:
        periods = period_service.get_level_periods(level_id)
        return APIRoute.success(data=periods)
    except Exception as e:
        return APIRoute.error(ErrorCodes.SERVER_ERROR, str(e), status_code=500)

@academic_bp.route('/period/<period_id>', methods=['GET'])
@APIRoute.standard(auth_required_flag=True)
def get_period(period_id):
    """
    Obtiene los detalles de un período académico específico por su ID.
    """
    try:
        period = period_service.get_period_by_id(period_id)
        if period:
            return APIRoute.success(data=period)
        else:
            return APIRoute.error(ErrorCodes.NOT_FOUND, "Período académico no encontrado", status_code=404)
    except Exception as e:
        return APIRoute.error(ErrorCodes.SERVER_ERROR, str(e), status_code=500)

@academic_bp.route('/period/<period_id>/update', methods=['PUT'])
@APIRoute.standard(auth_required_flag=True, roles=[ROLES["ADMIN"], ROLES["INSTITUTE_ADMIN"]])
def update_period(period_id):
    """
    Actualiza un período académico existente con los parámetros proporcionados.
    """
    try:
        # Validar que viene al menos un campo para actualizar
        if not request.json:
            return APIRoute.error("No se proporcionaron datos para actualizar", 400)
            
        # Campos permitidos para actualización
        allowed_fields = ['name', 'type', 'start_date', 'end_date', 'order', 'level_id']
        updates = {}
        
        for field in allowed_fields:
            if field in request.json:
                updates[field] = request.json[field]
                
        if not updates:
            return APIRoute.error("No se proporcionaron campos válidos para actualizar", 400)
            
        success, result = period_service.update_period(period_id, updates)

        if success:
            return APIRoute.success(data={"message": result}, message=result)
        else:
            return APIRoute.error(ErrorCodes.UPDATE_ERROR, result)
    except Exception as e:
        return APIRoute.error(ErrorCodes.SERVER_ERROR, str(e), status_code=500)

@academic_bp.route('/period/<period_id>/delete', methods=['DELETE'])
@APIRoute.standard(auth_required_flag=True, roles=[ROLES["ADMIN"], ROLES["INSTITUTE_ADMIN"]])
def delete_period(period_id):
    """
    Elimina un período académico específico por su ID.
    """
    try:
        payload = request.get_json(silent=True) or {}
        cascade_delete = bool(payload.get("cascadeDelete") or payload.get("cascade"))

        success, result = period_service.delete_period(period_id, cascade=cascade_delete)

        if success:
            return APIRoute.success(data={"message": result}, message=result)
        else:
            return APIRoute.error(ErrorCodes.DELETION_ERROR, result)
    except Exception as e:
        return APIRoute.error(ErrorCodes.SERVER_ERROR, str(e), status_code=500)

# Rutas para Secciones
@academic_bp.route('/section/create', methods=['POST'])
@APIRoute.standard(auth_required_flag=True, roles=[ROLES["ADMIN"], ROLES["INSTITUTE_ADMIN"]])
def create_section():
    """
    Crea una nueva sección con los parámetros especificados.
    """
    try:
        # Validar que vienen los campos requeridos
        required_fields = ['level_id', 'code', 'capacity']
        for field in required_fields:
            if field not in request.json:
                return APIRoute.error(ErrorCodes.MISSING_FIELD, f"Campo requerido: {field}")
                
        success, result = section_service.create_section(request.json)
        
        if success:
            return APIRoute.success(data={"id": result}, message="Sección creada exitosamente", status_code=201)
        else:
            return APIRoute.error(ErrorCodes.CREATION_ERROR, result)
    except Exception as e:
        return APIRoute.error(ErrorCodes.SERVER_ERROR, str(e), status_code=500)

@academic_bp.route('/level/<level_id>/sections', methods=['GET'])
@APIRoute.standard(auth_required_flag=True)
def get_level_sections(level_id):
    """
    Obtiene todas las secciones para un nivel específico.
    """
    try:
        sections = section_service.get_level_sections(level_id)
        return APIRoute.success(data=sections)
    except Exception as e:
        return APIRoute.error(ErrorCodes.SERVER_ERROR, str(e), status_code=500)

@academic_bp.route('/section/<section_id>', methods=['GET'])
@APIRoute.standard(auth_required_flag=True)
def get_section(section_id):
    """
    Obtiene los detalles de una sección específica por su ID.
    """
    try:
        section = section_service.get_section_by_id(section_id)
        if section:
            return APIRoute.success(data=section)
        else:
            return APIRoute.error(ErrorCodes.NOT_FOUND, "Sección no encontrada", status_code=404)
    except Exception as e:
        return APIRoute.error(ErrorCodes.SERVER_ERROR, str(e), status_code=500)

@academic_bp.route('/section/<section_id>/update', methods=['PUT'])
@APIRoute.standard(auth_required_flag=True, roles=[ROLES["ADMIN"], ROLES["INSTITUTE_ADMIN"]])
def update_section(section_id):
    """
    Actualiza una sección existente con los parámetros proporcionados.
    """
    try:
        # Validar que viene al menos un campo para actualizar
        if not request.json:
            return APIRoute.error("No se proporcionaron datos para actualizar", 400)
            
        # Campos permitidos para actualización
        allowed_fields = ['code', 'capacity', 'schedule', 'level_id']
        updates = {}
        
        for field in allowed_fields:
            if field in request.json:
                updates[field] = request.json[field]
                
        if not updates:
            return APIRoute.error("No se proporcionaron campos válidos para actualizar", 400)
            
        success, result = section_service.update_section(section_id, updates)

        if success:
            return APIRoute.success(data={"message": result}, message=result)
        else:
            return APIRoute.error(ErrorCodes.UPDATE_ERROR, result)
    except Exception as e:
        return APIRoute.error(ErrorCodes.SERVER_ERROR, str(e), status_code=500)

@academic_bp.route('/section/<section_id>/delete', methods=['DELETE'])
@APIRoute.standard(auth_required_flag=True, roles=[ROLES["ADMIN"], ROLES["INSTITUTE_ADMIN"]])
def delete_section(section_id):
    """
    Elimina una sección específica por su ID.
    """
    try:
        payload = request.get_json(silent=True) or {}
        cascade_delete = bool(payload.get("cascadeDelete") or payload.get("cascade"))

        success, result = section_service.delete_section(section_id, cascade=cascade_delete)

        if success:
            return APIRoute.success(data={"message": result}, message=result)
        else:
            return APIRoute.error(ErrorCodes.DELETION_ERROR, result)
    except Exception as e:
        return APIRoute.error(ErrorCodes.SERVER_ERROR, str(e), status_code=500)

# Rutas para Materias
@academic_bp.route('/subject/create', methods=['POST'])
@APIRoute.standard(auth_required_flag=True, roles=[ROLES["ADMIN"], ROLES["INSTITUTE_ADMIN"]])
def create_subject():
    """
    Crea una nueva materia con los parámetros especificados.
    """
    try:
        # Validar que vienen los campos requeridos
        required_fields = ['level_id', 'name', 'code', 'credits', 'competencies']
        for field in required_fields:
            if field not in request.json:
                return APIRoute.error(ErrorCodes.MISSING_FIELD, f"Campo requerido: {field}")
                
        success, result = subject_service.create_subject(request.json)
        
        if success:
            return APIRoute.success(data={"id": result}, message="Materia creada exitosamente", status_code=201)
        else:
            return APIRoute.error(ErrorCodes.CREATION_ERROR, result)
    except Exception as e:
        return APIRoute.error(ErrorCodes.SERVER_ERROR, str(e), status_code=500)

@academic_bp.route('/level/<level_id>/subjects', methods=['GET'])
@APIRoute.standard(auth_required_flag=True)
def get_level_subjects(level_id):
    """
    Obtiene todas las materias para un nivel específico.
    """
    try:
        subjects = subject_service.get_level_subjects(level_id)
        return APIRoute.success(data=subjects)
    except Exception as e:
        return APIRoute.error(ErrorCodes.SERVER_ERROR, str(e), status_code=500)

@academic_bp.route('/subject/<subject_id>', methods=['GET'])
@APIRoute.standard(auth_required_flag=True)
def get_subject_details(subject_id):
    """
    Obtiene los detalles de una materia específica por su ID.
    """
    try:
        subject = subject_service.get_subject_details(subject_id)
        if subject:
            return APIRoute.success(data=subject)
        else:
            return APIRoute.error(ErrorCodes.NOT_FOUND, "Materia no encontrada", status_code=404)
    except Exception as e:
        return APIRoute.error(ErrorCodes.SERVER_ERROR, str(e), status_code=500)

@academic_bp.route('/subject/<subject_id>/update', methods=['PUT'])
@APIRoute.standard(auth_required_flag=True, roles=[ROLES["ADMIN"], ROLES["INSTITUTE_ADMIN"]])
def update_subject(subject_id):
    """
    Actualiza una materia existente con los parámetros proporcionados.
    """
    try:
        # Validar que viene al menos un campo para actualizar
        if not request.json:
            return APIRoute.error("No se proporcionaron datos para actualizar", 400)
            
        # Campos permitidos para actualización
        allowed_fields = ['name', 'code', 'credits', 'competencies', 'required', 'level_id']
        updates = {}
        
        for field in allowed_fields:
            if field in request.json:
                updates[field] = request.json[field]
                
        if not updates:
            return APIRoute.error("No se proporcionaron campos válidos para actualizar", 400)
            
        success, result = subject_service.update_subject(subject_id, updates)

        if success:
            return APIRoute.success(data={"message": result}, message=result)
        else:
            return APIRoute.error(ErrorCodes.UPDATE_ERROR, result)
    except Exception as e:
        return APIRoute.error(ErrorCodes.SERVER_ERROR, str(e), status_code=500)

@academic_bp.route('/subject/<subject_id>/delete', methods=['DELETE'])
@APIRoute.standard(auth_required_flag=True, roles=[ROLES["ADMIN"], ROLES["INSTITUTE_ADMIN"]])
def delete_subject(subject_id):
    """
    Elimina una materia específica por su ID.
    """
    try:
        payload = request.get_json(silent=True) or {}
        cascade_delete = bool(payload.get("cascadeDelete") or payload.get("cascade"))

        success, result = subject_service.delete_subject(subject_id, cascade=cascade_delete)

        if success:
            return APIRoute.success(data={"message": result}, message=result)
        else:
            return APIRoute.error(ErrorCodes.DELETION_ERROR, result)
    except Exception as e:
        return APIRoute.error(ErrorCodes.SERVER_ERROR, str(e), status_code=500)

