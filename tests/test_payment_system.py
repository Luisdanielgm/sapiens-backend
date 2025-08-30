import unittest
from unittest.mock import Mock, patch
from datetime import datetime, timezone
import sys
import os

# Agregar el directorio src al path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', 'src'))

from src.marketplace.models import PlanType, PaymentProvider, SubscriptionStatus
from src.marketplace.plan_service import PlanService
from src.marketplace.paypal_service import PayPalService
from src.marketplace.binance_service import BinancePayService
from src.marketplace.webhook_service import WebhookService

class TestPlanService(unittest.TestCase):
    """Tests para PlanService"""
    
    def setUp(self):
        self.mock_db = Mock()
        self.plan_service = PlanService()
        self.plan_service.db = self.mock_db
        self.plan_service.subscriptions_collection = Mock()
        self.plan_service.transactions_collection = Mock()
        
        self.test_user_id = "test_user_123"
    
    def test_get_available_plans(self):
        """Test obtener planes disponibles"""
        plans = self.plan_service.get_available_plans()
        
        self.assertEqual(len(plans), 3)
        self.assertIn('free', [p['type'] for p in plans])
        self.assertIn('premium', [p['type'] for p in plans])
        self.assertIn('enterprise', [p['type'] for p in plans])
    
    def test_get_user_subscription_free_default(self):
        """Test obtener suscripción de usuario (default FREE)"""
        self.plan_service.subscriptions_collection.find_one.return_value = None
        self.plan_service.subscriptions_collection.insert_one.return_value = Mock(inserted_id="sub_123")
        
        subscription = self.plan_service.get_user_subscription(self.test_user_id)
        
        self.assertEqual(subscription.plan_type, PlanType.FREE)
        self.assertEqual(subscription.status, SubscriptionStatus.ACTIVE)
    
    def test_get_user_subscription_existing(self):
        """Test obtener suscripción existente"""
        mock_subscription = {
            'user_id': self.test_user_id,
            'plan_type': PlanType.PREMIUM.value,
            'status': SubscriptionStatus.ACTIVE.value,
            'payment_provider': PaymentProvider.PAYPAL.value,
            'created_at': datetime.now(timezone.utc),
            'updated_at': datetime.now(timezone.utc)
        }
        
        self.plan_service.subscriptions_collection.find_one.return_value = mock_subscription
        
        subscription = self.plan_service.get_user_subscription(self.test_user_id)
        
        self.assertEqual(subscription.plan_type, PlanType.PREMIUM)
        self.assertEqual(subscription.status, SubscriptionStatus.ACTIVE)
    
    def test_upgrade_subscription_new_user(self):
        """Test upgrade de suscripción para usuario nuevo"""
        self.plan_service.subscriptions_collection.update_many.return_value = Mock(modified_count=0)
        self.plan_service.subscriptions_collection.insert_one.return_value = Mock(inserted_id="new_id")
        
        result = self.plan_service.upgrade_subscription(
            self.test_user_id, PlanType.PREMIUM, PaymentProvider.PAYPAL, "paypal_sub_123"
        )
        
        self.assertTrue(result)
        self.plan_service.subscriptions_collection.insert_one.assert_called_once()
    
    def test_upgrade_subscription_existing_user(self):
        """Test upgrade de suscripción para usuario existente"""
        self.plan_service.subscriptions_collection.update_many.return_value = Mock(modified_count=1)
        self.plan_service.subscriptions_collection.insert_one.return_value = Mock(inserted_id="new_id")
        
        result = self.plan_service.upgrade_subscription(
            self.test_user_id, PlanType.PREMIUM, PaymentProvider.PAYPAL, "paypal_sub_123"
        )
        
        self.assertTrue(result)
        self.plan_service.subscriptions_collection.update_many.assert_called_once()
    
    def test_cancel_subscription(self):
        """Test cancelación de suscripción"""
        self.plan_service.subscriptions_collection.update_one.return_value = Mock(modified_count=1)
        
        result = self.plan_service.cancel_subscription(self.test_user_id)
        
        self.assertTrue(result)
        self.plan_service.subscriptions_collection.update_one.assert_called_once()
    
    def test_workspace_limit_free_plan(self):
        """Test límite de workspaces para plan FREE"""
        self.plan_service.subscriptions_collection = Mock()
        self.plan_service.workspaces_collection = Mock()
        self.plan_service.subscriptions_collection.find_one.return_value = None
        self.plan_service.workspaces_collection.count_documents.return_value = 0
        
        can_create, current, limit = self.plan_service.check_workspace_limit(self.test_user_id)
        
        self.assertEqual(current, 0)
        self.assertEqual(limit, 1)
        self.assertTrue(can_create)
    
    def test_workspace_limit_premium_plan(self):
        """Test límite de workspaces para plan PREMIUM"""
        mock_subscription = {
            'user_id': self.test_user_id,
            'plan_type': PlanType.PREMIUM.value,
            'status': SubscriptionStatus.ACTIVE.value,
            'created_at': datetime.utcnow(),
            'updated_at': datetime.utcnow()
        }
        
        self.plan_service.subscriptions_collection = Mock()
        self.plan_service.workspaces_collection = Mock()
        self.plan_service.subscriptions_collection.find_one.return_value = mock_subscription
        self.plan_service.workspaces_collection.count_documents.return_value = 3
        
        can_create, current, limit = self.plan_service.check_workspace_limit(self.test_user_id)
        
        self.assertEqual(current, 3)
        self.assertEqual(limit, 5)
        self.assertTrue(can_create)
    
    def test_record_payment_transaction(self):
        """Test registro de transacción de pago"""
        from bson import ObjectId
        mock_id = ObjectId()
        self.plan_service.transactions_collection.insert_one.return_value = Mock(inserted_id=mock_id)
        
        transaction_id = self.plan_service.record_payment_transaction(
            self.test_user_id, PlanType.PREMIUM, PaymentProvider.PAYPAL, "paypal_sub_123"
        )
        
        self.assertEqual(transaction_id, str(mock_id))
        self.plan_service.transactions_collection.insert_one.assert_called_once()

class TestPayPalService(unittest.TestCase):
    """Tests para PayPalService"""
    
    def setUp(self):
        self.paypal_service = PayPalService()
        self.test_user_id = "test_user_123"
    
    @patch('marketplace.paypal_service.requests.post')
    def test_get_access_token_success(self, mock_post):
        """Test obtener token de acceso exitoso"""
        mock_response = Mock()
        mock_response.status_code = 200
        mock_response.json.return_value = {
            'access_token': 'test_token_123',
            'expires_in': 3600
        }
        mock_post.return_value = mock_response
        
        token = self.paypal_service.get_access_token()
        
        self.assertEqual(token, 'test_token_123')
    
    @patch('marketplace.paypal_service.requests.post')
    def test_get_access_token_failure(self, mock_post):
        """Test fallo al obtener token de acceso"""
        mock_response = Mock()
        mock_response.status_code = 401
        mock_post.return_value = mock_response
        
        token = self.paypal_service.get_access_token()
        
        self.assertIsNone(token)
    
    @patch.object(PayPalService, 'get_access_token')
    @patch('marketplace.paypal_service.requests.post')
    def test_create_subscription_success(self, mock_post, mock_get_token):
        """Test crear suscripción exitosa"""
        mock_get_token.return_value = 'test_token'
        
        mock_response = Mock()
        mock_response.status_code = 201
        mock_response.json.return_value = {
            'id': 'subscription_123',
            'status': 'APPROVAL_PENDING',
            'links': [{
                'href': 'https://paypal.com/approve',
                'rel': 'approve'
            }]
        }
        mock_post.return_value = mock_response
        
        subscription = self.paypal_service.create_subscription(
             plan_id="P-123",
             user_email="test@example.com",
             return_url="https://example.com/success",
             cancel_url="https://example.com/cancel"
         )
        
        self.assertIsNotNone(subscription)
        self.assertEqual(subscription['subscription_id'], 'subscription_123')
    
    def test_verify_webhook_signature_invalid_headers(self):
        """Test verificación de firma de webhook con headers inválidos"""
        headers = {}
        body = '{"test": "data"}'
        
        result = self.paypal_service.verify_webhook_signature(headers, body)
        
        self.assertFalse(result)

class TestBinancePayService(unittest.TestCase):
    """Tests para BinancePayService"""
    
    def setUp(self):
        self.binance_service = BinancePayService()
        self.test_user_id = "test_user_123"
    
    def test_generate_signature(self):
        """Test generación de firma"""
        timestamp = "1234567890"
        nonce = "test_nonce"
        body = '{"test": "data"}'
        
        # Mock the secret key for testing
        self.binance_service.secret_key = 'test_secret_key'
        
        signature = self.binance_service._generate_signature(timestamp, nonce, body)
        
        self.assertIsNotNone(signature)
        self.assertIsInstance(signature, str)
        self.assertGreater(len(signature), 0)
    
    @patch('src.marketplace.binance_service.PlanModel.to_dict')
    @patch('src.marketplace.binance_service.requests.post')
    def test_create_order_success(self, mock_post, mock_plan_dict):
        # Mock secret key
        self.binance_service.secret_key = 'test_secret_key'
        
        # Mock plan info
        mock_plan_dict.return_value = {
            'name': 'Premium',
            'price_cents': 999
        }
        
        # Mock successful response
        mock_response = Mock()
        mock_response.status_code = 200
        mock_response.json.return_value = {
            'status': 'SUCCESS',
            'data': {
                'prepayId': 'test_prepay_id',
                'checkoutUrl': 'https://test.binance.com/checkout'
            }
        }
        mock_post.return_value = mock_response
        
        result = self.binance_service.create_order(
            plan_type=PlanType.PREMIUM,
            user_id="test_user",
            user_email="test@example.com",
            return_url="https://example.com/return",
            cancel_url="https://example.com/cancel"
        )
        
        self.assertIsNotNone(result)
        self.assertEqual(result['prepay_id'], 'test_prepay_id')
    
    def test_verify_webhook_signature_missing_headers(self):
        """Test verificación de firma de webhook con headers faltantes"""
        headers = {}
        body = '{"test": "data"}'
        
        result = self.binance_service.verify_webhook_signature(headers, body)
        
        self.assertFalse(result)

class TestWebhookService(unittest.TestCase):
    """Tests para WebhookService"""
    
    def setUp(self):
        self.webhook_service = WebhookService()
        self.webhook_service.db = Mock()
        self.webhook_service.webhook_logs_collection = Mock()
        self.webhook_service.paypal_service = Mock()
        self.webhook_service.binance_service = Mock()
        self.webhook_service.plan_service = Mock()
    
    def test_log_webhook_success(self):
        """Test logging de webhook exitoso"""
        self.webhook_service.webhook_logs_collection.insert_one.return_value = Mock(inserted_id="log_123")
        
        log_id = self.webhook_service.log_webhook(
            "paypal", "subscription.activated", {"test": "data"}, "received"
        )
        
        self.assertEqual(log_id, "log_123")
        self.webhook_service.webhook_logs_collection.insert_one.assert_called_once()
    
    def test_process_paypal_webhook_invalid_signature(self):
        """Test procesamiento de webhook de PayPal con firma inválida"""
        self.webhook_service.paypal_service.verify_webhook_signature.return_value = False
        
        headers = {'test': 'header'}
        body = '{"event_type": "test"}'
        
        result = self.webhook_service.process_paypal_webhook(headers, body)
        
        self.assertEqual(result['status'], 'error')
        self.assertIn('Invalid webhook signature', result['message'])
    
    def test_process_binance_webhook_invalid_signature(self):
        """Test procesamiento de webhook de Binance con firma inválida"""
        self.webhook_service.binance_service.verify_webhook_signature.return_value = False
        
        headers = {'test': 'header'}
        body = '{"test": "data"}'
        
        result = self.webhook_service.process_binance_webhook(headers, body)
        
        self.assertEqual(result['status'], 'error')
        self.assertIn('Invalid webhook signature', result['message'])

class TestPaymentSystemIntegration(unittest.TestCase):
    """Tests de integración del sistema de pagos"""
    
    def setUp(self):
        self.plan_service = PlanService()
        self.paypal_service = PayPalService()
        self.binance_service = BinancePayService()
        self.webhook_service = WebhookService()
        
        # Mock de la base de datos
        self.mock_db = Mock()
        self.plan_service.db = self.mock_db
        self.webhook_service.db = self.mock_db
    
    def test_complete_payment_flow_paypal(self):
        """Test flujo completo de pago con PayPal"""
        user_id = "test_user_123"
        plan_type = PlanType.PREMIUM
        
        # Mock de servicios
        self.plan_service.subscriptions_collection = Mock()
        self.plan_service.transactions_collection = Mock()
        
        # Simular creación de suscripción
        self.plan_service.subscriptions_collection.find_one.return_value = None
        self.plan_service.subscriptions_collection.insert_one.return_value = Mock(inserted_id="sub_123")
        self.plan_service.transactions_collection.insert_one.return_value = Mock(inserted_id="trans_123")
        
        # Test upgrade de suscripción
        result = self.plan_service.upgrade_subscription(
            user_id, plan_type, PaymentProvider.PAYPAL, "paypal_sub_123"
        )
        
        self.assertTrue(result)
        
        # Test registro de transacción
        transaction_id = self.plan_service.record_payment_transaction(
            user_id, plan_type, PaymentProvider.PAYPAL, "paypal_sub_123"
        )
        
        self.assertEqual(transaction_id, "trans_123")
    
    def test_plan_limits_enforcement(self):
        """Test aplicación de límites según el plan"""
        user_id = "test_user_123"
        
        # Mock para plan FREE
        self.plan_service.subscriptions_collection = Mock()
        self.plan_service.subscriptions_collection.find_one.return_value = None
        
        # Mock collections for integration test
        self.plan_service.subscriptions_collection = Mock()
        self.plan_service.transactions_collection = Mock()
        self.plan_service.workspaces_collection = Mock()
        self.plan_service.study_plans_collection = Mock()
        
        # Mock user subscription (FREE plan)
        self.plan_service.subscriptions_collection.find_one.return_value = None
        self.plan_service.subscriptions_collection.insert_one.return_value = Mock(inserted_id="sub_123")
        self.plan_service.workspaces_collection.count_documents.return_value = 2
        self.plan_service.study_plans_collection.count_documents.return_value = 1
        
        # Verificar límites de plan FREE
        self.plan_service.subscriptions_collection.find_one.return_value = None
        self.plan_service.workspaces_collection.count_documents.return_value = 0
        self.plan_service.study_plans_collection.count_documents.return_value = 2
        
        can_create_workspace, current_workspaces, max_workspaces = self.plan_service.check_workspace_limit(user_id)
        can_create_study_plan, current_study_plans, max_study_plans = self.plan_service.check_study_plans_limit(user_id)
        
        self.assertEqual(current_workspaces, 0)
        self.assertEqual(max_workspaces, 1)
        self.assertTrue(can_create_workspace)
        
        self.assertEqual(current_study_plans, 2)
        self.assertEqual(max_study_plans, 5)
        self.assertTrue(can_create_study_plan)
        
        # Mock para plan PREMIUM
        mock_premium_subscription = {
            'user_id': user_id,
            'plan_type': PlanType.PREMIUM.value,
            'status': SubscriptionStatus.ACTIVE.value,
            'created_at': datetime.now(timezone.utc),
            'updated_at': datetime.now(timezone.utc)
        }
        self.plan_service.subscriptions_collection.find_one.return_value = mock_premium_subscription
        self.plan_service.workspaces_collection.count_documents.return_value = 3
        self.plan_service.study_plans_collection.count_documents.return_value = 8
        
        # Verificar límites de plan PREMIUM
        can_create_workspace, current_workspaces, max_workspaces = self.plan_service.check_workspace_limit(user_id)
        can_create_study_plan, current_study_plans, max_study_plans = self.plan_service.check_study_plans_limit(user_id)
        
        self.assertEqual(current_workspaces, 3)
        self.assertEqual(max_workspaces, 5)
        self.assertTrue(can_create_workspace)
        
        self.assertEqual(current_study_plans, 8)
        self.assertEqual(max_study_plans, 50)
        self.assertTrue(can_create_study_plan)

if __name__ == '__main__':
    # Configurar variables de entorno para tests
    os.environ['PAYPAL_CLIENT_ID'] = 'test_client_id'
    os.environ['PAYPAL_CLIENT_SECRET'] = 'test_client_secret'
    os.environ['BINANCE_API_KEY'] = 'test_api_key'
    os.environ['BINANCE_SECRET_KEY'] = 'test_secret_key'
    
    unittest.main(verbosity=2)