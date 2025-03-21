from flask import request, jsonify
from bson import ObjectId

from src.shared.standardization import APIBlueprint, APIRoute, ErrorCodes
from src.shared.constants import ROLES
from .services import ResourceService, ResourceFolderService

resources_bp = APIBlueprint('resources', __name__)
resource_service = ResourceService()
folder_service = ResourceFolderService()

@resources_bp.route('/teacher', methods=['GET'])
@APIRoute.standard(auth_required_flag=True, roles=[ROLES["TEACHER"]])
def list_teacher_resources():
    """
    Obtiene todos los recursos de un profesor.
    Puede filtrar por carpeta_id y admite búsqueda de texto.
    """
    try:
        # Obtener parámetros
        email = request.args.get('email')
        folder_id = request.args.get('folder_id')
        query = request.args.get('query')
        
        # Validar email
        if not email:
            return APIRoute.error(
                ErrorCodes.MISSING_FIELDS, 
                "Se requiere el email del profesor", 
                status_code=400
            )
            
        # Obtener el ID del profesor a partir del email
        teacher_id = resource_service.get_teacher_by_email(email)
        if not teacher_id:
            return APIRoute.error(
                ErrorCodes.USER_NOT_FOUND, 
                "Profesor no encontrado", 
                status_code=404
            )
            
        # Verificar si es búsqueda o listado simple
        if query:
            # Procesar filtros adicionales
            filters = {}
            
            # Tipos de recursos
            if request.args.get('types'):
                filters['types'] = request.args.get('types').split(',')
                
            # Etiquetas
            if request.args.get('tags'):
                filters['tags'] = request.args.get('tags').split(',')
                
            # Rango de fechas
            if request.args.get('start_date') and request.args.get('end_date'):
                filters['start_date'] = request.args.get('start_date')
                filters['end_date'] = request.args.get('end_date')
                
            # Buscar recursos
            resources = resource_service.search_resources(teacher_id, query, filters)
        else:
            # Listado simple por carpeta o todos
            resources = resource_service.get_teacher_resources(teacher_id, folder_id)
            
        return APIRoute.success({"resources": resources})
    except Exception as e:
        return APIRoute.error(
            ErrorCodes.SERVER_ERROR, 
            str(e), 
            status_code=500
        )

@resources_bp.route('/teacher/tree', methods=['GET'])
@APIRoute.standard(auth_required_flag=True, roles=[ROLES["TEACHER"]])
def get_folder_tree():
    """
    Obtiene el árbol completo de carpetas y recursos del profesor.
    """
    try:
        # Obtener parámetros
        email = request.args.get('email')
        
        # Validar email
        if not email:
            return APIRoute.error(
                ErrorCodes.MISSING_FIELDS, 
                "Se requiere el email del profesor", 
                status_code=400
            )
            
        # Obtener el ID del profesor a partir del email
        teacher_id = resource_service.get_teacher_by_email(email)
        if not teacher_id:
            return APIRoute.error(
                ErrorCodes.USER_NOT_FOUND, 
                "Profesor no encontrado", 
                status_code=404
            )
            
        # Obtener árbol de carpetas
        tree = folder_service.get_folder_tree(teacher_id)
            
        return APIRoute.success(tree)
    except Exception as e:
        return APIRoute.error(
            ErrorCodes.SERVER_ERROR, 
            str(e), 
            status_code=500
        )

@resources_bp.route('/teacher', methods=['POST'])
@APIRoute.standard(auth_required_flag=True, roles=[ROLES["TEACHER"]])
def create_resource():
    """
    Crea un nuevo recurso.
    El frontend debe haber subido el archivo a la nube y proporcionar la URL.
    """
    try:
        # Validar que vienen los campos requeridos
        required_fields = ['name', 'type', 'url', 'created_by']
        for field in required_fields:
            if field not in request.json:
                return APIRoute.error(
                    ErrorCodes.MISSING_FIELDS, 
                    f"Campo requerido: {field}", 
                    status_code=400
                )
                
        # Crear recurso
        success, result = resource_service.create_resource(request.json)
        
        if success:
            # Obtener el recurso creado
            resource = resource_service.get_resource(result)
            return APIRoute.success(
                resource, 
                message="Recurso creado exitosamente", 
                status_code=201
            )
        else:
            return APIRoute.error(
                ErrorCodes.CREATION_ERROR, 
                result, 
                status_code=400
            )
    except Exception as e:
        return APIRoute.error(
            ErrorCodes.SERVER_ERROR, 
            str(e), 
            status_code=500
        )

@resources_bp.route('/<resource_id>', methods=['GET'])
@APIRoute.standard(auth_required_flag=True)
def get_resource(resource_id):
    """
    Obtiene un recurso específico por su ID.
    """
    try:
        resource = resource_service.get_resource(resource_id)
        if resource:
            return APIRoute.success(resource)
        else:
            return APIRoute.error(
                ErrorCodes.RESOURCE_NOT_FOUND, 
                "Recurso no encontrado", 
                status_code=404
            )
    except Exception as e:
        return APIRoute.error(
            ErrorCodes.SERVER_ERROR, 
            str(e), 
            status_code=500
        )

@resources_bp.route('/<resource_id>', methods=['PUT'])
@APIRoute.standard(auth_required_flag=True, roles=[ROLES["TEACHER"]])
def update_resource(resource_id):
    """
    Actualiza un recurso existente.
    """
    try:
        # Validar que viene al menos un campo para actualizar
        if not request.json:
            return APIRoute.error(
                ErrorCodes.INVALID_DATA, 
                "No se proporcionaron datos para actualizar", 
                status_code=400
            )
            
        # Campos permitidos para actualización
        allowed_fields = [
            'name', 'description', 'tags', 'folder_id', 
            'thumbnail_url', 'metadata'
        ]
        
        updates = {}
        for field in allowed_fields:
            if field in request.json:
                updates[field] = request.json[field]
                
        if not updates:
            return APIRoute.error(
                ErrorCodes.INVALID_DATA, 
                "No se proporcionaron campos válidos para actualizar", 
                status_code=400
            )
            
        # Actualizar recurso
        success, result = resource_service.update_resource(resource_id, updates)
        
        if success:
            # Obtener el recurso actualizado
            resource = resource_service.get_resource(resource_id)
            return APIRoute.success(
                resource,
                message=result
            )
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

@resources_bp.route('/<resource_id>', methods=['DELETE'])
@APIRoute.standard(auth_required_flag=True, roles=[ROLES["TEACHER"]])
def delete_resource(resource_id):
    """
    Elimina un recurso específico por su ID.
    """
    try:
        success, result = resource_service.delete_resource(resource_id)
        
        if success:
            return APIRoute.success(
                {"message": result}
            )
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

@resources_bp.route('/<resource_id>/move', methods=['PUT'])
@APIRoute.standard(auth_required_flag=True, roles=[ROLES["TEACHER"]])
def move_resource(resource_id):
    """
    Mueve un recurso a otra carpeta.
    """
    try:
        # Validar que viene el campo folder_id
        if 'folder_id' not in request.json:
            return APIRoute.error(
                ErrorCodes.MISSING_FIELDS, 
                "Se requiere el ID de la carpeta destino", 
                status_code=400
            )
            
        folder_id = request.json.get('folder_id')
        
        # Si folder_id es null, mover a la raíz
        if folder_id is None:
            updates = {"folder_id": None}
        else:
            # Verificar que la carpeta existe
            if not resource_service.check_folder_exists(folder_id):
                return APIRoute.error(
                    ErrorCodes.RESOURCE_NOT_FOUND, 
                    "La carpeta destino no existe", 
                    status_code=404
                )
                
            updates = {"folder_id": folder_id}
            
        # Actualizar recurso
        success, result = resource_service.update_resource(resource_id, updates)
        
        if success:
            return APIRoute.success(
                {"message": "Recurso movido correctamente"}
            )
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

@resources_bp.route('/folders', methods=['POST'])
@APIRoute.standard(auth_required_flag=True, roles=[ROLES["TEACHER"]])
def create_folder():
    """
    Crea una nueva carpeta de recursos.
    """
    try:
        # Validar que vienen los campos requeridos
        required_fields = ['name', 'created_by']
        for field in required_fields:
            if field not in request.json:
                return APIRoute.error(
                    ErrorCodes.MISSING_FIELDS, 
                    f"Campo requerido: {field}", 
                    status_code=400
                )
                
        # Crear carpeta
        success, result = folder_service.create_folder(request.json)
        
        if success:
            # Obtener la carpeta creada
            folder = folder_service.get_folder(result)
            return APIRoute.success(
                folder, 
                message="Carpeta creada exitosamente", 
                status_code=201
            )
        else:
            return APIRoute.error(
                ErrorCodes.CREATION_ERROR, 
                result, 
                status_code=400
            )
    except Exception as e:
        return APIRoute.error(
            ErrorCodes.SERVER_ERROR, 
            str(e), 
            status_code=500
        )

@resources_bp.route('/folders/<folder_id>', methods=['GET'])
@APIRoute.standard(auth_required_flag=True)
def get_folder(folder_id):
    """
    Obtiene una carpeta específica por su ID.
    """
    try:
        folder = folder_service.get_folder(folder_id)
        if folder:
            return APIRoute.success(folder)
        else:
            return APIRoute.error(
                ErrorCodes.RESOURCE_NOT_FOUND, 
                "Carpeta no encontrada", 
                status_code=404
            )
    except Exception as e:
        return APIRoute.error(
            ErrorCodes.SERVER_ERROR, 
            str(e), 
            status_code=500
        )

@resources_bp.route('/folders/<folder_id>/resources', methods=['GET'])
@APIRoute.standard(auth_required_flag=True)
def get_folder_resources(folder_id):
    """
    Obtiene todos los recursos de una carpeta específica.
    """
    try:
        # Verificar que la carpeta existe
        folder = folder_service.get_folder(folder_id)
        if not folder:
            return APIRoute.error(
                ErrorCodes.RESOURCE_NOT_FOUND, 
                "Carpeta no encontrada", 
                status_code=404
            )
            
        # Obtener recursos de la carpeta
        resources = resource_service.get_teacher_resources(folder["created_by"], folder_id)
            
        return APIRoute.success({
            "folder": folder,
            "resources": resources
        })
    except Exception as e:
        return APIRoute.error(
            ErrorCodes.SERVER_ERROR, 
            str(e), 
            status_code=500
        )

@resources_bp.route('/folders/<folder_id>', methods=['PUT'])
@APIRoute.standard(auth_required_flag=True, roles=[ROLES["TEACHER"]])
def update_folder(folder_id):
    """
    Actualiza una carpeta existente.
    """
    try:
        # Validar que viene al menos un campo para actualizar
        if not request.json:
            return APIRoute.error(
                ErrorCodes.INVALID_DATA, 
                "No se proporcionaron datos para actualizar", 
                status_code=400
            )
            
        # Campos permitidos para actualización
        allowed_fields = ['name', 'description', 'parent_id']
        
        updates = {}
        for field in allowed_fields:
            if field in request.json:
                updates[field] = request.json[field]
                
        if not updates:
            return APIRoute.error(
                ErrorCodes.INVALID_DATA, 
                "No se proporcionaron campos válidos para actualizar", 
                status_code=400
            )
            
        # Actualizar carpeta
        success, result = folder_service.update_folder(folder_id, updates)
        
        if success:
            # Obtener la carpeta actualizada
            folder = folder_service.get_folder(folder_id)
            return APIRoute.success(
                folder,
                message=result
            )
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

@resources_bp.route('/folders/<folder_id>', methods=['DELETE'])
@APIRoute.standard(auth_required_flag=True, roles=[ROLES["TEACHER"]])
def delete_folder(folder_id):
    """
    Elimina una carpeta específica por su ID.
    """
    try:
        success, result = folder_service.delete_folder(folder_id)
        
        if success:
            return APIRoute.success(
                {"message": result}
            )
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