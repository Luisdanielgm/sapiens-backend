from datetime import datetime
from bson import ObjectId
from .mongodb import get_indigenous_db

def create_translation(español, traduccion, dialecto, language_pair, type_data):
    """Crea una nueva traducción"""
    db = get_indigenous_db()
    translation = {
        "español": español,
        "traduccion": traduccion,
        "dialecto": dialecto,
        "language_pair": language_pair,
        "type_data": type_data,
        "created_at": datetime.utcnow(),
        "updated_at": datetime.utcnow()
    }
    result = db.translations.insert_one(translation)
    return str(result.inserted_id)

def get_translations(language_pair=None, type_data=None, dialecto=None):
    """Obtiene traducciones con filtros opcionales"""
    db = get_indigenous_db()
    query = {}
    
    if language_pair:
        query["language_pair"] = language_pair
    if type_data:
        query["type_data"] = type_data
    if dialecto:
        query["dialecto"] = dialecto
        
    translations = list(db.translations.find(query))
    
    # Convertir ObjectId a string para serialización
    for translation in translations:
        translation["_id"] = str(translation["_id"])
        
    return translations

def update_translation(translation_id, updates):
    """Actualiza una traducción existente"""
    db = get_indigenous_db()
    updates["updated_at"] = datetime.utcnow()
    
    result = db.translations.update_one(
        {"_id": ObjectId(translation_id)},
        {"$set": updates}
    )
    return result.modified_count > 0

def delete_translation(translation_id):
    """Elimina una traducción"""
    db = get_indigenous_db()
    result = db.translations.delete_one({"_id": ObjectId(translation_id)})
    return result.deleted_count > 0

def bulk_create_translations(translations):
    """Crea múltiples traducciones a la vez"""
    db = get_indigenous_db()
    now = datetime.utcnow()
    
    for translation in translations:
        translation["created_at"] = now
        translation["updated_at"] = now
        
    result = db.translations.insert_many(translations)
    return [str(id) for id in result.inserted_ids] 