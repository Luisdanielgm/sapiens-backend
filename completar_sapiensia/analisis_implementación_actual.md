Análisis comparativo de implementación actual de SapiensIA
Arquitectura virtual y flujo actual
Ámbito	¿Implementado?	Evidencias y análisis
Modelo de Virtualización (VirtualModule, VirtualTopic, VirtualTopicContent)	Sí	En el backend existen modelos completos para VirtualModule, VirtualTopic y VirtualTopicContent. VirtualModule registra el módulo original, el estudiante, el estado de generación y progreso
raw.githubusercontent.com
. VirtualTopic incorpora campos de orden, estado y un flag locked para controlar el acceso
raw.githubusercontent.com
. VirtualTopicContent almacena el contenido adaptado para el alumno, el content_id original y un objeto interaction_tracking con métricas de uso y porcentaje de completado
raw.githubusercontent.com
.
Servicio de módulos virtuales	Sí	Existe VirtualModuleService con métodos para crear módulos y obtener detalles con las propiedades necesarias
raw.githubusercontent.com
. El método get_student_modules devuelve todos los módulos virtuales de un estudiante en un plan de estudios
raw.githubusercontent.com
.
Generación progresiva de temas	Sí, con limitaciones	La función trigger_next_topic_generation genera hasta dos temas por delante cuando el progreso de un tema virtual supera el 80 %
raw.githubusercontent.com
. Genera nuevos VirtualTopic desbloqueados y copia sus contenidos sin filtrarlos por perfil
raw.githubusercontent.com
. Actualmente, los nuevos temas se crean con locked=False
raw.githubusercontent.com
, por lo que el alumno puede saltar entre ellos. El servicio también marca el tema como completado al 100 %
raw.githubusercontent.com
.
Sincronización de contenidos	Parcialmente	Hay una función _generate_topic_contents_for_sync que, al crear un tema virtual, copia todos los TopicContent originales al estudiante. No existe lógica de filtrado: el bucle inserta cada contenido independientemente del perfil cognitivo
raw.githubusercontent.com
. Por tanto, la personalización por estilo de aprendizaje aún no está implementada.
Sistema de resultados de contenido (ContentResult)	Sí	La clase ContentResult almacena el resultado de la interacción (score, feedback y métricas)
raw.githubusercontent.com
. El servicio ContentResultService.record_result permite registrar resultados y actualiza el tracking del VirtualTopicContent para marcar su porcentaje de completado
raw.githubusercontent.com
raw.githubusercontent.com
.
Evaluaciones (Evaluation)	Modelo implementado, lógica faltante	El modelo Evaluation define título, descripción, peso, uso de nota de quiz y fecha límite
raw.githubusercontent.com
, y existe EvaluationResource para asociar archivos
raw.githubusercontent.com
. En la API de módulos virtuales aún no se observa un flujo completo para crear evaluaciones, subir entregas o calcular notas. La entrega de resultados de contenidos se hace mediante POST /virtual/content-result
raw.githubusercontent.com
, pero no hay un endpoint análogo para evaluaciones formales, por lo que la funcionalidad de evaluaciones está incompleta.
Marcadores y personalización de contenido	Extracción implementada, IA no integrada	El servicio ContentPersonalizationService.extract_markers identifica marcadores {{...}} en textos y los devuelve segmentados
raw.githubusercontent.com
. Estos marcadores se guardan en TopicContent.personalization_markers
raw.githubusercontent.com
. En el frontend se usan hooks para reemplazar esos marcadores, pero en el backend no existe servicio que invoque una IA real; se señala que hoy se usa una función simulada.
Sistema de traducciones indígenas	Sí	El módulo indigenous_languages ofrece endpoints para crear traducciones (POST /translations) y consultarlas con filtros avanzados
raw.githubusercontent.com
raw.githubusercontent.com
. También existen rutas para búsqueda, obtención de idiomas y carga masiva
raw.githubusercontent.com
.

Funcionalidades no implementadas o parciales
Filtrado por perfil cognitivo: Durante la generación de temas virtuales, el servicio _generate_topic_contents_for_sync clona todos los TopicContent del tema original y sólo anota en personalization_data que están adaptados al perfil
raw.githubusercontent.com
. No existe lógica que seleccione tipos de contenido según el estilo de aprendizaje del estudiante, por lo que los alumnos reciben todos los recursos (diapositivas, textos, quizzes, etc.). Implementar ese filtrado es esencial para la personalización.

Aprendizaje por refuerzo del perfil: El plan propone ajustar el perfil cognitivo en función de los resultados del alumno, pero no hay código que actualice el perfil usando los ContentResult. Falta un servicio que analice los resultados y modifique profile.preferred_modalities.

Sistema completo de evaluaciones: Aunque existen modelos de Evaluation y EvaluationResource
raw.githubusercontent.com
, la API no ofrece endpoints para que el profesor configure evaluaciones, asocie un quiz o solicite entregas. Tampoco hay lógica que calcule la nota final combinando ContentResult de quizzes o proyectos.

Corrección automática de exámenes con IA: No se implementa ningún servicio que procese imágenes de exámenes, extraiga texto por OCR y llame a un LLM para calificar. El backend carece de un endpoint que reciba archivos de examen y devuelva una nota. La clase ContentTypes enumera tipos de evaluación (exam, project)
raw.githubusercontent.com
, pero no hay servicios para manejarlos.

Generación concurrente de contenidos y modelos en paralelo: El plan menciona la necesidad de disparar varias peticiones de generación en paralelo y alternar modelos IA según fallos. No se observa en el backend un servicio que gestione múltiples modelos ni lógica de reintentos. La generación de contenido es secuencial y basada en un único modelo.

Marketplace de plantillas de juegos/simulaciones: Aunque ContentTypes incluye categorías para juegos y simulaciones
raw.githubusercontent.com
, no hay modelos para GameTemplate ni rutas para un mercado de plantillas. La sección sobre generación de juegos se trata aparte y todavía no está integrada.

Integración completa del frontend: El código del frontend no está disponible en este entorno, pero a partir de la descripción del usuario se sabe que hay un useTopicOrchestrator que divide HTML de diapositivas y un ContentRenderer que reemplaza marcadores. La IA que secuencia las diapositivas y personaliza el contenido está simulada. No se han encontrado en el backend endpoints específicos para secuenciación con IA, por lo que se presume que la secuencia se calcula en el frontend.

Suscripciones, multiinstitución y app móvil: El backend actual no incluye un sistema de pagos ni modelos para diferentes planes de suscripción; los endpoints de autenticación se basan en JWT simples. El soporte para multiinstituto (usuarios con varias instituciones) y la app móvil de corrección de exámenes tampoco se observa en los servicios actuales.

Sistema de notificaciones y dashboards: No hay evidencia de un servicio de notificaciones ni de APIs que devuelvan estadísticas elaboradas para los dashboards. La mayoría de los indicadores que se muestran en las maquetas deben calcularse de manera custom; en los servicios actuales no se encuentran funciones de analítica que consoliden progreso o calificaciones globales.

Conclusiones y pasos recomendados
El núcleo de la virtualización —modelos y endpoints para crear módulos virtuales, temas y registrar resultados— está implementado y operativo
raw.githubusercontent.com
raw.githubusercontent.com
. La plataforma actualmente permite a un estudiante recibir todos los contenidos de un tema en su módulo virtual, visualizarlos y reportar su progreso y resultados de interacción
raw.githubusercontent.com
raw.githubusercontent.com
. Existe un módulo robusto para la gestión de traducciones de lenguas indígenas
raw.githubusercontent.com
, así como modelos de evaluación que sientan la base de un sistema de calificaciones
raw.githubusercontent.com
.

Sin embargo, la visión de SapiensIA de una educación realmente personalizada y multidimensional aún no se materializa del todo. Falta integrar la selección adaptativa de recursos al perfil cognitivo, el aprendizaje por refuerzo de dicho perfil, un flujo completo de evaluaciones con corrección automática por IA, el marketplace de contenidos y el soporte para multiinstituto y suscripciones. La orquestación de contenidos y la personalización de marcadores funcionan con datos simulados; es necesario conectar un servicio real de IA para que los estudiantes reciban contenidos ajustados a su contexto. Consolidar estas áreas permitirá que la plataforma pase de ser un repositorio de contenidos a un asistente pedagógico adaptativo. Pensando en el futuro, convendría priorizar la personalización y el sistema de evaluaciones, ya que son los diferenciales más valiosos para los usuarios.