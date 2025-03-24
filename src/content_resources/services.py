import logging
import random
import requests
import json
import os
from datetime import datetime, timedelta
from urllib.parse import quote_plus
from bs4 import BeautifulSoup
from bson import ObjectId
from typing import List, Dict, Tuple, Optional
from src.shared.database import get_db
from src.shared.utils import ensure_json_serializable
from .models import WebSearchResult, SearchProvider
import sys

logger = logging.getLogger(__name__)

class SearchProviderService:
    """Servicio para gestionar proveedores de búsqueda SearXNG"""

    def __init__(self):
        self.collection = get_db().search_providers
        
    def list_providers(self, active_only: bool = True) -> List[Dict]:
        """Obtiene lista de proveedores de búsqueda
        
        Args:
            active_only: Si es True, sólo devuelve proveedores activos
            
        Returns:
            Lista de proveedores de búsqueda
        """
        query = {"status": "active"} if active_only else {}
        providers = list(self.collection.find(query))
        
        # Convertir ObjectId a string para serialización JSON
        for provider in providers:
            if "_id" in provider:
                provider["_id"] = str(provider["_id"])
        
        return providers

    def add_searxng_instance(self, provider_id: str, instance_url: str) -> Tuple[bool, str]:
        """Añade una nueva instancia SearXNG a un proveedor existente
        
        Args:
            provider_id: ID del proveedor
            instance_url: URL de la instancia a añadir
            
        Returns:
            Tupla (éxito, mensaje)
        """
        try:
            # Validar la URL
            if not instance_url.startswith(("http://", "https://")):
                return False, "La URL debe comenzar con http:// o https://"
                
            # Comprobar si la instancia está accesible
            headers = {
                'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36'
            }
            
            try:
                response = requests.get(f"{instance_url}/search?q=test", headers=headers, timeout=10)
                if response.status_code != 200:
                    return False, f"La instancia no está respondiendo correctamente: {response.status_code}"
            except Exception as e:
                return False, f"Error al conectar con la instancia: {str(e)}"
                
            # Obtener el proveedor
            provider = self.collection.find_one({"_id": ObjectId(provider_id)})
            if not provider:
                return False, f"No se encontró proveedor con ID {provider_id}"
                
            # Comprobar si la instancia ya existe
            instances = provider.get("instances", [])
            if instance_url in instances:
                return False, "La instancia ya está registrada en este proveedor"
                
            # Añadir la instancia
            instances.append(instance_url)
            
            self.collection.update_one(
                {"_id": ObjectId(provider_id)},
                {"$set": {
                    "instances": instances,
                    "updated_at": datetime.now()
                }}
            )
            
            # Añadir a la lista de instancias verificadas si no existe
            verified_instances_path = os.path.join(
                os.path.dirname(os.path.abspath(__file__)),
                "verified_searxng_instances.json"
            )
            
            if os.path.exists(verified_instances_path):
                try:
                    with open(verified_instances_path, "r") as f:
                        verified_instances = json.load(f)
                        
                    if instance_url not in verified_instances:
                        verified_instances.append(instance_url)
                        
                        with open(verified_instances_path, "w") as f:
                            json.dump(verified_instances, f, indent=2)
                except Exception as e:
                    logger.warning(f"No se pudo actualizar la lista de instancias verificadas: {str(e)}")
            
            return True, "Instancia añadida correctamente"
            
        except Exception as e:
            logger.error(f"Error al añadir instancia: {str(e)}")
            return False, str(e)

    def create_provider(self, provider_data: Dict) -> Tuple[bool, str]:
        """Crea un nuevo proveedor de búsqueda SearXNG
        
        Args:
            provider_data: Datos del proveedor a crear
            
        Returns:
            Tupla (éxito, id o mensaje de error)
        """
        try:
            if not provider_data.get("name"):
                return False, "El nombre del proveedor es requerido"
            
            # Validar si ya existe un proveedor con el mismo nombre
            existing = self.collection.find_one({"name": provider_data["name"]})
            if existing:
                return False, f"Ya existe un proveedor con el nombre {provider_data['name']}"
            
            # Validar instancias    
            if not provider_data.get("instances"):
                # Cargar instancias verificadas
                instances_file = os.path.join(os.path.dirname(__file__), 'verified_searxng_instances.json')
                with open(instances_file, 'r') as f:
                    provider_data["instances"] = json.load(f)
                    
            # Crear proveedor
            provider = SearchProvider(
                name=provider_data["name"],
                provider_type="searxng",
                instances=provider_data["instances"],
                config=provider_data.get("config", {})
            )
            
            result = self.collection.insert_one(provider.to_dict())
            return True, str(result.inserted_id)
            
        except Exception as e:
            logger.error(f"Error al crear proveedor: {str(e)}")
            return False, str(e)

    def update_provider(self, provider_id: str, update_data: Dict) -> Tuple[bool, str]:
        """Actualiza un proveedor existente
        
        Args:
            provider_id: ID del proveedor a actualizar
            update_data: Datos a actualizar
            
        Returns:
            Tupla (éxito, mensaje)
        """
        try:
            # Verificar que el proveedor existe
            provider = self.collection.find_one({"_id": ObjectId(provider_id)})
            if not provider:
                return False, f"No se encontró proveedor con ID {provider_id}"
            
            update_fields = {}
            
            if "name" in update_data:
                update_fields["name"] = update_data["name"]
                
            if "instances" in update_data:
                update_fields["instances"] = update_data["instances"]
                
            if "config" in update_data:
                update_fields["config"] = update_data["config"]
                
            if "status" in update_data:
                if update_data["status"] in ["active", "inactive"]:
                    update_fields["status"] = update_data["status"]
            else:
                    return False, "El estado debe ser 'active' o 'inactive'"
                    
            if not update_fields:
                return True, "No se realizaron cambios"
                
            update_fields["updated_at"] = datetime.now()
            
            self.collection.update_one(
                {"_id": ObjectId(provider_id)},
                {"$set": update_fields}
            )
            
            return True, "Proveedor actualizado correctamente"
            
        except Exception as e:
            logger.error(f"Error al actualizar proveedor: {str(e)}")
            return False, str(e)

    def delete_provider(self, provider_id: str) -> Tuple[bool, str]:
        """Elimina un proveedor de búsqueda
        
        Args:
            provider_id: ID del proveedor a eliminar
            
        Returns:
            Tupla (éxito, mensaje)
        """
        try:
            result = self.collection.delete_one({"_id": ObjectId(provider_id)})
            if result.deleted_count > 0:
                return True, "Proveedor eliminado correctamente"
            return False, "No se encontró proveedor para eliminar"
        except Exception as e:
            logger.error(f"Error al eliminar proveedor: {str(e)}")
            return False, str(e)
    
    def test_provider(self, provider_id: str) -> Tuple[bool, str, Dict]:
        """Prueba la conexión con un proveedor SearXNG
        
        Args:
            provider_id: ID del proveedor a probar
            
        Returns:
            Tupla (éxito, mensaje, resultados)
        """
        try:
            # Obtener el proveedor
            provider = self.collection.find_one({"_id": ObjectId(provider_id)})
            if not provider:
                return False, f"Proveedor no encontrado: {provider_id}", {}
                
            # Obtener instancias
            instances = provider.get("instances", [])
            if not instances:
                return False, "No hay instancias SearXNG configuradas", {}
            
            # Probar conexión con todas las instancias
            results = []
            successful_instances = 0
            
            # Cabeceras HTTP para simular un navegador real
            headers = {
                'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36',
                'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,image/webp,*/*;q=0.8',
                'DNT': '1'
            }
            
            for instance in instances:
                try:
                    # Intentar hacer una consulta de prueba con HTML
                    test_url = f"{instance}/search?q=test"
                    response = requests.get(test_url, headers=headers, timeout=10)
                    
                    if response.status_code == 200:
                        successful_instances += 1
                        results.append({
                            "instance": instance,
                            "status": "online",
                            "response_time": round(response.elapsed.total_seconds(), 2)
                        })
                    else:
                        results.append({
                            "instance": instance,
                            "status": "error",
                            "error": f"Error HTTP {response.status_code}"
                        })
                except Exception as e:
                    results.append({
                        "instance": instance,
                        "status": "error",
                        "error": str(e)
                    })
            
            # Actualizar el proveedor con la información de las instancias
            self.collection.update_one(
                {"_id": ObjectId(provider_id)},
                {"$set": {"instance_status": {r["instance"]: r for r in results}}}
            )
            
            if successful_instances > 0:
                return True, f"{successful_instances} de {len(instances)} instancias están activas", {
                    "instances": results,
                    "active_count": successful_instances
                }
            else:
                return False, "Ninguna instancia está activa", {
                    "instances": results
                }
                
        except Exception as e:
            logger.error(f"Error al probar proveedor: {str(e)}")
            return False, f"Error inesperado: {str(e)}", {}


class WebSearchService:
    """Servicio para realizar búsquedas web utilizando ValueSerp API"""
    
    def __init__(self):
        self.collection = get_db().web_search_results
        
    def search_web(self, query: str, max_results: int = 10) -> Dict:
        """Realiza una búsqueda web usando ValueSerp API"""
        try:
            print("\n" + "="*50)
            print("INICIANDO BÚSQUEDA EN VALUESERP")
            print("="*50)
            
            print(f"\n📝 Consulta: {query}")
            print(f"📊 Máximo de resultados: {max_results}")
            
            # Parámetros de la API
            params = {
                'api_key': '149DE3776FAC4354AA6974C82FCFD9FA',
                'q': query,
                'hl': 'es',  # Idioma español
                'gl': 'es',  # Región España
                'num': max_results,  # Número de resultados
                'include_ai_overview': 'true'  # Incluir resumen AI
            }
            
            print("\n🔍 Realizando búsqueda...")
            api_result = requests.get('https://api.valueserp.com/search', params)
            
            print(f"\n📡 Estado de la respuesta: {api_result.status_code}")
            
            if api_result.status_code == 200:
                response_json = api_result.json()
                
                # Procesar y mostrar resultados
                self._print_search_results(response_json)
                
                # Guardar resultados en la base de datos
                organic_results = response_json.get('organic_results', [])
                saved_results = []
                
                for result in organic_results:
                    search_result = {
                        'title': result.get('title'),
                        'url': result.get('link'),
                        'snippet': result.get('snippet'),
                        'position': result.get('position'),
                        'domain': result.get('domain'),
                        'query': query,
                        'created_at': datetime.now(),
                        'saved': False
                    }
                    
                    # Insertar en la base de datos
                    result_id = self.collection.insert_one(search_result).inserted_id
                    search_result['_id'] = str(result_id)
                    saved_results.append(search_result)
                
                # Convertir resultados al formato de la API
                formatted_results = {
                    'organic_results': saved_results,
                    'knowledge_graph': response_json.get('knowledge_graph', {}),
                    'videos': response_json.get('inline_videos', []),
                    'related_searches': response_json.get('related_searches', []),
                    'search_metadata': response_json.get('search_metadata', {}),
                    'total_results': response_json.get('search_information', {}).get('total_results', 0)
                }
                
                return formatted_results
            else:
                print("\n❌ Error en la respuesta:")
                print(api_result.text)
                return {
                    'organic_results': [],
                    'knowledge_graph': {},
                    'videos': [],
                    'related_searches': [],
                    'search_metadata': {},
                    'total_results': 0,
                    'error': api_result.text
                }
                
        except Exception as e:
            print(f"\n❌ Error en la petición: {str(e)}")
            return {
                'organic_results': [],
                'knowledge_graph': {},
                'videos': [],
                'related_searches': [],
                'search_metadata': {},
                'total_results': 0,
                'error': str(e)
            }
            
    def save_search_result(self, result_id: str) -> Tuple[bool, str]:
        """Marca un resultado de búsqueda como guardado
        
        Args:
            result_id: ID del resultado a guardar
            
        Returns:
            Tupla (éxito, mensaje)
        """
        try:
            # Convertir string ID a ObjectId
            result = self.collection.find_one({'_id': ObjectId(result_id)})
            
            if not result:
                return False, f"No se encontró el resultado con ID {result_id}"
                
            # Actualizar el estado a guardado
            self.collection.update_one(
                {'_id': ObjectId(result_id)},
                {'$set': {'saved': True}}
            )
            
            return True, "Resultado guardado exitosamente"
            
        except Exception as e:
            logger.error(f"Error al guardar resultado: {str(e)}")
            return False, str(e)
            
    def _print_search_results(self, response_json: Dict) -> None:
        """Imprime los resultados de búsqueda de forma formateada"""
        print("\n" + "="*50)
        print("RESULTADOS DE LA BÚSQUEDA")
        print("="*50)
        
        # Resultados orgánicos
        if 'organic_results' in response_json:
            print("\n🌐 RESULTADOS ORGÁNICOS:")
            for i, result in enumerate(response_json['organic_results'], 1):
                print(f"\n📌 Resultado #{i}")
                print(f"📑 Título: {result['title']}")
                print(f"🔗 URL: {result['link']}")
                print(f"📖 Descripción: {result['snippet']}")
                print("-"*30)
        
        # Knowledge Graph
        if 'knowledge_graph' in response_json:
            print("\n🧠 KNOWLEDGE GRAPH:")
            kg = response_json['knowledge_graph']
            print(f"📚 Título: {kg['title']}")
            print(f"🏷️ Tipo: {kg['type']}")
            if 'known_attributes' in kg:
                print("\n📋 Atributos:")
                for attr in kg['known_attributes']:
                    print(f"• {attr['name']}: {attr['value']}")
            print("-"*30)
        
        # Videos
        if 'inline_videos' in response_json:
            print("\n🎥 VÍDEOS RELACIONADOS:")
            for i, video in enumerate(response_json['inline_videos'], 1):
                print(f"\n🎬 Video #{i}")
                print(f"📺 Título: {video['title']}")
                print(f"⏱️ Duración: {video['length']}")
                print(f"📡 Fuente: {video['source']}")
                print(f"🔗 URL: {video['link']}")
                print("-"*30)
        
        # Búsquedas relacionadas
        if 'related_searches' in response_json:
            print("\n🔍 BÚSQUEDAS RELACIONADAS:")
            for i, related in enumerate(response_json['related_searches'], 1):
                print(f"• {related['query']}")
        
        print("\n" + "="*50)
        print("FIN DE LOS RESULTADOS")
        print("="*50)