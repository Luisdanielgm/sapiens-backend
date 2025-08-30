import os
import hmac
import hashlib
import time
import requests
import json
from typing import Dict, Optional, List
from datetime import datetime
from decimal import Decimal
from .models import PlanType, PlanModel

class BinancePayService:
    """Servicio para integración con Binance Pay API"""
    
    def __init__(self):
        self.api_key = os.getenv('BINANCE_PAY_API_KEY')
        self.secret_key = os.getenv('BINANCE_PAY_SECRET_KEY')
        self.environment = os.getenv('BINANCE_PAY_ENVIRONMENT', 'sandbox')  # sandbox o production
        
        if self.environment == 'sandbox':
            self.base_url = 'https://bpay.binanceapi.com'
        else:
            self.base_url = 'https://bpay.binanceapi.com'
        
        self.merchant_id = os.getenv('BINANCE_PAY_MERCHANT_ID')
    
    def _generate_signature(self, timestamp: str, nonce: str, body: str) -> str:
        """Genera la firma HMAC-SHA512 requerida por Binance Pay"""
        payload = f"{timestamp}\n{nonce}\n{body}\n"
        signature = hmac.new(
            self.secret_key.encode('utf-8'),
            payload.encode('utf-8'),
            hashlib.sha512
        ).hexdigest().upper()
        return signature
    
    def _get_headers(self, body: str) -> Dict[str, str]:
        """Genera los headers necesarios para las peticiones a Binance Pay"""
        timestamp = str(int(time.time() * 1000))
        nonce = str(int(time.time() * 1000000))  # Nonce único
        signature = self._generate_signature(timestamp, nonce, body)
        
        return {
            'Content-Type': 'application/json',
            'BinancePay-Timestamp': timestamp,
            'BinancePay-Nonce': nonce,
            'BinancePay-Certificate-SN': self.api_key,
            'BinancePay-Signature': signature
        }
    
    def create_order(self, plan_type: PlanType, user_id: str, user_email: str,
                    return_url: str, cancel_url: str) -> Optional[Dict]:
        """Crea una orden de pago en Binance Pay"""
        try:
            if plan_type == PlanType.FREE:
                return None  # No se puede pagar por el plan gratuito
            
            plan_info = PlanModel.to_dict(plan_type)
            price_usd = plan_info['price_cents'] / 100  # Convertir centavos a dólares
            
            # Generar un ID único para la orden
            merchant_trade_no = f"sapiensai_{user_id}_{plan_type.value}_{int(time.time())}"
            
            order_data = {
                "env": {
                    "terminalType": "WEB"
                },
                "merchantTradeNo": merchant_trade_no,
                "orderAmount": price_usd,
                "currency": "USDT",  # Usar USDT como moneda base
                "goods": {
                    "goodsType": "02",  # Servicios virtuales
                    "goodsCategory": "Z000",  # Otros
                    "referenceGoodsId": f"sapiensai_plan_{plan_type.value}",
                    "goodsName": f"SapiensAI {plan_info['name']} Plan",
                    "goodsDetail": f"Suscripción mensual al plan {plan_info['name']} de SapiensAI"
                },
                "buyer": {
                    "referenceBuyerId": user_id,
                    "buyerEmail": user_email
                },
                "returnUrl": return_url,
                "cancelUrl": cancel_url,
                "webhookUrl": f"{os.getenv('BASE_URL', 'https://api.sapiensai.com')}/api/payments/binance/webhook"
            }
            
            body = json.dumps(order_data, separators=(',', ':'))
            headers = self._get_headers(body)
            
            url = f"{self.base_url}/binancepay/openapi/v2/order"
            response = requests.post(url, headers=headers, data=body)
            
            if response.status_code == 200:
                result = response.json()
                if result.get('status') == 'SUCCESS':
                    data = result.get('data', {})
                    return {
                        'order_id': merchant_trade_no,
                        'prepay_id': data.get('prepayId'),
                        'checkout_url': data.get('checkoutUrl'),
                        'qr_content': data.get('qrcodeLink'),
                        'deep_link': data.get('deeplink'),
                        'universal_url': data.get('universalUrl')
                    }
                else:
                    print(f"Binance Pay order creation failed: {result}")
                    return None
            else:
                print(f"Error creating Binance Pay order: {response.text}")
                return None
                
        except Exception as e:
            print(f"Exception creating Binance Pay order: {e}")
            return None
    
    def query_order(self, merchant_trade_no: str) -> Optional[Dict]:
        """Consulta el estado de una orden en Binance Pay"""
        try:
            query_data = {
                "merchantTradeNo": merchant_trade_no
            }
            
            body = json.dumps(query_data, separators=(',', ':'))
            headers = self._get_headers(body)
            
            url = f"{self.base_url}/binancepay/openapi/v2/order/query"
            response = requests.post(url, headers=headers, data=body)
            
            if response.status_code == 200:
                result = response.json()
                if result.get('status') == 'SUCCESS':
                    return result.get('data', {})
                else:
                    print(f"Binance Pay order query failed: {result}")
                    return None
            else:
                print(f"Error querying Binance Pay order: {response.text}")
                return None
                
        except Exception as e:
            print(f"Exception querying Binance Pay order: {e}")
            return None
    
    def close_order(self, merchant_trade_no: str) -> bool:
        """Cierra una orden en Binance Pay"""
        try:
            close_data = {
                "merchantTradeNo": merchant_trade_no
            }
            
            body = json.dumps(close_data, separators=(',', ':'))
            headers = self._get_headers(body)
            
            url = f"{self.base_url}/binancepay/openapi/order/close"
            response = requests.post(url, headers=headers, data=body)
            
            if response.status_code == 200:
                result = response.json()
                return result.get('status') == 'SUCCESS'
            else:
                print(f"Error closing Binance Pay order: {response.text}")
                return False
                
        except Exception as e:
            print(f"Exception closing Binance Pay order: {e}")
            return False
    
    def verify_webhook_signature(self, headers: Dict, body: str) -> bool:
        """Verifica la firma del webhook de Binance Pay"""
        try:
            timestamp = headers.get('BinancePay-Timestamp')
            nonce = headers.get('BinancePay-Nonce')
            signature = headers.get('BinancePay-Signature')
            
            if not all([timestamp, nonce, signature]):
                print("Missing required headers for Binance Pay webhook verification")
                return False
            
            expected_signature = self._generate_signature(timestamp, nonce, body)
            
            return hmac.compare_digest(signature, expected_signature)
                
        except Exception as e:
            print(f"Exception verifying Binance Pay webhook: {e}")
            return False
    
    def process_webhook_notification(self, notification_data: Dict) -> Optional[Dict]:
        """Procesa una notificación de webhook de Binance Pay"""
        try:
            # Extraer información relevante del webhook
            merchant_trade_no = notification_data.get('merchantTradeNo')
            binance_pay_id = notification_data.get('binancePayId')
            status = notification_data.get('status')
            order_amount = notification_data.get('orderAmount')
            currency = notification_data.get('currency')
            
            if not merchant_trade_no:
                print("Missing merchantTradeNo in Binance Pay webhook")
                return None
            
            # Parsear el merchant_trade_no para extraer información
            # Formato: sapiensai_{user_id}_{plan_type}_{timestamp}
            parts = merchant_trade_no.split('_')
            if len(parts) >= 4 and parts[0] == 'sapiensai':
                user_id = parts[1]
                plan_type_str = parts[2]
                
                try:
                    plan_type = PlanType(plan_type_str)
                except ValueError:
                    print(f"Invalid plan type in merchant_trade_no: {plan_type_str}")
                    return None
                
                return {
                    'user_id': user_id,
                    'plan_type': plan_type,
                    'merchant_trade_no': merchant_trade_no,
                    'binance_pay_id': binance_pay_id,
                    'status': status,
                    'amount': order_amount,
                    'currency': currency
                }
            else:
                print(f"Invalid merchant_trade_no format: {merchant_trade_no}")
                return None
                
        except Exception as e:
            print(f"Exception processing Binance Pay webhook: {e}")
            return None
    
    def create_refund(self, merchant_trade_no: str, refund_amount: float, 
                     refund_reason: str = "User requested refund") -> Optional[Dict]:
        """Crea un reembolso en Binance Pay"""
        try:
            refund_trade_no = f"refund_{merchant_trade_no}_{int(time.time())}"
            
            refund_data = {
                "merchantTradeNo": merchant_trade_no,
                "refundRequestId": refund_trade_no,
                "refundAmount": refund_amount,
                "refundReason": refund_reason
            }
            
            body = json.dumps(refund_data, separators=(',', ':'))
            headers = self._get_headers(body)
            
            url = f"{self.base_url}/binancepay/openapi/order/refund"
            response = requests.post(url, headers=headers, data=body)
            
            if response.status_code == 200:
                result = response.json()
                if result.get('status') == 'SUCCESS':
                    return result.get('data', {})
                else:
                    print(f"Binance Pay refund failed: {result}")
                    return None
            else:
                print(f"Error creating Binance Pay refund: {response.text}")
                return None
                
        except Exception as e:
            print(f"Exception creating Binance Pay refund: {e}")
            return None
    
    def get_supported_currencies(self) -> List[str]:
        """Obtiene las monedas soportadas por Binance Pay"""
        try:
            body = "{}"
            headers = self._get_headers(body)
            
            url = f"{self.base_url}/binancepay/openapi/currencies"
            response = requests.post(url, headers=headers, data=body)
            
            if response.status_code == 200:
                result = response.json()
                if result.get('status') == 'SUCCESS':
                    data = result.get('data', [])
                    return [currency.get('currency') for currency in data]
                else:
                    print(f"Failed to get Binance Pay currencies: {result}")
                    return ['USDT', 'BUSD', 'BNB']  # Fallback a monedas comunes
            else:
                print(f"Error getting Binance Pay currencies: {response.text}")
                return ['USDT', 'BUSD', 'BNB']  # Fallback
                
        except Exception as e:
            print(f"Exception getting Binance Pay currencies: {e}")
            return ['USDT', 'BUSD', 'BNB']  # Fallback
    
    def convert_usd_to_crypto(self, usd_amount: float, target_currency: str = 'USDT') -> float:
        """Convierte USD a criptomoneda usando la API de Binance"""
        try:
            # Para USDT, la conversión es 1:1 aproximadamente
            if target_currency == 'USDT':
                return usd_amount
            
            # Para otras monedas, usar la API de precios de Binance
            url = f"https://api.binance.com/api/v3/ticker/price?symbol={target_currency}USDT"
            response = requests.get(url)
            
            if response.status_code == 200:
                price_data = response.json()
                crypto_price = float(price_data['price'])
                return usd_amount / crypto_price
            else:
                print(f"Error getting {target_currency} price: {response.text}")
                return usd_amount  # Fallback
                
        except Exception as e:
            print(f"Exception converting USD to {target_currency}: {e}")
            return usd_amount  # Fallback