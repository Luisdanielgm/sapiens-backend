from typing import List, Dict, Optional, Union, Tuple
from bson import ObjectId
import logging
import random
import requests
import json
import os
from datetime import datetime, timedelta
from urllib.parse import quote_plus
from bs4 import BeautifulSoup
from src.shared.database import get_db
from src.shared.utils import ensure_json_serializable
from .models import WebSearchResult, SearchProvider

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
    """Servicio para realizar búsquedas web utilizando SearXNG"""
    
    def __init__(self):
        self.collection = get_db().web_search_results
        self.provider_service = SearchProviderService()
        self.cache_duration = 3600  # 1 hora en segundos
        self.USER_AGENT = 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36'
        # Añadir contador de reintentos por instancia
        self.instance_failures = {}
        self.max_failures = 5  # Número máximo de fallos antes de marcar la instancia como inactiva
        
    def search_web(self, query: str, result_type: str = None, max_results: int = 10, topic_id: str = None) -> List[Dict]:
        """Realiza una búsqueda web con SearXNG
        
        Args:
            query: Consulta de búsqueda
            result_type: Tipo de resultado (webpage, image, video, news)
            max_results: Número máximo de resultados
            topic_id: ID del tema relacionado (opcional)
            
        Returns:
            Lista de resultados de búsqueda
        """
        try:
            # Buscar en caché primero
            cached_results = self._get_cached_results(query, max_results)
            if cached_results:
                logger.info(f"Resultados obtenidos de caché para: {query}")
                return cached_results
                
            # Obtener proveedores activos
            providers = self.provider_service.list_providers(active_only=True)
            searxng_providers = [p for p in providers if p.get("provider_type") == "searxng"]
            
            if not searxng_providers:
                # Cargar instancias verificadas y crear un proveedor predeterminado
                verified_instances_path = os.path.join(
                    os.path.dirname(os.path.abspath(__file__)),
                    "verified_searxng_instances.json"
                )
                
                if os.path.exists(verified_instances_path):
                    try:
                        with open(verified_instances_path, "r") as f:
                            verified_instances = json.load(f)
                        
                        # Verificar que hay instancias válidas
                        if not verified_instances:
                            logger.error("No hay instancias verificadas disponibles")
                            return []
                            
                        # Filtrar instancias con demasiados fallos
                        filtered_instances = self._filter_working_instances(verified_instances)
                        
                        if not filtered_instances:
                            # Si todas están fallando, reiniciar contadores y probar con todas
                            logger.warning("Todas las instancias tienen problemas, reiniciando contadores de fallos")
                            self.instance_failures = {}
                            filtered_instances = verified_instances
                        
                        # Crear proveedor predeterminado
                        default_provider = {
                            "name": "SearXNG Default",
                            "provider_type": "searxng",
                            "instances": filtered_instances
                        }
                        
                        success, provider_id = self.provider_service.create_provider(default_provider)
                        if success:
                            provider = self.provider_service.collection.find_one({"_id": ObjectId(provider_id)})
                            provider["_id"] = str(provider["_id"])
                            searxng_providers = [provider]
                        else:
                            logger.error(f"No se pudo crear proveedor predeterminado: {provider_id}")
                        
                    except Exception as e:
                        logger.error(f"Error al cargar instancias verificadas: {e}")
                        return []
                else:
                    logger.error("Archivo de instancias verificadas no encontrado")
                    return []
            
            if not searxng_providers:
                logger.error("No hay proveedores SearXNG disponibles")
                return []
                
            # Realizar búsqueda con el primer proveedor disponible
            provider = searxng_providers[0]
            
            # Actualizar las instancias del proveedor para evitar instancias problemáticas
            if "instances" in provider:
                provider["instances"] = self._filter_working_instances(provider["instances"])
                if not provider["instances"]:
                    # Si no hay instancias buenas, cargar todas de nuevo y reiniciar contadores
                    logger.warning("Todas las instancias tienen problemas, reiniciando contadores")
                    self.instance_failures = {}
                    verified_instances_path = os.path.join(
                        os.path.dirname(os.path.abspath(__file__)),
                        "verified_searxng_instances.json"
                    )
                    if os.path.exists(verified_instances_path):
                        with open(verified_instances_path, "r") as f:
                            provider["instances"] = json.load(f)
                
            # Buscar con SearXNG
            search_results = self._search_with_searxng(provider, query, result_type, max_results, topic_id)
            
            # Guardar resultados en caché si hay resultados
            if search_results:
                try:
                    cache_entry = {
                        "query": query,
                        "results": search_results,
                        "provider": provider.get("name"),
                        "timestamp": datetime.now()
                    }
                    self.collection.insert_one(cache_entry)
                    logger.info(f"Resultados guardados en caché para: {query}")
                except Exception as e:
                    logger.error(f"Error al guardar resultados en caché: {e}")
            
            return search_results
        except Exception as e:
            logger.error(f"Error en búsqueda web: {str(e)}")
            return []
            
    def _get_cached_results(self, query: str, max_results: int) -> List[Dict]:
        """Obtiene resultados de búsqueda desde caché
        
        Args:
            query: Consulta de búsqueda
            max_results: Número máximo de resultados
            
        Returns:
            Lista de resultados o lista vacía si no hay caché válida
        """
        try:
            # Calcular tiempo máximo de antigüedad para considerar el caché válido
            max_age_hours = 24  # 24 horas
            max_age = datetime.now() - timedelta(hours=max_age_hours)
            
            # Buscar en caché
            cached = self.collection.find_one(
                {
                    "query": query,
                    "timestamp": {"$gte": max_age}
                }
            )
            
            if cached and "results" in cached:
                # Limitar cantidad de resultados si es necesario
                return cached["results"][:max_results]
            
                return []
        except Exception as e:
            logger.error(f"Error al obtener resultados de caché: {e}")
            return []
    
    def _filter_working_instances(self, instances: List[str]) -> List[str]:
        """Filtra instancias basándose en su historial de fallos
        
        Args:
            instances: Lista de instancias a filtrar
            
        Returns:
            Lista de instancias que no tienen demasiados fallos
        """
        return [
            instance for instance in instances 
            if self.instance_failures.get(instance, 0) < self.max_failures
        ]
    
    def _search_with_searxng(self, provider: dict, query: str, result_type: Optional[str] = None, 
                        max_results: int = 10, topic_id: Optional[str] = None) -> List[dict]:
        """Realiza una búsqueda utilizando instancias de SearXNG
        
        Args:
            provider: Proveedor SearXNG configurado
            query: Consulta de búsqueda
            result_type: Tipo de resultado (web, image, video)
            max_results: Número máximo de resultados
            topic_id: ID del tópico asociado
            
        Returns:
            Lista de resultados de búsqueda
        """
        instances = provider.get("instances", [])
        if not instances:
            logger.error("No hay instancias SearXNG configuradas")
            return []
            
        # Aleatorizar el orden de las instancias para distribuir la carga
        random.shuffle(instances)
            
        search_params = {
            "q": query,
            "format": "html"  # Usar HTML en lugar de JSON debido a restricciones de algunas instancias
        }
        
        # Ajustar parámetros según tipo de resultado
        if result_type == "image":
            search_params["categories"] = "images"
        elif result_type == "video":
            search_params["categories"] = "videos"
        
        # Lista de agentes de usuario para rotación
        user_agents = [
            'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36',
            'Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/92.0.4515.107 Safari/537.36',
            'Mozilla/5.0 (Windows NT 10.0; Win64; x64; rv:90.0) Gecko/20100101 Firefox/90.0',
            'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/14.1.1 Safari/605.1.15'
        ]
        
        # Preparar variables para recopilar resultados
        all_results = []
        all_results_by_url = {}
        errors = []
        unique_urls = set()
        success_count = 0
        
        # Intentar con cada instancia hasta obtener resultados o agotar instancias
        for instance in instances:
            # Si ya tenemos suficientes resultados, salir del bucle
            if len(all_results_by_url) >= max_results * 2:
                break
                
            try:
                # Construir URL de búsqueda
                search_url = f"{instance}/search"
                
                # Seleccionar un agente de usuario aleatorio
                current_user_agent = random.choice(user_agents)
                
                # Realizar solicitud
                response = requests.get(
                    search_url, 
                    params=search_params,
                    headers={"User-Agent": current_user_agent},
                    timeout=10
                )
                
                if response.status_code == 200:
                    # Parsear HTML
                    soup = BeautifulSoup(response.text, "html.parser")
                    
                    # Buscar resultados
                    result_elements = soup.select('.result')
                    
                    if result_elements:
                        success_count += 1
                        # Reiniciar contador de fallos para esta instancia
                        self.instance_failures[instance] = 0
                        
                        for i, result_div in enumerate(result_elements):
                            # Extraer título y URL
                            title_el = None
                            for selector in ['.result-title', '.result-header', 'h3 a', '.title a', 'a', 'h4 a', 'h3']:
                                title_el = result_div.select_one(selector)
                                if title_el:
                                    break
                            
                            if not title_el:
                                continue
                            
                            title = title_el.get_text(strip=True)
                            url = title_el.get('href')
                            
                            # Verificar URL
                            if not url:
                                continue
                            
                            # Extraer snippet
                            snippet = ""
                            for selector in ['.result-content', '.content', '.snippet', '.description', 'p', '.text']:
                                snippet_el = result_div.select_one(selector)
                                if snippet_el:
                                    snippet = snippet_el.get_text(strip=True)
                                    break
                            
                            # Extraer motor de búsqueda
                            engine = "desconocido"
                            for selector in ['.engines', '.engine', '.source', '.provider']:
                                engine_el = result_div.select_one(selector)
                                if engine_el:
                                    engine = engine_el.get_text(strip=True)
                                    break
                            
                            # Determinar tipo de resultado
                            item_type = "webpage"  # Por defecto
                            if result_type == "image" or result_div.select_one('img'):
                                item_type = "image"
                            elif result_type == "video" or "video" in url.lower():
                                item_type = "video"
                            elif url.lower().endswith((".pdf", ".doc", ".docx", ".ppt", ".pptx")):
                                item_type = "document"
                    
                            # Crear objeto de resultado
                            result = WebSearchResult(
                                title=title,
                                url=url,
                                snippet=snippet,
                                result_type=item_type,
                                topic_id=topic_id,
                                metadata={
                                    "engine": engine,
                                    "source": "searxng",
                                    "source_instance": instance
                                },
                                relevance_score=1.0 - (i * 0.01)  # Mayor score para los primeros resultados
                            )
                            
                            # Usar la URL como clave para agrupar resultados
                            result_dict = ensure_json_serializable(result.to_dict())
                            
                            # Agregar a la lista de resultados por URL
                            if url in all_results_by_url:
                                all_results_by_url[url]["metadata"]["instances"].append(instance)
                                all_results_by_url[url]["metadata"]["score"] += 1
                            else:
                                result_dict["metadata"]["instances"] = [instance]
                                result_dict["metadata"]["score"] = 1
                                all_results_by_url[url] = result_dict
                                unique_urls.add(url)
                    else:
                        logger.warning(f"No se encontraron resultados en {instance}")
                        # Incrementar conteo de fallos pero no mucho
                        self.instance_failures[instance] = self.instance_failures.get(instance, 0) + 1
                elif response.status_code == 429:
                    logger.warning(f"Límite de tasa excedido para {instance}")
                    errors.append(f"Límite de tasa excedido para {instance}")
                    # Incrementar el conteo de fallos
                    self.instance_failures[instance] = self.instance_failures.get(instance, 0) + 1
                else:
                    logger.warning(f"Error al consultar {instance}: {response.status_code}")
                    errors.append(f"Error al consultar {instance}: {response.status_code}")
                    # Incrementar el conteo de fallos
                    self.instance_failures[instance] = self.instance_failures.get(instance, 0) + 1
            except requests.exceptions.RequestException as e:
                logger.error(f"Error de conexión con {instance}: {str(e)}")
                errors.append(f"Error de conexión con {instance}: {str(e)}")
                # Incrementar el conteo de fallos
                self.instance_failures[instance] = self.instance_failures.get(instance, 0) + 2  # Penalizar más los errores de conexión
                
            # Pausa corta entre instancias para evitar sobrecarga
            if len(instances) > 1:
                import time
                time.sleep(0.5)  # 500ms de pausa
        
        # Convertir el diccionario de resultados a lista
        for url, result in all_results_by_url.items():
            # Normalizar relevancia basada en score
            result["relevance_score"] = min(1.0, result["relevance_score"] + (result["metadata"]["score"] * 0.05))
            all_results.append(result)
        
        # Registrar estado de la búsqueda
        logger.info(f"Búsqueda completada. Se encontraron {len(all_results)} resultados únicos")
        if len(errors) > 0:
            logger.warning(f"Se encontraron {len(errors)} errores durante la búsqueda")
            
        # Ordenar resultados por relevancia
        all_results.sort(key=lambda x: x.get("relevance_score", 0), reverse=True)
        
        # Limitar cantidad de resultados
        if max_results > 0 and len(all_results) > max_results:
            all_results = all_results[:max_results]
        
        return all_results
    
    def save_search_result(self, result_id: str) -> Tuple[bool, str]:
        """Marca un resultado de búsqueda como guardado
        
        Args:
            result_id: ID del resultado de búsqueda
            
        Returns:
            Tupla (éxito, mensaje)
        """
        try:
            # Buscar el resultado
            result = self.collection.find_one({"_id": ObjectId(result_id)})
            if not result:
                return False, "Resultado no encontrado"
                
            # Actualizarlo como guardado
            self.collection.update_one(
                {"_id": ObjectId(result_id)},
                {"$set": {"is_saved": True}}
            )
            
            return True, "Resultado guardado exitosamente"
        except Exception as e:
            logger.error(f"Error al guardar resultado: {str(e)}")
            return False, str(e)