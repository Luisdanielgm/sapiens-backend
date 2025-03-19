"""
Funciones de validación para datos de la aplicación.

Este módulo contiene funciones para validar datos contra esquemas predefinidos,
validar IDs de MongoDB y realizar otras validaciones comunes.

Ejemplos de uso:
    # Validar datos contra un esquema
    schema = {
        'name': {'type': 'string', 'required': True, 'minLength': 3},
        'age': {'type': 'integer', 'minimum': 18}
    }
    is_valid, errors = validate_schema(data, schema)
    
    # Validar un ObjectId de MongoDB
    if not is_valid_object_id(id_str):
        raise AppException("ID inválido", AppException.BAD_REQUEST)
"""

from bson.objectid import ObjectId
from src.shared.exceptions import AppException
from src.shared.logging import log_error
from src.shared.constants import RESOURCE_TYPES

def is_valid_object_id(id_str: str) -> bool:
    """
    Valida si un string es un ObjectId válido de MongoDB.
    
    Args:
        id_str: String a validar
        
    Returns:
        bool: True si es un ObjectId válido, False en caso contrario
    """
    if id_str is None:
        return False
        
    try:
        ObjectId(id_str)
        return True
    except Exception:
        return False

def validate_object_id(id_str: str, entity_name: str = "objeto") -> None:
    """
    Valida un ObjectId y lanza una excepción si no es válido.
    
    Args:
        id_str: String a validar
        entity_name: Nombre de la entidad para personalizar el mensaje de error
        
    Raises:
        AppException: Si el ID no es un ObjectId válido
    """
    if not id_str:
        log_error(f"ID no proporcionado para {entity_name}")
        raise AppException(f"ID de {entity_name} no proporcionado", AppException.BAD_REQUEST)
        
    if not is_valid_object_id(id_str):
        log_error(f"ID inválido: {id_str} para {entity_name}")
        raise AppException(f"ID de {entity_name} inválido: {id_str}", AppException.BAD_REQUEST)

def validate_schema(data, schema):
    """
    Valida un objeto de datos contra un esquema
    
    Args:
        data (dict): Los datos a validar
        schema (dict): El esquema con las reglas de validación
        
    Returns:
        tuple: (is_valid, errors) donde is_valid es un booleano y errors es un dict con los errores
    """
    errors = {}
    
    # Validar cada campo según el esquema
    for field, rules in schema.items():
        # Si el campo es requerido y no está presente
        if rules.get('required', False) and field not in data:
            errors[field] = "Campo requerido"
            continue
            
        # Si el campo no está presente (y no es requerido), continuar
        if field not in data:
            continue
            
        value = data[field]
        
        # Validar tipo
        if 'type' in rules:
            expected_type = rules['type']
            
            # Validación de tipos básicos
            if expected_type == 'string' and not isinstance(value, str):
                errors[field] = "Debe ser una cadena de texto"
            elif expected_type == 'number' and not isinstance(value, (int, float)):
                errors[field] = "Debe ser un número"
            elif expected_type == 'integer' and not isinstance(value, int):
                errors[field] = "Debe ser un número entero"
            elif expected_type == 'boolean' and not isinstance(value, bool):
                errors[field] = "Debe ser un valor booleano"
            elif expected_type == 'array' and not isinstance(value, list):
                errors[field] = "Debe ser una lista"
            elif expected_type == 'object' and not isinstance(value, dict):
                errors[field] = "Debe ser un objeto"
                
        # Validar longitud mínima (para strings y arrays)
        if 'minLength' in rules and isinstance(value, (str, list)):
            min_length = rules['minLength']
            if len(value) < min_length:
                errors[field] = f"Debe tener al menos {min_length} caracteres"
                
        # Validar longitud máxima (para strings y arrays)
        if 'maxLength' in rules and isinstance(value, (str, list)):
            max_length = rules['maxLength']
            if len(value) > max_length:
                errors[field] = f"Debe tener como máximo {max_length} caracteres"
                
        # Validar mínimo (para números)
        if 'minimum' in rules and isinstance(value, (int, float)):
            minimum = rules['minimum']
            if value < minimum:
                errors[field] = f"Debe ser mayor o igual a {minimum}"
                
        # Validar máximo (para números)
        if 'maximum' in rules and isinstance(value, (int, float)):
            maximum = rules['maximum']
            if value > maximum:
                errors[field] = f"Debe ser menor o igual a {maximum}"
                
        # Validar patrón (para strings)
        if 'pattern' in rules and isinstance(value, str):
            import re
            pattern = rules['pattern']
            if not re.match(pattern, value):
                errors[field] = f"No cumple con el formato requerido"
                
        # Validar enum (valores permitidos)
        if 'enum' in rules:
            enum = rules['enum']
            if value not in enum:
                errors[field] = f"Valor no permitido. Opciones válidas: {', '.join(map(str, enum))}"
    
    return len(errors) == 0, errors

def validate_email(email: str) -> bool:
    """
    Valida si un string tiene formato de email.
    
    Args:
        email: String a validar
        
    Returns:
        bool: True si tiene formato de email, False en caso contrario
    """
    import re
    # Patrón básico para validar emails
    pattern = r'^[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}$'
    return re.match(pattern, email) is not None 

# Esquemas de validación para recursos
resource_schema = {
    "type": "object",
    "required": ["name", "type", "url", "created_by"],
    "properties": {
        "name": {
            "type": "string",
            "minLength": 1,
            "maxLength": 100
        },
        "type": {
            "type": "string",
            "enum": list(RESOURCE_TYPES.values())
        },
        "url": {
            "type": "string",
            "format": "uri",
            "minLength": 1
        },
        "description": {
            "type": "string",
            "maxLength": 1000
        },
        "created_by": {
            "type": "string",
            "pattern": "^[0-9a-fA-F]{24}$"
        },
        "folder_id": {
            "type": ["string", "null"],
            "pattern": "^[0-9a-fA-F]{24}$"
        },
        "tags": {
            "type": "array",
            "items": {
                "type": "string",
                "minLength": 1,
                "maxLength": 50
            }
        },
        "size": {
            "type": ["integer", "null"],
            "minimum": 0
        },
        "duration": {
            "type": ["integer", "null"],
            "minimum": 0
        },
        "thumbnail_url": {
            "type": ["string", "null"],
            "format": "uri"
        },
        "is_external": {
            "type": "boolean"
        },
        "metadata": {
            "type": "object"
        }
    }
}

# Esquema de validación para carpetas de recursos
resource_folder_schema = {
    "type": "object",
    "required": ["name", "created_by"],
    "properties": {
        "name": {
            "type": "string",
            "minLength": 1,
            "maxLength": 100
        },
        "description": {
            "type": ["string", "null"],
            "maxLength": 500
        },
        "created_by": {
            "type": "string",
            "pattern": "^[0-9a-fA-F]{24}$"
        },
        "parent_id": {
            "type": ["string", "null"],
            "pattern": "^[0-9a-fA-F]{24}$"
        }
    }
} 