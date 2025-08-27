Estado actual e implementación pendiente de SapiensIA

El sistema SapiensIA muestra avances importantes pero persisten brechas críticas. En el backend, ya existen las colas y modelos para generación progresiva de módulos virtuales (e.g. VirtualGenerationTask) y los endpoints /api/virtual/progressive-generation y /api/virtual/trigger-next-generation están implementados
GitHub
GitHub
. Estos endpoints encolan los primeros 2–3 módulos y luego disparan el siguiente módulo cuando el progreso supera el 80%
GitHub
GitHub
. Sin embargo, queda pendiente centralizar reglas estrictas antes de encolar (e.g. verificar evaluaciones previas, plantillas de pensamiento crítico y contenidos interactivos). También debe corregirse que en ContentResultService se busca el contenido virtual por el campo original_content_id
GitHub
, cuando el modelo VirtualTopicContent almacena el id original en content_id
GitHub
; esto rompe la asociación ContentResult→VirtualTopicContent y requiere ajuste o migración de datos. Por otra parte, la personalización adaptativa ya almacena resultados (ContentResult) y cuenta con endpoint de consulta (GET /api/virtual/content-results/student/{id})
GitHub
, pero el servicio estadístico por V-A-K-R aún no procesa esos datos. El catálogo de ContentType es amplio (e.g. véase ContentTypes en código
GitHub
) pero la intercalación dinámica de tipos en un plan de estudio aún no está activa.

En el frontend, el workspace unificado y las vistas clave de estudiante (/student/learning, /student/study-plan, /student/progress) están implementados y funcionando correctamente
GitHub
. Se corrigió el bug del sidebar del alumno para mostrar la opción de iniciar generación cuando no hay módulos virtuales. Queda pendiente consolidar las vistas privadas de profesor (/teacher/private-classes, /teacher/private-students, /earnings), así como completar los dashboards con métricas reales de progreso y calificaciones.

Otros puntos técnicos: el endpoint cognitivo activo es /api/users/profile/cognitive (GET/PUT)
GitHub
; no existe un endpoint separado /api/profiles/cognitive, por lo que conviene unificar rutas o documentar su uso. Ya existe /api/users/check para verificar email en registro
GitHub
. El trigger para el siguiente módulo usa correctamente un umbral de 80% (no 0.8)
GitHub
. Se detectó que el endpoint PUT /api/templates/:id falla con 400 por validación HTML; esto requiere revisar el esquema de datos de plantillas.

Revisión de tareas pendientes (backend/frontend)

A continuación se detallan las áreas funcionales con lo ya implementado y lo pendiente, destacando que toda ejecución de modelos de IA debe realizarse en el front-end (Vercel). Esto significa que las tareas que impliquen llamados a LLM (Gemini, OpenRouter, etc.) deben definirse como funciones del cliente (sin límite de tiempo), usando el backend solo para colas y orquestación.

Módulos Virtuales (generación progresiva): Ya existe la lógica de encolado inicial y trigger automático al 80%
GitHub
GitHub
. Faltan validaciones previas antes de encolar (e.g. verificar cumplidos criterios de habilitación). El front-end debe mostrar indicadores de “generando…” y la cola de espera con mensajes claros, refinando UX. Importante: la generación de contenidos IA (prompt, texto, etc.) se moverá al front-end, invocando al backend sólo para iniciar la tarea en la cola.

Personalización de contenidos (perfil cognitivo): El backend ya guarda los ContentResult y permite consultarlos
GitHub
. Falta implementar un servicio que analice esos resultados por etiquetas V-A-K-R y ajuste recomendaciones (esta era la Fase 1 estadística). Con el nuevo modelo RL, se debe llamar a la API de recomendación (ver Anexo RL). Se necesita un endpoint (e.g. /api/personalization/adaptive) que el front-end pueda invocar para obtener contenidos sugeridos usando el modelo de refuerzo. En el front-end, el contenido personalizado debe renderizarse sin agrupar estrictamente por tipo, respetando el orden mixto definido por la recomendación.

Motor adaptativo / Aprendizaje por refuerzo: Ahora contamos con un servicio externo de RL. Hay que integrar dos operaciones: get_recommendation y submit_feedback, usando los ejemplos CURL del documento rl_tutor_tool_tests.md. Por ejemplo, el backend (en Python) deberá llamar a http://149.50.139.104:8000/api/tools/msp/execute con el payload adecuado, obteniendo recomendaciones de contenido y enviando feedback. Se debe validar qué datos (perfil cognitivo, historial del estudiante, métricas de sesión) ya están en nuestra DB y mapearlos al formato esperado. En el frontend, se consultará este endpoint adaptativo para ajustar el flujo de contenidos tras cada sesión.

Nuevos tipos de contenido: El backend debe permitir definir y validar nuevos formatos (ejercicios matemáticos, simulaciones, GEMINI_LIVE, etc.) en el modelo ContentType. A futuro, debería listar esos tipos dinámicamente. En el frontend, habrá que crear la UI para seleccionar/generar estos contenidos y verificar su renderizado (p. ej. vistas de simulación interactivas).

Generación masiva/paralela (profesor): Falta implementar un pool de generación asíncrona (p.ej. 5 workers configurables por modelo) que genere en paralelo contenidos de un tema. Cada sub-tarea de generación paralela debe ejecutar un modelo de IA (en frontend) según el provider configurado y reintentos. El backend orquestará la cola (ParallelContentGenerationTask existe en el modelo
GitHub
). En el UI, se deben mostrar toasts independientes por contenido generado (persistentes hasta cerrarlos) y ocultar notificaciones genéricas al aparecer específicas.

Contenido teórico (“primeros principios”): Se planea generar explicaciones tipo método Feynman. Hay que ajustar los prompts de generación en el backend (o mejor, en el front-end) para que el modelo emita explicaciones simples y analogías. Documentar dichos prompts en el código. La generación de texto largo debe realizarse en el frontend.

Desbloqueo de temas y actualizaciones: Implementar la política de desbloqueo:

Añadir contenido: se inserta al final de los no vistos (backend: ordenar correctamente en VirtualTopic).

Editar contenido: afectar solo a alumnos que aún no lo vieron (verificar VirtualTopicContent).

Eliminar contenido: debe ocultarse para nuevos alumnos pero conservar históricos (quizás marcando status “archived”). Reforzar que las consultas de VirtualTopicContent apliquen estas reglas. En el frontend, refrescar las listas sin perder el progreso marcado y corregir los checkmarks según estos cambios.

Resultados de contenido (ContentResult): Validar que cada ContentResult se vincule al VirtualTopicContent correcto. Actualmente la búsqueda por original_content_id (en [20]) no funciona debido al desalineamiento de campos, por lo que debe corregirse la asociación. Además, al completar contenidos de “solo lectura” al 100%, hay que enviar un marcador automático de completitud (endpoint /content/{virtual_id}/complete-auto)
GitHub
. En el frontend, luego de interacciones no evaluativas, debe enviarse esta marca de completitud para actualizar el progreso.

Evaluaciones y entregables: Pendiente definir la relación M:N entre Evaluation y Topic, así como endpoints para subir/listar entregables y vincular recursos de apoyo. En el frontend, habrá que permitir descargar rúbricas, subir archivos de estudiante y mostrar el estado de la entrega.

Corrección automática con IA: Aún no está implementado. Se planea un servicio (CorrectionService) que realice OCR de entregas, compare con rúbrica y ejecute código en sandbox. Al subir una entrega (y si hay rúbrica), el backend debería invocar este servicio. En el frontend, se requerirán vistas para mostrar el progreso/resultados de la corrección y permitir ajustes manuales por parte del profesor.

Marketplace de cursos: Pendiente implementar la publicación y listado de planes de estudio públicos con precios, integración con pasarelas (e.g. Stripe) y landing page. El frontend debe mostrar el marketplace (/pages/landing y listado), gestionar inscripción gratuita o de pago.

Gestión de claves de API: Falta crear campos en el perfil del usuario para que el usuario introduzca sus claves de IA (Gemini, OpenRouter, Groq). En el backend, guardar esas claves seguras y darles prioridad sobre las globales al realizar llamadas a los servicios IA.

Aplicación móvil y UI: Aún faltan la app móvil (e.g. React Native) iniciando con corrección IA y cursado de módulos, además de mejoras de UI como modo oscuro completo, responsividad y limpieza de código.

Autenticación y dashboards: La autenticación con email/contraseña (con recuperación) ya existe en backend
GitHub
GitHub
. Los dashboards por rol están parcialmente implementados; falta conectar indicadores reales (calificaciones, progreso) y eliminar métricas irrelevantes (e.g. asistencia).

Plantillas (templates) y sistemas de simulación: El backend tiene modelos Template/TemplateInstance planificados pero incompletos. Los campos nuevos (render_engine, templateId, instanceId, templateVersion, learningMix) ya figuran en TopicContent
GitHub
. Queda pendiente corregir el bug en PUT /api/templates/:id (400 error) ajustando el esquema de validación. En el frontend, reutilizar la sección “Juegos y Simulaciones” como “Mis Plantillas”: debe permitir listar, buscar, editar HTML (Extraer marcadores), clonar una plantilla en un tema, y previsualizar en un iframe sandbox. En la fase final (Hito C), se creará una instancia (TemplateInstance) al usar una plantilla y se actualizará el TopicContent.render_engine='html_template'.

Idiomas indígenas: Verificar datos existentes y soporte multilenguaje en la UI.

Herramientas de concentración: En frontend, pulir temporizador Pomodoro con sonidos (persistencia en localStorage, controles estilizados). En backend, opcionalmente exponer endpoints si se desea guardar sesiones de estudio.

Eliminación en cascada: Asegurarse de que al borrar objetos (topics, contenidos, módulos) se eliminen también datos asociados sin dejar huérfanos (cascada en DB). En el frontend, sincronizar las eliminaciones con confirmaciones y refresco adecuado de listas.

En resumen, las vistas de estudiante y el flujo básico de planes ya están operativos, pero quedan pendientes principalmente las plantillas (incluso corregir el PUT 400), la intercalación de contenidos, la generación paralela y toasts detallados, la gestión de evaluaciones/entregables y corrección IA, el motor RL, el marketplace/pagos, la gestión de claves, dashboards finales y limpieza, y la eliminación coherente. Muchos de estos puntos ya estaban en backlog; ahora se insiste en mover al front-end las tareas de IA (p.ej. generación de texto/simulaciones con Gemini) para evitar el límite de 1 minuto en funciones serverless, usando el backend solo como colas y router de datos.

Plan de implementación por fases

Fase 1 (3–4 semanas, crítica): Backend – corregir PUT /api/templates/:id (bug de validación HTML), reparar la asociación ContentResult→VirtualTopicContent (usar content_id en lugar de original_content_id)
GitHub
GitHub
. Unificar los endpoints cognitivos y documentar /api/users/check (ya existente)
GitHub
GitHub
. Asegurar trigger de módulo al 80%
GitHub
. Frontend/Backend – diseño de toasts granulares y persistentes para generación paralela. Front – completar vistas básicas de profesor (/teacher/private-classes, /teacher/private-students). F/B – dashboards de progreso/calificaciones reales, limpieza de métricas.

Fase 2 (3–4 semanas, alta): Backend – implementar relación Evaluación<>Temas y endpoints para subir/listar entregables. Incluir reglas de habilitación previas a la virtualización. Front – UI de entregas (rúbrica, subida archivos, estado). Backend – extender generación de contenidos intercalados; Front – presentar contenidos según orden adaptativo y mostrar estados de cola.

Fase 3 (3–4 semanas, media): B/F – Corrección IA: servicio de OCR/rúbrica/sandbox y vistas de resultados; posibilidad de ajuste manual. Backend – refactor de generación paralela (pool de 5 hilos, reintentos); Front – toasts persistentes por contenido, opción de cancelar (X). B/F – Plantillas (Hitos A/B/C): editor, extractor de marcadores, clonación, preview sandbox, y flujo “Usar como contenido” completo.

Fase 4 (3–4 semanas, baja): B/F – marketplace público (landing, filtros, inscripción/pago con Stripe). Front – mejorar Pomodoro/sonidos y soporte multi-idioma. B/F – eliminación en cascada con tests (o script validación post-migración). F/QA – testing multi-workspace e inicio de la app móvil RN (cursado y corrección IA).

Nota: Si la asociación ContentResult→VirtualTopicContent ya se corrigió, marcar como “done” y priorizar el bloque de Plantillas, la intercalación y la generación en paralelo con toasts. En todo el plan, recuerde delegar cualquier ejecución pesada de modelos de IA al front-end para esquivar las limitaciones de tiempo de Vercel.

Fuentes: Se validó el código en los repositorios internos (rutas y servicios de backend
GitHub
GitHub
) y la documentación del proyecto (rl_tutor_tool_tests.md en GitHub) para los nuevos requisitos. Los fragmentos de código citados ilustran la implementación actual de generación progresiva y manejo de resultados
GitHub
GitHub
.