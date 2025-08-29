# Plan de Implementación Actualizado con Sistema de Plantillas - SapiensIA

## Evolución Arquitectónica y Estado Actual

### 1. Sistema de Plantillas e Instancias (IMPLEMENTADO)

**Arquitectura Core:**
- ✅ **Modelo Template**: Plantillas HTML interactivas con schema de parámetros
- ✅ **Modelo TemplateInstance**: Instancias personalizadas con props específicos
- ✅ **Sistema de Marcadores**: Extracción automática de parámetros (`data-sapiens-param`, `data-sapiens-asset`)
- ✅ **Motor de Renderizado**: Render dinámico HTML + props en tiempo real
- ✅ **Marketplace Privado**: Gestión de plantillas por profesor

**Funcionalidades Operativas:**
- ✅ Editor de plantillas con Monaco Editor y realce de sintaxis
- ✅ Previsualización en vivo con iframe sandbox y postMessage
- ✅ Formularios dinámicos basados en propsSchema
- ✅ Clonación y versionado con POST /api/templates/{id}/fork
- ✅ Integración seamless con TopicContent existente
- ✅ Sistema de scopes: private, org, public

**APIs Implementadas:**
```
POST /api/templates - Crear plantilla
GET /api/templates - Listar plantillas con filtros
PUT /api/templates/{id} - Actualizar plantilla
POST /api/templates/{id}/extract - Extraer marcadores
POST /api/templates/{id}/fork - Clonar plantilla
POST /api/template-instances - Crear instancia
GET /preview/instance/{instanceId} - Render en vivo
```

### 2. Tres Niveles de Personalización (ARQUITECTURA HÍBRIDA)

**Nivel 1 - Personalización Básica (✅ IMPLEMENTADO):**
- Adaptación inicial basada en perfil VARK del estudiante
- Selección de tipos de contenido según preferencias cognitivas
- Ajuste de dificultad según nivel académico

**Nivel 2 - Personalización Adaptativa (🔄 EN DESARROLLO):**
- Motor estadístico que analiza ContentResult históricos
- Cálculo de contentPreferences basado en performance
- Ajuste dinámico de tipos de contenido según éxito/fracaso
- Retroalimentación continua del sistema

**Nivel 3 - Personalización Híbrida (🔄 PLANIFICADO):**
- Combinación de motor estadístico + Reinforcement Learning
- Predicción de contenido óptimo usando ML avanzado
- Adaptación en tiempo real durante la sesión de estudio
- Optimización multi-objetivo (engagement, retención, performance)

### 3. Módulos Virtuales Evolucionados

**Estado Actual:**
- ✅ VirtualModule y VirtualTopic con soporte para plantillas
- ✅ VirtualTopicContent con instanceId para contenidos basados en plantillas
- ✅ Generación automática que combina IA + plantillas predefinidas
- ✅ Sistema de progresión que incluye contenidos interactivos

**Nuevas Capacidades:**
- ✅ **Contenido Híbrido**: Mezcla de contenido generado por IA y plantillas
- ✅ **Render Condicional**: TopicContent con render_engine="html_template"
- ✅ **Personalización de Instancias**: Props ajustados por perfil del estudiante
- 🔄 **Overrides Estudiantiles**: Personalización a nivel individual (Fase 5)

### 4. Sistema de Evaluaciones Avanzado (PENDIENTE MEJORAS)

**Estado Actual:**
- ✅ Evaluaciones básicas por tema
- ✅ ContentResult para tracking de progreso
- ✅ Integración con sistema de calificaciones

**Brechas Identificadas:**
- ❌ **Evaluaciones Multi-Tema**: Una evaluación que abarque varios temas
- ❌ **Evaluaciones Compuestas**: Combinación de múltiples ContentResult
- ❌ **Entregables Avanzados**: Sistema de recursos y documentos
- ❌ **Evaluación Automática**: IA para corrección de exámenes escritos

**Requerimientos Específicos:**
1. **Flexibilidad de Asociación**: Evaluaciones → múltiples temas/módulos
2. **Tres Tipos de Ponderación**:
   - Manual (exposiciones, presentaciones)
   - Automática (ContentResult individuales o combinados)
   - Entregables (documentos subidos por estudiantes)
3. **Sistema de Recursos Expandido**:
   - Recursos de apoyo (rúbricas, plantillas de evaluación)
   - Recursos entregables (trabajos de estudiantes)
   - Recursos de referencia (materiales de consulta)

### 5. Motor de Corrección Automática (NUEVO MÓDULO)

**Funcionalidades Requeridas:**
- 📋 **Procesamiento de Imágenes**: OCR para exámenes fotografiados
- 📋 **Procesamiento de Documentos**: Análisis directo de PDFs/Word
- 📋 **Sistema de Rúbricas**: Criterios de evaluación personalizables
- 📋 **IA de Evaluación**: Modelos de visión + NLP para corrección
- 📋 **Sandbox de Código**: Ejecución segura para ejercicios de programación

**Arquitectura Propuesta:**
```
Modelos de Datos:
- EvaluationRubric: Criterios y pesos de evaluación
- AutoGradingResult: Resultado de corrección automática
- CodeExecution: Resultados de ejecución en sandbox

APIs Requeridas:
- POST /api/auto-grading/image - Procesar imagen de examen
- POST /api/auto-grading/document - Procesar documento digital
- POST /api/auto-grading/code - Ejecutar y evaluar código
- GET /api/rubrics - Gestionar rúbricas de evaluación
```

## Plan de Implementación por Fases

### Fase 1 - Correcciones Backend Críticas (Semana 1)

**Objetivo**: Estabilizar la base del sistema y corregir inconsistencias detectadas.

**(B) Corrección de Lógica de Módulos Virtuales:**
- Revisar y corregir VirtualTopicService.generate_virtual_content()
- Asegurar que VirtualTopicContent.personalization_data se aplique correctamente
- Validar que el progreso se calcule adecuadamente con contenidos mixtos (IA + plantillas)
- Corregir cualquier inconsistencia en la relación VirtualTopic ↔ TopicContent

**(B) Optimización de ContentResult:**
- Verificar que ContentResult esté asociado correctamente a VirtualTopicContent
- Implementar lógica diferenciada por tipo de contenido:
  - Lectura: 100% al completar visualización
  - Quiz: Porcentaje basado en respuestas correctas
  - Juegos: Score del juego como porcentaje
  - Plantillas interactivas: Resultado enviado via postMessage

**(B) Cascada de Eliminación Completa:**
- Implementar eliminación en cascada para Topics → TopicContents → TemplateInstances
- Agregar eliminación de VirtualTopicContents al eliminar VirtualTopics
- Probar eliminación completa: StudyPlan → Modules → Topics → Contents → Instances

### Fase 2 - Fundamentos del Ecosistema de Plantillas (Semana 2)

**Objetivo**: Establecer la base sólida del sistema de plantillas y su integración.

**(B) APIs de Plantillas e Instancias:**
- Completar endpoints faltantes para gestión avanzada de plantillas
- Implementar sistema de extracción de marcadores mejorado
- Crear endpoints de preview/render con seguridad CSP
- Desarrollar lógica de fork automático para plantillas públicas

**(B) Integración con Contenidos Legacy:**
- Asegurar compatibilidad total entre contenidos tradicionales y plantillas
- Implementar render condicional en ContentService.get_topic_content()
- Adaptar VirtualTopicService para manejar contenidos híbridos
- Crear migración suave sin romper funcionalidad existente

**(F) Vista "Mis Plantillas" Mejorada:**
- Refinar UI con grid de tarjetas más informativo
- Implementar filtros avanzados (tipo, estado, scope)
- Mejorar editor con autocompletado y validación
- Agregar sistema de tags y categorización

### Fase 3 - Marketplace Público y Uso Avanzado (Semana 3)

**Objetivo**: Abrir el ecosistema de plantillas a la comunidad y refinar la experiencia.

**(F) Marketplace Público de Plantillas:**
- Crear página pública accesible desde landing
- Implementar filtros por categoría, popularidad y certificación
- Desarrollar sistema de rating y reviews
- Crear flujo de fork automático para plantillas públicas

**(B) Sistema de Certificación:**
- Implementar endpoint admin PUT /api/templates/{id}/certify
- Crear flujo de validación manual por administradores
- Desarrollar insignias y badges de calidad
- Establecer criterios de certificación documentados

**(F) Editor de Plantillas Avanzado:**
- Integrar editor de código con realce de sintaxis completo
- Implementar previsualización en tiempo real con postMessage
- Crear formulario de edición de schema JSON manual
- Desarrollar sistema de versionado y historial

**(B) Documentación para Creadores:**
- Crear manual de convenciones de marcadores
- Documentar APIs de integración con ContentResult
- Establecer guías de seguridad para plantillas
- Crear ejemplos de plantillas de referencia

### Fase 4 - Motor Adaptativo Estadístico (Semana 4)

**Objetivo**: Implementar la primera fase del motor de personalización híbrido.

**(B) Servicio de Personalización Estadística:**
- Desarrollar AdaptiveLearningService.calculate_content_preferences()
- Implementar análisis de ContentResult históricos
- Crear algoritmo de cálculo de prefer_types/avoid_types
- Integrar con cognitive_profile.contentPreferences

**(B) Adaptación de VirtualTopic:**
- Modificar generación de contenidos según contentPreferences
- Implementar sesgo VARK dinámico en VirtualTopicContent
- Crear sistema de vakHints para plantillas
- Desarrollar lógica de ajuste de dificultad

**(F) Feedback del Estudiante:**
- Implementar modal de encuesta post-módulo
- Crear selector de tipos de contenido preferidos
- Desarrollar captura de feedback cualitativo
- Integrar feedback manual con perfil cognitivo

**(F) Visualización de Progreso Adaptativo:**
- Crear página "Mi Perfil de Aprendizaje"
- Implementar gráficos de rendimiento por tipo de contenido
- Desarrollar indicadores de estilo de aprendizaje
- Mostrar evolución del perfil cognitivo

### Fase 5 - Sistema de Evaluaciones Avanzado (Semana 5)

**Objetivo**: Completar el sistema de evaluaciones con flexibilidad multi-tema y entregables.

**(B) Evaluaciones Multi-Tema:**
- Modificar modelo Evaluation para soportar múltiples topic_ids
- Crear lógica de evaluación compuesta (múltiples ContentResult)
- Implementar cálculo de nota final ponderada
- Desarrollar UI para asociar evaluaciones a múltiples temas

**(B) Sistema de Entregables:**
- Expandir modelo Resource con tipos: support, deliverable, reference
- Crear flujo de subida de entregables por estudiantes
- Implementar asociación Evaluation ↔ Resource (rúbricas y entregables)
- Desarrollar sistema de revisión manual por profesores

**(F) UI de Gestión de Evaluaciones:**
- Crear interfaz para configurar evaluaciones multi-tema
- Implementar selector de tipo de ponderación (manual/automática/entregable)
- Desarrollar vista de revisión de entregables
- Crear dashboard de evaluaciones pendientes

**(B) Preparación para IA de Corrección:**
- Diseñar modelos de datos para EvaluationRubric
- Crear estructura para AutoGradingResult
- Implementar endpoints base para procesamiento futuro
- Documentar especificaciones para módulo de IA

## Funcionalidades Futuras (Post-Fase 5)

### Motor de Corrección Automática con IA
- Procesamiento OCR de exámenes fotografiados
- Evaluación automática con modelos de visión
- Sandbox de ejecución para código
- Sistema de rúbricas inteligentes

### Personalización Híbrida con RL
- Integración de Reinforcement Learning
- Predicción de contenido óptimo en tiempo real
- Optimización multi-objetivo avanzada
- Microservicio de ML independiente

### Aplicación Móvil Completa
- React Native para iOS/Android
- Corrección de exámenes con cámara
- Modo offline para contenidos
- Sincronización automática

### Marketplace de Cursos con Pagos
- Publicación de StudyPlans como productos
- Integración con Stripe/PayPal
- Sistema de suscripciones
- Revenue sharing para creadores

## Conclusión

Este plan actualizado refleja la evolución arquitectónica de SapiensIA hacia un sistema educativo verdaderamente adaptativo y escalable. La integración del sistema de plantillas e instancias marca un hito importante, permitiendo:

1. **Reutilización de Contenido**: Plantillas reutilizables que reducen tiempo de creación
2. **Personalización Granular**: Tres niveles de adaptación según necesidades
3. **Escalabilidad Mejorada**: Arquitectura modular que soporta crecimiento
4. **Marketplace Educativo**: Ecosistema de intercambio de recursos
5. **Motor Híbrido**: Combinación de estadísticas y ML para personalización óptima

La implementación por fases asegura estabilidad mientras se introducen innovaciones, manteniendo compatibilidad con el sistema existente y preparando el terreno para funcionalidades avanzadas futuras.