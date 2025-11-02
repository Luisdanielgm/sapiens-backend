from flask import Blueprint, jsonify, request, current_app
from src.shared.standardization import APIRoute
from .services import MarketplaceService
from .plan_service import PlanService
from .paypal_service import PayPalService
from .binance_service import BinancePayService
from .webhook_service import WebhookService
from .models import PlanType, PaymentProvider

try:
    import stripe
except ModuleNotFoundError:
    stripe = None
from src.shared.decorators import auth_required
from flask_jwt_extended import get_jwt_identity

marketplace_bp = Blueprint('marketplace', __name__, url_prefix='/api/marketplace')
marketplace_service = MarketplaceService()
plan_service = PlanService()
paypal_service = PayPalService()
binance_service = BinancePayService()
webhook_service = WebhookService()

@marketplace_bp.route('/plans', methods=['GET'])
def list_public_plans():
    """Lists all public study plans available for purchase."""
    try:
        plans = marketplace_service.list_public_plans()
        return APIRoute.success(data=plans)
    except Exception as e:
        return APIRoute.error(message=str(e), status_code=500)

@marketplace_bp.route('/checkout/<plan_id>', methods=['POST'])
@auth_required
def create_checkout_session(plan_id):
    """Creates a Stripe checkout session for a given study plan."""
    try:
        if stripe is None:
            return APIRoute.error(
                message="Stripe SDK no está instalado. Ejecuta 'pip install stripe' para habilitar pagos con tarjeta.",
                status_code=503
            )
        user_id = get_jwt_identity()
        stripe.api_key = current_app.config['STRIPE_SECRET_KEY']
        
        # For now, we'll use a fixed price. In the future, this would come from the plan itself.
        session = stripe.checkout.Session.create(
            payment_method_types=['card'],
            line_items=[{
                'price_data': {
                    'currency': 'usd',
                    'product_data': {
                        'name': f'Estudio: {plan_id}',
                    },
                    'unit_amount': 2000, # $20.00
                },
                'quantity': 1,
            }],
            mode='payment',
            success_url=request.host_url + 'marketplace/success?session_id={CHECKOUT_SESSION_ID}',
            cancel_url=request.host_url + 'marketplace/cancel',
            client_reference_id=user_id,
            metadata={
                'plan_id': plan_id
            }
        )
        return APIRoute.success(data={"id": session.id})
    except Exception as e:
        return APIRoute.error(message=str(e), status_code=500)

@marketplace_bp.route('/stripe-webhook', methods=['POST'])
def stripe_webhook():
    """Handles webhooks from Stripe."""
    if stripe is None:
        return 'Stripe SDK not installed', 503
    payload = request.get_data(as_text=True)
    sig_header = request.headers.get('Stripe-Signature')
    webhook_secret = current_app.config['STRIPE_WEBHOOK_SECRET']

    try:
        event = stripe.Webhook.construct_event(
            payload, sig_header, webhook_secret
        )
    except ValueError as e:
        # Invalid payload
        return 'Invalid payload', 400
    except stripe.error.SignatureVerificationError as e:
        # Invalid signature
        return 'Invalid signature', 400

    # Handle the checkout.session.completed event
    if event['type'] == 'checkout.session.completed':
        session = event['data']['object']
        user_id = session.get('client_reference_id')
        plan_id = session.get('metadata', {}).get('plan_id')

        if user_id and plan_id:
            marketplace_service.fulfill_purchase(user_id, plan_id)
        else:
            log_error(f"Webhook received for completed session without user_id or plan_id: {session.id}")

    return 'Success', 200

# ============ NUEVAS RUTAS PARA SISTEMA DE PAGOS Y SUSCRIPCIONES ============

@marketplace_bp.route('/subscription/plans', methods=['GET'])
def get_subscription_plans():
    """Obtiene los planes de suscripción disponibles"""
    try:
        plans = plan_service.get_available_plans()
        return APIRoute.success(data=plans)
    except Exception as e:
        return APIRoute.error(message=str(e), status_code=500)

@marketplace_bp.route('/subscription/current', methods=['GET'])
@auth_required
def get_current_subscription():
    """Obtiene la suscripción actual del usuario"""
    try:
        user_id = get_jwt_identity()
        subscription = plan_service.get_user_subscription(user_id)
        return APIRoute.success(data=subscription)
    except Exception as e:
        return APIRoute.error(message=str(e), status_code=500)

@marketplace_bp.route('/subscription/limits', methods=['GET'])
@auth_required
def get_user_limits():
    """Obtiene los límites del usuario según su plan"""
    try:
        user_id = get_jwt_identity()
        limits = {
            'workspaces': plan_service.get_workspace_limit(user_id),
            'study_plans': plan_service.get_study_plan_limit(user_id),
            'templates': plan_service.get_template_limit(user_id),
            'monthly_evaluations': plan_service.get_monthly_evaluation_limit(user_id),
            'ai_corrections': plan_service.get_ai_correction_limit(user_id)
        }
        return APIRoute.success(data=limits)
    except Exception as e:
        return APIRoute.error(message=str(e), status_code=500)

# ============ RUTAS DE PAYPAL ============

@marketplace_bp.route('/paypal/create-subscription', methods=['POST'])
@auth_required
def create_paypal_subscription():
    """Crea una suscripción de PayPal"""
    try:
        user_id = get_jwt_identity()
        data = request.get_json()
        plan_type = data.get('plan_type')
        
        if not plan_type or plan_type not in [p.value for p in PlanType]:
            return APIRoute.error(message="Plan type is required and must be valid", status_code=400)
        
        plan_type_enum = PlanType(plan_type)
        subscription = paypal_service.create_subscription(user_id, plan_type_enum)
        
        if subscription:
            return APIRoute.success(data=subscription)
        else:
            return APIRoute.error(message="Failed to create PayPal subscription", status_code=500)
            
    except Exception as e:
        return APIRoute.error(message=str(e), status_code=500)

@marketplace_bp.route('/paypal/subscription/<subscription_id>', methods=['GET'])
@auth_required
def get_paypal_subscription(subscription_id):
    """Obtiene detalles de una suscripción de PayPal"""
    try:
        subscription = paypal_service.get_subscription_details(subscription_id)
        
        if subscription:
            return APIRoute.success(data=subscription)
        else:
            return APIRoute.error(message="Subscription not found", status_code=404)
            
    except Exception as e:
        return APIRoute.error(message=str(e), status_code=500)

@marketplace_bp.route('/paypal/cancel-subscription/<subscription_id>', methods=['POST'])
@auth_required
def cancel_paypal_subscription(subscription_id):
    """Cancela una suscripción de PayPal"""
    try:
        user_id = get_jwt_identity()
        success = paypal_service.cancel_subscription(subscription_id)
        
        if success:
            # También cancelar en nuestro sistema
            plan_service.cancel_subscription(user_id)
            return APIRoute.success(message="Subscription cancelled successfully")
        else:
            return APIRoute.error(message="Failed to cancel subscription", status_code=500)
            
    except Exception as e:
        return APIRoute.error(message=str(e), status_code=500)

# ============ RUTAS DE BINANCE PAY ============

@marketplace_bp.route('/binance/create-order', methods=['POST'])
@auth_required
def create_binance_order():
    """Crea una orden de pago con Binance Pay"""
    try:
        user_id = get_jwt_identity()
        data = request.get_json()
        plan_type = data.get('plan_type')
        
        if not plan_type or plan_type not in [p.value for p in PlanType]:
            return APIRoute.error(message="Plan type is required and must be valid", status_code=400)
        
        plan_type_enum = PlanType(plan_type)
        order = binance_service.create_order(user_id, plan_type_enum)
        
        if order:
            return APIRoute.success(data=order)
        else:
            return APIRoute.error(message="Failed to create Binance Pay order", status_code=500)
            
    except Exception as e:
        return APIRoute.error(message=str(e), status_code=500)

@marketplace_bp.route('/binance/order/<merchant_trade_no>', methods=['GET'])
@auth_required
def get_binance_order(merchant_trade_no):
    """Obtiene el estado de una orden de Binance Pay"""
    try:
        order = binance_service.query_order(merchant_trade_no)
        
        if order:
            return APIRoute.success(data=order)
        else:
            return APIRoute.error(message="Order not found", status_code=404)
            
    except Exception as e:
        return APIRoute.error(message=str(e), status_code=500)

@marketplace_bp.route('/binance/close-order/<merchant_trade_no>', methods=['POST'])
@auth_required
def close_binance_order(merchant_trade_no):
    """Cierra una orden de Binance Pay"""
    try:
        success = binance_service.close_order(merchant_trade_no)
        
        if success:
            return APIRoute.success(message="Order closed successfully")
        else:
            return APIRoute.error(message="Failed to close order", status_code=500)
            
    except Exception as e:
        return APIRoute.error(message=str(e), status_code=500)

# ============ WEBHOOKS ============

@marketplace_bp.route('/paypal-webhook', methods=['POST'])
def paypal_webhook():
    """Maneja webhooks de PayPal"""
    try:
        headers = dict(request.headers)
        body = request.get_data(as_text=True)
        
        result = webhook_service.process_paypal_webhook(headers, body)
        
        if result['status'] == 'success':
            return jsonify(result), 200
        elif result['status'] == 'ignored':
            return jsonify(result), 200
        else:
            return jsonify(result), 400
            
    except Exception as e:
        return jsonify({"status": "error", "message": str(e)}), 500

@marketplace_bp.route('/binance-webhook', methods=['POST'])
def binance_webhook():
    """Maneja webhooks de Binance Pay"""
    try:
        headers = dict(request.headers)
        body = request.get_data(as_text=True)
        
        result = webhook_service.process_binance_webhook(headers, body)
        
        if result['status'] == 'success':
            return jsonify(result), 200
        elif result['status'] == 'ignored':
            return jsonify(result), 200
        else:
            return jsonify(result), 400
            
    except Exception as e:
        return jsonify({"status": "error", "message": str(e)}), 500

# ============ RUTAS DE ADMINISTRACIÓN ============

@marketplace_bp.route('/admin/transactions', methods=['GET'])
@auth_required
def get_payment_transactions():
    """Obtiene el historial de transacciones de pago (solo admin)"""
    try:
        user_id = get_jwt_identity()
        # TODO: Verificar que el usuario sea admin
        
        page = request.args.get('page', 1, type=int)
        limit = request.args.get('limit', 20, type=int)
        
        transactions = plan_service.get_payment_transactions(page, limit)
        return APIRoute.success(data=transactions)
        
    except Exception as e:
        return APIRoute.error(message=str(e), status_code=500)

@marketplace_bp.route('/admin/subscriptions', methods=['GET'])
@auth_required
def get_all_subscriptions():
    """Obtiene todas las suscripciones (solo admin)"""
    try:
        user_id = get_jwt_identity()
        # TODO: Verificar que el usuario sea admin
        
        page = request.args.get('page', 1, type=int)
        limit = request.args.get('limit', 20, type=int)
        
        subscriptions = plan_service.get_all_subscriptions(page, limit)
        return APIRoute.success(data=subscriptions)
        
    except Exception as e:
        return APIRoute.error(message=str(e), status_code=500)
