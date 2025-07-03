import os
import sys
from pymongo import MongoClient
from dotenv import load_dotenv
from bson import ObjectId

# Asegurarse de que el script pueda encontrar los módulos de la aplicación
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

def migrate_topics():
    """
    Añade el campo 'published' a todos los documentos de la colección 'topics'.
    - Si el tema tiene 'theory_content' no vacío, published = True.
    - De lo contrario, published = False.
    """
    # Cargar variables de entorno del archivo .env
    load_dotenv()

    mongo_uri = os.getenv("MONGO_DB_URI")
    db_name = os.getenv("DB_NAME")

    if not mongo_uri or not db_name:
        print("Error: Las variables de entorno MONGO_DB_URI y DB_NAME deben estar configuradas.")
        return

    try:
        client = MongoClient(mongo_uri)
        db = client[db_name]
        topics_collection = db["topics"]

        print(f"Conectado a la base de datos '{db_name}'.")

        # Criterio para encontrar temas que no tienen el campo 'published'
        query = {"published": {"$exists": False}}
        topics_to_migrate = list(topics_collection.find(query))
        
        if not topics_to_migrate:
            print("No se encontraron temas para migrar. El campo 'published' ya podría existir en todos los documentos.")
            return

        print(f"Se encontraron {len(topics_to_migrate)} temas para migrar...")

        migrated_count = 0
        published_count = 0
        unpublished_count = 0

        for topic in topics_to_migrate:
            topic_id = topic["_id"]
            theory_content = topic.get("theory_content", "")
            
            # Determinar el valor de 'published'
            # Se considera publicado si tiene contenido teórico principal.
            is_published = bool(theory_content and theory_content.strip())

            # Actualizar el documento
            result = topics_collection.update_one(
                {"_id": topic_id},
                {"$set": {"published": is_published}}
            )

            if result.modified_count > 0:
                migrated_count += 1
                if is_published:
                    published_count += 1
                else:
                    unpublished_count += 1

        print("\n--- Resumen de la Migración ---")
        print(f"Temas actualizados exitosamente: {migrated_count}")
        print(f"Temas marcados como 'publicados': {published_count}")
        print(f"Temas marcados como 'no publicados': {unpublished_count}")
        print("---------------------------------")

    except Exception as e:
        print(f"Ocurrió un error durante la migración: {e}")
    finally:
        if 'client' in locals():
            client.close()
            print("Conexión a la base de datos cerrada.")

if __name__ == "__main__":
    print("Iniciando migración para añadir el campo 'published' a los temas...")
    migrate_topics()
    print("Migración completada.") 