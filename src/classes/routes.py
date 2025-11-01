from flask import request, jsonify
from bson import ObjectId
from flask_jwt_extended import get_jwt_identity, get_jwt

from datetime import datetime
import logging

from src.shared.standardization import APIBlueprint, APIRoute, ErrorCodes
from src.shared.constants import ROLES
from src.shared.decorators import (
    auth_required, 
    role_required, 
    workspace_type_required,
    workspace_access_required
)
from src.shared.middleware import apply_workspace_filter, get_current_workspace_info
from .services import ClassService, MembershipService, SubperiodService
from src.shared.database import get_db

classes_bp = APIBlueprint('classes', __name__)
class_service = ClassService()
membership_service = MembershipService()

logger = logging.getLogger(__name__)
# content_service ha sido eliminado ya que ahora se usa StudentIndividualContentService
subperiod_service = SubperiodService()

# Rutas para manejo de clases
@classes_bp.route('/create', methods=['POST'])
@auth_required
@role_required([ROLES["TEACHER"], ROLES["INSTITUTE_ADMIN"]])
@apply_workspace_filter('classes')
def create_class():
    """
    Crea una nueva clase con los parámetros especificados.
    El usuario creador se agrega automáticamente como miembro con rol de profesor.
    """
    try:
        # Obtener información del workspace actual
        workspace_info = get_current_workspace_info()
        workspace_type = workspace_info.get('workspace_type')
        
        # Para workspaces individuales de profesor, validar que sea el usuario actual
        if workspace_type == 'INDIVIDUAL_TEACHER':
            if request.user_id != workspace_info.get('user_id'):
                return APIRoute.error(
                    ErrorCodes.FORBIDDEN,
                    "Solo puedes crear clases en tu workspace individual",
                    status_code=403
                )
        
        # Validar que vienen los campos requeridos
        required_fields = ['subject_id', 'section_id', 'academic_period_id', 'level_id', 'name', 'access_code']
        for field in required_fields:
            if field not in request.json:
                return APIRoute.error(ErrorCodes.MISSING_FIELD, f"Campo requerido: {field}")
        
        # Obtener el usuario actual
        user_id = get_jwt_identity()
        
        # Crear la clase con información del workspace
        class_data = {
            'institute_id': ObjectId(workspace_info.get('institute_id')),
            'workspace_id': ObjectId(workspace_info.get('workspace_id')),
            'workspace_type': workspace_type,
            'subject_id': ObjectId(request.json['subject_id']),
            'section_id': ObjectId(request.json['section_id']),
            'academic_period_id': ObjectId(request.json['academic_period_id']),
            'level_id': ObjectId(request.json['level_id']),
            'name': request.json['name'],
            'access_code': request.json['access_code'],
            'created_by': ObjectId(user_id) if ObjectId.is_valid(user_id) else user_id
        }

        created_at_value = request.json.get('created_at')
        if created_at_value:
            try:
                class_data['created_at'] = datetime.fromisoformat(created_at_value)
            except (ValueError, TypeError):
                logger.warning("create_class: valor de created_at no v\u00e1lido recibido, se usar\u00e1 la fecha actual")
        
        # Si hay un schedule, agregarlo
        if 'schedule' in request.json:
            class_data['schedule'] = request.json['schedule']
        
        success, result = class_service.create_class(class_data)

        if success:
            return APIRoute.success(data={"id": result}, message="Clase creada exitosamente", status_code=201)
        else:
            return APIRoute.error(ErrorCodes.CREATION_ERROR, result)
    except Exception as e:
        return APIRoute.error(ErrorCodes.SERVER_ERROR, str(e), status_code=500)

@classes_bp.route('/<class_id>', methods=['GET'])
@auth_required
@role_required([ROLES["TEACHER"], ROLES["STUDENT"], ROLES["INSTITUTE_ADMIN"]])
@apply_workspace_filter('classes')
def get_class_details(class_id):
    """
    Obtiene los detalles de una clase específica.
    """
    try:
        workspace_info = get_current_workspace_info()
        class_details = class_service.get_class_details(class_id, workspace_info)
        if class_details:
            return APIRoute.success(data=class_details)
        else:
            return APIRoute.error(ErrorCodes.NOT_FOUND, "Clase no encontrada", status_code=404)
    except Exception as e:
        return APIRoute.error(ErrorCodes.SERVER_ERROR, str(e), status_code=500)

@classes_bp.route('/<class_id>/update', methods=['PUT'])
@auth_required
@role_required([ROLES["TEACHER"], ROLES["INSTITUTE_ADMIN"]])
@apply_workspace_filter('classes')
def update_class(class_id):
    """
    Actualiza una clase existente.
    """
    try:
        # Obtener información del workspace actual
        workspace_info = get_current_workspace_info()
        workspace_type = workspace_info.get('workspace_type')
        
        # Para workspaces individuales de profesor, validar que sea el usuario actual
        if workspace_type == 'INDIVIDUAL_TEACHER':
            if request.user_id != workspace_info.get('user_id'):
                return APIRoute.error(
                    ErrorCodes.FORBIDDEN,
                    "Solo puedes actualizar clases en tu workspace individual",
                    status_code=403
                )
        
        # Validar que viene al menos un campo para actualizar
        if not request.json:
            return APIRoute.error(ErrorCodes.MISSING_FIELD, "No se proporcionaron datos para actualizar", status_code=400)
        
        # Campos permitidos para actualización
        allowed_fields = [
            'name',
            'access_code',
            'status',
            'settings',
            'subject_id',
            'section_id',
            'academic_period_id'
        ]
        updates = {}
        
        for field in allowed_fields:
            if field in request.json:
                value = request.json[field]
                if field in {'subject_id', 'section_id', 'academic_period_id'} and value is not None:
                    updates[field] = str(value)
                else:
                    updates[field] = value
        
        if not updates:
            return APIRoute.error(ErrorCodes.MISSING_FIELD, "No se proporcionaron campos válidos para actualizar", status_code=400)
        
        success, result = class_service.update_class(class_id, updates)

        if success:
            return APIRoute.success(data={"message": result})
        else:
            return APIRoute.error(ErrorCodes.UPDATE_ERROR, result)
    except Exception as e:
        return APIRoute.error(ErrorCodes.SERVER_ERROR, str(e), status_code=500)

@classes_bp.route('/<class_id>', methods=['DELETE'])
@auth_required
@role_required([ROLES["TEACHER"], ROLES["INSTITUTE_ADMIN"]])
@apply_workspace_filter('classes')
def delete_class(class_id):
    """
    Elimina una clase específica. Si cascade=true en query params, elimina también todas sus dependencias.
    
    Args:
        class_id: ID de la clase a eliminar
    Query params:
        cascade: Si es 'true', elimina en cascada todas las dependencias
    """
    try:
        # Obtener información del workspace actual
        workspace_info = get_current_workspace_info()
        workspace_type = workspace_info.get('workspace_type')
        
        # Para workspaces individuales de profesor, validar que sea el usuario actual
        if workspace_type == 'INDIVIDUAL_TEACHER':
            if request.user_id != workspace_info.get('user_id'):
                return APIRoute.error(
                    ErrorCodes.FORBIDDEN,
                    "Solo puedes eliminar clases en tu workspace individual",
                    status_code=403
                )
        
        # Obtener parámetro cascade del query string
        cascade = request.args.get('cascade', 'false').lower() == 'true'
        
        # Llamar al método con todos los parámetros explícitos
        success, message = class_service.delete_class(
            class_id=class_id,
            workspace_info=workspace_info,
            cascade=cascade
        )

        if success:
            return APIRoute.success(data={"message": message})
        return APIRoute.error(
            ErrorCodes.DELETE_ERROR,
            message,
            status_code=400,
        )
    except Exception as e:
        return APIRoute.error(
            ErrorCodes.SERVER_ERROR,
            str(e),
            status_code=500
        )

@classes_bp.route('/<class_id>/check-dependencies', methods=['GET'])
@auth_required
@role_required([ROLES["TEACHER"], ROLES["INSTITUTE_ADMIN"]])
@apply_workspace_filter('classes')
def check_class_dependencies(class_id):
    """
    Verifica si una clase tiene dependencias que impiden su eliminación.
    
    Args:
        class_id: ID de la clase a verificar
    """
    try:
        # Obtener información del workspace actual
        workspace_info = get_current_workspace_info()
        
        # Verificar que la clase existe y pertenece al workspace
        workspace_type = workspace_info.get('workspace_type')

        # Tratar workspace_type ausente como INSTITUTE por compatibilidad
        if workspace_type == 'INSTITUTE' or not workspace_type:
            # Para workspaces de instituto, buscar por workspace_id O por institute_id
            filter_query = {
                "_id": ObjectId(class_id),
                "$or": [
                    {"workspace_id": ObjectId(workspace_info['workspace_id'])},
                    {
                        "workspace_id": {"$exists": False},
                        "institute_id": ObjectId(workspace_info.get('institute_id'))
                    }
                ]
            }
        else:
            # Para otros tipos de workspace, mantener filtro estricto
            filter_query = {
                "_id": ObjectId(class_id),
                "workspace_id": ObjectId(workspace_info.get('workspace_id'))
            }
        
        # Log de depuración para entender el filtro aplicado
        try:
            logger.info(
                f"check_class_dependencies: class_id={class_id}, workspace_info={{'workspace_id': {workspace_info.get('workspace_id')}, 'workspace_type': {workspace_type}, 'institute_id': {workspace_info.get('institute_id')}}}, filter={filter_query}"
            )
        except Exception:
            pass

        class_data = class_service.collection.find_one(filter_query)
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
        
        return APIRoute.success(
            data={
                "has_dependencies": members_count > 0 or subperiods_count > 0,
                "dependencies": {
                    "members": members_count,
                    "subperiods": subperiods_count,
                },
            }
        )
        
    except Exception as e:
        return APIRoute.error(
            ErrorCodes.SERVER_ERROR,
            str(e),
            status_code=500
        )

# Rutas para manejo de miembros de la clase
@classes_bp.route('/<class_id>/members/add', methods=['POST'])
@auth_required
@role_required([ROLES["TEACHER"], ROLES["INSTITUTE_ADMIN"]])
@apply_workspace_filter('classes')
def add_class_member(class_id):
    """
    Agrega un miembro a una clase.
    """
    try:
        # Obtener información del workspace actual
        workspace_info = get_current_workspace_info()
        workspace_type = workspace_info.get('workspace_type')
        
        # Para workspaces individuales, no se pueden agregar miembros
        if workspace_type in ['INDIVIDUAL_TEACHER', 'INDIVIDUAL_STUDENT']:
            return APIRoute.error(
                ErrorCodes.FORBIDDEN,
                "No se pueden agregar miembros en workspaces individuales",
                status_code=403
            )
        
        # Validar que vienen los campos requeridos
        if 'user_id' not in request.json or 'role' not in request.json:
            return APIRoute.error(ErrorCodes.MISSING_FIELD, "Se requieren los campos user_id y role", status_code=400)
        
        user_id = request.json['user_id']
        role = request.json['role']
        
        # Validar que el rol es válido
        if role not in ["TEACHER", "STUDENT"]:
            return APIRoute.error(ErrorCodes.INVALID_DATA, "Rol no válido. Debe ser 'TEACHER' o 'STUDENT'", status_code=400)
        
        success, result = membership_service.add_member(class_id, user_id, role, workspace_info)

        if success:
            return APIRoute.success(data={"id": result}, status_code=201)
        else:
            return APIRoute.error(ErrorCodes.CREATION_ERROR, result)
    except Exception as e:
        return APIRoute.error(ErrorCodes.SERVER_ERROR, str(e), status_code=500)

@classes_bp.route('/<class_id>/members', methods=['GET'])
@auth_required
@role_required([ROLES["TEACHER"], ROLES["STUDENT"], ROLES["INSTITUTE_ADMIN"]])
@apply_workspace_filter('classes')
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
        return APIRoute.success(data=members)
    except Exception as e:
        return APIRoute.error(ErrorCodes.SERVER_ERROR, str(e), status_code=500)

@classes_bp.route('/teacher/<teacher_id_or_email>', methods=['GET'])
@auth_required
@apply_workspace_filter('classes')
def get_teacher_classes(teacher_id_or_email):
    """
    Obtiene todas las clases de un profesor.
    """
    try:
        # Obtener información del workspace actual
        workspace_info = get_current_workspace_info()
        workspace_type = workspace_info.get('workspace_type')
        
        # Para workspaces individuales de profesor, validar que sea el usuario actual
        if workspace_type == 'INDIVIDUAL_TEACHER':
            if teacher_id_or_email != request.user_id:
                return APIRoute.error(
                    ErrorCodes.FORBIDDEN,
                    "Solo puedes acceder a tus propias clases en workspace individual",
                    status_code=403
                )
        
        classes = membership_service.get_classes_by_teacher(
            teacher_id_or_email, workspace_info
        )
        return APIRoute.success(data=classes)
    except Exception as e:
        return APIRoute.error(ErrorCodes.SERVER_ERROR, str(e), status_code=500)

@classes_bp.route('/student/<student_id_or_email>', methods=['GET'])
@auth_required
@apply_workspace_filter('classes')
def get_student_classes(student_id_or_email):
    """
    Obtiene todas las clases de un estudiante.
    """
    try:
        # Obtener información del workspace actual
        workspace_info = get_current_workspace_info()
        workspace_type = workspace_info.get('workspace_type')
        
        # Para workspaces individuales de estudiante, validar que sea el usuario actual
        if workspace_type == 'INDIVIDUAL_STUDENT':
            if student_id_or_email != request.user_id:
                return APIRoute.error(
                    ErrorCodes.FORBIDDEN,
                    "Solo puedes acceder a tus propias clases en workspace individual",
                    status_code=403
                )
        
        classes = membership_service.get_classes_by_student(
            student_id_or_email, workspace_info
        )
        return APIRoute.success(data=classes)
    except Exception as e:
        return APIRoute.error(ErrorCodes.SERVER_ERROR, str(e), status_code=500)

@classes_bp.route('/<class_id>/students', methods=['GET'])
@APIRoute.standard(auth_required_flag=True, roles=[ROLES["TEACHER"], ROLES["INSTITUTE_ADMIN"]])
def get_class_students(class_id):
    """
    Obtiene todos los estudiantes de una clase.
    """
    try:
        students = membership_service.get_class_students(class_id)
        return APIRoute.success(data=students)
    except Exception as e:
        return APIRoute.error(ErrorCodes.SERVER_ERROR, str(e), status_code=500)

@classes_bp.route('/<class_id>/members/<member_id>', methods=['DELETE'])
@auth_required
@role_required([ROLES["TEACHER"], ROLES["INSTITUTE_ADMIN"]])
@apply_workspace_filter('classes')
def remove_class_member(class_id, member_id):
    """
    Elimina un miembro de una clase.
    
    Args:
        class_id: ID de la clase
        member_id: ID del miembro a eliminar
    """
    try:
        # Obtener información del workspace actual
        workspace_info = get_current_workspace_info()
        workspace_type = workspace_info.get('workspace_type')
        
        # Para workspaces individuales, no se pueden eliminar miembros
        if workspace_type in ['INDIVIDUAL_TEACHER', 'INDIVIDUAL_STUDENT']:
            return APIRoute.error(
                ErrorCodes.FORBIDDEN,
                "No se pueden eliminar miembros en workspaces individuales",
                status_code=403
            )
        
        success, message = membership_service.remove_member(class_id, member_id, workspace_info)

        if success:
            return APIRoute.success(data={"message": message})
        return APIRoute.error(
            ErrorCodes.DELETE_ERROR,
            message,
            status_code=400,
        )
    except Exception as e:
        return APIRoute.error(
            ErrorCodes.SERVER_ERROR,
            str(e),
            status_code=500
        )

@classes_bp.route('/<class_id>/members/add-by-email', methods=['POST'])
@auth_required
@role_required([ROLES["TEACHER"], ROLES["INSTITUTE_ADMIN"]])
@apply_workspace_filter('classes')
def add_class_member_by_email(class_id):
    """
    Agrega un miembro a una clase mediante su email.
    
    Args:
        class_id: ID de la clase
    """
    try:
        # Obtener información del workspace actual
        workspace_info = get_current_workspace_info()
        workspace_type = workspace_info.get('workspace_type')
        
        # Para workspaces individuales, no se pueden agregar miembros
        if workspace_type in ['INDIVIDUAL_TEACHER', 'INDIVIDUAL_STUDENT']:
            return APIRoute.error(
                ErrorCodes.FORBIDDEN,
                "No se pueden agregar miembros en workspaces individuales",
                status_code=403
            )
        
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
        
        success, result = membership_service.add_member_by_email(class_id, email, role, workspace_info)

        if success:
            if isinstance(result, dict) and "message" in result:
                return APIRoute.success(data=result, message=result["message"], status_code=200)
            return APIRoute.success(data=result, status_code=201)
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
@auth_required
@role_required([ROLES["TEACHER"], ROLES["INSTITUTE_ADMIN"]])
@apply_workspace_filter('classes')
def create_subperiod(class_id):
    """
    Crea un nuevo subperíodo para una clase.
    """
    try:
        # Obtener información del workspace actual
        workspace_info = get_current_workspace_info()
        workspace_type = workspace_info.get('workspace_type')
        
        # Para workspaces individuales de profesor, validar que sea el usuario actual
        if workspace_type == 'INDIVIDUAL_TEACHER':
            if request.user_id != workspace_info.get('user_id'):
                return APIRoute.error(
                    ErrorCodes.FORBIDDEN,
                    "Solo puedes crear subperíodos en tu workspace individual",
                    status_code=403
                )
        
        # Validar que vienen los campos requeridos
        required_fields = ['name', 'start_date', 'end_date']
        for field in required_fields:
            if field not in request.json:
                return APIRoute.error(ErrorCodes.MISSING_FIELD, f"Campo requerido: {field}", status_code=400)
        
        # Obtener el ID del usuario actual
        user_id = get_jwt_identity()
        
        # Crear el subperiodo
        subperiod_data = {
            'class_id': ObjectId(class_id),
            'workspace_id': ObjectId(workspace_info.get('workspace_id')),
            'workspace_type': workspace_type,
            'name': request.json['name'],
            'start_date': request.json['start_date'],
            'end_date': request.json['end_date'],
            'status': request.json.get('status', 'active'),
            'created_by': ObjectId(user_id)
        }
        
        success, result = subperiod_service.create_subperiod(subperiod_data, workspace_info)

        if success:
            return APIRoute.success(data={"id": result}, status_code=201)
        else:
            return APIRoute.error(ErrorCodes.CREATION_ERROR, result)
    except Exception as e:
        return APIRoute.error(ErrorCodes.SERVER_ERROR, str(e), status_code=500)

@classes_bp.route('/<class_id>/subperiods', methods=['GET'])
@auth_required
@role_required([ROLES["TEACHER"], ROLES["STUDENT"]])
@apply_workspace_filter('classes')
def get_class_subperiods(class_id):
    """
    Obtiene todos los subperíodos de una clase.
    """
    try:
        subperiods = subperiod_service.get_class_subperiods(class_id)
        return APIRoute.success(data=subperiods)
    except Exception as e:
        return APIRoute.error(ErrorCodes.SERVER_ERROR, str(e), status_code=500)

@classes_bp.route('/<class_id>/subperiod/<subperiod_id>', methods=['PUT'])
@auth_required
@role_required([ROLES["TEACHER"], ROLES["INSTITUTE_ADMIN"]])
@apply_workspace_filter('classes')
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
        # Obtener información del workspace actual
        workspace_info = get_current_workspace_info()
        workspace_type = workspace_info.get('workspace_type')
        
        # Para workspaces individuales de profesor, validar que sea el usuario actual
        if workspace_type == 'INDIVIDUAL_TEACHER':
            if request.user_id != workspace_info.get('user_id'):
                return APIRoute.error(
                    ErrorCodes.FORBIDDEN,
                    "Solo puedes actualizar subperíodos en tu workspace individual",
                    status_code=403
                )
        
        # Verificar que vienen datos para actualizar
        if not request.json:
            return APIRoute.error(
                ErrorCodes.MISSING_FIELDS,
                "No se proporcionaron datos para actualizar",
                status_code=400
            )
        
        # Verificar que el subperíodo pertenece a la clase especificada
        if workspace_type == 'INSTITUTE':
            # Para workspaces de instituto, buscar por workspace_id O por institute_id
            subperiod_filter = {
                "_id": ObjectId(subperiod_id),
                "class_id": ObjectId(class_id),
                "$or": [
                    {"workspace_id": ObjectId(workspace_info['workspace_id'])},
                    {
                        "workspace_id": {"$exists": False},
                        "institute_id": ObjectId(workspace_info.get('institute_id'))
                    }
                ]
            }
        else:
            # Para otros tipos de workspace, mantener filtro estricto
            subperiod_filter = {
                "_id": ObjectId(subperiod_id),
                "class_id": ObjectId(class_id),
                "workspace_id": ObjectId(workspace_info.get('workspace_id'))
            }
        
        subperiod = subperiod_service.collection.find_one(subperiod_filter)
        
        if not subperiod:
            return APIRoute.error(
                ErrorCodes.NOT_FOUND,
                "Subperíodo no encontrado o no pertenece a la clase especificada",
                status_code=404
            )
        
        # Actualizar el subperíodo
        success, message = subperiod_service.update_subperiod(subperiod_id, request.json, workspace_info)

        if success:
            return APIRoute.success(data={"message": message})
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
@auth_required
@role_required([ROLES["TEACHER"], ROLES["INSTITUTE_ADMIN"]])
@apply_workspace_filter('classes')
def delete_subperiod(class_id, subperiod_id):
    """
    Elimina un subperíodo existente.
    
    Args:
        class_id: ID de la clase
        subperiod_id: ID del subperíodo a eliminar
    """
    try:
        # Obtener información del workspace actual
        workspace_info = get_current_workspace_info()
        workspace_type = workspace_info.get('workspace_type')
        
        # Para workspaces individuales de profesor, validar que sea el usuario actual
        if workspace_type == 'INDIVIDUAL_TEACHER':
            if request.user_id != workspace_info.get('user_id'):
                return APIRoute.error(
                    ErrorCodes.FORBIDDEN,
                    "Solo puedes eliminar subperíodos en tu workspace individual",
                    status_code=403
                )
        
        # Verificar que el subperíodo pertenece a la clase especificada
        if workspace_type == 'INSTITUTE':
            # Para workspaces de instituto, buscar por workspace_id O por institute_id
            subperiod_filter = {
                "_id": ObjectId(subperiod_id),
                "class_id": ObjectId(class_id),
                "$or": [
                    {"workspace_id": ObjectId(workspace_info['workspace_id'])},
                    {
                        "workspace_id": {"$exists": False},
                        "institute_id": ObjectId(workspace_info.get('institute_id'))
                    }
                ]
            }
        else:
            # Para otros tipos de workspace, mantener filtro estricto
            subperiod_filter = {
                "_id": ObjectId(subperiod_id),
                "class_id": ObjectId(class_id),
                "workspace_id": ObjectId(workspace_info.get('workspace_id'))
            }
        
        subperiod = subperiod_service.collection.find_one(subperiod_filter)
        
        if not subperiod:
            return APIRoute.error(
                ErrorCodes.NOT_FOUND,
                "Subperíodo no encontrado o no pertenece a la clase especificada",
                status_code=404
            )
        
        # Eliminar el subperíodo
        success, message = subperiod_service.delete_subperiod(subperiod_id, workspace_info)

        if success:
            return APIRoute.success(data={"message": message})
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
@auth_required
@role_required([ROLES["INSTITUTE_ADMIN"]])
@apply_workspace_filter('classes')
def get_level_classes(level_id):
    """
    Obtiene todas las clases de un nivel específico.
    Solo accesible para administradores del instituto.
    """
    try:
        # Obtener información del workspace actual
        workspace_info = get_current_workspace_info()
        
        classes = class_service.get_classes_by_level(level_id, workspace_info)
        return APIRoute.success(data=classes)
    except Exception as e:
        return APIRoute.error(ErrorCodes.SERVER_ERROR, str(e), status_code=500)

@classes_bp.route('/', methods=['OPTIONS'])
@classes_bp.route('/<path:path>', methods=['OPTIONS'])
def handle_options(path=None):
    """
    Manejador para solicitudes OPTIONS - requerido para CORS
    """
    return "", 200