from flask import request
import logging

from src.shared.standardization import APIBlueprint, APIRoute, ErrorCodes
from src.shared.constants import ROLES
from src.shared.utils import ensure_json_serializable
from src.student_individual_content.services import StudentIndividualContentService

student_individual_content_bp = APIBlueprint('student_individual_content', __name__)
content_service = StudentIndividualContentService()


@student_individual_content_bp.route('/', methods=['POST'])
@APIRoute.standard(
    auth_required_flag=True,
    roles=[ROLES["STUDENT"]],
    required_fields=['class_id', 'student_id', 'title', 'content']
)
def create_student_content():
    """
    Crea un nuevo contenido individual para un estudiante.
    
    Body:
        class_id: ID de la clase
        student_id: ID del estudiante
        title: Título del contenido
        content: Contenido en sí
        content_type: (opcional) Tipo de contenido (text, code, multimedia, etc.)
        tags: (opcional) Etiquetas para categorizar el contenido
        metadata: (opcional) Metadatos adicionales
    """
    try:
        data = request.get_json()
        
        success, result = content_service.create_content(data)
        
        if success:
            return APIRoute.success(
                data={"content_id": result},
                message="Contenido creado exitosamente",
                status_code=201
            )
        return APIRoute.error(
            ErrorCodes.CREATION_ERROR,
            result,
            status_code=400
        )
    except Exception as e:
        logging.error(str(e))
        return APIRoute.error(
            ErrorCodes.SERVER_ERROR,
            str(e),
            status_code=500
        )

@student_individual_content_bp.route('/<content_id>', methods=['PUT'])
@APIRoute.standard(
    auth_required_flag=True,
    roles=[ROLES["STUDENT"]]
)
def update_student_content(content_id):
    """
    Actualiza un contenido individual existente.
    
    Params:
        content_id: ID del contenido a actualizar
        
    Body:
        title: (opcional) Nuevo título
        content: (opcional) Nuevo contenido
        content_type: (opcional) Nuevo tipo de contenido
        tags: (opcional) Nuevas etiquetas
        metadata: (opcional) Nuevos metadatos
    """
    try:
        data = request.get_json()
        
        success, message = content_service.update_content(content_id, data)
        
        if success:
            return APIRoute.success(message=message)
        return APIRoute.error(
            ErrorCodes.UPDATE_ERROR,
            message,
            status_code=400
        )
    except Exception as e:
        logging.error(str(e))
        return APIRoute.error(
            ErrorCodes.SERVER_ERROR,
            str(e),
            status_code=500
        )

@student_individual_content_bp.route('/<content_id>', methods=['GET'])
@APIRoute.standard(auth_required_flag=True)
def get_student_content_by_id(content_id):
    """
    Obtiene un contenido individual específico.
    
    Params:
        content_id: ID del contenido a obtener
    """
    try:
        content = content_service.get_content(content_id)
        
        if content:
            return APIRoute.success(data={"content": content})
        return APIRoute.error(
            ErrorCodes.NOT_FOUND,
            "Contenido no encontrado",
            status_code=404
        )
    except Exception as e:
        logging.error(str(e))
        return APIRoute.error(
            ErrorCodes.SERVER_ERROR,
            str(e),
            status_code=500
        )

@student_individual_content_bp.route('/student/<student_id>', methods=['GET'])
@APIRoute.standard(auth_required_flag=True)
def get_student_all_content(student_id):
    """
    Obtiene todo el contenido de un estudiante, opcionalmente filtrado por clase.
    
    Params:
        student_id: ID del estudiante
        
    Query Params:
        class_id: (opcional) ID de la clase para filtrar
    """
    try:
        class_id = request.args.get('class_id')
        contents = content_service.get_student_content(student_id, class_id)
        
        return APIRoute.success(data={"contents": contents})
    except Exception as e:
        logging.error(str(e))
        return APIRoute.error(
            ErrorCodes.SERVER_ERROR,
            str(e),
            status_code=500
        )

@student_individual_content_bp.route('/<content_id>', methods=['DELETE'])
@APIRoute.standard(
    auth_required_flag=True,
    roles=[ROLES["STUDENT"], ROLES["TEACHER"]]
)
def delete_student_content(content_id):
    """
    Elimina un contenido individual.
    
    Params:
        content_id: ID del contenido a eliminar
    """
    try:
        success, message = content_service.delete_content(content_id)
        
        if success:
            return APIRoute.success(message=message)
        return APIRoute.error(
            ErrorCodes.DELETE_ERROR,
            message,
            status_code=400
        )
    except Exception as e:
        logging.error(str(e))
        return APIRoute.error(
            ErrorCodes.SERVER_ERROR,
            str(e),
            status_code=500
        )
