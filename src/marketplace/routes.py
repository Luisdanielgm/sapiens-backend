from flask import Blueprint, jsonify, request, current_app
from src.shared.standardization import APIRoute
from .services import MarketplaceService
import stripe
from src.shared.decorators import auth_required
from flask_jwt_extended import get_jwt_identity

marketplace_bp = Blueprint('marketplace', __name__, url_prefix='/api/marketplace')
marketplace_service = MarketplaceService()

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
        return jsonify(id=session.id)
    except Exception as e:
        return APIRoute.error(message=str(e), status_code=500)

@marketplace_bp.route('/stripe-webhook', methods=['POST'])
def stripe_webhook():
    """Handles webhooks from Stripe."""
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
