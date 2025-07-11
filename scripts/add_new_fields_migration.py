#!/usr/bin/env python3
"""
Script de migración para agregar nuevos campos al sistema de módulos virtuales.

Este script agrega:
1. Campo 'slide_template' a documentos TopicContent de tipo 'slides'
2. Campo 'locked' a documentos VirtualTopic existentes

Ejecutar desde el directorio raíz del proyecto:
python scripts/add_new_fields_migration.py
"""

import sys
import os
from datetime import datetime
from pymongo import MongoClient

# Agregar el directorio raíz al path para importar módulos
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from config import get_database_url

def get_database():
    """Obtiene la conexión a la base de datos."""
    try:
        client = MongoClient(get_database_url())
        db = client.get_default_database()
        return db
    except Exception as e:
        print(f"Error conectando a la base de datos: {e}")
        return None

def migrate_topic_content_slide_template(db):
    """
    Agrega el campo 'slide_template' a documentos TopicContent de tipo 'slides'.
    """
    print("🔄 Iniciando migración de slide_template en TopicContent...")
    
    try:
        collection = db.topic_contents
        
        # Buscar documentos de tipo 'slides' que no tengan slide_template
        query = {
            "content_type": "slides",
            "slide_template": {"$exists": False}
        }
        
        slides_without_template = list(collection.find(query))
        
        if not slides_without_template:
            print("✅ No se encontraron documentos de slides sin slide_template.")
            return True
        
        print(f"📊 Encontrados {len(slides_without_template)} documentos de slides sin slide_template")
        
        # Plantilla por defecto para slides existentes
        default_slide_template = {
            "background": {
                "type": "color",
                "value": "#ffffff",
                "image_url": None
            },
            "styles": {
                "font_family": "Arial, sans-serif",
                "font_size": "16px",
                "text_color": "#333333",
                "heading_color": "#2c3e50",
                "accent_color": "#3498db"
            },
            "layout": {
                "padding": "20px",
                "max_width": "800px",
                "text_align": "left"
            }
        }
        
        updated_count = 0
        
        for doc in slides_without_template:
            try:
                result = collection.update_one(
                    {"_id": doc["_id"]},
                    {
                        "$set": {
                            "slide_template": default_slide_template,
                            "updated_at": datetime.now()
                        }
                    }
                )
                
                if result.modified_count > 0:
                    updated_count += 1
                    print(f"✅ Actualizado slide {doc['_id']}")
                
            except Exception as e:
                print(f"❌ Error actualizando slide {doc['_id']}: {e}")
        
        print(f"✅ Migración completada: {updated_count}/{len(slides_without_template)} slides actualizados")
        return True
        
    except Exception as e:
        print(f"❌ Error en migración de slide_template: {e}")
        return False

def migrate_virtual_topic_locked_field(db):
    """
    Agrega el campo 'locked' a documentos VirtualTopic existentes.
    """
    print("🔄 Iniciando migración de campo 'locked' en VirtualTopic...")
    
    try:
        collection = db.virtual_topics
        
        # Buscar documentos que no tengan el campo 'locked'
        query = {"locked": {"$exists": False}}
        
        topics_without_locked = list(collection.find(query))
        
        if not topics_without_locked:
            print("✅ No se encontraron VirtualTopics sin campo 'locked'.")
            return True
        
        print(f"📊 Encontrados {len(topics_without_locked)} VirtualTopics sin campo 'locked'")
        
        updated_count = 0
        
        for doc in topics_without_locked:
            try:
                # Determinar el valor de 'locked' basado en el status actual
                current_status = doc.get("status", "locked")
                locked_value = current_status == "locked"
                
                result = collection.update_one(
                    {"_id": doc["_id"]},
                    {
                        "$set": {
                            "locked": locked_value,
                            "updated_at": datetime.now()
                        }
                    }
                )
                
                if result.modified_count > 0:
                    updated_count += 1
                    status_info = f"(status: {current_status} -> locked: {locked_value})"
                    print(f"✅ Actualizado VirtualTopic {doc['_id']} {status_info}")
                
            except Exception as e:
                print(f"❌ Error actualizando VirtualTopic {doc['_id']}: {e}")
        
        print(f"✅ Migración completada: {updated_count}/{len(topics_without_locked)} VirtualTopics actualizados")
        return True
        
    except Exception as e:
        print(f"❌ Error en migración de campo 'locked': {e}")
        return False

def verify_migration(db):
    """
    Verifica que la migración se haya completado correctamente.
    """
    print("🔍 Verificando migración...")
    
    try:
        # Verificar TopicContent
        slides_count = db.topic_contents.count_documents({"content_type": "slides"})
        slides_with_template = db.topic_contents.count_documents({
            "content_type": "slides",
            "slide_template": {"$exists": True}
        })
        
        print(f"📊 TopicContent slides: {slides_with_template}/{slides_count} tienen slide_template")
        
        # Verificar VirtualTopic
        virtual_topics_count = db.virtual_topics.count_documents({})
        virtual_topics_with_locked = db.virtual_topics.count_documents({
            "locked": {"$exists": True}
        })
        
        print(f"📊 VirtualTopics: {virtual_topics_with_locked}/{virtual_topics_count} tienen campo 'locked'")
        
        # Verificar que la migración fue exitosa
        migration_success = (
            (slides_count == 0 or slides_with_template == slides_count) and
            (virtual_topics_count == 0 or virtual_topics_with_locked == virtual_topics_count)
        )
        
        if migration_success:
            print("✅ Verificación exitosa: Todos los documentos tienen los nuevos campos")
        else:
            print("⚠️  Verificación parcial: Algunos documentos pueden no tener los nuevos campos")
        
        return migration_success
        
    except Exception as e:
        print(f"❌ Error en verificación: {e}")
        return False

def main():
    """Función principal del script de migración."""
    print("🚀 Iniciando migración de nuevos campos para módulos virtuales")
    print("=" * 60)
    
    # Conectar a la base de datos
    db = get_database()
    if not db:
        print("❌ No se pudo conectar a la base de datos")
        sys.exit(1)
    
    print(f"✅ Conectado a la base de datos: {db.name}")
    
    # Ejecutar migraciones
    success = True
    
    # 1. Migrar slide_template en TopicContent
    if not migrate_topic_content_slide_template(db):
        success = False
    
    print("-" * 40)
    
    # 2. Migrar campo locked en VirtualTopic
    if not migrate_virtual_topic_locked_field(db):
        success = False
    
    print("-" * 40)
    
    # 3. Verificar migración
    if not verify_migration(db):
        success = False
    
    print("=" * 60)
    
    if success:
        print("🎉 Migración completada exitosamente")
        print("✅ El sistema está listo para usar las nuevas funcionalidades")
    else:
        print("⚠️  Migración completada con advertencias")
        print("🔧 Revisa los errores anteriores y ejecuta el script nuevamente si es necesario")
    
    return 0 if success else 1

if __name__ == "__main__":
    exit_code = main()
    sys.exit(exit_code) 