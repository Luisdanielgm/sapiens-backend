Requerimientos de la Funcionalidad (Generación de Contenido Teórico y Diapositivas)

Guardar contenido teórico correctamente: Al generar el contenido teórico de un tema mediante LLM, el texto resultante debe almacenarse como string en el campo theory_content del Topic. Actualmente se está guardando "[object Object]" por un error de serialización
GitHub
, lo cual hay que corregir. No se debe crear una entrada separada de tipo “texto” en los contenidos; el contenido teórico irá únicamente en el Topic.

Generación automática de diapositivas y quiz: Al generar contenido teórico de un tema, el sistema debe automáticamente producir una presentación (diapositivas HTML) y una evaluación tipo quiz. Estas son componentes obligatorias para “virtualizar” un módulo estudiantil. En particular: primero se obtiene el texto teórico completo; luego se divide ese texto en fragmentos (subtemas) y se genera un plan de diapositivas con estilo (paleta de colores, tipografías, layout general); a partir de ese plan se crean las diapositivas individuales (HTML) y una narrativa por diapositiva; finalmente se genera el quiz, asegurando que salga de último una vez listas las narrativas
GitHub
.

Uso correcto de los workers LLM: La orquestación debe explotar el pool de 5 workers en frontend. El flujo deseado es secuencial por fases y luego paralelo: (a) un único worker genera el contenido teórico; (b) se divide el texto y se obtiene el plan/estilos base de las diapositivas con otro llamado LLM; (c) guardar en base de datos todas las diapositivas “esqueleto” (texto completo de cada fragmento + snapshot de estilos, sin HTML todavía); (d) en paralelo con hasta 5 workers, generar el HTML creativo de cada diapositiva (pasando el texto fragmento + estilos de referencia como prompt) – tras cada generación actualizar la diapositiva con content_html y marcarla html_ready; (e) en paralelo (5 workers), generar el texto narrativo de cada diapositiva (usando el HTML + texto como contexto) y guardarlo – marcar narrative_ready; y (f) cuando todas las narrativas estén listas, lanzar la generación del quiz final
GitHub
GitHub
. Importante: configurar el dispatcher de tareas para no encolar el quiz antes de tiempo; el quiz solo inicia cuando ningún slide está pendiente de narrativa
GitHub
GitHub
.

Almacenamiento estructurado de las diapositivas: Cada diapositiva generada debe almacenarse como documento independiente en la colección topic_contents (content_type = "slide"). Según los lineamientos, cada documento de diapositiva contendrá: el texto completo del fragmento (full_text), un snapshot de estilo (template_snapshot con colores, fuentes, etc. de referencia), el HTML generado (content_html), el texto narrativo (narrative_text), un flag render_engine indicando que es HTML crudo ("raw_html"), el orden dentro de la presentación (order) y referencias al tema (topic_id y agrupación parent_content_id común)
GitHub
GitHub
. Inicialmente tras el plan se guardan como “skeleton” (solo texto y estilos); luego se actualizan a html_ready y narrative_ready conforme se llenan los campos HTML y narrativa
GitHub
GitHub
.

Diapositivas creativas con estilo consistente: El HTML de cada diapositiva debe ser generado por el LLM siguiendo el estilo base definido en el plan pero con libertad creativa en el diseño. Es decir, pasar en el prompt de cada slide la paleta de colores, tipografía, layout base e íconos permitidos (la plantilla) como referencia, pero no reutilizar literalmente el HTML de la plantilla
GitHub
. El resultado debe ser código HTML completo y semántico (secciones, listas, etc.), adaptado al contenido de ese fragmento (ej.: puede incluir listas, cuadros, mini diagramas ASCII, etc.)
GitHub
. Todas las diapositivas deben compartir el mismo estilo visual (mismos colores, fuentes, tamaño de slide), cumpliendo con los parámetros dados en el plan.

Narrativa por diapositiva: Por cada diapositiva HTML generada, producir un texto narrativo que describa o explique la diapositiva en tono de voz pedagógico, como si fuera un instructor hablando. Esta narrativa (90–150 palabras aprox.) debe correlacionar el contenido de la diapositiva con los conocimientos base del tema
GitHub
. Se almacenará en el campo narrative_text de la diapositiva y posteriormente podría usarse para generar audio locutado.

Visualización en el módulo del profesor: En la vista del profesor (generación de topics), tras generar el contenido teórico y sus diapositivas, el visor de presentación debe mostrar las diapositivas generadas. Si existe HTML de diapositivas (content_html), el SlideContentViewer debe renderizarlo directamente (por ejemplo, usando dangerouslySetInnerHTML con las precauciones de sanitización)
GitHub
. En caso de no haber HTML (p.ej. diapositivas legacy solo con texto), debe haber un fallback para mostrar al menos el texto o una indicación. Actualmente esta vista no está mostrando nada porque solo tenía JSON sin HTML. Hay que corregirlo para soportar el nuevo formato.

Visualización en el módulo del estudiante: En la interfaz de alumno (módulo virtual), asegurar que al virtualizar un topic con contenido teórico generado, se muestren las nuevas diapositivas HTML y el quiz. Un módulo podrá considerarse “virtualizable” cuando tenga al menos el contenido teórico (teoría), sus diapositivas generadas y el quiz listos. La lógica de frontend debe reconocer que hay contenidos tipo slide disponibles y habilitar la pestaña de “Diapositivas” para el estudiante. En la vista de contenido del alumno, debe poder navegar todas las diapositivas generadas (idealmente en formato presentación navegable). Nota: No se debe romper la funcionalidad de personalización (virtual_topic_contents, etc.); simplemente integrar estas nuevas diapositivas al flujo existente de virtualización sin eliminar nada de personalización ya implementada.

Refactor de “Juegos y Simulaciones” a plantillas: El sistema original tenía contenidos interactivos etiquetados como “games” o “simulations”. La nueva dirección es manejarlos como plantillas (templates) de contenido interactivo. Se requiere gradualmente eliminar o migrar referencias a juegos/simulaciones en favor de plantillas. Por ejemplo, la vista de “Juegos y Simulaciones” debe rediseñarse como “Mis Plantillas”, mostrando un catálogo de plantillas interactivas reutilizables
GitHub
. Los contenidos nuevos de tipo juego/simulación se integrarán vía plantillas (por ejemplo, generando contenido interactivo basado en una plantilla seleccionada, en lugar de un “game” ad-hoc). En resumen, hay que planificar la transición: retirar funciones legacy de generateGame/generateSimulation, reutilizar esa UI para plantillas, y asegurarse que el backend/DB soporte la creación y uso de plantillas (modelo Template, TemplateInstance, etc.) en lugar de content_type específicos de juegos.

Estado Actual vs. Requerimientos (Desviaciones Identificadas)

Actualmente, la implementación tiene varias fallas y desviaciones respecto a los requerimientos arriba:

Contenido teórico mal guardado: Al presionar “Generar Contenido Teórico” en un topic, el texto se obtiene correctamente del LLM, pero al guardarlo en la base de datos termina como "[object Object]" en el campo theory_content
GitHub
. Esto indica que se está pasando un objeto en lugar de string en algún punto (posiblemente el resultado del LLM no se maneja bien). Como resultado, el contenido teórico no se guarda correctamente en el Topic. Además, en paralelo el frontend crea un TopicContent de tipo text con ese mismo contenido – algo no deseado. En resumen: debe guardarse solo en Topic.theory_content (string) y actualmente no ocurre así (hay un objeto serializado incorrectamente y una entrada redundante).

Generación de diapositivas desalineada: La lógica actual de TopicGeneration sigue usando el flujo heredado secuencial y simplificado. El hook useTopicContent llama a generateSlides (no la versión nueva) que: divide el texto en párrafos, y por cada subtema invoca generateIndividualSlide. Esta función no llama al LLM para HTML ni narrativa reales; en su lugar, crea directamente un objeto JSON para cada diapositiva con title, content (texto bruto) y una narrative_text muy básica (un resumen de 200 caracteres)
GitHub
GitHub
. Luego esas diapositivas se guardan vía createTopicContent con un slide_template fijo (colores dummy) y status “draft”
GitHub
GitHub
. Problemas: (1) No se genera HTML ni se usan los 5 workers en paralelo – todo es síncrono y simplificado; (2) El campo content de cada diapositiva contiene un objeto con título y texto en vez de un string HTML; (3) La narrativa no aprovecha el HTML final ni la IA (es un simple recorte del texto)
GitHub
. Esto explica por qué en la base de datos aparecía "[object Object]": ese objeto JSON probablemente al mostrarse se serializa mal.

Orden de generación del quiz incorrecto: En la implementación actual, la generación del quiz puede dispararse antes de finalizar las diapositivas. De hecho se observó que el quiz a veces aparece antes de que todas las slides estén listas. Esto es un bug reconocido: el quiz debería generarse al final, cuando ya se tienen las preguntas basadas en todo el contenido del tema. La falta de control de dependencia en la cola de tareas provoca esta condición
GitHub
. Actualmente el código no impone que el quiz espere a las narrativas, por lo que se “cuela” tempranamente.

Visor de diapositivas (profesor) no funcional: La vista del profesor para las diapositivas generadas no está mostrando nada útil. Dado que las diapositivas se guardaban solo con JSON (sin HTML), el componente SlideContentViewer no renderiza contenido. Según la especificación debería renderizar el HTML si existe o mostrar un fallback si no
GitHub
, pero hoy no sucede (posiblemente porque no había HTML alguno). En la rama actual, el código del viewer espera quizá un array de slides con content_html, que nunca llega. En suma, el profesor no puede previsualizar las diapositivas generadas automáticamente, lo cual contradice el requerimiento de tener un visor integrado.

Contenido en el módulo del estudiante incompleto: En la interfaz del alumno, las pestañas de contenido (Teoría, Diapositivas, Quiz, etc.) se habilitan según los contenidos disponibles. Actualmente, dado que las diapositivas generadas no tienen content_html, puede que la pestaña “Diapositivas” ni aparezca o quede vacía. El código del frontend estudiante filtra los contenidos por tipo y muestra cada slide mediante UniversalContentViewer
GitHub
GitHub
. Si cada slide content tiene solo JSON sin HTML, el viewer posiblemente no renderiza nada. Es decir, el estudiante no ve las diapositivas generadas automáticamente. Además, el sistema de virtualización espera ciertos campos para considerar “completo” un topic (content_completeness_score, etc.), los cuales quizá no se actualizan correctamente al no haber HTML/quiz final. Esto impide cumplir la idea de que con teoría+slides+quiz el alumno ya pueda ver el módulo virtual.

Referencias legacy a juegos/simulaciones: El código todavía maneja “games” y “simulations” como tipos de contenido separados. Por ejemplo, en el módulo estudiante existen pestañas para juegos y simulaciones
GitHub
 y en la vista del profesor hay modo viewMode: 'juegos' y 'simulaciones' con funciones para cargar contenidos de esos tipos
GitHub
GitHub
. Sin embargo, en la nueva visión esos deben integrarse como plantillas. Esta discrepancia genera confusión y complejidad: se tienen componentes como GameContentViewer/SimulationContentViewer legacy. Actualmente no hay generación automática de “games” salvo que el profesor manualmente suba uno, pero mantener ese código separado ya no es deseable. En resumen, el estado actual no refleja la transición a plantillas interactivas: la UI no unifica “Juegos y Simulaciones” bajo plantillas, y el backend tampoco (aunque hay modelos Template, no se están usando plenamente para reemplazar games). Esto requiere una refactorización para alinearse con la estrategia nueva.

(En síntesis, la situación actual es que se tienen algunas piezas preparatorias – p. ej. un generador unificado en código que soportaría HTML, un modelo TopicContent flexible con campos slide_template y render_engine
GitHub
 – pero no están siendo aprovechadas por la implementación vigente. Hace falta integrar esas piezas según los pasos requeridos.)

Plan de Implementación Propuesto

Resumen de la estrategia: Se abordará la solución en fases, enfocando primero correcciones urgentes (guardar contenido correctamente, eliminar lógica obsoleta), luego implementando el pipeline completo de generación de diapositivas con HTML/narrativa y ajustes de visualización, y finalmente refactorizando el manejo de contenidos interactivos (juegos/simulaciones) hacia plantillas. En cada fase se listan las tareas necesarias, separando claramente las de Frontend (F) y Backend (B). Asimismo, se indica dónde se puede trabajar en paralelo para agilizar desarrollo. Es prioritario no romper funcionalidades existentes (personalización, datos legacy), por lo que muchas tareas consisten en extender o desactivar en vez of eliminar por completo. A continuación, el plan detallado:

Fase 1: Correcciones Inmediatas en Generación de Contenido Teórico

Objetivo: Solucionar el bug de guardado de teoría y preparar el terreno eliminando lógica vieja de contenidos de texto. Esto garantiza que el contenido teórico se almacene bien y evita duplicaciones.

(F1) Corrección de serialización de teoría: Revisar la función de frontend que maneja la respuesta del LLM para el contenido teórico (p.ej. generateTopicContent en deepResearchService.ts). Asegurarse de que el resultado se convierta a string correctamente antes de enviarlo al backend. En específico, usar result.content || result.text apropiadamente y evitar pasar objetos directos. Si se detecta que cleanedContent puede ser objeto, forzar JSON.stringify o extraer la propiedad correcta para obtener el markdown puro. Resultado esperado: topic.theory_content recibe un string markdown válido (ya limpiado de backticks) y nunca más el valor literal "[object Object]". 
GitHub
(Se puede reproducir el flujo actual con logs para verificar que content ya no sea objeto).

(F2) Guardar teoría solo en Topic: Modificar el flujo de guardado para que, tras obtener el texto teórico, se llame únicamente al endpoint de actualizar el Topic (PUT /study_plans/topic_theory o similar) con el campo theory_content. No crear ninguna entrada en topic_contents de tipo texto. En el código del hook useTopicContent, esto implica eliminar o desactivar llamadas a funciones como createTopicContent(... 'text' ...) si existían (en la lectura del código no se vio explícito, pero confirmar). Tras esta corrección, cada tema tendrá su teoría en Topic.theory_content, sin contenido duplicado en la subcolección.

(B1) Verificación en backend (Topic model): Validar que el modelo Topic espera theory_content string (ya existe con default "" 
GitHub
). No se requieren cambios de esquema; solo asegurar que la ruta de API que actualiza la teoría (UPDATE_TOPIC_THEORY) toma el string del frontend y lo asigna directamente. Añadir controles en ese endpoint para rechazar si recibe un objeto. (Posiblemente ya hay logs en backend detectando el caso "[object Object]"
GitHub
, que servirán para pruebas).

(B2) Eliminar contenido “text” obsoleto: Si en la base de datos quedaron contenidos de tipo text (por la antigua implementación), decidir una estrategia: o bien migrarlos al campo Topic.theory_content correspondiente (quizá innecesario si Topic ya lo tiene completo), o simplemente no usarlos. Para no complicar, se puede dejar de considerar topic_contents de tipo text en las consultas. Por ejemplo, en TopicContentViewer del profesor, omitir cargar text en existingTextContents. (En loadExistingText() frontend, quizá mantenerlo para legacy, pero no mostrar nada en UI si estamos usando directamente Topic.theory_content). En suma, tras fase 1, el flujo principal ya no generará TopicContent text, quedando deprecado.

Paralelismo: Las tareas F1 y F2 son relacionadas (ambas en frontend: una prepara el string, la otra ajusta el guardado). Pueden hacerse en secuencia por un mismo desarrollador. B1 es simple verificación backend, no depende de otras tareas y puede hacerse en paralelo. B2 (ajuste de consultas) es opcional menor y puede hacerse junto con alguna de las anteriores sin conflicto.

Fase 2: Implementación del Pipeline Completo de Diapositivas (GenerateSlides V2)

Objetivo: Reemplazar la lógica antigua de generación de diapositivas por la nueva secuencia con tareas secuenciales/paralelas y HTML/narrativa, usando los 5 workers. Se dividirá en sub-fases A–E correspondientes al flujo requerido
GitHub
. También se implementarán los nuevos endpoints en backend para creación/actualización de contenidos de diapositiva.

Frontend (Actualizar Generación de Slides):

(F3) Desactivar flujo legacy: Inutilizar las funciones antiguas generateSlides y generateIndividualSlide en useUnifiedContentGenerator. Esto puede ser renombrándolas o removiendo su uso. En el hook useTopicContent, cambiar la llamada que antes hacía generateSlides() por la nueva función generateSlidesV2. Garantizar que la UI muestre el botón “Generar diapositivas (v2)” correctamente (el UniversalContentViewer ya cambia la etiqueta a Generar (v2) para tipo slide
GitHub
). Así evitamos seguir creando diapositivas JSON como antes.

(F4) Fase A – Contenido teórico → Plan de diapositivas: Dentro de generateSlidesV2, implementar la primera fase secuencial: tomar el topicContent (markdown teórico ya generado) y dividirlo en fragmentos lógicos. Usar una función como divideContentIntoFragments (puede basarse en la existente divideTopicIntoSubtopics pero adaptada para máximo detalle). Enviar un prompt al LLM para obtener un plan maestro de presentación: pedir que devuelva un desglose de diapositivas con estilo unificado. Simplificar: en lugar de JSON complejo, podemos solicitar una lista de características generales (fondo, color texto, fuente títulos/cuerpo, íconos sugeridos, etc.). Esta llamada se hace con un único worker. Recibir el resultado (podría ser markdown o JSON ligero) con la plantilla de estilo.

(F5) Fase B – Guardar skeletons de diapositivas: Tomar los fragmentos resultantes (texto de cada subtema) y el estilo de plan obtenido, y realizar un bulk insert en la colección de contenidos: crear un TopicContent para cada diapositiva con campos: content_type: "slide", full_text = texto completo del fragmento, template_snapshot = estilos de referencia (el plan, posiblemente como objeto/JSON), order = índice de diapositiva, parent_content_id = un identificador común (puede ser el Topic ID o un UUID para esa serie de slides), status: "skeleton", y render_engine: "legacy" por ahora (o un valor temporal indicando que aún no hay HTML). Este guardado debe hacerse mediante una nueva API en backend (POST bulk, ver más abajo). Desde frontend, llamar a /api/content/bulk pasando el arreglo de diapositivas. Tras éxito, el backend devolverá los IDs asignados a cada content; almacenarlos si se requiere. Nota: Esta inserción en lote marca el cambio de tener las diapositivas separadas en la DB desde el inicio, en lugar de agruparlas en un solo JSON.

(F6) Fase C – Generar HTML de cada diapositiva (paralelo): Para cada diapositiva skeleton creada, encolar una tarea LLM en el pool de workers. Deben poder correr hasta 5 concurrentes. Implementar un loop que recorra las diapositivas (fragmentos), y para cada una construya el prompt de HTML usando: el full_text de la diapositiva, más el template_snapshot (paleta, layout guía), más instrucciones de creatividad (por ejemplo, “usa listas, cuadros de texto, no incluir <script> ni iframes, etc.” siguiendo lo indicado)
GitHub
GitHub
. Llamar al modelo (puede ser workerPoolService.generateContent con tipo 'text' ya que devuelve HTML como texto). Al recibir la respuesta (HTML string), inmediatamente hacer una petición PUT al backend para actualizar esa diapositiva: endpoint /api/content/{id}/html con el cuerpo HTML generado. El backend deberá guardar ese HTML en el campo correspondiente y marcar status="html_ready" y render_engine="raw_html". En el frontend, manejar estas tareas de forma asíncrona: usar el WorkerPool/TaskQueue para que lance hasta 5 a la vez. Se puede aprovechar el sistema existente de notificaciones de progreso para cada tarea (p. ej., emitir eventos contentUpdateEmitter de progreso al 100% cuando cada HTML termine).

(F7) Fase D – Generar narrativas (paralelo): Similar a Fase C, pero ahora para cada diapositiva con HTML listo, encolar una tarea para obtener la narrativa. Prompt para LLM: proveer el content_html (posiblemente truncado o sin etiquetas?) más el full_text original, indicando que genere un párrafo hablado explicando la slide
GitHub
. Ejecutar hasta 5 en paralelo. Al recibir cada narrative_text, hacer PUT a /api/content/{id}/narrative para guardar el texto en la diapositiva correspondiente y marcar status="narrative_ready". Tras esto, la diapositiva está completa. También aquí utilizar events/toasts para indicar progreso. Idealmente, cuando todas las diapositivas de un tema alcancen narrative_ready, podemos emitir un evento de “all slides ready”.

(F8) Fase E – Generar Quiz al final: Implementar la lógica para que, una vez completadas todas las tareas anteriores, se genere el Quiz. Esto implica esperar hasta que no queden tareas pendientes en la cola de workers y que todas las diapositivas tengan narrative_ready. En ese momento, usar la función existente generateQuiz (o similar) para crear las preguntas basado en el contenido teórico completo (que ya tenemos). Asegurar que esta llamada ocurra último: p. ej., monitorizar en el workerPool o mediante un contador de tareas completadas. Detalle: No es necesario esperar a que todas las narrativas terminen si podemos iniciar el quiz apenas la última tarea de slide se lanza – pero para seguridad y simplicidad, sincronizarlo al final. Una vez obtenido el quiz (generalmente un JSON de preguntas), llamar al backend para guardarlo (probablemente vía createTopicContent con content_type: "quiz"). Esto ya existe en parte del código actual (generateQuiz en useTopicContent lo hacía de forma secuencial después de teoría). Ahora, integrarlo en el flujo automático.

(F9) Notificaciones y estado de generación: Mientras se ejecutan las fases B–E, actualizar la UI de progreso para el usuario. Refinar los toasts o banners de estado: por ejemplo, “Generando diapositivas: X%” durante Fase C/D, y “Generando evaluación” en Fase E. Utilizar el ProgressToastManager o el mecanismo unificado ya presente. Al terminar todo, mostrar “Contenido generado con éxito” o similar. También manejar errores: si un worker falla en una diapositiva, capturarlo y notificar cuál slide falló pero continuar con las demás. (El diseño de tareas paralelas debe tolerar que alguna falle sin abortar todo). Al final, podría haber opción de retry en caso de fallos individuales.

(F10) Viewer del profesor adaptado: Con el flujo anterior, ahora cada diapositiva tendrá HTML y narrativa guardados por separado. Ajustar la vista de TopicContentViewer en modo “presentación” para utilizarlos. Como indica el pseudocódigo actual, si existingSlidesContents.length > 1 y cada content tiene content_html y order, se debe agruparlas en una presentación completa
GitHub
. Ya existe una lógica condicional en el código: agrupa y usa <SlideViewer slides={groupedSlides} ... />
GitHub
. Habrá que asegurar que content.content_html y content.narrative_text están presentes en existingSlidesContents (tras load desde backend). Entonces esa rama hasMultipleIndividualSlides será verdadera y mostrará el visor. Posiblemente necesitemos implementar el componente <SlideViewer> (si no estaba completo) o usar el SlideContentViewer común. El objetivo es que el profesor pueda ver todas las diapositivas en un carrusel navegable. Acción: probar esta vista tras implementar lo anterior y depurar si algo no se muestra.

(F11) Viewer del estudiante (módulo virtual): Verificar la sección de VirtualModule/TopicContent que maneja las diapositivas. Actualmente carga slideContents con todos los contenidos tipo slide y los pasa a UniversalContentViewer
GitHub
. Dado que ahora slideContents tendrá objetos con HTML (campo content_html), el UniversalContentViewer → SlideContentViewer debería poder mostrarlos correctamente. Hay que ajustar el SlideContentViewer (componente común) para que si recibe content.slides vacío pero tiene un content_html en content, igualmente lo renderice. Podemos mejorar el SlideContentViewer para que en caso de una sola diapositiva en props, la muestre. Adicionalmente, ofrecer navegación entre slides para el alumno también sería deseable (podemos reutilizar el mismo SlideViewer/carousel con controles de navegación). Si eso es complejo, una primera versión puede listar todas las diapositivas una debajo de otra (como hacía antes) – pero dado que tendremos HTML rico, probablemente queden muy largas. Tarea concreto: Integrar el SlideContentViewer con soporte de “presentación completa”: e.g., pasarle slides=[...groupedSlides...] también en contexto estudiante, o usar el mismo componente <SlideViewer> en la pestaña “Diapositivas” del alumno. En cualquier caso, probar que hasSlideTab se activa y las diapositivas aparecen con estilo.

Backend (Nuevos Endpoints y Modelos):

(B3) Endpoint POST /api/content/bulk: Implementar un endpoint en backend que permita la creación masiva de contenidos. Por ejemplo /content/bulk que reciba un array de objetos con topic_id, content_type, full_text, template_snapshot, order, etc. En el servicio backend, iterar y hacer inserciones en la colección topic_contents. Se puede aprovechar que quizás ya exista un método utilitario (mencionan create_bulk_content en documentación
GitHub
). Asegurarse de devolver los _id generados de cada documento para que frontend pueda mapearlos. Incluir validaciones mínimas: que content_type sea “slide”, que traiga topic_id válido, etc.

(B4) Endpoint PUT /api/content/{id}/html: Este endpoint actualizará solo campos relacionados al HTML de una diapositiva. Recibirá content_html (string HTML generado). Debe ubicar el documento por ID y hacer update: set content_html = ese string, set render_engine = "raw_html", set status = "html_ready", opcionalmente set updated_at. Como implicación, habría que extender el modelo TopicContent para incluir content_html y narrative_text como campos almacenables (alternativamente, guardarlos dentro de content dict, pero es más limpio añadirlos de forma explícita). Dado que Pydantic model no se usó estricto (es una clase), podemos simplemente guardarlos en el documento Mongo. De hecho, el snippet de requerimientos listaba content_html y narrative_text como campos independientes
GitHub
. Implementar la lógica y retornar éxito.

(B5) Endpoint PUT /api/content/{id}/narrative: Similar al anterior, pero para actualizar la narrativa. Recibirá narrative_text (string). Hacer update: set narrative_text = texto, set status = "narrative_ready". (El campo render_engine probablemente ya estaba en raw_html desde antes, se mantiene). Con estas dos actualizaciones tenemos la capacidad de llenar progresivamente las diapositivas.

(B6) Validar estados y dependencias (quiz al final): Aunque la cola se maneja en frontend, es buena práctica que backend también valide algunas reglas. Por ejemplo, en el endpoint de generar quiz (si se implementa, ver B7) o en create_virtual_module, etc., verificar que no se cree un quiz para un topic si existen diapositivas con status != narrative_ready. Esto puede evitar inconsistencias si alguien intenta llamar fuera de orden. Implementar una verificación en un lugar adecuado (por simplicidad, quizás omitir esto en primera instancia ya que el control se hará en frontend principalmente).

(B7) (Opcional) Endpoint POST /api/content/quiz: Si se desea un endpoint dedicado para crear el quiz luego de las diapositivas, se podría implementar uno que reciba topic_id y quizá algunas opciones, luego genere (o reciba del frontend) las preguntas. Sin embargo, dado que la generación de preguntas seguirá haciéndose en frontend con la LLM (por la restricción serverless de 60s
GitHub
), este endpoint realmente solo haría un insert de Content tipo quiz. Una alternativa es no crear un endpoint nuevo, y simplemente usar el existente flujo de createTopicContent para quiz: el frontend tras generar las preguntas llama a createTopicContent(topic_id, {content_type:'quiz', ...}). En cualquier caso, asegurarse que el quiz se guarda con su estructura en interactive_data o content según corresponda (por ejemplo, preguntas y opciones probablemente van en interactive_data JSON).

(B8) Modelo TopicContent – ajustes de campos: Agregar representaciones para full_text, content_html y narrative_text. Actualmente, TopicContent guarda content que puede ser string o Dict, más slide_template (Dict), más render_engine etc.
GitHub
GitHub
. Podemos optar por:

Opción A: Guardar full_text, content_html, narrative_text como campos de primer nivel en TopicContent (más sencillo de consultar y filtrar). En to_dict, incluirlos si existen. Esto alineado con lo propuesto en requerimientos
GitHub
.

Opción B: Incrustar content_html y narrative_text dentro del campo content (por ejemplo, hacer content = {"title":..., "content_html": ..., "narrative_text": ...} como quizás ya hacía generateIndividualSlide). Esto evita cambiar el esquema, pero es menos limpio.

Se prefiere la opción A para claridad. Implementar esta adición en el modelo (solo agregando atributos opcionales). Verificar impacto: el campo antiguo content aún existirá (usado para otros tipos, e.g. diagramas), pero para slides nuevas podríamos dejarlo vacío o usarlo para full_text. Quizá mejor: poner full_text en content también para mantener compatibilidad (o duplicar en ambos). En fin, decidir una convención y documentarla. Ejemplo: para diapositiva, content podría no usarse, usando en cambio full_text (o viceversa). Dado que legacy content ya guardaba el texto completo en slides JSON, podríamos reutilizarlo como full_text. Sin embargo, por claridad, popularemos ambos: guardar full_text separado y quizá también dejar una copia en content (string) para no romper nada.

(B9) Actualizar métodos de consulta: Adecuar las funciones backend que devuelven contenidos para incluir estos nuevos campos. Por ejemplo, si hay un getTopicContentByType(topic_id, 'slide'), asegurarse que devuelve content_html y narrative_text. Si usan .to_dict(), tras la modificación del modelo esos campos deberían ya aparecer si existen. Probar con la UI del profesor: cuando fetchTopicContentByType('slide') se llama
GitHub
, ahora obtendrá cada content con content.content_html y content.narrative_text presentes, permitiendo al viewer agruparlos.

(B10) Seguridad HTML: Dado que estaremos guardando HTML generado por una IA, es importante sanitizar o asegurar su uso. En backend, podríamos validar que content_html no contenga <script> ni iframes. El prompt ya indica al modelo que no incluya esos elementos
GitHub
, pero por seguridad se podría aplicar una limpieza básica (por ejemplo, eliminar <script> tags si aparecieran, etc.). Alternativamente, realizar la sanitización en frontend justo antes de injectar en DOM (SlideContentViewer podría usar una librería de sanitize). Incluir esta consideración como tarea, aunque sea en forma de comentario, para evitar futuras brechas de seguridad.

Paralelismo: Dentro de esta fase, algunas tareas frontend pueden llevarse en paralelo por desarrolladores diferentes: por ejemplo, F3 (desactivar legacy) es independiente y rápido, F4 y F5 (división y bulk insert) van de la mano – podrían hacerse por una persona, mientras F6 y F7 (HTML y narrativa paralela) las podría trabajar otra en simultáneo, dado que son funciones distintas (aunque en el mismo archivo, habría que coordinar merge). Las tareas backend B3, B4, B5 son separables y pueden hacerse en paralelo por el equipo de backend. Es importante que F5 (llamar al bulk API) espere a que B3 esté listo; similarmente F6/F7 (PUT HTML/Narrative) requieren B4/B5. Pero el desarrollo puede solaparse coordinando los contratos de API. Las tareas de viewer (F10, F11) pueden empezar una vez haya datos de ejemplo generados – posiblemente en paralelo un tester puede crear datos dummy en DB para diseñar la UI. En suma, dividir el trabajo entre frontend (implementación pipeline) y backend (endpoints) y luego integrar.

Fase 3: Integración y Ajustes de Visualización (Post-Generación)

Objetivo: Pulir la experiencia una vez que la generación automática está implementada. Incluye asegurar la visualización correcta para profesor y alumno, ajustes en virtualización y verificar que no se rompe nada existente.

(F12) Verificación de virtualización automática: Confirmar que cuando un profesor genera el contenido teórico y automático, el sistema marca el módulo como completable para virtualización. En particular, revisar si Module.content_completeness_score o virtualization_requirements se actualizan. Posiblemente, tras generar todo, habría que actualizar un campo indicando que el topic tiene los contenidos mínimos. Esto puede hacerse en backend: por ejemplo, incrementar content_completeness_score para ese módulo. Si no existe un mecanismo automático, implementar uno sencillo: después de generar quiz, hacer una llamada backend para marcar el topic o módulo como “ready”. (Esto depende de cómo estén definidas las reglas – en Module.virtualization_requirements podría haber flags de needing theory, slides, quiz). En esta tarea, básicamente asegurar que el alumno verá el contenido sin intervenciones manuales: quizás establecer Topic.published = true automáticamente (en el ejemplo de Topic dado, published estaba true
GitHub
). Si no se hace ya, hacerlo ahora.

(F13) UX en visor de profesor: Mejorar la presentación de la sección “Presentación Completa”. Por ejemplo, agregar en el cuadro azul de introducción un indicador si alguna diapositiva está aún procesándose (si implementamos generación asíncrona on the fly, podría darse que el profesor abra el viewer antes de terminar todas). Podemos usar los estados de status de cada content: si hay alguno != narrative_ready, mostrar un aviso “Generando diapositivas…”. Alternativamente, bloquear abrir la pestaña de presentacion hasta terminar. Decidir qué es mejor. Asimismo, podría añadirse un botón “Regenerar Presentación” que use de nuevo generateSlidesV2 (quizá pasando una metodología distinta). Ya que el UniversalContentViewer agrega una opción “Regenerar (v2)” automáticamente para contentType slide
GitHub
, verificar que funcione: al hacer click debería volver a ejecutar la generación completa (posiblemente pidiendo confirmación). Probar esto y corregir cualquier bug (por ej., si no estaba enganchado a generateSlidesV2 correctamente).

(F14) UX en visor del alumno: Probar el módulo virtual en la interfaz de estudiante con un topic generado. Asegurarse de que aparecen las pestañas: “Contenido Principal” (teoría), “Diapositivas”, “Quiz” al menos. Navegar las diapositivas: implementar en SlideContentViewer la navegación con botones anterior/siguiente (posiblemente ya hay estado currentSlideIndex manejado
GitHub
). Confirmar que la narrativa puede mostrarse si se desea – el SlideContentViewer tiene lógica para mostrar modal de texto completo y modal de narrativa (variables showFullTextModal, showNarrativeModal en código
GitHub
). Se podría habilitar un botón “Ver narrativa” (por ejemplo, un ícono de globo de diálogo) para que el alumno pueda leer la explicación oral. Si no es prioritario, al menos asegurarse que la narrativa no se pierde: quizá mostrarla debajo de cada slide como párrafo descriptivo (simple). Decidir según tiempo.

(F15) Pruebas y ajuste de límites: Hacer pruebas con temas de distinto tamaño: p.ej. un tema muy largo que genere 10+ diapositivas. Verificar que nuestro código de división (F4) limita a ~8–10 slides para no saturar. Si se necesitan más, ajustar maxSlides. Probar también con temas muy cortos (que quizás generen 1–2 slides): el viewer debe manejarlos (nuestro grouping lógica, si length > 1, agrupa; si solo 1, mostrará individualmente con UniversalViewer fallback). Asegurarse que ese caso funciona (podría requerir que la condición use >=1 en vez de >1, dependiendo de cómo queremos mostrar una sola slide – quizás directamente mostrarla sin carrusel). Hacer pequeños retoques según estos tests.

(B11) Optimización de consultas: Ahora que potencialmente cada topic tiene varios contenidos más (slides, quiz), revisar el impacto en rendimiento. La carga de fetchTopicContents(topicId) traerá múltiples docs. Podríamos implementar lazy loading en la UI: por ejemplo, no cargar juegos/sims (ya no se usan) o diagramas si no están seleccionados. En el código ya hay lógica de cargar solo al cambiar tab (e.g., if viewMode==='slide' then loadExistingSlides()
GitHub
). Asegurarse que funciona bien. También, considerar indexar en Mongo por topic_id y content_type para acelerar esas búsquedas (si no existe ya, añadir índices compuestos).

(B12) Limpieza de código obsoleto: Ahora que generateIndividualSlide no se usará, eventualmente se podría eliminar. Sin embargo, por prudencia, podríamos comentar su cuerpo o marcarlo como deprecated por ahora, confirmando que nada más lo llama. Igualmente, las rutas backend antiguas como DELETE_TOPIC_THEORY (si no se usan) o cosas del generador unificado preexistente que quedaron sin uso podrían limpiarse para reducir confusión. Esta limpieza debe hacerse con cuidado de no borrar nada que otras partes (p.ej. personalización) usen. Priorizar quitar referencias claras del scope de slides: e.g., quizás había un structured_sequence_service para slides que ya no aplicará con este enfoque; se puede retirar o actualizar.

(La fase 3 es principalmente de prueba e iteración. Muchas de estas tareas se irán resolviendo al depurar lo desarrollado en fase 2 con casos reales. La colaboración QA-Desarrollo aquí es clave. Estas tareas no son altamente paralelizables ya que conviene una visión integral de la experiencia, pero diferentes miembros pueden tomar diferentes roles: uno prueba como “profesor” la creación y visualización, otro como “estudiante”, etc., y se van corrigiendo detalles en paralelo.)

Fase 4: Refactorización de Juegos/Simulaciones a Plantillas

Objetivo: Realinear el sistema de contenidos interactivos con el nuevo enfoque de templates, eliminando progresivamente los componentes legacy de “game” y “simulation”. Esto mejorará la consistencia y reducirá código muerto. Se planifica en pasos para no afectar a usuarios existentes hasta tener la funcionalidad de plantillas plenamente operativa.

(F16) UI – Unificar vista de plantillas: En la interfaz del profesor, rediseñar la sección actualmente denominada “Juegos y Simulaciones”. Según el backlog, debe convertirse en “Mis Plantillas”, mostrando plantillas interactivas disponibles
GitHub
. Como primer paso, renombrar esas pestañas y ocultar las opciones que listan contenidos antiguos. Luego, reutilizar el componente de listado (quizás el TopicGames y TopicSims arrays gestionados en TopicContentViewer
GitHub
) para en su lugar mostrar plantillas. Esto implica invocar un servicio de Templates en lugar de fetchTopicContentByType('game'). Es probable que exista ya un templatesService y rutas como /api/templates. Implementar la llamada para obtener las plantillas del profesor (podrían ser plantillas públicas o creadas por él). Mostrar en una lista con información básica (nombre, tipo, etiquetas, etc.) y acciones: Ver, Editar, Clonar, Usar – tal como dice el backlog
GitHub
. Inicialmente, podemos poblar esta lista con las plantillas equivalentes a juegos que había (si hay). El resultado es que el profesor verá una única sección de plantillas, en vez de separar juegos/simulaciones.

(F17) Eliminar generación legacy de games: En el hook unificado, hay funciones generateGame y generateSimulation
GitHub
 que simplemente llamaban generateContent con type 'game' o 'simulation'. Estas ya no se usarán (a menos que hubiera un plan de generar juegos automáticamente, lo cual no está en foco ahora). Se pueden deshabilitar o dejar de exponer en la UI. Por ejemplo, si en la interfaz de TopicContentViewer había botones para generar juegos/sims, quitarlos. A futuro, la generación de contenido interactivo será vía plantillas (p.ej., seleccionar una plantilla de juego y adaptarla, en lugar de generarlo cero a uno). Por lo tanto, estas funciones se vuelven obsoletas. Marcarlas como deprecated y asegurar que nada las llame (un grep global para generateGame(, generateSimulation( confirmará).

(F18) Contenido existente – compatibilidad: Si la base de datos tiene contenidos TopicContent con content_type: "game" o "simulation" asociados a topics previos, planificar su migración. Una idea es convertirlos en TemplateInstances: por ejemplo, crear un Template a partir de cada juego guardado, y un TemplateInstance ligado al topic. Sin embargo, esto puede ser complejo. Alternativamente, podemos continuar soportando la visualización de esos contenidos pero bajo la nueva UI. Es decir, en Mis Plantillas, incluir también aquellos “plantillas” provenientes de antiguos juegos del topic actual. Por ejemplo, cuando cargamos existingGameContents (que ahora estarían ocultos), podríamos mapearlos a un formato de plantilla temporal para mostrarlos. Dado que probablemente no hay muchos datos legacy en producción, quizás se podría hacer una migración offline posteriormente. Para ahora, enfocarse en no romper: dejar el código de SimulationContentViewer y GameContentViewer para reproducir cualquier juego existente en modo estudiante, pero ya no permitir agregar nuevos así.

(B13) Endpoints de Template: Verificar si en backend existen ya endpoints para listar/crear plantillas. El backlog indica que sí habrá (p.ej. POST /api/templates/:id/extract para extraer marcadores de HTML
GitHub
). A corto plazo, implementar lo mínimo necesario para soportar la nueva vista: probablemente un GET /api/templates que devuelva plantillas disponibles (filtradas por profesor o públicas). Si no existe, crearlo en Template routes. Asimismo, si vamos a permitir “Usar” una plantilla (que crearía contenidos en un topic a partir de esa plantilla), habrá que implementar esa lógica: posiblemente un endpoint POST /api/topic/{topicId}/use_template/{templateId} que cree los TopicContent correspondientes (ej.: inserte un content de tipo según la plantilla, con instance linking). Esto es complejo y quizás fuera del alcance inmediato – se puede dejar planeado para el futuro. Inicialmente, el botón “Usar” en la UI puede simplemente notificar “en construcción”. Lo importante en esta fase es sentar la base para movernos a plantillas.

(B14) Actualizar ContentType enumeraciones: En el modelo ContentType (si existe una lista de tipos), marcar game y simulation como deprecated o cambiar su status a “inactive”. Añadir uno para template si corresponde. Esto evitará que nuevos contenidos se creen con esos códigos salvo que se quiera. Del mismo modo, en la definición de metodologías compatibles (LearningMethodology.compatible_content_types), revisar si aparecían game/sim y decidir si se reemplazan por 'template'. Por ejemplo, quizás metodologías kinestésicas aceptaban 'game'/'simulation'; ahora deberían mapear a cierto tipo de plantilla interactiva. Dejar este ajuste consistente.

Paralelismo: Las tareas de fase 4 pueden ejecutarse en paralelo con fase 3 si hay equipo separado, ya que son bastante independientes de la generación de slides. Por ejemplo, se puede asignar a un desarrollador la tarea de refactor UI de plantillas (F16–F18) mientras otros finalizan slides. B13 y B14 (backend de templates) también pueden manejarse aparte. Se recomienda abordar este refactor una vez que las funcionalidades críticas de contenido teórico y slides estén estables, para no dispersar el foco. Sin embargo, planificarlo desde ya nos asegura que el sistema evolucionará en la dirección correcta sin carga técnica innecesaria.

Notas Finales: Tras implementar todas las fases, el sistema cumplirá con la especificación: el contenido teórico se genera y guarda correctamente, y desencadena la creación automática de diapositivas con HTML y narraciones, más un quiz, usando eficientemente los workers. El profesor podrá ver una presentación navegable directamente en la plataforma
GitHub
GitHub
, y el estudiante recibirá un módulo virtual completo con teoría, slides y evaluación. Los contenidos interactivos estarán preparados para la nueva arquitectura basada en plantillas, evitando confusiones con los antiguos “juegos”. Es fundamental realizar pruebas integrales en este proceso: verificar distintos escenarios de generación, la persistencia en base de datos (que los campos queden en el formato esperado) y la visualización en diversos navegadores. Con estos cambios, alineamos la implementación al backlog deseado y dejamos el camino listo para futuras extensiones (p.ej. personalización por tipo de contenido, marketplace de plantillas, etc.), cumpliendo así con los requerimientos planteados.