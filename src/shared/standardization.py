"""
Estandarización para la API de SapiensAI

Este módulo unifica todas las funcionalidades de estandarización para la API:
1. Estandarización de rutas (APIBlueprint, APIRoute)
2. Estandarización de servicios (BaseService)
3. Códigos de error estandarizados (ErrorCodes)

Propósito: Reducir la cantidad de archivos y proporcionar un punto único
de importación para toda la funcionalidad de estandarización.
"""

from functools import wraps
from flask import jsonify, Blueprint, request
from src.shared.decorators import handle_errors, auth_required, role_required, validate_json
from src.shared.exceptions import AppException
from src.shared.utils import ensure_json_serializable
from typing import List, Dict, Any, Union, Optional, Callable, Tuple
from bson.objectid import ObjectId
from src.shared.database import get_db

#-------------------------------------------------------
# ESTANDARIZACIÓN DE RUTAS
#-------------------------------------------------------

class APIBlueprint(Blueprint):
    """
    Extensión de Flask Blueprint para definir rutas estandarizadas.
    
    Proporciona una base consistente para definir rutas en toda la aplicación.
    """
    
    def __init__(self, name, import_name, **kwargs):
        """Inicializa un nuevo APIBlueprint"""
        super().__init__(name, import_name, **kwargs)


class APIRoute:
    """
    Clase de utilidad para estandarizar rutas y respuestas.
    
    Proporciona decoradores y métodos para crear respuestas estandarizadas.
    """
    
    @staticmethod
    def standard(auth_required_flag: bool = False, 
                 roles: List[str] = None, 
                 required_fields: List[str] = None,
                 schema: Dict = None):
        """
        Decorador compuesto que aplica los decoradores estándar de la aplicación.
        
        Args:
            auth_required_flag: Si es True, requiere autenticación JWT
            roles: Lista de roles permitidos para acceder a la ruta
            required_fields: Lista de campos requeridos en el cuerpo JSON
            schema: Esquema de validación para el cuerpo JSON
            
        Returns:
            Función decoradora compuesta
        """
        decorators = [handle_errors]
        
        # Agregar validación de JSON si se especifican campos o esquema
        if required_fields or schema:
            decorators.append(validate_json(required_fields, schema))
        
        # Agregar autenticación si se requiere
        if auth_required_flag:
            decorators.append(auth_required)
            
            # Agregar validación de roles si se especifican
            if roles:
                decorators.append(role_required(roles))
        
        def decorator(f):
            # Aplicar todos los decoradores en orden inverso
            for decorator in reversed(decorators):
                f = decorator(f)
            return f
        
        return decorator
    
    @staticmethod
    def success(data: Any = None, message: str = None, status_code: int = 200) -> tuple:
        """
        Crea una respuesta exitosa estandarizada.
        
        Args:
            data: Datos a incluir en la respuesta (opcional)
            message: Mensaje descriptivo (opcional)
            status_code: Código de estado HTTP (por defecto 200)
            
        Returns:
            Tupla (response, status_code) para retornar desde una ruta Flask
        """
        response = {"success": True}
        
        if data is not None:
            response["data"] = ensure_json_serializable(data)
            
        if message:
            response["message"] = message
            
        return jsonify(response), status_code
    
    @staticmethod
    def error(error_code: str, message: str, details: Dict = None, status_code: int = 400) -> tuple:
        """
        Crea una respuesta de error estandarizada.
        
        Args:
            error_code: Código de error único (ej. "USUARIO_NO_ENCONTRADO")
            message: Mensaje descriptivo del error
            details: Detalles adicionales del error (opcional)
            status_code: Código de estado HTTP (por defecto 400)
            
        Returns:
            Tupla (response, status_code) para retornar desde una ruta Flask
        """
        response = {
            "success": False,
            "error": error_code,
            "message": message
        }
        
        if details:
            response["details"] = details
            
        return jsonify(response), status_code
    
    @staticmethod
    def from_app_exception(exception: AppException) -> tuple:
        """
        Crea una respuesta de error a partir de una AppException.
        
        Args:
            exception: Instancia de AppException
            
        Returns:
            Tupla (response, status_code) para retornar desde una ruta Flask
        """
        response = {
            "success": False,
            "error": exception.__class__.__name__,
            "message": exception.message
        }
        
        if exception.details:
            response["details"] = exception.details
            
        return jsonify(response), exception.code

#-------------------------------------------------------
# ESTANDARIZACIÓN DE SERVICIOS
#-------------------------------------------------------

class BaseService:
    """
    Clase base para servicios que provee funcionalidad CRUD estándar.
    
    Proporciona operaciones básicas para interactuar con la base de datos MongoDB.
    """
    
    def __init__(self, collection_name: str):
        """
        Inicializa un nuevo servicio base.
        
        Args:
            collection_name: Nombre de la colección de MongoDB que utilizará este servicio
        """
        self.db = get_db()
        self.collection = self.db[collection_name]
        self.collection_name = collection_name
    
    def get_by_id(self, id: str) -> Dict:
        """
        Obtiene un documento por su ID.
        
        Args:
            id: ID del documento a obtener
            
        Returns:
            Documento encontrado o None si no existe
            
        Raises:
            AppException: Si el ID no es válido
        """
        try:
            object_id = ObjectId(id)
            result = self.collection.find_one({"_id": object_id})
            return ensure_json_serializable(result) if result else None
        except Exception as e:
            raise AppException(f"ID inválido: {id}", AppException.BAD_REQUEST)
    
    def list_all(self, filter: Dict = None, limit: int = 0, skip: int = 0) -> List[Dict]:
        """
        Lista todos los documentos que coinciden con el filtro.
        
        Args:
            filter: Filtro para aplicar a la consulta
            limit: Número máximo de documentos a retornar (0 = sin límite)
            skip: Número de documentos a omitir
            
        Returns:
            Lista de documentos
        """
        filter = filter or {}
        cursor = self.collection.find(filter).skip(skip)
        
        if limit > 0:
            cursor = cursor.limit(limit)
            
        return ensure_json_serializable(list(cursor))
    
    def create(self, data: Dict) -> str:
        """
        Crea un nuevo documento.
        
        Args:
            data: Datos del documento a crear
            
        Returns:
            ID del documento creado
            
        Raises:
            AppException: Si ocurre un error durante la creación
        """
        try:
            result = self.collection.insert_one(data)
            return str(result.inserted_id)
        except Exception as e:
            raise AppException(f"Error al crear documento: {str(e)}", AppException.BAD_REQUEST)
    
    def update(self, id: str, data: Dict, replace: bool = False) -> bool:
        """
        Actualiza un documento existente.
        
        Args:
            id: ID del documento a actualizar
            data: Datos a actualizar
            replace: Si es True, reemplaza todo el documento; si es False, solo actualiza los campos proporcionados
            
        Returns:
            True si se actualizó correctamente, False si no se encontró el documento
            
        Raises:
            AppException: Si el ID no es válido o si ocurre un error durante la actualización
        """
        try:
            object_id = ObjectId(id)
            
            if replace:
                # Asegurarse de no sobrescribir el _id
                if '_id' in data:
                    del data['_id']
                result = self.collection.replace_one({"_id": object_id}, data)
            else:
                result = self.collection.update_one(
                    {"_id": object_id},
                    {"$set": data}
                )
                
            return result.modified_count > 0
        except Exception as e:
            raise AppException(f"Error al actualizar documento: {str(e)}", AppException.BAD_REQUEST)
    
    def delete(self, id: str) -> bool:
        """
        Elimina un documento.
        
        Args:
            id: ID del documento a eliminar
            
        Returns:
            True si se eliminó correctamente, False si no se encontró el documento
            
        Raises:
            AppException: Si el ID no es válido
        """
        try:
            object_id = ObjectId(id)
            result = self.collection.delete_one({"_id": object_id})
            return result.deleted_count > 0
        except Exception as e:
            raise AppException(f"Error al eliminar documento: {str(e)}", AppException.BAD_REQUEST)
    
    def count(self, filter: Dict = None) -> int:
        """
        Cuenta documentos que coinciden con el filtro.
        
        Args:
            filter: Filtro para aplicar a la consulta
            
        Returns:
            Número de documentos
        """
        filter = filter or {}
        return self.collection.count_documents(filter)

#-------------------------------------------------------
# CÓDIGOS DE ERROR ESTANDARIZADOS
#-------------------------------------------------------

class ErrorCodes:
    """
    Códigos de error estandarizados para toda la aplicación.
    
    Estos códigos deben usarse en las respuestas de error para mantener la consistencia.
    """
    
    # Errores de recursos
    RESOURCE_NOT_FOUND = "RECURSO_NO_ENCONTRADO"    # 404 - Recurso solicitado no encontrado
    RESOURCE_ALREADY_EXISTS = "RECURSO_YA_EXISTE"   # 409 - Conflicto, el recurso ya existe
    RESOURCE_DELETED = "RECURSO_ELIMINADO"          # 410 - Recurso eliminado permanentemente
    
    # Errores de validación
    INVALID_DATA = "DATOS_INVALIDOS"                # 400 - Datos no válidos (genérico)
    MISSING_FIELDS = "CAMPOS_FALTANTES"             # 400 - Faltan campos requeridos
    VALIDATION_ERROR = "ERROR_VALIDACION"           # 400 - Error en validación de datos
    INVALID_FORMAT = "FORMATO_INVALIDO"             # 400 - Formato de datos incorrecto
    INVALID_ID = "ID_INVALIDO"                      # 400 - ID con formato incorrecto
    
    # Errores de autenticación y autorización
    AUTHENTICATION_ERROR = "ERROR_AUTENTICACION"    # 401 - Error de autenticación
    INVALID_TOKEN = "TOKEN_INVALIDO"                # 401 - Token JWT inválido o expirado
    PERMISSION_DENIED = "PERMISO_DENEGADO"          # 403 - Sin permisos para la operación
    ACCESS_DENIED = "ACCESO_DENEGADO"               # 403 - Acceso denegado al recurso
    
    # Errores de operaciones
    OPERATION_FAILED = "OPERACION_FALLIDA"          # 400 - La operación no pudo completarse
    DATABASE_ERROR = "ERROR_BASE_DATOS"             # 500 - Error al interactuar con la BD
    
    # Errores de dominio específico
    USER_NOT_FOUND = "USUARIO_NO_ENCONTRADO"        # 404 - Usuario no encontrado
    INSTITUTE_NOT_FOUND = "INSTITUTO_NO_ENCONTRADO" # 404 - Instituto no encontrado
    CLASS_NOT_FOUND = "CLASE_NO_ENCONTRADA"         # 404 - Clase no encontrada
    
    # Errores de registro y usuarios
    REGISTRATION_ERROR = "ERROR_REGISTRO"           # 400 - Error al registrar usuario
    EMAIL_IN_USE = "EMAIL_EN_USO"                   # 409 - Email ya registrado
    
    # Errores de servidor
    SERVER_ERROR = "ERROR_SERVIDOR"                 # 500 - Error interno del servidor 