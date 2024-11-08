from PyPDF2 import PdfReader
import pandas as pd
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
    df = pd.read_excel(file_path)
    
    # Implementar lógica de extracción específica
    return {
        'name': df.iloc[0]['nombre_plan'],
        'description': df.iloc[0]['descripcion'],
        'modules': []  # Implementar extracción de módulos
    }

def _upload_to_storage(file_path):
    """Sube el archivo a almacenamiento permanente"""
    # Implementar lógica de subida a almacenamiento (S3, etc.)
    return f"https://storage.example.com/documents/{os.path.basename(file_path)}" 