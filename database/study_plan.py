from bson import ObjectId
from datetime import datetime
from database.mongodb import get_db
from PyPDF2 import PdfReader
import pandas as pd
import os
from werkzeug.utils import secure_filename

def create_study_plan(classroom_id, name, description, document_url):
    db = get_db()
    study_plan = {
        "classroom_id": ObjectId(classroom_id),
        "name": name,
        "description": description,
        "document_url": document_url,
        "created_at": datetime.utcnow(),
        "updated_at": datetime.utcnow()
    }
    result = db.study_plans.insert_one(study_plan)
    return result.inserted_id

def create_module(study_plan_id, name, start_date, end_date, objectives):
    db = get_db()
    module = {
        "study_plan_id": ObjectId(study_plan_id),
        "name": name,
        "start_date": start_date,
        "end_date": end_date,
        "objectives": objectives,
        "created_at": datetime.utcnow()
    }
    result = db.modules.insert_one(module)
    return result.inserted_id

def create_topic(module_id, name, description, date_range, class_schedule):
    db = get_db()
    topic = {
        "module_id": ObjectId(module_id),
        "name": name,
        "description": description,
        "date_range": date_range,
        "class_schedule": class_schedule,
        "created_at": datetime.utcnow()
    }
    result = db.topics.insert_one(topic)
    return result.inserted_id

def create_evaluation_plan(classroom_ids, document_url):
    db = get_db()
    evaluation_plan = {
        "classroom_ids": [ObjectId(id) for id in classroom_ids],
        "document_url": document_url,
        "created_at": datetime.utcnow(),
        "updated_at": datetime.utcnow()
    }
    result = db.evaluation_plans.insert_one(evaluation_plan)
    return result.inserted_id

def create_evaluation(evaluation_plan_id, module_id, topic_ids, name, description, methodology, weight, date):
    db = get_db()
    evaluation = {
        "evaluation_plan_id": ObjectId(evaluation_plan_id),
        "module_id": ObjectId(module_id),
        "topic_ids": [ObjectId(id) for id in topic_ids],
        "name": name,
        "description": description,
        "methodology": methodology,
        "weight": weight,
        "date": date,
        "created_at": datetime.utcnow()
    }
    result = db.evaluations.insert_one(evaluation)
    return result.inserted_id

# Funciones GET
def get_study_plan(study_plan_id):
    db = get_db()
    return db.study_plans.find_one({"_id": ObjectId(study_plan_id)})

def get_modules(study_plan_id):
    db = get_db()
    return list(db.modules.find({"study_plan_id": ObjectId(study_plan_id)}))

def get_topics(module_id):
    db = get_db()
    return list(db.topics.find({"module_id": ObjectId(module_id)}))

def get_evaluation_plan(evaluation_plan_id):
    db = get_db()
    return db.evaluation_plans.find_one({"_id": ObjectId(evaluation_plan_id)})

def get_evaluations(evaluation_plan_id):
    db = get_db()
    return list(db.evaluations.find({"evaluation_plan_id": ObjectId(evaluation_plan_id)}))

# Funciones UPDATE
def update_study_plan(study_plan_id, updates):
    db = get_db()
    updates["updated_at"] = datetime.utcnow()
    result = db.study_plans.update_one(
        {"_id": ObjectId(study_plan_id)},
        {"$set": updates}
    )
    return result.modified_count > 0

def update_module(module_id, updates):
    db = get_db()
    result = db.modules.update_one(
        {"_id": ObjectId(module_id)},
        {"$set": updates}
    )
    return result.modified_count > 0

def update_topic(topic_id, updates):
    db = get_db()
    result = db.topics.update_one(
        {"_id": ObjectId(topic_id)},
        {"$set": updates}
    )
    return result.modified_count > 0

def update_evaluation_plan(evaluation_plan_id, updates):
    db = get_db()
    updates["updated_at"] = datetime.utcnow()
    result = db.evaluation_plans.update_one(
        {"_id": ObjectId(evaluation_plan_id)},
        {"$set": updates}
    )
    return result.modified_count > 0

def update_evaluation(evaluation_id, updates):
    db = get_db()
    result = db.evaluations.update_one(
        {"_id": ObjectId(evaluation_id)},
        {"$set": updates}
    )
    return result.modified_count > 0

# Funciones DELETE
def delete_study_plan(study_plan_id):
    db = get_db()
    result = db.study_plans.delete_one({"_id": ObjectId(study_plan_id)})
    return result.deleted_count > 0

def delete_module(module_id):
    db = get_db()
    result = db.modules.delete_one({"_id": ObjectId(module_id)})
    return result.deleted_count > 0

def delete_topic(topic_id):
    db = get_db()
    result = db.topics.delete_one({"_id": ObjectId(topic_id)})
    return result.deleted_count > 0

def delete_evaluation_plan(evaluation_plan_id):
    db = get_db()
    result = db.evaluation_plans.delete_one({"_id": ObjectId(evaluation_plan_id)})
    return result.deleted_count > 0

def delete_evaluation(evaluation_id):
    db = get_db()
    result = db.evaluations.delete_one({"_id": ObjectId(evaluation_id)})
    return result.deleted_count > 0

def process_uploaded_document(file):
    """
    Procesa un archivo subido (PDF o Excel) y extrae la información estructurada.
    
    Args:
        file: Objeto FileStorage de Flask
        
    Returns:
        dict: Datos estructurados extraídos del documento
    """
    filename = secure_filename(file.filename)
    file_ext = os.path.splitext(filename)[1].lower()
    
    # Guardar el archivo temporalmente
    temp_path = f"temp/{filename}"
    file.save(temp_path)
    
    try:
        if file_ext == '.pdf':
            data = _process_pdf(temp_path)
        elif file_ext in ['.xlsx', '.xls']:
            data = _process_excel(temp_path)
        else:
            raise ValueError("Formato de archivo no soportado. Use PDF o Excel.")
            
        # Guardar el archivo en almacenamiento permanente (ej: S3)
        document_url = _upload_to_storage(temp_path)
        
        # Agregar URL del documento a los datos procesados
        data['document_url'] = document_url
        
        return data
        
    finally:
        # Limpiar archivo temporal
        if os.path.exists(temp_path):
            os.remove(temp_path)

def _process_pdf(file_path):
    """Procesa archivo PDF y extrae información estructurada"""
    reader = PdfReader(file_path)
    text = ""
    
    for page in reader.pages:
        text += page.extract_text()
    
    # Aquí implementar la lógica de extracción según el formato esperado
    # Este es un ejemplo simplificado
    return {
        'name': 'Plan extraído de PDF',
        'description': 'Descripción extraída del PDF',
        'modules': [
            {
                'name': 'Módulo ejemplo',
                'start_date': '2024-01-01',
                'end_date': '2024-02-01',
                'objectives': ['Objetivo 1', 'Objetivo 2'],
                'topics': [
                    {
                        'name': 'Tema ejemplo',
                        'description': 'Descripción del tema',
                        'date_range': '2024-01-01/2024-01-15',
                        'class_schedule': 'Lunes y Miércoles 10:00-12:00'
                    }
                ]
            }
        ]
    }

def _process_excel(file_path):
    """Procesa archivo Excel y extrae información estructurada"""
    df = pd.read_excel(file_path)
    
    # Aquí implementar la lógica de extracción según el formato esperado
    # Este es un ejemplo simplificado
    return {
        'name': df.iloc[0]['nombre_plan'],
        'description': df.iloc[0]['descripcion'],
        'modules': [
            {
                'name': row['nombre_modulo'],
                'start_date': row['fecha_inicio'],
                'end_date': row['fecha_fin'],
                'objectives': row['objetivos'].split(','),
                'topics': _get_topics_from_excel(df, row['id_modulo'])
            }
            for _, row in df.iterrows()
        ]
    }

def _get_topics_from_excel(df, module_id):
    """Extrae los temas relacionados a un módulo del Excel"""
    # Implementar lógica para extraer temas según estructura del Excel
    return [
        {
            'name': 'Tema desde Excel',
            'description': 'Descripción del tema',
            'date_range': '2024-01-01/2024-01-15',
            'class_schedule': 'Lunes y Miércoles 10:00-12:00'
        }
    ]

def _upload_to_storage(file_path):
    """
    Sube el archivo a almacenamiento permanente (ej: S3)
    Retorna la URL del documento almacenado
    """
    # Implementar lógica de subida a almacenamiento
    return f"https://storage.example.com/documents/{os.path.basename(file_path)}"
# ... (más funciones de base de datos) 