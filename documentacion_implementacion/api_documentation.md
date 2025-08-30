# Documentación de API - SapiensAI Backend

## Información General

- **Base URL**: `http://localhost:5000`
- **Autenticación**: JWT Bearer Token
- **Formato de respuesta**: JSON
- **Versionado**: v1

## Estructura de Respuesta Estándar

```json
{
  "success": true|false,
  "data": {},
  "message": "string",
  "error_code": "string" // Solo en errores
}
```

## Endpoints por Módulo

### 1. Autenticación y Usuarios (`/api/users`)

#### Registro de Usuario
- **POST** `/api/users/register`
- **Descripción**: Registra un nuevo usuario
- **Body**: `{"email": "string", "password": "string", "name": "string"}`

#### Inicio de Sesión
- **POST** `/api/users/login`
- **Descripción**: Autentica un usuario
- **Body**: `{"email": "string", "password": "string"}`

#### Verificación de Token
- **POST** `/api/users/check`
- **Descripción**: Verifica la validez del token JWT

#### Perfil Cognitivo
- **GET** `/api/users/profile/cognitive`
- **PUT** `/api/users/profile/cognitive`
- **Descripción**: Obtiene/actualiza el perfil cognitivo del usuario

#### Gestión de Institutos
- **GET** `/api/users/my-institutes`
- **POST** `/api/users/switch-institute/{institute_id}`

#### Recuperación de Contraseña
- **POST** `/api/users/forgot-password`
- **POST** `/api/users/reset-password`

#### Perfil de Usuario
- **GET** `/api/users/me`
- **PUT** `/api/users/me/api-keys`

### 2. Contenido (`/api/content`)

#### Tipos de Contenido
- **GET** `/api/content/types`
- **Descripción**: Obtiene los tipos de contenido disponibles

#### Gestión de Contenido
- **POST** `/api/content/`
- **GET** `/api/content/`
- **Descripción**: Crea/obtiene contenido unificado
- **Parámetros de consulta**: `topic_id`, `content_type`, `interactive_only`

#### Contenido por ID
- **GET** `/api/content/{content_id}`
- **Descripción**: Obtiene contenido específico por ID

### 3. Plantillas de Contenido (`/api/content/templates`)

#### Gestión de Plantillas
- **POST** `/api/content/templates`
- **GET** `/api/content/templates`
- **GET** `/api/content/templates/{template_id}`
- **PUT** `/api/content/templates/{template_id}`
- **DELETE** `/api/content/templates/{template_id}`

#### Operaciones de Plantillas
- **POST** `/api/content/templates/{template_id}/fork`
- **POST** `/api/content/templates/{template_id}/extract`
- **GET** `/api/content/templates/recommendations`

#### Instancias de Plantillas
- **POST** `/api/content/instances`
- **GET** `/api/content/instances/{instance_id}`
- **GET** `/api/content/instances/topic/{topic_id}`
- **PUT** `/api/content/instances/{instance_id}`
- **POST** `/api/content/instances/{instance_id}/publish`
- **DELETE** `/api/content/instances/{instance_id}`

### 4. Módulos Virtuales (`/api/virtual`)

#### Gestión de Módulos
- **POST** `/api/virtual/module`
- **GET** `/api/virtual/module/{module_id}`
- **GET** `/api/virtual/modules`
- **PUT** `/api/virtual/module/{module_id}/progress`
- **GET** `/api/virtual/module/{module_id}/progress`

#### Gestión de Temas
- **POST** `/api/virtual/topic`
- **GET** `/api/virtual/module/{module_id}/topics`
- **GET** `/api/virtual/topic/{virtual_topic_id}/contents`

#### Resultados de Contenido
- **POST** `/api/virtual/content-result`
- **GET** `/api/virtual/content-results/student/{student_id}`

#### Generación Progresiva
- **POST** `/api/virtual/progressive-generation`
- **POST** `/api/virtual/trigger-next-generation`
- **POST** `/api/virtual/trigger-next-topic`
- **GET** `/api/virtual/generation-status/{student_id}`

#### Autocompletado de Contenido
- **POST** `/api/virtual/content/{virtual_content_id}/complete-auto`
- **POST** `/api/virtual/content/{virtual_content_id}/complete-reading`

#### Sincronización
- **POST** `/api/virtual/module/{virtual_module_id}/sync-auto`
- **POST** `/api/virtual/sync/bulk`
- **POST** `/api/virtual/sync/schedule`
- **GET** `/api/virtual/module/{virtual_module_id}/sync-status`

#### Métricas y Optimización
- **POST** `/api/virtual/ui-metrics`
- **GET** `/api/virtual/ui-optimizations`
- **GET** `/api/virtual/ui-config`
- **GET** `/api/virtual/performance-analytics`

### 5. Evaluaciones (`/api/evaluations`)

#### Gestión de Evaluaciones
- **POST** `/api/evaluations/`
- **POST** `/api/evaluations/multi-topic`
- **GET** `/api/evaluations/{evaluation_id}`
- **PUT** `/api/evaluations/{evaluation_id}`
- **DELETE** `/api/evaluations/{evaluation_id}`

#### Envíos y Calificaciones
- **POST** `/api/evaluations/{evaluation_id}/submissions`
- **GET** `/api/evaluations/{evaluation_id}/submissions/{student_id}`
- **POST** `/api/evaluations/submissions/{submission_id}/grade`
- **PUT** `/api/evaluations/{evaluation_id}/weights`

#### Rúbricas
- **POST** `/api/evaluations/rubrics`
- **POST** `/api/evaluations/submissions/{submission_id}/grade-with-rubric`

#### Evaluaciones por Tema
- **GET** `/api/evaluations/by-topic/{topic_id}`
- **GET** `/api/evaluations/students/{student_id}/summary`

#### Operaciones en Lote
- **POST** `/api/evaluations/bulk/create`
- **POST** `/api/evaluations/{evaluation_id}/recalculate-all-grades`

### 6. Recursos (`/api/resources`)

#### Gestión de Recursos
- **GET** `/api/resources/`
- **POST** `/api/resources/`
- **GET** `/api/resources/{resource_id}`
- **PUT** `/api/resources/{resource_id}`
- **DELETE** `/api/resources/{resource_id}`
- **PUT** `/api/resources/{resource_id}/move`

#### Recursos para Profesores
- **GET** `/api/resources/teacher`
- **POST** `/api/resources/teacher`
- **GET** `/api/resources/teacher/tree`

#### Gestión de Carpetas
- **POST** `/api/resources/folders`
- **GET** `/api/resources/folders/{folder_id}`
- **GET** `/api/resources/folders/{folder_id}/resources`
- **PUT** `/api/resources/folders/{folder_id}`
- **DELETE** `/api/resources/folders/{folder_id}`
- **GET** `/api/resources/folders/tree`

### 7. Clases (`/api/classes`)

#### Gestión de Clases
- **POST** `/api/classes/create`
- **GET** `/api/classes/{class_id}`
- **PUT** `/api/classes/{class_id}/update`
- **DELETE** `/api/classes/{class_id}`
- **GET** `/api/classes/{class_id}/check-dependencies`

### 8. Planes de Estudio (`/api/study-plans`)

#### Gestión de Planes
- **POST** `/api/study-plans/`
- **GET** `/api/study-plans/`
- **GET** `/api/study-plans/{plan_id}`
- **PUT** `/api/study-plans/{plan_id}`
- **DELETE** `/api/study-plans/{plan_id}`

#### Asignaciones
- **POST** `/api/study-plans/assignment`
- **DELETE** `/api/study-plans/assignment/{assignment_id}`
- **GET** `/api/study-plans/assignments`

#### Módulos
- **POST** `/api/study-plans/module`
- **GET** `/api/study-plans/module/{module_id}`
- **PUT** `/api/study-plans/module/{module_id}`
- **DELETE** `/api/study-plans/module/{module_id}`

#### Temas
- **POST** `/api/study-plans/topic`
- **GET** `/api/study-plans/topic`
- **PUT** `/api/study-plans/topic/{topic_id}`
- **DELETE** `/api/study-plans/topic/{topic_id}`
- **PUT** `/api/study-plans/topic/{topic_id}/publish`

### 9. Corrección Automática (`/api/correction`)

#### Gestión de Correcciones
- **PUT** `/api/correction/submission/{submission_id}/ai-result`
- **POST** `/api/correction/start`
- **GET** `/api/correction/task/{task_id}`
- **PUT** `/api/correction/task/{task_id}`
- **POST** `/api/correction/process-next`

### 10. Personalización (`/api/personalization`)

#### Personalización Adaptativa
- **POST** `/api/personalization/adaptive`
- **POST** `/api/personalization/feedback`

#### Análisis VAKR
- **GET** `/api/personalization/analytics/vakr/{student_id}`
- **GET** `/api/personalization/statistics/vakr/{student_id}`
- **GET** `/api/personalization/analytics/compare/{student_id}`

### 11. Analíticas (`/api/analytics`)

#### Análisis de Estudiantes
- **GET** `/api/analytics/student/{student_id}/performance`
- **GET** `/api/analytics/student/{student_id}/subjects`

#### Análisis de Clases
- **GET** `/api/analytics/class/{class_id}/statistics`
- **GET** `/api/analytics/class/{class_id}/comprehensive`
- **GET** `/api/analytics/class/{class_id}/dashboard`

#### Análisis de Evaluaciones
- **GET** `/api/analytics/evaluation/{evaluation_id}/analytics`

#### Análisis de Institutos
- **GET** `/api/analytics/institute/{institute_id}/statistics`
- **GET** `/api/analytics/institute/{institute_id}/statistics/history`
- **GET** `/api/analytics/institute/statistics/compare`

### 12. Investigación Profunda (`/api/deep-research`)

#### Búsqueda y Extracción
- **GET/POST** `/api/deep-research/search`
- **GET/POST** `/api/deep-research/search/unified`
- **POST** `/api/deep-research/extract`

#### Procesamiento con IA
- **POST** `/api/deep-research/ai/format`
- **POST** `/api/deep-research/ai/suggest-questions`
- **POST** `/api/deep-research/ai/process`

#### Gestión de Sesiones
- **POST** `/api/deep-research/session`
- **GET** `/api/deep-research/session/{session_id}`
- **PUT** `/api/deep-research/session/{session_id}`
- **DELETE** `/api/deep-research/session/{session_id}`

### 13. Idiomas Indígenas (`/api/indigenous-languages`)

#### Traducciones
- **POST** `/api/indigenous-languages/translations`
- **GET** `/api/indigenous-languages/translations`
- **PUT** `/api/indigenous-languages/{translation_id}`
- **DELETE** `/api/indigenous-languages/{translation_id}`

#### Búsqueda y Idiomas
- **GET** `/api/indigenous-languages/search`
- **GET** `/api/indigenous-languages/languages`
- **POST** `/api/indigenous-languages/language`
- **GET** `/api/indigenous-languages/language-pairs`

#### Verificadores
- **POST** `/api/indigenous-languages/verificadores`
- **GET** `/api/indigenous-languages/verificadores`
- **PUT** `/api/indigenous-languages/verificadores/{verificador_id}`
- **DELETE** `/api/indigenous-languages/verificadores/{verificador_id}`

### 14. Marketplace (`/api/marketplace`)

#### Planes y Suscripciones
- **GET** `/api/marketplace/plans`
- **POST** `/api/marketplace/checkout/{plan_id}`
- **GET** `/api/marketplace/subscription/plans`
- **GET** `/api/marketplace/subscription/current`
- **GET** `/api/marketplace/subscription/limits`

#### Webhooks de Pago
- **POST** `/api/marketplace/stripe-webhook`
- **POST** `/api/marketplace/paypal-webhook`
- **POST** `/api/marketplace/binance-webhook`

#### Administración
- **GET** `/api/marketplace/admin/transactions`
- **GET** `/api/marketplace/admin/subscriptions`

### 15. Workspaces (`/api/workspaces`)

#### Gestión de Workspaces
- **GET** `/api/workspaces/`
- **POST** `/api/workspaces/switch/{workspace_id}`
- **GET** `/api/workspaces/{workspace_id}`
- **PATCH** `/api/workspaces/{workspace_id}`

#### Workspaces Personales
- **POST** `/api/workspaces/personal`
- **GET/POST** `/api/workspaces/{workspace_id}/personal-study-plans`
- **GET/POST/PUT/DELETE** `/api/workspaces/{workspace_id}/study-goals`

### 16. Dashboards (`/api/dashboards`)

#### Dashboards por Rol
- **GET** `/api/dashboards/admin`
- **GET** `/api/dashboards/teacher`
- **GET** `/api/dashboards/student/{student_id}`
- **GET** `/api/dashboards/institute/{institute_id}`
- **GET** `/api/dashboards/individual/student`
- **GET** `/api/dashboards/individual/teacher`
- **GET** `/api/dashboards/workspace/summary`

### 17. Utilidades del Sistema

#### Limpieza en Cascada (`/api/cascade`)
- **DELETE** `/api/cascade/delete/{collection}/{entity_id}`
- **POST** `/api/cascade/cleanup/{collection}`
- **GET** `/api/cascade/report/{collection}/{entity_id}`
- **POST** `/api/cascade/cleanup-all`
- **GET** `/api/cascade/health`

## Códigos de Error Comunes

- `MISSING_FIELDS`: Campos requeridos faltantes
- `VALIDATION_ERROR`: Error de validación de datos
- `NOT_FOUND`: Recurso no encontrado
- `PERMISSION_DENIED`: Permisos insuficientes
- `SERVER_ERROR`: Error interno del servidor
- `CREATION_ERROR`: Error al crear recurso
- `UPDATE_ERROR`: Error al actualizar recurso
- `DELETE_ERROR`: Error al eliminar recurso

## Roles de Usuario

- `ADMIN`: Administrador del sistema
- `INSTITUTE_ADMIN`: Administrador de instituto
- `TEACHER`: Profesor
- `STUDENT`: Estudiante

## Notas de Implementación

1. Todos los endpoints requieren autenticación JWT excepto login y register
2. Los endpoints están organizados por módulos funcionales
3. Se utiliza el patrón APIRoute.standard para respuestas consistentes
4. Los workspaces proporcionan aislamiento de datos por contexto
5. El sistema soporta múltiples tipos de contenido y plantillas
6. La personalización adaptativa utiliza análisis VAKR
7. El sistema incluye corrección automática con IA
8. Soporte para idiomas indígenas con verificadores
9. Marketplace integrado con múltiples proveedores de pago
10. Análisis completo de rendimiento y métricas

---

*Documentación generada automáticamente - Última actualización: $(date)*