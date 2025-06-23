from typing import Optional, Dict, List
from bson import ObjectId
from datetime import datetime

class AIApiCall:
    """
    Modelo para registrar llamadas a APIs de IA.
    Registra cada petición a modelos de IA con información de tokens y costos.
    """
    def __init__(self,
                call_id: str,
                provider: str,
                model_name: str,
                prompt_tokens: int,
                user_id: Optional[str] = None,
                session_id: Optional[str] = None,
                completion_tokens: Optional[int] = None,
                total_tokens: Optional[int] = None,
                input_cost: Optional[float] = None,
                output_cost: Optional[float] = None,
                total_cost: Optional[float] = None,
                endpoint: Optional[str] = None,
                response_time: Optional[int] = None,
                success: bool = False,
                error_message: Optional[str] = None,
                feature: Optional[str] = None,
                user_type: Optional[str] = None):
        self.call_id = call_id
        self.timestamp = datetime.now()
        self.provider = provider
        self.model_name = model_name
        self.user_id = user_id
        self.session_id = session_id
        
        # Datos de tokens
        self.prompt_tokens = prompt_tokens
        self.completion_tokens = completion_tokens
        self.total_tokens = total_tokens
        
        # Datos de costos
        self.input_cost = input_cost
        self.output_cost = output_cost
        self.total_cost = total_cost
        
        # Metadatos
        self.endpoint = endpoint
        self.response_time = response_time
        self.success = success
        self.error_message = error_message
        
        # Contexto
        self.feature = feature
        self.user_type = user_type
        
        # Auditoría
        self.created_at = datetime.now()
        self.updated_at = datetime.now()
        
    def to_dict(self) -> dict:
        return {
            "call_id": self.call_id,
            "timestamp": self.timestamp,
            "provider": self.provider,
            "model_name": self.model_name,
            "user_id": self.user_id,
            "session_id": self.session_id,
            "prompt_tokens": self.prompt_tokens,
            "completion_tokens": self.completion_tokens,
            "total_tokens": self.total_tokens,
            "input_cost": self.input_cost,
            "output_cost": self.output_cost,
            "total_cost": self.total_cost,
            "endpoint": self.endpoint,
            "response_time": self.response_time,
            "success": self.success,
            "error_message": self.error_message,
            "feature": self.feature,
            "user_type": self.user_type,
            "created_at": self.created_at,
            "updated_at": self.updated_at
        }

class AIMonitoringConfig:
    """
    Modelo para la configuración del sistema de monitoreo.
    Solo debe existir UN documento de configuración global.
    """
    def __init__(self,
                daily_budget: float = 50.0,
                weekly_budget: float = 300.0,
                monthly_budget: float = 1000.0,
                provider_limits: Optional[Dict] = None,
                user_daily_limit: float = 5.0,
                user_weekly_limit: float = 25.0,
                user_monthly_limit: float = 80.0,
                alert_thresholds: Optional[List[float]] = None,
                log_level: str = "info",
                enable_detailed_logging: bool = True):
        
        self.daily_budget = daily_budget
        self.weekly_budget = weekly_budget
        self.monthly_budget = monthly_budget
        self.provider_limits = provider_limits or {
            "gemini": {
                "daily_budget": 30.0,
                "weekly_budget": 180.0,
                "monthly_budget": 600.0
            },
            "openai": {
                "daily_budget": 15.0,
                "weekly_budget": 90.0,
                "monthly_budget": 300.0
            }
        }
        self.user_daily_limit = user_daily_limit
        self.user_weekly_limit = user_weekly_limit
        self.user_monthly_limit = user_monthly_limit
        self.alert_thresholds = alert_thresholds or [0.5, 0.8, 0.95]
        self.log_level = log_level
        self.enable_detailed_logging = enable_detailed_logging
        self.created_at = datetime.now()
        self.updated_at = datetime.now()
        
    def to_dict(self) -> dict:
        return {
            "daily_budget": self.daily_budget,
            "weekly_budget": self.weekly_budget,
            "monthly_budget": self.monthly_budget,
            "provider_limits": self.provider_limits,
            "user_daily_limit": self.user_daily_limit,
            "user_weekly_limit": self.user_weekly_limit,
            "user_monthly_limit": self.user_monthly_limit,
            "alert_thresholds": self.alert_thresholds,
            "log_level": self.log_level,
            "enable_detailed_logging": self.enable_detailed_logging,
            "created_at": self.created_at,
            "updated_at": self.updated_at
        }

class AIMonitoringAlert:
    """
    Modelo para alertas del sistema de monitoreo.
    Se crean cuando se alcanzan umbrales de presupuesto.
    """
    def __init__(self,
                alert_id: str,
                alert_type: str,
                threshold: float,
                current_usage: float,
                provider: Optional[str] = None,
                model_name: Optional[str] = None,
                user_id: Optional[str] = None,
                triggered: bool = True,
                triggered_at: Optional[datetime] = None,
                dismissed: bool = False,
                dismissed_at: Optional[datetime] = None):
        
        self.alert_id = alert_id
        self.type = alert_type
        self.threshold = threshold
        self.current_usage = current_usage
        self.provider = provider
        self.model_name = model_name
        self.user_id = user_id
        self.triggered = triggered
        self.triggered_at = triggered_at or datetime.now()
        self.dismissed = dismissed
        self.dismissed_at = dismissed_at
        self.created_at = datetime.now()
        
    def to_dict(self) -> dict:
        return {
            "alert_id": self.alert_id,
            "type": self.type,
            "threshold": self.threshold,
            "current_usage": self.current_usage,
            "provider": self.provider,
            "model_name": self.model_name,
            "user_id": self.user_id,
            "triggered": self.triggered,
            "triggered_at": self.triggered_at,
            "dismissed": self.dismissed,
            "dismissed_at": self.dismissed_at,
            "created_at": self.created_at
        } 