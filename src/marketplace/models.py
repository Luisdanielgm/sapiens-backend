from typing import Dict, List, Optional
from datetime import datetime
from enum import Enum
from dataclasses import dataclass

class PlanType(Enum):
    FREE = "free"
    PREMIUM = "premium"
    ENTERPRISE = "enterprise"

class PaymentProvider(Enum):
    STRIPE = "stripe"
    PAYPAL = "paypal"
    BINANCE = "binance"

class SubscriptionStatus(Enum):
    ACTIVE = "active"
    INACTIVE = "inactive"
    CANCELLED = "cancelled"
    EXPIRED = "expired"
    PENDING = "pending"

@dataclass
class PlanLimits:
    """Límites específicos para cada tipo de plan"""
    max_workspaces: int
    max_students_per_workspace: int
    max_study_plans: int
    max_templates: int
    max_evaluations_per_month: int
    ai_corrections_per_month: int
    storage_gb: int
    can_access_marketplace: bool
    can_create_public_content: bool
    priority_support: bool

class PlanModel:
    """Modelo para los planes de suscripción"""
    
    # Definición de límites por tipo de plan
    PLAN_LIMITS = {
        PlanType.FREE: PlanLimits(
            max_workspaces=1,
            max_students_per_workspace=30,
            max_study_plans=5,
            max_templates=10,
            max_evaluations_per_month=50,
            ai_corrections_per_month=20,
            storage_gb=1,
            can_access_marketplace=True,
            can_create_public_content=False,
            priority_support=False
        ),
        PlanType.PREMIUM: PlanLimits(
            max_workspaces=5,
            max_students_per_workspace=100,
            max_study_plans=50,
            max_templates=100,
            max_evaluations_per_month=500,
            ai_corrections_per_month=200,
            storage_gb=10,
            can_access_marketplace=True,
            can_create_public_content=True,
            priority_support=True
        ),
        PlanType.ENTERPRISE: PlanLimits(
            max_workspaces=-1,  # Ilimitado
            max_students_per_workspace=-1,  # Ilimitado
            max_study_plans=-1,  # Ilimitado
            max_templates=-1,  # Ilimitado
            max_evaluations_per_month=-1,  # Ilimitado
            ai_corrections_per_month=-1,  # Ilimitado
            storage_gb=100,
            can_access_marketplace=True,
            can_create_public_content=True,
            priority_support=True
        )
    }
    
    # Precios por plan (en centavos USD)
    PLAN_PRICES = {
        PlanType.FREE: 0,
        PlanType.PREMIUM: 2999,  # $29.99
        PlanType.ENTERPRISE: 9999  # $99.99
    }
    
    @staticmethod
    def get_plan_limits(plan_type: PlanType) -> PlanLimits:
        """Obtiene los límites para un tipo de plan específico"""
        return PlanModel.PLAN_LIMITS.get(plan_type)
    
    @staticmethod
    def get_plan_price(plan_type: PlanType) -> int:
        """Obtiene el precio para un tipo de plan específico"""
        return PlanModel.PLAN_PRICES.get(plan_type, 0)
    
    @staticmethod
    def to_dict(plan_type: PlanType) -> Dict:
        """Convierte la información del plan a diccionario"""
        limits = PlanModel.get_plan_limits(plan_type)
        price = PlanModel.get_plan_price(plan_type)
        
        return {
            "type": plan_type.value,
            "price_cents": price,
            "price_usd": price / 100,
            "limits": {
                "max_workspaces": limits.max_workspaces,
                "max_students_per_workspace": limits.max_students_per_workspace,
                "max_study_plans": limits.max_study_plans,
                "max_templates": limits.max_templates,
                "max_evaluations_per_month": limits.max_evaluations_per_month,
                "ai_corrections_per_month": limits.ai_corrections_per_month,
                "storage_gb": limits.storage_gb,
                "can_access_marketplace": limits.can_access_marketplace,
                "can_create_public_content": limits.can_create_public_content,
                "priority_support": limits.priority_support
            }
        }

class UserSubscription:
    """Modelo para las suscripciones de usuario"""
    
    def __init__(self, user_id: str, plan_type: PlanType, 
                 status: SubscriptionStatus = SubscriptionStatus.ACTIVE,
                 payment_provider: Optional[PaymentProvider] = None,
                 external_subscription_id: Optional[str] = None,
                 start_date: Optional[datetime] = None,
                 end_date: Optional[datetime] = None,
                 auto_renew: bool = True):
        self.user_id = user_id
        self.plan_type = plan_type
        self.status = status
        self.payment_provider = payment_provider
        self.external_subscription_id = external_subscription_id
        self.start_date = start_date or datetime.utcnow()
        self.end_date = end_date
        self.auto_renew = auto_renew
        self.created_at = datetime.utcnow()
        self.updated_at = datetime.utcnow()
    
    def to_dict(self) -> Dict:
        """Convierte la suscripción a diccionario para MongoDB"""
        return {
            "user_id": self.user_id,
            "plan_type": self.plan_type.value,
            "status": self.status.value,
            "payment_provider": self.payment_provider.value if self.payment_provider else None,
            "external_subscription_id": self.external_subscription_id,
            "start_date": self.start_date,
            "end_date": self.end_date,
            "auto_renew": self.auto_renew,
            "created_at": self.created_at,
            "updated_at": self.updated_at
        }
    
    @classmethod
    def from_dict(cls, data: Dict) -> 'UserSubscription':
        """Crea una instancia desde un diccionario de MongoDB"""
        subscription = cls(
            user_id=data["user_id"],
            plan_type=PlanType(data["plan_type"]),
            status=SubscriptionStatus(data["status"]),
            payment_provider=PaymentProvider(data["payment_provider"]) if data.get("payment_provider") else None,
            external_subscription_id=data.get("external_subscription_id"),
            start_date=data.get("start_date"),
            end_date=data.get("end_date"),
            auto_renew=data.get("auto_renew", True)
        )
        subscription.created_at = data.get("created_at", datetime.utcnow())
        subscription.updated_at = data.get("updated_at", datetime.utcnow())
        return subscription
    
    def is_active(self) -> bool:
        """Verifica si la suscripción está activa"""
        if self.status != SubscriptionStatus.ACTIVE:
            return False
        
        if self.end_date and datetime.utcnow() > self.end_date:
            return False
        
        return True
    
    def get_limits(self) -> PlanLimits:
        """Obtiene los límites del plan actual"""
        return PlanModel.get_plan_limits(self.plan_type)

class PaymentTransaction:
    """Modelo para transacciones de pago"""
    
    def __init__(self, user_id: str, plan_type: PlanType, 
                 payment_provider: PaymentProvider, amount_cents: int,
                 external_transaction_id: str, status: str = "pending"):
        self.user_id = user_id
        self.plan_type = plan_type
        self.payment_provider = payment_provider
        self.amount_cents = amount_cents
        self.external_transaction_id = external_transaction_id
        self.status = status
        self.created_at = datetime.utcnow()
        self.updated_at = datetime.utcnow()
    
    def to_dict(self) -> Dict:
        """Convierte la transacción a diccionario para MongoDB"""
        return {
            "user_id": self.user_id,
            "plan_type": self.plan_type.value,
            "payment_provider": self.payment_provider.value,
            "amount_cents": self.amount_cents,
            "external_transaction_id": self.external_transaction_id,
            "status": self.status,
            "created_at": self.created_at,
            "updated_at": self.updated_at
        }
    
    @classmethod
    def from_dict(cls, data: Dict) -> 'PaymentTransaction':
        """Crea una instancia desde un diccionario de MongoDB"""
        transaction = cls(
            user_id=data["user_id"],
            plan_type=PlanType(data["plan_type"]),
            payment_provider=PaymentProvider(data["payment_provider"]),
            amount_cents=data["amount_cents"],
            external_transaction_id=data["external_transaction_id"],
            status=data["status"]
        )
        transaction.created_at = data.get("created_at", datetime.utcnow())
        transaction.updated_at = data.get("updated_at", datetime.utcnow())
        return transaction