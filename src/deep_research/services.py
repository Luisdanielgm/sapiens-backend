"""
Servicios para el módulo de investigación profunda (deep research)
"""
import requests
import logging
import json
from datetime import datetime
from typing import Dict, List, Tuple, Optional, Any
from bson import ObjectId
from src.shared.database import get_db
from src.shared.standardization import VerificationBaseService
from src.shared.logging import log_info, log_error
from src.study_plans.services import TopicService
from .models import DeepResearchSession

logger = logging.getLogger(__name__)

# URL base de la API externa de deep research
DEEP_RESEARCH_API_URL = "http://149.50.139.104:8000"

class DeepResearchService(VerificationBaseService):
    """Servicio para la investigación profunda y búsqueda web avanzada"""
    
    def __init__(self):
        """Inicializa el servicio de investigación profunda"""
        self.collection = get_db().deep_research_sessions
        self.topic_service = TopicService()
        
    def _call_deepresearch_api(self, endpoint: str, method: str = "GET", data: Dict = None, params: Dict = None) -> Tuple[bool, Dict]:
        """
        Realiza una llamada a la API externa de deep research
        
        Args:
            endpoint: Endpoint de la API sin la URL base (ej. "/search")
            method: Método HTTP (GET, POST, etc.)
            data: Datos para enviar en el cuerpo de la petición (para POST/PUT)
            params: Parámetros de consulta (para GET)
            
        Returns:
            Tupla (éxito, respuesta)
        """
        try:
            url = f"{DEEP_RESEARCH_API_URL}{endpoint}"
            headers = {
                "Content-Type": "application/json",
                "User-Agent": "SapiensAI-DeepResearch-Proxy/1.0"
            }
            
            log_info(f"Llamando a API DeepResearch: {method} {endpoint}", "deep_research.services")
            
            if method.upper() == "GET":
                response = requests.get(url, headers=headers, params=params, timeout=60)
            elif method.upper() == "POST":
                response = requests.post(url, headers=headers, json=data, timeout=60)
            else:
                return False, {"error": f"Método HTTP no soportado: {method}"}
                
            # Comprobar si la respuesta es exitosa
            if response.status_code >= 200 and response.status_code < 300:
                return True, response.json()
            else:
                log_error(
                    f"Error en API DeepResearch: {response.status_code}", 
                    Exception(f"Status: {response.status_code}, Body: {response.text}"), 
                    "deep_research.services"
                )
                return False, {"error": f"Error en la API externa: {response.status_code}", "details": response.text}
                
        except requests.RequestException as e:
            log_error(f"Error de conexión con API DeepResearch", e, "deep_research.services")
            return False, {"error": f"Error de conexión: {str(e)}"}
        except json.JSONDecodeError as e:
            log_error(f"Error al decodificar respuesta JSON", e, "deep_research.services")
            return False, {"error": f"Error al procesar respuesta: {str(e)}"}
        except Exception as e:
            log_error(f"Error inesperado al llamar a API DeepResearch", e, "deep_research.services")
            return False, {"error": f"Error inesperado: {str(e)}"}
    
    def search(self, provider: str, query: str, search_type: str = "web", **kwargs) -> Tuple[bool, Dict]:
        """
        Realiza una búsqueda en la web usando la API externa
        
        Args:
            provider: Proveedor a usar
            query: Consulta de búsqueda
            search_type: Tipo de búsqueda (web, image, video, news)
            **kwargs: Parámetros adicionales
            
        Returns:
            Tupla (éxito, resultados)
        """
        params = {
            "provider": provider,
            "q": query,
            "search_type": search_type,
            **kwargs
        }
        
        return self._call_deepresearch_api("/search", method="GET", params=params)
    
    def search_unified(self, provider: str, query: str, **kwargs) -> Tuple[bool, Dict]:
        """
        Realiza una búsqueda combinada (web, imagen, video) usando la API externa
        
        Args:
            provider: Proveedor a usar
            query: Consulta de búsqueda
            **kwargs: Parámetros adicionales
            
        Returns:
            Tupla (éxito, resultados)
        """
        params = {
            "provider": provider,
            "q": query,
            **kwargs
        }
        
        return self._call_deepresearch_api("/search/unified", method="GET", params=params)
    
    def extract_content(self, url: str) -> Tuple[bool, Dict]:
        """
        Extrae el contenido textual de una URL usando la API externa
        
        Args:
            url: URL de la cual extraer el texto
            
        Returns:
            Tupla (éxito, contenido)
        """
        data = {"url": url}
        return self._call_deepresearch_api("/extract", method="POST", data=data)
    
    def format_content(self, raw_content: str) -> Tuple[bool, Dict]:
        """
        Formatea el contenido crudo usando la API externa
        
        Args:
            raw_content: Contenido crudo a formatear
            
        Returns:
            Tupla (éxito, contenido formateado)
        """
        data = {"raw_content": raw_content}
        return self._call_deepresearch_api("/ai/format", method="POST", data=data)
    
    def suggest_questions(self, text_block: str) -> Tuple[bool, Dict]:
        """
        Genera preguntas sugeridas basadas en un texto usando la API externa
        
        Args:
            text_block: Bloque de texto para analizar
            
        Returns:
            Tupla (éxito, preguntas sugeridas)
        """
        data = {"text_block": text_block}
        return self._call_deepresearch_api("/ai/suggest-questions", method="POST", data=data)
    
    def ai_process(self, task: str, params: Dict) -> Tuple[bool, Dict]:
        """
        Procesa una tarea de IA para DeepResearch usando la API externa
        
        Args:
            task: Nombre de la tarea a realizar
            params: Parámetros específicos para la tarea
            
        Returns:
            Tupla (éxito, resultado)
        """
        data = {
            "task": task,
            "params": params
        }
        return self._call_deepresearch_api("/ai/process", method="POST", data=data)
    
    def structure_queries(self, topic: str, format_requirements: Optional[str] = None) -> Tuple[bool, List[str]]:
        """
        Genera consultas estructuradas para un tema usando la API externa
        
        Args:
            topic: Tema general de investigación
            format_requirements: Requisitos de formato para el informe final
            
        Returns:
            Tupla (éxito, lista de consultas)
        """
        params = {"topic": topic}
        if format_requirements:
            params["format_requirements"] = format_requirements
            
        success, result = self.ai_process("structure_queries", params)
        
        if success and "result" in result and "structured_queries" in result["result"]:
            return True, result["result"]["structured_queries"]
        
        return False, []
    
    def generate_plan(self, queries: List[str], format_requirements: Optional[str] = None) -> Tuple[bool, str]:
        """
        Genera un plan de investigación usando la API externa
        
        Args:
            queries: Lista de consultas estructuradas
            format_requirements: Requisitos de formato para el informe final
            
        Returns:
            Tupla (éxito, plan de investigación)
        """
        params = {"queries": queries}
        if format_requirements:
            params["format_requirements"] = format_requirements
            
        success, result = self.ai_process("generate_plan", params)
        
        if success and "result" in result and "research_plan" in result["result"]:
            return True, result["result"]["research_plan"]
        
        return False, ""
    
    def analyze_content(self, plan: str, extracted_data: List[Dict], iteration_counter: int, iteration_limit: int = 3) -> Tuple[bool, Dict]:
        """
        Analiza contenido web extraído usando la API externa
        
        Args:
            plan: Plan de investigación
            extracted_data: Lista de objetos con contenido web extraído
            iteration_counter: Contador de ciclos de búsqueda/análisis
            iteration_limit: Límite máximo de ciclos
            
        Returns:
            Tupla (éxito, resultado del análisis)
        """
        params = {
            "plan": plan,
            "extracted_data": extracted_data,
            "iteration_counter": iteration_counter,
            "iteration_limit": iteration_limit
        }
        
        success, result = self.ai_process("analyze_content", params)
        
        if success and "result" in result:
            return True, result["result"]
        
        return False, {}
    
    def synthesize_report(self, plan: str, relevant_data: List[Dict], stopped_by_limit: bool = False) -> Tuple[bool, str]:
        """
        Sintetiza un informe final basado en datos relevantes usando la API externa
        
        Args:
            plan: Plan de investigación
            relevant_data: Lista de objetos con contenido web relevante
            stopped_by_limit: Indica si el proceso se detuvo por límite de iteraciones
            
        Returns:
            Tupla (éxito, informe final)
        """
        params = {
            "plan": plan,
            "relevant_data": relevant_data,
            "stopped_by_limit": stopped_by_limit
        }
        
        success, result = self.ai_process("synthesize_report", params)
        
        if success and "result" in result and "final_report_text" in result["result"]:
            return True, result["result"]["final_report_text"]
        
        return False, ""
    
    def create_session(self, user_id: str, topic: str, format_requirements: Optional[str] = None, topic_id: Optional[str] = None) -> Tuple[bool, str]:
        """
        Crea una nueva sesión de investigación profunda
        
        Args:
            user_id: ID del usuario
            topic: Tema de investigación
            format_requirements: Requisitos de formato (opcional)
            topic_id: ID del tema asociado (opcional)
            
        Returns:
            Tupla (éxito, ID de la sesión o mensaje de error)
        """
        try:
            session = DeepResearchSession(
                user_id=user_id,
                topic=topic,
                format_requirements=format_requirements,
                topic_id=topic_id
            )
            
            result = self.collection.insert_one(session.to_dict())
            return True, str(result.inserted_id)
        except Exception as e:
            log_error(f"Error al crear sesión de investigación", e, "deep_research.services")
            return False, str(e)
    
    def get_session(self, session_id: str) -> Optional[Dict]:
        """
        Obtiene una sesión de investigación por su ID
        
        Args:
            session_id: ID de la sesión
            
        Returns:
            Datos de la sesión o None si no existe
        """
        try:
            session = self.collection.find_one({"_id": ObjectId(session_id)})
            
            if session:
                # Convertir ObjectId a string para serialización JSON
                session["_id"] = str(session["_id"])
                session["user_id"] = str(session["user_id"])
                if session.get("topic_id"):
                    session["topic_id"] = str(session["topic_id"])
                
            return session
        except Exception as e:
            log_error(f"Error al obtener sesión de investigación", e, "deep_research.services")
            return None
    
    def update_session(self, session_id: str, update_data: Dict) -> Tuple[bool, str]:
        """
        Actualiza una sesión de investigación
        
        Args:
            session_id: ID de la sesión
            update_data: Datos a actualizar
            
        Returns:
            Tupla (éxito, mensaje)
        """
        try:
            # Añadir timestamp de actualización
            update_data["updated_at"] = datetime.now()
            
            result = self.collection.update_one(
                {"_id": ObjectId(session_id)},
                {"$set": update_data}
            )
            
            if result.modified_count > 0:
                return True, "Sesión actualizada correctamente"
            return False, "No se encontró la sesión o no hubo cambios"
        except Exception as e:
            log_error(f"Error al actualizar sesión de investigación", e, "deep_research.services")
            return False, str(e)
    
    def delete_session(self, session_id: str) -> Tuple[bool, str]:
        """
        Elimina una sesión de investigación
        
        Args:
            session_id: ID de la sesión
            
        Returns:
            Tupla (éxito, mensaje)
        """
        try:
            result = self.collection.delete_one({"_id": ObjectId(session_id)})
            
            if result.deleted_count > 0:
                return True, "Sesión eliminada correctamente"
            return False, "No se encontró la sesión"
        except Exception as e:
            log_error(f"Error al eliminar sesión de investigación", e, "deep_research.services")
            return False, str(e)
    
    def update_topic_theory_content(self, topic_id: str, content: str) -> Tuple[bool, str]:
        """
        Actualiza el contenido teórico de un tema con el resultado de la investigación
        
        Args:
            topic_id: ID del tema
            content: Contenido teórico (informe final)
            
        Returns:
            Tupla (éxito, mensaje)
        """
        return self.topic_service.update_theory_content(topic_id, content) 