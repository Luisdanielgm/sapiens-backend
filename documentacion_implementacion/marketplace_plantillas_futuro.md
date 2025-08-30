# Marketplace Público de Plantillas - Consideraciones Futuras

## Resumen Ejecutivo

Este documento presenta las consideraciones técnicas, de negocio y de producto para la implementación futura de un marketplace público de plantillas en SapiensIA, donde educadores puedan compartir, vender y adquirir plantillas educativas.

## Índice
1. [Visión del Marketplace](#visión-del-marketplace)
2. [Arquitectura Propuesta](#arquitectura-propuesta)
3. [Modelos de Datos](#modelos-de-datos)
4. [Funcionalidades Core](#funcionalidades-core)
5. [Sistema de Monetización](#sistema-de-monetización)
6. [Calidad y Moderación](#calidad-y-moderación)
7. [Consideraciones Técnicas](#consideraciones-técnicas)
8. [Roadmap de Implementación](#roadmap-de-implementación)
9. [Riesgos y Mitigaciones](#riesgos-y-mitigaciones)

## Visión del Marketplace

### Objetivos Estratégicos
- **Democratizar la creación de contenido**: Permitir que educadores sin conocimientos técnicos accedan a plantillas de alta calidad
- **Monetizar el ecosistema**: Crear una fuente de ingresos para creadores de plantillas y la plataforma
- **Acelerar la adopción**: Reducir el tiempo de creación de contenido mediante plantillas pre-construidas
- **Fomentar la innovación**: Incentivar la creación de plantillas innovadoras y especializadas

### Casos de Uso Principales
1. **Educador busca plantilla**: Encuentra y adquiere plantillas para sus clases
2. **Creador publica plantilla**: Sube y monetiza sus creaciones
3. **Institución compra licencias**: Adquiere acceso masivo para su organización
4. **Estudiante accede a contenido**: Interactúa con contenido creado desde plantillas del marketplace

## Arquitectura Propuesta

### Componentes del Sistema

```
┌─────────────────────────────────────────────────────────────┐
│                    Frontend Marketplace                     │
├─────────────────────────────────────────────────────────────┤
│  • Catálogo de Plantillas    • Preview Interactivo         │
│  • Sistema de Búsqueda       • Carrito de Compras          │
│  • Perfiles de Creadores     • Gestión de Licencias        │
└─────────────────────────────────────────────────────────────┘
                                │
                                ▼
┌─────────────────────────────────────────────────────────────┐
│                   API Gateway Marketplace                   │
├─────────────────────────────────────────────────────────────┤
│  • Autenticación/Autorización • Rate Limiting              │
│  • Validación de Requests     • Logging/Monitoring         │
└─────────────────────────────────────────────────────────────┘
                                │
                ┌───────────────┼───────────────┐
                ▼               ▼               ▼
┌─────────────────┐ ┌─────────────────┐ ┌─────────────────┐
│  Template       │ │   Commerce      │ │   Content       │
│  Service        │ │   Service       │ │   Service       │
├─────────────────┤ ├─────────────────┤ ├─────────────────┤
│ • CRUD          │ │ • Payments      │ │ • Generation    │
│ • Validation    │ │ • Licensing     │ │ • Deployment    │
│ • Versioning    │ │ • Analytics     │ │ • Monitoring    │
└─────────────────┘ └─────────────────┘ └─────────────────┘
                                │
                                ▼
┌─────────────────────────────────────────────────────────────┐
│                    Storage & Database                       │
├─────────────────────────────────────────────────────────────┤
│  • MongoDB (Metadata)         • S3 (Assets)                │
│  • Redis (Cache)              • CDN (Distribution)          │
│  • Elasticsearch (Search)     • Stripe (Payments)          │
└─────────────────────────────────────────────────────────────┘
```

### Microservicios Propuestos

#### 1. Template Marketplace Service
```python
# Gestión de plantillas en el marketplace
class MarketplaceTemplateService:
    def publish_template(self, template_id: str, pricing: Dict) -> bool
    def update_listing(self, listing_id: str, updates: Dict) -> bool
    def search_templates(self, filters: Dict) -> List[Dict]
    def get_template_details(self, template_id: str) -> Dict
    def download_template(self, template_id: str, user_id: str) -> str
```

#### 2. Commerce Service
```python
# Gestión de transacciones y licencias
class CommerceService:
    def create_purchase(self, items: List[Dict], user_id: str) -> str
    def process_payment(self, purchase_id: str, payment_method: str) -> bool
    def grant_license(self, template_id: str, user_id: str, license_type: str) -> bool
    def validate_license(self, template_id: str, user_id: str) -> bool
    def generate_invoice(self, purchase_id: str) -> Dict
```

#### 3. Review & Rating Service
```python
# Sistema de reseñas y calificaciones
class ReviewService:
    def submit_review(self, template_id: str, user_id: str, review: Dict) -> bool
    def get_reviews(self, template_id: str, filters: Dict) -> List[Dict]
    def moderate_review(self, review_id: str, action: str) -> bool
    def calculate_rating(self, template_id: str) -> float
```

## Modelos de Datos

### MarketplaceListing
```python
class MarketplaceListing:
    _id: ObjectId
    template_id: ObjectId          # Referencia a Template
    creator_id: ObjectId           # Creador de la plantilla
    title: str                     # Título para el marketplace
    description: str               # Descripción detallada
    category: str                  # Categoría (math, science, language, etc.)
    subcategory: str              # Subcategoría específica
    grade_levels: List[str]        # Niveles educativos (K-12, university, etc.)
    subjects: List[str]            # Materias aplicables
    
    # Pricing
    pricing_model: str             # free, one_time, subscription
    price: Decimal                 # Precio en USD
    currency: str = "USD"          # Moneda
    
    # Media
    preview_images: List[str]      # URLs de imágenes de preview
    demo_url: str                  # URL de demo interactiva
    video_preview: str             # URL de video explicativo
    
    # Metadata
    tags: List[str]                # Tags para búsqueda
    difficulty_level: str          # beginner, intermediate, advanced
    estimated_time: int            # Tiempo estimado de uso (minutos)
    learning_objectives: List[str]  # Objetivos de aprendizaje
    
    # Stats
    downloads: int = 0             # Número de descargas
    rating: float = 0.0           # Calificación promedio
    review_count: int = 0         # Número de reseñas
    
    # Status
    status: str = "draft"          # draft, pending, approved, rejected
    moderation_notes: str          # Notas de moderación
    
    # Timestamps
    created_at: datetime
    updated_at: datetime
    published_at: datetime
```

### Purchase
```python
class Purchase:
    _id: ObjectId
    user_id: ObjectId              # Comprador
    items: List[Dict]              # Items comprados
    total_amount: Decimal          # Total de la compra
    currency: str = "USD"
    
    # Payment
    payment_method: str            # stripe, paypal, etc.
    payment_status: str            # pending, completed, failed, refunded
    stripe_payment_intent: str     # ID de Stripe
    
    # License
    license_type: str              # personal, institutional, commercial
    license_duration: int          # Duración en días (0 = perpetua)
    
    # Metadata
    created_at: datetime
    completed_at: datetime
    refunded_at: datetime
```

### Review
```python
class Review:
    _id: ObjectId
    template_id: ObjectId          # Plantilla reseñada
    user_id: ObjectId              # Usuario que reseña
    purchase_id: ObjectId          # Compra verificada
    
    # Review content
    rating: int                    # 1-5 estrellas
    title: str                     # Título de la reseña
    content: str                   # Contenido de la reseña
    
    # Categorized ratings
    ease_of_use: int              # 1-5
    design_quality: int           # 1-5
    educational_value: int        # 1-5
    
    # Moderation
    status: str = "pending"        # pending, approved, rejected
    moderation_reason: str         # Razón de moderación
    
    # Engagement
    helpful_votes: int = 0         # Votos de "útil"
    
    created_at: datetime
    updated_at: datetime
```

## Funcionalidades Core

### 1. Catálogo y Búsqueda

#### Búsqueda Avanzada
```python
# Elasticsearch query para búsqueda de plantillas
def search_templates(query: str, filters: Dict) -> Dict:
    search_body = {
        "query": {
            "bool": {
                "must": [
                    {
                        "multi_match": {
                            "query": query,
                            "fields": ["title^3", "description^2", "tags"]
                        }
                    }
                ],
                "filter": []
            }
        },
        "aggs": {
            "categories": {"terms": {"field": "category"}},
            "grade_levels": {"terms": {"field": "grade_levels"}},
            "price_ranges": {
                "range": {
                    "field": "price",
                    "ranges": [
                        {"key": "free", "to": 0.01},
                        {"key": "budget", "from": 0.01, "to": 10},
                        {"key": "premium", "from": 10}
                    ]
                }
            }
        },
        "sort": [
            {"_score": {"order": "desc"}},
            {"rating": {"order": "desc"}},
            {"downloads": {"order": "desc"}}
        ]
    }
    
    # Aplicar filtros
    if filters.get('category'):
        search_body['query']['bool']['filter'].append(
            {"term": {"category": filters['category']}}
        )
    
    if filters.get('price_range'):
        price_filter = get_price_filter(filters['price_range'])
        search_body['query']['bool']['filter'].append(price_filter)
    
    return elasticsearch_client.search(index="marketplace_templates", body=search_body)
```

#### Sistema de Recomendaciones
```python
class RecommendationEngine:
    def get_recommendations(self, user_id: str, context: Dict) -> List[str]:
        # Collaborative filtering
        similar_users = self.find_similar_users(user_id)
        collaborative_recs = self.get_collaborative_recommendations(similar_users)
        
        # Content-based filtering
        user_preferences = self.get_user_preferences(user_id)
        content_recs = self.get_content_based_recommendations(user_preferences)
        
        # Trending templates
        trending_recs = self.get_trending_templates(context.get('timeframe', '7d'))
        
        # Combine and rank
        combined_recs = self.combine_recommendations([
            (collaborative_recs, 0.4),
            (content_recs, 0.4),
            (trending_recs, 0.2)
        ])
        
        return combined_recs[:10]
```

### 2. Preview Interactivo

#### Sistema de Preview Seguro
```python
class PreviewService:
    def generate_preview(self, template_id: str) -> str:
        template = self.get_template(template_id)
        
        # Crear versión sandbox del template
        sandbox_html = self.create_sandbox_version(template.html)
        
        # Aplicar datos de ejemplo
        preview_props = self.generate_sample_props(template.props_schema)
        rendered_html = self.apply_props(sandbox_html, preview_props)
        
        # Subir a CDN temporal
        preview_url = self.upload_to_temp_cdn(rendered_html)
        
        return preview_url
    
    def create_sandbox_version(self, html: str) -> str:
        # Remover scripts peligrosos
        safe_html = self.sanitize_html(html)
        
        # Agregar sandbox iframe
        sandbox_wrapper = f"""
        <iframe 
            src="data:text/html;base64,{base64.b64encode(safe_html.encode()).decode()}"
            sandbox="allow-scripts allow-same-origin"
            style="width: 100%; height: 600px; border: none;">
        </iframe>
        """
        
        return sandbox_wrapper
```

### 3. Sistema de Licencias

#### Tipos de Licencias
```python
class LicenseType(Enum):
    PERSONAL = "personal"          # Uso personal del educador
    CLASSROOM = "classroom"        # Uso en una clase específica
    INSTITUTIONAL = "institutional" # Uso en toda la institución
    COMMERCIAL = "commercial"      # Uso comercial/reventa

class LicenseManager:
    def grant_license(self, template_id: str, user_id: str, license_type: LicenseType) -> License:
        license = License(
            template_id=template_id,
            user_id=user_id,
            license_type=license_type,
            granted_at=datetime.utcnow(),
            expires_at=self.calculate_expiry(license_type),
            usage_limits=self.get_usage_limits(license_type)
        )
        
        self.save_license(license)
        return license
    
    def validate_usage(self, template_id: str, user_id: str, usage_context: Dict) -> bool:
        license = self.get_active_license(template_id, user_id)
        
        if not license:
            return False
        
        # Verificar límites de uso
        if license.usage_limits:
            current_usage = self.get_current_usage(license)
            if current_usage >= license.usage_limits.get('max_students', float('inf')):
                return False
        
        # Verificar contexto de uso
        if license.license_type == LicenseType.CLASSROOM:
            if usage_context.get('class_id') != license.restricted_to_class:
                return False
        
        return True
```

## Sistema de Monetización

### Modelos de Pricing

#### 1. Freemium
```python
class FreemiumModel:
    def __init__(self):
        self.free_templates_limit = 5
        self.premium_features = [
            'unlimited_downloads',
            'commercial_license',
            'priority_support',
            'advanced_customization'
        ]
    
    def can_download(self, user_id: str, template_id: str) -> bool:
        user_downloads = self.get_user_downloads(user_id)
        template = self.get_template(template_id)
        
        if template.pricing_model == 'free':
            return len(user_downloads) < self.free_templates_limit
        
        return self.has_premium_subscription(user_id)
```

#### 2. Revenue Sharing
```python
class RevenueSharing:
    def __init__(self):
        self.platform_commission = 0.30  # 30% para la plataforma
        self.creator_share = 0.70        # 70% para el creador
    
    def calculate_payout(self, sale_amount: Decimal, creator_tier: str) -> Dict:
        # Ajustar comisión según tier del creador
        commission_rate = self.get_commission_rate(creator_tier)
        
        platform_fee = sale_amount * commission_rate
        creator_payout = sale_amount - platform_fee
        
        return {
            'sale_amount': sale_amount,
            'platform_fee': platform_fee,
            'creator_payout': creator_payout,
            'commission_rate': commission_rate
        }
    
    def get_commission_rate(self, creator_tier: str) -> Decimal:
        rates = {
            'bronze': Decimal('0.30'),
            'silver': Decimal('0.25'),
            'gold': Decimal('0.20'),
            'platinum': Decimal('0.15')
        }
        return rates.get(creator_tier, Decimal('0.30'))
```

### Integración con Stripe

```python
class StripeIntegration:
    def create_product(self, template: MarketplaceListing) -> str:
        product = stripe.Product.create(
            name=template.title,
            description=template.description,
            metadata={
                'template_id': str(template.template_id),
                'creator_id': str(template.creator_id)
            }
        )
        
        price = stripe.Price.create(
            product=product.id,
            unit_amount=int(template.price * 100),  # Convertir a centavos
            currency=template.currency
        )
        
        return price.id
    
    def create_checkout_session(self, items: List[Dict], user_id: str) -> str:
        line_items = []
        for item in items:
            line_items.append({
                'price': item['stripe_price_id'],
                'quantity': 1
            })
        
        session = stripe.checkout.Session.create(
            payment_method_types=['card'],
            line_items=line_items,
            mode='payment',
            success_url=f"{settings.FRONTEND_URL}/marketplace/success?session_id={{CHECKOUT_SESSION_ID}}",
            cancel_url=f"{settings.FRONTEND_URL}/marketplace/cancel",
            metadata={'user_id': user_id}
        )
        
        return session.url
```

## Calidad y Moderación

### Sistema de Moderación Automática

```python
class AutoModerationService:
    def __init__(self):
        self.content_filters = [
            self.check_malicious_code,
            self.check_inappropriate_content,
            self.check_copyright_violations,
            self.check_technical_quality
        ]
    
    def moderate_template(self, template: Template) -> ModerationResult:
        results = []
        
        for filter_func in self.content_filters:
            result = filter_func(template)
            results.append(result)
        
        overall_score = self.calculate_overall_score(results)
        
        if overall_score >= 0.8:
            status = "auto_approved"
        elif overall_score >= 0.6:
            status = "needs_review"
        else:
            status = "auto_rejected"
        
        return ModerationResult(
            status=status,
            score=overall_score,
            issues=self.extract_issues(results),
            recommendations=self.generate_recommendations(results)
        )
    
    def check_malicious_code(self, template: Template) -> FilterResult:
        dangerous_patterns = [
            r'eval\s*\(',
            r'Function\s*\(',
            r'document\.write',
            r'innerHTML\s*=',
            r'<script[^>]*src\s*=\s*["\'][^"\']*(http|//)',
        ]
        
        issues = []
        for pattern in dangerous_patterns:
            if re.search(pattern, template.html, re.IGNORECASE):
                issues.append(f"Potentially dangerous code pattern: {pattern}")
        
        return FilterResult(
            passed=len(issues) == 0,
            score=1.0 if len(issues) == 0 else 0.0,
            issues=issues
        )
```

### Sistema de Calidad

```python
class QualityAssessment:
    def assess_template_quality(self, template: Template) -> QualityScore:
        metrics = {
            'code_quality': self.assess_code_quality(template.html),
            'educational_value': self.assess_educational_value(template),
            'user_experience': self.assess_user_experience(template),
            'accessibility': self.assess_accessibility(template.html),
            'performance': self.assess_performance(template.html)
        }
        
        weighted_score = (
            metrics['code_quality'] * 0.2 +
            metrics['educational_value'] * 0.3 +
            metrics['user_experience'] * 0.2 +
            metrics['accessibility'] * 0.15 +
            metrics['performance'] * 0.15
        )
        
        return QualityScore(
            overall_score=weighted_score,
            metrics=metrics,
            recommendations=self.generate_quality_recommendations(metrics)
        )
```

## Consideraciones Técnicas

### Escalabilidad

#### CDN y Caching
```python
class CDNManager:
    def __init__(self):
        self.cdn_client = CloudFrontClient()
        self.cache_ttl = {
            'templates': 3600,      # 1 hora
            'previews': 1800,       # 30 minutos
            'assets': 86400,        # 24 horas
            'metadata': 300         # 5 minutos
        }
    
    def distribute_template(self, template_id: str) -> str:
        # Generar versión optimizada
        optimized_html = self.optimize_template(template_id)
        
        # Subir a CDN
        cdn_url = self.upload_to_cdn(optimized_html, f"templates/{template_id}")
        
        # Configurar cache headers
        self.set_cache_headers(cdn_url, self.cache_ttl['templates'])
        
        return cdn_url
```

#### Rate Limiting
```python
class RateLimiter:
    def __init__(self):
        self.redis_client = redis.Redis()
        self.limits = {
            'search': {'requests': 100, 'window': 3600},      # 100/hora
            'download': {'requests': 10, 'window': 3600},     # 10/hora
            'preview': {'requests': 50, 'window': 3600},      # 50/hora
            'upload': {'requests': 5, 'window': 3600}         # 5/hora
        }
    
    def check_limit(self, user_id: str, action: str) -> bool:
        limit_config = self.limits.get(action)
        if not limit_config:
            return True
        
        key = f"rate_limit:{user_id}:{action}"
        current = self.redis_client.get(key)
        
        if current is None:
            self.redis_client.setex(key, limit_config['window'], 1)
            return True
        
        if int(current) >= limit_config['requests']:
            return False
        
        self.redis_client.incr(key)
        return True
```

### Seguridad

#### Sandbox de Ejecución
```python
class TemplateSandbox:
    def __init__(self):
        self.allowed_domains = ['cdn.sapiensai.com', 'fonts.googleapis.com']
        self.blocked_apis = ['fetch', 'XMLHttpRequest', 'WebSocket']
    
    def sanitize_template(self, html: str) -> str:
        # Parsear HTML
        soup = BeautifulSoup(html, 'html.parser')
        
        # Remover scripts externos no autorizados
        for script in soup.find_all('script', src=True):
            src_domain = self.extract_domain(script['src'])
            if src_domain not in self.allowed_domains:
                script.decompose()
        
        # Sanitizar JavaScript inline
        for script in soup.find_all('script', src=False):
            sanitized_js = self.sanitize_javascript(script.string)
            script.string = sanitized_js
        
        # Aplicar CSP headers
        csp_meta = soup.new_tag('meta')
        csp_meta.attrs['http-equiv'] = 'Content-Security-Policy'
        csp_meta.attrs['content'] = self.generate_csp_policy()
        soup.head.insert(0, csp_meta)
        
        return str(soup)
```

## Roadmap de Implementación

### Fase 1: MVP (3-4 meses)
- [ ] Modelo de datos básico
- [ ] API de marketplace
- [ ] Frontend básico de catálogo
- [ ] Sistema de búsqueda simple
- [ ] Integración con Stripe
- [ ] Sistema de licencias básico

### Fase 2: Core Features (2-3 meses)
- [ ] Sistema de reseñas
- [ ] Preview interactivo
- [ ] Moderación automática básica
- [ ] Dashboard de creadores
- [ ] Analytics básicas
- [ ] Sistema de notificaciones

### Fase 3: Advanced Features (3-4 meses)
- [ ] Recomendaciones personalizadas
- [ ] Moderación avanzada
- [ ] Múltiples tipos de licencia
- [ ] API para integraciones
- [ ] Analytics avanzadas
- [ ] Sistema de afiliados

### Fase 4: Enterprise (2-3 meses)
- [ ] Licencias institucionales
- [ ] Marketplace privado
- [ ] SSO enterprise
- [ ] Reportes avanzados
- [ ] SLA garantizado

## Riesgos y Mitigaciones

### Riesgos Técnicos

| Riesgo | Probabilidad | Impacto | Mitigación |
|--------|--------------|---------|------------|
| Escalabilidad de búsqueda | Media | Alto | Implementar Elasticsearch con sharding |
| Seguridad de plantillas | Alta | Crítico | Sandbox robusto + moderación automática |
| Performance de preview | Media | Medio | CDN + caching agresivo |
| Fraude en pagos | Media | Alto | Integración robusta con Stripe + ML |

### Riesgos de Negocio

| Riesgo | Probabilidad | Impacto | Mitigación |
|--------|--------------|---------|------------|
| Baja adopción inicial | Alta | Alto | Programa de incentivos para early adopters |
| Competencia | Media | Medio | Diferenciación por calidad e integración |
| Problemas de calidad | Media | Alto | Sistema de moderación + community feedback |
| Disputas de copyright | Baja | Alto | Proceso claro de DMCA + verificación |

### Riesgos Regulatorios

| Riesgo | Probabilidad | Impacto | Mitigación |
|--------|--------------|---------|------------|
| GDPR compliance | Baja | Alto | Diseño privacy-first desde el inicio |
| Regulaciones de pagos | Baja | Medio | Compliance con PCI DSS |
| Derechos educativos | Baja | Medio | Asesoría legal especializada |

## Métricas de Éxito

### KPIs Principales
- **Adopción**: Número de plantillas publicadas/mes
- **Engagement**: Descargas por plantilla
- **Monetización**: Revenue mensual recurrente
- **Calidad**: Rating promedio de plantillas
- **Retención**: Creadores activos mes a mes

### Métricas Técnicas
- **Performance**: Tiempo de carga < 2s
- **Disponibilidad**: 99.9% uptime
- **Seguridad**: 0 incidentes críticos
- **Escalabilidad**: Soporte para 10K+ plantillas

---

## Conclusión

El marketplace público de plantillas representa una oportunidad significativa para:
1. **Monetizar el ecosistema** SapiensIA
2. **Acelerar la adopción** mediante contenido de calidad
3. **Crear una comunidad** de educadores innovadores
4. **Diferenciarse** de la competencia

La implementación debe ser gradual, priorizando la calidad y seguridad desde el inicio, con un enfoque en la experiencia del usuario tanto para creadores como para consumidores de plantillas.

**Próximos pasos recomendados**:
1. Validar la propuesta con usuarios beta
2. Desarrollar MVP con funcionalidades core
3. Establecer partnerships con creadores de contenido
4. Implementar sistema de moderación robusto
5. Lanzar programa de early adopters

Esta funcionalidad tiene el potencial de transformar SapiensIA de una plataforma de creación de contenido a un ecosistema completo de educación digital.