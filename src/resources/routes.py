from flask import request, jsonify
from bson import ObjectId

from src.shared.standardization import APIBlueprint, APIRoute, ErrorCodes
from src.shared.constants import ROLES
from src.shared.database import get_db
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
    Respeta la jerarquía de carpetas del usuario.
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
                
            # Buscar recursos (pasando email para respetar jerarquía)
            resources = resource_service.search_resources(teacher_id, query, filters, email=email)
        else:
            # Listado simple por carpeta o todos (pasando email para respetar jerarquía)
            resources = resource_service.get_teacher_resources(teacher_id, folder_id, email=email)
            
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
    Respeta la jerarquía de carpetas del usuario.
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
            
        # Obtener árbol de carpetas (pasando email para respetar jerarquía)
        tree = folder_service.get_folder_tree(teacher_id, email=email)
            
        return APIRoute.success(tree)
    except Exception as e:
        return APIRoute.error(
            ErrorCodes.SERVER_ERROR, 
            str(e), 
            status_code=500
        )

@resources_bp.route('/teacher', methods=['POST', 'OPTIONS'])
def create_resource_handler():
    """
    Punto de entrada para crear un nuevo recurso a través del endpoint /teacher.
    Maneja directamente las solicitudes OPTIONS para evitar problemas de CORS.
    """
    if request.method == 'OPTIONS':
        return APIRoute.success({})
    
    # Para POST, usar el handler con autenticación
    return create_resource()

@APIRoute.standard(auth_required_flag=True, roles=[ROLES["TEACHER"]])
def create_resource():
    """
    Crea un nuevo recurso a través del endpoint /teacher.
    El frontend debe haber subido el archivo a la nube y proporcionar la URL.
    Respeta la jerarquía de carpetas del usuario.
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
        
        # Asegurarse de que se proporciona email para respetar jerarquía
        email = request.json.get('email')
        if not email:
            # Intentar obtener email del usuario creador
            created_by = request.json.get('created_by')
            if created_by:
                user = get_db().users.find_one({"_id": ObjectId(created_by)})
                if user and "email" in user:
                    # Agregar email a los datos del recurso para jerarquía
                    email = user.get("email")
                    resource_data = request.json.copy()
                    resource_data["email"] = email
                else:
                    return APIRoute.error(
                        ErrorCodes.MISSING_FIELDS,
                        "No se pudo determinar el email del creador",
                        status_code=400
                    )
            else:
                return APIRoute.error(
                    ErrorCodes.MISSING_FIELDS,
                    "Se requiere el email o created_by para crear el recurso",
                    status_code=400
                )
        else:
            resource_data = request.json
                
        # Crear recurso
        success, result = resource_service.create_resource(resource_data)
        
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

@resources_bp.route('/<resource_id>', methods=['PUT', 'OPTIONS'])
def update_resource_handler(resource_id):
    """
    Punto de entrada para actualizar un recurso.
    Maneja directamente las solicitudes OPTIONS para evitar problemas de CORS.
    """
    if request.method == 'OPTIONS':
        return APIRoute.success({})
    
    # Para PUT, usar el handler con autenticación
    return update_resource(resource_id)

@APIRoute.standard(auth_required_flag=True, roles=[ROLES["TEACHER"]])
def update_resource(resource_id):
    """
    Actualiza un recurso existente.
    Respeta la jerarquía de carpetas del usuario.
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
        
        # Obtener email para verificación de jerarquía
        email = request.json.get('email')
            
        # Actualizar recurso
        success, result = resource_service.update_resource(resource_id, updates, email=email)
        
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

@resources_bp.route('/<resource_id>/move', methods=['PUT', 'OPTIONS'])
def move_resource_handler(resource_id):
    """
    Punto de entrada para mover un recurso.
    Maneja directamente las solicitudes OPTIONS para evitar problemas de CORS.
    """
    if request.method == 'OPTIONS':
        return APIRoute.success({})
    
    # Para PUT, usar el handler con autenticación
    return move_resource(resource_id)

@APIRoute.standard(auth_required_flag=True, roles=[ROLES["TEACHER"]])
def move_resource(resource_id):
    """
    Mueve un recurso a otra carpeta.
    Respeta la jerarquía de carpetas del usuario.
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
        email = request.json.get('email')
        
        # Verificar pertenencia si se proporciona email
        if email:
            # Obtener recurso y verificar que pertenece al usuario
            resource = resource_service.get_resource(resource_id)
            if not resource:
                return APIRoute.error(
                    ErrorCodes.RESOURCE_NOT_FOUND,
                    "Recurso no encontrado",
                    status_code=404
                )
                
            # Verificar que el recurso pertenece al usuario
            user = get_db().users.find_one({"email": email})
            if not user or str(user["_id"]) != resource["created_by"]:
                return APIRoute.error(
                    ErrorCodes.PERMISSION_DENIED,
                    "No tienes permiso para mover este recurso",
                    status_code=403
                )
                
            # Si folder_id no es nulo, verificar que está en la jerarquía del usuario
            if folder_id:
                folder_service = ResourceFolderService()
                root_folder = folder_service.get_user_root_folder(email)
                is_in_hierarchy = folder_service._verify_folder_in_user_hierarchy(
                    ObjectId(folder_id), root_folder["_id"])
                
                if not is_in_hierarchy:
                    return APIRoute.error(
                        ErrorCodes.PERMISSION_DENIED,
                        "No puedes mover el recurso fuera de tu espacio de usuario",
                        status_code=403
                    )
        
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
            
        # Actualizar recurso (pasando email para respetar jerarquía)
        success, result = resource_service.update_resource(resource_id, updates, email=email)
        
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

@resources_bp.route('/<resource_id>', methods=['DELETE', 'OPTIONS'])
def delete_resource_handler(resource_id):
    """
    Punto de entrada para eliminar un recurso.
    Maneja directamente las solicitudes OPTIONS para evitar problemas de CORS.
    """
    if request.method == 'OPTIONS':
        return APIRoute.success({})
    
    # Para DELETE, usar el handler con autenticación
    return delete_resource(resource_id)

@APIRoute.standard(auth_required_flag=True, roles=[ROLES["TEACHER"]])
def delete_resource(resource_id):
    """
    Elimina un recurso específico por su ID.
    """
    try:
        # Obtener email para verificación de jerarquía
        email = request.args.get('email')
        
        # Si se proporciona email, primero verificar pertenencia
        if email:
            # Obtener recurso y verificar que pertenece al usuario
            resource = resource_service.get_resource(resource_id)
            if not resource:
                return APIRoute.error(
                    ErrorCodes.RESOURCE_NOT_FOUND,
                    "Recurso no encontrado",
                    status_code=404
                )
                
            # Verificar que el recurso pertenece al usuario
            user = get_db().users.find_one({"email": email})
            if not user or str(user["_id"]) != resource["created_by"]:
                return APIRoute.error(
                    ErrorCodes.PERMISSION_DENIED,
                    "No tienes permiso para eliminar este recurso",
                    status_code=403
                )
        
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

@resources_bp.route('/folders', methods=['POST', 'OPTIONS'])
def create_folder_handler():
    """
    Punto de entrada para crear una nueva carpeta.
    Maneja directamente las solicitudes OPTIONS para evitar problemas de CORS.
    """
    if request.method == 'OPTIONS':
        return APIRoute.success({})
    
    # Para POST, usar el handler con autenticación
    return create_folder()

@APIRoute.standard(auth_required_flag=True, roles=[ROLES["TEACHER"]])
def create_folder():
    """
    Crea una nueva carpeta de recursos.
    Respeta la jerarquía de carpetas del usuario.
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
        
        # Asegurarse que email esté presente para jerarquía
        if 'email' not in request.json:
            # Intentar obtener email del usuario creador
            created_by = request.json.get('created_by')
            if created_by:
                user = get_db().users.find_one({"_id": ObjectId(created_by)})
                if user and "email" in user:
                    # Agregar email a los datos de la carpeta para jerarquía
                    request.json["email"] = user.get("email")
                else:
                    return APIRoute.error(
                        ErrorCodes.MISSING_FIELDS,
                        "No se pudo determinar el email del creador",
                        status_code=400
                    )
            else:
                return APIRoute.error(
                    ErrorCodes.MISSING_FIELDS,
                    "Se requiere el email para crear la carpeta en la jerarquía correcta",
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
    Respeta la jerarquía de carpetas del usuario.
    """
    try:
        # Obtener email para verificación de jerarquía
        email = request.args.get('email')
        
        # Verificar que la carpeta existe
        folder = folder_service.get_folder(folder_id)
        if not folder:
            return APIRoute.error(
                ErrorCodes.RESOURCE_NOT_FOUND, 
                "Carpeta no encontrada", 
                status_code=404
            )
        
        # Si se proporciona email, verificar que la carpeta está en la jerarquía
        if email:
            try:
                root_folder = folder_service.get_user_root_folder(email)
                is_in_hierarchy = folder_service._verify_folder_in_user_hierarchy(
                    ObjectId(folder_id), root_folder["_id"])
                
                if not is_in_hierarchy:
                    return APIRoute.error(
                        ErrorCodes.PERMISSION_DENIED,
                        "No tienes permiso para acceder a esta carpeta",
                        status_code=403
                    )
            except Exception as e:
                return APIRoute.error(
                    ErrorCodes.SERVER_ERROR,
                    f"Error al verificar jerarquía: {str(e)}",
                    status_code=500
                )
            
        # Obtener recursos de la carpeta (pasando email para respetar jerarquía)
        resources = resource_service.get_teacher_resources(folder["created_by"], folder_id, email=email)
            
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

@resources_bp.route('/folders/<folder_id>', methods=['PUT', 'OPTIONS'])
def update_folder_handler(folder_id):
    """
    Punto de entrada para actualizar una carpeta.
    Maneja directamente las solicitudes OPTIONS para evitar problemas de CORS.
    """
    if request.method == 'OPTIONS':
        return APIRoute.success({})
    
    # Para PUT, usar el handler con autenticación
    return update_folder(folder_id)

@APIRoute.standard(auth_required_flag=True, roles=[ROLES["TEACHER"]])
def update_folder(folder_id):
    """
    Actualiza una carpeta existente.
    Respeta la jerarquía de carpetas del usuario.
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
            
        # Obtener email para verificación de jerarquía
        email = request.json.get('email')
            
        # Actualizar carpeta (pasando email para respetar jerarquía)
        success, result = folder_service.update_folder(folder_id, updates, email=email)
        
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

@resources_bp.route('/folders/<folder_id>', methods=['DELETE', 'OPTIONS'])
def delete_folder_handler(folder_id):
    """
    Punto de entrada para eliminar una carpeta.
    Maneja directamente las solicitudes OPTIONS para evitar problemas de CORS.
    """
    if request.method == 'OPTIONS':
        return APIRoute.success({})
    
    # Para DELETE, usar el handler con autenticación
    return delete_folder(folder_id)

@APIRoute.standard(auth_required_flag=True, roles=[ROLES["TEACHER"]])
def delete_folder(folder_id):
    """
    Elimina una carpeta específica por su ID.
    Respeta la jerarquía de carpetas del usuario.
    """
    try:
        # Obtener email para verificación de jerarquía
        email = request.args.get('email')
        
        # Eliminar carpeta (pasando email para respetar jerarquía)
        success, result = folder_service.delete_folder(folder_id, email=email)
        
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

@resources_bp.route('/folders/tree', methods=['GET'])
@APIRoute.standard(auth_required_flag=True)
def get_folders_tree():
    """
    Obtiene el árbol de carpetas del usuario especificado.
    Requiere el parámetro email para identificar al usuario.
    """
    try:
        # Obtener email de la solicitud
        email = request.args.get('email')
        if not email:
            return APIRoute.error(
                ErrorCodes.MISSING_FIELDS,
                "Se requiere el email del usuario para obtener el árbol de carpetas",
                status_code=400
            )
            
        # Obtener árbol de carpetas - Esto debería encontrar la carpeta raíz existente
        # sin crear una nueva usando la lógica mejorada en get_user_root_folder
        try:
            folder_tree = folder_service.get_folder_tree(None, email=email)
            return APIRoute.success(folder_tree)
        except Exception as e:
            log_error = getattr(folder_service, 'log_error', print)
            log_error(f"Error al obtener árbol de carpetas: {str(e)}")
            return APIRoute.error(
                ErrorCodes.SERVER_ERROR,
                f"Error al obtener el árbol de carpetas: {str(e)}",
                status_code=500
            )
    except Exception as e:
        return APIRoute.error(
            ErrorCodes.SERVER_ERROR,
            str(e),
            status_code=500
        )

@resources_bp.route('', methods=['POST', 'OPTIONS'])
def create_resource_direct_handler():
    """
    Punto de entrada para crear un nuevo recurso directo.
    Maneja directamente las solicitudes OPTIONS para evitar problemas de CORS.
    """
    if request.method == 'OPTIONS':
        return APIRoute.success({})
    
    # Para POST, usar el handler con autenticación
    return create_resource_direct()

@APIRoute.standard(auth_required_flag=True, roles=[ROLES["TEACHER"]])
def create_resource_direct():
    """
    Endpoint directo para crear un nuevo recurso.
    Intenta usar get_or_create_external_resource para tipos externos (link, video) para evitar duplicados.
    Respeta la jerarquía de carpetas del usuario.
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
        
        # Asegurarse de que se proporciona email para respetar jerarquía
        email = request.json.get('email')
        created_by = request.json.get('created_by') # Necesario para get_or_create
        if not email:
            if created_by:
                user = get_db().users.find_one({"_id": ObjectId(created_by)})
                if user and "email" in user:
                    email = user.get("email")
                else:
                    return APIRoute.error(ErrorCodes.MISSING_FIELDS, "No se pudo determinar el email del creador", status_code=400)
            else:
                return APIRoute.error(ErrorCodes.MISSING_FIELDS, "Se requiere el email o created_by", status_code=400)
        
        resource_data = request.json.copy()
        resource_data["email"] = email # Asegurar que email esté para los servicios

        resource_type = resource_data.get("type", "link")
        is_external = resource_data.get("is_external", False) # Opcional, si el frontend lo indica
        # Decidir si usar get_or_create basado en tipo o flag
        use_get_or_create = is_external or resource_type in ["link", "video", "external_document"]

        if use_get_or_create:
            # Intentar obtener o crear recurso externo (evita duplicados por URL)
            success, result_id_or_msg, existed = resource_service.get_or_create_external_resource(resource_data)
            if not success:
                 return APIRoute.error(ErrorCodes.OPERATION_FAILED, result_id_or_msg, status_code=400)
            resource_id = result_id_or_msg
            message = "Recurso externo encontrado" if existed else "Recurso externo creado exitosamente"
            status_code = 200 if existed else 201
        else:
            # Crear recurso interno (no chequea duplicados por URL)
            success, result_id_or_msg = resource_service.create_resource(resource_data)
            if not success:
                 return APIRoute.error(ErrorCodes.CREATION_ERROR, result_id_or_msg, status_code=400)
            resource_id = result_id_or_msg
            message="Recurso creado exitosamente"
            status_code = 201
        
        # Obtener el recurso final (existente o nuevo)
        resource = resource_service.get_resource(resource_id)
        if not resource:
            # Esto no debería pasar si la creación/obtención fue exitosa, pero por seguridad
            return APIRoute.error(ErrorCodes.RESOURCE_NOT_FOUND, "No se pudo encontrar el recurso después de crearlo/obtenerlo", status_code=404)

        return APIRoute.success(
            resource, 
            message=message, 
            status_code=status_code
        )

    except Exception as e:
        log_error = getattr(resource_service, 'log_error', print)
        log_error(f"Error en create_resource_direct: {str(e)}")
        return APIRoute.error(
            ErrorCodes.SERVER_ERROR, 
            str(e), 
            status_code=500
        ) 