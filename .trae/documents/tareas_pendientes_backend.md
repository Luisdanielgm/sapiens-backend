# Análisis de Tareas Pendientes del Backend - SapiensAI

## Resumen Ejecutivo

Basándome en el análisis de la documentación de implementación final y el código actual del backend de SapiensAI, se han identificado las tareas pendientes para completar las 5 fases de implementación planificadas. Las Fases 1 y 2 están mayormente completadas en el backend, pero existen implementaciones críticas faltantes en las Fases 3, 4 y 5.

## Estado Actual de Implementación por Fase

### ✅ Fase 1: Reestructuración de Contenidos (COMPLETADA)
**Estado:** Implementada en backend
- ✅ Modelos de contenido con soporte para diapositivas (`TopicContent`)
- ✅ Sistema de plantillas HTML (`Template`, `TemplateInstance`)
- ✅ Servicios de integración de plantillas (`TemplateIntegrationService`)
- ✅ Soporte para contenido interactivo y personalización

### ✅ Fase 2: Integración de Plantillas por Subtema (COMPLETADA)
**Estado:** Implementada en backend
- ✅ Sistema de recomendación de plantillas (`TemplateRecommendationService`)
- ✅ Servicios de plantillas (`TemplateService`, `TemplateInstanceService`)
- ✅ Modelos de personalización y seguimiento de resultados (`ContentResult`)

### ⚠️ Fase 3: Sistema de Evaluaciones Flexible (PARCIALMENTE IMPLEMENTADA)
**Estado:** Modelos básicos implementados, faltan servicios y APIs

**Implementado:**
- ✅ Modelo `Evaluation` con soporte multi-tema
- ✅ Modelos `EvaluationSubmission`, `EvaluationResource`, `EvaluationRubric`
- ✅ Campos para ponderación y tipos de evaluación

**Pendiente:**
- ❌ Servicios completos de evaluación flexible
- ❌ APIs para gestión de evaluaciones multi-tema
- ❌ Lógica de cálculo de calificaciones ponderadas
- ❌ Sistema de corrección automática con IA

### ❌ Fase 4: Pagos y Planes de Suscripción (NO IMPLEMENTADA)
**Estado:** Completamente faltante

**Faltante:**
- ❌ Modelos de suscripción y planes
- ❌ Sistema de facturación y límites
- ❌ Integración con PayPal
- ❌ Integración con Binance Pay
- ❌ Encriptación de API keys
- ❌ Sistema de créditos y monetización

### ❌ Fase 5: Refinamientos y Testing Integral (NO IMPLEMENTADA)
**Estado:** Pendiente

**Faltante:**
- ❌ Sistema de eliminación en cascada
- ❌ Monitoreo y métricas avanzadas
- ❌ Optimizaciones de rendimiento
- ❌ Testing integral automatizado

## Tareas Específicas Pendientes del Backend

### 🔴 PRIORIDAD ALTA - Fase 3: Sistema de Evaluaciones Flexible

#### 3.1 Servicios de Evaluación Avanzada
**Ubicación:** `src/evaluations/` (carpeta vacía)

**Tareas:**
1. **EvaluationService Completo**
   ```python
   # src/evaluations/services.py
   class EvaluationService:
       def create_multi_topic_evaluation(self, topic_ids, weights, evaluation_type)
       def calculate_weighted_grade(self, evaluation_id, student_id)
       def process_content_result_grading(self, evaluation_id, student_id)
       def auto_grade_submission(self, submission_id)
   ```

2. **APIs de Evaluación Flexible**
   ```python
   # src/evaluations/routes.py
   # POST /api/evaluations/multi-topic
   # PUT /api/evaluations/{id}/weights
   # GET /api/evaluations/{id}/grades/calculated
   # POST /api/evaluations/{id}/auto-grade
   ```

3. **Sistema de Corrección Automática**
   ```python
   # src/correction/ai_grading_service.py
   class AIGradingService:
       def grade_text_submission(self, submission_text, rubric)
       def grade_file_submission(self, file_path, rubric)
       def ocr_and_grade(self, image_path, rubric)
   ```

#### 3.2 Migración de Modelos de Evaluación
**Archivo:** `src/study_plans/models.py` → `src/evaluations/models.py`

**Tareas:**
1. Mover modelos `Evaluation`, `EvaluationSubmission`, `EvaluationResource`, `EvaluationRubric`
2. Actualizar imports en todo el proyecto
3. Crear servicios especializados por tipo de evaluación

### 🔴 PRIORIDAD ALTA - Fase 4: Sistema de Pagos y Suscripciones

#### 4.1 Modelos de Suscripción
**Ubicación:** `src/subscriptions/` (nueva carpeta)

**Tareas:**
1. **Modelos de Planes**
   ```python
   # src/subscriptions/models.py
   class SubscriptionPlan:
       # free, premium_teacher, premium_student, institutional
       def __init__(self, name, type, price, limits, features)
   
   class UserSubscription:
       def __init__(self, user_id, plan_id, status, billing_cycle)
   
   class UsageLimits:
       def __init__(self, max_students, max_modules, max_generations)
   ```

2. **Sistema de Créditos**
   ```python
   class CreditTransaction:
       def __init__(self, user_id, amount, type, description)
   
   class CreditBalance:
       def __init__(self, user_id, balance, reserved)
   ```

#### 4.2 Servicios de Facturación
**Ubicación:** `src/billing/` (nueva carpeta)

**Tareas:**
1. **BillingService**
   ```python
   # src/billing/services.py
   class BillingService:
       def check_usage_limits(self, user_id, action_type)
       def consume_credits(self, user_id, amount, description)
       def upgrade_subscription(self, user_id, new_plan_id)
       def downgrade_subscription(self, user_id)
   ```

2. **APIs de Facturación**
   ```python
   # src/billing/routes.py
   # GET /api/billing/usage
   # POST /api/billing/upgrade
   # GET /api/billing/plans
   # POST /api/billing/credits/purchase
   ```

#### 4.3 Integración de Pagos
**Ubicación:** `src/payments/` (nueva carpeta)

**Tareas:**
1. **PayPal Integration**
   ```python
   # src/payments/paypal_service.py
   class PayPalService:
       def create_payment_order(self, amount, currency, description)
       def capture_payment(self, order_id)
       def create_subscription(self, plan_id, user_id)
       def handle_webhook(self, webhook_data)
   ```

2. **Binance Pay Integration**
   ```python
   # src/payments/binance_service.py
   class BinancePayService:
       def create_crypto_payment(self, amount_usd, description)
       def verify_payment(self, payment_id)
       def handle_webhook(self, webhook_data)
   ```

3. **Payment Routes**
   ```python
   # src/payments/routes.py
   # POST /api/payments/paypal/create
   # POST /api/payments/paypal/capture
   # POST /api/payments/binance/create
   # POST /api/payments/webhooks/paypal
   # POST /api/payments/webhooks/binance
   ```

#### 4.4 Encriptación de API Keys
**Ubicación:** `src/security/` (nueva carpeta)

**Tareas:**
1. **Encryption Service**
   ```python
   # src/security/encryption_service.py
   class EncryptionService:
       def encrypt_api_key(self, api_key, user_id)
       def decrypt_api_key(self, encrypted_key, user_id)
       def rotate_encryption_key()
   ```

2. **Actualizar User Model**
   ```python
   # Modificar src/users/models.py
   class User:
       # Cambiar api_keys de Dict[str, str] a Dict[str, EncryptedApiKey]
       def set_encrypted_api_key(self, provider, api_key)
       def get_decrypted_api_key(self, provider)
   ```

### 🟡 PRIORIDAD MEDIA - Fase 5: Refinamientos

#### 5.1 Sistema de Eliminación en Cascada
**Ubicación:** `src/shared/cascade_service.py`

**Tareas:**
1. **CascadeService**
   ```python
   class CascadeService:
       def delete_study_plan_cascade(self, plan_id)
       def delete_user_cascade(self, user_id)
       def delete_workspace_cascade(self, workspace_id)
   ```

#### 5.2 Monitoreo y Métricas
**Ubicación:** `src/monitoring/` (nueva carpeta)

**Tareas:**
1. **Metrics Service**
   ```python
   # src/monitoring/metrics_service.py
   class MetricsService:
       def track_api_usage(self, endpoint, user_id, response_time)
       def track_generation_metrics(self, user_id, content_type, tokens_used)
       def track_payment_metrics(self, amount, method, status)
   ```

## Modelos Faltantes por Implementar

### Suscripciones y Facturación
```python
# src/subscriptions/models.py
class SubscriptionPlan
class UserSubscription  
class UsageLimits
class CreditTransaction
class CreditBalance
```

### Pagos
```python
# src/payments/models.py
class PaymentOrder
class PaymentTransaction
class PaymentMethod
class Invoice
```

### Seguridad
```python
# src/security/models.py
class EncryptedApiKey
class SecurityAuditLog
class AccessToken
```

### Monitoreo
```python
# src/monitoring/models.py
class APIUsageMetric
class GenerationMetric
class PaymentMetric
class SystemHealthMetric
```

## Servicios Faltantes por Implementar

### Core Services
1. **EvaluationService** (completo)
2. **BillingService** 
3. **SubscriptionService**
4. **PaymentService**
5. **EncryptionService**
6. **CascadeService**
7. **MetricsService**
8. **AIGradingService**

### Integration Services
1. **PayPalService**
2. **BinancePayService** 
3. **WebhookService**
4. **NotificationService**

## APIs Faltantes por Implementar

### Evaluaciones
- `POST /api/evaluations/multi-topic`
- `PUT /api/evaluations/{id}/weights`
- `GET /api/evaluations/{id}/grades/calculated`
- `POST /api/evaluations/{id}/auto-grade`

### Suscripciones
- `GET /api/subscriptions/plans`
- `POST /api/subscriptions/upgrade`
- `GET /api/subscriptions/current`
- `POST /api/subscriptions/cancel`

### Facturación
- `GET /api/billing/usage`
- `POST /api/billing/credits/purchase`
- `GET /api/billing/history`
- `POST /api/billing/limits/check`

### Pagos
- `POST /api/payments/paypal/create`
- `POST /api/payments/paypal/capture`
- `POST /api/payments/binance/create`
- `POST /api/payments/webhooks/{provider}`

### Seguridad
- `POST /api/security/api-keys/encrypt`
- `GET /api/security/api-keys/providers`
- `PUT /api/security/api-keys/{provider}`
- `DELETE /api/security/api-keys/{provider}`

## Priorización de Tareas

### Sprint 1 (Semanas 1-2): Evaluaciones Flexible
1. Crear estructura `src/evaluations/`
2. Implementar `EvaluationService` completo
3. Migrar modelos de evaluación
4. Crear APIs de evaluación multi-tema
5. Testing de evaluaciones flexibles

### Sprint 2 (Semanas 3-4): Sistema de Suscripciones
1. Crear modelos de suscripción y planes
2. Implementar `BillingService`
3. Crear sistema de límites de uso
4. APIs de suscripciones
5. Testing de facturación

### Sprint 3 (Semanas 5-6): Integración de Pagos
1. Implementar `PayPalService`
2. Implementar `BinancePayService`
3. Crear sistema de webhooks
4. APIs de pagos
5. Testing de transacciones

### Sprint 4 (Semanas 7-8): Seguridad y Encriptación
1. Implementar `EncryptionService`
2. Actualizar gestión de API keys
3. Migrar claves existentes
4. APIs de seguridad
5. Auditoría de seguridad

### Sprint 5 (Semanas 9-10): Refinamientos
1. Sistema de eliminación en cascada
2. Monitoreo y métricas
3. Optimizaciones de rendimiento
4. Testing integral
5. Documentación técnica

## Consideraciones Técnicas

### Arquitectura
- Mantener separación de responsabilidades por módulos
- Usar decoradores para validación de límites de uso
- Implementar middleware para tracking de métricas
- Asegurar transacciones atómicas en pagos

### Seguridad
- Encriptar todas las API keys en base de datos
- Implementar rate limiting por plan de suscripción
- Validar webhooks con signatures
- Logs de auditoría para transacciones

### Performance
- Cache de límites de uso frecuentemente consultados
- Índices de base de datos para consultas de facturación
- Procesamiento asíncrono de webhooks
- Optimización de consultas de métricas

### Testing
- Unit tests para todos los servicios nuevos
- Integration tests para flujos de pago
- Mock services para APIs externas
- Load testing para endpoints críticos

## Estimación de Esfuerzo

- **Fase 3 (Evaluaciones):** 2-3 semanas
- **Fase 4 (Pagos/Suscripciones):** 4-5 semanas  
- **Fase 5 (Refinamientos):** 2-3 semanas

**Total estimado:** 8-11 semanas de desarrollo backend

## Conclusión

El backend de SapiensAI tiene una base sólida con las Fases 1 y 2 completadas. Las tareas pendientes se concentran en:

1. **Sistema de evaluaciones flexible** (crítico para funcionalidad educativa)
2. **Monetización y pagos** (crítico para sostenibilidad del negocio)
3. **Seguridad y refinamientos** (crítico para producción)

La implementación debe seguir el orden de prioridad establecido para asegurar que las funcionalidades más críticas estén disponibles primero.