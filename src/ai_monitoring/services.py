from typing import Tuple, Optional, Dict, List, Any
from bson import ObjectId
from datetime import datetime, timedelta
import logging

from src.shared.database import get_db
from src.shared.standardization import VerificationBaseService, ErrorCodes
from src.shared.exceptions import AppException
from .models import AICall, AIMonitoringConfig, AIMonitoringAlert, AIApiCall

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
            ai_call_data = {
                "call_id": call_data["call_id"],
                "provider": call_data["provider"],
                "model_name": call_data["model_name"],
                "prompt_tokens": call_data.get("prompt_tokens"),
                "user_id": call_data.get("user_id"),
                "session_id": call_data.get("session_id"),
                "feature": call_data.get("feature"),
                "user_type": call_data.get("user_type"),
                "origin": call_data.get("origin"),
                "endpoint": call_data.get("endpoint"),
                "success": None  # Usar None para estado pendiente
            }
            
            # Usar el modelo Pydantic para validar y crear el diccionario
            ai_call = AICall(**ai_call_data)
            
            result = self.collection.insert_one(ai_call.model_dump())
            
            logging.info(f"Llamada registrada: {call_data['call_id']}")
            return True, call_data["call_id"]
            
        except Exception as e:
            logging.error(f"Error al registrar llamada: {str(e)}")
            return False, str(e)
    
    def update_call(self, call_id: str, update_data: Dict) -> Tuple[bool, str]:
        """
        Actualiza una llamada existente con los resultados.
        
        DEPRECADO: Use update_call_secure() para mayor seguridad.
        
        Args:
            call_id: ID de la llamada
            update_data: Datos a actualizar
            
        Returns:
            Tuple[bool, str]: (success, message/error)
        """
        # Redireccionar al método seguro como admin para mantener compatibilidad
        return self.update_call_secure(call_id, update_data, is_admin=True)
    
    def update_call_secure(self, call_id: str, update_data: Dict, is_admin: bool = False) -> Tuple[bool, str]:
        """
        Actualiza una llamada existente con los resultados.
        Los costos se calculan automáticamente en el servidor para TODOS los usuarios.
        
        Args:
            call_id: ID de la llamada
            update_data: Datos a actualizar (NO incluir campos de costo)
            is_admin: Si el usuario es administrador (parámetro mantenido para compatibilidad)
            
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
            
            # Campos seguros que cualquier usuario puede actualizar
            safe_fields = ["completion_tokens", "response_time", "success", "total_tokens", "error_message"]
            
            # Procesar solo campos seguros (sin campos de costo)
            for field in safe_fields:
                if field in update_data:
                    update_fields[field] = update_data[field]
            
            # SIEMPRE calcular costos automáticamente del lado del servidor
            calculated_costs = self._calculate_costs_server_side(call, update_data)
            update_fields.update(calculated_costs)
            
            logging.info(f"Llamada {call_id} actualizada con costos calculados automáticamente")
            
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
    
    def _calculate_costs_server_side(self, call: Dict, update_data: Dict) -> Dict:
        """
        Calcula los costos del lado del servidor para usuarios no-admin.
        
        Args:
            call: Documento de la llamada original
            update_data: Datos de actualización del usuario
            
        Returns:
            Dict: Campos de costo calculados
        """
        try:
            # Obtener tokens actualizados o usar los originales
            prompt_tokens = call.get("prompt_tokens", 0)
            completion_tokens = update_data.get("completion_tokens", call.get("completion_tokens", 0))
            
            # Solo calcular si tenemos tokens válidos
            if prompt_tokens > 0 or completion_tokens > 0:
                provider = call.get("provider", "")
                model_name = call.get("model_name", "")
                
                # Calcular costos usando la función existente
                total_estimated_cost = self._estimate_cost(provider, model_name, prompt_tokens)
                
                # Si tenemos completion_tokens, calcular costos más precisos
                if completion_tokens > 0:
                    # Obtener precios específicos del modelo
                    prices = self._get_model_prices()
                    provider_prices = prices.get(provider, {})
                    model_prices = provider_prices.get(model_name, {"input": 0.001, "output": 0.002})
                    
                    # Calcular costos precisos
                    input_cost = (prompt_tokens / 1000) * model_prices["input"]
                    output_cost = (completion_tokens / 1000) * model_prices["output"]
                    total_cost = input_cost + output_cost
                    
                    return {
                        "input_cost": round(input_cost, 6),
                        "output_cost": round(output_cost, 6),
                        "total_cost": round(total_cost, 6),
                        "total_tokens": prompt_tokens + completion_tokens
                    }
                else:
                    # Solo estimación basada en prompt_tokens
                    return {
                        "total_cost": round(total_estimated_cost, 6)
                    }
            
            return {}
            
        except Exception as e:
            logging.error(f"Error al calcular costos del servidor: {str(e)}")
            return {}
    
    def _get_model_prices(self) -> Dict:
        """
        Obtiene los precios actualizados de los modelos.
        En el futuro, esto podría venir de una base de datos o API externa.
        
        Returns:
            Dict: Estructura de precios por proveedor y modelo
        """
        # Precios base desde configuración
        base_prices = self._get_base_model_prices()
        
        # Buscar precios personalizados en configuración (si existen)
        custom_prices = self._get_custom_model_prices()
        
        # Combinar precios base con personalizados
        return self._merge_model_prices(base_prices, custom_prices)
    
    def _get_base_model_prices(self) -> Dict:
        """
        Obtiene los precios base de modelos desde configuración estática.
        """
        return {
            "gemini": {
                # Gemini 2.5 models (latest)
                "gemini-2.5-pro": {"input": 0.00125, "output": 0.01},  # <=200K tokens
                "gemini-2.5-pro-preview": {"input": 0.00125, "output": 0.01},
                "gemini-2.5-pro-preview-05-06": {"input": 0.00125, "output": 0.01},
                "gemini-2.5-flash": {"input": 0.0003, "output": 0.0025},
                "gemini-2.5-flash-preview": {"input": 0.0003, "output": 0.0025},
                "gemini-2.5-flash-preview-04-17": {"input": 0.0003, "output": 0.0025},
                "google/gemini-2.5-flash-preview": {"input": 0.0003, "output": 0.0025},
                "gemini-2.5-flash-lite": {"input": 0.0001, "output": 0.0004},
                "gemini-2.5-flash-lite-preview": {"input": 0.0001, "output": 0.0004},
                
                # Gemini 2.0 models 
                "gemini-2.0-flash": {"input": 0.00015, "output": 0.0006},
                "gemini-2.0-flash-preview": {"input": 0.00015, "output": 0.0006},
                "gemini-2.0-flash-lite": {"input": 0.000075, "output": 0.0003},
                "gemini-2.0-flash-thinking-exp-01-21": {"input": 0.00015, "output": 0.0030}, # Precio de salida elevado por "thinking"
                
                # Gemini 1.5 models (legacy but still supported)
                "gemini-1.5-flash": {"input": 0.000075, "output": 0.0003},
                "gemini-1.5-flash-002": {"input": 0.000075, "output": 0.0003},
                "gemini-1.5-flash-8b": {"input": 0.0000375, "output": 0.00015},
                "gemini-1.5-pro": {"input": 0.00125, "output": 0.005},
                "gemini-1.5-pro-002": {"input": 0.00125, "output": 0.005},
                "gemini-2.5-flash-preview-native-audio-dialog": {"input": 0.0005, "output": 0.002}, # Precios de texto para modelo de audio
            },
            "openai": {
                # GPT-4 family
                "gpt-4": {"input": 0.03, "output": 0.06},
                "gpt-4-turbo": {"input": 0.01, "output": 0.03},
                "gpt-4-turbo-preview": {"input": 0.01, "output": 0.03},
                "gpt-4o": {"input": 0.005, "output": 0.015},
                "gpt-4o-mini": {"input": 0.00015, "output": 0.0006},
                
                # GPT-3.5 family
                "gpt-3.5-turbo": {"input": 0.0015, "output": 0.002},
                "gpt-3.5-turbo-16k": {"input": 0.003, "output": 0.004},
                
                # O1 reasoning models
                "o1-preview": {"input": 0.015, "output": 0.06},
                "o1-mini": {"input": 0.003, "output": 0.012},
            },
            "openrouter": {
                "openai/o3-mini-high": {"input": 0.0011, "output": 0.0044},
            },
            "requesty": {
                "cline/o3-mini": {"input": 0.0011, "output": 0.0044},
            },
            "claude": {
                # Claude 3.5 family
                "claude-3-5-sonnet-20241022": {"input": 0.003, "output": 0.015},
                "claude-3-5-sonnet-20240620": {"input": 0.003, "output": 0.015},
                "claude-3-5-haiku-20241022": {"input": 0.0008, "output": 0.004},
                
                # Claude 3 family
                "claude-3-opus-20240229": {"input": 0.015, "output": 0.075},
                "claude-3-sonnet-20240229": {"input": 0.003, "output": 0.015},
                "claude-3-haiku-20240307": {"input": 0.00025, "output": 0.00125},
                
                # Legacy
                "claude-2": {"input": 0.008, "output": 0.024},
                "claude-instant-1.2": {"input": 0.00163, "output": 0.00551},
            }
        }
    
    def _get_custom_model_prices(self) -> Dict:
        """
        Obtiene precios personalizados desde la configuración de MongoDB.
        Permite sobrescribir precios base o agregar nuevos modelos.
        """
        try:
            config = self.config_collection.find_one()
            if config and "custom_model_prices" in config:
                return config["custom_model_prices"]
        except Exception as e:
            logging.warning(f"No se pudieron cargar precios personalizados: {str(e)}")
        
        return {}
    
    def _merge_model_prices(self, base_prices: Dict, custom_prices: Dict) -> Dict:
        """
        Combina precios base con precios personalizados.
        Los precios personalizados tienen prioridad.
        """
        merged_prices = base_prices.copy()
        
        for provider, models in custom_prices.items():
            if provider not in merged_prices:
                merged_prices[provider] = {}
            
            for model_name, pricing in models.items():
                merged_prices[provider][model_name] = pricing
                
        return merged_prices
    
    def add_custom_model_pricing(self, provider: str, model_name: str, input_price: float, output_price: float) -> Tuple[bool, str]:
        """
        Agrega o actualiza precios de un modelo específico en la configuración.
        
        Args:
            provider: Proveedor del modelo ('gemini', 'openai', 'claude')
            model_name: Nombre del modelo
            input_price: Precio por 1K tokens de entrada (USD)
            output_price: Precio por 1K tokens de salida (USD)
            
        Returns:
            Tuple[bool, str]: (success, message)
        """
        try:
            # Validar precios
            if input_price < 0 or output_price < 0:
                return False, "Los precios no pueden ser negativos"
                
            # Buscar configuración actual
            config = self.config_collection.find_one()
            if not config:
                return False, "Configuración de monitoreo no encontrada"
            
            # Inicializar estructura si no existe
            if "custom_model_prices" not in config:
                config["custom_model_prices"] = {}
            
            if provider not in config["custom_model_prices"]:
                config["custom_model_prices"][provider] = {}
            
            # Agregar/actualizar precio del modelo
            config["custom_model_prices"][provider][model_name] = {
                "input": input_price,
                "output": output_price,
                "updated_at": datetime.now().isoformat(),
                "added_by": "system"  # En el futuro podríamos rastrear quién agregó el modelo
            }
            
            # Guardar en base de datos
            result = self.config_collection.update_one(
                {"_id": config["_id"]},
                {"$set": {"custom_model_prices": config["custom_model_prices"]}}
            )
            
            if result.modified_count > 0:
                logging.info(f"Precio agregado para modelo {provider}/{model_name}: input=${input_price}, output=${output_price}")
                return True, f"Precio agregado exitosamente para {provider}/{model_name}"
            else:
                return False, "No se pudo guardar el precio del modelo"
                
        except Exception as e:
            logging.error(f"Error al agregar precio de modelo: {str(e)}")
            return False, str(e)
    
    def get_supported_models(self) -> Dict:
        """
        Obtiene la lista completa de modelos soportados con sus precios.
        
        Returns:
            Dict: Modelos organizados por proveedor con precios
        """
        try:
            all_prices = self._get_model_prices()
            supported_models = {}
            
            for provider, models in all_prices.items():
                supported_models[provider] = []
                for model_name, pricing in models.items():
                    supported_models[provider].append({
                        "model_name": model_name,
                        "input_price_per_1k": pricing["input"],
                        "output_price_per_1k": pricing["output"],
                        "status": "supported"
                    })
            
            return supported_models
            
        except Exception as e:
            logging.error(f"Error al obtener modelos soportados: {str(e)}")
            return {}
    
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
                        
                        # Por origen de llamada
                        "by_origin": [
                            {
                                "$group": {
                                    "_id": "$origin",
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
            
            stats["by_origin"] = {item["_id"]: {
                "calls": item["calls"],
                "tokens": item["tokens"],
                "cost": round(item["cost"], 4)
            } for item in result["by_origin"] if item["_id"]}
            
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
        # Obtenemos los precios desde la fuente única de verdad
        prices = self._get_model_prices()
        
        provider_prices = prices.get(provider, {})
        model_prices = provider_prices.get(model_name)

        if not model_prices:
            logging.warning(f"No se encontraron precios para el modelo '{model_name}' del proveedor '{provider}'. Usando precios por defecto.")
            model_prices = {"input": 0.001, "output": 0.002}
        
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