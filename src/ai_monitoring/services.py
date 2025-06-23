from typing import Tuple, Optional, Dict, List, Any
from bson import ObjectId
from datetime import datetime, timedelta
import logging

from src.shared.database import get_db
from src.shared.standardization import VerificationBaseService, ErrorCodes
from src.shared.exceptions import AppException
from .models import AIApiCall, AIMonitoringConfig, AIMonitoringAlert

class AIMonitoringService(VerificationBaseService):
    """
    Servicio para el monitoreo de APIs de IA.
    Maneja el registro de llamadas, cálculo de costos y generación de alertas.
    """
    
    def __init__(self):
        super().__init__(collection_name="ai_api_calls")
        self.db = get_db()
        self.config_collection = self.db["ai_monitoring_config"]
        self.alerts_collection = self.db["ai_monitoring_alerts"]
        
    def initialize_config(self) -> bool:
        """
        Inicializa la configuración por defecto si no existe.
        """
        try:
            existing_config = self.config_collection.find_one()
            
            if not existing_config:
                default_config = AIMonitoringConfig()
                self.config_collection.insert_one(default_config.to_dict())
                logging.info("Configuración de monitoreo IA inicializada")
                return True
            return True
        except Exception as e:
            logging.error(f"Error al inicializar configuración: {str(e)}")
            return False
    
    def register_call(self, call_data: Dict) -> Tuple[bool, str]:
        """
        Registra una nueva llamada a API de IA.
        Verifica límites de presupuesto antes de permitir la llamada.
        
        Args:
            call_data: Datos de la llamada
            
        Returns:
            Tuple[bool, str]: (success, message/error)
        """
        try:
            # Verificar que callId sea único
            existing_call = self.collection.find_one({"call_id": call_data["call_id"]})
            if existing_call:
                return False, "El call_id ya existe"
            
            # Verificar límites de presupuesto
            config = self.get_monitoring_config()
            if not config:
                return False, "Configuración de monitoreo no encontrada"
            
            # Estimar costo basado en prompt_tokens
            estimated_cost = self._estimate_cost(
                call_data["provider"], 
                call_data["model_name"], 
                call_data["prompt_tokens"]
            )
            
            # Verificar límite diario global
            daily_usage = self.calculate_daily_usage()
            if daily_usage + estimated_cost > config["daily_budget"]:
                return False, "Límite de presupuesto diario excedido"
            
            # Verificar límite por proveedor
            provider_limits = config.get("provider_limits", {}).get(call_data["provider"])
            if provider_limits:
                provider_daily_usage = self.calculate_daily_usage(provider=call_data["provider"])
                if provider_daily_usage + estimated_cost > provider_limits.get("daily_budget", float('inf')):
                    return False, f"Límite diario de {call_data['provider']} excedido"
            
            # Verificar límite por usuario
            if call_data.get("user_id"):
                user_daily_usage = self.calculate_daily_usage(user_id=call_data["user_id"])
                if user_daily_usage + estimated_cost > config.get("user_daily_limit", float('inf')):
                    return False, "Límite diario del usuario excedido"
            
            # Crear llamada con success=False inicialmente
            ai_call = AIApiCall(
                call_id=call_data["call_id"],
                provider=call_data["provider"],
                model_name=call_data["model_name"],
                prompt_tokens=call_data["prompt_tokens"],
                user_id=call_data.get("user_id"),
                session_id=call_data.get("session_id"),
                feature=call_data.get("feature"),
                user_type=call_data.get("user_type"),
                endpoint=call_data.get("endpoint"),
                success=False  # Inicialmente False hasta que se complete
            )
            
            result = self.collection.insert_one(ai_call.to_dict())
            
            logging.info(f"Llamada registrada: {call_data['call_id']}")
            return True, call_data["call_id"]
            
        except Exception as e:
            logging.error(f"Error al registrar llamada: {str(e)}")
            return False, str(e)
    
    def update_call(self, call_id: str, update_data: Dict) -> Tuple[bool, str]:
        """
        Actualiza una llamada existente con los resultados.
        
        Args:
            call_id: ID de la llamada
            update_data: Datos a actualizar
            
        Returns:
            Tuple[bool, str]: (success, message/error)
        """
        try:
            # Buscar la llamada
            call = self.collection.find_one({"call_id": call_id})
            if not call:
                return False, "Llamada no encontrada"
            
            # Preparar datos de actualización
            update_fields = {
                "updated_at": datetime.now()
            }
            
            # Actualizar campos si están presentes
            for field in ["completion_tokens", "response_time", "success", 
                         "input_cost", "output_cost", "total_cost", "total_tokens", "error_message"]:
                if field in update_data:
                    update_fields[field] = update_data[field]
            
            # Actualizar en la base de datos
            result = self.collection.update_one(
                {"call_id": call_id},
                {"$set": update_fields}
            )
            
            if result.modified_count > 0:
                # Si la llamada fue exitosa, verificar alertas
                if update_data.get("success", False):
                    self._check_and_create_alerts()
                
                logging.info(f"Llamada actualizada: {call_id}")
                return True, "Llamada actualizada exitosamente"
            else:
                return False, "No se pudo actualizar la llamada"
                
        except Exception as e:
            logging.error(f"Error al actualizar llamada: {str(e)}")
            return False, str(e)
    
    def get_statistics(self, filters: Dict = None) -> Dict:
        """
        Obtiene estadísticas del uso de APIs de IA.
        
        Args:
            filters: Filtros para aplicar (startDate, endDate, provider, etc.)
            
        Returns:
            Dict: Estadísticas completas
        """
        try:
            # Construir query de match
            match_query = {"success": True}
            
            if filters:
                if filters.get("start_date"):
                    match_query["timestamp"] = {"$gte": filters["start_date"]}
                if filters.get("end_date"):
                    if "timestamp" in match_query:
                        match_query["timestamp"]["$lte"] = filters["end_date"]
                    else:
                        match_query["timestamp"] = {"$lte": filters["end_date"]}
                
                for field in ["provider", "user_id", "user_type", "feature"]:
                    if filters.get(field):
                        match_query[field] = filters[field]
            
            # Agregación completa usando $facet
            pipeline = [
                {"$match": match_query},
                {
                    "$facet": {
                        # Estadísticas generales
                        "general": [
                            {
                                "$group": {
                                    "_id": None,
                                    "total_calls": {"$sum": 1},
                                    "total_tokens": {"$sum": "$total_tokens"},
                                    "total_cost": {"$sum": "$total_cost"},
                                    "average_response_time": {"$avg": "$response_time"},
                                    "successful_calls": {"$sum": {"$cond": ["$success", 1, 0]}}
                                }
                            }
                        ],
                        
                        # Por proveedor
                        "by_provider": [
                            {
                                "$group": {
                                    "_id": "$provider",
                                    "calls": {"$sum": 1},
                                    "tokens": {"$sum": "$total_tokens"},
                                    "cost": {"$sum": "$total_cost"}
                                }
                            }
                        ],
                        
                        # Por modelo
                        "by_model": [
                            {
                                "$group": {
                                    "_id": "$model_name",
                                    "calls": {"$sum": 1},
                                    "tokens": {"$sum": "$total_tokens"},
                                    "cost": {"$sum": "$total_cost"}
                                }
                            }
                        ],
                        
                        # Por característica
                        "by_feature": [
                            {
                                "$group": {
                                    "_id": "$feature",
                                    "calls": {"$sum": 1},
                                    "tokens": {"$sum": "$total_tokens"},
                                    "cost": {"$sum": "$total_cost"}
                                }
                            }
                        ],
                        
                        # Por tipo de usuario
                        "by_user_type": [
                            {
                                "$group": {
                                    "_id": "$user_type",
                                    "calls": {"$sum": 1},
                                    "tokens": {"$sum": "$total_tokens"},
                                    "cost": {"$sum": "$total_cost"}
                                }
                            }
                        ],
                        
                        # Tendencias diarias
                        "daily_trends": [
                            {
                                "$group": {
                                    "_id": {"$dateToString": {"format": "%Y-%m-%d", "date": "$timestamp"}},
                                    "calls": {"$sum": 1},
                                    "tokens": {"$sum": "$total_tokens"},
                                    "cost": {"$sum": "$total_cost"}
                                }
                            },
                            {"$sort": {"_id": 1}}
                        ]
                    }
                }
            ]
            
            result = list(self.collection.aggregate(pipeline))[0]
            
            # Procesar resultados
            stats = {}
            
            # Estadísticas generales
            general = result["general"][0] if result["general"] else {}
            stats["total_calls"] = general.get("total_calls", 0)
            stats["total_tokens"] = general.get("total_tokens", 0)
            stats["total_cost"] = round(general.get("total_cost", 0), 4)
            stats["average_response_time"] = round(general.get("average_response_time", 0), 2)
            stats["success_rate"] = round(
                general.get("successful_calls", 0) / max(general.get("total_calls", 1), 1), 4
            )
            
            # Convertir agregaciones a diccionarios
            stats["by_provider"] = {item["_id"]: {
                "calls": item["calls"],
                "tokens": item["tokens"],
                "cost": round(item["cost"], 4)
            } for item in result["by_provider"] if item["_id"]}
            
            stats["by_model"] = {item["_id"]: {
                "calls": item["calls"],
                "tokens": item["tokens"],
                "cost": round(item["cost"], 4)
            } for item in result["by_model"] if item["_id"]}
            
            stats["by_feature"] = {item["_id"]: {
                "calls": item["calls"],
                "tokens": item["tokens"],
                "cost": round(item["cost"], 4)
            } for item in result["by_feature"] if item["_id"]}
            
            stats["by_user_type"] = {item["_id"]: {
                "calls": item["calls"],
                "tokens": item["tokens"],
                "cost": round(item["cost"], 4)
            } for item in result["by_user_type"] if item["_id"]}
            
            stats["daily_trends"] = [{
                "date": item["_id"],
                "calls": item["calls"],
                "tokens": item["tokens"],
                "cost": round(item["cost"], 4)
            } for item in result["daily_trends"]]
            
            return stats
            
        except Exception as e:
            logging.error(f"Error al obtener estadísticas: {str(e)}")
            return {}
    
    def get_active_alerts(self) -> List[Dict]:
        """
        Obtiene las alertas activas (no dismisseadas).
        
        Returns:
            List[Dict]: Lista de alertas activas
        """
        try:
            alerts = list(self.alerts_collection.find({
                "triggered": True,
                "dismissed": False
            }).sort("created_at", -1))
            
            # Convertir ObjectId a string
            for alert in alerts:
                alert["_id"] = str(alert["_id"])
                
            return alerts
            
        except Exception as e:
            logging.error(f"Error al obtener alertas: {str(e)}")
            return []
    
    def get_monitoring_config(self) -> Optional[Dict]:
        """
        Obtiene la configuración actual del monitoreo.
        
        Returns:
            Optional[Dict]: Configuración o None si no existe
        """
        try:
            config = self.config_collection.find_one()
            if config:
                config["_id"] = str(config["_id"])
            return config
        except Exception as e:
            logging.error(f"Error al obtener configuración: {str(e)}")
            return None
    
    def update_monitoring_config(self, update_data: Dict) -> Tuple[bool, str]:
        """
        Actualiza la configuración del monitoreo.
        
        Args:
            update_data: Datos a actualizar
            
        Returns:
            Tuple[bool, str]: (success, message/error)
        """
        try:
            # Agregar timestamp de actualización
            update_data["updated_at"] = datetime.now()
            
            # Buscar configuración existente
            config = self.config_collection.find_one()
            
            if config:
                # Actualizar configuración existente
                result = self.config_collection.update_one(
                    {"_id": config["_id"]},
                    {"$set": update_data}
                )
                
                if result.modified_count > 0:
                    logging.info("Configuración de monitoreo actualizada")
                    return True, "Configuración actualizada exitosamente"
                else:
                    return False, "No se realizaron cambios en la configuración"
            else:
                # Crear nueva configuración
                new_config = AIMonitoringConfig()
                config_dict = new_config.to_dict()
                config_dict.update(update_data)
                
                self.config_collection.insert_one(config_dict)
                logging.info("Nueva configuración de monitoreo creada")
                return True, "Configuración creada exitosamente"
                
        except Exception as e:
            logging.error(f"Error al actualizar configuración: {str(e)}")
            return False, str(e)
    
    def get_calls_paginated(self, page: int = 1, limit: int = 50, filters: Dict = None) -> Dict:
        """
        Obtiene llamadas de forma paginada para auditoría.
        
        Args:
            page: Número de página
            limit: Límite por página
            filters: Filtros opcionales
            
        Returns:
            Dict: Llamadas y información de paginación
        """
        try:
            # Validar límites
            limit = min(limit, 100)  # Máximo 100 por página
            skip = (page - 1) * limit
            
            # Construir query
            query = {}
            if filters:
                if filters.get("start_date"):
                    query["timestamp"] = {"$gte": filters["start_date"]}
                if filters.get("end_date"):
                    if "timestamp" in query:
                        query["timestamp"]["$lte"] = filters["end_date"]
                    else:
                        query["timestamp"] = {"$lte": filters["end_date"]}
                
                if filters.get("provider"):
                    query["provider"] = filters["provider"]
                if filters.get("success") is not None:
                    query["success"] = filters["success"]
            
            # Obtener llamadas
            calls = list(self.collection.find(query)
                        .sort("timestamp", -1)
                        .skip(skip)
                        .limit(limit))
            
            # Convertir ObjectId a string
            for call in calls:
                call["_id"] = str(call["_id"])
            
            # Contar total
            total = self.collection.count_documents(query)
            total_pages = (total + limit - 1) // limit
            
            return {
                "calls": calls,
                "pagination": {
                    "page": page,
                    "limit": limit,
                    "total": total,
                    "total_pages": total_pages,
                    "has_next": page < total_pages,
                    "has_prev": page > 1
                }
            }
            
        except Exception as e:
            logging.error(f"Error al obtener llamadas paginadas: {str(e)}")
            return {"calls": [], "pagination": {}}
    
    def cleanup_old_data(self, days_to_keep: int = 30, provider: Optional[str] = None) -> Tuple[bool, int]:
        """
        Elimina datos antiguos del sistema.
        
        Args:
            days_to_keep: Días a mantener
            provider: Proveedor específico (opcional)
            
        Returns:
            Tuple[bool, int]: (success, deleted_count)
        """
        try:
            cutoff_date = datetime.now() - timedelta(days=days_to_keep)
            
            query = {"timestamp": {"$lt": cutoff_date}}
            if provider:
                query["provider"] = provider
            
            result = self.collection.delete_many(query)
            
            logging.info(f"Limpieza completada: {result.deleted_count} registros eliminados")
            return True, result.deleted_count
            
        except Exception as e:
            logging.error(f"Error en limpieza de datos: {str(e)}")
            return False, 0
    
    def calculate_daily_usage(self, date: Optional[datetime] = None, 
                            provider: Optional[str] = None, 
                            user_id: Optional[str] = None) -> float:
        """
        Calcula el uso diario en USD.
        
        Args:
            date: Fecha a calcular (por defecto hoy)
            provider: Proveedor específico (opcional)
            user_id: Usuario específico (opcional)
            
        Returns:
            float: Costo total del día
        """
        try:
            if date is None:
                date = datetime.now()
            
            start_of_day = date.replace(hour=0, minute=0, second=0, microsecond=0)
            end_of_day = date.replace(hour=23, minute=59, second=59, microsecond=999999)
            
            query = {
                "timestamp": {"$gte": start_of_day, "$lte": end_of_day},
                "success": True
            }
            
            if provider:
                query["provider"] = provider
            if user_id:
                query["user_id"] = user_id
            
            result = list(self.collection.aggregate([
                {"$match": query},
                {
                    "$group": {
                        "_id": None,
                        "total_cost": {"$sum": "$total_cost"}
                    }
                }
            ]))
            
            return result[0]["total_cost"] if result else 0.0
            
        except Exception as e:
            logging.error(f"Error al calcular uso diario: {str(e)}")
            return 0.0
    
    def _estimate_cost(self, provider: str, model_name: str, prompt_tokens: int) -> float:
        """
        Estima el costo de una llamada basado en tokens de entrada.
        
        Args:
            provider: Proveedor de la API
            model_name: Nombre del modelo
            prompt_tokens: Tokens de entrada
            
        Returns:
            float: Costo estimado
        """
        # Precios estimados por 1K tokens (estos deberían estar en configuración)
        prices = {
            "gemini": {
                "gemini-1.5-flash": {"input": 0.000075, "output": 0.0003},
                "gemini-1.5-flash-002": {"input": 0.000075, "output": 0.0003},
                "gemini-2.0-flash": {"input": 0.00015, "output": 0.0006}
            },
            "openai": {
                "gpt-4": {"input": 0.03, "output": 0.06},
                "gpt-4-turbo": {"input": 0.01, "output": 0.03},
                "gpt-3.5-turbo": {"input": 0.0015, "output": 0.002}
            }
        }
        
        provider_prices = prices.get(provider, {})
        model_prices = provider_prices.get(model_name, {"input": 0.001, "output": 0.002})
        
        # Estimar costo de entrada + salida estimada (asumimos 1.5x los tokens de entrada)
        input_cost = (prompt_tokens / 1000) * model_prices["input"]
        estimated_output_tokens = prompt_tokens * 1.5
        output_cost = (estimated_output_tokens / 1000) * model_prices["output"]
        
        return input_cost + output_cost
    
    def _check_and_create_alerts(self):
        """
        Verifica si se deben crear alertas basadas en el uso actual.
        """
        try:
            config = self.get_monitoring_config()
            if not config:
                return
            
            current_usage = self.calculate_daily_usage()
            
            for threshold in config.get("alert_thresholds", []):
                limit = config["daily_budget"] * threshold
                
                if current_usage >= limit and not self._alert_exists("daily", limit):
                    self._create_alert({
                        "type": "daily",
                        "threshold": limit,
                        "current_usage": current_usage,
                        "triggered": True
                    })
                    
        except Exception as e:
            logging.error(f"Error al verificar alertas: {str(e)}")
    
    def _alert_exists(self, alert_type: str, threshold: float, provider: Optional[str] = None, 
                     user_id: Optional[str] = None) -> bool:
        """
        Verifica si ya existe una alerta para los parámetros dados.
        """
        try:
            today_start = datetime.now().replace(hour=0, minute=0, second=0, microsecond=0)
            
            query = {
                "type": alert_type,
                "threshold": threshold,
                "triggered": True,
                "dismissed": False,
                "created_at": {"$gte": today_start}
            }
            
            if provider:
                query["provider"] = provider
            if user_id:
                query["user_id"] = user_id
            
            alert = self.alerts_collection.find_one(query)
            return alert is not None
            
        except Exception as e:
            logging.error(f"Error al verificar existencia de alerta: {str(e)}")
            return False
    
    def _create_alert(self, alert_data: Dict):
        """
        Crea una nueva alerta en la base de datos.
        """
        try:
            # Generar ID único con microsegundos para evitar colisiones
            timestamp_str = datetime.now().strftime('%Y%m%d_%H%M%S_%f')
            alert_id = f"alert_{alert_data['type']}_{alert_data['threshold']}_{timestamp_str}"
            
            alert = AIMonitoringAlert(
                alert_id=alert_id,
                alert_type=alert_data["type"],
                threshold=alert_data["threshold"],
                current_usage=alert_data["current_usage"],
                provider=alert_data.get("provider"),
                model_name=alert_data.get("model_name"),
                user_id=alert_data.get("user_id"),
                triggered=alert_data.get("triggered", True)
            )
            
            self.alerts_collection.insert_one(alert.to_dict())
            logging.info(f"Alerta creada: {alert_id}")
            
        except Exception as e:
            logging.error(f"Error al crear alerta: {str(e)}") 