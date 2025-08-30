from typing import Dict, Optional
from datetime import datetime, timezone
from flask import request
import json
from .paypal_service import PayPalService
from .binance_service import BinancePayService
from .plan_service import PlanService
from .models import PaymentProvider, PlanType, SubscriptionStatus
from src.shared.database import get_db

class WebhookService:
    """Servicio para manejar webhooks de confirmación de pagos"""
    
    def __init__(self):
        self.db = get_db()
        self.paypal_service = PayPalService()
        self.binance_service = BinancePayService()
        self.plan_service = PlanService()
        self.webhook_logs_collection = self.db.webhook_logs
    
    def log_webhook(self, provider: str, event_type: str, data: Dict, 
                   status: str = "received", error: str = None) -> str:
        """Registra un webhook en los logs"""
        try:
            log_entry = {
                "provider": provider,
                "event_type": event_type,
                "data": data,
                "status": status,
                "error": error,
                "created_at": datetime.now(timezone.utc),
                "processed_at": datetime.now(timezone.utc) if status == "processed" else None
            }
            
            result = self.webhook_logs_collection.insert_one(log_entry)
            return str(result.inserted_id)
            
        except Exception as e:
            print(f"Error logging webhook: {e}")
            return None
    
    def process_paypal_webhook(self, headers: Dict, body: str) -> Dict:
        """Procesa un webhook de PayPal"""
        try:
            # Verificar la firma del webhook
            if not self.paypal_service.verify_webhook_signature(headers, body):
                self.log_webhook("paypal", "unknown", {}, "failed", "Invalid signature")
                return {"status": "error", "message": "Invalid webhook signature"}
            
            # Parsear el evento
            event_data = json.loads(body)
            event_type = event_data.get('event_type')
            resource = event_data.get('resource', {})
            
            log_id = self.log_webhook("paypal", event_type, event_data)
            
            # Procesar según el tipo de evento
            if event_type == 'BILLING.SUBSCRIPTION.ACTIVATED':
                return self._handle_paypal_subscription_activated(resource, log_id)
            
            elif event_type == 'BILLING.SUBSCRIPTION.CANCELLED':
                return self._handle_paypal_subscription_cancelled(resource, log_id)
            
            elif event_type == 'BILLING.SUBSCRIPTION.SUSPENDED':
                return self._handle_paypal_subscription_suspended(resource, log_id)
            
            elif event_type == 'BILLING.SUBSCRIPTION.PAYMENT.FAILED':
                return self._handle_paypal_payment_failed(resource, log_id)
            
            elif event_type == 'PAYMENT.SALE.COMPLETED':
                return self._handle_paypal_payment_completed(resource, log_id)
            
            else:
                self._update_webhook_log(log_id, "ignored", f"Unhandled event type: {event_type}")
                return {"status": "ignored", "message": f"Event type {event_type} not handled"}
                
        except Exception as e:
            error_msg = f"Error processing PayPal webhook: {e}"
            print(error_msg)
            if 'log_id' in locals():
                self._update_webhook_log(log_id, "failed", error_msg)
            return {"status": "error", "message": error_msg}
    
    def process_binance_webhook(self, headers: Dict, body: str) -> Dict:
        """Procesa un webhook de Binance Pay"""
        try:
            # Verificar la firma del webhook
            if not self.binance_service.verify_webhook_signature(headers, body):
                self.log_webhook("binance", "unknown", {}, "failed", "Invalid signature")
                return {"status": "error", "message": "Invalid webhook signature"}
            
            # Parsear el evento
            event_data = json.loads(body)
            
            log_id = self.log_webhook("binance", "payment_notification", event_data)
            
            # Procesar la notificación
            notification_info = self.binance_service.process_webhook_notification(event_data)
            
            if not notification_info:
                self._update_webhook_log(log_id, "failed", "Invalid notification data")
                return {"status": "error", "message": "Invalid notification data"}
            
            # Manejar según el estado del pago
            status = notification_info.get('status')
            
            if status == 'PAY_SUCCESS':
                return self._handle_binance_payment_success(notification_info, log_id)
            
            elif status == 'PAY_CLOSED':
                return self._handle_binance_payment_closed(notification_info, log_id)
            
            elif status == 'PAY_FAILED':
                return self._handle_binance_payment_failed(notification_info, log_id)
            
            else:
                self._update_webhook_log(log_id, "ignored", f"Unhandled status: {status}")
                return {"status": "ignored", "message": f"Status {status} not handled"}
                
        except Exception as e:
            error_msg = f"Error processing Binance webhook: {e}"
            print(error_msg)
            if 'log_id' in locals():
                self._update_webhook_log(log_id, "failed", error_msg)
            return {"status": "error", "message": error_msg}
    
    def _handle_paypal_subscription_activated(self, resource: Dict, log_id: str) -> Dict:
        """Maneja la activación de una suscripción de PayPal"""
        try:
            subscription_id = resource.get('id')
            plan_id = resource.get('plan_id')
            subscriber_email = resource.get('subscriber', {}).get('email_address')
            
            # Buscar el usuario por email
            user = self.db.users.find_one({"email": subscriber_email})
            if not user:
                error_msg = f"User not found for email: {subscriber_email}"
                self._update_webhook_log(log_id, "failed", error_msg)
                return {"status": "error", "message": error_msg}
            
            user_id = str(user['_id'])
            
            # Determinar el tipo de plan basado en el plan_id
            plan_type = self._get_plan_type_from_paypal_plan_id(plan_id)
            if not plan_type:
                error_msg = f"Unknown PayPal plan ID: {plan_id}"
                self._update_webhook_log(log_id, "failed", error_msg)
                return {"status": "error", "message": error_msg}
            
            # Registrar la transacción
            transaction_id = self.plan_service.record_payment_transaction(
                user_id, plan_type, PaymentProvider.PAYPAL, subscription_id
            )
            
            # Actualizar la suscripción
            success = self.plan_service.upgrade_subscription(
                user_id, plan_type, PaymentProvider.PAYPAL, subscription_id
            )
            
            if success and transaction_id:
                self.plan_service.complete_payment_transaction(transaction_id)
                self._update_webhook_log(log_id, "processed", "Subscription activated successfully")
                return {"status": "success", "message": "Subscription activated"}
            else:
                error_msg = "Failed to update subscription"
                self._update_webhook_log(log_id, "failed", error_msg)
                return {"status": "error", "message": error_msg}
                
        except Exception as e:
            error_msg = f"Error handling PayPal subscription activation: {e}"
            self._update_webhook_log(log_id, "failed", error_msg)
            return {"status": "error", "message": error_msg}
    
    def _handle_paypal_subscription_cancelled(self, resource: Dict, log_id: str) -> Dict:
        """Maneja la cancelación de una suscripción de PayPal"""
        try:
            subscription_id = resource.get('id')
            
            # Buscar la suscripción en la base de datos
            subscription = self.db.user_subscriptions.find_one({
                "external_subscription_id": subscription_id,
                "payment_provider": PaymentProvider.PAYPAL.value
            })
            
            if not subscription:
                error_msg = f"Subscription not found: {subscription_id}"
                self._update_webhook_log(log_id, "failed", error_msg)
                return {"status": "error", "message": error_msg}
            
            # Cancelar la suscripción
            success = self.plan_service.cancel_subscription(subscription['user_id'])
            
            if success:
                self._update_webhook_log(log_id, "processed", "Subscription cancelled successfully")
                return {"status": "success", "message": "Subscription cancelled"}
            else:
                error_msg = "Failed to cancel subscription"
                self._update_webhook_log(log_id, "failed", error_msg)
                return {"status": "error", "message": error_msg}
                
        except Exception as e:
            error_msg = f"Error handling PayPal subscription cancellation: {e}"
            self._update_webhook_log(log_id, "failed", error_msg)
            return {"status": "error", "message": error_msg}
    
    def _handle_paypal_subscription_suspended(self, resource: Dict, log_id: str) -> Dict:
        """Maneja la suspensión de una suscripción de PayPal"""
        try:
            subscription_id = resource.get('id')
            
            # Actualizar el estado de la suscripción a suspendida
            result = self.db.user_subscriptions.update_one(
                {
                    "external_subscription_id": subscription_id,
                    "payment_provider": PaymentProvider.PAYPAL.value
                },
                {
                    "$set": {
                        "status": SubscriptionStatus.SUSPENDED.value,
                        "updated_at": datetime.now(timezone.utc)
                    }
                }
            )
            
            if result.modified_count > 0:
                self._update_webhook_log(log_id, "processed", "Subscription suspended successfully")
                return {"status": "success", "message": "Subscription suspended"}
            else:
                error_msg = f"Subscription not found: {subscription_id}"
                self._update_webhook_log(log_id, "failed", error_msg)
                return {"status": "error", "message": error_msg}
                
        except Exception as e:
            error_msg = f"Error handling PayPal subscription suspension: {e}"
            self._update_webhook_log(log_id, "failed", error_msg)
            return {"status": "error", "message": error_msg}
    
    def _handle_paypal_payment_failed(self, resource: Dict, log_id: str) -> Dict:
        """Maneja un fallo de pago de PayPal"""
        try:
            subscription_id = resource.get('id')
            
            # Registrar el fallo de pago
            self.db.payment_failures.insert_one({
                "subscription_id": subscription_id,
                "provider": PaymentProvider.PAYPAL.value,
                "reason": resource.get('status_change_note', 'Payment failed'),
                "created_at": datetime.now(timezone.utc)
            })
            
            self._update_webhook_log(log_id, "processed", "Payment failure recorded")
            return {"status": "success", "message": "Payment failure recorded"}
            
        except Exception as e:
            error_msg = f"Error handling PayPal payment failure: {e}"
            self._update_webhook_log(log_id, "failed", error_msg)
            return {"status": "error", "message": error_msg}
    
    def _handle_paypal_payment_completed(self, resource: Dict, log_id: str) -> Dict:
        """Maneja un pago completado de PayPal"""
        try:
            # Este evento se puede usar para registrar pagos individuales
            # o para confirmar renovaciones de suscripción
            
            self._update_webhook_log(log_id, "processed", "Payment completed event processed")
            return {"status": "success", "message": "Payment completed"}
            
        except Exception as e:
            error_msg = f"Error handling PayPal payment completion: {e}"
            self._update_webhook_log(log_id, "failed", error_msg)
            return {"status": "error", "message": error_msg}
    
    def _handle_binance_payment_success(self, notification_info: Dict, log_id: str) -> Dict:
        """Maneja un pago exitoso de Binance Pay"""
        try:
            user_id = notification_info['user_id']
            plan_type = notification_info['plan_type']
            binance_pay_id = notification_info['binance_pay_id']
            
            # Registrar la transacción
            transaction_id = self.plan_service.record_payment_transaction(
                user_id, plan_type, PaymentProvider.BINANCE, binance_pay_id
            )
            
            # Actualizar la suscripción
            success = self.plan_service.upgrade_subscription(
                user_id, plan_type, PaymentProvider.BINANCE, binance_pay_id
            )
            
            if success and transaction_id:
                self.plan_service.complete_payment_transaction(transaction_id)
                self._update_webhook_log(log_id, "processed", "Payment processed successfully")
                return {"status": "success", "message": "Payment processed"}
            else:
                error_msg = "Failed to process payment"
                self._update_webhook_log(log_id, "failed", error_msg)
                return {"status": "error", "message": error_msg}
                
        except Exception as e:
            error_msg = f"Error handling Binance payment success: {e}"
            self._update_webhook_log(log_id, "failed", error_msg)
            return {"status": "error", "message": error_msg}
    
    def _handle_binance_payment_closed(self, notification_info: Dict, log_id: str) -> Dict:
        """Maneja un pago cerrado/cancelado de Binance Pay"""
        try:
            # Registrar la cancelación del pago
            self.db.payment_cancellations.insert_one({
                "merchant_trade_no": notification_info['merchant_trade_no'],
                "binance_pay_id": notification_info['binance_pay_id'],
                "provider": PaymentProvider.BINANCE.value,
                "created_at": datetime.now(timezone.utc)
            })
            
            self._update_webhook_log(log_id, "processed", "Payment cancellation recorded")
            return {"status": "success", "message": "Payment cancellation recorded"}
            
        except Exception as e:
            error_msg = f"Error handling Binance payment closure: {e}"
            self._update_webhook_log(log_id, "failed", error_msg)
            return {"status": "error", "message": error_msg}
    
    def _handle_binance_payment_failed(self, notification_info: Dict, log_id: str) -> Dict:
        """Maneja un fallo de pago de Binance Pay"""
        try:
            # Registrar el fallo de pago
            self.db.payment_failures.insert_one({
                "merchant_trade_no": notification_info['merchant_trade_no'],
                "binance_pay_id": notification_info['binance_pay_id'],
                "provider": PaymentProvider.BINANCE.value,
                "reason": "Payment failed",
                "created_at": datetime.now(timezone.utc)
            })
            
            self._update_webhook_log(log_id, "processed", "Payment failure recorded")
            return {"status": "success", "message": "Payment failure recorded"}
            
        except Exception as e:
            error_msg = f"Error handling Binance payment failure: {e}"
            self._update_webhook_log(log_id, "failed", error_msg)
            return {"status": "error", "message": error_msg}
    
    def _get_plan_type_from_paypal_plan_id(self, plan_id: str) -> Optional[PlanType]:
        """Obtiene el tipo de plan basado en el ID del plan de PayPal"""
        import os
        
        if plan_id == os.getenv('PAYPAL_PREMIUM_PLAN_ID'):
            return PlanType.PREMIUM
        elif plan_id == os.getenv('PAYPAL_ENTERPRISE_PLAN_ID'):
            return PlanType.ENTERPRISE
        else:
            return None
    
    def _update_webhook_log(self, log_id: str, status: str, message: str = None):
        """Actualiza el estado de un log de webhook"""
        try:
            from bson import ObjectId
            
            update_data = {
                "status": status,
                "processed_at": datetime.now(timezone.utc)
            }
            
            if message:
                update_data["error" if status == "failed" else "message"] = message
            
            self.webhook_logs_collection.update_one(
                {"_id": ObjectId(log_id)},
                {"$set": update_data}
            )
            
        except Exception as e:
            print(f"Error updating webhook log: {e}")