# Guía de Adaptación del Frontend al Backend 100% Implementado

## 📋 Resumen Ejecutivo

Con el backend de SapiensAI completamente implementado y funcional, el frontend requiere actualizaciones específicas para aprovechar las nuevas funcionalidades y adaptarse a los cambios en endpoints existentes. Este documento detalla endpoint por endpoint las modificaciones necesarias.

## 🔄 1. Endpoints con Cambios en Estructura de Datos

### 1.1 PUT /api/templates/:id
**Estado**: Corregido con validación completa
**Cambios en Frontend**:
- **Validación previa**: Verificar que el HTML tenga mínimo 10 caracteres y máximo 1MB
- **Campos requeridos**: Asegurar que `name`, `scope`, `status` estén presentes
- **Manejo de errores**: Implementar manejo específico para errores de validación HTML
- **Estructura de request**:
```javascript
{
  name: string, // Requerido
  html_content: string, // Mínimo 10 chars, máximo 1MB
  scope: string, // Requerido
  status: string // Requerido
}
```

### 1.2 GET /api/study-plan
**Estado**: Filtrado por workspace corregido
**Cambios en Frontend**:
- **Parámetros**: El filtro por `email` ahora funciona correctamente
- **Respuesta**: Ahora devuelve planes reales (no array vacío)
- **Workspace context**: Incluye información de workspace en la respuesta
```javascript
// Respuesta actualizada
{
  data: [
    {
      _id: string,
      name: string,
      workspace_context: {
        workspace_type: string,
        workspace_name: string
      },
      // ... otros campos
    }
  ]
}
```

### 1.3 Evaluaciones - Relación M:N con Topics
**Estado**: Modelo actualizado para múltiples topics
**Cambios en Frontend**:
- **Campo modificado**: `topic_id` → `topic_ids` (array)
- **Formularios de creación**: Permitir selección múltiple de topics
- **Visualización**: Mostrar múltiples topics asociados
```javascript
// Estructura anterior
{ topic_id: string }
// Estructura nueva
{ topic_ids: [string] }
```

## 🆕 2. Nuevos Endpoints para Integrar

### 2.1 Módulo de Personalización (/api/personalization/)
**Nuevos endpoints disponibles**:

#### GET /api/personalization/adaptive
**Propósito**: Obtener recomendaciones adaptativas basadas en RL
**Integración Frontend**:
```javascript
// Llamada
GET /api/personalization/adaptive?user_id={id}&module_id={id}

// Respuesta
{
  recommendations: {
    content_type: string,
    difficulty_adjustment: number,
    learning_style_focus: string,
    confidence_score: number
  },
  vakr_stats: {
    visual: number,
    auditory: number,
    kinesthetic: number,
    reading: number
  }
}
```

#### POST /api/personalization/feedback
**Propósito**: Enviar feedback de aprendizaje al sistema RL
**Integración Frontend**:
```javascript
// Enviar después de cada interacción
POST /api/personalization/feedback
{
  user_id: string,
  content_id: string,
  interaction_type: string,
  performance_score: number,
  time_spent: number,
  difficulty_rating: number
}
```

### 2.2 Completitud Automática de Contenidos
#### POST /api/content/{virtual_id}/complete-auto
**Propósito**: Marcar contenidos de solo lectura como completados
**Integración Frontend**:
```javascript
// Llamar después de interacciones no evaluativas
POST /api/content/{virtual_id}/complete-auto
{
  completion_percentage: 100,
  interaction_data: {
    time_spent: number,
    scroll_percentage: number,
    interactions_count: number
  }
}
```

### 2.3 Sistema de Workspaces Completo
**12 nuevos endpoints disponibles**:

#### GET /api/workspaces/
**Listar workspaces del usuario**
```javascript
// Respuesta
{
  data: [
    {
      _id: string,
      name: string,
      workspace_type: 'INDIVIDUAL_TEACHER' | 'INSTITUTE' | 'INDIVIDUAL_STUDENT',
      member_role: 'owner' | 'admin' | 'member' | 'viewer',
      member_count: number
    }
  ]
}
```

#### POST /api/workspaces/
**Crear nuevo workspace**
```javascript
{
  name: string,
  description?: string,
  workspace_type: 'INDIVIDUAL_TEACHER' | 'INSTITUTE'
}
```

#### POST /api/workspaces/{id}/invite
**Generar código de invitación**
```javascript
{
  role: 'admin' | 'member' | 'viewer',
  expires_in_hours?: number // Default: 24
}
```

### 2.4 Corrección Automática con IA
#### PUT /api/correction/submission/{submission_id}/ai-result
**Propósito**: Guardar resultados de corrección IA
**Integración Frontend**:
```javascript
// Después de procesar con IA en frontend
PUT /api/correction/submission/{submission_id}/ai-result
{
  ai_score: number,
  ai_feedback: string,
  ai_confidence: number,
  processing_time: number
}
```

### 2.5 Marketplace y Pagos
#### GET /api/marketplace/plans
**Listar planes públicos**
```javascript
// Respuesta
{
  data: [
    {
      _id: string,
      name: string,
      price: number,
      is_public: true,
      author_name: string,
      rating: number,
      student_count: number
    }
  ]
}
```

#### POST /api/stripe/checkout
**Crear sesión de pago**
```javascript
{
  plan_id: string,
  success_url: string,
  cancel_url: string
}
```

### 2.6 Gestión de Claves API
#### PUT /api/users/me/api-keys
**Gestionar claves de IA del usuario**
```javascript
{
  api_keys: {
    gemini?: string,
    openrouter?: string,
    groq?: string
  }
}
```

## 🔧 3. Campos Deprecados y Modificados

### 3.1 ContentResult
**Campo corregido**: Ahora usa `content_id` en lugar de `original_content_id`
**Acción Frontend**: Verificar que todas las referencias usen `content_id`

### 3.2 EvaluationSubmission
**Nuevos campos añadidos**:
```javascript
{
  // Campos existentes...
  ai_score?: number,
  ai_feedback?: string,
  ai_corrected_at?: Date
}
```

### 3.3 StudyPlanPerSubject
**Nuevos campos para marketplace**:
```javascript
{
  // Campos existentes...
  is_public: boolean,
  price?: number
}
```

### 3.4 User
**Nuevo campo para claves API**:
```javascript
{
  // Campos existentes...
  api_keys?: {
    gemini?: string,
    openrouter?: string,
    groq?: string
  }
}
```

## 🔐 4. Cambios en Autenticación y Permisos

### 4.1 Sistema de Roles en Workspaces
**Nuevos roles implementados**:
- `owner`: Acceso completo
- `admin`: Gestión de miembros y contenido
- `member`: Acceso a contenido
- `viewer`: Solo lectura

**Validación Frontend**: Verificar permisos antes de mostrar opciones de edición

### 4.2 Validaciones Previas para Módulos Virtuales
**Endpoint**: GET /api/virtual/module/{id}/validation-status
**Validaciones implementadas**:
```javascript
{
  evaluations_completed: boolean,
  critical_thinking_templates: boolean,
  interactive_content_sufficient: boolean,
  cognitive_profile_valid: boolean,
  can_proceed: boolean,
  blocking_reasons: [string]
}
```

## 🏢 5. Modificaciones en Flujo de Workspaces

### 5.1 Selección de Workspace
**Nuevo flujo requerido**:
1. Al login, verificar workspaces disponibles
2. Si múltiples workspaces, mostrar selector
3. Guardar workspace activo en contexto
4. Filtrar contenido según workspace seleccionado

### 5.2 Invitaciones
**Nuevo flujo**:
1. Generar código de invitación: POST /api/workspaces/{id}/invite
2. Unirse con código: POST /api/workspaces/join
3. Gestionar miembros: GET/PUT/DELETE /api/workspaces/{id}/members

## 🎯 6. Sistema de Personalización

### 6.1 Integración con RL
**URL del servicio**: `http://149.50.139.104:8000/api/tools/msp/execute`
**Implementación Frontend**:
```javascript
// Obtener recomendaciones
const recommendations = await fetch('/api/personalization/adaptive', {
  method: 'GET',
  params: { user_id, module_id }
});

// Enviar feedback después de cada interacción
const feedback = await fetch('/api/personalization/feedback', {
  method: 'POST',
  body: JSON.stringify({
    user_id,
    content_id,
    interaction_type: 'completion',
    performance_score: 0.85,
    time_spent: 300
  })
});
```

### 6.2 Estadísticas V-A-K-R
**Nuevo componente requerido**: Dashboard de estadísticas de aprendizaje
**Datos disponibles**:
```javascript
{
  vakr_distribution: {
    visual: 35,
    auditory: 25,
    kinesthetic: 20,
    reading: 20
  },
  learning_patterns: {
    preferred_time: 'morning',
    optimal_session_length: 45,
    difficulty_preference: 'progressive'
  },
  performance_trends: {
    improvement_rate: 0.15,
    consistency_score: 0.78
  }
}
```

## 📚 7. Cambios en Contenidos y Evaluaciones

### 7.1 Intercalación Dinámica
**Implementación**: El backend ahora intercala contenidos automáticamente
**Frontend**: Mostrar contenidos en el orden devuelto por la API (no reordenar)

### 7.2 Nuevos Tipos de Contenido
**Tipos soportados**:
- `GEMINI_LIVE`: Interacciones en tiempo real
- `MATH_EXERCISE`: Ejercicios matemáticos
- `SIMULATION`: Simulaciones interactivas
- `CRITICAL_THINKING`: Plantillas de pensamiento crítico

**Frontend**: Implementar renderizadores específicos para cada tipo

### 7.3 Progreso Automático
**Cambio**: Contenidos de solo lectura se marcan automáticamente como completados
**Implementación**:
```javascript
// Después de leer contenido
if (contentType === 'READ_ONLY') {
  await fetch(`/api/content/${virtualId}/complete-auto`, {
    method: 'POST',
    body: JSON.stringify({
      completion_percentage: 100,
      interaction_data: {
        time_spent: timeSpent,
        scroll_percentage: 100
      }
    })
  });
}
```

## 🚀 8. Plan de Implementación Frontend

### Prioridad Alta (Crítico)
1. **Corregir endpoint de templates**: Actualizar validaciones PUT /api/templates/:id
2. **Integrar workspaces**: Implementar selector y contexto de workspace
3. **Personalización básica**: Conectar con /api/personalization/adaptive
4. **Completitud automática**: Implementar POST /api/content/{id}/complete-auto

### Prioridad Media (Importante)
1. **Marketplace**: Implementar listado y compra de planes
2. **Gestión de claves API**: Añadir sección en perfil de usuario
3. **Corrección IA**: Integrar flujo de corrección automática
4. **Estadísticas V-A-K-R**: Crear dashboard de personalización

### Prioridad Baja (Mejoras)
1. **Nuevos tipos de contenido**: Renderizadores específicos
2. **Invitaciones avanzadas**: UI completa de gestión de miembros
3. **Validaciones previas**: Mostrar estado de requisitos para virtualización

## 📝 9. Checklist de Verificación

### ✅ Endpoints Actualizados
- [ ] PUT /api/templates/:id con nuevas validaciones
- [ ] GET /api/study-plan con filtrado corregido
- [ ] Evaluaciones con topic_ids (array)

### ✅ Nuevos Endpoints Integrados
- [ ] /api/personalization/* (6 endpoints)
- [ ] /api/workspaces/* (12 endpoints)
- [ ] /api/content/{id}/complete-auto
- [ ] /api/correction/submission/{id}/ai-result
- [ ] /api/marketplace/plans
- [ ] /api/stripe/checkout
- [ ] /api/users/me/api-keys

### ✅ Flujos Actualizados
- [ ] Selección y contexto de workspace
- [ ] Personalización con RL
- [ ] Completitud automática de contenidos
- [ ] Marketplace y pagos
- [ ] Gestión de claves API

### ✅ UI/UX Mejorado
- [ ] Dashboard de estadísticas V-A-K-R
- [ ] Gestión de miembros de workspace
- [ ] Marketplace de cursos
- [ ] Configuración de claves API
- [ ] Indicadores de validación para virtualización

## 🎯 Conclusión

El backend está 100% implementado y funcional. El frontend requiere estas actualizaciones para aprovechar completamente las nuevas funcionalidades. La implementación debe seguir el orden de prioridades establecido para asegurar una transición suave y funcional del sistema completo.