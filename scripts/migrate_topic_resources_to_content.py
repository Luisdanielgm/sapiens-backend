import os
import sys
from pymongo import MongoClient
from bson import ObjectId
from datetime import datetime
from dotenv import load_dotenv

# Añadir el directorio raíz del proyecto al sys.path
# para que los módulos de la aplicación puedan ser importados
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

# Ahora se pueden importar los módulos necesarios
from src.shared.constants import COLLECTIONS
from src.study_plans.models import ContentTypes

# --- Configuración de la Base de Datos ---
# Se recomienda usar variables de entorno para la configuración en producción
load_dotenv()
MONGO_URI = os.environ.get("MONGO_DB_URI")
DB_NAME = os.environ.get("DB_NAME")

# Añadir la clave legacy temporalmente para el script
if "TOPIC_RESOURCES" not in COLLECTIONS:
    COLLECTIONS["TOPIC_RESOURCES"] = "topic_resources"
if "RESOURCES" not in COLLECTIONS:
    COLLECTIONS["RESOURCES"] = "resources"

def get_db():
    """Establece conexión con la base de datos MongoDB."""
    try:
        client = MongoClient(MONGO_URI)
        db = client[DB_NAME]
        print("Conexión a la base de datos exitosa.")
        return db
    except Exception as e:
        print(f"Error al conectar con la base de datos: {e}")
        sys.exit(1)

def migrate_topic_resources():
    """
    Migra los datos de la colección 'topic_resources' a 'topic_contents'.
    Por cada vínculo en 'topic_resources', se crea un nuevo documento
    en 'topic_contents' del tipo LINK, DOCUMENTS o IMAGE.
    """
    db = get_db()
    topic_resources_collection = db[COLLECTIONS["TOPIC_RESOURCES"]]
    resources_collection = db[COLLECTIONS["RESOURCES"]]
    topic_contents_collection = db[COLLECTIONS["TOPIC_CONTENTS"]]
    
    migrated_count = 0
    skipped_count = 0
    error_count = 0
    
    print("Iniciando migración de TopicResources a TopicContents...")
    
    # Usar un cursor para no cargar toda la colección en memoria
    for link in topic_resources_collection.find():
        try:
            topic_id = link.get("topic_id")
            resource_id = link.get("resource_id")
            creator_id = link.get("created_by")
            
            if not topic_id or not resource_id:
                print(f"Saltando vínculo (ID: {link['_id']}) por falta de topic_id o resource_id.")
                skipped_count += 1
                continue

            # Verificar si ya existe un TopicContent para este recurso y tema
            existing_content = topic_contents_collection.find_one({
                "topic_id": topic_id,
                "content_data.original_resource_id": resource_id
            })
            if existing_content:
                print(f"Saltando recurso ya migrado (Resource ID: {resource_id} para Topic ID: {topic_id}).")
                skipped_count += 1
                continue

            # Obtener el documento del recurso original
            resource = resources_collection.find_one({"_id": resource_id})
            if not resource:
                print(f"No se encontró el recurso original con ID: {resource_id}. Saltando.")
                skipped_count += 1
                continue
                
            # Determinar el tipo de contenido
            resource_type = resource.get("type", "link").lower()
            content_type = ContentTypes.LINK
            if resource_type in ["pdf", "document", "file"]:
                content_type = ContentTypes.DOCUMENTS
            elif resource_type in ["image", "jpg", "png"]:
                content_type = ContentTypes.IMAGE

            # Crear el nuevo documento de TopicContent
            new_content = {
                "_id": ObjectId(),
                "topic_id": topic_id,
                "content_type": content_type,
                "title": resource.get("name", "Recurso sin título"),
                "description": resource.get("description", ""),
                "content_data": {
                    "url": resource.get("url", ""),
                    "original_resource_id": resource_id,
                    "migrated_from": "topic_resources",
                    "migration_date": datetime.now()
                },
                "tags": resource.get("tags", []),
                "status": "active",
                "creator_id": creator_id or resource.get("created_by"),
                "created_at": resource.get("created_at", datetime.now()),
                "updated_at": datetime.now()
            }
            
            topic_contents_collection.insert_one(new_content)
            migrated_count += 1
            print(f"Recurso migrado: '{new_content['title']}' (ID: {resource_id})")

        except Exception as e:
            error_count += 1
            print(f"Error al migrar el vínculo con ID {link.get('_id')}: {e}")

    print("\n--- Resumen de la Migración ---")
    print(f"Total de recursos migrados exitosamente: {migrated_count}")
    print(f"Total de recursos omitidos (ya migrados o datos incompletos): {skipped_count}")
    print(f"Total de errores durante la migración: {error_count}")
    
    if error_count == 0 and migrated_count > 0:
        print("\n¡Migración completada exitosamente!")
        print("Recomendación: Después de verificar los datos, puedes considerar renombrar")
        print("las colecciones 'topic_resources' y 'resources' a 'topic_resources_deprecated'")
        print("y 'resources_deprecated' antes de eliminarlas definitivamente.")
    elif migrated_count == 0 and skipped_count > 0 and error_count == 0:
        print("\nNo se migraron nuevos recursos, parece que la data ya estaba actualizada.")
    else:
        print("\nLa migración finalizó con errores. Por favor, revisa los logs.")


if __name__ == "__main__":
    migrate_topic_resources() 