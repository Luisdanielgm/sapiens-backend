# 🤖 Sistema de Monitoreo de IA

El sistema de monitoreo de IA permite rastrear, controlar y analizar el uso de todas las APIs de inteligencia artificial (Gemini, OpenAI, Claude, etc.) en la plataforma SapiensAI.

## 🎯 Características Principales

- **Registro automático** de todas las llamadas a APIs de IA
- **Control de presupuesto** con límites configurables por día/semana/mes
- **Alertas automáticas** cuando se alcanzan umbrales de gasto
- **Estadísticas detalladas** por proveedor, modelo, usuario y funcionalidad
- **Auditoría completa** con paginación y filtros
- **Limpieza de datos** antiguos automática
- **Exportación de datos** para análisis externos

## 📊 Colecciones de MongoDB

### `ai_api_calls`
Registra cada llamada individual a APIs de IA:
```javascript
{
  _id: ObjectId,
  call_id: "call_1672234567890_abc123def",  // ID único
  timestamp: Date,
  provider: "gemini",                        // 'gemini', 'openai', 'claude'
  model_name: "gemini-1.5-flash-002",
  user_id: "user@example.com",              // Opcional
  session_id: "session_xyz789",             // Opcional
  
  // Datos de tokens
  prompt_tokens: 150,
  completion_tokens: 85,
  total_tokens: 235,
  
  // Costos en USD
  input_cost: 0.0001125,
  output_cost: 0.000255,
  total_cost: 0.0003675,
  
  // Metadatos
  endpoint: "gemini/gemini-1.5-flash-002",
  response_time: 1250,                      // ms
  success: true,
  error_message: null,
  
  // Contexto
  feature: "chat",                          // 'chat', 'content-generation', etc.
  user_type: "student",                     // 'student', 'teacher', 'admin'
  
  created_at: Date,
  updated_at: Date
}
```

### `ai_monitoring_config`
Configuración global del sistema (un solo documento):
```javascript
{
  _id: ObjectId,
  
  // Límites globales (USD)
  daily_budget: 50.0,
  weekly_budget: 300.0,
  monthly_budget: 1000.0,
  
  // Límites por proveedor
  provider_limits: {
    gemini: {
      daily_budget: 30.0,
      weekly_budget: 180.0,
      monthly_budget: 600.0
    },
    openai: {
      daily_budget: 15.0,
      weekly_budget: 90.0,
      monthly_budget: 300.0
    }
  },
  
  // Límites por usuario
  user_daily_limit: 5.0,
  user_weekly_limit: 25.0,
  user_monthly_limit: 80.0,
  
  // Configuración de alertas
  alert_thresholds: [0.5, 0.8, 0.95],      // 50%, 80%, 95%
  
  // Configuración técnica
  log_level: "info",
  enable_detailed_logging: true,
  
  created_at: Date,
  updated_at: Date
}
```

### `ai_monitoring_alerts`
Alertas generadas automáticamente:
```javascript
{
  _id: ObjectId,
  alert_id: "alert_daily_global_0.8",
  type: "daily",                            // 'daily', 'weekly', 'monthly'
  threshold: 40.0,                          // USD
  current_usage: 32.5,                      // USD
  provider: "gemini",                       // Opcional
  model_name: "gemini-1.5-flash-002",     // Opcional
  user_id: "user@example.com",             // Opcional
  triggered: true,
  triggered_at: Date,
  dismissed: false,
  dismissed_at: null,
  created_at: Date
}
```

## 🚀 Endpoints API

Todos los endpoints requieren autenticación JWT con rol `ADMIN`.

### 1. POST `/api/ai-monitoring/calls`
Registra una nueva llamada a API de IA.

**Request:**
```json
{
  "call_id": "call_1672234567890_abc123def",
  "provider": "gemini",
  "model_name": "gemini-1.5-flash-002",
  "prompt_tokens": 150,
  "user_id": "user@example.com",
  "session_id": "session_xyz789",
  "feature": "chat",
  "user_type": "student",
  "endpoint": "gemini/gemini-1.5-flash-002"
}
```

**Response:**
```json
{
  "success": true,
  "message": "Llamada registrada exitosamente",
  "data": {
    "call_id": "call_1672234567890_abc123def"
  }
}
```

### 2. PUT `/api/ai-monitoring/calls/{call_id}`
Actualiza una llamada con los resultados finales.

**Request:**
```json
{
  "completion_tokens": 85,
  "response_time": 1250,
  "success": true,
  "input_cost": 0.0001125,
  "output_cost": 0.000255,
  "total_cost": 0.0003675,
  "total_tokens": 235
}
```

### 3. GET `/api/ai-monitoring/stats`
Obtiene estadísticas completas del sistema.

**Query Parameters:**
- `start_date`: Fecha de inicio (ISO format)
- `end_date`: Fecha de fin (ISO format)
- `provider`: Filtrar por proveedor
- `user_id`: Filtrar por usuario
- `user_type`: Filtrar por tipo de usuario
- `feature`: Filtrar por funcionalidad

**Response:**
```json
{
  "success": true,
  "data": {
    "stats": {
      "total_calls": 1250,
      "total_tokens": 285000,
      "total_cost": 42.75,
      "average_response_time": 1180,
      "success_rate": 0.98,
      
      "by_provider": {
        "gemini": { "calls": 800, "tokens": 180000, "cost": 27.50 },
        "openai": { "calls": 450, "tokens": 105000, "cost": 15.25 }
      },
      
      "by_model": { /* ... */ },
      "by_feature": { /* ... */ },
      "by_user_type": { /* ... */ },
      "daily_trends": [ /* ... */ ]
    }
  }
}
```

### 4. GET `/api/ai-monitoring/alerts`
Obtiene alertas activas.

### 5. GET `/api/ai-monitoring/config`
Obtiene la configuración actual.

### 6. PUT `/api/ai-monitoring/config`
Actualiza la configuración del sistema.

### 7. GET `/api/ai-monitoring/calls`
Lista llamadas con paginación y filtros.

**Query Parameters:**
- `page`: Página (default: 1)
- `limit`: Límite por página (default: 50, max: 100)
- `start_date`: Fecha de inicio
- `end_date`: Fecha de fin
- `provider`: Proveedor específico
- `success`: Filtrar por éxito (true/false)

### 8. POST `/api/ai-monitoring/cleanup`
Limpia datos antiguos del sistema.

### 9. GET `/api/ai-monitoring/export`
Exporta datos en formato JSON o CSV.

## 🔧 Configuración e Instalación

### 1. Ejecutar Script de Inicialización

```bash
python scripts/setup_ai_monitoring.py
```

Este script:
- ✅ Crea la configuración por defecto
- ✅ Configura índices de la base de datos
- ✅ Ejecuta pruebas básicas del sistema

### 2. Configuración por Defecto

El sistema se inicializa con estos valores:

```python
{
    "daily_budget": 50.0,           # $50 USD por día
    "weekly_budget": 300.0,         # $300 USD por semana
    "monthly_budget": 1000.0,       # $1000 USD por mes
    "user_daily_limit": 5.0,        # $5 USD por usuario/día
    "alert_thresholds": [0.5, 0.8, 0.95]  # Alertas al 50%, 80%, 95%
}
```

### 3. Variables de Entorno

Asegúrate de tener configuradas:
```env
MONGO_DB_URI=mongodb://...
DB_NAME=sapiens_ai
```

## 📈 Uso del Sistema

### Flujo Típico de Monitoreo

1. **Antes de llamar a la API de IA:**
   ```python
   # El frontend registra la intención
   POST /api/ai-monitoring/calls
   ```

2. **Después de la llamada a la API:**
   ```python
   # El frontend actualiza con los resultados
   PUT /api/ai-monitoring/calls/{call_id}
   ```

3. **El sistema automáticamente:**
   - ✅ Calcula costos
   - ✅ Verifica límites de presupuesto
   - ✅ Genera alertas si es necesario
   - ✅ Actualiza estadísticas

### Integración en el Frontend

```javascript
// 1. Registrar llamada antes de enviar a la API
const callId = `call_${Date.now()}_${Math.random().toString(36).substr(2, 9)}`;

await fetch('/api/ai-monitoring/calls', {
  method: 'POST',
  headers: { 
    'Authorization': `Bearer ${token}`,
    'Content-Type': 'application/json'
  },
  body: JSON.stringify({
    call_id: callId,
    provider: 'gemini',
    model_name: 'gemini-1.5-flash-002',
    prompt_tokens: promptTokens,
    user_id: currentUser.email,
    feature: 'chat',
    user_type: currentUser.role
  })
});

// 2. Hacer llamada a la API de IA
const aiResponse = await callGeminiAPI(prompt);

// 3. Actualizar con resultados
await fetch(`/api/ai-monitoring/calls/${callId}`, {
  method: 'PUT',
  headers: {
    'Authorization': `Bearer ${token}`,
    'Content-Type': 'application/json'
  },
  body: JSON.stringify({
    completion_tokens: aiResponse.tokens,
    response_time: responseTime,
    success: true,
    total_cost: aiResponse.cost
  })
});
```

## 🔍 Monitoreo y Alertas

### Tipos de Alertas

1. **Alertas de Presupuesto Diario**
   - Se activan cuando el uso diario supera los umbrales configurados
   - Por defecto: 50%, 80%, 95% del límite diario

2. **Alertas por Proveedor**
   - Específicas para cada proveedor de IA
   - Permiten control granular del gasto

3. **Alertas por Usuario**
   - Controlan el uso individual de cada usuario
   - Previenen abuso o uso excesivo

### Dashboard de Estadísticas

El endpoint `/api/ai-monitoring/stats` proporciona:

- 📊 **Estadísticas generales**: Total de llamadas, tokens, costos
- 🏢 **Por proveedor**: Uso desglosado por cada API
- 🤖 **Por modelo**: Rendimiento de cada modelo específico
- 👥 **Por tipo de usuario**: Uso de estudiantes vs profesores vs admins
- 🔧 **Por funcionalidad**: Chat, generación de contenido, evaluaciones
- 📈 **Tendencias diarias**: Evolución del uso a lo largo del tiempo

## 🛠️ Mantenimiento

### Limpieza de Datos Antiguos

```bash
# Mantener solo últimos 30 días
POST /api/ai-monitoring/cleanup
{
  "days_to_keep": 30,
  "provider": "gemini"  // Opcional
}
```

### Exportación para Análisis

```bash
# Exportar en CSV
GET /api/ai-monitoring/export?format=csv&start_date=2025-01-01&end_date=2025-01-31
```

### Configuración de Límites

```bash
# Actualizar límites de presupuesto
PUT /api/ai-monitoring/config
{
  "daily_budget": 75.0,
  "alert_thresholds": [0.6, 0.8, 0.95]
}
```

## 🚨 Solución de Problemas

### Error 429: "Límite de presupuesto excedido"

**Causa:** El sistema detectó que la llamada excedería el límite diario configurado.

**Solución:**
1. Verificar uso actual: `GET /api/ai-monitoring/stats`
2. Revisar límites: `GET /api/ai-monitoring/config`
3. Ajustar límites si es necesario: `PUT /api/ai-monitoring/config`

### Alertas No Se Están Generando

**Verificar:**
1. Configuración de umbrales: `GET /api/ai-monitoring/config`
2. Llamadas se están marcando como exitosas: `success: true`
3. Índices de la base de datos están configurados

### Estadísticas Incorrectas

**Solución:**
1. Ejecutar script de verificación: `python scripts/setup_ai_monitoring.py`
2. Verificar índices: Revisar logs de la base de datos
3. Limpiar datos corruptos si es necesario

## 📋 Lista de Verificación de Implementación

- [x] ✅ Modelos implementados
- [x] ✅ Servicios implementados
- [x] ✅ Rutas implementadas
- [x] ✅ Blueprint registrado en main.py
- [x] ✅ Índices de BD configurados
- [x] ✅ Script de inicialización creado
- [x] ✅ Constantes agregadas
- [x] ✅ Documentación completa

## 🔗 Enlaces Relacionados

- [Documentación de APIs de IA](../docs/ai-apis.md)
- [Configuración de Presupuestos](../docs/budget-management.md)
- [Guía de Integración Frontend](../docs/frontend-integration.md) 