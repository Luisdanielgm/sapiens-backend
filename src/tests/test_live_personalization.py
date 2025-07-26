import unittest
from unittest.mock import Mock
import os
import sys
from bson import ObjectId

# --- Configuración del Entorno ---
# Añadir el directorio raíz al path para importar módulos de la aplicación
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..', '..')))

# Importar los servicios y la configuración de la base de datos
from src.virtual.services import FastVirtualModuleGenerator
from src.shared.database import get_db

class TestLivePersonalization(unittest.TestCase):
    """
    Prueba de integración para la lógica de personalización de contenidos
    utilizando datos reales de la base de datos MongoDB.
    """

    @classmethod
    def setUpClass(cls):
        """Se ejecuta una vez antes de todas las pruebas."""
        print("--- Iniciando Prueba de Personalización con Datos Reales ---")
        try:
            cls.db = get_db()
            cls.generator = FastVirtualModuleGenerator()
            print("✅ Conexión a la base de datos establecida.")
        except Exception as e:
            print(f"❌ ERROR: No se pudo conectar a la base de datos: {e}")
            raise

    def _find_suitable_topic(self, min_content_count=3):
        """
        Encuentra un topic_id adecuado para la prueba utilizando aggregation.
        Busca un tema que tenga al menos `min_content_count` contenidos.
        """
        print(f"\nBuscando un tema con al menos {min_content_count} contenidos...")
        pipeline = [
            {"$group": {"_id": "$topic_id", "count": {"$sum": 1}}},
            {"$match": {"count": {"$gte": min_content_count}}},
            {"$limit": 1}
        ]
        result = list(self.db.topic_contents.aggregate(pipeline))
        
        if result:
            topic_id = result[0]['_id']
            print(f"   - Tema encontrado: {topic_id} (tiene {result[0]['count']} contenidos)")
            return str(topic_id)
        else:
            print("   - ADVERTENCIA: No se encontró un tema adecuado. Buscando cualquier tema con al menos 1 contenido.")
            # Fallback: buscar cualquier tema que tenga al menos un contenido
            any_content = self.db.topic_contents.find_one()
            if any_content:
                topic_id = str(any_content['topic_id'])
                print(f"   - Tema de fallback encontrado: {topic_id}")
                return topic_id
            return None

    def test_personalization_with_real_data(self):
        """
        Ejecuta la lógica de personalización con un perfil y un tema reales.
        """
        # --- IDs de Prueba (reemplazar con IDs reales si es necesario) ---
        # Usando el ID de usuario del perfil que me mostraste
        USER_ID_TO_TEST = "681fa87135fbbacd2c883bb0"
        
        # --- Búsqueda Dinámica de un Tema Válido ---
        TOPIC_ID_TO_TEST = self._find_suitable_topic()
        self.assertIsNotNone(TOPIC_ID_TO_TEST, "No se pudo encontrar NINGÚN tema con contenidos en la base de datos.")

        print(f"\n1. Cargando datos para el usuario: {USER_ID_TO_TEST} y el tema encontrado: {TOPIC_ID_TO_TEST}")

        # --- Carga de Datos Reales ---
        # 1. Obtener el perfil cognitivo del usuario
        # La colección de perfiles parece estar separada, buscaré por user_id
        cognitive_profile_doc = self.db.cognitive_profiles.find_one({"user_id": ObjectId(USER_ID_TO_TEST)})
        self.assertIsNotNone(cognitive_profile_doc, f"No se encontró el perfil cognitivo para el user_id: {USER_ID_TO_TEST}")
        print("   - Perfil cognitivo encontrado.")

        # 2. Obtener todos los contenidos del tema original
        original_contents = list(self.db.topic_contents.find({"topic_id": ObjectId(TOPIC_ID_TO_TEST)}))
        self.assertTrue(len(original_contents) > 0, f"El tema {TOPIC_ID_TO_TEST} no tiene contenidos o no existe.")
        print(f"   - {len(original_contents)} contenidos originales encontrados para el tema.")

        # --- Ejecución de la Lógica de Personalización ---
        print("\n2. Ejecutando el servicio de personalización `_select_personalized_contents`...")
        selected_contents = self.generator._select_personalized_contents(
            original_contents,
            cognitive_profile_doc
        )
        print("   - Lógica de personalización ejecutada.")
        
        # --- Reporte de Resultados ---
        print("\n--- 📝 REPORTE DE PERSONALIZACIÓN ---")
        
        # Mostrar el perfil cognitivo utilizado
        print("\n[Perfil Cognitivo del Estudiante]")
        print(f"  - Estilo de Aprendizaje: {cognitive_profile_doc.get('learning_style', 'N/A')}")
        print(f"  - Dificultades Cognitivas: {cognitive_profile_doc.get('cognitive_difficulties', [])}")
        print(f"  - Diagnóstico (resumen): {cognitive_profile_doc.get('diagnosis', 'N/A')[:100]}...")

        # Mostrar los contenidos originales
        print("\n[Contenidos Originales Disponibles en el Tema]")
        for content in original_contents:
            print(f"  - Tipo: {content.get('content_type', 'N/A'):<25} | Título: {content.get('title', 'Sin título')}")

        # Mostrar los contenidos seleccionados
        print("\n[Contenidos Personalizados Seleccionados para el Estudiante]")
        self.assertTrue(len(selected_contents) > 0, "La selección de contenidos no debería estar vacía.")
        for content in selected_contents:
            print(f"  - ✅ Tipo: {content.get('content_type', 'N/A'):<25} | Título: {content.get('title', 'Sin título')}")

        print("\n--- Fin del Reporte ---")


if __name__ == '__main__':
    # Esto permite ejecutar el script directamente
    unittest.main(verbosity=2) 