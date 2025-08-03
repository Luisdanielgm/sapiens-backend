Análisis Integral de Requerimientos y Plan de Implementación
1. Requerimientos Completos del Sistema
A continuación se enumeran todas las características y políticas deseadas para la plataforma SapiensIA, según la descripción del proyecto:
•	Módulos Virtuales y Contenidos Personalizados: El sistema debe permitir generar módulos virtuales para cada estudiante a partir del plan de estudio de un curso. Cada módulo virtual contiene temas virtuales con contenidos personalizados para el alumno. Es requisito que cada tema tenga varios tipos de contenido (texto, diapositivas, video, quiz, juego, etc.) antes de poder virtualizarse. La virtualización es individual por alumno: cuando el estudiante inicia un módulo, el sistema crea sus contenidos virtuales personalizados. La generación es progresiva: al crear un módulo virtual, se generan inicialmente el contenido del primer tema y se preparan en cola los dos temas siguientes. Así, siempre debe haber dos temas por adelantado listos para que el alumno no tenga que esperar[1][2]. Si el estudiante avanza al segundo tema, el sistema genera en segundo plano el cuarto tema, manteniendo dos en cola, y así sucesivamente. Un alumno solo espera la primera vez (mientras se generan los 3 primeros temas); luego, el sistema asegura la cola de contenidos. Si no existen más temas publicables (ej. el profesor no ha terminado el tema 3), el alumno no podrá avanzar y se le indicará que espere a que se publiquen más contenidos.
•	Contenido Virtual vs Contenido Base: Distinguir entre contenido general de un tema (creado por el profesor en el plan de estudio) y el contenido virtual personalizado para el estudiante. Cada contenido base del profesor (modelo TopicContent) sirve como plantilla para generar un VirtualTopicContent específico de cada alumno[3]. Los contenidos virtuales heredan los campos del contenido original (texto, imágenes, preguntas, etc.) y agregan datos de personalización (p. ej. marcadores, adaptaciones para el perfil). Cada interacción del alumno con un contenido genera un ContentResult (resultado individual) asociado. Actualmente, el diseño guarda content_id apuntando al contenido original (TopicContent) en cada resultado, no al contenido virtual, para facilitar estadísticas globales[4]. Es decir, si 5 alumnos realizan el mismo quiz base, se crean 5 ContentResult con el mismo content_id (el ID del quiz base)[4]. Ventaja: esto permite al profesor ver el desempeño promedio en ese quiz a nivel de clase sin esfuerzo adicional. Desventaja: no diferencia variaciones personalizadas del contenido, aunque en principio los “marcadores” de personalización no deberían alterar la esencia evaluativa de un quiz. En general se considera correcto vincular ContentResult al contenido base[4].
•	Tipos de Contenido y Resultados: Se desea ampliar la variedad de tipos de contenido disponibles para abarcar mejor los temas. Actualmente existen tipos como texto teórico (explicaciones Método Feynman), diapositivas, diagramas, videos, quizzes, juegos, simulaciones, etc. Se planea agregar más: por ejemplo, flashcards, ejercicios de programación o matemáticos, mapas mentales, glosarios interactivos, Gemini Live (un contenido conversacional de preguntas y respuestas con IA), entre otros. Cada tipo de contenido tiene su forma de evaluarse o marcarse como completado:
•	Para contenidos informativos (lectura de texto, ver diapositivas, video, audio, infografía, etc.), el criterio de completitud es simplemente que el estudiante lo revise; al terminar, se registra un ContentResult con score 1.0 (100%) por haberlo visto[5].
•	Para contenidos interactivos (juegos, simulaciones, ejercicios), puede asignarse una puntuación base automática (ej. 80%) por participación[6], además de posibles puntajes internos si aplica.
•	Para contenidos evaluativos (quiz, exámenes, proyectos), el resultado depende de las respuestas correctas o la calificación otorgada, por lo que no se auto-completan (score inicial 0 hasta que se corrijan)[7].
•	Estos resultados por contenido se guardan en ContentResult con detalles como puntaje (score 0.0–1.0), retroalimentación (texto de IA o del profesor), métricas (tiempo empleado, intentos) y tipo de sesión (por ejemplo, "content_interaction", "auto_completion", etc.)[4].
•	Perfil Cognitivo y Personalización: El sistema debe adaptar la enseñanza al perfil de aprendizaje de cada estudiante. Hay dos niveles de personalización:
•	Selección de tipos de contenido adecuados al perfil cognitivo: Según el estilo de aprendizaje del estudiante (visual, auditivo, kinestésico, lectura/escritura) y sus necesidades (por ejemplo, TDAH, dislexia), se deben elegir los formatos de contenido más efectivos para él[8]. La idea original es no presentar todos los recursos disponibles de un tema, sino aquellos que mejor se ajusten a su estilo, garantizando a la vez una cobertura completa del tema. Ejemplo: un alumno muy visual podría recibir principalmente infografías, videos y diagramas, mientras que uno lector recibiría texto y diapositivas detalladas. Sin embargo, siempre se debe incluir al menos un contenido teórico completo (texto extenso, video o set de diapositivas) que cubra todo el tema, para evitar huecos de conocimiento[9]. Otros contenidos más específicos (juegos, ejercicios) pueden complementar abordando sub-temas particulares. No se debe dar solo contenidos parciales que dejen porciones del tema sin cubrir[9]. Asimismo, aplicar reglas de balance: por ejemplo, con TDAH preferir contenidos breves e interactivos; con dislexia, ofrecer modo lectura amigable (fuentes especiales o audio); si un perfil es muy auditivo, incluir audio/lectura en voz alta, etc.
•	Personalización interna del contenido: Dentro de cada recurso, pueden existir marcadores de personalización (placeholder del estilo {{nombre}}, {{interes}}) que la IA reemplazará con datos relevantes del estudiante[10]. Por ejemplo, insertar el nombre del alumno, referencias a su contexto (ciudad natal, hobby) o ajustar la dificultad del texto según su nivel. Esta personalización fina busca hacer el contenido más cercano. Debe basarse en el perfil cognitivo, intereses y conocimientos previos del estudiante. Actualmente, el sistema marca en cada contenido qué segmentos son personalizables (personalization_markers almacenados en TopicContent) y envía esa info al frontend[10], donde un hook de React (useContentPersonalization) consulta a la IA para obtener los reemplazos personalizados[11]. Es crucial que el formato de estos marcadores sea consistente entre backend y frontend (segmentos con id y tipo "marker")[10]. Al implementar, se utilizará probablemente un modelo de lenguaje (GPT-4 u otro) pasando como contexto el perfil del estudiante (edad, preferencias, dificultades) para generar sustituciones realistas. (Nota: actualmente estaba simulado con valores dummy)[10].
•	Aprendizaje por Refuerzo del Perfil: Además del perfil cognitivo estático obtenido por test inicial y chat, se planea un motor adaptativo que ajuste el contenido según el desempeño real del alumno. Es decir, usar los resultados (ContentResult) para inferir con qué tipo de recursos aprende mejor cada estudiante. Por ejemplo, si consistentemente obtiene mejores puntajes en quizzes que en juegos, el sistema podría priorizar quizzes en el futuro; si muestra mayor engagement con videos, ofrecer más videos, etc. Esto implica analizar métricas como score promedio y tiempo dedicado por tipo de contenido. Inicialmente, este sistema sería complementario: en vez de excluir formatos, podría añadir más recursos del tipo preferido o mostrarlos primero en la secuencia[12]. Es una funcionalidad avanzada de “aprendizaje del sistema”, pensada para implementarse tras tener suficientes datos de ContentResults.
•	Evaluaciones y Ponderaciones: El sistema maneja evaluaciones formales dentro del plan de estudio (por ejemplo exámenes o trabajos que cuentan para la nota). Existen requisitos complejos para flexibilizar las evaluaciones:
•	Una evaluación en el plan de estudio (por ejemplo Examen Final del Módulo 1) puede estar asociada a uno o varios temas, incluso abarcar un módulo completo o múltiples módulos. Debe existir la posibilidad de vincular una evaluación a varios contenidos o temas, ya que el profesor podría querer evaluar conjuntamente contenidos de distintas unidades. Actualmente, el modelo de plan de estudio asocia evaluaciones a un solo tema o módulo, lo cual es limitado; se necesita rediseñar para soportar relaciones N a N (una evaluación puede cubrir varios temas, y un tema puede tener varias evaluaciones).
•	Cada evaluación tendrá una ponderación (peso en la nota final) definida por el profesor. En la interfaz de generación de contenido del profesor, hay una sección para configurar evaluaciones donde se decide cómo se obtendrá la nota de esa evaluación:
a.	Calificación manual: El profesor evalúa fuera del sistema (por ejemplo, una exposición oral en clase) y luego ingresa la nota manualmente en la plataforma. Para ello, el sistema debe permitir registrar la calificación y feedback manual por estudiante.
b.	Resultado de contenido(s) virtual(es): La evaluación toma automáticamente la nota de uno o varios contenidos virtuales realizados por el alumno. Por ejemplo, si la evaluación “Quiz módulo 1” está vinculada al quiz generado en el tema 3, el sistema debería tomar el ContentResult de ese quiz como nota. Incluso podría promediar múltiples ContentResults si la evaluación abarca varios quizzes/juegos. Hay que decidir cómo vincularlos de forma flexible. Actualmente, un campo booleano use_quiz_score en la evaluación indica si se toma la nota de un quiz asociado automáticamente[13], pero se podría extender a una lista de content_ids cuyos resultados conformen la nota.
c.	Entregable (Proyecto/Tarea): El estudiante sube un archivo (reporte, ensayo, código, etc.) como respuesta a la evaluación, y el profesor lo califica. Aquí entran en juego los recursos del sistema: ya existe un módulo de recursos para subir archivos (PDFs, imágenes, etc.) asociados a temas. Para evaluaciones, necesitaremos manejar dos tipos especiales de recurso:
d.	Recurso de Enunciado/Rúbrica: Material de apoyo que el profesor adjunta a la evaluación para guiar al alumno (ej. un PDF con instrucciones o una plantilla a rellenar, o una rúbrica de evaluación). El sistema debe permitir al profesor subir este archivo y asociarlo a la evaluación (quizás guardándolo como Resource general y luego ligándolo mediante una entidad EvaluationResource con rol "support_material" o "template")[14].
e.	Recurso Entregable: El archivo que sube el alumno con su respuesta. El flujo sería: el alumno realiza la tarea fuera del sistema, luego en la plataforma selecciona la evaluación y sube su archivo (creando un Resource propiedad del alumno y un EvaluationResource con rol "submission")[14]. El sistema debe guardar la fecha/hora de entrega y posiblemente impedir nuevas subidas después de la fecha límite.
f.	Tras la entrega, el profesor debe poder calificarla. Si es manual, revisará el archivo y registrará la nota (idealmente asociada también a ContentResult para unificar el registro de calificaciones). Si se usa evaluación automática con IA (ver siguiente punto), el sistema generará una nota y feedback automáticamente.
•	Estructura de Evaluaciones en el Sistema: Ya existe un modelo Evaluation en backend, con campos como type (quiz, exam, project, etc.), weight (ponderación), flags como use_quiz_score, requires_submission, etc. La plataforma debe soportar CRUD de evaluaciones (crear, editar, eliminar evaluaciones dentro de un módulo) y la calificación centralizada a través de ContentResult (es decir, independientemente del tipo, todas las notas terminan creando un ContentResult para ese estudiante, bien sea automáticamente o mediante registro manual)[15][16]. Esto unifica la lógica de notas.
•	Corrección Automática de Exámenes con IA: Se propone un nuevo módulo para agilizar la calificación de exámenes escritos o trabajos:
•	El profesor podría subir una foto o PDF de un examen manuscrito del alumno. El sistema aplicaría Visión Artificial y NLP para corregirlo automáticamente. Pasos previstos:
a.	OCR (Reconocimiento Óptico de Caracteres): Extraer el texto de la imagen o PDF. Se podría usar una API de Google Vision o Tesseract para obtener el texto plano. Este texto extraído conviene guardarlo en la base de datos, por ejemplo anexarlo al Resource del entregable, para futuras referencias[17].
b.	Evaluación por IA: Tomar el texto del alumno y compararlo con los criterios de evaluación. El profesor debería haber definido una rúbrica o guía de corrección. Esto puede ser estructurado (p. ej., una lista de criterios con puntajes: ortografía vale 10%, contenido X vale 40%, etc.) o simplemente haber proporcionado las respuestas correctas esperadas. Toda esa información se pasaría a un modelo de lenguaje (por ejemplo GPT-4) junto con la respuesta del alumno, pidiéndole que genere una calificación numérica y un feedback detallado[17]. Por ejemplo, un prompt podría ser: "Eres un corrector. Respuesta del estudiante: ... Criterios: ... Evalúa del 0 al 10 y da retroalimentación."
c.	Resultado Automático: El sistema recibe la evaluación de la IA (puntuación y comentarios) y crea un ContentResult para esa entrega con ese puntaje y feedback[18]. Debería marcarse de alguna forma que es una calificación automática (quizá session_type = "auto_grading").
d.	Revisión y Aprobación: El profesor podrá ver la nota propuesta por la IA y el feedback. Debe haber opción de aceptar la calificación tal cual o ajustarla manualmente antes de guardar definitiva. Esto es importante para que el profesor tenga control final (la IA facilita pero no decide en último término).
e.	Flujo en la interfaz: Para el profesor, una vista de “Revisar Entregas” donde para cada alumno que envió algo, se vea la nota IA y botones “Aceptar” o “Modificar”. Para el alumno, una vez corregido, debería poder ver su nota y feedback.
f.	Consideraciones adicionales:
g.	Debe manejarse casos de error: si la imagen es ilegible o el modelo no puede evaluar (p. ej. respuesta vacía), marcar la entrega como “No pudo auto-corregir” para que el profesor intervenga manualmente[19].
h.	Seguridad y asociación: asegurarse de que la imagen que se envía a corregir corresponde al alumno y evaluación correctos, para no mezclar datos.
i.	Tiempo de procesamiento: esto puede tardar varios segundos; conviene que sea asíncrono (p.ej., encolar un job o al menos hacer polling en frontend hasta que el resultado esté listo)[14].
•	Nota: Esta funcionalidad sería un módulo nuevo muy potente, pero no es imprescindible para lanzar el sistema básico. Se planea implementarla en fases avanzadas dado su complejidad.
•	Evaluación Automática de Código: Relacionado con lo anterior, se mencionó la posibilidad de que en tareas de programación, el sistema pueda ejecutar código en un sandbox para validar resultados. Ejemplo: el alumno sube un script Python, el sistema lo ejecuta con entradas de prueba y comprueba si la salida coincide con la esperada. Esto permitiría calificar ejercicios prácticos automáticamente. Sería una extensión interesante para cursos de programación, aunque no estuvo en los requerimientos originales de MVP.
•	Secuenciación Óptima del Contenido (Orquestación): Una vez generados los contenidos de un tema para el alumno, el sistema debe presentarlos en el orden pedagógicamente más óptimo. La idea es que inicialmente se muestren en orden lógico (por ejemplo, teoría primero, luego ejemplos, luego quiz), pero luego se puede refinar ese orden mediante IA. En la implementación actual, el frontend ya hace algo de esto: usa un orquestador (useTopicOrchestrator) que:
•	Fragmenta las diapositivas en láminas individuales (ya que la IA genera todas las diapositivas de corrido en un solo HTML). Se usa un DOMParser para separar cada slide usando la plantilla base generada[20]. Así cada diapositiva se convierte en un fragmento de contenido con su propio identificador, manteniendo la plantilla original para estilos[3].
•	Compone una lista de “átomos de contenido” que incluye esos fragmentos de diapositivas y los demás contenidos (texto, video, quiz, etc.), con resúmenes breves.
•	Llama a un servicio de IA (por ejemplo getAiOrderedSequence) para que reordene esos ítems de contenido de forma óptima[3]. La IA recibe los resúmenes y devuelve un orden sugerido (p. ej., primero fragmento 1 de diapositivas, luego fragmento 2, luego video, etc.). El frontend entonces re-renderiza el contenido según ese orden recomendado, creando una experiencia más dinámica[3]. Si la IA falla o tarda, se mantiene el orden original como fallback.
•	La intención pedagógica es intercalar diferentes formatos: por ejemplo, en vez de mostrar todas las diapositivas seguidas, se podría alternar diapositiva -> video -> diapositiva -> juego, de modo que el estudiante no pierda la atención y refuerce inmediatamente conceptos tras la teoría. Esta orquestación debe garantizar también que todo el contenido finalmente se cubra.
•	Nuevos Tipos de Contenido y Plantillas reutilizables: Dado que generar ciertos contenidos (en especial juegos y simulaciones) puede ser complejo para la IA, se planteó un sistema de plantillas de contenido:
•	Una sección donde el profesor pueda generar y editar juegos/simulaciones de forma aislada (fuera del flujo de generación por tema). Estas creaciones se guardarían como plantillas genéricas en una biblioteca. Por ejemplo, un profesor diseña un juego tipo Angry Birds para enseñar parábolas en física, o un puzzle matemático. Esa plantilla queda almacenada con cierta parametrización.
•	Luego, en la generación de contenido de un tema, en lugar de pedir a la IA un juego desde cero cada vez, se podría reutilizar una plantilla existente adaptándola al contenido específico. Por ejemplo: tomar la plantilla del puzzle matemático y alimentarle un set de problemas del tema actual para generar una instancia de ese juego.
•	Incluso se podría tener un “Marketplace” de plantillas de juegos/simulaciones compartido entre profesores. Un profesor puede publicar una plantilla que creó para que otros la usen en sus cursos[21].
•	Esto mejora la calidad de los juegos (ya que se pueden pulir manualmente) y ahorra recursos de IA. Inicialmente, esta funcionalidad no es prioritaria para el MVP pero está en la visión a futuro.
•	Actualización de Contenido ya Virtualizado: Se debe definir la política para cuando el profesor modifica o añade contenidos en el plan de estudio después de que algunos alumnos ya hayan iniciado sus módulos virtuales. Ejemplos:
•	El profesor agrega un nuevo tipo de contenido a un tema (ej. añade un video que antes no existía). ¿Debería aparecer este nuevo recurso automáticamente a los alumnos que ya pasaron o están cursando ese tema? Posibles enfoques:
o	Si el alumno aún no ha llegado a ese contenido (porque estaba al final y aún no lo ve), se podría insertar en su módulo virtual para que lo tenga disponible antes de completar el tema.
o	Si el alumno ya completó ese tema, tal vez no sea conveniente alterar su historial; podría ofrecerse como material adicional opcional, pero sin forzarle a repetir el tema.
•	El profesor actualiza un contenido existente (corrige un texto, mejora unas diapositivas). Para alumnos que no lo han visto aún, debería reflejarse el cambio (quizá vía una sincronización del VirtualTopicContent). Para quienes ya lo vieron, no se revirtirá su progreso, pero en futuras revisiones podrían ver la versión actualizada.
•	Sincronización de cambios: Necesitamos un mecanismo para detectar cambios en los contenidos originales y aplicarlos a los virtuales. Podría ser al abrir el módulo virtual, el backend compara updated_at de cada TopicContent con la sync_date del VirtualTopicContent y decide si recrearlo o actualizarlo[22]. Hay que ser cuidadosos: si ya se personalizó o reordenó contenido, actualizarlo podría ser complejo (quizá solo si el contenido estaba marcado como “archivado” o no visto).
•	En general, esta actualización dinámica añade complejidad y se puede posponer hasta tener lo esencial estable. Se anota como importante para evitar inconsistencias, pero no urgente para la primera versión funcional[23].
•	Soporte Multi-Workspace para Profesores: Se ha implementado un nuevo modelo de "workspaces" que reemplaza el enfoque anterior de multi-instituto. Este modelo permite a los usuarios, especialmente profesores, gestionar múltiples entornos de trabajo (workspaces) de manera flexible. Cada workspace representa un contexto independiente (por ejemplo, una institución, un proyecto personal o un grupo de clases), y un usuario puede pertenecer a varios workspaces simultáneamente.

Implicaciones y Detalles de Implementación:
- **Refactor de Roles Obsoletos:** Se han eliminado roles obsoletos como INSTITUTE_ADMIN y SYSTEM, simplificando la estructura de permisos. Ahora, los roles se centran en OWNER, ADMIN, TEACHER y STUDENT, aplicados por workspace. Esto reduce complejidad y mejora la escalabilidad.
- **JWT con workspace_id:** El token JWT ahora incluye un campo workspace_id que indica el workspace activo del usuario. Esto asegura que todas las operaciones se filtren automáticamente por el contexto actual, evitando mezclas de datos entre workspaces.
- **Endpoints para Gestión de Workspaces:**
  - **/api/workspaces/switch/<workspace_id>:** Permite a los usuarios cambiar de workspace activo. Al llamar a este endpoint, se genera un nuevo JWT con el workspace_id actualizado, manteniendo la sesión segura.
  - **/api/workspaces:** Lista todos los workspaces a los que pertenece el usuario, facilitando la selección en la interfaz.
- **Migración de Datos:** Se ha realizado una migración para transferir datos existentes de institutos a workspaces. Cada instituto previo se convierte en un workspace, preservando clases, usuarios y contenidos asociados.
- **Interfaz de Usuario:** En el dashboard, se muestra un selector de workspaces. Al cambiar, se actualiza el contexto y se recargan los datos relevantes (cursos, clases, etc.), asegurando que no se mezclen elementos de diferentes entornos.

Esta implementación resuelve las limitaciones previas de multi-instituto, ofreciendo una solución más robusta y flexible para usuarios con múltiples afiliaciones. Inicialmente, se priorizó esta funcionalidad para soportar tanto entornos institucionales como usos individuales.
•	Uso Individual (Suscripción para autodidactas): Se identificó la necesidad de que personas particulares puedan usar la plataforma sin pertenecer a una institución. Por ejemplo, un estudiante autodidacta que quiere crear su propio curso para aprender algo, o un profesor independiente que quiere preparar material para un alumno privado. Actualmente, toda la estructura asume que un estudiante pertenece a un instituto y un curso formal. Para habilitar uso individual:
•	Se puede crear un instituto genérico “Academia Sapiens” que agrupe a usuarios independientes. Al registrarse un usuario particular, podría asignársele automáticamente este instituto.
•	Si es un estudiante individual: Podría actuar como su propio “profesor” en cierto sentido. Una idea es permitirle crear un plan de estudio personal: él ingresa el tema o materia que quiere estudiar (subiendo un documento con temario, o escribiendo una descripción), y el sistema genera los módulos y temas como lo haría para un profesor. En este caso, podríamos tras bambalinas crear un perfil profesor o usar un usuario del sistema que haga de profesor virtual. Alternativamente, darle al estudiante permisos limitados para usar la funcionalidad de generación de contenido. Lo más viable es:
o	Tras registrarse como estudiante independiente, el sistema crea automáticamente una estructura: un instituto “personal”, un curso con un plan de estudio vacío. El usuario entonces carga un documento o especifica la materia que quiere aprender, y el sistema genera el plan (temas) con IA como normalmente se hace para un profesor. Luego genera los contenidos y el alumno obtiene su módulo virtual listo para cursar, siendo él el único alumno y a la vez el que disparó la generación.
o	Otra opción es ofrecer un catálogo predefinido de cursos (ver “Marketplace” abajo) donde el autodidacta simplemente se inscribe para cursarlos.
•	Si es un profesor independiente que quiere usar la plataforma para sus clases particulares: En el registro podría marcar “Profesor particular”. Se le crearía un instituto propio (ej. “Clases de Prof. Juan”) donde él es admin y profesor a la vez. Ahí puede crear cursos y meter a sus alumnos (o compartirles un código de clase). Incluso podría ser también estudiante de sus propios cursos si quisiera ver la perspectiva alumno.
•	Roles duales: Debemos contemplar que una misma persona podría tener rol de profesor y alumno simultáneamente (por ejemplo, un profesor que crea un curso y luego quiere probar él mismo el módulo virtual como si fuera alumno). El sistema debería permitir asignar múltiples roles a un usuario. Una implementación práctica: en la colección InstituteMembers un usuario puede estar como TEACHER y también en ClassMembers como STUDENT de cierta clase (posiblemente de su propia clase)[26]. La interfaz tendría un toggle de modo: modo Profesor vs modo Alumno, para cambiar vistas[26]. Esto es complejo de UX pero manejable: por defecto un independiente entra en modo Profesor para crear su contenido, y luego podría “Iniciar curso como estudiante” que lo lleva a la experiencia de módulo virtual[27]. Internamente, al crear el plan de estudio del profesor individual, se podría automáticamente matricularlo como estudiante en ese plan (clase) para generar su VirtualModule.
•	En resumen, la plataforma debe soportar una modalidad “B2C” además del “B2B” tradicional. Probablemente esto se implementará introduciendo lógica adicional en registro (crear estructuras por defecto) y adaptando permisos.
•	Marketplace de Cursos: Vinculado a lo anterior, se propone un Marketplace público donde cursos completos (planes de estudio con sus contenidos) puedan compartirse o comercializarse:
•	Un profesor (o usuario independiente) podría publicar su curso una vez que lo haya creado. Marcar el plan de estudio como “público” o compartido[28]. Esto lo haría visible en un catálogo para todos los usuarios de SapiensIA.
•	Otros usuarios podrían inscribirse en ese curso aunque no pertenezcan a la institución original. Dos posibilidades de implementación:
a.	Crear módulos virtuales directamente para el estudiante externo basados en ese plan público, sin que este forme parte de la clase original. Esto requeriría permitir en backend la generación de VirtualModules aunque el estudiante no pertenezca al instituto dueño del plan (quizás omitir verificaciones de pertenencia o tener un instituto especial “Public” que todos comparten)[29].
b.	O duplicar el contenido: copiar el plan de estudio público al espacio del nuevo usuario (por ejemplo bajo el instituto “Academia Sapiens” si adoptamos esa idea) y que él lo curse allí. Esto conlleva duplicar datos y puede complicar actualizaciones, así que quizá no.
•	Podría haber cursos gratuitos y de pago. En caso de pago, integrarlo con el sistema de suscripciones/pagos (abajo) para gestionar acceso.
•	Además, un marketplace podría permitir valoraciones, comentarios de estudiantes, etc., aunque eso es secundario.
•	Inicialmente, se puede lanzar sin marketplace, pero tener la arquitectura en mente para más adelante abrir esta funcionalidad.
•	Landing Page y Suscripciones de Pago: Dado que la aplicación será ofrecida en modelo SaaS, se necesita:
•	Un Landing Page público (página de inicio) que presente la plataforma, sus beneficios, testimonios, etc., con opción de registro. Actualmente el inicio de la app es directamente la pantalla de login; esto debe cambiar para que si el usuario no está autenticado vaya a una página marketing (posiblemente en la misma app Next.js como página pública principal). Solo tras hacer clic en “Iniciar Sesión” o “Regístrate” se mostrarán los formularios correspondientes.
•	Planes de suscripción:
o	Plan Institución: orientado a escuelas/colegios. Un representante puede registrar su institución, posiblemente requiriendo un proceso especial (quizás un contacto de ventas, o permitir autogestionar con pago). Este plan probablemente involucra pago por número de alumnos o una licencia institucional.
o	Plan Profesor Particular: para docentes independientes. Un precio más bajo que les dé acceso a crear X cursos y Y alumnos.
o	Plan Estudiante Individual: quizá una suscripción muy económica o incluso modelo freemium, para alumnos autodidactas que acceden a los cursos públicos o crean un curso para sí mismos.
•	Integración de Pagos: No está pensado para MVP inmediato, pero se debería considerar. Lo más común es integrar Stripe:
o	Crear productos/planes en Stripe (por ejemplo, Instituto Mensual, Profesor Mensual, etc.).
o	Al registrarse un usuario de pago, redirigirlo a un Checkout de Stripe. Tras el pago, recibir un webhook de confirmación para activar la cuenta correspondiente[30].
o	Manejar renovaciones, cancelaciones, etc. Esto es complejo y tal vez se posponga hasta tener demanda real. Para una demo inicial, se puede suponer todo gratuito o usar códigos de invitación en vez de pago.
•	En síntesis, preparar la app para multi-tenant con pago: lo cual implica también roles de superadmin (para manejar el marketplace, ver estadísticas globales). Ya se añadieron roles SYSTEM y SUPER_ADMIN en backend para soporte futuro[31].
•	Aplicación Móvil (React Native): Se planea desarrollar una app móvil complementaria. Inicialmente con funcionalidad limitada:
•	Perfil Profesor (Móvil): Enfoque en la corrección de evaluaciones con foto. Es decir, la app permitiría al profesor tomar fotos de exámenes directamente desde el celular y subirlas para corrección automática. Así, en vez de escanear y subir en la web, podría hacerlo cómodamente en clase. La app mostraría la lista de evaluaciones pendientes de calificar, uno selecciona un alumno, abre la cámara, captura la imagen, y envía a la API de corrección[32][33]. Luego podría mostrar el resultado de IA inmediatamente o tras procesar.
•	Perfil Alumno (Móvil): Podría permitirle consumir los módulos virtuales desde el teléfono: ver contenidos, hacer quizzes, etc. Sin embargo, reimplementar toda la experiencia en móvil es mucho trabajo (por ejemplo, mostrar diapositivas interactivas, juegos en móvil, etc.). Quizá inicialmente se opta por una versión simplificada: por ejemplo, permitir ver textos, videos y quizzes (formatos más simples), pero juegos complejos podrían requerir un navegador. Alternativamente, podría incrustarse la web en una WebView dentro de la app, aunque no es ideal.
•	Tecnológicamente se sugiere usar React Native para compartir lógica con la web en lo posible (p. ej., servicios API, definiciones de interfaces). La app usará los mismos endpoints (JWT auth).
•	La app se hará en fases: primero una prueba de concepto con la funcionalidad de captura/corrección, luego se expandirá.
•	Mejoras de UI/UX Transversales:
•	Responsive Design y Dark Mode: Asegurarse que toda la aplicación web sea responsive (usable en pantallas pequeñas) y soportar tema claro/oscuro globalmente. Ya hay componentes con dark mode, pero se debe revisar cada página (login, dashboard, visores de contenido) para corregir estilos (por ejemplo, texto oscuro que no se lee en modo oscuro, o desbordes en móvil)[34][35].
•	Manejo de Errores y Experiencia: Implementar un mecanismo global de errores: por ejemplo, un <ErrorBoundary> en React para capturar excepciones de render y mostrar un mensaje amigable en lugar de pantalla en blanco[34]. Y centralizar la gestión de errores de peticiones fetch: si la API devuelve 401 (no autenticado), hacer logout; 403 (prohibido), mostrar “No autorizado”; 500, mostrar notificación “Error del servidor, intente más tarde”, etc.[34]. Esto mejora la robustez percibida.
•	Eliminar código y archivos obsoletos: Ha habido múltiples iteraciones, por lo que es importante limpiar componentes o servicios duplicados o no usados, para evitar confusión.
•	Fetch con autenticación unificada: Verificar que todas las llamadas a la API desde frontend usen el helper central (fetchWithAuth) para incluir el token y manejar expiraciones. Cualquier llamada directa con fetch debe migrarse para no romper la autenticación.
•	Indicadores y Dashboard: En los dashboards iniciales (profesor y alumno) se muestran métricas como asistencia, rendimiento, progreso, etc. Muchas estaban estáticas o de prueba. Ahora con los ContentResults y evaluaciones, se puede calcular datos reales:
o	Para el alumno: % de progreso en sus módulos (porcentaje de temas completados), calificación promedio en evaluaciones realizadas, quizá racha de días estudiando (número de días consecutivos que ingresó o completó algo).
o	Para el profesor: promedio de calificaciones de la clase en la última evaluación, % de alumnos que completaron X módulos, total de contenidos generados vs completados, etc.
o	Asistencia: Se tenía un widget de asistencia (presumiblemente para marcar asistencia diaria en clases presenciales), pero actualmente no existe funcionalidad para registrar asistencias. Se debe decidir eliminar ese widget o implementarlo. Dado que SapiensIA se centra más en lo virtual, podría omitirse por ahora para no confundir[36]. Otra opción: reinterpretar “asistencia” como participación en la plataforma (ej. ingreso diario) para cursos 100% en línea.
o	Estas estadísticas requerirán nuevos endpoints (posiblemente en analytics o dashboards service) que agreguen datos de la base. Si no da tiempo a cálculos complejos, al menos mostrar conteos básicos (por ejemplo: número de cursos del profesor, número de módulos virtuales activos, etc.) para llenar espacio[37].
•	Sidebar de Estudiante: Actualmente en la vista del alumno, el menú lateral debería listar sus cursos y al expandir, los módulos y temas virtuales correspondientes. Al parecer, ahora mismo solo muestra el nombre del curso pero no despliega módulos/temas correctamente (bug)[38]. Hay que corregirlo para que:
o	Se consulte al backend los módulos virtuales del estudiante en ese curso (existe endpoint get_student_modules que devuelve todos los VirtualModule de un alumno para un plan de estudios dado)[39].
o	Mostrar cada módulo con sus temas (posiblemente también obtenibles en un solo llamado con get_module_details que ya retorna la lista de topics virtuales[40]). Temas bloqueados deben aparecer con candado hasta que se desbloqueen (según la lógica de progresión).
o	Esto permite al alumno navegar su contenido y ver qué ha completado.
•	Notificaciones (a futuro): Sería útil tener un sistema de notificaciones in-app. Ejemplos:
o	Al alumno: “Nuevo módulo desbloqueado”, “Tu proyecto ha sido calificado con X”, “Tienes una evaluación mañana”.
o	Al profesor: “X ha entregado su tarea”, “La IA calificó automáticamente la entrega de Y, revisa los resultados”.
o	Esto podría implementarse con una colección notifications y un polling, o con WebSockets para inmediatez. No es prioridad inmediata, pero conviene diseñar la UI (un icono de campana en header con contador) con miras a adicionarlo luego[41].
•	Timer Pomodoro y Sonidos de Concentración: La plataforma incluye una herramienta de concentración: un temporizador Pomodoro integrado y la opción de ruido marrón (fondo sonoro para concentración). Ya existe un contexto React manejando esto (modos de trabajo/descanso de 25/5 minutos por defecto, toggling de ruido marrón)[42][43]. Se debe terminar de integrar su UI (un toggle en el header, quizá un pequeño panel mostrando el timer y controles). Posibles mejoras: permitir elegir otros sonidos (ruido blanco, música suave) o personalizar la duración del Pomodoro (ya soportado en el context). Es una funcionalidad auxiliar para mejorar la experiencia de estudio del alumno.
•	Eliminación en Cascada: A nivel de backend, hay que garantizar que si se elimina un objeto se borran o actualizan sus dependencias:
•	Ej: Si se borra un TopicContent (contenido de profesor), ¿qué pasa con VirtualTopicContents ya creados a partir de él? Quizá marcarlos como “archivados” o eliminar.
•	Si se borra un tema del plan de estudio, eliminar sus contenidos, y también los temas virtuales correspondientes de cada alumno.
•	Borrar un módulo (plan de estudio) debe idealmente eliminar los VirtualModule asociados de cada alumno, etc.
•	Se mencionó que esta lógica no está completa aún y debe implementarse cuidadosamente tanto en backend (transacciones o secuencia de deletes) como reflejarse en frontend (por ejemplo, si un profesor borra un contenido, quizá informar a los alumnos que ese material ya no está). Priorizar evitar orfandad de datos en BD.
•	Autenticación con Email/Contraseña: Actualmente solo se permite login con Google OAuth. Se requiere agregar la opción de registro/login con email y password comunes:
•	En backend: añadir al modelo User un campo para password hasheado (si no existe ya). Crear endpoints:
o	POST /api/users/register que reciba email, contraseña, y tipo de cuenta (institución/profesor/estudiante) para crear usuario[44]. Posiblemente, según el tipo, disparar lógica extra (ej. crear instituto por defecto si es profesor particular, etc., como discutido).
o	POST /api/users/login que valide credenciales y retorne JWT (similar a cómo se hace con Google, reutilizando la generación de token)[44].
o	Flujo de recuperación de contraseña: endpoint para iniciar reset (genera token y envía email con enlace) y endpoint para completar el reset estableciendo nueva contraseña[45]. Esto implica configurar un servicio de correo (SendGrid, SMTP). Quizá para MVP se puede omitir o simplificar (console log del link).
o	Asegurar compatibilidad: usuarios existentes de Google no tendrán password; permitírselos seguir usando Google o incluso asociar una contraseña manual si quisieran.
•	En frontend:
o	Pantalla de registro donde se elija el tipo de cuenta (Institución, Profesor, Estudiante). Según la elección, solicitar distintos datos (una institución pediría nombre de la escuela, por ejemplo). Este flujo hay que diseñarlo con cuidado, podría simplificarse inicialmente con solo profesor y estudiante particulares, dejando registro de instituciones vía contacto.
o	Pantalla de login con opción de usar correo/contraseña además del botón de Google.
o	Pantalla de “Olvidé mi contraseña” para ingresar email, y luego la de reestablecer con nueva contraseña tras seguir el enlace.
o	Integrar esto con el contexto de autenticación existente (actualmente manejando Google OAuth) para almacenar el JWT y roles.
•	Sin romper Google: Mantener ambos métodos funcionando en paralelo.
________________________________________
2. Estado Actual de la Implementación (Backend & Frontend)
Revisando el código de los repositorios sapiens-backend y sapiens-frontend, se observa lo siguiente sobre lo ya implementado en relación a los requerimientos:
•	Estructura de Módulos Virtuales: El backend ya define modelos para VirtualModule, VirtualTopic y VirtualTopicContent, reflejando la jerarquía Plan de Estudio → Módulo → Tema → Contenido Virtual[46]. Es decir, hay colecciones separadas en la base de datos para los objetos virtuales de cada alumno, distintos de los contenidos base (TopicContent). Esto confirma la arquitectura frontend-driven planificada: el backend almacena datos crudos y el frontend orquesta la presentación adaptativa. En el frontend, la lógica para manejar módulos virtuales está avanzada:
•	Existe un hook useProgressiveGeneration que maneja la inicialización de generación progresiva y el trigger del siguiente tema[47][48]. Parece utilizar endpoints como startProgressiveGeneration y triggerNextModuleGeneration (definidos en progressiveGenerationService.ts).
•	El backend tiene servicios para generación progresiva. Notablemente, se implementó un OptimizedQueueService o similar, encargado de mantener la cola de 2 temas virtuales por delante del progreso del alumno[49]. En el código, la clase VirtualContentProgressService.complete_content_automatically al marcar un contenido como completado, llama internamente a _check_and_update_topic_progress y luego _trigger_next_topic_generation cuando el progreso del tema alcanza cierto umbral[50]. De hecho, se observa que la regla del 80% de progreso está aplicada: si un tema virtual se completa en más de 80%, el backend genera el siguiente tema automáticamente[51].
•	Durante la creación inicial de un módulo virtual, el sistema marca los primeros temas como desbloqueados. En la base de datos, cada VirtualTopic tiene un campo locked. Se notó que en la implementación actual, los temas generados se están guardando con locked: False incluso para los en cola[52]. Esto difiere ligeramente de la idea original (tenerlos bloqueados hasta que el anterior se complete). Es un detalle a ajustar en UX: probablemente conviene crear los temas por adelantado pero marcarlos locked=True excepto el actual, y luego actualizar a False cuando corresponda desbloquearlos.
•	La API de backend ya ofrece endpoints tipo GET /api/virtual/topic/<id>/contents para obtener los contenidos virtuales de un tema[53]. Esa respuesta incluye, para cada contenido virtual, datos como original_content (la versión no personalizada), original_personalization_markers y original_slide_template[53]. El frontend usa esos campos para poder aplicar la personalización y fragmentar las diapositivas localmente.
•	Orquestación y Fragmentación en Frontend: Confirmado en el código React:
•	En el componente de visualización de un tema virtual, se utiliza un hook useTopicOrchestrator (o similar) que:
o	Toma el HTML completo de las diapositivas generado por IA y lo divide en slides individuales usando DOMParser[20]. Cada fragmento obtiene la plantilla base (las diapositivas generadas tienen una estructura HTML con ciertas clases/CSS; el código extrae esa plantilla para aplicarla a cada fragmento)[54]. Esto permite luego renderizar slide por slide.
o	Arma una lista con todos los contenidos (fragmentos de slide, texto, quiz, etc.) y envía sus resúmenes a un servicio de IA de secuenciación. El código sugiere que efectivamente se está llamando a una función getAiOrderedSequence y reordenando el estado según la respuesta[54]. Asimismo, se maneja que si la IA no responde o falla, simplemente se deja el orden original[54]. Esto concuerda con la especificación de secuenciación flexible.
o	Resultado: el contenido se muestra inicialmente en el orden base y luego, casi de forma transparente para el usuario, se reordena cuando llega la secuencia óptima (con una transición suave, sin recargar la página). Esto ya estaría implementado, mejorando la experiencia.
•	Personalización de Contenido (marcadores): En el frontend, cada elemento de contenido se renderiza mediante un componente ContentRenderer que utiliza el hook useContentPersonalization. Este hook:
•	Escanea el contenido en busca de los marcadores {{...}} enviados desde backend en original_personalization_markers[11].
•	Luego (actualmente) llama a una función simulada (fetchIaReplacements) para obtener valores de reemplazo[11]. En la implementación actual, esta función devuelve datos dummy (por ejemplo, nombres genéricos, colores aleatorios) solo para probar el flujo[11]. Aún no está conectado a un servicio real de IA para generar personalizaciones auténticas, pero la estructura está lista.
•	Aplica recursivamente los reemplazos en el HTML/texto e incluso en objetos JSON embebidos (por si un marcador define, por ejemplo, un cambio en un parámetro de un juego)[11].
•	Si un contenido no tiene marcadores, se presenta tal cual.
•	En resumen, el pipeline de personalización interna está montado en frontend; falta sustituir el mock por la integración real con IA (lo cual se hará cuando se habilite un endpoint apropiado en backend).
•	Selección Adaptativa de Tipos de Contenido: En versiones anteriores, el backend no filtraba contenidos por perfil – insertaba todos los TopicContent de un tema en la colección virtual del alumno[8]. Esto ha sido mejorado recientemente: Según la documentación de fase 1, ya se implementó un filtrado inteligente:
•	Se creó o ajustó un método _select_personalized_contents en el servicio de generación virtual que lee el perfil cognitivo del alumno (desde la colección cognitive_profiles) y decide qué contenidos incluir[55]. De hecho, se corrigieron errores: inicialmente la lógica buscaba mal los datos anidados; se refactorizó para tomar el JSON correcto del perfil y normalizar los valores VAK de 0-100 a 0-1[55].
•	Reglas aplicadas (según el código fuente observado y el resumen de fase 1):
o	A cada TopicContent posiblemente se le define una lista de metodologías de aprendizaje (visual, auditivo, etc.) o características. Con base en ellas y el perfil del estudiante, el sistema prioriza o descarta contenidos. Por ejemplo, si un estudiante tiene ADHD alto, se buscarán contenidos marcados como interactivos o breves; el código muestra que hay una “REGLA #2: ADHD necesita contenidos cortos e interactivos” que filtra la lista de contenidos específicos para incluir solo los adecuados[56].
o	Se asegura incluir siempre al menos un recurso teórico completo: el sistema marca algunos contenidos como base obligatoria (slides generadas con método Feynman, por ejemplo) y los incluye aunque el perfil preferiría otra cosa, para garantizar cobertura[9].
o	En el código de generación, vimos que cada VirtualTopicContent resultante lleva un campo personalization_data.adapted_for_profile indicando que fue seleccionado/adaptado según el perfil[57]. También se incluyen subcampos como vak_adaptation (ej. flags visual_emphasis, audio_support según puntuaciones VAK) y accessibility_adaptations (ej. dyslexia_friendly, adhd_optimized)[58]. Esto confirma que se están aplicando varias adaptaciones al contenido en base al perfil del alumno.
o	Adicionalmente, se normaliza la dificultad del contenido según el perfil (posiblemente ajustando la complejidad del texto si detecta, por ejemplo, nivel educativo bajo). En el código se menciona _calculate_quick_difficulty_adjustment usando el perfil, quizás reduciendo detalles avanzados para ciertos alumnos[59].
•	Conclusión: Ahora mismo, al generar un módulo virtual, el backend no inserta todos los contenidos indiscriminadamente; aplica un filtro con ~5 reglas clave (VAK, dificultades, equilibrio de formatos) para decidir qué contenidos terminan en la versión personalizada[60]. Esto atiende la petición de selección adaptativa. Sin embargo, se debe probar y ajustar con datos reales para ver si ningún tema queda con huecos (por ejemplo, si el perfil filtra demasiado). Queda pendiente exponer claramente estas reglas en documentación o interfaz para que los educadores entiendan qué recibe cada alumno.
•	ContentResult Unificado: El sistema de resultados de contenido está activo:
•	Se eliminó un antiguo modelo EvaluationResult en favor de usar ContentResult para todo (pruebas, juegos, lecturas, evaluaciones)[4]. El modelo ContentResult tiene campos: content_id (ID del TopicContent original asociado), student_id, score (0 a 1), feedback (texto), metrics (diccionario con detalles como tiempo, intentos, etc.), session_type (por defecto “content_interaction”)[4].
•	En backend existe ContentResultService.record_result que centraliza la creación de resultados. El snippet de código del servicio de progreso automático muestra que, al completar un contenido, se invoca ContentResultService.record_result pasando los datos correspondientes[61][62].
•	Importante: El auto-registro de finalización ya está implementado para contenidos no evaluativos. Por ejemplo, VirtualContentProgressService.complete_content_automatically:
o	Verifica que el alumno no haya completado ya el contenido.
o	Calcula un score automático según el tipo de contenido (como se describió: 1.0 para lecturas, 0.8 para juegos, 0 para quizzes)[63][64].
o	Crea un ContentResult con ese score y marca el contenido como completado (actualiza interaction_tracking.completion_status a “completed”)[65][66].
o	Actualiza también el progreso del VirtualTopic (posiblemente acumulando % de contenidos completados) y si excede 80%, lanza la generación del siguiente tema en cola[50].
o	Este flujo cubre automáticamente el caso de lecturas/visto. Para quizzes o juegos, la idea es que el frontend llame a otro endpoint (quizá record_result) pasando la puntuación obtenida cuando el alumno termina ese juego/quiz, en cuyo caso también se crearía un ContentResult. De hecho, se prevé un endpoint POST /api/content/result para recibir resultados de quizzes interactivos – habrá que confirmar su existencia.
•	El modelo TopicContent ya no tiene un subdocumento de resultados; todo va a ContentResult. Y en el modelo StudyPlan (plan de estudio) se limpió cualquier referencia a resultados antiguos, apuntando también a ContentResult para evaluaciones[4].
•	En resumen, el backend soporta correctamente el almacenamiento unificado de resultados de aprendizaje, faltando integrar algunas llamadas desde frontend (por ejemplo, asegurar que al completar un quiz se llame al backend para guardar la nota).
•	Sistema de Evaluaciones en Backend: Se encuentra parcialmente implementado:
•	El modelo Evaluation existe (con campos como nombre, tipo, peso, flags, due_date, etc.) y se relaciona con StudyPlan (o Module).
•	Se detectó que había intentos previos de manejar entregas mediante modelos separados (EvaluationSubmission, EvaluationRubric), pero estos fueron eliminados para evitar duplicación[16][67]. Ahora la estrategia es usar el sistema de Recursos para eso:
o	En study_plans/services.py, la lógica de calificación se centró en un método record_result que crea ContentResult para registrar notas tanto de quizzes automáticos como de evaluaciones manuales[68].
o	Los endpoints específicos para submission/grade que se estaban creando se eliminaron, en favor de reusar los ya existentes y la estructura de resources[16]. Esto sugiere que aún no hay un endpoint directo tipo /evaluation/{id}/grade, sino que planean usar quizás /content/result genérico o crear uno unificado después.
•	Recursos en Evaluaciones: El backend tiene un modelo Resource general y se introdujo el concepto EvaluationResource (probablemente para asociar Resource + Evaluation + rol). De la documentación:
o	El profesor puede adjuntar archivos de enunciado/guía. Esto seguramente ya se soporta haciendo primero POST /api/resources para subir el archivo, y luego un POST /api/study_plans/evaluation/{eval_id}/resource para asociarlo con un campo role (por ahora, quizá se hace manualmente)[14].
o	No está confirmado si existe ya ese segundo endpoint, pero es parte del plan.
o	Para las entregas de alumnos, el flujo sería similar: alumno hace upload a /api/resources (lo que retorna un resource_id) y luego una llamada para vincularlo a la evaluación como submission. Es probable que todavía no esté implementado el endpoint específico, viéndose en la doc que se sugería crear /api/study_plans/evaluation/{id}/submit[14].
•	Trigger de generación en 80%: Mencionamos antes que backend lo tiene. El frontend debe invocar esto en el momento adecuado. Es decir, cuando el alumno termina un tema (o alcanza >= 80% de contenidos completados), debería llamar a POST /api/virtual/trigger-next-topic (o el endpoint equivalente, posiblemente triggerNextModuleGeneration). En el código React, en useProgressiveGeneration.triggerNext se ve que espera parámetros currentModuleId, studentId, progress y hace la llamada[47]. Es decir, la estructura está pero hay que asegurarse de llamarla realmente en la interfaz cuando corresponde (por ejemplo, al marcar la última actividad de un tema como completada, o cuando el alumno intenta pasar al siguiente tema y este está bloqueado).
•	Estado actual resumido: Los cimientos para evaluaciones están: modelo unificado, usar ContentResult para notas, recurso para entregas. Falta terminar de conectar piezas (endpoints finales y la interfaz para usarlo).
•	Generación con Múltiples Modelos de IA: En el frontend hay indicios de soporte para múltiples modelos:
•	Existe configuración para diferentes endpoints de IA (OpenAI vía OpenRouter, modelos Gemini de Google). En algún archivo se listan modelos como o3_mini, gemini_2_5_flash, gemini_2_5_pro, etc., y estrategias de alternancia[69]. Esto sugiere que la aplicación puede utilizar distintos modelos ya integrados via APIs.
•	Actualmente, sin embargo, parece que los contenidos se siguen generando secuencialmente (uno tras otro). La petición del usuario es implementar paralelismo: usar hasta 3 llamadas simultáneas a modelos distintos para generar 3 contenidos a la vez[70]. Por ejemplo, al hacer clic en “Generar contenido” del profesor para un tema:
o	Lanzar en paralelo la generación del texto teórico (quizá con modelo grande Gemini 2.5 Pro por calidad), del diagrama (con otro modelo más rápido) y de la evaluación/quiz (con un tercer modelo). Así se reduce el tiempo total de espera casi a 1/3.
o	Si alguna generación falla (por timeout u otro error de la API), inmediatamente reintentar ese contenido con otro modelo disponible (fallback). Y para la siguiente ronda de generación, se puede volver a intentar con el modelo original por si el fallo fue puntual[70].
•	Parte de esto requerirá coordinación en frontend (por ejemplo, usar Promise.all con diferentes endpoints de generación) y quizás soporte en backend para marcar contenidos como “en generación”.
•	Estado actual: No hay evidencia de que el paralelismo ya esté activo; más bien es un pendiente identificado. Sin embargo, los modelos alternativos ya están configurados, lo cual facilita implementarlo.
•	Notificaciones de Progreso de Generación: Actualmente, cuando el profesor genera contenido, si navega fuera o recarga podría perder la visibilidad de qué se ha generado. Se quiere implementar toasts persistentes que informen “Generando quiz...”, “Generando diagrama...” y permanezcan hasta completarse[71][72]. Esto requiere que el frontend pueda al montarse chequear si hay tareas de generación en curso (quizá consultando el estado de TopicContent.status = generating). Es mencionado como pendiente. Hasta ahora, probablemente, las notificaciones de generación desaparecen con un refresh.
•	Multi-rol / Multi-instituto: No se observa aún en el código implementado. Por defecto, al login se asocia a un institute_id. No hay UI de selección de instituto, ni endpoints para cambiarlo. Por tanto, no soportado todavía.
•	En la base de datos, existe ya una colección institute_members que permite ver membresías (un profesor podría tener dos entradas allí con distinto institute_id). Eso es buena base. Pero funcionalmente, falta implementación.
•	Rol dual profesor-alumno: tampoco implementado aún. Un usuario tiene un rol principal. No hay toggle en UI para cambiar vista. Probablemente requerirá varias modificaciones.
•	Marketplace, Suscripciones, Mobile: Como era de esperar, no están implementados todavía. No se hallan secciones de código relativas a publicar cursos públicamente, ni integración con Stripe, ni proyecto React Native iniciado dentro del repo (sería separado). El código de landing page posiblemente tampoco, ya que el login es directo por ahora.
•	Módulo de Lenguas Indígenas: Sí existe en backend:
•	Hay servicios y rutas para traducciones (translations) y lenguajes (languages). Por ejemplo, TranslationService con métodos para crear nuevas traducciones, conteniendo campos como español, traducción, dialecto, verificaciones, etc.[73]. Endpoints detectados:
o	POST /api/translations para agregar una traducción (requiere campos de idioma origen/destino, etc.)[73].
o	GET /api/translations y /api/translations/search para consultar entradas, con filtros como dialecto, número mínimo de verificaciones, etc.[73].
o	GET /api/languages para listar los idiomas disponibles (posiblemente lenguas indígenas cargadas)[73].
o	Un sistema de verificación colaborativa: campos como verifier_id, min_verifications sugieren que varios usuarios pueden verificar una traducción hasta marcarla como aprobada.
•	Esto muestra que la plataforma tiene un módulo tipo “diccionario bilingüe” enfocado en lenguas indígenas. Probablemente la idea es permitir contribuir con traducciones para preservar esos idiomas.
•	Front-end: Habría que ver si hay interfaz ya (quizá solo accesible a admins). Podría no estar expuesta aún. En cualquier caso, parece semi-terminado en backend pero con prioridad menor respecto al núcleo educativo.
•	Falta: crear una UI para que los usuarios consulten el diccionario, filtren por idioma, aporten nuevas palabras o validen existentes. Dado que es un objetivo cultural importante, se debe incluir en el plan, aunque sea en fases intermedias[74].
•	Concentración (Pomodoro/Ruido): Como vimos en frontend:
•	Está implementado el context ConcentrationContext con todo el estado y funciones para Pomodoro y ruido marrón[42][43]. También existe un componente ConcentrationToggle posiblemente en el header para controlar esto.
•	Uno puede activar/desactivar el ruido marrón (se carga un archivo MP3 ruido_marron.mp3 en loop con volumen 0.2)[75]. Y controlar el temporizador (iniciar, pausar, reset; alterna entre modo 'work' y 'break' con los segundos configurados).
•	Pendiente menor: asegurar que el audio de ruido marrón se carga correctamente en producción (tal vez mover el archivo estático a ubicación accesible), y terminar detalles de UI (mostrar countdown, etc.). Pero la funcionalidad base está lista.
•	Limpieza de Redundancias: De la auditoría de fase 1:
•	Se eliminaron endpoints duplicados en virtual/routes.py (había definiciones repetidas de auto_complete_content y detect_module_changes que causaban error de inicio)[76].
•	Se corrigió un typo de rol (TEACH-ER a TEACHER) que impedía iniciar el servidor[76].
•	Estas correcciones ya están aplicadas, pues la app arranca correctamente ahora.
•	También, como se dijo, se eliminaron modelos duplicados para submissions y rubrics[16], consolidando todo en uno.
•	Estructura de perfil: Se solucionó la lectura incorrecta del perfil cognitivo (antes el código esperaba datos en users cuando realmente están en colección separada). Ahora carga bien el JSON del perfil y lo parsea[55].
En síntesis, tras la Fase 1 del desarrollo, el sistema tiene implementado gran parte del núcleo funcional: generación adaptativa de módulos virtuales, almacenamiento unificado de resultados, evaluaciones en modelo unificado, y correcciones de duplicación/errores. Los algoritmos de personalización de contenido y cola de progreso están en marcha, aunque algunas partes todavía usan datos simulados (marcadores con valores dummy) o necesitan conexión final (llamadas IA reales, endpoints finales). No obstante, la base es sólida para continuar.
Quedan pendientes importantes en el estado actual: terminar de implementar la interfaz de evaluaciones (subir tareas, introducir notas manuales), mejorar la sincronización de cambios de contenido, habilitar la nueva autenticación, corregir fallos de UI (sidebar, etc.), y luego abordar las expansiones grandes (auto-corrección completa, marketplace, app móvil, etc.). Procedemos a detallar un plan paso a paso para completar todo lo faltante.
________________________________________
3. Plan de Implementación Paso a Paso (Frontend & Backend)
Dada la amplitud de tareas, se propone un plan organizado en fases, priorizando primero consolidar lo esencial (módulos virtuales y evaluaciones funcionando de forma estable), luego mejoras de plataforma y finalmente extensiones avanzadas. Dentro de cada fase se listan tareas específicas, indicando (B) para backend y (F) para frontend. Se enfatiza coordinar cada cambio en backend con su contraparte en frontend para mantener la coherencia API-UI. También se destacará en qué archivos o servicios se deben realizar modificaciones principales.
Fase 1: Consolidación de Núcleo Personalizado (Máxima Prioridad)
Objetivo: Dejar totalmente funcional la experiencia principal de aprendizaje personalizado y evaluación básica, sin bugs ni características incompletas. Incluye finalizar módulos virtuales, resultados de contenido y evaluaciones en flujo básico.
•	(B) Completar integración de ContentResult en todas las interacciones:
Asegurarse de registrar ContentResults en todas las situaciones:
•	Cuando un alumno finaliza un quiz o juego, actualmente debería haber un llamado explícito. Implementar el endpoint correspondiente si falta. Por ejemplo, podría ser POST /api/content_results con body {content_id, student_id, score, ...}. Verificar si ya existe en content/routes.py o implementarlo en ContentResultService y exponerlo.
•	Unificar creación de notas manuales: Crear un método en EvaluationService o reutilizar ContentResultService.record_result para cuando un profesor introduce una nota manual. Podría ser un endpoint POST /api/evaluations/{eval_id}/grade que recibe {student_id, score, feedback} y dentro crea un ContentResult apropiado[77]. Este ContentResult puede usar content_id igual a algún contenido de referencia (por ejemplo, si la evaluación estaba ligada a un quiz, usar ese ID; si no, quizá crear un TopicContent especial de tipo “exam” para vincular).
•	Auto-completar visualizaciones: Confirmar que el backend ya marca como completados (y crea ContentResult) para contenidos de solo lectura cuando el frontend los notifica. Si no, usar el VirtualContentProgressService.complete_content_automatically que ya está escrito[65][50]. Exponerlo vía endpoint POST /api/virtual/content/{id}/complete al que el frontend llame al terminar un recurso. Este endpoint internamente invocará complete_content_automatically para generar el ContentResult y actualizar progreso.
•	(B) Sistema de Evaluaciones – casos pendientes:
Implementar los endpoints y lógica mínima para que las evaluaciones funcionen end-to-end:
•	Crear/Editar evaluaciones: Si no está, agregar endpoint POST /api/study_plans/{plan_id}/evaluations (o similar) para crear evaluaciones (usado en vista profesor al configurar el plan). Permitir setear campos como nombre, peso, tipo, flags (use_quiz_score, requires_submission)[77]. Igualmente, endpoint PUT /api/evaluations/{id} para editar detalles.
•	Entrega de archivos (submissions): Implementar el flujo de entrega:
a.	(F) En la vista del alumno dentro del módulo, para evaluaciones con requires_submission = true, mostrar un formulario para subir archivo (puede reutilizar componente de subida existente).
b.	(B) Reutilizar POST /api/resources para guardar el archivo (ya retorna URL o id). Luego, implementar POST /api/evaluations/{eval_id}/submit que:
c.	Crea un EvaluationResource con role "submission", referenciando el Resource subido y al student_id correspondiente[14].
d.	Marca en la entidad Evaluation o en algún registro que el estudiante X entregó (por ejemplo, guardar en EvaluationResult placeholder).
e.	Devolver confirmación. Posiblemente aquí también podríamos iniciar la corrección automática si la evaluación tiene auto-corrección activa (ver más abajo). De momento, quizás solo marcar “entregado”.
•	Registro de calificaciones manuales: Endpoint POST /api/evaluations/{eval_id}/grade (como se mencionó) para que el profesor ponga nota:
o	Input: {student_id, score, feedback}.
o	Lógica: crear ContentResult con content_id asociado a la evaluación (puede ser un campo evaluation_id en ContentResult, o usando content_id de un Quiz vinculado si use_quiz_score=true, etc.). Probablemente más claro es ampliar ContentResult con un campo optional evaluation_id, pero si no, usar content_id de un TopicContent “placeholder”. En cualquier caso, garantizar que luego podamos recuperar la nota.
o	Esto permite ingresar notas de exposiciones, etc.
•	Cálculo de nota de evaluaciones automáticas: Para evaluaciones con use_quiz_score = true, su nota final para cada alumno dependerá del ContentResult del quiz correspondiente. En backend, al obtener una evaluación, se podría juntar esa info. Ver siguiente punto.
•	(B) Endpoints de obtención de evaluaciones y notas:
Facilitar que frontend pueda mostrar el estado de evaluaciones tanto a alumnos como profesores:
•	GET /api/virtual/modules/{module_id}/evaluations: devuelve la lista de evaluaciones de ese módulo (o plan) con detalles como nombre, peso, due_date, flags, y para el alumno actual incluir: si requiere entrega, si ya entregó (y posiblemente la fecha de entrega), y si ya tiene nota (con el score obtenido)[78]. Esto implica hacer join con ContentResult (para ver si hay nota) y con submissions (para ver si entregó).
•	GET /api/evaluations/{id}/submissions (profesor): lista todos los estudiantes y su estado: entregado o no, nota asignada o pendiente, etc., para que el profesor sepa a quién calificar. Alternativamente, un endpoint más general /api/classes/{class_id}/evaluations_status que para una clase y evaluación dé un resumen.
•	Con estos, el frontend puede:
o	En la vista del alumno, listar evaluaciones del módulo con indicadores “pendiente”, “entregado el X”, “calificado: nota Y”[78].
o	En la vista del profesor, ver por evaluación quién entregó y acceder a calificar.
•	(B) Corrección Automática (Backbone inicial):
Preparar el terreno para la auto-corrección de entregas:
•	Cuando un alumno hace submit de una tarea (ver arriba), se podría disparar inmediatamente un proceso asíncrono si la evaluación está marcada para corrección automática. Dos maneras:
a.	Sencilla: al recibir el submit, retornar éxito y en segundo plano iniciar la corrección (por ejemplo, un thread o una task encolada). No se bloquea al alumno.
b.	Compleja: integrar un sistema de colas (Celery/RQ) para procesar en background. Quizá excesivo para MVP; un thread puede valer siempre que se controle.
•	Crear un servicio AutomaticGradingService con método grade_submission(resource_id, evaluation_id):
o	Por ahora, implementarlo de forma simulada (dummy) para probar flujo: leer el Resource (tal vez obtener solo texto “dummy”), asignar siempre score 1.0 y feedback “Calificado automáticamente.”[17].
o	Crear el ContentResult con ese score y feedback (similar a como se dijo).
o	Marcar de alguna forma que ya está calificado (tal vez actualizar un campo en EvaluationResource o crear un campo en Evaluation de “graded_count”).
•	Este es el “esqueleto”. Más adelante, en fase 3, se conectará con OCR y GPT reales.
•	(B) Sincronización de cambios de contenido:
Implementar al menos la funcionalidad básica para reflejar cambios de plan de estudio en módulos virtuales:
•	En backend, en el servicio de virtualización (quizá en VirtualModuleService o separado) existe una función synchronize_module_content o similar. Confirmar su existencia; de no existir, crearla.
•	Estrategia mínima: cada vez que un alumno abre su módulo virtual, ejecutar sincronización:
o	Para cada VirtualTopicContent del alumno, comprobar si el contenido original (TopicContent referido por content_id) tiene un updated_at más reciente que el sync_date almacenado en el virtual[22].
o	Si sí y si el alumno no ha interactuado aún con ese VirtualTopicContent (por ejemplo, status no completed), entonces actualizar el campo content en VirtualTopicContent con la nueva versión del contenido original (posiblemente regenerar el adapted_content si ya tenía personalización, o marcarlo para regenerar).
o	Si un contenido original fue archivado/eliminado, quizás quitarlo de los VirtualTopicContents (o marcarlo oculto).
o	Si se añadió un nuevo TopicContent en el tema y el alumno no ha completado ese tema: crear un nuevo VirtualTopicContent para él en ese tema (al final de la lista, o en la posición adecuada). Marcarlo como nuevo.
o	Mantener dos temas adelantados: si el profesor publicó un nuevo tema en el plan (antes inexistente) y el alumno ya está cerca del final, habría que generar su VirtualTopic para ese nuevo tema cuando corresponda.
•	Esto es complejo de hacer perfecto; para MVP se puede cubrir solo escenarios simples (updates menores). Documentar esta limitación si queda pendiente una sincronización más fina.
•	(F) Frontend Módulos Virtuales y Navegación:
Mejorar la experiencia del estudiante en su módulo virtual:
•	Sidebar de navegación: Corregir el componente Sidebar para listar módulos y temas:
o	Llamar al backend (get_student_modules ya disponible) al cargar la vista estudiante para obtener los módulos virtuales del alumno en cada curso[79].
o	Poblar el menú lateral: mostrar el nombre del curso, dentro los módulos (por nombre del módulo, e.g. “Módulo 1: Introducción”) y dentro de cada módulo los temas virtuales ya generados[80].
o	Marcar los temas bloqueados con ícono candado. Solo permitir click en el tema actual o anteriores completados.
o	Si se desea, mostrar porcentaje completado de cada tema y módulo (por ejemplo, un ✅ en temas completados).
•	Indicador de progreso dentro del tema: En la vista de un tema virtual, añadir un progreso (e.g. “3/5 contenidos completados” o una barra). Esto se puede calcular contando ContentResults de ese VirtualTopic vs total contenidos. También usarlo para saber cuándo alcanza 80%.
•	Trigger de siguiente tema: Integrar el hook useProgressiveGeneration.triggerNext:
o	Por ejemplo, en el componente de visor, cuando el estudiante completa el último contenido (o al salir del tema), si topic.progress >= 80% llamar triggerNext(currentModuleId, studentId, topic.progress)[47]. Esto llamará al backend para generar el siguiente tema.
o	Manejar la respuesta: si devuelve que se generó un nuevo tema, actualizar la lista de temas en el estado (posiblemente recargando via get_module_details nuevamente, o aprovechando refreshStatus del hook que da generatedModules y queueStatus)[48][81].
o	Notificar al usuario quizás con un pequeño mensaje “Nuevo tema preparado: <título>” o simplemente habilitando el siguiente tema en el sidebar.
•	Evaluaciones en UI (básico):
o	En la pantalla del módulo (vista alumno), debajo de la lista de temas o en otra pestaña, listar las Evaluaciones del módulo:
o	Mostrar nombre de la evaluación, fecha límite (due_date) si la tiene, y peso (%).
o	Si la evaluación toma nota de un quiz existente (flag use_quiz_score), y el quiz ya fue hecho, mostrar “Calificación obtenida: X” o un botón “Ir al Quiz” si aún no lo ha hecho[78].
o	Si es con entrega (requires_submission), mostrar botón “Subir entrega” si no entregó aún; si ya entregó, indicar “Entregado el {fecha}” y quizás permitir re-subir hasta cierta fecha.
o	Si ya está calificada, mostrar “Calificación: Y (Feedback: ...)” para cerrar el ciclo.
o	En la pantalla del módulo (vista profesor), sección de Evaluaciones:
o	Listar las evaluaciones definidas con sus detalles (nombre, peso, etc.).
o	Si es manual, permitir ingresar notas: un botón “Calificar” al lado de cada evaluación que abre una modal o nueva página con la lista de alumnos y un campo para poner nota y feedback a cada uno[82]. Tras guardar, eso llama al endpoint de grade para cada alumno.
o	Si es por entrega, mostrar para cada estudiante si entregó o no, y un link para descargar cada archivo entregado (recordando que guardamos Resource, así que dar la URL del resource). También un botón “Autocalificar” global o por alumno si vamos a usar IA (en MVP quizás no, se hará manual).
o	Mostrar también el material adjunto de la evaluación (ej. si el profesor subió un enunciado PDF, poner un enlace “Descargar instrucciones” para verlo)[82].
o	Estas interfaces requieren tiempo, pero son importantes para completar el módulo educativo. Empezar por lo esencial: el alumno al menos debe ver sus tareas y subir archivos; el profesor debe poder poner notas manualmente.
•	Notificación de correcciones automáticas: Si implementamos el auto-grading dummy, podría haber un polling para que el alumno se entere cuando su entrega fue calificada. Simplest: después de entregar, en la UI alumno mostrar “Estado: Corrigiendo...” y refrescar cada X segundos consultando /evaluations/{id}/status hasta ver una nota[82]. Igual para el profesor, o usar websockets en el futuro.
•	(F) Toasts persistentes de generación:
Implementar el sistema de notificaciones de generación de contenido del profesor:
•	En la vista de generación de tema (donde al hacer clic se generan teoría, quiz, etc.), utilizar algún estado global (context o Redux) para añadir “toasts” o alertas informativas cuando inicia la generación de cada recurso. Por ejemplo: “Generando Texto Teórico...”, “Generando Quiz...”.
•	Cuando el backend responde con éxito y guarda el contenido, cerrar/eliminar ese toast.
•	Persistencia al recargar: Esto es tricky porque si recarga la página, se pierde estado. Alternativas:
o	Consultar al backend si hay contenidos en estado "generating" para ese tema y re-lanzar los toasts correspondientes. Esto implica marcar de algún modo en la BD los contenidos en curso. Podría añadirse un campo status: generating en TopicContent mientras espera respuesta de IA.
o	O mantener en localStorage una bandera de “generación en curso” con qué estaba generando, de modo que al recargar, el frontend lea eso y muestre nuevamente las notificaciones.
•	Esto mejora UX pero no es crítico para funcionalidad, se puede hacer al final de fase 1 si el tiempo lo permite[2][83].
•	(F) Dark mode & Responsive audit:
Revisar y corregir detalles de estilo:
•	Abrir la aplicación en modo oscuro y en dispositivos móviles (DevTools) para las páginas principales:
o	Login/Registro: que el texto sea legible en ambos modos, ajustar colores si hace falta.
o	Dashboard inicial (prof y alumno): Asegurar que tarjetas y gráficos cambian de estilo en dark mode adecuadamente. Corregir por ejemplo si hay texto negro sobre fondo oscuro.
o	Vista de Módulo Virtual: que el fondo y texto de los contenidos se adapten (puede que el contenido HTML de IA venga con fondo blanco fijo; en tal caso, envolverlo con clases CSS o aplicar estilos para invertirse en dark).
o	Componentes de código o juegos: si hay sandboxes con iframes, tratar de que no desentonen en dark mode (quizá no trivial).
o	Responsividad: Ver que el sidebar se oculte/muestre adecuadamente en móvil (tal vez implementar un botón de menú para togglearlo). Ver que los contenidos se pueden scroll en pantallas pequeñas sin desbordes horizontales.
•	Esto implica principalmente CSS/Tailwind changes en componentes existentes.
•	(F) Manejo global de errores de fetch:
Centralizar usando el helper fetchWithAuth:
•	En fetchWithAuth, después de obtener la respuesta, si es status 401, hacer logout() global (por ej, borrar token, redirigir a /login). Si 403, mostrar toast “No autorizado” (puede usar algún toast context global). Si 500, toast “Error en el servidor, intente más tarde”.
•	Asegurarse de envolver las páginas en un <ErrorBoundary> component (React) para capturar errores JS y renderizar un mensaje amigable (“Ocurrió un error inesperado. Por favor, recarga.”).
•	Remover console.log debugs de producción o reemplazarlos con notificaciones user-friendly donde corresponda.
Con todo lo anterior, Fase 1 cierra con el sistema principal funcionando: los estudiantes pueden realizar sus módulos virtuales completos y evaluaciones básicas, y los profesores pueden generar contenido y ver resultados, todo sin cabos sueltos. Se prioriza arreglar cualquier bug que impida estos flujos antes de añadir nuevas características.
Fase 2: Mejoras de Plataforma y Usuarios (Autenticación, Multi-rol, Pulido UI)
Objetivo: Pulir la plataforma para un entorno real con distintos tipos de usuarios, haciendo el sistema más robusto y amigable. Incluye agregar la autenticación tradicional, soportar multi-instituto en cierto grado, y mejoras generales de interfaz.
•	(B) Autenticación Email/Contraseña:
•	Modelos: Añadir password_hash (string) al modelo User si no existe. Instalar una librería de hashing (bcrypt) si no está ya.
•	Registro (Email): Crear POST /api/users/register. Lógica:
o	Recibe email, password, tipo de cuenta (opcional). Hash la contraseña.
o	Crea el User (rol dependiendo del tipo elegido: si es Institución, crear user con rol ADMIN y crear nueva Institute; si es Profesor particular, rol TEACHER y crear Institute “Personal de {nombre}” quizás; si es Estudiante individual, rol STUDENT bajo instituto “Academia Sapiens” global).
o	Para simplificar, quizás limitar la elección a “Profesor” o “Estudiante” inicialmente e internamente manejar un instituto genérico para ambos.
o	Retornar JWT igual que OAuth login.
•	Login (Email): POST /api/users/login:
o	Buscar user por email, verificar hash de password. Si ok, generar JWT (reutilizar método de Google login, solo que claims tendrán user id, role, institute id principal).
o	Si falla, retornar 401.
•	Recuperación Password:
o	POST /api/users/forgot-password: generar un token (p.ej. UUID, asociado al user en una tabla temporal o en user doc con campo reset_token y expira). Enviar email con enlace que contenga ese token.
o	Enviar Email: Configurar algo simple – si SMTP no está disponible, al menos loguear el “enlace de reset” en el servidor para pruebas.
o	POST /api/users/reset-password: recibe token y new password, valida token, setea nueva password hash y elimina token.
•	JWT y compatibilidad: Asegurarse que el login OAuth existente sigue funcionando. Probablemente hay un endpoint /api/auth/google que crea/verifica usuario. Mantener ambos.
o	El JWT puede incluir provider info o simplemente no diferenciar; como vamos a permitir ambos, no hace falta distinguir en token.
•	Testing: Probar registrarse con email, login, logout. Y que login con Google aún funcione tras estos cambios.
•	(F) UI de Registro/Login:
•	Pantalla de Registro: Crear una página /register con formulario:
o	Campos básicos: Nombre, Email, Password, Confirm Password.
o	Dropdown o toggle para tipo de cuenta: Institución, Profesor, Estudiante (si hay diferencia).
o	Si elige Institución: pedir nombre de la institución, quizás teléfono de contacto, etc. (O podemos inicialmente no implementarlo por complejidad de pago, etc., y en vez de eso solo permitir profesor/estudiante).
o	Si Profesor: quizá pedir algún dato opcional como materia principal o nada extra.
o	Si Estudiante: podría preguntar “¿Estás afiliado a una institución existente?” pero eso complicaría (ya que si sí, debería invitarle un admin...). Para MVP, Estudiante individual crea cuenta normal para cursos públicos o propios.
o	Al submit, llamar POST /api/users/register. Si éxito, guardar token y redirigir a dashboard adecuado.
•	Pantalla de Login: Extender la actual para incluir campos Email/Password y un botón para login social Google:
o	Dos pestañas o un toggle “Iniciar sesión con email” vs “Con Google”.
o	Procesar email/password via POST /api/users/login, guardar token, roles, etc., luego redirect.
•	Flujo Forgot Password: Un link “¿Olvidaste tu contraseña?” en login:
o	Al hacer click, mostrar formulario para ingresar email.
o	Llamar POST /api/users/forgot-password, y mostrar un mensaje tipo “Hemos enviado un correo con instrucciones” independientemente (para no revelar si el email existe).
o	Crear páginas /reset-password?token=XYZ donde el usuario ingresa nueva contraseña dos veces. Submit a POST /api/users/reset-password con token y pass. Mostrar confirmación y link a login.
•	Integración en estado global: En el contexto Auth, manejar también login tradicional. Guardar el JWT en localStorage.
o	Asegurarse de incluirlo en fetchWithAuth.
o	Gestionar logout correctamente (borrar token, limpiar datos, redirect landing).
•	Notas: Debe probarse todo el flujo. Esta funcionalidad amplía público potencial (no restringe a Google accounts).
•	(B) Soporte Multi-Instituto (parcial):
•	JWT vs Contexto: Decidir enfoque: más sencillo será NO cambiar el JWT por ahora (seguir incluyendo un institute_id principal). En su lugar, manejar la multi-afiliación en frontend:
o	Backend: Proveer endpoint GET /api/users/me/institutes que devuelva la lista de institutos (nombre, id, rol en cada uno) donde el user es miembro[25].
o	Si se quiere cambiar instituto activo sin regenerar token, entonces en cada request de frontend se debe mandar cuál instituto usar. Esto puede ser vía un header X-Institute-ID o como query param. O incluso más simple: cuando frontend pida cursos, podría llamar a /api/institutes/{id}/courses en vez de /api/courses globales.
o	Cambiar todas las consultas en frontend para filtrar por institute_id seleccionado (ej. instituteService.getCourses(instituteId) etc.).
•	Alternativa JWT: reemitir token con institute distinto. Esto requiere un endpoint /switch-institute que valide que el user pertenece a ese institute, y devuelve nuevo JWT con claim institute = seleccionado[25]. Este método encaja si el backend internamente siempre filtra por token.institute.
o	Revisar cómo está hecho ahora: si en cada servicio se usa user.institute_id del token para queries, cambiar a un modelo multi complicaría muchas funciones.
o	Por simplicidad, quizás mantener enfoque actual (token con único institute) y usar re-login (switch) es más seguro a corto plazo.
•	Implementación minimal:
o	Backend: GET /api/users/me/institutes (como arriba). Y si optamos por switch vía token: POST /api/users/switch-institute/{inst_id} que genera token nuevo. Este necesita la clave JWT secret, etc., pero reutilizando la generación del login.
o	Frontend: Tras login, si institutes.length > 1, mostrar modal “Seleccione Institución” con opciones. Al elegir, si usamos token switching, llamar endpoint y reemplazar token; si no, simplemente guardar en contexto el instituteId elegido para usar en próximas llamadas.
o	Agregar en la UI (quizás en el header, esquina superior) el nombre del instituto activo con un dropdown para cambiarlo[84].
o	Ajustar servicios frontend, por ejemplo:
o	En courseService.getCourses() pasar el instituteId actual para que consulte solo cursos de ese institute (o llamar a ruta con ID).
o	Similar en classService, subjectService etc., asegurarse de filtrar.
o	Documentar: de momento, un profesor con multi-instituto deberá cambiar manualmente de contexto para ver cada set de cursos. No mezclar datos.
o	Si falta tiempo: se puede posponer la implementación real; en cuyo caso, instruir a usar cuentas separadas temporalmente. Pero lo planificamos aquí para completitud.
•	(F) Selector de Instituto en UI:
Como mencionado:
•	Después del login (o registro) de un profesor/admin, si la lista de institutos > 1, mostrar modal de selección.
•	O siempre mostrar en navbar un menu donde aparece el instituto actual y al hacer click permite cambiar.
•	Este componente consultará quizás un estado global (lista de institutos ya traída en /me) para opciones.
•	Al cambiar, debe refrescar los datos (cursos, clases) para el nuevo contexto. Probablemente recargar la página o volver a dashboard y trigger fetches con el nuevo ID.
•	(F) Correcciones y Pulido de Textos/Componentes:
•	Hacer un pasada general por la aplicación buscando cualquier texto placeholder en inglés o latiguillos, y reemplazar con formulaciones claras en español. Estandarizar terminología (ej.: usar siempre “módulo virtual” en lugar de a veces “curso” equivocadamente).
•	Mejorar loaders/spinners donde las acciones tardan (por ejemplo, al generar contenidos con IA, asegurar que hay algún indicador visible además de los toasts).
•	Revisar consistencia de botones, modales, etc., para una experiencia más pulida.
•	(B) Dashboard con datos reales:
Implementar en backend consultas para alimentar las estadísticas de los dashboards:
•	Podría crearse un servicio AnalyticsService o usar dashboards/services.py. Algunos métodos:
o	getStudentDashboardData(student_id): calcula % progreso en cada curso (usando VirtualModule.progress si se almacena, o derivarlo de temas completados vs totales), promedio de calificaciones (ej: media de ContentResults de evaluaciones formales, filtrar por session_type evaluative), total de días de estudio (distintos días con actividad).
o	getTeacherDashboardData(teacher_id): nº de cursos, nº total de estudiantes (sumando sus clases), promedio general de calificaciones recientes (quizá tomar última evaluación de cada curso), etc.
o	getInstituteDashboardData(admin_id): si fuese necesario para admins, total de usuarios, etc.
•	Hacerlo eficiente; si los cálculos complejos llevan tiempo, considerar almacenarlos o simplificarlos. Por MVP, incluso poner valores simples como “Cursos: X, Estudiantes: Y” es aceptable.
•	Exponer vía endpoints (GET /api/dashboard/student, /api/dashboard/teacher).
•	Asistencia: Decidir sobre el widget de asistencia:
o	Opción 1: Ocultarlo del frontend por ahora para no mostrar 0% vacío.
o	Opción 2: Implementar un modelo Attendance básico:
o	Un schema attendance_records con class_id, date, present_student_ids (o inverso, absent_ids).
o	Endpoint para que el profesor marque asistencia de un día (lista de presentes).
o	Para e-learning puro quizás no tiene mucho sentido; probablemente se optará por eliminarlo de la interfaz hasta integrar con clases presenciales.
•	Perfil de aprendizaje en dashboard alumno: Si es viable, mostrar en el dashboard del alumno un resumen de su perfil cognitivo (ej. un gráfico de barras Visual/Auditivo/Kinestésico). Los datos ya los tenemos en cognitive_profile.
o	Esto sería un toque interesante: un componente que lea el perfil (posible via endpoint GET /api/cognitive_profile/{student_id}) y muestre “Estilo de Aprendizaje: 40% Visual, 30% Auditivo, 30% Kinestésico” y quizá sus fortalezas listadas.
o	No prioritario, pero deseable para enfatizar la personalización.
•	(F) Notificaciones UI (estructura):
Aunque la funcionalidad push se pospone, podemos implementar un icono de notificaciones ya, para el futuro:
•	Un icono campana en la barra superior. Al hacer click, despliega un dropdown (o panel lateral) con lista de notificaciones (cargadas de un endpoint simulado).
•	De momento podría mostrar notificaciones dummy (ej: “Bienvenido a SapiensIA!”) o las básicas como “Contenido generado con éxito” si queremos reutilizar los toasts.
•	Preparar esto para luego llenarlo cuando tengamos eventos reales (desbloqueos, calificaciones, etc.). Por ahora, dejarlo no muy prominente si no muestra mucho.
Con Fase 2 completa, la plataforma estará lista para usuarios reales con distintas necesidades: podrán registrarse sin Google, profesores podrán manejar varios institutos (con cierto trabajo manual), y la interfaz se verá profesional y con datos significativos. Esto allana el camino para atraer usuarios y construir sobre una base sólida.
Fase 3: Extensiones Avanzadas (IA Avanzada, Marketplace, App Móvil)
Objetivo: Desarrollar las funcionalidades de alto valor agregado una vez que el núcleo esté estable. Aquí abordamos la corrección automática completa con IA, la apertura de la plataforma mediante marketplace y plantillas compartidas, y el inicio del aplicativo móvil.
•	(B) Corrección Automática de Exámenes (completa):
Expandir la implementación dummy previa con integración real:
•	OCR de imágenes: Integrar una librería o API para reconocimiento de texto en imágenes. Opciones:
o	Google Cloud Vision API: precisa credenciales y es muy precisa con manuscrita (en cierto grado).
o	Tesseract OCR: open-source, se puede instalar pero su precisión en manuscrita varía.
o	Quizá permitir ambos (cloud vs local) según configuración.
o	Al procesar, extraer el texto y guardarlo en el Resource.metadata o en un campo text_extracted[18].
•	Preparar Prompt IA: Construir un prompt con:
o	El texto extraído de la respuesta del alumno.
o	Los criterios de evaluación. Si implementamos rubricas estructuradas, pasarlos en formato JSON o texto. Si solo hay un documento de guía, extraerlo también como texto.
o	Pedir al modelo (GPT-4 o similar vía OpenAI API) que devuelva una evaluación. Ejemplo de respuesta esperada: JSON con campos score y feedback detallado.
•	Llamada al modelo: Usar una librería de OpenAI (o PaLM) para enviar el prompt. Manejar la latencia (puede tardar algunos segundos).
•	Procesar respuesta: Parsear el JSON o texto devuelto para obtener la calificación. Asegurar consistencia (ej: si devolvió un número sobre 10, convertirlo a 0-1 escala).
•	Crear ContentResult: Igual que antes, guardar score y feedback de IA.
•	Notificar resultado: Esto puede hacerse actualizando el estado de la entrega (EvaluationResource) a “graded”.
•	Errores: Si la respuesta de IA es vacía o confusa, marcar error. Si el OCR no pudo leer nada (caso extremo), quizá setear un flag “auto_grade_failed”.
•	Seguridad: Verificar que solo se procese OCR si el archivo es imagen o PDF, y que ese resource pertenece a la evaluación indicada (no permitir que un usuario malicioso envíe cualquier resource_id).
•	Considerar usar un sistema de jobs asíncronos más robusto en esta parte, para no bloquear peticiones web. Una idea: mantener una colección grading_jobs con estado “pending/running/done”, procesada por un hilo aparte o un script cron. Dado el alcance, quizás implementarlo sin colas dedicadas pero con un approach no bloqueante (hilos + polling front).
•	(F) Interfaz de Revisión por IA:
En la vista del profesor para evaluaciones con entregas:
•	Mostrar junto a cada entrega un indicador si se ha auto-corregido. Por ejemplo, “Corrección automática: 8/10 (pendiente de aprobación)”.
•	Permitir al profesor ver el feedback generado.
•	Botones: “Aceptar calificación” – guarda tal cual (quizá simplemente confirma que ese ContentResult es definitivo), “Modificar” – abre un campo para editar la puntuación y/o feedback manualmente y luego guardar.
•	Este flujo requiere que distingamos calificaciones provisionales de IA vs finales. Podría hacerse guardando ContentResult con un flag provisional hasta que el profesor confirme. O más sencillo: no crear ContentResult hasta que el profesor acepte; en su lugar, almacenar el resultado IA temporal en algún campo (o en EvaluationResource).
•	Sin embargo, dado que queremos notificar al alumno rápido, tal vez mejor crear el ContentResult inmediatamente con nota IA y un campo feedback con aclaración. El profesor al modificar podría simplemente actualizar ese ContentResult (o borrarlo y reemplazarlo). ContentResultService.record_result debería admitir update de feedback.
•	En todo caso, construir la UI para visualizar y ajustar es el desafío principal.
•	(F) Aplicación Móvil (inicio):
Comenzar un proyecto React Native (Expo es una buena opción para rapidez):
•	Configurar la base del proyecto con TypeScript.
•	Implementar Login: Pantalla de login que llama a los mismos endpoints JWT (email/pass login, y quizás podría ofrecer “Continuar con Google” vía Expo AuthSession, pero se puede dejar solo email inicialmente para simplicidad).
•	Tras login, dependiendo del rol:
o	Si profesor: Mostrar lista de evaluaciones pendientes de calificar (llamar a un endpoint como /api/evaluations?pending=true&teacher_id=). Podría listar solo evaluaciones de tipo entrega vencidas sin nota.
o	Al seleccionar una evaluación, mostrar la lista de alumnos sin nota.
o	Al seleccionar un alumno, abrir cámara para capturar imagen. Expo proporciona Camera API para esto.
o	Tras tomar la foto, llamar al endpoint de submit entrega (similar al flujo web, pero podemos tener un endpoint directo móvil: e.g. POST /api/evaluations/{eval_id}/grade-image que combine subir y calificar en uno). O hacerlo en dos pasos: subir Resource y luego llamar al de submit ya existente.
o	Recibir respuesta (inmediata o tras polling) con la nota. Mostrarla en pantalla móvil con opción “Guardar” para confirmar (equivalente a aceptar).
o	Este flujo se apoyará en la lógica de auto-corrección ya hecha en backend.
o	Si estudiante: Podríamos en esta fase no implementar todo el módulo virtual en móvil, pero quizás algo:
o	Mostrar lista de sus cursos y módulos. Permitir ver contenidos textuales y quizzes en una vista simple.
o	Alternativamente, por MVP móvil inicial, centrarse solo en el caso profesor.
•	Esta fase mobile es un proyecto en sí, se puede paralelizar. Para fines de este plan, se enumeró qué debe hacer en la app, pero la prioridad es la corrección de exámenes que justifica la app. La experiencia completa de alumno en móvil puede dejarse para más adelante (o proveer un link que abra el sitio web en el navegador móvil como solución temporal).
•	(B) Marketplace de Cursos (Back-end):
Preparar la infraestructura para compartir cursos:
•	Campo is_public: Añadir a StudyPlan (o a Course según el modelo) un boolean is_public y posiblemente price (decimal) if courses can have cost.
•	Endpoint listar cursos públicos: GET /api/public/courses que devuelve los planes públicos con info básica (nombre del curso, nivel/materia, nombre del profesor autor, quizás rating si hubiera). Filtrar solo is_public=True.
•	Endpoint suscribirse a curso público: Este es complejo, posible enfoques:
o	Si usamos un pseudo-institute global: por ejemplo, todos los cursos públicos pertenecen a un instituto “Marketplace” visible para todos. Entonces, al suscribirse un alumno:
o	Se crea un VirtualModule para ese alumno en el módulo correspondiente sin necesidad de matricularlo formalmente en la clase original. Para esto, permitir en VirtualModuleService.create_module pasar un study_plan_id (del curso público) y un student_id externo. Ya que la verificación actual comprueba que el plan exista y luego inserta VirtualModule[85], podría funcionar directamente, aunque no pertenezca a la institución. Habría que omitir chequeos de pertenencia.
o	Alternativamente, hacer al alumno miembro de una clase genérica de ese plan. Quizá lo más seguro: crear una Class especial “Inscritos externos” asociada al curso, añadir al alumno allí para formalidad (y para que los ContentResults y demás lo consideren).
o	Si optamos por copiar el contenido:
o	Crear un nuevo Plan de estudio bajo el instituto personal del alumno (o Academia Sapiens), clonando todos los módulos, temas y contenidos del plan público. Luego generar su módulo virtual. Esto garantiza aislamiento, pero duplica datos y el alumno no recibe actualizaciones si el autor cambia el curso.
o	Dado el tiempo, parece mejor la primera: un curso público se comporta como un MOOC, todos los inscritos acceden al mismo contenido base.
•	Permisos: Permitir que usuarios de fuera puedan leer los contenidos de un plan público. Actualmente quizás check_study_plan_exists y otras funciones asumen que solo miembros pueden. Podríamos aflojar: si plan.is_public, permitir lectura sin ser miembro.
•	No implementar pagos aún aquí; asumir gratuitos o usarlo solo para libres.
•	(F) Marketplace UI:
•	Añadir una página “Marketplace” accesible desde landing o dashboard, donde se listan cursos públicos.
•	Permitir filtrar por categoría, buscar por nombre.
•	Cada curso con botón “Inscribirse” (si no está inscrito ya). Al hacer clic:
o	Si no logueado, redirigir a registro (quizá señalando que se registra como estudiante particular).
o	Si logueado estudiante, llamar al endpoint suscribirse. Luego navegar a la vista del curso inscrito (que puede ser el mismo módulo virtual ya iniciado).
•	Añadir en dashboard del estudiante sección de “Cursos externos inscritos” separados de los de su institución.
•	Para profesores: en su lista de cursos, permitir marcar los suyos como públicos (un toggle “Publicar en Marketplace”). Quizá con confirmación “cualquiera podrá inscribirse”.
•	UI de publicación: si se admite precio, poner campo de precio; pero inicialmente asumir todos gratis.
•	Esto convierte la plataforma en un estilo Coursera/Udemy académico. Es bastante trabajo; se puede planear en esta fase final y ajustar alcance según recursos.
•	(B) Plantillas de Juegos/Simulaciones:
Estructurar la funcionalidad de plantillas:
•	Modelo GameTemplate: crear colección game_templates con campos: título, descripción, autor_id, resource_id (enlace al archivo del juego), metadata (tipo de juego, variables paramétricas).
•	Endpoints:
o	POST /api/games/templates: para que un profesor cree una plantilla. Podría requerir primero subir un Resource (zip con juego, por ejemplo) y luego enviar resource_id junto con metadata.
o	GET /api/games/templates (y filtrado, e.g. por autor o por palabra clave) para listar.
o	POST /api/games/templates/{id}/publish para marcar una plantilla como compartida públicamente (así otros la ven).
•	Uso de plantillas en generación de contenido:
o	Cuando un profesor genera contenido de un tema y selecciona tipo “Juego”, se podría ofrecer la opción de usar una plantilla existente. Implementarlo podría ser complejo de integrar con la generación IA actual. Alternativa:
o	Añadir en la UI de creación de contenido un botón “Usar Plantilla de Juego” que abre lista de plantillas (propias o públicas).
o	Al elegir una, hacer que el backend cree un TopicContent para ese tema de tipo “game” y copie el Resource de la plantilla (o referencie al mismo). Probablemente duplicar el resource para mantener independencia.
o	Quizá permitir editar algunos parámetros; esto requeriría que la plantilla defina variables (p.ej., preguntas, nivel de dificultad) que se puedan alimentar. Eso implicaría o bien un prompt a IA que rellene o simplemente un formulario.
o	Dado lo complejo, se puede dejar planteado como subproyecto paralelo. Lo importante es tener la base de compartir juegos, que ya es valor agregado.
•	Nota: Como este sistema no es crítico para el funcionamiento básico, su implementación podría ser simultánea a la app móvil o pospuesta tras las demás.
•	(B) Roles Individuales (Profesor+Alumno):
Extender la lógica de registro para manejar usuarios duales:
•	Cuando un profesor particular crea un curso para sí mismo, implementar lo mencionado:
o	Crear un instituto “Personal de {Nombre}” y una clase dentro con él mismo inscrito.
o	Asignarle en institute_members como TEACHER y también en class_members como STUDENT.
o	Adaptar el JWT o sesión para reconocer ambos roles (por ejemplo, guardar array roles = [TEACHER, STUDENT]).
o	Frontend: Si detecta que un usuario tiene rol dual, mostrar interfaz para cambiar de modo. Ej: un toggle en header “Modo Profesor / Modo Alumno”.
o	En modo Profesor: ver sus cursos, generar contenido, etc.
o	En modo Alumno: ver los módulos virtuales de sus cursos como estudiante (en este caso, su propio curso).
o	Con un solo usuario jugando ambos papeles, hay que tener cuidado de no confundir datos (pero dado que es solo él en su clase, no hay conflicto real).
•	Esto habilita el caso de uso autodidacta completamente: un usuario puede crear su curso y luego cursarlo.
•	(F) Landing Page & Pago:
•	Diseñar una landing page atractiva:
o	Mensaje de valor, características (por ej. “Tutor virtual inteligente”, “Aprendizaje adaptativo”, “Para profesores innovadores” etc.), quizás ilustraciones.
o	Botones de llamada a la acción: “Quiero probar como Profesor”, “Quiero aprender como Estudiante”. Cada uno dirigiendo al flujo de registro correspondiente.
o	Secciones de planes/precios: tabla comparando Plan Instituto vs Particular vs Estudiante. (Aunque no implementemos pagos ahora, al menos mostrar “Gratis durante beta” o algo así).
o	Footer con info de contacto, etc.
•	Configurar la ruta inicial de Next.js para que muestre esta landing cuando no haya usuario logueado. Si hay token activo, redirigir inmediatamente al dashboard interno.
•	Integrar pago (opcional esta fase): Si se decide avanzar:
o	Crear cuenta Stripe, productos para los planes.
o	En el flujo de registro de instituto, después de llenar datos, llamar a un backend endpoint /api/stripe/create-checkout-session?plan=institute que use Stripe SDK para crear una sesión de pago (con success_url retornando a alguna página).
o	Mostrar un componente <StripeCheckout> o redirigir a la URL de Checkout.
o	Backend: implementar /api/stripe/webhook para escuchar eventos de pago, verificar completados y activar la cuenta (ej. marcar institute como paid, etc.).
o	Esto es bastante trabajo de integración y probablemente se omita hasta tener usuarios reales dispuestos a pagar.
•	(B) Asistencia y otros indicadores:
Si se decidió implementar asistencia:
•	Crear modelo y endpoints como ya se discutió (Attendance model, mark attendance).
•	UI: en vista profesor curso, una pestaña “Asistencia” con lista de alumnos y checkboxes por fecha.
•	Dado que esto se aparta del enfoque online, quizás es mejor eliminarlo por ahora como se notó antes. Incluirlo aquí solo si alguna institución lo requiere.
•	(F) Extensión de App Móvil:
Más allá de la POC inicial:
•	Añadir gradualmente funcionalidades de alumno: un listado de módulos->temas->contenidos y visores adaptados. Se podría reutilizar componentes web vía React Native Web or just mimic them.
•	Incluir notificaciones push (especialmente para avisar de calificaciones o nuevos contenidos).
•	Esto seguramente excede el MVP, pero se deja planificado.
________________________________________
Coordinación y Consideraciones Finales:
- Se recomienda implementar por fases incrementales como arriba. Primero garantizar que no quedan errores lógicos ni features incompletos en el core (Fase 1). Por ejemplo, probar con un caso real: profesor sube temario, genera contenidos, alumno los cursa, se registran resultados, profesor crea una evaluación, alumno envía entrega, profesor pone nota. Pulir esa ruta hasta que funcione sin contratiempos. - Reutilización de código: En cada tarea, checar si ya existe funcionalidad similar: - Antes de escribir un nuevo endpoint, buscar en el código por algo parecido. Ej: antes de hacer /submit, ver si en study_plans/routes.py ya había algo para submissions que se comentó; quizás se puede rescatar parte[16]. - Evitar duplicar servicios: si ResourceService existe, usarlo para subir archivos en vez de escribir lógica repetida. - Si se necesita un nuevo modelo o campo, verificar si no hay uno existente que sirva. Ej: para notificaciones, tal vez ya hay un modelo inactivo. - Eficiencia: Revisar consultas en bucle que puedan optimizarse con índices o agregaciones. Con pocos datos no se notará, pero con muchos estudiantes generando contenidos, hay que cuidar no colapsar con triggers mal manejados. La cola de generación ya se optimizó centralizándola (eliminando duplicados)[86]. - Pruebas: Tras cada fase, realizar pruebas integrales: - Fase 1: pruebas unitarias de generación de módulo, de personalización aplicada (ver que el VirtualTopicContent coincide con perfil), de completar contenidos genera resultados, etc. Probar flujos multiusuario si posible (varios alumnos en un curso). - Fase 2: probar registro/login, cambio de instituto, roles duales. Asegurar que token y permisos funcionan. - Fase 3: probar auto-corrección con imágenes de ejemplo, etc. - Documentación actualizada: Conforme se implementen todos estos cambios, actualizar la documentación en la carpeta completar_sapiensia o Wiki del proyecto para que refleje el estado final. Especialmente porque la documentación previa estaba algo desactualizada y este análisis reenumeró requisitos. Elaborar guías de uso de nuevas funciones (ej. “Cómo publicar un curso”, “Cómo usar la app móvil”).
En conclusión, siguiendo este plan detallado se cubrirán todos los requerimientos establecidos – desde la experiencia principal de módulos virtuales personalizados, pasando por el robustecimiento de evaluaciones y resultados, hasta las expansiones innovadoras de corrección con IA y marketplace. Cada paso se dio con miras a minimizar cambios redundantes, reusar lo existente (por ejemplo, usar ContentResult para todo tipo de nota, usar Resources para archivos, etc.) y mantener la lógica consistente. También se identificaron y corrigieron ciertas inconsistencias (como endpoints duplicados, roles mal escritos, o filtrado de perfil inicialmente errado) para asegurar que la aplicación sea lógica y eficiente.
Con esta hoja de ruta, el equipo de desarrollo puede proceder fase a fase, verificando en cada etapa la integración entre frontend y backend (p. ej., endpoints de evaluaciones y sus componentes UI asociados) para lograr que “todo funcione” armónicamente. Ningún detalle clave quedó fuera en este análisis, abarcando desde las reglas pedagógicas de personalización hasta consideraciones de diseño de producto (landing, pagos, mobile). Ahora la prioridad es implementar según lo planificado, probando continuamente con usuarios de ejemplo, para finalmente lanzar una plataforma SapiensIA completa, estable y preparada para escalar. [87][88]
________________________________________
[1] [2] [3] [4] [8] [9] [10] [11] [12] [13] [14] [17] [18] [19] [20] [21] [22] [23] [24] [25] [26] [27] [28] [29] [30] [32] [33] [34] [35] [36] [37] [38] [41] [44] [45] [46] [51] [52] [53] [54] [69] [70] [71] [72] [73] [74] [77] [78] [80] [82] [83] [84] [87] [88] implementacion.md
https://github.com/Luisdanielgm/sapiens-backend/blob/64509395367f69bbb14413b279d884c6f01c8517/completar_sapiensia/implementacion.md
[5] [6] [7] [39] [40] [50] [56] [57] [58] [59] [61] [62] [63] [64] [65] [66] [79] [85] services.py
https://github.com/Luisdanielgm/sapiens-backend/blob/64509395367f69bbb14413b279d884c6f01c8517/src/virtual/services.py
[15] [16] [31] [49] [55] [60] [67] [68] [76] [86] FASE_1_IMPLEMENTACION_RESUMEN.md
https://github.com/Luisdanielgm/sapiens-backend/blob/64509395367f69bbb14413b279d884c6f01c8517/completar_sapiensia/FASE_1_IMPLEMENTACION_RESUMEN.md
[42] [43] [75] concentrationContext.tsx
https://github.com/Luisdanielgm/sapiens-frontend/blob/ecbcd96f9011ed1aea094c0e12c40e0b6ddf3c72/src/context/concentrationContext.tsx
[47] [48] [81] useProgressiveGeneration.ts
https://github.com/Luisdanielgm/sapiens-frontend/blob/ecbcd96f9011ed1aea094c0e12c40e0b6ddf3c72/src/hooks/useProgressiveGeneration.ts
