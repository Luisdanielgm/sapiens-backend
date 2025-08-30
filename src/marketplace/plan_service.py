from typing import Dict, List, Optional, Tuple
from datetime import datetime, timedelta
from src.shared.database import get_db
from bson import ObjectId
from .models import (
    PlanType, PlanModel, UserSubscription, SubscriptionStatus, 
    PaymentProvider, PaymentTransaction, PlanLimits
)

class PlanService:
    """Servicio para gestión de planes y verificación de límites"""
    
    def __init__(self):
        self.db = get_db()
        self.subscriptions_collection = self.db.user_subscriptions
        self.transactions_collection = self.db.payment_transactions
        self.workspaces_collection = self.db.workspaces
        self.study_plans_collection = self.db.study_plans_per_subject
        self.templates_collection = self.db.templates
        self.evaluations_collection = self.db.evaluations
    
    def get_user_subscription(self, user_id: str) -> Optional[UserSubscription]:
        """Obtiene la suscripción activa del usuario"""
        try:
            subscription_data = self.subscriptions_collection.find_one({
                "user_id": user_id,
                "status": SubscriptionStatus.ACTIVE.value
            })
            
            if subscription_data:
                return UserSubscription.from_dict(subscription_data)
            
            # Si no tiene suscripción, crear una gratuita por defecto
            return self.create_free_subscription(user_id)
            
        except Exception as e:
            print(f"Error getting user subscription: {e}")
            return None
    
    def create_free_subscription(self, user_id: str) -> UserSubscription:
        """Crea una suscripción gratuita para un usuario nuevo"""
        try:
            subscription = UserSubscription(
                user_id=user_id,
                plan_type=PlanType.FREE,
                status=SubscriptionStatus.ACTIVE
            )
            
            self.subscriptions_collection.insert_one(subscription.to_dict())
            return subscription
            
        except Exception as e:
            print(f"Error creating free subscription: {e}")
            return None
    
    def upgrade_subscription(self, user_id: str, new_plan: PlanType, 
                           payment_provider: PaymentProvider,
                           external_subscription_id: str) -> bool:
        """Actualiza la suscripción del usuario a un plan superior"""
        try:
            # Desactivar suscripción actual
            self.subscriptions_collection.update_many(
                {"user_id": user_id, "status": SubscriptionStatus.ACTIVE.value},
                {"$set": {"status": SubscriptionStatus.INACTIVE.value, "updated_at": datetime.utcnow()}}
            )
            
            # Crear nueva suscripción
            end_date = datetime.utcnow() + timedelta(days=30)  # Suscripción mensual
            new_subscription = UserSubscription(
                user_id=user_id,
                plan_type=new_plan,
                status=SubscriptionStatus.ACTIVE,
                payment_provider=payment_provider,
                external_subscription_id=external_subscription_id,
                end_date=end_date
            )
            
            self.subscriptions_collection.insert_one(new_subscription.to_dict())
            return True
            
        except Exception as e:
            print(f"Error upgrading subscription: {e}")
            return False
    
    def cancel_subscription(self, user_id: str) -> bool:
        """Cancela la suscripción del usuario (mantiene activa hasta el final del período)"""
        try:
            result = self.subscriptions_collection.update_one(
                {"user_id": user_id, "status": SubscriptionStatus.ACTIVE.value},
                {
                    "$set": {
                        "auto_renew": False,
                        "updated_at": datetime.utcnow()
                    }
                }
            )
            return result.modified_count > 0
            
        except Exception as e:
            print(f"Error canceling subscription: {e}")
            return False
    
    def check_workspace_limit(self, user_id: str) -> Tuple[bool, int, int]:
        """Verifica si el usuario puede crear más workspaces"""
        subscription = self.get_user_subscription(user_id)
        if not subscription:
            return False, 0, 0
        
        limits = subscription.get_limits()
        current_count = self.workspaces_collection.count_documents({"owner_id": user_id})
        
        if limits.max_workspaces == -1:  # Ilimitado
            return True, current_count, -1
        
        can_create = current_count < limits.max_workspaces
        return can_create, current_count, limits.max_workspaces
    
    def check_students_limit(self, user_id: str, workspace_id: str) -> Tuple[bool, int, int]:
        """Verifica si el usuario puede agregar más estudiantes al workspace"""
        subscription = self.get_user_subscription(user_id)
        if not subscription:
            return False, 0, 0
        
        limits = subscription.get_limits()
        
        # Contar estudiantes en el workspace (asumiendo que hay una colección de miembros)
        current_count = self.db.members.count_documents({
            "workspace_id": workspace_id,
            "role": "student"
        })
        
        if limits.max_students_per_workspace == -1:  # Ilimitado
            return True, current_count, -1
        
        can_add = current_count < limits.max_students_per_workspace
        return can_add, current_count, limits.max_students_per_workspace
    
    def check_study_plans_limit(self, user_id: str) -> Tuple[bool, int, int]:
        """Verifica si el usuario puede crear más planes de estudio"""
        subscription = self.get_user_subscription(user_id)
        if not subscription:
            return False, 0, 0
        
        limits = subscription.get_limits()
        current_count = self.study_plans_collection.count_documents({"author_id": user_id})
        
        if limits.max_study_plans == -1:  # Ilimitado
            return True, current_count, -1
        
        can_create = current_count < limits.max_study_plans
        return can_create, current_count, limits.max_study_plans
    
    def check_templates_limit(self, user_id: str) -> Tuple[bool, int, int]:
        """Verifica si el usuario puede crear más plantillas"""
        subscription = self.get_user_subscription(user_id)
        if not subscription:
            return False, 0, 0
        
        limits = subscription.get_limits()
        current_count = self.templates_collection.count_documents({"author_id": user_id})
        
        if limits.max_templates == -1:  # Ilimitado
            return True, current_count, -1
        
        can_create = current_count < limits.max_templates
        return can_create, current_count, limits.max_templates
    
    def check_monthly_evaluations_limit(self, user_id: str) -> Tuple[bool, int, int]:
        """Verifica si el usuario puede crear más evaluaciones este mes"""
        subscription = self.get_user_subscription(user_id)
        if not subscription:
            return False, 0, 0
        
        limits = subscription.get_limits()
        
        # Contar evaluaciones del mes actual
        start_of_month = datetime.utcnow().replace(day=1, hour=0, minute=0, second=0, microsecond=0)
        current_count = self.evaluations_collection.count_documents({
            "author_id": user_id,
            "created_at": {"$gte": start_of_month}
        })
        
        if limits.max_evaluations_per_month == -1:  # Ilimitado
            return True, current_count, -1
        
        can_create = current_count < limits.max_evaluations_per_month
        return can_create, current_count, limits.max_evaluations_per_month
    
    def check_ai_corrections_limit(self, user_id: str) -> Tuple[bool, int, int]:
        """Verifica si el usuario puede usar más correcciones de IA este mes"""
        subscription = self.get_user_subscription(user_id)
        if not subscription:
            return False, 0, 0
        
        limits = subscription.get_limits()
        
        # Contar correcciones de IA del mes actual
        start_of_month = datetime.utcnow().replace(day=1, hour=0, minute=0, second=0, microsecond=0)
        current_count = self.db.ai_corrections.count_documents({
            "user_id": user_id,
            "created_at": {"$gte": start_of_month}
        })
        
        if limits.ai_corrections_per_month == -1:  # Ilimitado
            return True, current_count, -1
        
        can_use = current_count < limits.ai_corrections_per_month
        return can_use, current_count, limits.ai_corrections_per_month
    
    def can_access_marketplace(self, user_id: str) -> bool:
        """Verifica si el usuario puede acceder al marketplace"""
        subscription = self.get_user_subscription(user_id)
        if not subscription:
            return False
        
        limits = subscription.get_limits()
        return limits.can_access_marketplace
    
    def can_create_public_content(self, user_id: str) -> bool:
        """Verifica si el usuario puede crear contenido público"""
        subscription = self.get_user_subscription(user_id)
        if not subscription:
            return False
        
        limits = subscription.get_limits()
        return limits.can_create_public_content
    
    def has_priority_support(self, user_id: str) -> bool:
        """Verifica si el usuario tiene soporte prioritario"""
        subscription = self.get_user_subscription(user_id)
        if not subscription:
            return False
        
        limits = subscription.get_limits()
        return limits.priority_support
    
    def get_user_limits_summary(self, user_id: str) -> Dict:
        """Obtiene un resumen completo de los límites del usuario"""
        subscription = self.get_user_subscription(user_id)
        if not subscription:
            return {}
        
        # Verificar todos los límites
        workspace_check = self.check_workspace_limit(user_id)
        study_plans_check = self.check_study_plans_limit(user_id)
        templates_check = self.check_templates_limit(user_id)
        evaluations_check = self.check_monthly_evaluations_limit(user_id)
        ai_corrections_check = self.check_ai_corrections_limit(user_id)
        
        return {
            "plan_type": subscription.plan_type.value,
            "status": subscription.status.value,
            "end_date": subscription.end_date.isoformat() if subscription.end_date else None,
            "limits": {
                "workspaces": {
                    "current": workspace_check[1],
                    "max": workspace_check[2],
                    "can_create": workspace_check[0]
                },
                "study_plans": {
                    "current": study_plans_check[1],
                    "max": study_plans_check[2],
                    "can_create": study_plans_check[0]
                },
                "templates": {
                    "current": templates_check[1],
                    "max": templates_check[2],
                    "can_create": templates_check[0]
                },
                "monthly_evaluations": {
                    "current": evaluations_check[1],
                    "max": evaluations_check[2],
                    "can_create": evaluations_check[0]
                },
                "monthly_ai_corrections": {
                    "current": ai_corrections_check[1],
                    "max": ai_corrections_check[2],
                    "can_use": ai_corrections_check[0]
                }
            },
            "permissions": {
                "can_access_marketplace": self.can_access_marketplace(user_id),
                "can_create_public_content": self.can_create_public_content(user_id),
                "has_priority_support": self.has_priority_support(user_id)
            }
        }
    
    def record_payment_transaction(self, user_id: str, plan_type: PlanType,
                                 payment_provider: PaymentProvider,
                                 external_transaction_id: str) -> str:
        """Registra una transacción de pago"""
        try:
            amount_cents = PlanModel.get_plan_price(plan_type)
            transaction = PaymentTransaction(
                user_id=user_id,
                plan_type=plan_type,
                payment_provider=payment_provider,
                amount_cents=amount_cents,
                external_transaction_id=external_transaction_id
            )
            
            result = self.transactions_collection.insert_one(transaction.to_dict())
            return str(result.inserted_id)
            
        except Exception as e:
            print(f"Error recording payment transaction: {e}")
            return None
    
    def complete_payment_transaction(self, transaction_id: str) -> bool:
        """Marca una transacción como completada y actualiza la suscripción"""
        try:
            # Obtener la transacción
            transaction_data = self.transactions_collection.find_one({"_id": ObjectId(transaction_id)})
            if not transaction_data:
                return False
            
            transaction = PaymentTransaction.from_dict(transaction_data)
            
            # Actualizar estado de la transacción
            self.transactions_collection.update_one(
                {"_id": ObjectId(transaction_id)},
                {"$set": {"status": "completed", "updated_at": datetime.utcnow()}}
            )
            
            # Actualizar suscripción del usuario
            return self.upgrade_subscription(
                transaction.user_id,
                transaction.plan_type,
                transaction.payment_provider,
                transaction.external_transaction_id
            )
            
        except Exception as e:
            print(f"Error completing payment transaction: {e}")
            return False
    
    def get_available_plans(self) -> List[Dict]:
        """Obtiene la lista de planes disponibles"""
        return [
            PlanModel.to_dict(PlanType.FREE),
            PlanModel.to_dict(PlanType.PREMIUM),
            PlanModel.to_dict(PlanType.ENTERPRISE)
        ]