Análisis del Sistema de Módulos Virtuales Progresivos
Estructura Actual: Planes de Estudio, Módulos, Temas y Contenido
En el backend, cada Plan de Estudio (StudyPlanPerSubject) contiene una lista de Módulos asociados. Cada Módulo tiene atributos como nombre, resultados de aprendizaje y fechas, e incluye un indicador booleano ready_for_virtualization que indica si el profesor lo ha habilitado para virtualización
GitHub
. Inicialmente este flag está en False, lo que significa que el módulo no está listo para generar módulos virtuales hasta que el profesor agregue contenido y lo habilite explícitamente. Cada Módulo abarca varios Temas. Un Tema (Topic) pertenece a un módulo (campo module_id) e incluye información como nombre, dificultad, contenido teórico (campo theory_content) y una lista de recursos adjuntos
GitHub
GitHub
. Estos campos permiten al profesor crear la estructura curricular: por ejemplo, un módulo puede tener 5 temas, cada uno con su teoría, ejercicios, recursos multimedia, etc. Para gestionar el contenido de los temas, el sistema unificó todos los tipos de contenido (texto, diapositivas, videos, juegos, simulaciones, cuestionarios, etc.) bajo un modelo único de Contenido de Tema (TopicContent). Ya no existen colecciones separadas para juegos o simulaciones; ahora se define un catálogo de tipos de contenido (ContentType) con categorías (estático, interactivo, inmersivo) y subcategorías (p. ej. game, simulation, quiz, diagram, etc.)
GitHub
. Cada instancia de TopicContent representa una pieza de contenido dentro de un tema, indicando su tipo (content_type), título, datos (por ejemplo texto HTML, JSON de una simulación, URL de video), duración estimada, etc
GitHub
. Esto significa que un tema puede tener múltiples contenidos (por ejemplo, una sección teórica de texto, un video de YouTube y un juego interactivo) todos registrados en la colección unificada topic_contents. Adicionalmente, los Recursos (archivos, enlaces externos) se vinculan a los temas a través de una colección de recursos por tópico (por ejemplo, TopicResource), permitiendo adjuntar materiales de apoyo. Algunas evaluaciones también se asocian a recursos a través del modelo EvaluationResource
GitHub
 (por ejemplo, un PDF con enunciados o una rúbrica). En general, el sistema busca tratar vídeos, diagramas o juegos ya no como entidades separadas sino como contenidos del tema. Esto simplifica el modelo de datos: un video de YouTube ahora se podría guardar como un contenido de tipo "VIDEO" en TopicContent, en vez de manejarlo como recurso aislado. En cuanto a las Evaluaciones: Cada módulo puede tener evaluaciones planificadas (exámenes, proyectos, cuestionarios). Existe un modelo de Evaluación (Evaluation) que incluye título, descripción, peso en la calificación, criterios de evaluación, fecha de entrega, etc
GitHub
. Notablemente, una evaluación puede tener use_quiz_score y linked_quiz_id
GitHub
, lo que indica que puede vincularse a un quiz interactivo y aprovechar automáticamente la puntuación de ese quiz. Esto sugiere que las evaluaciones formativas (como cuestionarios en línea) se integran con la plataforma interactiva de quizzes, aunque actualmente los Quizzes se manejan por separado en la capa virtual (ver más adelante). En resumen, la relación jerárquica está definida así: un Plan de Estudio contiene Módulos; cada Módulo contiene Temas; cada Tema tiene contenidos (teoría, multimedia, juegos, etc.) y recursos adjuntos. Los profesores deben ingresar el contenido de cada tema (mínimo texto teórico y posiblemente recursos o actividades) antes de habilitar el módulo para los estudiantes.
Módulos Virtuales y Temas Virtuales Personalizados
El objetivo de la aplicación es que los alumnos cursen versiones personalizadas de los módulos: para ello el sistema genera Módulos Virtuales y Temas Virtuales específicos para cada estudiante, basados en la planificación del profesor. Cada Módulo Virtual (VirtualModule) corresponde a un módulo del plan de estudios, pero adaptado a un alumno. Cuando se crea, se guarda la referencia al módulo original (module_id) y al plan de estudios original (study_plan_id) junto con el alumno (student_id)
GitHub
GitHub
. En la base de datos, por tanto, un VirtualModule actúa como instancia de un módulo del plan para un estudiante en particular. Incluye también campos para seguimiento de generación (generation_status, progreso, etc.) y un registro de adaptaciones aplicadas (p. ej. perfil cognitivo del alumno utilizado en la generación)
GitHub
GitHub
.
Nota: Originalmente la clase VirtualModule no incluía explícitamente el campo module_id en su constructor, pero en la creación sí se añade manualmente antes de insertar
GitHub
. Esto garantiza que en la base de datos cada módulo virtual conozca a qué módulo original corresponde. De hecho, al obtener detalles se rellena ese campo si falta para módulos virtuales antiguos
GitHub
. En la consulta de módulos virtuales de un estudiante, usan module_id para vincular con los módulos originales
GitHub
.
Cada Módulo Virtual contiene a su vez Temas Virtuales (VirtualTopic). Un VirtualTopic es la instancia personalizada de un tema para el estudiante. En la generación rápida se crea un VirtualTopic por cada tema original del módulo
GitHub
GitHub
. El modelo VirtualTopic guarda referencia a su módulo virtual padre (virtual_module_id), nombre y descripción (copiados del tema original), y un campo order para reflejar el orden secuencial del tema dentro del módulo
GitHub
. Importante: aunque VirtualTopic tiene un campo llamado content y multimedia_resources
GitHub
, en realidad el contenido detallado del tema virtual no se almacena directamente ahí, sino que se maneja mediante los Contenidos Virtuales del Tema. Para cada contenido de un tema original, el sistema crea un Contenido de Tema Virtual (VirtualTopicContent) específico para el alumno. Esta entidad representa la versión personalizada de un contenido para ese tema virtual. Por ejemplo, si el Tema 1 tenía un video y un juego, al generarse para el estudiante X se crearán dos VirtualTopicContent: uno apuntando al video (quizá simplemente referenciando el contenido original) y otro al juego (posiblemente adaptado o recién generado). El modelo VirtualTopicContent guarda la referencia al virtual_topic_id y al content_id original, más campos para personalización (p. ej. parámetros adaptados por IA), seguimiento de interacción (intentos, tiempo utilizado, score obtenido, etc.) y permisos de acceso
GitHub
GitHub
. En general, se buscó unificar también aquí las estructuras: antes había colecciones separadas como virtual_games o virtual_simulations, pero ahora todo es virtual_topic_contents con un campo indicando el tipo de contenido
GitHub
. Esto simplifica el manejo de contenido personalizado: un juego o simulador personalizado para el alumno se registra igual que un contenido estático personalizado. El sistema también registra resultados de la interacción del alumno con el contenido a través de Resultados de Contenido (ContentResult). Por ejemplo, cada vez que un alumno completa una actividad (un juego, un quiz, etc.), se puede guardar un ContentResult con su puntaje, feedback, métricas de aprendizaje, etc
GitHub
GitHub
. Esto reemplaza las antiguas colecciones separadas de resultados de juegos, de simulaciones, etc., unificando todos los tipos de resultado bajo un solo modelo
GitHub
. En otras palabras, todos los contenidos interactivos comparten un formato común de resultado, lo cual refuerza la idea de que un quiz, un juego o una simulación son simplemente distintos ContentTypes pero siguen una misma interfaz de registro de resultados. Ahora bien, el sistema aún maneja las Evaluaciones interactivas (Quizzes) con un modelo dedicado en la sección virtual. Existe la clase Quiz dentro de virtual.models.py, que representa un cuestionario interactivo asociado a un módulo virtual
GitHub
. Un Quiz virtual incluye el título, descripción, fecha límite, los temas cubiertos (referenciando IDs de temas originales) y la lista de preguntas con sus opciones y respuestas correctas
GitHub
GitHub
. Asimismo, QuizResult almacena el resultado de un intento de quiz por un estudiante (respuestas elegidas, puntaje, feedback)
GitHub
GitHub
. Estos quizzes se pueden ver como evaluaciones formativas integradas: por ejemplo, el profesor puede haber marcado en el plan una evaluación tipo "quiz" que el sistema despliega al alumno como un Quiz interactivo en el módulo virtual. Relación Evaluación-Quiz: Cuando una Evaluación del plan tiene use_quiz_score=True y un linked_quiz_id, significa que está ligada a un Quiz virtual y que la nota del quiz se usará como calificación de esa evaluación
GitHub
. Actualmente, los quizzes virtuales se crean en la fase de generación de módulos virtuales (si están definidos en el módulo original) y viven en la colección quizzes. Sin embargo, conceptualmente un quiz podría haberse modelado también como un tipo de TopicContent (por ejemplo, un contenido interactivo de tipo "quiz" dentro de un tema). Una posible simplificación sería unificar los quizzes con el modelo de contenidos, en vez de mantener un modelo separado. Esto se discute más adelante en las recomendaciones. En resumen, cuando un módulo virtual es generado para un alumno, se crean:
Un documento en virtual_modules que representa el módulo personalizado.
Un documento en virtual_topics por cada tema del módulo.
Varios documentos en virtual_topic_contents por cada contenido de cada tema (según el perfil del alumno, se pueden generar contenido adicionales o adaptar los existentes).
Opcionalmente, documentos en quizzes si el módulo incluye un quiz evaluativo, y en virtual_topic_contents para vincular contenido de tipo evaluación/quiz al tema correspondiente.
Los resultados (content_results o quiz_results) se generan conforme el alumno interactúa.
Toda esta generación ocurre sujeta a que el módulo original esté habilitado para virtualización, como veremos a continuación.
Habilitación de Módulos y Temas para Virtualización
Antes de que un alumno pueda generar su módulo virtual personalizado, el profesor debe habilitar el módulo. Esto se hace mediante el flag ready_for_virtualization en el módulo. En la interfaz docente se presenta como un checkbox al lado del nombre del módulo en la lista de módulos del plan
GitHub
. El docente debería marcarlo solo cuando el contenido del módulo esté completo y listo: es decir, todos sus temas tienen contenido suficiente (teoría, recursos) y al menos una evaluación configurada. El sistema proporciona un endpoint que calcula la preparación para virtualizar un módulo, devolviendo si está listo o qué le falta. Esa verificación (get_virtualization_readiness) revisa: total de temas, cuántos temas carecen de contenido teórico, cuántos sin recursos, cuántas evaluaciones tiene, y calcula un porcentaje de completitud de contenido
GitHub
GitHub
. También sugiere acciones al docente, por ejemplo "Agregar al menos un tema" si el módulo no tiene ninguno, o "X temas sin contenido teórico" si detecta temas vacíos
GitHub
. Según esta lógica, el sistema consideraría un módulo listo (ready=True) únicamente si: ready_for_virtualization es True y missing_theory_count = 0 y missing_resources_count = 0 y hay al menos 1 evaluación
GitHub
. Es una política bastante estricta: requiere que no falte contenido en ningún tema y exista al menos una evaluación, antes de dar luz verde definitiva. Sin embargo, en la práctica los profesores podrían querer habilitar parcialmente. Por ejemplo, el escenario planteado describe un caso donde el profesor solo tuvo tiempo de preparar 3 temas (de 5) esta semana y quiere habilitar esos, dejando los últimos 2 temas para más adelante. Actualmente, el sistema no maneja un flag de "tema habilitado" individual; el control es a nivel módulo completo. Esto podría significar que, con la lógica actual, el profesor no debería marcar ready_for_virtualization hasta completar todo el módulo, porque si lo marca antes, la verificación detectará temas con contenido faltante y ready seguirá siendo falso (aunque el flag esté true, las sugerencias indicarían contenido faltante). De hecho, el endpoint de readiness sugiere "habilitar la virtualización del módulo" si ready_for_virtualization está falso
GitHub
, pero también sugiere completar contenido faltante si lo hay. ¿Qué ocurre si el profesor habilita un módulo incompleto? En el estado actual, el backend no impide hacer ready_for_virtualization=True aunque falten contenidos; simplemente registra el flag. Luego, al generar, el código de generación no filtra tema por tema en base a contenido presente: tomaría todos los temas del módulo. Esto puede causar situaciones donde se generan temas vacíos para el alumno o se alcanza un punto en que faltan temas siguientes. Por ejemplo, supongamos que un módulo tiene 5 temas pero solo 3 tienen contenido; el profesor marca el módulo como listo. Al alumno generar su módulo virtual, el sistema crearía 5 VirtualTopics (porque encuentra 5 temas) y para cada uno intentaría generar contenido. Para los temas 4 y 5, posiblemente generaría contenidos en blanco o muy básicos (la función _generate_virtual_topics_fast actualmente no comprueba si theory_content existe; simplemente recorre todos los topics
GitHub
). Esto no es lo ideal, ya que el alumno vería temas 4 y 5 vacíos o sin habilitar. Lo esperado en la especificación original es un comportamiento progresivo: solo se deben generar los primeros temas que estén habilitados y disponibles, y los demás esperar a que el profesor los active. Para lograr esto, habría que refinar la lógica. Algunas opciones de mejora podrían ser:
Control por tema: Introducir un flag por cada tema indicando si el profesor lo ha publicado (por ejemplo ready o enabled a nivel de tema). Así, la generación de temas virtuales podría filtrar topics.find({"module_id": X, "enabled": True}) para solo generar aquellos temas cuyo contenido ya fue publicado por el docente. Actualmente, la consulta toma todos los temas del módulo
GitHub
, lo cual ignora el estado de completitud individual. Con un flag a nivel tema, se podría generar solo los temas habilitados.
Generación diferida de temas: Alternativamente, incluso sin flag por tema, se podría limitar la generación inicial a un número fijo de temas (por ejemplo 2) y generar los siguientes sobre la marcha conforme el alumno avance (similar a lo que se hace a nivel módulos). Esto implementaría la idea "si solo 1 tema está habilitado, generar 1; si hay 2 o más, generar 2, que es el máximo inicial". Sin embargo, el backend actual no lo hace así: como se mencionó, genera todos. Habría que cambiar _generate_virtual_topics_fast para que en vez de iterar todos los topics, solo tome los primeros N (N=2, por ejemplo) o los que estén marcados como listos.
En cualquier caso, el diseño actual confía en el flag del módulo. Si ningún módulo está habilitado, el alumno no puede generar nada y recibirá un error. De hecho, el endpoint de inicialización progresiva verifica esto explícitamente: busca módulos ready_for_virtualization: True en el plan, y si la lista sale vacía retorna error "No hay módulos habilitados para virtualización en este plan"
GitHub
. Esto corresponde al mensaje descrito "este módulo aún no está habilitado" cuando un alumno intenta iniciar un curso y el profesor no habilitó nada. Por último, mencionar que en la interfaz hay redundancia en la habilitación: el checkbox de habilitar módulo aparece tanto en la sección de gestión de contenido (lista de módulos del plan) como en la herramienta de generación de contenido IA para el profesor. En ambos casos, marcan el mismo flag ready_for_virtualization vía la API
GitHub
GitHub
. Esta duplicación puede ser confusa y, según se indica, estaría fallando en algún lugar. Es posible que al habilitar en una vista no se refleje inmediatamente en la otra sin recargar, o que haya dos mecanismos distintos intentando lo mismo. Una recomendación menor aquí sería unificar la experiencia: idealmente habilitar módulos solo en la vista de plan de estudios, y en la vista de generación mostrar qué módulos están habilitados (checkbox read-only o indicador), para evitar confusiones. El código de la lista de módulos muestra cómo se actualiza el estado local inmediatamente tras togglear
GitHub
, aplicando un toast de éxito
GitHub
; en la otra vista (TopicGenerations) también se lanza un toast y se recarga la lista de módulos tras togglear
GitHub
GitHub
. Pudiera haber casos de sincronización en que un cambio no llegue a reflejarse en el otro panel sin actualizar datos.
Lógica de Generación Progresiva de Módulos Virtuales
Una vez hay al menos un módulo habilitado, el alumno (o el profesor en su nombre) puede iniciar la generación de módulos virtuales personalizados. En la API existe la ruta POST /api/virtual/progressive-generation que desencadena la generación progresiva inicial para un plan y estudiante dados
GitHub
. Esta ruta implementa la lógica de “dos módulos por delante” en el recorrido de un curso:
Validaciones iniciales: Confirma que el estudiante existe y que el plan de estudios existe (y está asignado a la clase del estudiante, si aplica)
GitHub
GitHub
. También comprueba que haya al menos un módulo habilitado (ready_for_virtualization=True) en ese plan
GitHub
, como mencionamos. Si no, aborta con error indicando que no hay módulos disponibles.
Selección de módulos pendientes: Obtiene la lista de módulos habilitados del plan y filtra aquellos que ya tengan un módulo virtual generado para este estudiante (por si el alumno ya había iniciado antes). Los que aún no se generaron se consideran pendientes
GitHub
.
Encolado de los primeros módulos: De esos pendientes, toma un batch inicial de hasta 3 módulos (usa batch_size = min(3, len(pending_modules)))
GitHub
. La idea de permitir hasta 3 es para cubrir el caso donde idealmente queremos 2 módulos por delante del que cursa el alumno. Al inicio, el alumno no cursa ninguno aún, así que darle 3 significa: generar módulo 1 inmediatamente y tener módulo 2 y 3 preparados por adelantado. Si solo hubiera 1 o 2 módulos habilitados, pues se encolarán solo esos. Cada módulo en este lote inicial se ingresa en una cola de tareas mediante enqueue_generation_task, asignándole prioridades 1, 2, 3 respectivamente
GitHub
GitHub
. Queda entonces una cola de generación con tareas del tipo "generar módulo X para estudiante Y".
Generación inmediata del primer módulo: Para mejorar la experiencia (y dado límites de tiempo en entornos serverless), el endpoint trata de generar de inmediato el primer módulo encolado, en lugar de esperar a un procesador asíncrono. Llama a fast_generator.generate_single_module para el primer módulo con un timeout de ~35 segundos
GitHub
. Esta función efectivamente crea el módulo virtual y sus temas para el estudiante (veremos detalles abajo). Si la generación inmediata tiene éxito, el código marca la tarea como completada en la cola y devuelve al cliente el resultado del módulo generado
GitHub
GitHub
. De esta manera, cuando el alumno inicie el curso, ya tiene el Módulo 1 listo inmediatamente, y sabe que los módulos 2 y 3 están en proceso (o en cola) para más adelante.
Devolver estado inicial: La respuesta de este endpoint incluye la lista de tareas encoladas, el resultado inmediato (ID del módulo virtual 1 generado) y un resumen del estado de la cola (cuántos pendientes, procesando, completados)
GitHub
. Por ejemplo, si había 5 módulos habilitados, encolará los primeros 3 (1 generado, 2 y 3 pendientes). Quedarán aún 2 módulos pendientes que no se encolaron todavía; total_pending_modules reflejará cuántos módulos habilitados quedaron sin encolar (en este ejemplo, 2)
GitHub
.
Con esto, el alumno inicia cursando el Módulo 1 virtual y sabe que el 2 y 3 vienen en camino. Ahora, la siguiente parte de la progresión es asegurar que siempre haya dos módulos listos por delante del que está cursando. Esto lo maneja la ruta POST /api/virtual/trigger-next-generation, que el front-end llama cuando el alumno alcanza cierto progreso en el módulo actual. Según el código, este trigger se debe invocar cuando el progreso del módulo actual supere el 80%
GitHub
GitHub
. En ese punto:
Verifica el progreso mínimo: Si por error se llamara con <80%, rechaza la solicitud.
Identifica el siguiente módulo habilitado no generado: El sistema mira todos los módulos del plan que estén habilitados (ready_for_virtualization=True), ordenados por orden de creación (que debería corresponder al orden lógico del plan)
GitHub
. Luego filtra cuáles de esos ya tienen módulo virtual generado para el alumno
GitHub
. El primero de la lista habilitada que aún no se haya generado se toma como next_module
GitHub
. Si no encuentra ninguno (es decir, ya se generaron todos los habilitados), responde con has_next: False indicando que la generación progresiva está completa
GitHub
 (no quedan más módulos por preparar por ahora).
Encola la generación del siguiente módulo: Si encontró un módulo siguiente, entonces crea una nueva tarea en la cola de generación (task_type = "generate") para ese módulo, con prioridad alta (2) porque fue activado por progreso del alumno
GitHub
GitHub
. Marca en el payload que fue desencadenada por progreso (para trazabilidad). La tarea se agrega exitosamente y se devuelve al front-end la información del módulo siguiente en cola (su ID, nombre y el ID de la tarea) junto con el estado actualizado de la cola
GitHub
GitHub
. Así el alumno sabe que, por ejemplo, al terminar ~80% del Módulo 1, ya se puso en marcha la generación del Módulo 4, manteniendo de nuevo dos módulos por delante (en ese momento tendría quizás módulo 2 y 3 ya listos, cursando el 1; luego de desencadenar, módulo 4 en cola, con 2 y 3 disponibles, etc.). En caso de error al encolar, respondería con error (pero normalmente no ocurrirá).
Con este mecanismo, siempre que el profesor haya habilitado suficientes módulos, el alumno irá liberando el siguiente a medida que avanza. Si el alumno llega a un punto donde no se puede generar más porque el profesor no habilitó el próximo módulo, la respuesta de trigger va a indicar que no hay más (lo cual en la app se reflejará como un mensaje de “no hay más módulos disponibles por ahora”). Esa situación corresponde a "si me toca pasar al módulo 4 y el profesor no lo ha habilitado, el sistema me da un mensaje y no genera más hasta que esté habilitado". Tan pronto el profesor marque listo ese módulo (por ejemplo la semana siguiente), el alumno podrá intentar de nuevo y entonces trigger-next-generation encontrará ese módulo y lo encolará/generará. En resumen, la progresión a nivel módulos está implementada y sincroniza el avance del alumno con la publicación de contenido por el profesor. Cabe destacar que la generación de los módulos en cola (los que no fueron hechos inmediatamente) la atiende el endpoint POST /api/virtual/process-queue. Este endpoint está pensado para ser llamado automáticamente (por un worker o webhook cron) y procesar, de a 1 o 2, las tareas pendientes en la cola
GitHub
GitHub
. Por cada tarea pendiente, marca su estado como "processing" y ejecuta según el tipo de tarea:
Para tareas generate: invoca nuevamente fast_generator.generate_single_module de manera similar, con un timeout de ~40s
GitHub
. Si genera con éxito, marca la tarea como completada y guarda en ella el virtual_module_id generado
GitHub
GitHub
. Si falla, marca la tarea como fallida con el mensaje de error
GitHub
GitHub
.
Para tareas update (que serían actualizaciones incrementales de contenido, discutidas más adelante), actualmente no hay lógica implementada: el código las marca completadas inmediatamente sin hacer nada
GitHub
. (Esto evidencia que la parte de actualizaciones por cambios de contenido aún no está desarrollada).
El endpoint de procesamiento de cola devuelve cuántas tareas procesó y cuántas fallaron, etc., y ocasionalmente limpia tareas muy antiguas de la cola
GitHub
GitHub
. La arquitectura de cola es útil para entornos serverless donde no se pueden ejecutar procesos largos en la petición del alumno; aquí se delega a un mecanismo asíncrono que puede ser llamado periódicamente. Generación interna de módulos y temas: La función FastVirtualModuleGenerator.generate_single_module es la que efectivamente crea los documentos en la base de datos para un módulo virtual y sus temas. En el pseudocódigo de más arriba ya vimos su uso, pero veamos detalles relevantes de su implementación:
Comprueba si ya existe un módulo virtual para ese alumno y módulo original (para no duplicar)
GitHub
.
Obtiene el módulo original y el perfil cognitivo del alumno (si existe en la colección de usuarios)
GitHub
.
Arma los datos para el nuevo módulo virtual: copia el nombre y descripción del original, referencia al plan de estudios original, adapta con el perfil cognitivo y marca generation_status: "generating" y progreso 50%
GitHub
GitHub
. Añade también el module_id del original
GitHub
.
Inserta el VirtualModule en la colección y luego llama a _generate_virtual_topics_fast para crear los temas virtuales
GitHub
.
La función _generate_virtual_topics_fast(module_id, student_id, virtual_module_id, cognitive_profile, remaining_time) realiza lo siguiente:
Recupera todos los topics del módulo original de la DB
GitHub
 (aquí es donde actualmente no filtra por estado del tema, simplemente hace find({"module_id": module_id})).
Calcula cuántos topics por segundo puede generar con el tiempo disponible (por simplicidad, distribuye el tiempo entre los temas)
GitHub
.
Itera cada topic original:
Si queda muy poco tiempo (remaining_time <= 5s), rompe el bucle para no pasarse de tiempo
GitHub
.
Prepara los datos de un VirtualTopic: referencia a virtual_module_id, student_id, título (nombre del topic), adaptaciones (perfil cognitivo y un ajuste de dificultad rápido según el perfil)
GitHub
GitHub
. Pone status "active", progress 0.0 y timestamps.
Inserta el VirtualTopic en virtual_topics
GitHub
.
Luego llama a _generate_basic_content_from_templates(topic_id, cognitive_profile, virtual_topic_data) para generar contenido básico para ese tema virtual
GitHub
.
Decrementa el tiempo restante conforme al cálculo de tasa
GitHub
.
(Si alguna excepción ocurre, logea error pero no hay handling específico por ahora)
GitHub
.
Esa función _generate_basic_content_from_templates y la de cálculo de dificultad interna _calculate_quick_difficulty_adjustment generan contenido inicial muy básico (probablemente plantillas predefinidas o textos genéricos) acorde al perfil cognitivo
GitHub
GitHub
. Por ejemplo, siempre incluye al menos texto, y luego puede agregar un diagrama, un resumen, etc., dependiendo de si el alumno es visual, auditivo, etc
GitHub
GitHub
. Si encuentra contenido existente en topic_contents del tipo requerido, prefiere vincularlo en vez de generar nuevo; esto se ve en el código de generate_personalized_content: para cada tipo seleccionado, busca si ya hay un TopicContent que coincida (por ejemplo, un diagrama ya creado por el profesor)
GitHub
. Si existe, simplemente inserta un documento en virtual_topic_contents apuntando al contenido existente
GitHub
GitHub
. Para diagramas incluso, decide no crear nuevos si no había, simplemente omite si no hay uno existente (para evitar múltiples diagramas)
GitHub
GitHub
. Si no existe contenido de ese tipo, entonces crea uno nuevo “generado” — en la implementación actual, esto es simulado poniendo un texto placeholder en el campo content indicando que fue generado
GitHub
GitHub
, lo inserta en topic_contents y luego lo vincula al tema virtual
GitHub
. Esta lógica hace que el módulo virtual tenga una variedad de contenidos (hasta 5 tipos diferentes máximo) combinando lo que ya hubiera en el tema con contenidos sintéticos. Es una funcionalidad de auto-completar contenido que aún es bastante básica (no integra realmente una IA generativa, aunque podría en el futuro usando prompts). Limitación: Dado que _generate_virtual_topics_fast genera todos los temas de un módulo de golpe, no implementa la idea de “temas progresivos dentro de un módulo”. La narrativa original sugería que dentro de un mismo módulo también se liberaran los temas gradualmente (si hay 5 temas, generar 2 primero, luego a medida que completa uno generar el siguiente, etc.). Actualmente, no hay una mecánica equivalente de cola para temas individuales. Todos los temas virtuales de ese módulo se crean en lote. Sin embargo, se podría emular cierto progresivismo en la presentación al estudiante: es decir, aunque estén creados los 5 temas virtuales, la interfaz podría inicialmente mostrar solo el primero (o los primeros 2) y mantener los siguientes “bloqueados” hasta que el alumno avance. Para soportar esto mejor, quizás el modelo de VirtualTopic debería tener un campo de estado (e.g. locked=True/False). Por ahora tiene completion_status (not_started, in_progress, completed)
GitHub
, que se usa para seguimiento pero no indica bloqueo. Una posibilidad es reutilizar ese campo o status para distinguir temas aún no accesibles. En el estado actual del backend, esta lógica no existe; todos los VirtualTopics de un módulo virtual quedan con status "active" y se devolverían en la API de obtención de temas virtuales sin distinción
GitHub
. En síntesis, la progresión implementada es a nivel de módulos completos. Dentro de cada módulo, la generación es completa y no escalonada, aunque la intención descrita sugiere que debería serlo. Abordaremos esto en las recomendaciones, ya que implicaría cambios tanto de modelo (flag por tema) como de lógica (generar temas on-demand).
Actualización de Contenido y Sincronización en Módulos Virtuales
Un aspecto crítico mencionado es: “si se actualiza un contenido o un recurso, automáticamente se debe actualizar en los módulos virtuales”, lo cual "aún no pasa". Efectivamente, el sistema tiene planeado un mecanismo de actualizaciones incrementales que aún no está completo. En el backend vemos una clase ContentChangeDetector que se importa en las rutas virtuales
GitHub
. La idea es que cuando el profesor modifica algo en un módulo (por ejemplo, actualiza la teoría de un tema, añade un recurso, cambia la dificultad), el sistema detecte cambios y encole tareas de tipo "update" para aplicar esos cambios a los módulos virtuales ya generados. Por ejemplo, en la ruta virtual_bp.route('/modules/<virtual_module_id>/incremental-update', PUT) (expuesta en el servicio frontend
GitHub
), se podría recibir datos de cambios y actualizarlos. Más claramente, en la ruta de notificación de cambios (posiblemente dentro de ContentChangeDetector), tras detectar cambios se llama a schedule_incremental_updates(module_id, change_info) para programar tareas de actualización. Estas tareas 'update' entran a la misma cola de generación con la idea de ser procesadas por process-queue. De hecho, en process_generation_queue, hay un branch para task_type == "update" que actualmente solo marca la tarea como completada sin ninguna lógica
GitHub
. Esto significa que la infraestructura está ahí (cola, tasks) pero la implementación concreta de cómo propagar los cambios no se realizó aún. Implicaciones: Si un profesor corrige un error en el contenido de un tema (por ejemplo, actualiza una definición en el texto teórico), los alumnos que ya hubieran generado ese tema virtual no verán automáticamente el cambio. Sus VirtualTopicContents siguen apuntando al contenido antiguo. Ahora bien, recordar que si el VirtualTopicContent fue vinculado a un TopicContent original (caso frecuente si el contenido existía), podría reflejar cambios si el contenido original se edita en lugar de reemplazarse. Por ejemplo, si el contenido teórico está guardado en topic_contents y el VirtualTopicContent guarda content_id apuntando a ese mismo documento
GitHub
GitHub
, entonces una edición en ese TopicContent podría reflejarse automáticamente en todos los virtuales (porque apuntan al mismo objeto). Habría que confirmar si el flujo de edición de teoría modifica el campo dentro de topics o crea un topic_content. El modelo Topic tiene theory_content embebido
GitHub
, que probablemente se llena de texto. Ese contenido teórico suele duplicarse en la generación? Observando generate_personalized_content, parece que no transfiere explícitamente theory_content a ningún VirtualTopicContent (aunque en _generate_virtual_topics_fast, cuando genera el string para IA, concatena topic.get('theory_content', '') para usarlo de contexto
GitHub
). Esto indica que la teoría del tema original no se guarda como un VirtualTopicContent separado, sino que se podría esperar que el alumno la vea directamente del campo theory_content del VirtualTopic (o posiblemente esté incrustada como un contenido de tipo texto en virtual_topic_contents si la IA generó un resumen). Actualmente, no vimos en el código una inserción que copie theory_content a virtual_topic_contents, por lo que quizás el front-end al mostrar un tema virtual combine la teoría original con los contenidos virtuales generados. Dado este panorama, es necesario reforzar la sincronización de contenidos. Recomendamos implementar las siguientes mejoras:
Cuando el profesor edite un TopicContent (p. ej. actualice un video o un texto existente), actualizar todos los VirtualTopicContent vinculados a ese contenido (si fueron copiados, reemplazar su adapted_content; si fueron referenciados, probablemente ya estén al día salvo que se haya creado una nueva versión).
Si el profesor agrega un nuevo recurso o contenido a un tema ya virtualizado por alumnos, quizás notificar o generar una tarea para insertar ese contenido faltante en los VirtualTopics correspondientes.
Aprovechar la arquitectura de cola: por ejemplo, ContentChangeDetector podría comparar una huella (hash) del contenido de un módulo con otra previa, determinar qué temas cambiaron y encolar tasks 'update' por cada virtual module afectado con un payload que indique qué tema o contenido cambió. Luego, en process-queue, implementar la lógica para cada tarea 'update': esto podría buscar todos los virtual_topic_contents de ese módulo virtual que correspondan al contenido modificado y actualizarlos. En ausencia de un diseño de versionado de contenido, una aproximación simple es: invalidar o borrar los VirtualTopicContents afectados y volver a generarlos como nuevos (posiblemente usando la misma función generadora pero solo para ese tema).
Un detalle: el modelo VirtualModule tiene un campo updates (lista) para registrar cambios aplicados y un last_generation_attempt
GitHub
GitHub
, lo cual sugiere que se pensó en anotar las actualizaciones incrementales (por ejemplo, "se agregó contenido X posteriormente"). Actualmente no vimos código que llene updates, pero tenerlo es útil para historial.
En resumen, hoy por hoy el sistema no refleja automáticamente los cambios de contenido en los cursos ya generados. Es una funcionalidad incompleta. Implementarla evitará la divergencia entre lo que el profesor ve (contenido actualizado) y lo que el alumno ve en su módulo virtual (contenido antiguo). Será clave para mantener los módulos virtuales vivos y actualizados conforme evoluciona el contenido original.
Complejidad del Modelo Actual y Oportunidades de Refactorización
Tanto en el backend como en el frontend se nota que el modelo de datos y la lógica de negocio se han ido extendiendo y unificando, pero aún hay áreas complejas o redundantes que podrían simplificarse:
Unificación de Quizzes y Evaluaciones: Actualmente coexisten las Evaluaciones (estáticas, parte del plan de estudios) y los Quizzes interactivos (parte de la capa virtual). Un quiz es esencialmente un tipo especial de contenido interactivo evaluativo. Se podría eliminar el modelo separado de Quiz y manejarlo como un TopicContent de tipo "quiz" o "assessment" dentro de un Tema. Por ejemplo, el profesor crea una evaluación con preguntas, eso genera internamente un TopicContent (u objeto similar) en el tema, y cuando se virtualiza, ese contenido se personaliza como cualquier otro. Los resultados de ese quiz podrían entonces guardarse en ContentResult en lugar de tener QuizResult aparte. La presencia de Evaluation.use_quiz_score muestra que ya hay un puente; dar un paso más permitiría que una Evaluación se represente 100% como un contenido interactivo. Esto simplificaría las colecciones: podríamos prescindir de virtual.quizzes y virtual.quiz_results y reducir lógica duplicada de manejo de preguntas, consolidándolo con la lógica de contenidos interactivos.
Modelos Virtuales vs. Estáticos: Si bien separar las colecciones estáticas (planes, módulos, temas, contenidos) de las virtuales (virtual_modules, virtual_topics, virtual_topic_contents) tiene sentido por claridad, hay cierta duplicación de información. Por ejemplo, un VirtualTopic almacena nombre y descripción que son copias del Topic original
GitHub
, y VirtualModule copia nombre/desc del módulo. Esto puede ser necesario para independizar en caso de que luego se quiera permitir divergencia (contenido adaptativo diferente), pero en muchos casos se podría simplemente referenciar y no duplicar campos. Una alternativa de diseño sería que VirtualTopic referencie al Topic original y solo contenga campos adicionales (p. ej. progreso del alumno). Sin embargo, eso complica consultas (tendría que hacer join manual con la colección de topics para cada fetch). La decisión de duplicar fue probablemente para tener documentos autocontenidos para la API (sin tener que consultar la colección original). Dado que MongoDB no hace joins fácilmente en REST, está bien duplicar algunos campos denormalizados. No obstante, se podría considerar eliminar campos redundantes como description si no se usan realmente en la vista del alumno, reduciendo tamaño.
Contenido estático vs. virtual: Actualmente, hay dos colecciones: topic_contents (contenido maestro creado por docentes) y virtual_topic_contents (contenido personalizado generado o referenciado para alumnos). Una idea agresiva de simplificación sería combinarlas en una sola colección de contenidos, distinguiendo con un campo si es global (para todos) o personalizado (para un alumno). Por ejemplo, añadir student_id opcional en TopicContent: si es null, es contenido general del tema; si tiene un ID, es un contenido generado para ese estudiante. También un campo virtual_topic_id opcional para vincularlo directamente a un tema virtual. Esto permitiría buscar contenidos de un tema (tanto globales como los del alumno) en una sola consulta. Sin embargo, complicaría un poco la separación lógico/permiso (habría que filtrar por student_id null o específico según corresponda). La aproximación actual de colecciones separadas está bien por claridad. Quizás lo que se puede simplificar es la estructura interna de VirtualTopicContent: actualmente guarda campos como adapted_content (posible contenido modificado) que muchas veces es None (usando el original)
GitHub
. Podría simplificarse almacenando siempre un documento completo de contenido (como una copia) en vez de referencias + adaptaciones por separado, aunque eso sacrificaría la referencia única a contenido original. Dado que ya unificaron juegos/simulaciones/quizzes en TopicContent, esta parte está bastante optimizada.
Recursos vs. Contenido: Mencionaste que “algunos recursos se convierten en contenido para poder ser usados, algunas evaluaciones se convierten en recursos”. Esto apunta a la idea de homogeneizar todos los materiales. Por ejemplo, un video de YouTube inicialmente podría haberse tratado como un recurso externo, pero para integrarlo en la experiencia del alumno es mejor considerarlo un contenido multimedia incrustado. Entonces ese recurso se transforma en un TopicContent de categoría "video". De igual forma, se podría pensar que una Evaluación tradicional (un trabajo escrito, por ejemplo) se represente en la plataforma como un recurso descargable (una hoja de preguntas) que el alumno sube luego - es decir, la evaluación en sí actúa como recurso. Actualmente, las evaluaciones tienen su propio modelo y pueden vincular EvaluationResource (por ejemplo una plantilla o guía)
GitHub
. Simplificación posible: Tratar también las evaluaciones como un tipo de contenido (p. ej. un contenido de tipo "assignment" con peso y criterios). En la práctica, las evaluaciones suelen requerir calificación manual, pero se podría registrar su entrega como ContentResult también. El beneficio de unificarlo sería tener toda la secuencia de aprendizaje (teoría, práctica, evaluación) como contenido interactivo en la interfaz de alumno, en lugar de manejar secciones separadas.
Reducir redundancia en el Frontend: La existencia de dos interfaces para habilitar módulos (en Panel de Plan vs. Generación de Contenido) sugiere que se podrían fusionar o al menos reutilizar componentes. De hecho, vemos que ambos usan un componente Checkbox similar y llaman a setVirtualizationSettings en el servicio
GitHub
. Consolidar esto evitaría problemas de que esté “dos veces”. Quizá se podría eliminar el toggle de la vista TopicGenerations y solo mostrar el estado, para forzar que el profesor habilite módulos desde el panel principal (donde también puede ver las sugerencias de readiness y el porcentaje de completitud). Así se evita confusión.
Estructura de Presentación Unificada: En la descripción final señalaste el deseo de que “todo el tema fuese como un juego o diapositiva”, con todos los contenidos integrados en un formato interactivo tipo slider. Esto es más una refactorización de frontend/UX, pero tiene impacto en cómo se modelan los contenidos: significa que en lugar de presentar al alumno una lista de recursos (por ejemplo, una sección de texto, luego un enlace a video, luego un juego separado), se le presentaría una sola experiencia unificada donde va pasando “pantallas” o “láminas” con distintos tipos de contenido embebidos. Esto es muy interesante porque mejoraría la inmersión y motivación. Para lograrlo:
Podríamos definir un tipo de contenido “Slide” o simplemente usar la ordenación existente: cada TopicContent tendría un orden secuencial. El front podría renderizar secuencialmente los contenidos de un tema según ese orden, cada uno ocupando pantalla completa como slide. Por ejemplo, orden 1: texto introductorio, orden 2: video de YouTube (incrustado en un player dentro de la “diapositiva”), orden 3: juego HTML5 incrustado (esto requeriría que los juegos/simulaciones se puedan ejecutar embebidos; quizás usando un <iframe> con la URL del juego generado o un canvas), orden 4: un cuestionario.
Para integrar un diagrama o simulación en la “lámina”, se puede, como dices, incrustarlo en un frame interno. Dado que los contenidos interactivos están definidos por plantillas (ContentTemplate con código HTML/JS, etc.)
GitHub
GitHub
, es factible renderizarlos dentro de un contenedor en la página.
Los videos de YouTube se podrían presentar con su reproductor incrustado ya que se tiene la URL (quizá están en web_resources de TopicContent).
Los juegos, si son HTML5, podrían integrarse en un <iframe> o contenedor especializado. Si son externos, similar.
En esencia, todos los tipos de contenido se convierten en “páginas” de una macro-diapositive. Esto requiere en frontend un componente que recorre los contenidos de un tema como un carrusel.
Con este enfoque, se puede hacer que el alumno sienta que progresa dentro de un mismo flujo interactivo. Además, se podría gamificar: por ejemplo, se podría mostrar un mini-mapa o índice de slides, con secciones bloqueadas hasta completar la anterior (lo cual conecta con la idea de progresión dentro del tema). Para implementarlo de modo flexible, habría que garantizar que cada TopicContent tenga suficiente información para renderizarse autónomamente en una slide. Esto ya es así (tiene content_data, tipo, etc.). Quizá haría falta un campo en TopicContent para marcar la secuencia (un simple order o usar el existente tags/tipo). En VirtualTopicContent igualmente se preservaría el orden. Un beneficio de este método es que el contenido teórico principal del tema (que hoy está en Topic.theory_content) podría ser tratado como simplemente el primer TopicContent del tipo "texto"/"presentación". Sería conveniente migrar esa teoría a un TopicContent con content_type "text" o "slide" para seguir el mismo flujo, en vez de manejarlo aparte. Esto unificaría aún más el modelo: todo lo que ve el alumno es un TopicContent. De hecho, en generate_personalized_content, al no encontrar suficientes tipos, el sistema se asegura de añadir contenido básico de texto/diagrama
GitHub
. Podría mejorarse haciendo que siempre se genere o incluya la teoría original como primer contenido.
En síntesis, las recomendaciones de refactorización y simplificación son:
Tratar quizzes como contenidos interactivos, integrándolos con el modelo de contenido y resultados unificado, reduciendo modelos separados.
Introducir un indicador de estado a nivel Tema para soportar habilitación parcial (que el profesor pueda marcar qué temas de un módulo están listos). Esto podría ser un campo booleano en Topic (ej. published=True). El sistema de generación usaría eso para filtrar temas a generar y podría permitir marcar un módulo ready_for_virtualization incluso si no todos los temas lo están (generando solo los publicados). Alternativamente, limitar la generación inicial a 1-2 temas y necesitar llamada para generar siguientes (similar a trigger de módulos).
Completar la funcionalidad de actualizaciones incrementales: implementar en las tareas 'update' la lógica para sincronizar cambios de contenido y recursos a los módulos virtuales (como se discutió, puede implicar regen de ciertos contenidos o al menos notificar al alumno que hay contenido nuevo disponible en su curso).
Simplificar la interfaz de habilitación de módulos, evitando duplicación de toggles en múltiples pantallas. Una sola fuente de verdad en UI reducirá errores. Por ejemplo, consolidar la acción en PanelPlans y en TopicGenerations simplemente observar ese estado.
Avanzar hacia una presentación unificada por slides de los contenidos de cada tema. Esto es más de frontend, pero influye en asegurar que los datos estén estructurados secuencialmente. Posiblemente agregar campo order en los contenidos (si no existe) y migrar theory_content a un contenido tipo texto para poder incluirlo en la secuencia.
Posible reducción de modelos: Evaluar si VirtualTopic y VirtualTopicContent pueden fusionarse. Actualmente cada VirtualTopic agrupa múltiples VirtualTopicContents. Podríamos anidar una lista de contenidos dentro del documento de VirtualTopic (MongoDB permite arrays de subdocumentos). Esto eliminaría una colección entera y haría más sencilla la obtención de todo el contenido de un tema virtual de golpe. Sin embargo, perderíamos cierta flexibilidad de consultas directas sobre contenidos (aunque rara vez se consulta un VirtualTopicContent aislado sin contexto de su tema). Es una decisión de diseño: menos colecciones significa menos operaciones de join manual en la aplicación. Dado que un VirtualTopic siempre se consulta junto con sus contenidos para mostrarse al alumno, podría tener sentido almacenarlos juntos. Trade-off: mantenerlos separados facilita reusar contenidos iguales en varios lugares, pero en este caso cada VirtualTopicContent es único a un estudiante, así que no hay reuso entre distintos VirtualTopics (solo comparten referencia al original quizás). Incluirlos dentro de VirtualTopic podría ser viable.
De manera análoga, podríamos considerar guardar los resultados como parte del VirtualTopicContent o VirtualTopic. Actualmente ContentResult es colección separada, pero si quisiéramos menos fragmentación, podríamos anidar un histórico de resultados dentro de cada VirtualTopicContent (por ejemplo, una lista de intentos del alumno en ese contenido). Eso hace más complejo el documento y el manejo de concurrencia, así que quizá dejar resultados separados está bien.
En conclusión, el sistema en su estado actual funciona pero es complejo, con muchas piezas que interactúan. Hay evidencia de mejoras en curso (unificación de contenidos, cola de generación, adaptaciones por perfil), pero también de código incompleto (actualizaciones no implementadas, progresión por temas no realizada). Las refactorizaciones propuestas buscan:
Simplificar el modelo de datos (unificar donde hay duplicación innecesaria).
Mejorar la consistencia de la lógica de negocio (p. ej. garantizar que no se generen contenidos sin habilitar).
Enriquecer la experiencia del usuario (presentación integrada tipo juego/diapositiva).
Facilitar el mantenimiento futuro (menos modelos especiales como Quiz, menos puntos de fallo con toggles duplicados).
Al implementar estas recomendaciones, se deberá hacer con cuidado de no perder datos existentes (por ejemplo, migrando quizzes existentes a contenidos, o actualizando la estructura de documentos virtuales). Igualmente, habrá que ajustar el frontend para alinearse con los cambios en los endpoints o modelos. Para resumir: El sistema de módulos progresivos es innovador y avanzado en funcionalidades (personalización por perfil cognitivo, generación dinámica de contenido, liberación progresiva según avance del alumno), pero tiene áreas por completar. Actualmente, la progresión por módulos está implementada (siempre 2 módulos adelante)
GitHub
GitHub
, aunque la progresión dentro de un módulo no lo está. La relación entre elementos (planes, módulos, temas, recursos, contenidos) se ha simplificado bastante con modelos unificados de contenido
GitHub
, pero se puede refinar más (quiz como contenido, evaluación como contenido). La sincronización de cambios profesor-alumno aún es manual (no automática) pero hay cimientos para hacerla automática en breve
GitHub
. Adoptando las mejoras sugeridas, el sistema podrá entregar una experiencia más coherente y sencilla: con menos entidades conceptuales para el desarrollador (todo es contenido, todo produce un resultado), y para el usuario final, un recorrido de aprendizaje continuo donde cada tema es presentado como una narrativa interactiva única, sin saltos ni secciones desconectadas. Todas estas optimizaciones contribuirán a que la plataforma Sapiens sea más mantenible, eficaz y cercana a la visión pedagógica deseada.