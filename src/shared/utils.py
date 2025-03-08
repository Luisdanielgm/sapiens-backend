"""
Utilidades generales para toda la aplicación. 

IMPORTANTE: Para decoradores como handle_errors, auth_required, role_required y validate_json,
importar desde src.shared.decorators, NO desde este archivo.

Ejemplo:
    from src.shared.decorators import handle_errors, validate_json
    
Este archivo solo contiene funciones de utilidad generales.
"""

from functools import wraps
from flask import jsonify, request, current_app
from datetime import datetime, timedelta
import jwt
import os
from typing import List, Any, Callable
from bson import ObjectId
import json
from flask_jwt_extended import create_access_token, decode_token

# Reemplazar la importación circular y la redeclaración
__all__ = ['parse_date', 'generate_token', 'verify_token', 
           'serialize_object_id', 'ensure_json_serializable']

def parse_date(date_string: str) -> str:
    """Parsea diferentes formatos de fecha a formato estándar"""
    formats_to_try = [
        "%Y-%m-%d",
        "%d/%m/%Y",
        "%Y/%m/%d",
        "%a, %d %b %Y %H:%M:%S %Z"
    ]
    
    for format_str in formats_to_try:
        try:
            date_obj = datetime.strptime(date_string, format_str)
            return date_obj.strftime("%Y-%m-%d")
        except ValueError:
            continue
    return None

def generate_token(user_id: str, email: str) -> str:
    """
    Genera un token JWT
    
    DEPRECATED: Usar flask_jwt_extended en su lugar
    """
    # Usar flask_jwt_extended para generar el token de forma consistente
    identity = user_id
    additional_claims = {"email": email}
    return create_access_token(identity=identity, additional_claims=additional_claims)

def verify_token(token: str) -> dict:
    """
    Verifica y decodifica un token JWT
    
    DEPRECATED: Usar flask_jwt_extended en su lugar
    """
    try:
        # Usar flask_jwt_extended para verificar el token
        return decode_token(token)
    except Exception as e:
        raise Exception(f"Error al verificar token: {str(e)}")

def serialize_object_id(obj: dict) -> dict:
    """Convierte ObjectId a string en un diccionario"""
    if isinstance(obj, dict):
        return {k: str(v) if isinstance(v, ObjectId) else v 
                for k, v in obj.items()}
    return obj

# Función para convertir ObjectId a string en un objeto o lista de objetos
def ensure_json_serializable(data):
    """Convierte todos los ObjectId a string para garantizar que el objeto sea JSON serializable"""
    if isinstance(data, list):
        return [ensure_json_serializable(item) for item in data]
    elif isinstance(data, dict):
        return {key: ensure_json_serializable(value) for key, value in data.items()}
    elif isinstance(data, ObjectId):
        return str(data)
    else:
        return data