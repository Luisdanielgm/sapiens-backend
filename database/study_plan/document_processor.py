from PyPDF2 import PdfReader
from openpyxl import load_workbook
import os
from werkzeug.utils import secure_filename

def process_uploaded_document(file):
    """
    Procesa un archivo subido (PDF o Excel) y extrae la información estructurada.
    """
    filename = secure_filename(file.filename)
    file_ext = os.path.splitext(filename)[1].lower()
    
    temp_path = f"temp/{filename}"
    file.save(temp_path)
    
    try:
        if file_ext == '.pdf':
            data = _process_pdf(temp_path)
        elif file_ext in ['.xlsx', '.xls']:
            data = _process_excel(temp_path)
        else:
            raise ValueError("Formato de archivo no soportado. Use PDF o Excel.")
            
        document_url = _upload_to_storage(temp_path)
        data['document_url'] = document_url
        
        return data
        
    finally:
        if os.path.exists(temp_path):
            os.remove(temp_path)

def _process_pdf(file_path):
    """Procesa archivo PDF y extrae información estructurada"""
    reader = PdfReader(file_path)
    text = ""
    for page in reader.pages:
        text += page.extract_text()
    
    # Implementar lógica de extracción específica
    return {
        'name': 'Plan extraído de PDF',
        'description': 'Descripción extraída del PDF',
        'modules': []  # Implementar extracción de módulos
    }

def _process_excel(file_path):
    """Procesa archivo Excel y extrae información estructurada"""
    wb = load_workbook(file_path, read_only=True)
    sheet = wb.active
    
    # Obtener los encabezados (primera fila)
    headers = [cell.value for cell in next(sheet.rows)]
    
    # Convertir filas a diccionarios
    rows = []
    for row in sheet.rows:
        row_dict = {}
        for header, cell in zip(headers, row):
            row_dict[header] = cell.value
        rows.append(row_dict)
    
    if not rows:
        return {
            'name': '',
            'description': '',
            'modules': []
        }
    
    # Extraer información del plan
    return {
        'name': rows[0].get('nombre_plan', ''),
        'description': rows[0].get('descripcion', ''),
        'modules': [
            {
                'name': row.get('nombre_modulo', ''),
                'start_date': str(row.get('fecha_inicio', '')),
                'end_date': str(row.get('fecha_fin', '')),
                'objectives': row.get('objetivos', '').split(',') if row.get('objetivos') else [],
                'topics': _get_topics_from_excel(rows, row.get('id_modulo'))
            }
            for row in rows
        ]
    }

def _get_topics_from_excel(rows, module_id):
    """Extrae los temas relacionados a un módulo del Excel"""
    # Filtrar temas por module_id
    topics = []
    for row in rows:
        if row.get('id_modulo') == module_id:
            topics.append({
                'name': row.get('nombre_tema', 'Tema desde Excel'),
                'description': row.get('descripcion_tema', 'Descripción del tema'),
                'date_range': f"{row.get('fecha_inicio_tema', '2024-01-01')}/{row.get('fecha_fin_tema', '2024-01-15')}",
                'class_schedule': row.get('horario_clase', 'Lunes y Miércoles 10:00-12:00')
            })
    return topics

def _upload_to_storage(file_path):
    """Sube el archivo a almacenamiento permanente"""
    # Implementar lógica de subida a almacenamiento (S3, etc.)
    return f"https://storage.example.com/documents/{os.path.basename(file_path)}" 