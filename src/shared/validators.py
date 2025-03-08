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

def is_valid_object_id(id_str: str) -> bool:
    """
    Valida si un string es un ObjectId válido de MongoDB.
    
    Args:
        id_str: String a validar
        
    Returns:
        bool: True si es un ObjectId válido, False en caso contrario
    """
    try:
        ObjectId(id_str)
        return True
    except:
        return False

def validate_object_id(id_str: str) -> None:
    """
    Valida un ObjectId y lanza una excepción si no es válido.
    
    Args:
        id_str: String a validar
        
    Raises:
        AppException: Si el ID no es un ObjectId válido
    """
    if not is_valid_object_id(id_str):
        raise AppException(f"ID inválido: {id_str}", AppException.BAD_REQUEST)

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
        
        # Validar longitud mínima/máxima para cadenas
        if isinstance(value, str):
            if 'minLength' in rules and len(value) < rules['minLength']:
                errors[field] = f"Debe tener al menos {rules['minLength']} caracteres"
            if 'maxLength' in rules and len(value) > rules['maxLength']:
                errors[field] = f"Debe tener como máximo {rules['maxLength']} caracteres"
        
        # Validar valores mínimos/máximos para números
        if isinstance(value, (int, float)):
            if 'minimum' in rules and value < rules['minimum']:
                errors[field] = f"Debe ser al menos {rules['minimum']}"
            if 'maximum' in rules and value > rules['maximum']:
                errors[field] = f"Debe ser como máximo {rules['maximum']}"
        
        # Validar enumeración (valores permitidos)
        if 'enum' in rules and value not in rules['enum']:
            enum_values = ', '.join(str(v) for v in rules['enum'])
            errors[field] = f"Debe ser uno de los siguientes valores: {enum_values}"
    
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