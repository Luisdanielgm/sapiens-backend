from flask import request, jsonify
from bson import ObjectId
from flask_jwt_extended import get_jwt_identity

from src.shared.standardization import APIBlueprint, APIRoute, ErrorCodes
from src.shared.constants import ROLES
from .services import ClassService, MembershipService, SubperiodService
from src.shared.database import get_db

classes_bp = APIBlueprint('classes', __name__)
class_service = ClassService()
membership_service = MembershipService()
# content_service ha sido eliminado ya que ahora se usa StudentIndividualContentService
subperiod_service = SubperiodService()

# Rutas para manejo de clases
@classes_bp.route('/create', methods=['POST'])
@APIRoute.standard(auth_required_flag=True, roles=[ROLES["TEACHER"], ROLES["INSTITUTE_ADMIN"]])
def create_class():
    """
    Crea una nueva clase con los parámetros especificados.
    El usuario creador se agrega automáticamente como miembro con rol de profesor.
    """
    try:
        # Validar que vienen los campos requeridos
        required_fields = ['subject_id', 'section_id', 'academic_period_id', 'level_id', 'name', 'access_code']
        for field in required_fields:
            if field not in request.json:
                return APIRoute.error(ErrorCodes.MISSING_FIELD, f"Campo requerido: {field}")
        
        # Obtener el usuario actual
        user_id = get_jwt_identity()
        
        # Obtener información del instituto del usuario
        db = get_db()
        user = db.users.find_one({"_id": ObjectId(user_id)})
        if not user:
            return APIRoute.error(ErrorCodes.USER_NOT_FOUND, "Usuario no encontrado", status_code=404)
        
        # Crear la clase
        class_data = {
            'institute_id': request.json.get('institute_id') or ObjectId(user.get('institute_id')),
            'subject_id': ObjectId(request.json['subject_id']),
            'section_id': ObjectId(request.json['section_id']),
            'academic_period_id': ObjectId(request.json['academic_period_id']),
            'level_id': ObjectId(request.json['level_id']),
            'name': request.json['name'],
            'access_code': request.json['access_code'],
            'created_by': user_id,
            'created_at': ObjectId(request.json.get('created_at', '')).generation_time if request.json.get('created_at') else None
        }
        
        # Si hay un schedule, agregarlo
        if 'schedule' in request.json:
            class_data['schedule'] = request.json['schedule']
        
        success, result = class_service.create_class(class_data)
        
        if success:
            # Agregar al creador como miembro con rol de profesor
            membership_service.add_member(result, user_id, 'TEACHER')
            return APIRoute.success({"id": result}, message="Clase creada exitosamente", status_code=201)
        else:
            return APIRoute.error(ErrorCodes.CREATION_ERROR, result)
    except Exception as e:
        return APIRoute.error(ErrorCodes.SERVER_ERROR, str(e), status_code=500)

@classes_bp.route('/<class_id>', methods=['GET'])
@APIRoute.standard(auth_required_flag=True, roles=[ROLES["TEACHER"], ROLES["STUDENT"], ROLES["INSTITUTE_ADMIN"]])
def get_class_details(class_id):
    """
    Obtiene los detalles de una clase específica.
    """
    try:
        class_details = class_service.get_class_details(class_id)
        if class_details:
            return APIRoute.success(class_details)
        else:
            return APIRoute.error("Clase no encontrada", 404)
    except Exception as e:
        return APIRoute.error(str(e), 500)

@classes_bp.route('/<class_id>/update', methods=['PUT'])
@APIRoute.standard(auth_required_flag=True, roles=[ROLES["TEACHER"], ROLES["INSTITUTE_ADMIN"]])
def update_class(class_id):
    """
    Actualiza una clase existente.
    """
    try:
        # Validar que viene al menos un campo para actualizar
        if not request.json:
            return APIRoute.error("No se proporcionaron datos para actualizar", 400)
        
        # Campos permitidos para actualización
        allowed_fields = ['name', 'access_code', 'status', 'settings']
        updates = {}
        
        for field in allowed_fields:
            if field in request.json:
                updates[field] = request.json[field]
        
        if not updates:
            return APIRoute.error("No se proporcionaron campos válidos para actualizar", 400)
        
        success, result = class_service.update_class(class_id, updates)
        
        if success:
            return APIRoute.success({"message": result})
        else:
            return APIRoute.error(result, 400)
    except Exception as e:
        return APIRoute.error(str(e), 500)

@classes_bp.route('/<class_id>', methods=['DELETE'])
@APIRoute.standard(auth_required_flag=True, roles=[ROLES["TEACHER"], ROLES["INSTITUTE_ADMIN"]])
def delete_class(class_id):
    """
    Elimina una clase específica si no tiene dependencias.
    
    Args:
        class_id: ID de la clase a eliminar
    """
    try:
        success, message = class_service.delete_class(class_id)
        
        if success:
            return APIRoute.success(message=message)
        return APIRoute.error(
            ErrorCodes.DELETE_ERROR,
            message,
            status_code=400
        )
    except Exception as e:
        return APIRoute.error(
            ErrorCodes.SERVER_ERROR,
            str(e),
            status_code=500
        )

@classes_bp.route('/<class_id>/check-dependencies', methods=['GET'])
@APIRoute.standard(auth_required_flag=True, roles=[ROLES["TEACHER"], ROLES["INSTITUTE_ADMIN"]])
def check_class_dependencies(class_id):
    """
    Verifica si una clase tiene dependencias que impiden su eliminación.
    
    Args:
        class_id: ID de la clase a verificar
    """
    try:
        # Verificar que la clase existe
        class_data = class_service.collection.find_one({"_id": ObjectId(class_id)})
        if not class_data:
            return APIRoute.error(
                ErrorCodes.NOT_FOUND,
                "Clase no encontrada",
                status_code=404
            )

        # Verificar miembros
        members_count = class_service.db.class_members.count_documents({
            "class_id": ObjectId(class_id)
        })
        
        # Verificar subperiodos
        subperiods_count = class_service.db.subperiods.count_documents({
            "class_id": ObjectId(class_id)
        })
        
        return APIRoute.success({
            "has_dependencies": members_count > 0 or subperiods_count > 0,
            "dependencies": {
                "members": members_count,
                "subperiods": subperiods_count
            }
        })
        
    except Exception as e:
        return APIRoute.error(
            ErrorCodes.SERVER_ERROR,
            str(e),
            status_code=500
        )

# Rutas para manejo de miembros de la clase
@classes_bp.route('/<class_id>/members/add', methods=['POST'])
@APIRoute.standard(auth_required_flag=True, roles=[ROLES["TEACHER"], ROLES["INSTITUTE_ADMIN"]])
def add_class_member(class_id):
    """
    Agrega un miembro a una clase.
    """
    try:
        # Validar que vienen los campos requeridos
        if 'user_id' not in request.json or 'role' not in request.json:
            return APIRoute.error("Se requieren los campos user_id y role", 400)
        
        user_id = request.json['user_id']
        role = request.json['role']
        
        # Validar que el rol es válido
        if role not in ["TEACHER", "STUDENT"]:
            return APIRoute.error("Rol no válido. Debe ser 'TEACHER' o 'STUDENT'", 400)
        
        success, result = membership_service.add_member(class_id, user_id, role)
        
        if success:
            return APIRoute.success({"id": result}, 201)
        else:
            return APIRoute.error(result, 400)
    except Exception as e:
        return APIRoute.error(str(e), 500)

@classes_bp.route('/<class_id>/members', methods=['GET'])
@APIRoute.standard(auth_required_flag=True, roles=[ROLES["TEACHER"], ROLES["STUDENT"], ROLES["INSTITUTE_ADMIN"]])
def get_class_members(class_id):
    """
    Obtiene todos los miembros de una clase.
    
    Query Parameters:
        role: (opcional) Filtrar miembros por rol ('TEACHER' o 'STUDENT')
    """
    try:
        # Obtener el parámetro role de la consulta si existe
        role = request.args.get('role')
        
        # Validar el rol si se proporciona
        if role and role not in ["TEACHER", "STUDENT"]:
            return APIRoute.error(
                ErrorCodes.INVALID_DATA,
                "Rol no válido. Debe ser 'TEACHER' o 'STUDENT'",
                status_code=400
            )
        
        # Modificar el servicio para filtrar por rol
        members = membership_service.get_class_members(class_id, role)
        return APIRoute.success(members)
    except Exception as e:
        return APIRoute.error(str(e), 500)

@classes_bp.route('/teacher/<teacher_id_or_email>', methods=['GET'])
@APIRoute.standard(auth_required_flag=True)
def get_teacher_classes(teacher_id_or_email):
    """
    Obtiene todas las clases de un profesor.
    """
    try:
        classes = membership_service.get_classes_by_teacher(teacher_id_or_email)
        return APIRoute.success(classes)
    except Exception as e:
        return APIRoute.error(str(e), 500)

@classes_bp.route('/student/<student_id_or_email>', methods=['GET'])
@APIRoute.standard(auth_required_flag=True)
def get_student_classes(student_id_or_email):
    """
    Obtiene todas las clases de un estudiante.
    """
    try:
        classes = membership_service.get_classes_by_student(student_id_or_email)
        return APIRoute.success(classes)
    except Exception as e:
        return APIRoute.error(str(e), 500)

@classes_bp.route('/<class_id>/students', methods=['GET'])
@APIRoute.standard(auth_required_flag=True, roles=[ROLES["TEACHER"], ROLES["INSTITUTE_ADMIN"]])
def get_class_students(class_id):
    """
    Obtiene todos los estudiantes de una clase.
    """
    try:
        students = membership_service.get_class_students(class_id)
        return APIRoute.success(students)
    except Exception as e:
        return APIRoute.error(str(e), 500)

@classes_bp.route('/<class_id>/members/<member_id>', methods=['DELETE'])
@APIRoute.standard(auth_required_flag=True, roles=[ROLES["TEACHER"], ROLES["INSTITUTE_ADMIN"]])
def remove_class_member(class_id, member_id):
    """
    Elimina un miembro de una clase.
    
    Args:
        class_id: ID de la clase
        member_id: ID del miembro a eliminar
    """
    try:
        success, message = membership_service.remove_member(class_id, member_id)
        
        if success:
            return APIRoute.success(message=message)
        return APIRoute.error(
            ErrorCodes.DELETE_ERROR,
            message,
            status_code=400
        )
    except Exception as e:
        return APIRoute.error(
            ErrorCodes.SERVER_ERROR,
            str(e),
            status_code=500
        )

@classes_bp.route('/<class_id>/members/add-by-email', methods=['POST'])
@APIRoute.standard(auth_required_flag=True, roles=[ROLES["TEACHER"], ROLES["INSTITUTE_ADMIN"]])
def add_class_member_by_email(class_id):
    """
    Agrega un miembro a una clase mediante su email.
    
    Args:
        class_id: ID de la clase
    """
    try:
        # Validar que vienen los campos requeridos
        if 'email' not in request.json or 'role' not in request.json:
            return APIRoute.error(
                ErrorCodes.MISSING_FIELD,
                "Se requieren los campos email y role",
                status_code=400
            )
        
        email = request.json['email']
        role = request.json['role']
        
        # Validar formato de email básico
        if '@' not in email:
            return APIRoute.error(
                ErrorCodes.INVALID_FORMAT,
                "Formato de email inválido",
                status_code=400
            )
        
        # Validar que el rol es válido
        if role not in ["TEACHER", "STUDENT"]:
            return APIRoute.error(
                ErrorCodes.INVALID_DATA,
                "Rol no válido. Debe ser 'TEACHER' o 'STUDENT'",
                status_code=400
            )
        
        success, result = membership_service.add_member_by_email(class_id, email, role)
        
        if success:
            if isinstance(result, dict) and "message" in result:
                return APIRoute.success(result, message=result["message"], status_code=200)
            return APIRoute.success(result, status_code=201)
        else:
            return APIRoute.error(
                ErrorCodes.OPERATION_FAILED,
                result,
                status_code=400
            )
    except Exception as e:
        return APIRoute.error(
            ErrorCodes.SERVER_ERROR,
            str(e),
            status_code=500
        )

# Rutas para manejo de subperiodos
@classes_bp.route('/<class_id>/subperiod/create', methods=['POST'])
@APIRoute.standard(auth_required_flag=True, roles=[ROLES["TEACHER"], ROLES["INSTITUTE_ADMIN"]])
def create_subperiod(class_id):
    """
    Crea un nuevo subperíodo para una clase.
    """
    try:
        # Validar que vienen los campos requeridos
        required_fields = ['name', 'start_date', 'end_date']
        for field in required_fields:
            if field not in request.json:
                return APIRoute.error(f"Campo requerido: {field}", 400)
        
        # Obtener el ID del usuario actual
        user_id = get_jwt_identity()
        
        # Crear el subperiodo
        subperiod_data = {
            'class_id': ObjectId(class_id),
            'name': request.json['name'],
            'start_date': request.json['start_date'],
            'end_date': request.json['end_date'],
            'status': request.json.get('status', 'active'),
            'created_by': ObjectId(user_id)
        }
        
        success, result = subperiod_service.create_subperiod(subperiod_data)
        
        if success:
            return APIRoute.success({"id": result}, 201)
        else:
            return APIRoute.error(result, 400)
    except Exception as e:
        return APIRoute.error(str(e), 500)

@classes_bp.route('/<class_id>/subperiods', methods=['GET'])
@APIRoute.standard(auth_required_flag=True, roles=[ROLES["TEACHER"], ROLES["STUDENT"]])
def get_class_subperiods(class_id):
    """
    Obtiene todos los subperíodos de una clase.
    """
    try:
        subperiods = subperiod_service.get_class_subperiods(class_id)
        return APIRoute.success(subperiods)
    except Exception as e:
        return APIRoute.error(str(e), 500)

@classes_bp.route('/<class_id>/subperiod/<subperiod_id>', methods=['PUT'])
@APIRoute.standard(auth_required_flag=True, roles=[ROLES["TEACHER"], ROLES["INSTITUTE_ADMIN"]])
def update_subperiod(class_id, subperiod_id):
    """
    Actualiza un subperíodo existente.
    
    Args:
        class_id: ID de la clase
        subperiod_id: ID del subperíodo a actualizar
    
    Request JSON:
        name: (opcional) Nuevo nombre del subperíodo
        start_date: (opcional) Nueva fecha de inicio
        end_date: (opcional) Nueva fecha de fin
        status: (opcional) Nuevo estado ('active' o 'inactive')
    """
    try:
        # Verificar que vienen datos para actualizar
        if not request.json:
            return APIRoute.error(
                ErrorCodes.MISSING_FIELDS,
                "No se proporcionaron datos para actualizar",
                status_code=400
            )
        
        # Verificar que el subperíodo pertenece a la clase especificada
        subperiod = subperiod_service.collection.find_one({
            "_id": ObjectId(subperiod_id),
            "class_id": ObjectId(class_id)
        })
        
        if not subperiod:
            return APIRoute.error(
                ErrorCodes.NOT_FOUND,
                "Subperíodo no encontrado o no pertenece a la clase especificada",
                status_code=404
            )
        
        # Actualizar el subperíodo
        success, message = subperiod_service.update_subperiod(subperiod_id, request.json)
        
        if success:
            return APIRoute.success(message=message)
        return APIRoute.error(
            ErrorCodes.OPERATION_FAILED,
            message,
            status_code=400
        )
    except Exception as e:
        return APIRoute.error(
            ErrorCodes.SERVER_ERROR,
            str(e),
            status_code=500
        )

@classes_bp.route('/<class_id>/subperiod/<subperiod_id>', methods=['DELETE'])
@APIRoute.standard(auth_required_flag=True, roles=[ROLES["TEACHER"], ROLES["INSTITUTE_ADMIN"]])
def delete_subperiod(class_id, subperiod_id):
    """
    Elimina un subperíodo existente.
    
    Args:
        class_id: ID de la clase
        subperiod_id: ID del subperíodo a eliminar
    """
    try:
        # Verificar que el subperíodo pertenece a la clase especificada
        subperiod = subperiod_service.collection.find_one({
            "_id": ObjectId(subperiod_id),
            "class_id": ObjectId(class_id)
        })
        
        if not subperiod:
            return APIRoute.error(
                ErrorCodes.NOT_FOUND,
                "Subperíodo no encontrado o no pertenece a la clase especificada",
                status_code=404
            )
        
        # Eliminar el subperíodo
        success, message = subperiod_service.delete_subperiod(subperiod_id)
        
        if success:
            return APIRoute.success(message=message)
        return APIRoute.error(
            ErrorCodes.DELETE_ERROR,
            message,
            status_code=400
        )
    except Exception as e:
        return APIRoute.error(
            ErrorCodes.SERVER_ERROR,
            str(e),
            status_code=500
        )

@classes_bp.route('/level/<level_id>', methods=['GET'])
@APIRoute.standard(auth_required_flag=True, roles=[ROLES["INSTITUTE_ADMIN"]])
def get_level_classes(level_id):
    """
    Obtiene todas las clases de un nivel específico.
    Solo accesible para administradores del instituto.
    """
    try:
        classes = class_service.get_classes_by_level(level_id)
        return APIRoute.success(classes)
    except Exception as e:
        return APIRoute.error(str(e), 500)

@classes_bp.route('/', methods=['OPTIONS'])
@classes_bp.route('/<path:path>', methods=['OPTIONS'])
def handle_options(path=None):
    """
    Manejador para solicitudes OPTIONS - requerido para CORS
    """
    return "", 200 