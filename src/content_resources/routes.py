from flask import request, jsonify
import logging
import os
from werkzeug.utils import secure_filename

from src.shared.standardization import APIBlueprint, APIRoute, ErrorCodes
from src.shared.constants import ROLES
from src.shared.utils import ensure_json_serializable
from .services import (
    PDFProcessingService,
    WebSearchService,
    DiagramService,
    SearchProviderService
)

# Crear blueprint
content_resources_bp = APIBlueprint('content_resources', __name__)

# Inicializar servicios
pdf_service = PDFProcessingService()
web_search_service = WebSearchService()
diagram_service = DiagramService()
provider_service = SearchProviderService()

# Rutas para procesamiento de PDFs
@content_resources_bp.route('/pdf/process', methods=['POST'])
@APIRoute.standard(auth_required_flag=True, roles=[ROLES["TEACHER"]])
def process_pdf():
    """Procesa un archivo PDF para extraer su contenido"""
    try:
        # Verificar si hay un archivo en la solicitud
        if 'file' not in request.files:
            return APIRoute.error(
                ErrorCodes.BAD_REQUEST,
                "No se proporcionó ningún archivo",
                status_code=400
            )
            
        pdf_file = request.files['file']
        if pdf_file.filename == '':
            return APIRoute.error(
                ErrorCodes.BAD_REQUEST,
                "No se seleccionó ningún archivo",
                status_code=400
            )
            
        # Verificar que sea un archivo PDF
        if not pdf_file.filename.lower().endswith('.pdf'):
            return APIRoute.error(
                ErrorCodes.BAD_REQUEST,
                "El archivo debe ser un PDF",
                status_code=400
            )
            
        # Obtener el título y metadatos adicionales
        title = request.form.get('title', pdf_file.filename)
        
        # Guardar el archivo temporalmente
        upload_folder = os.environ.get("UPLOAD_FOLDER", "uploads")
        os.makedirs(os.path.join(upload_folder, "pdfs"), exist_ok=True)
        
        filename = secure_filename(pdf_file.filename)
        temp_path = os.path.join(upload_folder, "pdfs", filename)
        pdf_file.save(temp_path)
        
        # Procesar el PDF
        success, result = pdf_service.process_pdf(
            file_path=temp_path,
            title=title,
            original_filename=filename,
            creator_id=request.user_id
        )
        
        if not success:
            # Eliminar el archivo temporal en caso de error
            if os.path.exists(temp_path):
                os.remove(temp_path)
                
            return APIRoute.error(
                ErrorCodes.BAD_REQUEST,
                result,
                status_code=400
            )
            
        return APIRoute.success(
            {"id": result},
            message="PDF procesado exitosamente",
            status_code=201
        )
    except Exception as e:
        logging.error(f"Error al procesar PDF: {str(e)}")
        return APIRoute.error(
            ErrorCodes.SERVER_ERROR,
            str(e),
            status_code=500
        )

@content_resources_bp.route('/pdf/<pdf_id>', methods=['GET'])
@APIRoute.standard(auth_required_flag=True)
def get_processed_pdf(pdf_id):
    """Obtiene un PDF procesado por su ID"""
    try:
        pdf = pdf_service.get_processed_pdf(pdf_id)
        
        if not pdf:
            return APIRoute.error(
                ErrorCodes.NOT_FOUND,
                "PDF procesado no encontrado",
                status_code=404
            )
            
        return APIRoute.success(data=pdf)
    except Exception as e:
        logging.error(f"Error al obtener PDF procesado: {str(e)}")
        return APIRoute.error(
            ErrorCodes.SERVER_ERROR,
            str(e),
            status_code=500
        )

@content_resources_bp.route('/pdf/<pdf_id>/extract', methods=['POST'])
@APIRoute.standard(auth_required_flag=True, roles=[ROLES["TEACHER"]], required_fields=['topic_id'])
def extract_pdf_for_topic(pdf_id):
    """Extrae contenido relevante de un PDF para un tema específico"""
    try:
        data = request.get_json()
        topic_id = data.get('topic_id')
        
        success, content = pdf_service.extract_pdf_for_topic(pdf_id, topic_id)
        
        if not success:
            return APIRoute.error(
                ErrorCodes.BAD_REQUEST,
                "No se pudo extraer contenido del PDF",
                status_code=400
            )
            
        return APIRoute.success(
            {"content": content},
            message="Contenido extraído exitosamente"
        )
    except Exception as e:
        logging.error(f"Error al extraer contenido de PDF: {str(e)}")
        return APIRoute.error(
            ErrorCodes.SERVER_ERROR,
            str(e),
            status_code=500
        )

@content_resources_bp.route('/pdf/<pdf_id>/summarize', methods=['POST'])
@APIRoute.standard(auth_required_flag=True, roles=[ROLES["TEACHER"]])
def summarize_pdf(pdf_id):
    """Genera un resumen del contenido de un PDF procesado"""
    try:
        # Verificar parámetros opcionales
        data = request.get_json() or {}
        max_length = data.get('max_length', 500)  # Longitud máxima del resumen en palabras
        focus_areas = data.get('focus_areas', [])  # Áreas específicas en las que enfocarse
        
        # Obtener el PDF procesado
        pdf = pdf_service.get_processed_pdf(pdf_id)
        
        if not pdf:
            return APIRoute.error(
                ErrorCodes.NOT_FOUND,
                "PDF procesado no encontrado",
                status_code=404
            )
            
        # Generar el resumen
        success, summary = pdf_service.generate_pdf_summary(pdf_id, max_length, focus_areas)
        
        if not success:
            return APIRoute.error(
                ErrorCodes.BAD_REQUEST,
                summary,  # Mensaje de error
                status_code=400
            )
            
        return APIRoute.success(
            {"summary": summary},
            message="Resumen generado exitosamente"
        )
    except Exception as e:
        logging.error(f"Error al resumir PDF: {str(e)}")
        return APIRoute.error(
            ErrorCodes.SERVER_ERROR,
            str(e),
            status_code=500
        )

# Rutas para búsqueda web
@content_resources_bp.route('/web-search', methods=['POST'])
@APIRoute.standard(auth_required_flag=True, required_fields=['query'])
def search_web():
    """Realiza una búsqueda en la web"""
    try:
        data = request.get_json()
        query = data.get('query')
        result_type = data.get('result_type')
        max_results = data.get('max_results', 10)
        topic_id = data.get('topic_id')
        
        results = web_search_service.search_web(
            query=query,
            result_type=result_type,
            max_results=max_results,
            topic_id=topic_id
        )
        
        return APIRoute.success(data=results)
    except Exception as e:
        logging.error(f"Error al buscar en la web: {str(e)}")
        return APIRoute.error(
            ErrorCodes.SERVER_ERROR,
            str(e),
            status_code=500
        )

@content_resources_bp.route('/web-search/result/<result_id>/save', methods=['POST'])
@APIRoute.standard(auth_required_flag=True)
def save_search_result(result_id):
    """Marca un resultado de búsqueda como guardado"""
    try:
        success, message = web_search_service.save_search_result(result_id)
        
        if not success:
            return APIRoute.error(
                ErrorCodes.BAD_REQUEST,
                message,
                status_code=400
            )
            
        return APIRoute.success(
            message="Resultado guardado exitosamente"
        )
    except Exception as e:
        logging.error(f"Error al guardar resultado de búsqueda: {str(e)}")
        return APIRoute.error(
            ErrorCodes.SERVER_ERROR,
            str(e),
            status_code=500
        )

@content_resources_bp.route('/search-providers', methods=['GET'])
@APIRoute.standard(auth_required_flag=True)
def list_search_providers():
    """Lista proveedores de búsqueda"""
    try:
        active_only = request.args.get('active_only', 'false').lower() == 'true'
        providers = provider_service.list_providers(active_only)
        return APIRoute.success(data=providers)
    except Exception as e:
        logging.error(f"Error al listar proveedores de búsqueda: {str(e)}")
        return APIRoute.error(
            ErrorCodes.SERVER_ERROR,
            str(e),
            status_code=500
        )

@content_resources_bp.route('/search-providers', methods=['POST'])
@APIRoute.standard(auth_required_flag=True, roles=[ROLES["INSTITUTE_ADMIN"]], required_fields=['name', 'provider_type', 'api_key'])
def create_search_provider():
    """Crea un nuevo proveedor de búsqueda"""
    try:
        data = request.get_json()
        success, result = provider_service.create_provider(data)
        
        if not success:
            return APIRoute.error(
                ErrorCodes.BAD_REQUEST,
                result,
                status_code=400
            )
            
        return APIRoute.success(
            {"id": result},
            message="Proveedor creado exitosamente",
            status_code=201
        )
    except Exception as e:
        logging.error(f"Error al crear proveedor de búsqueda: {str(e)}")
        return APIRoute.error(
            ErrorCodes.SERVER_ERROR,
            str(e),
            status_code=500
        )

@content_resources_bp.route('/search-providers/<provider_id>', methods=['PUT'])
@APIRoute.standard(auth_required_flag=True, roles=[ROLES["INSTITUTE_ADMIN"]])
def update_search_provider(provider_id):
    """Actualiza un proveedor de búsqueda existente"""
    try:
        data = request.get_json()
        success, message = provider_service.update_provider(provider_id, data)
        
        if not success:
            return APIRoute.error(
                ErrorCodes.BAD_REQUEST,
                message,
                status_code=400
            )
            
        return APIRoute.success(
            message="Proveedor actualizado exitosamente"
        )
    except Exception as e:
        logging.error(f"Error al actualizar proveedor de búsqueda: {str(e)}")
        return APIRoute.error(
            ErrorCodes.SERVER_ERROR,
            str(e),
            status_code=500
        )

@content_resources_bp.route('/search-providers/<provider_id>', methods=['DELETE'])
@APIRoute.standard(auth_required_flag=True, roles=[ROLES["INSTITUTE_ADMIN"]])
def delete_search_provider(provider_id):
    """Elimina un proveedor de búsqueda"""
    try:
        success, message = provider_service.delete_provider(provider_id)
        
        if not success:
            return APIRoute.error(
                ErrorCodes.BAD_REQUEST,
                message,
                status_code=400
            )
            
        return APIRoute.success(
            message="Proveedor eliminado exitosamente"
        )
    except Exception as e:
        logging.error(f"Error al eliminar proveedor de búsqueda: {str(e)}")
        return APIRoute.error(
            ErrorCodes.SERVER_ERROR,
            str(e),
            status_code=500
        )

@content_resources_bp.route('/search-providers/<provider_id>/test', methods=['GET'])
@APIRoute.standard(auth_required_flag=True, roles=[ROLES["INSTITUTE_ADMIN"]])
def test_search_provider(provider_id):
    """Prueba la conexión con un proveedor de búsqueda"""
    try:
        success, message, results = provider_service.test_provider(provider_id)
        
        if not success:
            return APIRoute.error(
                ErrorCodes.BAD_REQUEST,
                message,
                status_code=400
            )
            
        return APIRoute.success(
            data=results,
            message=message
        )
    except Exception as e:
        logging.error(f"Error al probar proveedor de búsqueda: {str(e)}")
        return APIRoute.error(
            ErrorCodes.SERVER_ERROR,
            str(e),
            status_code=500
        )

# Rutas para diagramas
@content_resources_bp.route('/diagram/templates', methods=['GET'])
@APIRoute.standard(auth_required_flag=True)
def list_diagram_templates():
    """Lista plantillas de diagramas disponibles"""
    try:
        template_type = request.args.get('type')
        templates = diagram_service.list_templates(template_type)
        return APIRoute.success(data=templates)
    except Exception as e:
        logging.error(f"Error al listar plantillas de diagramas: {str(e)}")
        return APIRoute.error(
            ErrorCodes.SERVER_ERROR,
            str(e),
            status_code=500
        )

@content_resources_bp.route('/diagram/templates', methods=['POST'])
@APIRoute.standard(auth_required_flag=True, roles=[ROLES["INSTITUTE_ADMIN"]], required_fields=['name', 'template_type', 'template_schema', 'sample_code'])
def create_diagram_template():
    """Crea una nueva plantilla de diagrama"""
    try:
        data = request.get_json()
        success, result = diagram_service.create_template(data)
        
        if not success:
            return APIRoute.error(
                ErrorCodes.BAD_REQUEST,
                result,
                status_code=400
            )
            
        return APIRoute.success(
            {"id": result},
            message="Plantilla creada exitosamente",
            status_code=201
        )
    except Exception as e:
        logging.error(f"Error al crear plantilla de diagrama: {str(e)}")
        return APIRoute.error(
            ErrorCodes.SERVER_ERROR,
            str(e),
            status_code=500
        )

@content_resources_bp.route('/diagram/generate', methods=['POST'])
@APIRoute.standard(auth_required_flag=True, roles=[ROLES["TEACHER"]], required_fields=['title', 'diagram_type', 'content'])
def generate_diagram():
    """Genera un nuevo diagrama"""
    try:
        data = request.get_json()
        
        # Añadir ID del creador
        if request.user_id:
            data['creator_id'] = request.user_id
            
        success, result = diagram_service.generate_diagram(data)
        
        if not success:
            return APIRoute.error(
                ErrorCodes.BAD_REQUEST,
                result,
                status_code=400
            )
            
        return APIRoute.success(
            {"id": result},
            message="Diagrama generado exitosamente",
            status_code=201
        )
    except Exception as e:
        logging.error(f"Error al generar diagrama: {str(e)}")
        return APIRoute.error(
            ErrorCodes.SERVER_ERROR,
            str(e),
            status_code=500
        )

@content_resources_bp.route('/diagram/<diagram_id>', methods=['GET'])
@APIRoute.standard(auth_required_flag=True)
def get_diagram(diagram_id):
    """Obtiene un diagrama por su ID"""
    try:
        diagram = diagram_service.get_diagram(diagram_id)
        
        if not diagram:
            return APIRoute.error(
                ErrorCodes.NOT_FOUND,
                "Diagrama no encontrado",
                status_code=404
            )
            
        return APIRoute.success(data=diagram)
    except Exception as e:
        logging.error(f"Error al obtener diagrama: {str(e)}")
        return APIRoute.error(
            ErrorCodes.SERVER_ERROR,
            str(e),
            status_code=500
        ) 