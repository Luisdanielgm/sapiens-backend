import os
import re
import sys
from pathlib import Path

# Add project root to sys.path to allow imports from src
project_root = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(project_root))

try:
    from src.shared.database import get_db, get_indigenous_db
except ImportError as e:
    print(f"Error: No se pudo importar desde 'src'. Asegúrate de que el script se ejecuta desde la raíz del proyecto o que la ruta es correcta.")
    print(f"Detalle del error: {e}")
    sys.exit(1)

def get_db_collections():
    """Conecta a MongoDB y obtiene los nombres de todas las colecciones."""
    try:
        print("Conectando a la base de datos principal...")
        main_db = get_db()
        main_collections = set(main_db.list_collection_names())
        print(f"Se encontraron {len(main_collections)} colecciones en la BD principal.")
        
        print("\nConectando a la base de datos de lenguas indígenas...")
        indigenous_db = get_indigenous_db()
        indigenous_collections = set(indigenous_db.list_collection_names())
        print(f"Se encontraron {len(indigenous_collections)} colecciones en la BD de lenguas indígenas.")
        
        return main_collections, indigenous_collections
    except Exception as e:
        print(f"\n{'='*20} ERROR DE CONEXIÓN A MONGODB {'='*20}")
        print("No se pudo conectar a la base de datos. Asegúrate de que:")
        print("1. Las variables de entorno MONGO_DB_URI, DB_NAME, e INDIGENOUS_DB_NAME están configuradas correctamente.")
        print("2. MongoDB está en ejecución y accesible.")
        print(f"Detalle del error: {e}")
        print("="*65)
        return None, None

def find_collections_in_code(base_path='src'):
    """Analiza el código fuente para encontrar referencias a colecciones de MongoDB."""
    print(f"\nAnalizando el código en la ruta: '{base_path}'...")
    coded_collections = set()
    
    # Patrones de Regex para encontrar colecciones
    patterns = [
        re.compile(r'(?:db|get_db\(\))\.(?P<collection>\w+)\.'),
        re.compile(r'super\(\)\.__init__\((?:collection_name=)?["\'](?P<collection>\w+)["\']\)')
    ]
    
    for root, _, files in os.walk(base_path):
        for file in files:
            if file.endswith('.py'):
                file_path = os.path.join(root, file)
                try:
                    with open(file_path, 'r', encoding='utf-8') as f:
                        content = f.read()
                        for pattern in patterns:
                            for match in pattern.finditer(content):
                                coded_collections.add(match.group('collection'))
                except Exception as e:
                    print(f"  - Error leyendo el archivo {file_path}: {e}")

    print(f"Análisis de código completado. Se encontraron {len(coded_collections)} colecciones referenciadas.")
    return coded_collections

def print_report(title, collections):
    """Imprime una sección del reporte."""
    print(f"\n--- {title} ({len(collections)}) ---")
    if collections:
        for collection in sorted(list(collections)):
            print(f"  - {collection}")
    else:
        print("  Ninguna.")

def main():
    """Función principal del script."""
    print("="*60)
    print("Iniciando auditoría de colecciones de MongoDB...")
    print("="*60)

    db_main_collections, db_indigenous_collections = get_db_collections()
    if db_main_collections is None:
        return

    all_db_collections = db_main_collections.union(db_indigenous_collections)
    coded_collections = find_collections_in_code()

    # Comparación
    unused_in_db = all_db_collections - coded_collections
    missing_in_db = coded_collections - all_db_collections
    
    print("\n\n" + "="*25 + " REPORTE DE AUDITORÍA " + "="*25)
    
    print_report("Colecciones EN USO (encontradas en código y BD)", coded_collections.intersection(all_db_collections))
    print_report("Colecciones NO USADAS (en BD pero no en código)", unused_in_db)
    print_report("Colecciones FALTANTES (en código pero no en BD)", missing_in_db)
    
    print("\n" + "="*65)
    print("Auditoría finalizada.")


if __name__ == "__main__":
    main() 