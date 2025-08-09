Estado Actual vs. Nuevos Requerimientos
Antes de planificar las fases de implementación, es vital entender qué ya está implementado en SapiensIA y qué falta por hacer según el backlog reciente. A continuación, se detalla módulo por módulo:
1. Módulos Virtuales Personalizados y Generación Progresiva
Estado Actual: El backend ya implementa la creación progresiva de módulos virtuales. Existe un servicio FastVirtualModuleGenerator que genera un módulo virtual y sus primeros temas rápidamente
GitHub
GitHub
. También se incluyó un servicio optimizado de cola (OptimizedQueueService) que mantiene siempre 2 temas futuros virtualizados por módulo
GitHub
GitHub
. Este servicio crea inicialmente hasta 3 temas virtuales (1 activo y 2 bloqueados) cuando el alumno abre el módulo por primera vez
GitHub
GitHub
, y luego, a medida que el estudiante avanza, genera automáticamente nuevos temas en segundo plano para mantener el colchón. La lógica verifica el progreso y desbloquea temas: cuando un tema virtual se completa (progreso >= 100%), se marca como completado y desbloquea el siguiente tema bloqueado
GitHub
GitHub
. Además, el método trigger_on_progress lanza la generación anticipada del siguiente tema cuando el progreso del tema actual supera el 80%
GitHub
GitHub
 (la comparación ya está corregida a progress_percentage < 80 en vez de 0.8, acorde a porcentajes del 0-100%
GitHub
). También existe un modelo VirtualGenerationTask para encolar tareas de generación (tipos “generate”, “update”, “enhance”), aunque por ahora la generación ocurre principalmente de forma síncrona con la lógica anterior
GitHub
GitHub
. Gaps Identificados:
Generación de módulos siguientes: Actualmente, trigger_on_progress genera nuevos temas dentro del mismo módulo cuando se supera 80%, pero no inicia explícitamente la virtualización del próximo módulo del plan. Debemos añadir esa lógica: cuando el progreso de un módulo actual supere ~80% de sus temas, encolar la generación del primer tema del siguiente módulo (siguiendo la misma regla de 2 módulos por delante).
Reglas de habilitación de virtualización: El sistema marca un tema como “publicado” para permitir su virtualización solo si está completo. Existe un servicio TopicReadinessService que verifica requisitos multisensoriales para publicar un tema
GitHub
GitHub
. En código, se exige que el tema tenga contenido teórico base, un quiz, slides, un diagrama, un video y algo kinestésico (juego o simulación)
GitHub
GitHub
. Esto cubre implícitamente “un contenido de evaluación” (quiz) y “contenido interactivo” (juego/simulación), pero falta validar la “plantilla de pensamiento crítico” mencionada en el backlog
GitHub
. Habrá que incorporar ese chequeo (por ejemplo, exigir un contenido tipo guided_questions o similar).
Seguimiento de progreso del módulo: El modelo VirtualModule tiene campo progress
GitHub
, pero no encontramos una rutina que lo actualice dinámicamente. Probablemente deba calcularse según los temas completados del módulo.
Cola de tareas background: Aunque está definido VirtualGenerationTask, actualmente la generación es síncrona. A futuro, podríamos usar este modelo para delegar a un worker asíncrono (ej. Celery) la creación en background, pero no es crítico por ahora.
2. Personalización de Contenidos según Perfil Cognitivo
Estado Actual: La lógica de personalización estática está en gran parte implementada. Cuando se genera un tema virtual, el sistema selecciona los contenidos adecuados según el perfil VARK del estudiante:
Selección de tipos de contenido: El método _select_personalized_contents filtra y elige ~6 contenidos por tema adaptados al CognitiveProfile
GitHub
GitHub
. Garantiza un balance: siempre incluye al menos un contenido “completo” (texto, presentación, video, etc.)
GitHub
GitHub
, añade contenidos específicos (juegos, diagramas, etc.) y uno evaluativo (quiz) si existe. Incluso aplica la directriz de no cubrir solo partes del tema: si no hubiera contenido global, toma 2 específicos para no dejar lagunas
GitHub
. La personalización intercalada también se favorece, ya que la selección mezcla tipos diversos (el orden de presentación se puede ajustar al insertarlos en el VirtualTopic).
Adaptación a nivel de contenido: Al crear cada VirtualTopicContent para el alumno, se calcula personalization_data con ajustes según el perfil. Por ejemplo, en _generate_personalization se ven adaptaciones: si el alumno es fuertemente visual o auditivo, se agregan opciones para reforzar visuales o añadir audio; si tiene dislexia o TDAH, se activan fuentes especiales, más tiempo, etc.
GitHub
GitHub
. Estas adaptaciones se guardan en cada virtual_topic_contents.personalization_data
GitHub
.
Uso del perfil cognitivo: El perfil cognitivo del usuario se almacena en users.cognitive_profile. Este incluye estilos de aprendizaje (visual, auditory, reading_writing, kinesthetic) y otros datos (diagnóstico, dificultades, etc.)
GitHub
GitHub
. La selección de contenidos normaliza estos valores a 0-1 y deduce preferencias: e.g., prioriza evitar tipos no aptos (lista avoid_types) o preferir tipos favoritos (prefer_types) si el perfil adaptativo lo indica
GitHub
GitHub
. También está preparado para usar un análisis de contenidos previo (content_analysis con scores por tipo) para decidir cuántos contenidos visuales vs. kinestésicos incluir
GitHub
GitHub
.
Gaps Identificados:
Intercalación explícita: Aunque se escogen tipos variados, actualmente la presentación puede listar primero todos los completos luego específicos. Deberemos ajustar la ordenación final de selected_contents para alternar (por ejemplo: slide -> juego -> texto -> diagrama, etc.), cumpliendo la “experiencia dinámica” solicitada.
Plantillas de pensamiento crítico: Incorporar en la selección un contenido de tipo pensamiento crítico si existe (actualmente no se busca explícitamente). Podría ser un tipo guided_questions o critical_thinking en ContentTypes.
Validación del CognitiveProfile: Confirmaremos si el perfil cognitivo se está generando correctamente (posiblemente a través de un test VARK en la interfaz estudiante) y si la API /api/profiles/cognitive devuelve/actualiza ese perfil adecuadamente. Cualquier desalineación entre frontend y backend en este endpoint debe corregirse (según nota del backlog).
Ajustes menores: Afinar los parámetros de adaptación (ej.: umbrales de 0.7 para activar adaptaciones visuales/auditivas
GitHub
 se pueden calibrar).
3. Motor Adaptativo de Personalización (Aprendizaje por Refuerzo)
Estado Actual: Todavía no se ha implementado la fase 1 estadística del motor RL. Sin embargo, el diseño de datos anticipa su integración:
El objeto CognitiveProfile.profile (un JSON completo) puede almacenar un subobjeto contentPreferences con campos como prefer_types, avoid_types y un análisis detallado por tipo (content_analysis)
GitHub
GitHub
. De hecho, la lógica de selección ya utiliza contentPreferences si están presentes en el perfil
GitHub
. Esto significa que el sistema está listo para aprovechar las recomendaciones aprendidas, pero actualmente no hay un servicio que genere esas preferencias a partir de resultados.
Los resultados de contenido de cada alumno se registran en la colección content_results. Cada ContentResult guarda el content_id (ahora mismo, apunta al contenido base original) y student_id, con la puntuación obtenida
GitHub
. Asimismo, se guarda opcionalmente virtual_content_id en el documento (en record_result se añade si está presente) para vincularlo al contenido personalizado
GitHub
.
Gaps Identificados:
Asociación ContentResult -> VirtualContent: Crítico: Actualmente ContentResult.content_id se está almacenando con el ID de TopicContent original
GitHub
, lo cual dificulta diferenciar resultados de distintos alumnos sobre el mismo contenido. Queremos cambiar esto para que apunte al VirtualTopicContent específico (id único por alumno), conforme a la visión de “resultado único por alumno-contenido virtual”
GitHub
. Ya vemos en el código que al guardar un result se pasa virtual_content_id en paralelo y se hace seguimiento en track_interaction
GitHub
GitHub
, pero debemos modificar el modelo para incluir directamente un campo virtual_content_id y usarlo preferentemente (y quizás renombrar content_id a original_content_id para no romper datos antiguos). Esto permitirá que el motor adaptativo identifique con precisión qué intento corresponde a qué instancia personalizada.
Servicio estadístico fase 1: Debemos implementar un servicio backend (por ejemplo, AdaptiveLearningService) que al consultar todos los ContentResults de un alumno calcule sus tendencias. Por ejemplo: “el estudiante obtiene mejores notas en contenidos visuales y auditivos (diagramas, videos) que en lecto-escritura”. Con esos cálculos, llenaremos cognitive_profile.profile.contentPreferences con:
prefer_types: lista de códigos de contenido con mejor rendimiento.
avoid_types: tipos con rendimiento consistentemente bajo.
content_analysis: un mapa tipo -> {success_rate:..., preference_score:...} cuantificando su eficacia para el alumno.
Integración fase 1: El resultado de este análisis se volcará en la BD y afectará futuras selecciones de _select_personalized_contents (que ya considera estas preferencias). Importante: añadiremos en el código clarificaciones (comentarios) indicando que esta es una solución temporal basada en heurística estadística
GitHub
GitHub
, lista para ser reemplazada por un modelo RL real en fase 2.
Fase 2 (a futuro): Queda fuera del alcance inmediato, pero sentaremos las bases para luego integrar un modelo de RL que, por ejemplo, actualice el perfil tras cada módulo y pueda incluir feedback explícito del alumno (“¿Te gustó aprender con este recurso?”). Mencionaremos estas extensiones como trabajo futuro, sin implementarlas aún.
4. Ampliación de Tipos de Contenido Educativo
Estado Actual: El sistema ya reconoce una gran variedad de tipos de contenido en ContentTypes (teóricos, visuales, interactivos, evaluativos, etc.)
GitHub
GitHub
. El backlog menciona añadir más, especialmente dinámicas de juego, ejercicios de completación, matemáticos, glosarios, e incluso Gemini Live (chat con IA). Muchos de estos ya aparecen en ContentTypes (por ejemplo COMPLETION_EXERCISE, MATH_EXERCISE, flashcards, gemini_live están listados
GitHub
). Esto sugiere que el catálogo está actualizado, aunque quizás no todos se usan aún en la interfaz. Gaps Identificados:
Integración de nuevos formatos: Asegurar que al añadir un nuevo tipo (p. ej. un mini-juego o un lab virtual), la generación de contenido puede manejarlos. Por ahora, la generación unificada crea los contenidos vía IA solo para algunos tipos (texto, quiz, diagramas, slides). En la Fase de plantillas (ver más adelante) es donde incluiremos soporte para estos formatos de forma más flexible, permitiendo añadir plantillas HTML/JS para juegos, etc.
Front-end rendering: Verificar que los visores de contenido (en frontend) soporten estos nuevos tipos. Actualmente hay visores para slides, quiz, video, etc. Tipos como glosario, ejercicios interactivos o GeminiLive pueden requerir componentes específicos. Probablemente los implementaremos junto con la introducción del sistema de plantillas (pues muchas de estas dinámicas vendrán como plantillas reutilizables).
5. Generación Automática de Contenido con Múltiples Modelos (Paralelización)
Estado Actual: Se ha avanzado bastante en este aspecto en el backend. Existe ParallelContentGenerationTask y métodos en VirtualModuleService para manejar peticiones simultáneas a varios modelos de IA
GitHub
GitHub
. En la práctica:
El sistema puede crear hasta 5 hilos virtuales (en código, tareas paralelas) para generar distintos tipos de contenido a la vez. En ParallelContentGenerationService.create_parallel_task se selecciona un proveedor primario (OpenAI, Anthropic, Gemini, etc.) y fallback para cada contenido
GitHub
GitHub
. Luego process_parallel_task intenta la generación; si falla con un modelo, cambia al siguiente (manejando un “circuit breaker”)
GitHub
GitHub
. Al primer éxito, marca la tarea completada y crea automáticamente el VirtualTopicContent resultante
GitHub
GitHub
. Si todos fallan, la tarea se marca failed y se puede hacer fallback final al método tradicional
GitHub
GitHub
.
Asignación de modelos a hilos: Aunque configurable via código (listas de ai_providers y primary_provider con sus reliabilities
GitHub
GitHub
), actualmente está hardcodeado. Podemos adaptar fácilmente este mapeo leyendo de un archivo de config (p. ej. asignar Gemini a 2 hilos, OpenRouter a 2, etc., como el cliente pidió).
Ejecución simultánea real: Cabe notar que ahora mismo, tras crear las tareas paralelas para cada tipo de contenido, el código las procesa secuencialmente en un loop
GitHub
. En un entorno con threads o Celery, esto sería concurrente. Por simplicidad inicial, podría quedar secuencial pero seguiremos liberando las tareas una por una.
Gaps Identificados:
Integración con UI del profesor: Actualmente, al generar contenido teórico manualmente, solo se crean 2-3 tipos (texto, resumen, quiz...). Debemos modificar la acción de “Generar contenido” para que dispare la generación de todos los tipos de contenido faltantes de ese tema en paralelo. Esto implicará en el frontend:
Mostrar toasts de progreso por cada contenido: e.g. “Generando Diagrama...”, “Generando Quiz...”.
Persistir esas notificaciones incluso si se recarga la página (podemos guardar estado en context o redux store mientras las tareas siguen en backend).
Añadir un botón “X” en cada toast para permitir al usuario ocultar notificaciones individuales si lo desea.
Feedback en tiempo real: Asegurarnos de que el frontend consulte periódicamente el estado de las tareas (quizá exponiendo un endpoint GET /api/content_generation_tasks/{id} que devuelva el progreso agregado
GitHub
GitHub
, similar a get_task_status que ya calcula porcentaje
GitHub
). Así podemos actualizar la barra de progreso general (“Generando contenidos... 60%”).
Reintentos automáticos: Confirmar que si un sub-task falla, el sistema ya está reintentando con otro modelo (según código, sí lo hace
GitHub
GitHub
). Podríamos exponer en el resultado de tarea qué modelo terminó generando cada contenido para monitoreo (no crítico para funcionalidad, pero útil).
Sin bloqueos en UI: La generación es asíncrona, por lo que el usuario puede navegar mientras tanto. Debemos probar que si sale y vuelve, puede recuperar los contenidos generados sin problemas (los toasts persistentes ayudarán a informarle).
6. Contenido Teórico con Principios Fundamentales (Método Feynman)
Estado Actual: Esta es más una pauta de estilo de prompt para la IA que una funcionalidad de código. Actualmente, al solicitar generación de un contenido teórico (texto, feynman, story, etc.), el backend simplemente envía un prompt base (instrucción) al modelo. No vimos en el código una referencia explícita a “principios fundamentales” o “método Feynman” en los prompts. Sin embargo, existe un tipo de contenido FEYNMAN en ContentTypes
GitHub
, lo que sugiere que se puede generar una explicación con ese método. Gaps Identificados:
Ajuste de prompts: Incorporar en el generador de contenido teórico indicaciones a la IA para que explique los conceptos desde sus principios básicos, con analogías simples. Por ejemplo, modificar el prompt de generación de texto teórico para: “Explica este tema como si se lo enseñaras a alguien sin conocimientos previos, usando el método de Feynman (primeros principios).”. Esto no requiere cambios estructurales de código, sino actualizar plantillas de prompt en el servicio de IA correspondiente (posiblemente en ContentGenerationService o donde se integren las llamadas a OpenAI/Gemini).
Verificación de resultado: Tras implementar esto, haremos tests de generación de algún contenido teórico para ver si las respuestas son más pedagógicas. Esto mejora la calidad sin afectar otras partes.
7. Desbloqueo, Progreso y Actualizaciones en Módulos en Curso
Estado Actual: El avance secuencial está implementado: los modelos VirtualTopic tienen campo locked y status (“locked” vs “active”) para controlar qué temas están accesibles
GitHub
GitHub
. Conforme el alumno completa un tema virtual, el sistema (OptimizedQueueService) llama _unlock_next_topic para desbloquear automáticamente el siguiente tema
GitHub
GitHub
. Esto coincide con la navegación condicional pedida (no se puede saltar temas). El progreso de cada tema se rastrea en VirtualTopic.progress (0.0 a 1.0) y completion_status
GitHub
. Al marcar un tema completado, se setea progress=100 y status “completed”
GitHub
. Respecto a cambios del profesor en un módulo ya iniciado por alumnos: hay un mecanismo de detector de cambios (ContentChangeDetector) que calcula un hash del módulo (basado en contenidos y evaluaciones)
GitHub
GitHub
 y almacena versiones en content_versions. Cuando detecta discrepancias, registra la nueva versión y marca last_content_update
GitHub
GitHub
. Además, FastVirtualModuleGenerator.synchronize_module_content existe para sincronizar un módulo virtual existente con su módulo original
GitHub
GitHub
. Aunque la implementación detallada de este sync no la vimos completa, está preparada para:
Añadir contenidos nuevos: (El backlog sugiere agregarlos al final de la lista para esos alumnos).
Actualizar contenidos modificados: (Podría regenerarlos para alumnos que aún no los han visto; es complejo, quizá por ahora solo se reflejen a nuevos alumnos).
Eliminar contenidos: (Habría que ocultarlos a quienes no los han llegado a ver y mantener el registro para los ya completados).
Gaps Identificados:
Política clara de sincronización: Aplicaremos la propuesta del backlog: si el profesor añade un contenido a un tema ya en curso, crearemos la instancia VirtualTopicContent para todos los VirtualTopics de ese tema que estén “activos” y no completados, marcándolo como no iniciado (aparecerá pendiente al final). Si edita un contenido (p.ej. corrige un texto), podríamos decidir no cambiar lo que el alumno ya vio (para no confundir), a menos que sea crítico. Si elimina un contenido, lo eliminamos de los VirtualTopics pendientes; para los alumnos que lo completaron, simplemente no aparecerá en adelante (pero su ContentResult queda almacenado). Implementaremos esta lógica en synchronize_module_content y/o en endpoints de update/delete de contenido.
Interfaz al alumno: Si se agrega contenido nuevo a mitad de su avance, habrá que notificarlo en la UI (“Se ha añadido un nuevo recurso al tema X”). Podríamos reutilizar el mecanismo de notificaciones en la app o indicar visualmente el nuevo item como “Nuevo”.
Bug del sidebar del alumno: El backlog menciona un bug donde el estudiante no ve módulos/temas en el Sidebar si aún no se han generado. Al ser ahora la generación on-demand, corregiremos la UI para que: si no hay VirtualModule de ese plan aún, muestre el módulo con estado “Generar” o un botón “Iniciar Módulo Virtual”. Esto evitará un sidebar vacío. Es un cambio pequeño en frontend (comprobar lista de módulos virtuales y ofrecer acción si está vacía).
Registro de asistencia: Se nota que en los dashboard actuales hay métricas no aplicables (como asistencia). Eliminaremos esas estadísticas irrelevantes o las reemplazaremos con progreso de módulos, para que los dashboards muestren datos reales (por ejemplo: % de contenidos completados, calificación promedio, etc., según el rol).
8. Gestión de Resultados de Contenido (ContentResult)
Estado Actual: Como mencionado, cada interacción (ejercicio realizado, recurso visto) genera un ContentResult con score (o 100% para lecturas completadas)
GitHub
. Estos resultados se guardan en content_results. El ContentResult actualmente se asocia por content_id al contenido original, lo cual no distingue estudiantes (pero sí incluye student_id, diferenciando por combinación). Sin embargo, el VirtualTopicContent personalizado es la entidad ideal a enlazar. Vemos que la inserción de VirtualTopicContent guarda content_id apuntando al contenido base y copia el contenido en campo content junto con datos de tracking
GitHub
GitHub
. También en ContentResultService, si se proporciona virtual_content_id, se llama a VirtualContentService.track_interaction
GitHub
 que actualiza el registro de interacción (incrementa access_count, tiempo, etc. en la instancia virtual)
GitHub
GitHub
. Gaps Identificados:
Modelo de datos: Ajustaremos ContentResult para añadir campo virtual_content_id y usaremos ese en lugar de content_id siempre que exista. Así cada resultado referencia directamente la instancia única del alumno. Mantendremos content_id para retrocompatibilidad o para ciertos casos (como evaluaciones formales que no están ligadas a un contenido interactivo específico).
Uso de resultados en evaluaciones: El backlog indica que una Evaluation formal puede tomar la nota de uno o varios ContentResults (por ejemplo, un quiz hecho como contenido del tema). Actualmente, Evaluation.use_quiz_score y linked_quiz_id existen
GitHub
GitHub
, pero dado que “quiz” ahora es un TopicContent unificado, podríamos deprecar linked_quiz_id. En lugar, implementaremos que si use_quiz_score=true, al marcar el tema como completado, se busque el ContentResult del quiz de ese tema para asignarlo a la Evaluation. Este detalle se pulirá al trabajar en Evaluaciones.
9. Recursos, Entregables y Evaluaciones del Plan de Estudio
Estado Actual:
Evaluaciones Many-to-Many: Actualmente una Evaluation pertenece a un solo módulo (module_id)
GitHub
. No hay asociación directa a varios Topics. Para soportar evaluaciones transversales, habrá que extender el modelo para permitir ligar múltiples temas. Quizá añadiremos un campo topic_ids: [ObjectId] opcional (si presente, indica qué temas cubre), o migrar a nivel de plan. Por ahora, no está implementado.
Entregables: El sistema maneja entregas de archivos: al crear un entregable, se sube un Resource (archivo) marcado como tipo "submission"
GitHub
. El EvaluationSubmission (en modelos, no lo vimos pero se intuye) guarda referencia al recurso y estado. El flujo actual soporta: el alumno sube el archivo, se crea la entrega y si la Evaluación tiene auto_grading=true, se lanza inmediatamente la calificación automática
GitHub
. Vemos que AutomaticGradingService.grade_submission se invoca para generar nota y feedback
GitHub
. La implementación de auto-grading actualmente es básica (puntaje base por entregar, bonus por tipo de archivo, tamaño y prontitud)
GitHub
GitHub
, y devuelve siempre un feedback genérico
GitHub
GitHub
. Nota: Esto cubre en parte la idea de corregir exámenes a partir de fotos/PDF, aunque sin visión por IA. Aún no hay OCR ni ejecución de código.
Rúbricas y recursos de apoyo: El modelo EvaluationResource permite asociar archivos a evaluaciones con un rol (p. ej. "template" para la plantilla que el alumno debe descargar, o "rubric" para una guía de calificación). De hecho, en upload_submission se llama evaluation_resource_service.link_resource_to_evaluation(... role='submission' ...)
GitHub
, lo que sugiere roles distintos (quizás 'template' cuando el profe sube un recurso inicial). Esta parte parece operativa en backend; habría que revisar la UI profesor para subir dichos archivos de apoyo.
Calificación manual: El backend ofrece endpoints para calificar manualmente entregas (PUT /evaluation/submission/<id> para poner nota y feedback)
GitHub
, y también para asignar nota directa a una Evaluation por alumno (POST /evaluations/<id>/grade) que internamente crea un ContentResult de tipo evaluación formal
GitHub
GitHub
. Esto cubre la posibilidad de evaluaciones calificadas directamente (por ejemplo, nota de un proyecto o examen escrito).
Gaps Identificados:
Evaluación multi-tema: Decidiremos la mejor forma de modelarlo. Quizá lo más simple: añadir topic_ids (array) en Evaluation y permitir que una evaluación pertenezca a ningún módulo (o a uno principal) pero referencie tópicos de varios. También ajustaremos la UI para permitir elegir múltiples temas al crear una evaluación.
Pesos y cálculo de nota: Permitir ponderar una evaluación a mano (campo weight ya existe
GitHub
). En el futuro podríamos calcular nota de módulo o plan promediando ContentResults de evaluaciones con sus pesos.
Mejoras auto-grading: No se requieren inmediatamente, pero a futuro:
Integrar un servicio de OCR + IA para calificar exámenes a partir de fotos/PDF (por ahora devolvemos nota base; lo dejaremos como comentario de mejora futura).
Para ejercicios de código, podríamos en fase 2 implementar un sandbox (por ejemplo, usar Docker en backend o un servicio externo) que ejecute el código del alumno y verifique la salida. Esto es complejo; por ahora nos limitamos a mencionarlo como plan.
En esta fase, dejaremos claro en docs/código que la auto-corrección actual es simplificada y el profesor debe revisar manualmente (como ya sugiere el feedback devuelto: “Revisión manual recomendada”
GitHub
).
10. Sistema Unificado de Workspaces (Multi-institución)
Estado Actual: Ya implementado por completo. La aplicación usa un modelo de workspaces: los usuarios pueden pertenecer a múltiples espacios (institutos o cuentas individuales) con distintos roles. Vemos que en los endpoints de login/register se asignan claims JWT con workspace_id e institute_id del primer workspace del usuario
GitHub
GitHub
. También los listados de planes de estudio y otros datos filtran por workspace actual mediante decoradores (@workspace_type_required, @apply_workspace_filter)
GitHub
GitHub
. El frontend permite cambiar de instituto (endpoint /users/switch-institute/... existe)
GitHub
GitHub
. En esencia, una sola cuenta puede actuar como profesor particular (INDIVIDUAL_TEACHER), estudiante autodidacta (INDIVIDUAL_STUDENT) o miembro de un instituto, según el workspace seleccionado. Esto cumple con lo requerido de tener un workspace genérico "Academia Sapiens" para uso individual. No hay gaps mayores aquí. Solo se debe tener en cuenta en todas las nuevas funciones (marketplace, plantillas, etc.) filtrar/almacenar según el workspace. Por ejemplo, una plantilla puede ser “privada” (solo la ve su autor, en su workspace personal) u “organizacional” (visible a colegas del mismo instituto). Ya se previeron campos ownerId y scope en el modelo de plantilla (ver más abajo).
11. Marketplace de Cursos, Landing Page y Suscripciones
Estado Actual: Esto no está aún implementado. La página principal de la app actualmente redirige al login del sistema; no existe una landing pública. Tampoco hay funcionalidad de marketplace de cursos ni de pagos. Es un requerimiento a mediano plazo. Plan a Futuro (no en las fases inmediatas):
Implementar una Landing Page en la ruta raíz (/) con información comercial de SapiensIA, enlaces a registro/login, testimonios, etc. Esto se hará en React (o Next.js) separado del dashboard interno.
Marketplace de cursos: Consistirá en permitir a profesores publicar sus planes de estudio (que podrán ser consumidos por usuarios externos). Probablemente modelaremos un objeto PublicCourse o simplemente añadiremos flags a StudyPlan (ej. is_public, price, etc.). Dado que esto involucra pagos, lo dejaremos para después de estabilizar las plantillas. Requiere integrar un sistema de pagos (Stripe u otro) y manejo de suscripciones, lo cual escapa del sprint actual.
Mientras tanto, en la UI dejaremos quizás placeholders o pestañas ocultas para “Marketplace” (mostrando las plantillas por ahora, y con idea de agregar cursos más adelante).
12. Gestión de API Keys de Usuario
Estado Actual: No hay interfaz ni endpoints específicos para que un usuario ingrese sus propias API keys de servicios de IA. Actualmente, las llamadas a modelos usan claves configuradas en el servidor (por ejemplo, la de OpenAI, Gemini, etc., presumiblemente almacenadas en variables de entorno). Requerimiento: Permitir que desde el perfil de usuario se puedan introducir claves personales para los proveedores soportados. Implementación Planificada:
Backend: Crear campos opcionales en el modelo de usuario (por ejemplo api_keys: { openai?: string, gemini?: string, openrouter?: string, ... }). Añadir endpoints seguros para actualizar estas keys (cifradas en base de datos idealmente).
Frontend: En la sección perfil, agregar un formulario donde el usuario pueda pegar sus keys. Posiblemente con validación básica (ej. longitud o un test call para verificar la validez).
Uso: Modificar los servicios de IA en backend para, antes de usar la key global, chequear si user.api_keys[provider] existe. Si sí, usar la del usuario
GitHub
; sino, caer a la del sistema. Esto brinda flexibilidad y potencial ahorro de costos para nosotros.
Seguridad: Aseguraremos cifrado/ocultamiento de las claves. Quizá almacenar un hash o en un storage seguro. Al menos, jamás exponer la clave en respuestas, solo un indicador (“conectado”/“no conectado”).
13. Aplicación Móvil y Mejoras Generales de UI
Estado Actual:
App Móvil: No existe aún, aunque se planea usar React Native. Inicialmente enfocaría en que los profesores puedan sacar fotos de exámenes y corregir con IA desde el móvil, y que los alumnos puedan consumir los módulos virtuales en móvil de forma nativa. Por ahora, lo pospondremos hasta tener las funcionalidades web completas.
Responsividad: La web actual utiliza componentes responsive (Tailwind CSS está configurado y hay toggles de concentración). Sin embargo, debemos pulir detalles de estilo para móviles (posiblemente probar vistas de estudiante/profesor en pantallas pequeñas y ajustar).
Tema claro/oscuro: Parece estar en proceso (hay un util mui-theme.ts y config de Tailwind para dark mode). Implementaremos un switch de tema en la UI (quizás en el header perfil). Es principalmente trabajo de frontend (cargar clase dark en <html> y colores).
Eliminación de archivos obsoletos: Revisaremos el repo frontend para borrar componentes o estilos no usados tras los refactors (p.ej. elementos legacy de versiones previas). Esto mejora limpieza pero no afecta funcionalidad.
Optimización de rendimiento: Consideraremos técnicas como lazy loading de módulos (ya se ve intención en cargar editor de código de plantillas solo cuando se abre, etc.), memorización de resultados de APIs, y usar correctamente los hooks de datos. Con la paralelización y nuevas features, vigilar que no introduzcamos cuellos de botella.
Visores y sandboxes de contenido: Asegurarnos que los iframes o componentes interactivos (p. ej. simulaciones) carguen sin problema de estilos. Puede implicar añadir resets CSS dentro de iframes o usar Shadow DOM si fuera necesario para aislar estilos de plantillas (lo tendremos presente al implementar plantillas HTML).
Plan de Implementación por Fases
A continuación se propone un plan de trabajo por fases semanales, abordando primero las correcciones fundamentales de backend, luego la nueva arquitectura de Plantillas de Contenido, seguido de las mejoras adaptativas y de interfaz. Cada fase lista las tareas de Backend (B) y Frontend (F) correspondientes:
Fase 1 – Correcciones Base y Preparativos (Semana 1)
(B) Asociar ContentResult a VirtualTopicContent: Modificar el modelo y servicio:
Agregar campo virtual_content_id en ContentResult y completar este valor al guardar
GitHub
. Usarlo como clave principal para queries de resultados de estudiante (ajustar get_student_results en ContentResultService para filtrar por virtual_content_id directamente, simplificando la lógica actual)
GitHub
GitHub
.
Migración: Para resultados existentes, podríamos no migrar (pues igual guardan student y content_id); los nuevos ya vendrán con virtual_content_id.
(B) Fix trigger_next_topic bug: Verificar que la comparación de progreso está correctamente en porcentaje. Confirmamos que ya está usando 80 (no 0.8)
GitHub
, así que solo aseguramos que el frontend le pase valor 0-100 y no 0-1.
(B) Endpoint de progreso de módulo: Implementar en VirtualModuleService un método para calcular progreso del módulo (% de temas completados) y exponerlo (posible ruta: GET /virtual-module/<id>/progress). Usarlo tras completar cada tema para actualizar virtual_modules.progress. Nota: Esto habilitará en el futuro disparar la generación del siguiente módulo cuando progreso >= 80%. Podemos de una vez, al detectar ese umbral, llamar a FastVirtualModuleGenerator.generate_single_module para el próximo módulo (en cola).
(B) Topic readiness incluye pensamiento crítico: Actualizar TopicReadinessService.check_readiness para que, además de quiz, slides, video, etc., compruebe si hay al menos un contenido tipo pensamiento crítico. Si definimos uno (por ej. content_type "guided_questions"), añadir en el dict checks similar a quiz/slides
GitHub
. Marcar missing_requirements si no está.
(B) Endpoints perfiles cognitivos: Revisar /api/profiles/cognitive y /api/users/check para cualquier discrepancia (según backlog). Posiblemente unificar en uno solo o asegurarse de retornar los campos completos (learning_style, profile JSON, etc.). Ajustar frontend si consumía información parcial.
(F) Sidebar estudiante bug: Corregir componente Sidebar/Routes para estudiantes:
Si virtualModules list está vacío para un plan asignado, mostrar el módulo con botón “Iniciar”. Al clic, llamar endpoint que dispara FastVirtualModuleGenerator.generate_single_module(student, module) y luego recargar la lista. Hasta que responda, mostrar spinner “Generando módulo…”.
Si ya hay módulos, listarlos normalmente.
(F) Dashboard datos reales: Reemplazar placeholders de asistencia, etc., con datos de verdad:
Profesor: % de contenidos de cada clase creados o % plan completado por cada alumno (requiere queries, tal vez posponer).
Alumno: mostrar progreso general (ej: “Has completado 2/5 módulos, 45% del curso”) y promedio de calificaciones (de ContentResults evaluativos).
Esto puede requerir nuevos endpoints (por simplicidad, podríamos calcular en frontend a partir de datos de virtual_modules y content_results ya disponibles).
(B) Limpieza y preparación: Eliminar código obsoleto (p.ej. antiguos servicios de juegos simulaciones separados si quedaron referenciados, ya que todo está centralizado en ContentService). Confirmar que todas las llamadas a API usan los nuevos endpoints unificados (ej. create_content, record_result, etc.), evitando rutas legacy.
(B) Logging & docs: Añadir comentarios claros en el código donde apliquemos soluciones temporales: en AdaptiveLearning (fase 1 RL) y en AutoGrading (indicando que es simplificado), para alinear con la expectativa del cliente
GitHub
.
Resultado de Fase 1: Sistema consistente en lo básico: temas se publican solo si cumplen requisitos completos, los resultados de aprendizaje se asocian correctamente a contenidos virtuales, y la navegación del alumno estará libre de confusiones iniciales. Se habrán sentado bases para iniciar plantillas sin arrastrar bugs previos.
Fase 2 – Sistema de Plantillas: Modelos y APIs (Semana 2)
Objetivo: Introducir la nueva arquitectura de Plantillas de Contenido Educativo HTML, manteniendo compatibilidad con contenidos legacy. Esta fase se enfoca en backend (modelos, lógica) y minimal frontend (un lugar para ver “Mis Plantillas”).
(B) Modelos de Plantilla: Crear colección y clases para:
Template (plantilla global): según el diseño dado
GitHub
GitHub
, campos principales:
_id (ej. "tpl_mindmap_v1" si usamos un identificador legible o un ObjectId estándar),
name, ownerId, scope ("private" por default), status ("draft"/"usable"/"certified" para indicar madurez),
engine: "html" (por ahora todas serán HTML),
version (semver string),
forkOf (referencia al template original si es un fork),
html (código HTML completo de la plantilla),
propsSchema (esquema JSON de parámetros configurables),
defaults (valores por defecto para props, opcional),
baselineMix (ej. {V:60,A:10,K:20,R:10} porcentajes VARK base que cubre esta plantilla por diseño),
capabilities (booleans: si usa audio, micrófono, cámara, etc. para advertir requisitos),
styleTags y subjectTags (etiquetas descriptivas de estilo y temática).
TemplateInstance (instancia de plantilla ligada a un Topic): campos según backlog:
templateId, templateVersion (para referenciar la versión exacta usada),
topicId (tema del profesor al que pertenece este contenido),
props (objeto JSON con valores concretos para esta instancia),
assets (lista de assets subidos específicos, con identificador para referenciarlos en la plantilla),
learningMix (mix VARK ajustado: puede ser "mode": "auto" con valores calculados o "mode": "manual" si profesor ajustó),
status (draft/active de la instancia; p.ej. draft mientras el profesor edita).
Extender TopicContent: agregar campos:
render_engine: "legacy" (por defecto para contenidos antiguos) o "html_template" para los nuevos. Así sabemos qué visor/render usar.
instanceId (si este TopicContent está generado a partir de una TemplateInstance),
templateId y templateVersion (redundantes con instance pero útiles para queries globales),
learningMix (copiamos de la instancia para filtrar y para que VirtualContent lo herede fácilmente),
status (lo mantenemos).
Extender VirtualTopicContent: agregar instanceId opcional (apuntando a TemplateInstance) para fácil acceso durante el render en frontend. Su campo content_id seguirá apuntando al TopicContent fachada.
Actualizar los métodos to_dict() y los insert/find correspondientes para incluir estos nuevos campos (sin romper los existentes).
(B) CRUD de Plantillas (Backend):
POST /api/templates: crear una nueva plantilla (status draft). Al menos requerirá name; la versión inicial = "1.0.0"; owner = usuario actual; scope = según parámetro (por defecto private).
GET /api/templates?owner=me|all&scope=public|org|private: listado filtrado. Para “Mis plantillas”, usaremos owner=me (el backend resolverá ownerId = user_id actual) y scope no necesariamente (private+org para ese user). Para marketplace, scope=public.
GET /api/templates/<id>: obtener detalles (principalmente se usaría al editar una plantilla, trae su HTML, schema, etc.).
PUT /api/templates/<id>: actualizar campos de la plantilla (ej. luego de editar código o cambiar status a usable).
POST /api/templates/<id>/fork: clonar una plantilla publicada a propiedad del usuario actual (crea nuevo con forkOf apuntando al original, ownerId nuevo).
POST /api/templates/<id>/extract: procesará el HTML para extraer marcadores de personalización (ver más abajo).
(B) CRUD de Instancias:
POST /api/template-instances: crear instancia a partir de una plantilla para un Topic dado. Requiere templateId, topicId, props (inicialmente podría enviarse vacío para usar defaults), quizá override de learningMix. Devolverá el _id de la nueva instancia y también crear automáticamente un TopicContent asociado a esta instancia:
Al crear instancia, crear también un TopicContent con content_type derivado (p. ej. "diagram" si la plantilla es un diagrama interactivo), render_engine="html_template", instanceId y demás campos nuevos. No generamos el content final aún; se llenará en runtime al visualizar, usando la plantilla + props.
GET /api/template-instances/<id>: obtener instancia (con props) – útil para previsualizar o editar luego parámetros.
PUT /api/template-instances/<id>: actualizar props de instancia (ej. profesor ajusta color, texto, etc.).
POST /api/template-instances/<id>/publish: marcar la instancia como finalizada (podría cambiar status en TopicContent a "active/published"). No hay una gran diferencia entre draft/active en instancias, pero podríamos usarlo para ocultar contenido de alumnos hasta que el profe termine de personalizar.
(B) Render/Preview endpoints:
GET /preview/template/<templateId>: devuelve el HTML bruto de la plantilla (con placeholders) encerrado en un iframe amigable, para previsualizar en editor.
GET /preview/instance/<instanceId>: similar, pero aquí mezclamos la plantilla con sus props para devolver el HTML personalizado listo para mostrar al alumno (o al profe en vista previa).
Estos endpoints deben servir con Content Security Policy estricta (sandbox) para no exponer XSS. Podemos usar Flask para leer el HTML y enviarlo con headers CSP (ej. allow-scripts, disable forms if needed, etc.).
(B) Marcadores de Personalización (extractor):
Implementar la función extract_markers(html) que parsea el código HTML de la plantilla buscando atributos especiales:
data-sapiens-param="paramName" en elementos => en el schema propsSchema añadimos ese paramName con tipo según contexto (texto, número, color, etc. – podríamos inferir por el contenido o simplemente marcar string y dejar al autor ajustar luego).
data-sapiens-asset="assetName" => indica que la plantilla espera un recurso externo (imagen/audio) con id assetName. En propsSchema añadiremos un campo para ese asset (tipo = "asset", maybe store URL).
data-sapiens-slot="slotName" => trozos de texto que se pueden traducir/personalizar por IA para cada alumno (esto probablemente lo manejaremos en fase adaptativa, de momento podría tratarse como param de texto multilínea).
data-sapiens-if="condition" => lógica condicional para ciertos elementos. Esto es avanzado; para fase 1 quizás solo documentamos su existencia sin procesarlo mucho, o lo incluimos en propsSchema como booleanos derivados.
También procesar <script id="sapiens-defaults" type="application/json"> si existe, para prellenar defaults.
El endpoint POST /templates/:id/extract usará esta función para actualizar la plantilla con su propsSchema generado y marcar personalization.isExtracted = true. Devolverá el schema para que el frontend pueda mostrar un formulario de parámetros.
(B) Integración con contenidos legacy:
No eliminar topic_contents: Seguiremos almacenando los contenidos generados vía plantilla también en topic_contents, simplemente indicando render_engine. Así las consultas existentes (como ContentService.get_topic_content) seguirán devolviendo todos los contenidos de un tema (legacy y nuevos)
GitHub
. Sólo que los nuevos registros tendrán content vacío o mínimo y sabremos renderizarlos de otra manera en frontend.
Render condicional: Ajustar el endpoint GET /api/content/<content_id> para que, si el TopicContent tiene render_engine=="html_template", además de los datos habituales, enriquezca la respuesta con la plantilla resuelta o la instancia (podemos incluir directamente el instanceId y quizás un preview URL). Alternativamente, el frontend al ver un TopicContent de ese tipo llamará a preview/instance.
VirtualContent: Al virtualizar un Topic que tiene TemplateInstance, el backend debe generar su VirtualTopicContents derivados. Estrategia: Podríamos no “pre-generar” nada pesado, solo crear los VirtualTopicContents referenciando la misma instancia. En VirtualTopicContent.to_dict nuevo, incluiremos instanceId también
GitHub
. Así, cuando el alumno abra ese contenido, usaremos la plantilla + props + posiblemente overrides del estudiante (ver Fase 5).
(F) Vista básica “Mis Plantillas”:
Añadir una sección en el dashboard de profesor, menú “Plantillas” (junto a Contenidos, Planes, etc.). Allí, inicialmente, mostrar una lista vacía con botón “Nueva Plantilla”.
Nuevo Template (flujo inicial): Al hacer clic, llamar POST /api/templates (crea con html vacío o un boilerplate mínimo). Recibir el ID y luego redirigir a una pantalla de editor.
Editor de Plantilla (en esta fase, rudimentario): Podríamos simplemente abrir un <textarea> gigante con el HTML para que el usuario pegue su código. Sin embargo, para no hacer desde cero un editor, inicialmente permitiremos solo pegar código de plantillas pre-hechas (ya que el cliente proveerá algunas, e.g. mindmap, juegos).
Mostraremos también campos para Tags de estilo y temática, y un botón “Extraer Marcadores”.
Tras pegar el HTML y hacer clic en “Extraer”, llamamos POST /api/templates/{id}/extract. Esto devuelve el propsSchema. A partir de eso, podemos renderizar un formulario de parámetros para prueba.
Nota: En Fase 3 mejoraremos esta UI, pero al menos ya permitiremos guardar la plantilla. Por ahora no embedderemos preview en vivo (eso en Fase 3).
Guardar: Al finalizar, PUT /api/templates/{id} con html final, schema, tags, etc., y marcar status “usable”.
Resultado de Fase 2: Los cimientos de plantillas estarán colocados: modelos en BD, APIs para gestionarlas, y la capacidad de que un profesor registre plantillas HTML interactivas. No obstante, aún no las estamos usando en cursos; eso vendrá en la siguiente fase. El profesor podrá ver sus plantillas (aunque la edición sea básica), preparándonos para integrarlas con los contenidos.
Fase 3 – Integración de Plantillas en Contenidos (Semana 3)
Objetivo: Permitir al profesor usar una plantilla para crear contenido en un tema. Mejorar la UI de creación/edición de plantillas y su previsualización interactiva.
(F) Usar Plantilla como Contenido: En la vista de edición de un Topic (donde enumera sus contenidos y botones “Añadir Contenido”), agregar opción “Usar Plantilla”.
Esto abrirá un diálogo con el Marketplace de Plantillas (privadas propias + públicas disponibles). El profesor puede buscar por nombre, filtrar por tags o tipo (e.g. “quiz”, “diagrama”). Para la Fase 3, incluiremos al menos un filtro por texto y por tipo de contenido.
Al seleccionar una plantilla, llamamos POST /api/template-instances con topicId y templateId. Esto creará la instancia y el TopicContent. Luego, en la lista de contenidos del tema, aparecerá un nuevo item (p.ej. “Mindmap Interactivo – (en edición)”).
Si la plantilla tiene parámetros (propsSchema no vacío), al hacer clic en ese nuevo contenido, se abre un formulario para configurar los props (por ej., texto a mostrar, imágenes a subir, colores). Construimos ese formulario dinámicamente según el schema (tipos de campos: string, number, boolean, asset upload, etc.).
Cuando el profesor llene los campos, al dar Guardar actualizamos la instancia (PUT /api/template-instances/<id>) y recargamos.
(F) Previsualización Live de Instancia: Implementar un componente de vista previa donde el profe pueda ver cómo lucirá su contenido personalizado:
Montaremos un <iframe> sandbox que cargue la URL /preview/instance/{instanceId}. Este iframe mostrará el contenido interactivo funcionando.
Cuando el profesor cambie un parámetro en el formulario, podemos aplicar cambios en vivo enviando postMessage al iframe con los nuevos props, y programar la plantilla para escuchar esos mensajes y actualizar (esto requiere que en la plantilla HTML incluyamos un script para recibir mensajes y aplicar cambios, podríamos posponerlo). Alternativamente, ofrecer un botón “Actualizar Vista Previa” que simplemente recargue el iframe con la nueva configuración.
Este paso es clave para la “prueba de personalización en vivo” pedida: el profesor puede iterar hasta que quede satisfecho.
(F) Publicar/Privatizar Plantillas: En “Mis Plantillas”, para cada plantilla listada, implementar un toggle Publicar. Si la pone en scope=public, aparecerá en el Marketplace público para otros usuarios (solo si status es “usable” o superior). Similarmente, podría haber scope “org” si quiere compartir solo con su institución (eso requiere conocer su institute_id; tenemos MembershipService para consultar).
Implementar esos cambios con PUT /api/templates/<id> (cambiando scope y quizás status).
Nota: la “certificación” de plantillas (estado certified) la dejaremos como futuro (quizá para que administradores validen plantillas de calidad). Por ahora, cualquier plantilla usable puede publicarse.
(B) Backend – conexión con virtualización: Adaptar la generación de módulos virtuales para soportar contenidos de tipo plantilla:
Cuando VirtualTopicService va a generar los contenidos de un tema para un alumno, si encuentra un TopicContent con render_engine = "html_template", no necesita llamar a IA para generarlo (ya está predefinido por el profesor). En su lugar, simplemente crea el VirtualTopicContent copiando instanceId y marcando status not_started. La personalización al alumno quizá requiera ajustar ciertos props (ej.: avatar del estudiante, o dificultad). En esta fase podemos no personalizar a nivel de instancia (dejar todos ven la misma instancia). Más adelante, en Fase 5, veremos overrides por estudiante.
Garantizar que estos contenidos cuenten en la progresión y calificaciones exactamente igual que un legacy. Por ejemplo, si es un juego (plantilla interactiva), al terminar deberá invocar ContentResultService.record_result como cualquier quiz. Podemos implementar dentro de la plantilla cierta llamada (p. ej., la plantilla puede hacer fetch a /api/content/result cuando se cumple objetivo). Documentaremos a los creadores de plantillas cómo deben integrar ese hook (o quizás automatizaremos insertando un script de tracking, pero eso después).
(B) Serialización VARK en contenidos: Cada Template tiene un baseline V,A,K,R. Podemos automatizar que cuando se crea una instancia y su TopicContent, calculemos learningMix para ese contenido combinando su baseline con quizás el estilo del alumno promedio. Por ahora, podríamos simplemente copiar baseline->TopicContent.learningMix. En VirtualTopicContent, luego ajustaremos según perfil alumno (Fase 5).
(F) UI pulido de “Mis Plantillas”:
Mostrar las plantillas del usuario en forma de tarjetas con información: nombre, tipo principal (podemos deducir de un tag o del contenido mismo, e.g. si incluye diagram en styleTags), estado (Draft/Usable), scope (Privada/Pública). Cada tarjeta con botones: Ver, Editar, Clonar, Eliminar.
Ver: abre un modal/iframe con preview de la plantilla base (como la vería cualquiera sin datos).
Editar: navega al editor de plantillas (ya implementado rudimentariamente). En esta fase podemos mejorar el editor integrando un componente de code editor (tal vez Monaco o CodeMirror) para facilitar editar HTML/JS. Si es muy pesado, mantener textarea pero con resaltado básico.
Clonar: llama POST /api/templates/<id>/fork y refresca lista (añadirá “Copia de {Nombre}”). Útil para que un profe tome una pública y la adapte.
Eliminar: si status draft y no usada, permitir DELETE (simplemente ponemos status="deleted" o removemos registro). Hay que cuidar que si algún TopicInstance la usa, no se pueda eliminar (o elimine también esas instancias).
(B) Cascada de eliminación: Ya que tocamos eliminaciones: completar la lógica pendiente:
Cuando se elimina un Topic, ahora también hay que borrar sus topic_contents asociados
GitHub
 (en Fase 1 no lo hicimos). Añadir: get_db().topic_contents.delete_many({"topic_id": {"$in": topic_ids}}). Igualmente, borrar template_instances de esos topics y quizás virtual_topic_contents relacionados (aunque al eliminar topics, los virtual topics y sus contents se van a eliminar en cascada también si implementamos).
Cuando se elimina un Module, eliminar también template_instances ligados a topics de ese módulo, y virtual_contents relacionados (los VirtualModule/Topics se borran ya).
Probar varias veces eliminación de plan -> módulos -> temas -> contenidos -> instancias para evitar datos huérfanos.
El backlog enfatizó que esta limpieza en cascada esté completa, así evitamos acumulación de basura en BD.
Resultado de Fase 3: Los profesores podrán crear contenidos interactivos personalizados en sus temas usando plantillas. Aunque la experiencia de edición de plantilla mejorará en fases siguientes, ya tendrán disponible un pequeño catálogo (pudiendo subir algunas plantillas predefinidas que tengamos listas, e.g. un juego de memoria, un mapa mental). Los alumnos aún no verán cambios (los verán en Fase 4 cuando interactúen con ellos). Tendremos que capacitar a los primeros usuarios en la creación de plantillas, pero hemos construido la infraestructura clave.
Fase 4 – Marketplace Público y Uso Avanzado de Plantillas (Semana 4)
Objetivo: Abrir el Marketplace público de plantillas y afinar detalles avanzados: incrustar plantillas dentro de slides, certificación de plantillas, etc.
(F) Marketplace de Plantillas (Público):
Crear una página accesible quizás desde la Landing o desde la sección plantillas (“Buscar Plantillas Públicas”) listando todas las plantillas con scope="public" y status="usable" o "certified". Cada tarjeta similar a las de “Mis plantillas” pero sin botones de editar/eliminar (solo Ver y Usar/Clonar).
Permitir filtrar por categoría (ej. dropdown de styleTags: juegos, diagramas, quizzes…) y búsqueda por nombre/texto.
Cuando un usuario usa una plantilla pública en su curso, realmente hará un fork automático (para que pueda editar su instancia sin afectar la original). Así que el botón Usar puede llamar internamente POST /api/templates/{id}/fork, luego crear instancia de ese fork. O directamente POST /api/template-instances con templateId original pero lógica backend: si scope=public y owner≠user, entonces fork internamente antes de instanciar. Evaluaremos la mejor opción para que no tener instancias de plantillas ajenas que el autor podría cambiar.
UI mostrará también rating o indicativo de calidad si tuviéramos (no por ahora). Tal vez ordene por popularidad (podemos agregar campo usage_count a Template al ser usada, similar a cómo ContentService incrementa uso de tipos
GitHub
).
(B) Fusión con Slides existentes: Algunos contenidos legacy (como diapositivas) podrían querer incorporar plantillas. Por ejemplo, tener una slide con un iframe embed de una plantilla (como el backlog indicaba “Slides + Embed: bloque para embeber instancias”). Esto es complejo y quizá innecesario si podemos simplemente alternar slides y contenidos interactivos como elementos separados en el flujo del tema.
Por ahora, no incrustaremos plantillas dentro de slides; en lugar, un contenido de tipo plantilla estará al mismo nivel que una diapositiva. En el futuro, podríamos permitir en el editor de slides insertar un componente interactivo (lo que implicaría mezclar HTML de slide con el de plantilla, complicado). Así que dejamos esto como idea a futuro.
(B) Validación (“Certificación”) de Plantillas: Implementar un flujo (quizás manual por admin) para marcar plantillas probadas como “certified”.
Podríamos tener un endpoint admin PUT /api/templates/<id>/certify que setea status certified.
En la UI, mostrar insignia “✓ Certificada” para estas plantillas en el marketplace.
A efectos prácticos, esto es cosmético en esta fase. Lo principal es tener el campo y quizás filtrar: (ej. un filtro “Ver solo certificadas” en marketplace).
Como no hay aún roles de marketplace definidos, probablemente todos publicadas por SapiensIA se consideren certified. Documentaremos este concepto para uso futuro.
(F) Refinar Editor de Plantillas: Ideal dedicar tiempo a mejorar la experiencia:
Integrar un editor de código con realce de sintaxis y quizás autocompletado básico de HTML/CSS/JS.
Mostrar en una columna el formulario de parámetros (una vez extraídos) y permitir editar el JSON schema manualmente para ajustes finos.
Probar la personalización en vivo: implementar que al cambiar un campo, el iframe preview reciba postMessage y la plantilla (incluiremos en nuestras plantillas de ejemplo un script listener) actualice ese elemento. Si esto funciona, el profesor verá los cambios instantáneamente sin recargar.
Cuidar la seguridad: el iframe del preview debe estar aislado (usar sandbox attribute con allow-scripts, allow-same-origin si necesita). Como extra, podemos generar en backend un dominio separado (o endpoint distinto) para servir previsualizaciones sin JWT, quizás no necesario si embed en same origin con sandbox.
(B) Documentar a creadores de plantillas: Crear un pequeño manual (en Notion o en docs del repo) con las convenciones: cómo marcar parámetros, cómo enviar resultado de un juego (ejemplo: hacer parent.postMessage({type:'result', score: X}, '*') desde la plantilla para que el container lo capture y llame record_result), etc. Esto facilitará que terceros creen plantillas útiles.
(F) Ajustes visuales finales: Arreglar detalles en UI:
Tema claro/oscuro toggle funcional.
Modo concentración (Pomodoro timer, ruido blanco, música) finalizado: integrar los componentes ConcentrationToggle, etc., en la pantalla estudiante. Probar que el temporizador Pomodoro funciona y tiene notificaciones (puede que esté ya casi listo, solo styling).
Lenguas indígenas y diccionarios: Si hay una sección para esto (quizá en estudiante para consulta), revisarla. Puede ser simplemente un contenido estático o un pequeño módulo; asegurarnos que no quedó olvidada. Sino, anotarlo para fase posterior.
Revisión final de responsive: comprobar vistas clave en móvil (login, dashboard, ver módulo, hacer quiz) y aplicar CSS/tailwind fixes donde se rompa el layout.
Resultado de Fase 4: La plataforma tendrá un Marketplace de plantillas operando, permitiendo compartir recursos interactivos a toda la comunidad. Los profesores podrán enriquecer sus cursos con plantillas creadas por otros con un par de clics. La edición de plantillas será mucho más cómoda. Se habrán pulido muchos aspectos de la UI para una experiencia más fluida y moderna.
Fase 5 – Motor Adaptativo y Personalización por Alumno (Semana 5)
Objetivo: Aprovechar los datos de resultados para retroalimentar la experiencia de cada alumno y cerrar el ciclo adaptativo.
(B) Servicio Adaptativo Estadístico: Desarrollar AdaptiveLearningService.calculate_content_preferences(user_id):
Recuperar todos los ContentResult del usuario (quizá filtrar últimos N para dar más peso a lo reciente).
Calcular por cada tipo de contenido: tasa de éxito (promedio de score, o %aprobación si es evaluativo, o simplemente considerar completado=100 como éxito para lecturas).
Identificar los estilos predominantes: p.ej., si juegos/quizzes tienen notas > textos/diapositivas, inferir que el alumno aprende mejor de forma kinestésica/activa vs pasiva. Mapear estas conclusiones a prefer_types/avoid_types. (Ejemplo: si contenidos con visual tag tienen promedio 90 y con reading solo 60, entonces prefer_types+=visual, avoid_types+=text).
Rellenar un objeto contentPreferences con:
prefer_types: hasta 3 tipos con mejor desempeño relativo.
avoid_types: tipos con desempeño claramente inferior.
content_analysis: para cada tipo relevante almacenar stats calculadas (score_avg, n_attempts, etc. y quizás un preference_score normalizado 0-1).
Guardar esto en users.cognitive_profile.profile.contentPreferences. Añadir también quizás un timestamp de última actualización.
Marcar en comentarios del código que en segunda fase este cálculo será reemplazado por RL avanzado (y potencialmente movido a un microservicio/colab).
(B) Integración con VirtualTopic personalización: Ahora que cada VirtualTopicContent tiene personalization_data general (basado en cognitive_profile VARK), podemos mejorar:
Si tras algunas interacciones detectamos que al alumno le va mejor con cierto estilo, podríamos ajustar la dificultad o presentación de contenidos futuros. Ejemplo: Si contentPreferences indica muy visual, podríamos aumentar el uso de imágenes o diagramas dentro de los contenidos adaptados (para contenidos generados por IA, podríamos en prompts futuros pedir “incluye más diagramas”).
Esto es complejo de automatizar en esta fase, pero sí podemos ajustar al vuelo la mezcla VARK de plantillas en VirtualTopic: recordemos que cada TemplateInstance tiene learningMix (V,A,K,R). Cuando creamos VirtualTopicContents para un alumno, comparemos su perfil con el mix de la plantilla; si su perfil tiene un estilo muy dominante, podemos aplicar un “sesgo” en VirtualTopicContent.overrides.vakHints. Por ejemplo, en VirtualTopicContent almacenar vakHints: {"preferA": true} si el alumno es altamente auditivo y la plantilla soporta audio (esto se vio sugerido en backlog final). Las plantillas podrían leer estos hints para activarse en consecuencia (p.ej., si preferA, reproducir narración).
Este nivel de detalle es aspiracional; dado el tiempo, lo documentaremos y prepararemos, aunque la implementación completa quedaría para una fase posterior con RL.
(F) Feedback al alumno: Añadir quizá en la UI al finalizar un módulo/presentación una breve encuesta: “¿Con cuál tipo de recurso te sentiste más cómodo aprendiendo?” con opciones (texto, videos, juegos, etc.). Si responde, lo podemos capturar y alimentar manualmente su perfil (contentPreferences). Esto no estaba en requerimientos explícitos, pero se mencionó en conversaciones
GitHub
. De hacerlo, sería un pequeño modal opcional.
(F) Visualización de Progreso Adaptativo: En el perfil del estudiante (sección “Mi Perfil de Aprendizaje”), mostrarle su estilo de aprendizaje (lo obtenido de su test inicial, si lo hay, más las adaptaciones aprendidas). Por ejemplo: “Eres 40% visual, 30% kinestésico. El sistema ha notado que rindes mejor con contenidos visuales.”. Esto además de ser informativo, genera confianza en el sistema adaptativo. Podemos obtener estos datos de cognitive_profile.learning_style y contentPreferences.
(B) Evaluaciones – últimos retoques: Si la Evaluación formal puede componerse de varios ContentResults (quiz + entrega, etc.), quizá crearemos un método para combinar notas (p.ej., calculadora de nota final de evaluación si tiene varias partes). Esto podría sobrepasar el scope actual; lo básico es permitir manual override, que ya está.
(F) QA general: Realizar pruebas integrales con un curso completo:
Crear plan, módulos, temas con contenidos legacy y con plantillas.
Publicar temas, generar módulo virtual para un alumno de prueba.
Recorrer como alumno, completar contenidos, verificar que el progreso sube, que los nuevos contenidos se visualizan bien (e.g., plantillas funcionan en ambiente virtual).
Probar el motor adaptativo: simular que el alumno falla mucho en quizzes pero lee todos los textos -> tras contenido, recalcular perfil y ver si en siguientes temas selecciona más contenidos textuales (difícil de probar en poco tiempo, pero checar que no rompe nada).
Revisar logs de errores y corregir bugs encontrados.
Resultado de Fase 5: SapiensIA estará plenamente adaptativa: cada estudiante recibe no solo un curso personalizado inicialmente a su perfil, sino que el sistema aprende de sus interacciones para refinar aún más la experiencia. Aunque el motor RL aún será rudimentario, la infraestructura estará lista para una mejora continua.
Implementaciones Futuras (post-fase 5):
Al concluir estas fases, habremos cubierto los requerimientos prioritarios sin romper compatibilidad. Quedarán pendientes a abordar en el roadmap posterior:
Aplicación móvil completa: tras estabilizar web, desarrollar en React Native enfocándonos en las funciones clave (corrección de exámenes con foto – integrando quizá un servicio OCR en backend – y consumo de módulos por alumnos).
Marketplace de cursos con pagos: implementar la publicación de planes de estudio (quizás convertir StudyPlan en un “Course” con campos de precio, descripción) y listarlos públicamente, integrando un sistema de pago (Stripe) y suscripciones de alumnos a esos cursos. Requerirá también manejo de roles (profesor vendedor, etc.) y seguridad extra.
Aprendizaje por Refuerzo avanzado: integrar un modelo de IA (por ej. una red neuronal de bandit o un algoritmo de multi-armed bandit) que decida en tiempo real el mejor siguiente contenido para un alumno, en base a su historial. Esta sería la Fase 2 del motor adaptativo, potenciando la plataforma con verdadera personalización inteligente.
Más automatización en corrección de evaluaciones: incluir reconocimiento automático de texto en imágenes para exámenes escritos, evaluación de código con baterías de tests en sandbox, y eventualmente un análisis cualitativo por IA de ensayos (GPT que lea una respuesta larga y genere feedback/nota basado en la rúbrica).
Continuas mejoras UX/UI: incorporar gamificación en la interfaz (logros para alumnos), reportes analíticos para profesores (ej. “Tu clase tiene promedio X en visual, Y en kinestésico, etc.”), y optimizaciones de rendimiento a medida que crezca la base de usuarios y contenidos.
En síntesis, con este plan abordamos los requerimientos actuales de forma integral y escalonada, asegurando que el sistema evolucione sin traumas: primero corregimos la base, luego introducimos las plantillas interactivas (una mejora estructural grande) de forma retrocompatible, y finalmente potenciamos la adaptatividad y la experiencia de usuario. Así, SapiensIA quedará preparada para ofrecer una educación verdaderamente personalizada, interactiva y escalable.