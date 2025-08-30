# Backlog Consolidado de Requerimientos - SapiensIA

## ⚠️ RESTRICCIÓN ARQUITECTÓNICA CRÍTICA

**LIMITACIÓN VERCEL SERVERLESS:** El backend NUNCA debe generar contenido con LLMs debido a la limitación de 1 minuto máximo en funciones serverless de Vercel. La generación de contenido es responsabilidad exclusiva del frontend.

**Responsabilidades:**
- **Frontend**: Llamadas directas a LLMs, generación en tiempo real
- **Backend**: Solo procesamiento de resultados, almacenamiento, gestión de estados

---

## Resumen Ejecutivo

Este documento consolida todos los requerimientos, funcionalidades y políticas del sistema SapiensIA, unificando la información de los tres backlogs principales del proyecto. Representa la visión completa y actualizada de todas las características que debe tener el sistema para cumplir con los objetivos educativos y técnicos establecidos.

---

## 🟡 SISTEMAS COMPLETAMENTE IMPLEMENTADOS (No requieren trabajo)

✅ **Sistema de Plantillas y Templates**: Completamente funcional  
✅ **Sistema Many-to-Many de Evaluaciones**: Implementado con topic_ids  
✅ **Sistema de Personalización con RL**: Integrado con servicio externo  
✅ **Sistema de Workspaces**: Completamente operativo  
✅ **Sistema de Contenido Virtual**: Funcional con tracking  
✅ **WeightedGradingService**: Implementado para cálculo automático  

> **NOTA IMPORTANTE**: Los sistemas listados arriba están completamente implementados y operativos. No requieren desarrollo adicional y deben considerarse como funcionalidades base ya disponibles en el sistema.

---

## 1. Sistema de Contenido en Diapositivas y Plantillas por Subtema

### 1.1 Arquitectura de Contenido en Diapositivas
- **Prioridad**: Alta
- **Estado**: Planificado
- **Descripción**: Contenido teórico dividido en diapositivas por subtema
- **Requerimientos**:
  - **Reestructuración**: Contenido teórico dividido en diapositivas por subtema
  - **TopicContent independiente**: Cada diapositiva como entidad separada
  - **Generación por IA**: Contenido automático basado en subtemas específicos
  - **Vinculación**: parent_content_id para relacionar diapositivas del mismo tema
  - **Modalidad 1**: Contenido separado - plantilla independiente del contenido teórico
  - **Modalidad 2**: Contenido embebido - plantilla integrada en la diapositiva
  - **Etiquetas**: Sistema de categorización para recomendación automática
  - **Precedencia**: Campo para determinar orden de presentación

### 1.2 Sistema de Instancias
- **Prioridad**: Alta
- **Estado**: Planificado
- **Descripción**: Contenido específico del profesor ligado a topics
- **Requerimientos**:
  - **Modelo template_instances**: ligado a templateId y topicId
  - **Pin de versión**: templateVersion para estabilidad
  - **Personalización de contenido**: props, assets, learningMix por instancia
  - **Fachada estable**: topic_contents mantiene compatibilidad con campos legacy
  - **Motor de render**: render_engine determina legacy vs html_template

### 1.3 Gestión de Resultados de Contenido
- **Prioridad**: Alta
- **Estado**: Requiere corrección
- **Descripción**: Sistema para tracking y análisis de resultados de aprendizaje
- **Requerimientos**:
  - **CRÍTICO**: Corregir asociación del modelo ContentResult para que apunte a VirtualTopicContent
  - Métricas de rendimiento por estudiante contra mix V-A-K-R
  - Análisis estadístico de efectividad por tags de plantilla
  - Reportes de progreso detallados con personalización
  - Integración con sistema de evaluaciones Many-to-Many
  - **Tracking Granular**: Seguimiento detallado de interacciones por tipo de contenido
  - **Métricas Avanzadas**: Tiempo de permanencia, intentos, progreso, engagement
  - **Análisis de Patrones**: Identificación de patrones de aprendizaje individuales

### 1.4 Niveles de Personalización
- **Prioridad**: Alta
- **Estado**: Planificado
- **Descripción**: Tres niveles de personalización para máxima flexibilidad
- **Requerimientos**:
  - **De Contenido (instancia)**: Cambio de props/activos/textos sin tocar código
  - **De Plantilla (fork)**: Clonación con modificación de código y schema
  - **Virtual (alumno)**: Overlay por estudiante con overrides específicos
  - **Extractor de marcadores**: Pipeline automático que lee data-sapiens-* y genera propsSchema
  - **Prueba live**: Panel para cambios en tiempo real sin persistir

### 1.5 Sistema de Contenido Virtual por Estudiante
- **Prioridad**: Alta
- **Estado**: Implementado parcialmente
- **Descripción**: Personalización individual con virtual_topic_contents
- **Requerimientos**:
  - **Modelo virtual_topic_contents**: Overlay por estudiante con instanceId
  - **Overrides granulares**: props, assets, difficultyAdjustment, vakHints
  - **Variables de alumno**: {{student.firstName}}, {{student.level}}
  - **Condiciones dinámicas**: data-sapiens-if="student.level>=2"
  - **Estado de activación**: control de status por contenido virtual

---

## 2. Interfaz de Usuario y Marketplace

### 2.1 Vista "Mis Plantillas" (Actualizada)
- **Prioridad**: Alta
- **Estado**: Planificado
- **Descripción**: Vista unificada para gestión de plantillas organizadas por subtema
- **Requerimientos**:
  - **Listado**: Plantillas organizadas por subtema y etiquetas
  - **Búsqueda**: Filtros por subtema, etiquetas, modalidad (separado/embebido)
  - **Edición**: Editor HTML con soporte para ambas modalidades
  - **Vinculación**: Asociación automática con diapositivas por precedencia
  - **Previsualización**: Vista previa integrada con contenido de diapositiva
  - **Flujo de creación**: Card temporal → ventana preview → botones Extraer, Probar, Guardar

### 2.2 Marketplace Público (Expandido)
- **Prioridad**: Media
- **Estado**: Planificado
- **Descripción**: Catálogo público con monetización integrada
- **Requerimientos**:
  - **Catálogo**: Plantillas y planes de estudio completos
  - **Monetización**: Integración con PayPal y Binance Pay
  - **Suscripciones**: Planes Free, Premium, Enterprise
  - **Certificación**: Sistema de validación de calidad y contenido
  - **Filtros avanzados**: Por mix V-A-K-R, styleTags, subjectTags
  - **Badges dinámicos**: "Muy visual", "Auditivo alto", etc.
  - **Acciones**: Ver, Clonar, Usar (sin edición)
  - **Sistema de Valoraciones**: Calificaciones y comentarios de usuarios sobre plantillas
  - **Búsqueda y Filtrado**: Sistema de búsqueda avanzada por categorías, materias y niveles

---

## 3. Sistema de Evaluaciones Flexible (Many-to-Many)

### 3.1 Arquitectura Many-to-Many
- **Prioridad**: Alta
- **Estado**: Requiere modificación
- **Descripción**: Sistema flexible con asociaciones múltiples
- **Requerimientos**:
  - **Relación flexible**: Evaluaciones pueden asociarse a múltiples temas
  - **Tabla intermedia**: evaluation_topics para gestionar asociaciones
  - **Ponderación**: Peso específico por tema dentro de cada evaluación
  - **Cálculo combinado**: Notas distribuidas proporcionalmente entre temas
  - **Corrección automática**: Integración con CorrectionService por IA
  - **Evaluaciones personalizadas**: Basadas en plantillas con mix V-A-K-R
  - **Feedback detallado**: Análisis por perfil cognitivo del estudiante
  - **API Keys personales**: Usuario puede usar sus propias claves de IA

### 3.2 Soporte para Entregables
- **Prioridad**: Alta
- **Estado**: Pendiente
- **Descripción**: Gestión completa de entregables y recursos
- **Requerimientos**:
  - **Tipos expandidos**: Cuestionarios, ensayos, proyectos, entregables de archivos
  - **Gestión de archivos**: Subida, descarga y versionado de entregables
  - **Recursos de apoyo**: Materiales adicionales vinculados a evaluaciones
  - **Rúbricas**: Sistema de criterios de evaluación detallados

### 3.3 Modalidades de Evaluación (Actualizada)
- **Prioridad**: Alta
- **Estado**: Pendiente
- **Descripción**: Sistema flexible con personalización adaptativa
- **Requerimientos**:
  - **Formativa**: Evaluación continua con feedback inmediato
  - **Sumativa**: Evaluación con peso distribuido entre múltiples temas
  - **Diagnóstica**: Evaluación inicial para personalización adaptativa
  - **Autoevaluación**: Evaluación reflexiva integrada con sistema V-A-K-R

### 3.4 Sistema de Recursos Evaluativos
- **Prioridad**: Media
- **Estado**: Pendiente
- **Descripción**: Gestión completa de recursos para evaluaciones
- **Requerimientos**:
  - **Recursos de Apoyo**: Rúbricas, guías, documentos de referencia para evaluaciones
  - **Recursos Entregables**: Documentos que estudiantes suben para evaluación
  - **Gestión de Recursos**: Sistema unificado para manejar diferentes tipos de recursos

---

## 4. Sistema de Corrección Automática con IA

> **⚠️ NOTA ARQUITECTÓNICA IMPORTANTE**: 
> Las llamadas a LLMs para corrección de evaluaciones se realizan en el **FRONTEND**, no en el backend, debido a las limitaciones de Vercel serverless (timeout de 1 minuto). El OCR se realiza usando **Gemini 2.5 Pro** (modelo multimodal capaz de interpretar imágenes con alta precisión). El backend solo recibe y almacena los resultados ya procesados.

### 4.1 Procesamiento de Exámenes
- **Prioridad**: Alta
- **Estado**: Nuevo módulo
- **Descripción**: Sistema completo de corrección automática usando IA
- **Requerimientos**:
  - **Reconocimiento OCR**: Procesamiento de imágenes de exámenes escritos (Frontend: Gemini 2.5 Pro)
  - **Extracción de Texto**: Conversión automática de documentos a texto procesable (Frontend)
  - **Análisis de Contenido**: Evaluación automática usando modelos de IA (Frontend)

### 4.2 Sistema de Rúbricas Inteligentes
- **Prioridad**: Alta
- **Estado**: Nuevo módulo
- **Descripción**: Rúbricas personalizables con criterios específicos
- **Requerimientos**:
  - **Rúbricas Personalizables**: Criterios de evaluación específicos por examen (Backend: almacenamiento)
  - **Criterios Granulares**: Penalizaciones por errores ortográficos, falta de pensamiento crítico, etc. (Frontend: procesamiento IA)
  - **Evaluación Contextual**: Análisis de respuestas considerando el contexto específico (Frontend: Gemini 2.5 Pro)

### 4.3 Modalidades de Corrección
- **Prioridad**: Alta
- **Estado**: Nuevo módulo
- **Descripción**: Múltiples formas de procesamiento de evaluaciones
- **Requerimientos**:
  - **Corrección de Imágenes**: Procesamiento de fotos de exámenes físicos (Frontend: Gemini 2.5 Pro OCR)
  - **Corrección de Documentos**: Evaluación de archivos digitales (PDF, Word, etc.) (Frontend: procesamiento IA)
  - **Evaluación de Código**: Corrección automática de ejercicios de programación (Frontend: análisis IA)
  - **Sandbox de Ejecución**: Entorno seguro para ejecutar y evaluar código (Frontend: ejecución local)

### 4.4 Flujo de Revisión Híbrida
- **Prioridad**: Media
- **Estado**: Nuevo módulo
- **Descripción**: Combinación de corrección automática y revisión manual
- **Requerimientos**:
  - **Corrección Automática**: Primera evaluación completamente automatizada (Frontend: procesamiento IA)
  - **Revisión Manual**: Opción para que el profesor revise y ajuste calificaciones (Backend: almacenamiento)
  - **Feedback Detallado**: Comentarios específicos generados por IA (Frontend: Gemini 2.5 Pro)
  - **Historial de Correcciones**: Seguimiento de cambios entre corrección automática y manual (Backend: persistencia)

---

## 5. Módulos Virtuales y Personalización Adaptativa

### 5.1 Generación Progresiva con Diapositivas
- **Prioridad**: Alta
- **Estado**: Implementado parcialmente
- **Descripción**: Sistema de módulos virtuales con contenido en diapositivas
- **Requerimientos**:
  - **Trigger automático**: Al alcanzar 80% de progreso en módulo actual
  - **Generación por subtemas**: Cada diapositiva generada independientemente
  - **Validaciones previas**: Evaluaciones completadas, plantillas por subtema disponibles
  - **Vinculación automática**: parent_content_id para relacionar diapositivas
  - **Colchón de Contenido**: Mantener siempre al menos dos temas futuros ya virtualizados
  - **Requisitos de Virtualización**: Un módulo solo puede virtualizarse si todos sus temas han sido preparados y publicados por el profesor

### 5.2 Personalización Adaptativa con RL
- **Prioridad**: Alta
- **Estado**: En desarrollo
- **Descripción**: Sistema de personalización con Reinforcement Learning
- **Requerimientos**:
  - **Reinforcement Learning**: Integración con modelo externo para recomendaciones
  - **Análisis V-A-K-R**: Patrones de aprendizaje basados en historial de 30 días
  - **Recomendación de plantillas**: IA sugiere plantillas por subtema según perfil
  - **Adaptación en tiempo real**: Ajuste dinámico basado en interacciones
  - **Cola de tareas**: VirtualGenerationTask para procesar generación por IA sin bloquear la experiencia del usuario
  - **Gestión de reintentos**: En caso de fallos

### 5.3 Personalización de Contenidos y Perfil Cognitivo
- **Prioridad**: Alta
- **Estado**: Implementado parcialmente
- **Descripción**: Adaptación de contenidos según perfil de aprendizaje
- **Requerimientos**:
  - **Selección de Tipos de Contenido**: Conjunto equilibrado de contenidos (~6 por tema) adaptados al CognitiveProfile
  - **Balance de contenidos**: Al menos un contenido "completo" (que cubra todo el tema) y otros interactivos (juegos, diagramas) para subtemas
  - **Cobertura completa**: Los contenidos en conjunto deben cubrir todo el material sin dejar lagunas
  - **Adaptación a Nivel de Contenido**: Personalización de fragmentos según contexto del estudiante
  - **Intercalación de Contenidos**: Presentación dinámica (ej. diapositiva → juego → diapositiva → diagrama)

### 5.4 Motor de Personalización Adaptativa (Aprendizaje por Refuerzo)
- **Prioridad**: Alta
- **Estado**: Planificado
- **Descripción**: Motor híbrido que aprende de los ContentResult
- **Requerimientos**:
  - **Análisis de efectividad**: Qué tipos de contenido evaluativo son más efectivos para cada alumno
  - **Ajuste de recomendaciones**: Basado en desempeño del alumno
  - **Feedback subjetivo**: Solicitar feedback al final de tema/módulo
  - **Complemento al perfil estático**: No elimina el perfil cognitivo anterior, lo complementa

### 5.5 Tipos de Contenido Educativo Expandidos
- **Prioridad**: Media
- **Estado**: En expansión
- **Descripción**: Ampliar catálogo de tipos de contenido dinámicos
- **Requerimientos**:
  - **Contenidos Interactivos**: Juegos educativos, simulaciones, laboratorios virtuales
  - **Contenidos Multimedia**: Videos adaptativos, podcasts, presentaciones interactivas
  - **Contenidos Evaluativos**: Quiz adaptativos, ejercicios prácticos, casos de estudio
  - **Contenidos Teóricos**: Lecturas personalizadas, resúmenes adaptativos, mapas conceptuales
  - **Formatos dinámicos**: GEMINI_LIVE (conversaciones con IA), ejercicios de programación con auto-verificación
  - **Ejercicios matemáticos**: Glosarios interactivos y dinámicas de completación

### 5.6 Generación Automática de Contenidos con Múltiples Modelos
- **Prioridad**: Alta
- **Estado**: En desarrollo
- **Descripción**: Aceleración de generación usando múltiples modelos en paralelo
- **Requerimientos**:
  - **Generación paralela**: Hasta 3 modelos de IA en paralelo para poblar contenidos rápidamente
  - **Distribución inteligente**: Modelo más potente (Gemini 1.5 Pro) para tareas complejas, modelos rápidos (Gemini Flash) para otros contenidos
  - **Tolerancia a fallos**: Reintentar con otro modelo en caso de fallo
  - **Persistencia**: Generación en segundo plano que continúa aunque el usuario navegue
  - **Notificaciones**: Progreso visible incluso si se recarga la página

### 5.7 Contenido Teórico con Principios Fundamentales
- **Prioridad**: Media
- **Estado**: Planificado
- **Descripción**: Metodología de primeros principios para contenido explicativo
- **Requerimientos**:
  - **Método Feynman**: Explicaciones desde principios fundamentales
  - **Comprensión conceptual**: Enfoque en entendimiento profundo vs memorización
  - **Aplicación práctica**: Capacidad de crear "nuevas recetas" a partir de principios básicos

### 5.8 Desbloqueo, Seguimiento de Progreso y Actualizaciones
- **Prioridad**: Media
- **Estado**: Implementado parcialmente
- **Descripción**: Sistema de progreso y manejo de actualizaciones en curso
- **Requerimientos**:
  - **Navegación secuencial**: Desbloqueo lineal-condicional de contenidos
  - **Registro de progreso**: A nivel de contenido, tema y módulo
  - **Política de actualizaciones**: Manejo de cambios del profesor en módulos en curso
  - **Política propuesta**: Nuevo contenido se agrega al final de la lista de contenidos no vistos

---

## 6. Arquitectura Técnica y Servicios (Actualizada)

### 6.1 Arquitectura Modular con Workspaces
- **Prioridad**: Alta
- **Estado**: En desarrollo
- **Descripción**: Arquitectura escalable con sistema de workspaces
- **Requerimientos**:
  - **Sistema de Workspaces**: Gestión unificada de espacios de trabajo
  - **Roles y permisos**: Owner, Admin, Member, Viewer con permisos específicos
  - **Invitaciones**: Sistema de códigos de acceso y gestión de miembros
  - **APIs RESTful**: 12 endpoints para gestión completa de workspaces
  - **Pool de generación**: 5 hilos asíncronos configurables
  - **Servicios especializados**: TemplateService, InstanceService, VirtualizationService
  - **Seguridad**: iframe sandbox + CSP estricta para previews

### 6.2 Gestión de Estado y Pagos
- **Prioridad**: Media
- **Estado**: Planificado
- **Descripción**: Control de estado con integración de pagos
- **Requerimientos**:
  - **Encriptación de API Keys**: Almacenamiento seguro de claves de usuario
  - **Integración de pagos**: PayPal y Binance Pay para suscripciones
  - **Planes de suscripción**: Free, Premium, Enterprise con límites específicos
  - **PlanService**: Verificación automática de límites por plan
  - **Estados de generación**: draft, processing, completed, failed por contenido
  - **Notificaciones persistentes**: Toasts granulares con botón de cierre
  - **Error handling**: Recuperación automática y logs detallados

### 6.3 Backend Mejorado
- **Prioridad**: Alta
- **Estado**: En desarrollo
- **Descripción**: Mejoras en la arquitectura del backend
- **Requerimientos**:
  - **APIs de Plantillas**: Endpoints para gestión completa de plantillas e instancias
  - **Motor de Personalización**: Servicios para procesamiento de personalización híbrida
  - **Servicios de IA**: Integración con modelos de visión y procesamiento de lenguaje natural
  - **Sistema de Caching**: Optimización de rendimiento para contenido personalizado

### 6.4 Frontend Evolucionado
- **Prioridad**: Alta
- **Estado**: En desarrollo
- **Descripción**: Mejoras en la interfaz de usuario
- **Requerimientos**:
  - **Editor Visual de Plantillas**: Interfaz drag-and-drop para creación de plantillas
  - **Marketplace Integrado**: Interfaz completa para explorar y usar plantillas públicas
  - **Dashboard de Personalización**: Visualización de métricas de personalización
  - **Sistema de Corrección**: Interfaz para subir exámenes y revisar correcciones automáticas

---

## 7. Motor de Personalización Híbrido

### 7.1 Motor de Personalización Híbrido (Dos Fases)
- **Prioridad**: Alta
- **Estado**: Planificado
- **Descripción**: Engine híbrido estadístico + IA para personalización avanzada
- **Requerimientos**:
  - **Fase 1 - Estadística**: Análisis del historial de ContentResult contra tags y mix V-A-K-R
  - **Fase 2 - IA**: Refinamiento del perfil cognitivo mediante aprendizaje automático
  - **Adaptación dinámica**: Dificultad por estudiante
  - **Recomendaciones**: Contenido basado en rendimiento histórico
  - **Integración**: Con sistema de evaluaciones Many-to-Many
  - **Reglas estrictas**: Habilitación más estricta para virtualización

### 7.2 Tres Niveles de Personalización
- **Prioridad**: Alta
- **Estado**: Implementado parcialmente
- **Descripción**: Sistema de personalización en múltiples niveles
- **Requerimientos**:
  - **Nivel Básico**: Personalización basada en perfil VARK del estudiante
  - **Nivel Adaptativo**: Motor estadístico que ajusta contenido según rendimiento histórico
  - **Nivel Híbrido**: Combinación de estadísticas + Reinforcement Learning para personalización avanzada

### 7.3 Motor de Recomendaciones
- **Prioridad**: Media
- **Estado**: Planificado
- **Descripción**: Sistema inteligente de recomendaciones
- **Requerimientos**:
  - **Rutas de Aprendizaje**: Sugerencias de contenido basadas en progreso y rendimiento
  - **Contenido Complementario**: Recomendaciones de recursos adicionales
  - **Predicción de Dificultades**: Identificación temprana de áreas problemáticas

---

## 8. Modelos de Datos Detallados

### 8.1 Modelo templates
```json
{
  "_id": "tpl_mindmap_v1",
  "name": "Mindmap Interactivo",
  "ownerId": "user_123",
  "scope": "private",
  "status": "draft",
  "personalization": {
    "isExtracted": false,
    "extractedAt": null
  },
  "engine": "html",
  "version": "1.0.0",
  "forkOf": null,
  "html": "<!DOCTYPE html>...</html>",
  "propsSchema": {},
  "defaults": {},
  "baselineMix": {"V":60,"A":10,"K":20,"R":10},
  "capabilities": {"audio":false, "mic":false, "camera":false},
  "styleTags": ["interactivo","diagrama"],
  "subjectTags": ["astronomía","biología"]
}
```

### 8.2 Modelo template_instances
```json
{
  "_id": "inst_456",
  "templateId": "tpl_mindmap_v1",
  "templateVersion": "1.0.0",
  "topicId": "topic_abc",
  "props": {},
  "assets": [{"id":"bg","src":"/cdn/bg.png"}],
  "learningMix": {"mode":"auto","V":70,"A":10,"K":15,"R":5},
  "status": "draft"
}
```

### 8.3 Modelo topic_contents (actualizado)
```json
{
  "_id": "content_abc",
  "topic_id": "topic_abc",
  "content_type": "diagram",
  "content": {},
  "render_engine": "html_template",
  "instanceId": "inst_456",
  "templateId": "tpl_mindmap_v1",
  "templateVersion": "1.0.0",
  "learningMix": {"V":70,"A":10,"K":15,"R":5},
  "status": "draft"
}
```

### 8.4 Modelo virtual_topic_contents (actualizado)
```json
{
  "_id": "vtc_999",
  "content_id": "content_abc",
  "instanceId": "inst_456",
  "student_id": "stu_123",
  "overrides": {
    "props": {"accentColor":"#2244ff"},
    "assets": [{"id":"avatar","src":"/cdn/avatars/s_123.png"}],
    "difficultyAdjustment": 1,
    "vakHints": {"preferA": true}
  },
  "status": "active"
}
```

---

## 9. APIs Mínimas Requeridas

### 9.1 Plantillas
- `POST /api/templates` - Crear nueva plantilla
- `GET /api/templates` - Listar plantillas del usuario
- `PUT /api/templates/:id` - Actualizar plantilla
- `POST /api/templates/:id/fork` - Crear fork de plantilla
- `POST /api/templates/:id/extract` - Extraer marcadores

### 9.2 Instancias
- `POST /api/template-instances` - Crear instancia
- `GET /api/template-instances/:id` - Obtener instancia
- `PUT /api/template-instances/:id` - Actualizar instancia
- `POST /api/template-instances/:id/publish` - Publicar instancia

### 9.3 Preview y Render
- `GET /api/preview/template/:templateId` - Preview de plantilla
- `GET /api/preview/instance/:instanceId` - Preview de instancia

### 9.4 Marketplace
- `GET /api/marketplace/templates` - Listar plantillas públicas

---

## 10. Plan de Implementación Consolidado

### FASE 1: Cimientos, Correcciones Críticas y Fundamentos de Plantillas (Prioridad CRÍTICA)
**Tiempo estimado: 3-4 semanas**

#### Correcciones de Backend Fundamentales:
- **B**: Corregir la asociación del modelo ContentResult para que apunte a VirtualTopicContent (máxima prioridad técnica)
- **B**: Corregir el bug en trigger_next_topic (cambiar progress < 0.8 por progress < 80)
- **F/B**: Alinear los endpoints de Perfil Cognitivo (/api/profiles/cognitive) y Verificación de Usuario (/api/users/check)

#### Fundamentos del Ecosistema de Plantillas (Backend):
- **B**: Implementar en la base de datos los nuevos modelos: `templates` y `template_instances` con todos los campos especificados
- **B**: Modificar los modelos existentes `topic_contents` y `virtual_topic_contents` para añadir los campos `render_engine`, `instanceId`, `templateId`, `templateVersion`, `learningMix` (cacheado) y `overrides`, asegurando la retrocompatibilidad
- **B**: Crear las APIs mínimas para el CRUD de plantillas: `POST /api/templates`, `GET /api/templates?owner=me...`, `PUT /api/templates/:id`

#### Autenticación y Dashboards:
- **F/B**: Implementar la autenticación con email/contraseña y el flujo de recuperación de contraseña
- **F/B**: Conectar los indicadores de los dashboards a los datos reales del backend (progreso, calificaciones), eliminando métricas obsoletas como el control de asistencia

#### Corrección de Bugs de UI:
- **F**: Implementar la lógica en el Sidebar del Alumno para manejar el caso de no tener módulos virtuales generados, ofreciendo iniciar la generación

### FASE 2: UI "Mis Plantillas" y Flujo de Creación (Hitos A y B)
**Tiempo estimado: 4-5 semanas**

#### UI "Mis Plantillas" y Flujo de Creación:
- **F**: Reutilizar y rediseñar la vista de "Juegos y Simulaciones" como "Mis Plantillas". Implementar el listado, buscador, filtros, y la card de plantilla con sus badges, toggles y botones de acción (Ver, Editar, Clonar, Usar)
- **F/B**: Implementar el flujo completo de creación de plantillas, incluyendo la previsualización en ventana nueva (`/preview/template/:id`) y el editor de código con carga lazy
- **B**: Desarrollar el servicio Extractor de Marcadores (`POST /api/templates/:id/extract`) que parsea el HTML y genera/actualiza el propsSchema
- **F**: Implementar el panel "Probar personalización (live)" que se comunica con el iframe de preview vía postMessage para aplicar cambios de props en tiempo real sin guardarlos

#### Instancias y Sistema de Evaluaciones Completo:
- **B**: Modificar el modelo Evaluation para permitir la asociación Many-to-Many con Topics
- **F/B**: Implementar el flujo de "Usar como contenido", que crea una TemplateInstance (`POST /api/template-instances`) y actualiza el TopicContent correspondiente para usar `render_engine: 'html_template'`
- **F/B**: Implementar el ciclo de vida completo de Recurso-Plantilla -> Descarga -> Entrega para las evaluaciones

#### Vistas de Profesor Individual:
- **F**: Crear las páginas `/teacher/private-classes` y `/teacher/private-students`
- **B**: Adaptar memberService.ts para soportar la inscripción directa

### FASE 3: Motor de Personalización y Generación Paralela (Prioridad ALTA)
**Tiempo estimado: 3-4 semanas**

#### Motor de Personalización Estadístico:
- **B**: Crear el servicio backend que, a partir del historial de ContentResult de un usuario, analiza estadísticamente el rendimiento contra los tags y mix V-A-K-R de las plantillas para refinar el perfil cognitivo del alumno

#### Mejoras en Generación de Contenido:
- **B**: Refactorizar el servicio de generación de contenido para usar un pool configurable de 5 hilos asíncronos, con asignación de modelos por hilo definida en un archivo de configuración
- **F**: Implementar las notificaciones (toasts) granulares y persistentes con botón de cierre para el proceso de generación de contenido

#### Integración de IA y Gestión de APIs:
- **F/B**: Implementar la sección en el perfil de usuario para que pueda introducir sus propias API Keys. Modificar los servicios de IA para usar estas claves como prioridad sobre las del sistema
- **B/F**: Conectar el servicio de subida de entregas con el CorrectionService para disparar la corrección automática por IA

### FASE 4: Sistema de Corrección Automática y Marketplace (Hitos D, E, F)
**Tiempo estimado: 4-5 semanas**

#### Sistema de Corrección Automática:
- **B/F**: Implementar el módulo completo de corrección automática con OCR, análisis de contenido y rúbricas inteligentes
- **B/F**: Desarrollar las modalidades de corrección (imágenes, documentos, código) con sandbox de ejecución
- **F**: Crear la interfaz para subir exámenes y revisar correcciones automáticas

#### Lanzamiento del Marketplace Público:
- **F/B**: Desarrollar la vista pública del Marketplace (`GET /api/marketplace/templates?scope=public...`)
- **F/B**: Implementar la capacidad de embeber instancias de plantillas dentro de diapositivas (iframe)
- **B**: Implementar el flujo de "Certificación" para plantillas, con las validaciones correspondientes

#### Finalización de Funcionalidades Pendientes:
- **F/B**: Finalizar y pulir las Herramientas de Concentración (Pomodoro) y revisar el soporte a Lenguas Indígenas
- **B/F**: Completar y probar exhaustivamente la lógica de eliminación en cascada en todo el sistema

### FASE 5: Funcionalidades Avanzadas y Optimización
**Tiempo estimado: 3-4 semanas**

#### Expansiones del Sistema:
- **B/F**: Evaluación Automática de Entregables usando rúbricas predefinidas
- **B**: Análisis de Plagio con detección automática de contenido duplicado
- **B**: Evaluación de Creatividad con métricas para originalidad y pensamiento crítico

#### Vistas de Estudiante Individual y App Móvil:
- **F**: Crear las páginas `/student/learning`, `/student/study-plan` y `/student/progress`
- **QA/Mobile**: Iniciar el desarrollo de la aplicación móvil, comenzando con las funcionalidades priorizadas

---

## 11. Consideraciones de Implementación

### 11.1 Prioridades de Desarrollo
1. **Completar Sistema de Evaluaciones Flexible** (Alta prioridad)
2. **Implementar Módulo de Corrección Automática** (Alta prioridad)
3. **Mejorar Motor de Personalización Híbrido** (Media prioridad)
4. **Expandir Tipos de Contenido** (Media prioridad)

### 11.2 Restricciones Técnicas
- **Minimizar Cambios en Backend**: Aprovechar arquitectura existente cuando sea posible
- **Compatibilidad**: Mantener compatibilidad con funcionalidades existentes
- **Escalabilidad**: Diseñar para soportar crecimiento de usuarios y contenido
- **Seguridad**: Implementar medidas robustas para protección de datos educativos

### 11.3 Funcionalidades Futuras
- **Aplicación Móvil Completa**: Versión móvil con todas las funcionalidades
- **Marketplace de Cursos**: Plataforma para venta de cursos completos
- **Integración con LMS**: Conectores para sistemas de gestión de aprendizaje externos

---

## 12. Conclusión del Análisis Consolidado

El sistema SapiensIA representa una plataforma educativa integral que combina personalización avanzada, inteligencia artificial y metodologías pedagógicas modernas. La consolidación de estos requerimientos establece una hoja de ruta clara para el desarrollo de un sistema que:

1. **Personaliza el aprendizaje** a través de múltiples niveles de adaptación
2. **Automatiza la evaluación** mediante IA y corrección inteligente
3. **Facilita la creación de contenido** con plantillas reutilizables y marketplace
4. **Optimiza el rendimiento** con generación paralela y arquitectura modular
5. **Escala eficientemente** para soportar crecimiento institucional

La implementación exitosa de estos requerimientos posicionará a SapiensIA como una solución líder en el mercado de tecnología educativa, proporcionando una experiencia de aprendizaje verdaderamente personalizada y efectiva para estudiantes y educadores.