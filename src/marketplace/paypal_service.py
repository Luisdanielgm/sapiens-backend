import os
import requests
import json
from typing import Dict, Optional, List
from datetime import datetime
from .models import PlanType, PlanModel

class PayPalService:
    """Servicio para integración con PayPal API"""
    
    def __init__(self):
        self.client_id = os.getenv('PAYPAL_CLIENT_ID')
        self.client_secret = os.getenv('PAYPAL_CLIENT_SECRET')
        self.environment = os.getenv('PAYPAL_ENVIRONMENT', 'sandbox')  # sandbox o live
        
        if self.environment == 'sandbox':
            self.base_url = 'https://api-m.sandbox.paypal.com'
        else:
            self.base_url = 'https://api-m.paypal.com'
        
        self.access_token = None
        self.token_expires_at = None
    
    def get_access_token(self) -> Optional[str]:
        """Obtiene un token de acceso de PayPal"""
        try:
            # Verificar si el token actual sigue siendo válido
            if (self.access_token and self.token_expires_at and 
                datetime.utcnow() < self.token_expires_at):
                return self.access_token
            
            url = f"{self.base_url}/v1/oauth2/token"
            headers = {
                'Accept': 'application/json',
                'Accept-Language': 'en_US',
            }
            data = 'grant_type=client_credentials'
            
            response = requests.post(
                url, 
                headers=headers, 
                data=data,
                auth=(self.client_id, self.client_secret)
            )
            
            if response.status_code == 200:
                token_data = response.json()
                self.access_token = token_data['access_token']
                # El token expira en 'expires_in' segundos
                expires_in = token_data.get('expires_in', 3600)
                self.token_expires_at = datetime.utcnow().timestamp() + expires_in - 60  # 60s buffer
                return self.access_token
            else:
                print(f"Error getting PayPal access token: {response.text}")
                return None
                
        except Exception as e:
            print(f"Exception getting PayPal access token: {e}")
            return None
    
    def create_product(self, plan_type: PlanType) -> Optional[str]:
        """Crea un producto en PayPal para el plan especificado"""
        try:
            token = self.get_access_token()
            if not token:
                return None
            
            plan_info = PlanModel.to_dict(plan_type)
            
            url = f"{self.base_url}/v1/catalogs/products"
            headers = {
                'Content-Type': 'application/json',
                'Authorization': f'Bearer {token}',
                'Accept': 'application/json',
                'Prefer': 'return=representation'
            }
            
            product_data = {
                "name": f"SapiensAI {plan_info['name']} Plan",
                "description": f"Suscripción mensual al plan {plan_info['name']} de SapiensAI",
                "type": "SERVICE",
                "category": "SOFTWARE",
                "image_url": "https://sapiensai.com/logo.png",  # URL del logo
                "home_url": "https://sapiensai.com"
            }
            
            response = requests.post(url, headers=headers, json=product_data)
            
            if response.status_code == 201:
                product = response.json()
                return product['id']
            else:
                print(f"Error creating PayPal product: {response.text}")
                return None
                
        except Exception as e:
            print(f"Exception creating PayPal product: {e}")
            return None
    
    def create_subscription_plan(self, plan_type: PlanType, product_id: str) -> Optional[str]:
        """Crea un plan de suscripción en PayPal"""
        try:
            token = self.get_access_token()
            if not token:
                return None
            
            plan_info = PlanModel.to_dict(plan_type)
            price_usd = plan_info['price_cents'] / 100  # Convertir centavos a dólares
            
            url = f"{self.base_url}/v1/billing/plans"
            headers = {
                'Content-Type': 'application/json',
                'Authorization': f'Bearer {token}',
                'Accept': 'application/json',
                'Prefer': 'return=representation'
            }
            
            plan_data = {
                "product_id": product_id,
                "name": f"SapiensAI {plan_info['name']} Monthly",
                "description": f"Suscripción mensual al plan {plan_info['name']}",
                "status": "ACTIVE",
                "billing_cycles": [
                    {
                        "frequency": {
                            "interval_unit": "MONTH",
                            "interval_count": 1
                        },
                        "tenure_type": "REGULAR",
                        "sequence": 1,
                        "total_cycles": 0,  # 0 = infinito
                        "pricing_scheme": {
                            "fixed_price": {
                                "value": str(price_usd),
                                "currency_code": "USD"
                            }
                        }
                    }
                ],
                "payment_preferences": {
                    "auto_bill_outstanding": True,
                    "setup_fee": {
                        "value": "0",
                        "currency_code": "USD"
                    },
                    "setup_fee_failure_action": "CONTINUE",
                    "payment_failure_threshold": 3
                },
                "taxes": {
                    "percentage": "0",
                    "inclusive": False
                }
            }
            
            response = requests.post(url, headers=headers, json=plan_data)
            
            if response.status_code == 201:
                plan = response.json()
                return plan['id']
            else:
                print(f"Error creating PayPal subscription plan: {response.text}")
                return None
                
        except Exception as e:
            print(f"Exception creating PayPal subscription plan: {e}")
            return None
    
    def create_subscription(self, plan_id: str, user_email: str, 
                          return_url: str, cancel_url: str) -> Optional[Dict]:
        """Crea una suscripción en PayPal"""
        try:
            token = self.get_access_token()
            if not token:
                return None
            
            url = f"{self.base_url}/v1/billing/subscriptions"
            headers = {
                'Content-Type': 'application/json',
                'Authorization': f'Bearer {token}',
                'Accept': 'application/json',
                'Prefer': 'return=representation'
            }
            
            subscription_data = {
                "plan_id": plan_id,
                "start_time": datetime.utcnow().strftime('%Y-%m-%dT%H:%M:%SZ'),
                "subscriber": {
                    "email_address": user_email
                },
                "application_context": {
                    "brand_name": "SapiensAI",
                    "locale": "en-US",
                    "shipping_preference": "NO_SHIPPING",
                    "user_action": "SUBSCRIBE_NOW",
                    "payment_method": {
                        "payer_selected": "PAYPAL",
                        "payee_preferred": "IMMEDIATE_PAYMENT_REQUIRED"
                    },
                    "return_url": return_url,
                    "cancel_url": cancel_url
                }
            }
            
            response = requests.post(url, headers=headers, json=subscription_data)
            
            if response.status_code == 201:
                subscription = response.json()
                return {
                    'subscription_id': subscription['id'],
                    'status': subscription['status'],
                    'approval_url': next(
                        (link['href'] for link in subscription['links'] 
                         if link['rel'] == 'approve'), None
                    )
                }
            else:
                print(f"Error creating PayPal subscription: {response.text}")
                return None
                
        except Exception as e:
            print(f"Exception creating PayPal subscription: {e}")
            return None
    
    def get_subscription_details(self, subscription_id: str) -> Optional[Dict]:
        """Obtiene los detalles de una suscripción"""
        try:
            token = self.get_access_token()
            if not token:
                return None
            
            url = f"{self.base_url}/v1/billing/subscriptions/{subscription_id}"
            headers = {
                'Content-Type': 'application/json',
                'Authorization': f'Bearer {token}',
                'Accept': 'application/json'
            }
            
            response = requests.get(url, headers=headers)
            
            if response.status_code == 200:
                return response.json()
            else:
                print(f"Error getting PayPal subscription details: {response.text}")
                return None
                
        except Exception as e:
            print(f"Exception getting PayPal subscription details: {e}")
            return None
    
    def cancel_subscription(self, subscription_id: str, reason: str = "User requested cancellation") -> bool:
        """Cancela una suscripción en PayPal"""
        try:
            token = self.get_access_token()
            if not token:
                return False
            
            url = f"{self.base_url}/v1/billing/subscriptions/{subscription_id}/cancel"
            headers = {
                'Content-Type': 'application/json',
                'Authorization': f'Bearer {token}',
                'Accept': 'application/json'
            }
            
            cancel_data = {
                "reason": reason
            }
            
            response = requests.post(url, headers=headers, json=cancel_data)
            
            return response.status_code == 204
                
        except Exception as e:
            print(f"Exception canceling PayPal subscription: {e}")
            return False
    
    def verify_webhook_signature(self, headers: Dict, body: str) -> bool:
        """Verifica la firma del webhook de PayPal"""
        try:
            token = self.get_access_token()
            if not token:
                return False
            
            webhook_id = os.getenv('PAYPAL_WEBHOOK_ID')
            if not webhook_id:
                print("PayPal webhook ID not configured")
                return False
            
            url = f"{self.base_url}/v1/notifications/verify-webhook-signature"
            headers_to_send = {
                'Content-Type': 'application/json',
                'Authorization': f'Bearer {token}',
                'Accept': 'application/json'
            }
            
            verification_data = {
                "auth_algo": headers.get('PAYPAL-AUTH-ALGO'),
                "cert_id": headers.get('PAYPAL-CERT-ID'),
                "transmission_id": headers.get('PAYPAL-TRANSMISSION-ID'),
                "transmission_sig": headers.get('PAYPAL-TRANSMISSION-SIG'),
                "transmission_time": headers.get('PAYPAL-TRANSMISSION-TIME'),
                "webhook_id": webhook_id,
                "webhook_event": json.loads(body)
            }
            
            response = requests.post(url, headers=headers_to_send, json=verification_data)
            
            if response.status_code == 200:
                result = response.json()
                return result.get('verification_status') == 'SUCCESS'
            else:
                print(f"Error verifying PayPal webhook: {response.text}")
                return False
                
        except Exception as e:
            print(f"Exception verifying PayPal webhook: {e}")
            return False
    
    def setup_webhook(self, webhook_url: str) -> Optional[str]:
        """Configura un webhook en PayPal"""
        try:
            token = self.get_access_token()
            if not token:
                return None
            
            url = f"{self.base_url}/v1/notifications/webhooks"
            headers = {
                'Content-Type': 'application/json',
                'Authorization': f'Bearer {token}',
                'Accept': 'application/json'
            }
            
            webhook_data = {
                "url": webhook_url,
                "event_types": [
                    {"name": "BILLING.SUBSCRIPTION.ACTIVATED"},
                    {"name": "BILLING.SUBSCRIPTION.CANCELLED"},
                    {"name": "BILLING.SUBSCRIPTION.SUSPENDED"},
                    {"name": "BILLING.SUBSCRIPTION.PAYMENT.FAILED"},
                    {"name": "PAYMENT.SALE.COMPLETED"},
                    {"name": "PAYMENT.SALE.DENIED"}
                ]
            }
            
            response = requests.post(url, headers=headers, json=webhook_data)
            
            if response.status_code == 201:
                webhook = response.json()
                return webhook['id']
            else:
                print(f"Error setting up PayPal webhook: {response.text}")
                return None
                
        except Exception as e:
            print(f"Exception setting up PayPal webhook: {e}")
            return None
    
    def get_plan_id_for_type(self, plan_type: PlanType) -> Optional[str]:
        """Obtiene el ID del plan de PayPal para un tipo de plan específico"""
        # En un entorno real, estos IDs se almacenarían en la base de datos
        # o en variables de entorno después de crear los planes
        plan_ids = {
            PlanType.PREMIUM: os.getenv('PAYPAL_PREMIUM_PLAN_ID'),
            PlanType.ENTERPRISE: os.getenv('PAYPAL_ENTERPRISE_PLAN_ID')
        }
        return plan_ids.get(plan_type)