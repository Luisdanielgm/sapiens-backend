Informe sobre Workers y Generación de Contenido
Estado Actual del Sistema de Generación

Actualmente, SapiensAI utiliza un sistema de generación de contenido en fases apoyado por un pool de "workers" (trabajadores). El flujo para generar contenido de un tema virtual sigue estas etapas:

Fase 1 – Contenido Teórico (Prerequisites): Se genera el texto teórico base del tema, junto con el estilo de presentación y la estructura de contenidos. Esta fase se ejecuta de forma secuencial, aunque internamente utiliza el sistema de workers (concurrencia 1) para las tareas subyacentes
GitHub
GitHub
. Es decir, primero se genera el texto teórico, luego el estilo de presentación y finalmente la estructura de secciones, cada uno esperando al anterior
GitHub
.

Fase 2 – Plan o "Skeleton" de Diapositivas: A partir del contenido teórico y la estructura calculada, se determinan las diapositivas necesarias (por ejemplo, títulos, puntos clave por diapositiva). Actualmente, esta fase también opera de forma secuencial por sección: el código recorre cada sección del contenido y genera las diapositivas correspondientes una por una
GitHub
GitHub
. Para cada sección se llega incluso a crear un pool de 1 worker y procesar la tarea secuencialmente
GitHub
, lo que significa que no se están aprovechando múltiples workers en paralelo durante esta etapa (se genera sección 1, luego sección 2, etc., en orden). Al final de esta fase se obtiene la lista de diapositivas "esqueleto" con sus títulos, tipo (introducción, contenido, conclusión, etc.) y puntos clave.

Fase 3 – Contenido Visual (Imágenes/Diagrams): Para cada diapositiva planificada, se genera contenido visual (diagramas, imágenes ilustrativas, etc.). Esta fase sí utiliza concurrencia, pero fuera del sistema de workers; en el código actual se lanza una promesa por cada diapositiva usando Promise.allSettled, generando todos los visuales en paralelo de forma nativa
GitHub
. Es decir, todas las peticiones de visuales se hacen simultáneamente, sin pasar por la cola de workerPool. No hay límite explícito de concurrentes aquí, más allá de las restricciones del navegador o API externa.

Fase 4 – Texto Narrativo de las Diapositivas: Tras obtener las imágenes/visuales, se genera texto narrativo detallado para acompañar cada diapositiva (esto podría ser utilizado como notas del presentador o explicaciones ampliadas). Similar a la fase visual, esta etapa lanza peticiones en paralelo nativo para todas las diapositivas con Promise.allSettled
GitHub
GitHub
. Cada diapositiva obtiene su narrativa en simultáneo. Tampoco se usa el pool de workers en esta fase, sino llamadas directas al generador de contenido IA.

Fase 5 – Evaluación (Quiz): Finalmente, se genera un conjunto de preguntas tipo quiz basadas en el contenido teórico del tema. En la implementación actual, la generación del quiz ocurre después de las diapositivas, de forma secuencial como una fase final del flujo
GitHub
GitHub
. Es una única tarea (generar X preguntas), que actualmente se realiza mediante una llamada al generador IA con tipo de contenido "quiz". En el enfoque secuencial estándar, esta llamada se hace solo una vez completadas las fases previas.

Sistema de Workers: El sistema de “workers” está diseñado para permitir la generación paralela controlada. Por diseño, hay hasta 5 workers disponibles para procesar tareas concurrentemente. Solo el worker-1 actúa como dispatcher (despachador) que asigna nuevas tareas a los demás
GitHub
GitHub
. La asignación actual recorre los workers en orden ascendente (1, 2, 3, ...)**, encontrando el primero libre para asignarle la siguiente tarea pendiente
GitHub
. Esto significa que, en teoría, hasta 5 tareas de generación distintas podrían estar ejecutándose en paralelo si hay suficiente carga.

Modos de Ejecución: Existen dos modos en el código:

Un modo secuencial por fases (gestionado por AutomaticGenerationService) que sigue estrictamente el orden arriba mencionado, esperando a que cada fase termine antes de iniciar la siguiente
GitHub
. Este es el flujo pensado para generar el contenido completo de un tema paso a paso.

Un modo paralelo por tareas (gestionado por ParallelGenerationService y usado en ParallelGenerationControls.tsx) que encola de golpe varias tareas de diferentes tipos en el pool de workers. En este modo “batch”, por ejemplo, para un tema se pueden encolar tareas de tipo slide, diagram y quiz simultáneamente
GitHub
GitHub
. Cada tarea lleva un tipo de contenido y una prioridad; el dispatcher las va asignando según disponibilidad y peso de prioridad. Importante: En esta configuración actual, se definió que las tareas slide tienen mayor peso/prioridad que quiz (ver más adelante), lo que intenta asegurar que las diapositivas se atiendan primero
GitHub
. Sin embargo, todas las tareas (incluyendo el quiz) están en la cola desde el inicio.

Prioridades de Tareas: En la cola paralela, las prioridades están definidas mediante pesos en la configuración del pool. Según el código, slide tiene peso 3, diagram peso 2, y quiz peso 1 (más bajo)
GitHub
. Además, se asigna prioridad 'high', 'medium' o 'low' según ciertos criterios; para contenido, internamente se da prioridad más baja al quiz
GitHub
. En conjunto, esto implica que el algoritmo de getNextTask() ordena las tareas pendientes de manera que las diapositivas y contenidos visuales se consideren antes que los quizzes
GitHub
. En principio, el quiz quedaría al final de la cola por tener el menor peso.

Configuración de Concurrencia: Actualmente, el pool se inicializa con maxWorkers: 5 pero con maxConcurrentTasks: 2 por defecto en el modo paralelo
GitHub
. Esto significa que, aunque se arrancan 5 workers, el sistema intenta no ejecutar más de 2 tareas a la vez (posiblemente esperando que solo 2 workers tomen tareas simultáneamente). Esta configuración podría estar limitando la utilización plena de los 5 workers.

Resumen del Estado: En resumen, la arquitectura actual cumple con tener un flujo de generación dividido en fases lógicas y soporte para paralelismo. El backend no realiza llamadas a LLMs (eso es 100% del frontend, usando las claves/API de Gemini u OpenAI)
GitHub
. El frontend tiene implementado casi todo el pipeline, pero hay algunos detalles en cómo se orquestan los workers y las fases que provocan desviaciones respecto al comportamiento esperado (detallados abajo). Notablemente:

El contenido teórico y el plan de diapositivas se generan secuencialmente usando workers de a uno.

Las partes de visuales y narrativa se generan en paralelo inmediato (no via pool).

El quiz en el flujo secuencial ocurre al final (después de todo lo anterior).

Existe un mecanismo para cola paralela que encola quiz junto con otras tareas, confiando en prioridades para postergar su ejecución.

Requerimientos vs. Implementación Actual

A continuación se listan los requerimientos específicos mencionados y se contrasta con el comportamiento actual del sistema, indicando si ya se cumplen o no:

El quiz (evaluación) debe generarse después de las diapositivas, no simultáneamente con estas.
🔸 Estado actual: En el flujo secuencial por fases, efectivamente el quiz inicia solo tras completar todas las diapositivas (es la última fase)
GitHub
GitHub
. En ese modo se cumple el requerimiento. Sin embargo, en el modo paralelo (donde se encolan todas las tareas juntas), no se garantiza plenamente: el quiz se pone en la cola junto a las tareas de diapositivas. Gracias a la prioridad más baja, en muchos casos esperará hasta el final, pero existe la posibilidad de que arranque en cuanto un worker quede libre y ya no haya tareas de slide pendientes (lo cual podría ocurrir antes de que todas las diapositivas estén terminadas, ver “Problemas Identificados”)
GitHub
. Por tanto, actualmente podría violarse el requisito si se usa la generación paralela sin control adicional, ya que la evaluación puede empezar conjuntamente hacia el final de la generación de diapositivas en lugar de estrictamente después.

Orden correcto de las fases de generación: primero contenido teórico, luego planificación/estilos, luego generación de diapositivas.
🔸 Estado actual: La implementación secuencial sigue exactamente este orden: Contenido teórico → Estilo de presentación → Estructura → Diapositivas → (visual/narrativo) → Quiz
GitHub
GitHub
. El contenido teórico se genera antes de cualquier diapositiva, y la planificación (estructura de secciones) también se completa antes de empezar a generar las diapositivas en sí
GitHub
GitHub
. Este orden se está respetando en la lógica actual, por lo que el sistema sí cumple con la secuencia solicitada. El único matiz es que las fases de contenido visual y texto narrativo ocurren después de obtener las diapositivas esqueleto, pero eso también sigue la intención (primero definir qué diapositivas, luego llenarlas de contenido visual y texto).

Uso de los 5 workers en paralelo para generar las diapositivas: se espera que hasta 5 diapositivas se generen simultáneamente para aprovechar la infraestructura.
🔸 Estado actual: Esto no se cumple plenamente. En la fase de skeleton de diapositivas (fase 2) la implementación actual no lanza 5 tareas a la vez, sino que va sección por sección secuencialmente con un solo worker
GitHub
GitHub
. Incluso si una sección contiene varias diapositivas, las genera en bloque como respuesta única de una tarea. Por lo tanto, en ese momento típicamente solo 1 worker está activo generando diapositivas (el resto están ociosos). En las fases 3 y 4 (visual/narrativa) sí hay múltiples peticiones concurrentes, pero esas no usan el mecanismo de “5 workers” sino llamadas paralelas sin control de cantidad. Además, en la configuración del pool paralelo se observa maxConcurrentTasks: 2
GitHub
, lo que sugiere que en ese modo, aunque haya 5 workers, solo 2 tareas se manejan a la vez (limitación configurada quizás para no sobrecargar la API). En resumen: no se está explotando el potencial de los 5 workers de forma consistente, quedando ociosos en la fase de generación de contenido de diapositivas. Esto es un desvío respecto al requerimiento de paralelismo máximo.

Feedback visual en la UI y encadenamiento de generaciones: Cuando un worker termina su tarea, la interfaz debería reflejarlo (por ejemplo, removiendo el indicador “generando” si era la última tarea o pasando al siguiente paso automáticamente).
🔸 Estado actual: Se ha notado que al completar una tarea (p. ej. terminar de generar una diapositiva), el toast o indicador sigue mostrando estado “generando” y la siguiente fase no inicia hasta que manualmente se fuerza o espera un tiempo. Esto indica que la UI no está siendo notificada inmediatamente del final de ciertas tareas/fases. En el código, el WorkerPoolService emite eventos como 'task_completed' y 'pool_completed' correctamente
GitHub
GitHub
, y el AutomaticGenerationService emite eventos de fase completada y generación completada
GitHub
. Por tanto, probablemente falta conectar esos eventos con la lógica de la interfaz. Actualmente, no se cumple bien este requerimiento: la UI no libera el estado “generando” a tiempo ni habilita el siguiente paso en cuanto debería, generando confusión (p.ej., el botón “Generar” puede seguir deshabilitado aun cuando ya no hay nada ejecutándose, hasta que se actualiza el estado global).

Menú de “aplicaciones de usuario” (mención de “menú de roedores”): Aunque fue mencionado al inicio, parece referirse a la visibilidad de ciertas apps en el menú. Por contexto, podría tratarse de un detalle de configuración (posiblemente qué aplicaciones se muestran en cierto menú lateral para el usuario).
🔸 Estado actual: No se halló referencia específica en el código analizado sobre “menú de roedores”, por lo que no podemos confirmar su significado exacto. Podría ser que actualmente solo se listan en ese menú las aplicaciones predeterminadas y no las del usuario. Sin más detalles concretos en el código disponible, este punto queda pendiente de clarificación. Es posible que no esté implementado aún (lo cual implicaría que no se cumple el requerimiento de mostrar todas las apps del usuario en ese menú).

En resumen, la arquitectura básica está alineada con los requerimientos, pero hay desacoples en la implementación que hacen que algunos no se cumplan en la práctica (especialmente la sincronización del quiz con las diapositivas en modo paralelo, la subutilización de los 5 workers, y la actualización de la UI en tiempo real).

Problemas Identificados en la Implementación Actual

Del análisis del código y comportamiento, destacamos los siguientes hallazgos que explican los desvíos:

Inicio Prematuro de la Generación del Quiz (modo paralelo): Existe un riesgo de que el quiz se genere concurrentemente con las últimas diapositivas. Esto ocurre en el flujo paralelo porque el quiz se encola junto con las demás tareas. Si, por ejemplo, hay pocas diapositivas a generar (digamos 2) y 5 workers disponibles, el dispatcher asignará esas 2 tareas de diapositiva de inmediato a worker-1 y worker-2. En ese momento, quedan workers libres (3,4,5) y la tarea de quiz ya está en cola (aunque con prioridad menor). Resultado: un worker libre podría tomar la tarea quiz antes de que las tareas de diapositiva hayan concluido completamente – únicamente espera a que no queden pendientes sin asignar de mayor prioridad, pero no necesariamente a que estén finalizadas. Esto concuerda con la observación de que la evaluación se estaba “generando en conjunto con las diapositivas”. El diseño de prioridades intenta serializarlo, pero no es suficiente en todos los casos sin un mecanismo de dependencia explícita.

No utilización completa de los 5 workers en generación de diapositivas: En la fase crítica de crear el contenido de las diapositivas (que potencialmente es la más tardada por incluir varias llamadas al modelo IA), el código actual procesa sección por sección secuencialmente
GitHub
. Incluso si hay 5 workers, solo uno trabaja a la vez en esta etapa, lo cual alarga innecesariamente el proceso. Además, la configuración de maxConcurrentTasks: 2 en la cola global limita la concurrencia globalmente
GitHub
, lo que podría ser otro factor de subutilización: es posible que nunca haya más de 2 tareas simultáneas aunque haya 5 workers activos. Esto fue quizás configurado para no sobrecargar la API, pero contradice la expectativa de “trabajar los 5”. En suma, se identifican cuellos de botella artificiales que impiden el paralelismo máximo.

Estado de UI no se actualiza inmediatamente al completar tareas: Se detecta un problema de sincronización UI. Cuando un worker termina (particularmente en flujo secuencial fase a fase), la siguiente fase debería arrancar o al menos el indicador visual cambiar. Que el toast siga “como si estuviese generando” sugiere que o bien:

La lógica que inicia la siguiente fase no se está llamando automáticamente. Por ejemplo, tras completar contenido teórico, debería dispararse automáticamente la generación del plan de diapositivas; si eso no ocurre, el sistema queda esperando manualmente.

O la interfaz no está escuchando el evento correcto para actualizar el estado. Quizá el evento 'phase_completed' no está conectado a cambiar el statuses en el GenerationStatusPanel, o el evento de fin de generación no reinicializa el estado de currentJob.

Hay evidencia en el código de eventos que podrían usarse para esto (ej: onGenerationCompleted en AutomaticGenerationService) pero pueden no estar suscritos por la UI. Consecuencia: el usuario ve “atorado” el proceso en la interfaz aunque internamente pudo haber terminado una fase o incluso todo el trabajo. Este es un bug de integración entre backend-frontend (eventos) y la capa visual.

Orden de asignación de workers diferente a la descripción: Como nota menor, observamos una discrepancia entre la descripción verbal dada (“si están 2 y 4 disponibles, trabaja primero el 4”) y la implementación real (getNextAvailableWorker busca siempre el menor ID disponible primero
GitHub
). En el código actual, trabajaría primero el 2 antes que el 4. Esto no afecta directamente funcionalidades, pero sugiere o bien una confusión en la descripción o la intención de cambiar la estrategia de asignación. Podría ser irrelevante para el usuario final, pero se destaca como hallazgo para confirmar cuál es el comportamiento deseado (orden ascendente actual vs. algún criterio diferente planeado).

Manejo de “apps de usuario” en el menú (pendiente): Si profundizamos en la primera parte de la conversación, parece que no se están montando todas las aplicaciones del usuario en el menú (solo algunas predeterminadas). Se menciona que no haría falta usar clon ni datum para ello, indicando que podría ser una configuración faltante. Sin referencias claras en el código, asumimos que es un issue pendiente en frontend: cargar dinámicamente las apps del usuario en el menú lateral (quizá relacionado a toggles de features). Es un punto a revisar en la configuración de la UI o estado global de aplicaciones permitidas por usuario.

En síntesis, los problemas se centran en sincronización y paralelismo: el quiz debería esperar su turno correctamente, los 5 workers deberían emplearse más agresivamente en las partes pesadas, y la interfaz debe reaccionar al instante a los cambios de estado. Adicionalmente, hay un asunto de listado de aplicaciones de usuario en la UI que parece no implementado.

Tareas a Implementar

A partir de lo anterior, se proponen las siguientes tareas concretas para alinear la implementación con los requerimientos. Se dividen en tareas de frontend (orquestación de generación y UI) y backend (modelado y almacenamiento de contenidos generados):

Frontend

Asegurar que la generación del Quiz inicia solo tras las diapositivas:
Modificar la lógica de generación en modo paralelo para introducir una dependencia o postergación explícita de la tarea de quiz. Algunas opciones:

No encolar inmediatamente el quiz: Cambiar ParallelGenerationService para que cree las tareas de slide (y diagram) y comience a procesarlas, y recién cuando esas estén asignadas o casi terminadas, agregar la tarea de quiz. Por ejemplo, se podría dividir el startJob en dos etapas: primero encolar diapositivas/diagrams; al recibir un evento de que quedan pocas tareas (o al completar la asignación de todas las de tipo slide), entonces encolar el quiz. De esta forma, el quiz no compite por workers hasta el final.

Implementar "dependencia" en el dispatcher: Alternativamente, introducir una bandera en la tarea de quiz o en el dispatcher para que, mientras existan tareas de tipo diapositiva en curso, no se asigne la tarea de quiz aunque esté en cola. Esto podría hacerse comprobando dentro de getNextTask() o getNextAvailableWorker() si el siguiente en cola es quiz y aún hay diapositivas en ejecución, omitirlo temporalmente. Si bien es más complejo, garantizaría que "en paralelo pero al final" se cumpla exactamente: el quiz arrancaría únicamente cuando ya no quede ninguna diapositiva pendiente de asignar ni encolada (es decir, cuando la cola de diapositivas esté completamente vacía).
Cualquiera de las dos estrategias lograría que el quiz no se genere prematuramente. Esto solucionaría el problema observado de quiz ejecutándose simultáneamente con diapositivas. Se deberá probar con casos de pocas diapositivas y muchos workers para validar que el quiz realmente espera.

Incrementar la utilización del pool de 5 workers en generación de diapositivas:
Para acortar tiempos y cumplir con la expectativa:

Paralelizar la fase de "Esqueleto de Diapositivas": En lugar de generar sección por sección de manera secuencial
GitHub
, se puede aprovechar los 5 workers. Por ejemplo, si hay 5 secciones, lanzar 5 tareas en paralelo (una por sección) usando workerPoolService.processTasksWithFlexibleConcurrency con maxConcurrent acorde. Ya que cada sección es independiente en cuanto a generación de su set de diapositivas, esto es viable. Requerirá recopilar luego los resultados de cada tarea para construir el sectionsMap y navigationFlow. Esta modificación permitiría generar múltiples diapositivas en simultáneo (hasta 5) desde el principio.

Revisar configuración de concurrencia del pool global: Si mantenemos maxWorkers = 5, podemos subir maxConcurrentTasks a 5 también (o permitir configurarlo desde la UI). Actualmente está a 2
GitHub
, lo que limita la cantidad de workers efectivos corriendo a la vez. Aumentarlo a 5 hará que el dispatcher pueda asignar tareas a los 5 workers en intervalos de ~1s sin restricción artificial. Esto debe acompañarse de pruebas de rendimiento, pero alineará el sistema con la intención de usar los “5 en paralelo”.

Distribución de tareas de diapositivas en el pool: En el modo paralelo, cerciorarse de que si hay muchas diapositivas (ej. 10), el pool las reparte entre los 5 workers de manera balanceada. Dado que el dispatcher ya asigna al primer libre, esto ocurrirá automáticamente si no hay otras restricciones. El cambio principal aquí es evitar colas secuenciales internas como la de sección por sección.

Con estos cambios, sí estarían "trabajando los 5 workers" durante la generación de diapositivas cuando haya 5 o más tareas de slide. Esto acelerará la generación y cumple el requerimiento de paralelismo.

Corrección de la actualización de estado y toasts en la UI:
Implementar manejadores de eventos y lógica de interfaz para reflejar inmediatamente el progreso:

Suscribirse a eventos del servicio de generación: En el componente que inicia la generación (por ejemplo, ParallelGenerationControls o donde se llame a automaticGenerationService.startGeneration), añadir suscripciones a eventos onPhaseCompleted, onGenerationCompleted y onGenerationFailed. Al ocurrir generation_completed, se debe:

Ocultar cualquier toast de “Generando…” aún visible (o cambiar su estado a éxito).

Marcar los estados en GenerationStatusPanel como completados (por ejemplo, establecer quizStatus: 'success', slideStatus: 'success', etc., cuando correspondan)
GitHub
.

Rehabilitar botones o acciones bloqueadas durante la generación (p.ej. reactivar el botón de “Generar contenido” para permitir regenerar si se desea, o habilitar la navegación).

Cerrar automáticamente toasts persistentes: Si se usa algún sistema de notificaciones tipo toast, configurarlo para que se cierre al completar (o al menos cambiar de “loading” a “success” icono). En el código se ve que las notificaciones de progreso podrían manejarse con un estado interno de ProgressNotification. Asegurarse que al llegar al 100% o evento de completion, se actualice o remueva.

Encadenamiento de fases en modo secuencial: Si se continúa con la lógica secuencial fase por fase (que parece estar en uso cuando se presiona “Generar contenido teórico”), asegurarse de que tras completar la fase teórica, se llame automáticamente a la siguiente (plan de diapositivas), y así sucesivamente, sin intervención manual. Esto probablemente ya esté en executePhases del AutomaticGenerationService
GitHub
, pero conviene verificar que la UI no requiera varios clics. Idealmente, un clic en “Generar contenido” debería disparar todo el pipeline hasta quiz, mostrando el progreso de cada sub-etapa en el UI. Si actualmente el flujo se detiene esperando otro clic para “Generar diapositivas” por ejemplo, habría que integrarlo para que sea continuo (o al menos muy claramente guiado al usuario con botones de “Siguiente paso” cuando corresponda).

Actualizar currentJob y progreso general: En ParallelGenerationControls se calcula canStart como verdadero solo si no hay un job corriendo
GitHub
GitHub
. Asegurarse de que cuando la generación termina, se hace setCurrentJob(null) o se actualiza el estado a “completed”, de modo que canStart se vuelva true inmediatamente. Esto quitará la apariencia de “bloqueado” en el botón después de terminar.

Estas acciones garantizarán que el usuario reciba feedback inmediato: el spinner desaparece al terminar cada fase, los iconos de check verde aparecen al completar, y la siguiente generación puede iniciarse sin tener que refrescar o esperar innecesariamente. En otras palabras, resuelve el bug donde “se queda el toast como si estuviese generando”.

Montar todas las aplicaciones del usuario en el menú correspondiente (si aplica):
Si el “menú de roedores” hace referencia a un menú lateral donde deberían aparecer apps personalizadas del usuario, se debe:

Revisar de dónde obtiene la lista de apps ese menú. Quizá hay un filtro mal aplicado o simplemente no se está poblando con la información del usuario logueado.

Asegurar que tras login, se carga la lista completa de aplicaciones disponibles al usuario (posiblemente desde una respuesta del backend o un archivo de configuración).

Confirmar qué se quiso decir con “Autos, clone, datum no se necesitan para eso” – posiblemente son nombres de apps o funciones internas. Podría implicar eliminar dependencias innecesarias o banderas de configuración.

Probar que efectivamente tras el cambio las aplicaciones del usuario aparecen.

Esta tarea es menos relacionada con los workers, pero fue mencionada. Requiere aclaración con el equipo, pero la implementación seguramente involucra el estado global de la app o un componente de menú.

(Opcional) Simplificar/enfocar un solo flujo de generación:
Actualmente coexisten el flujo secuencial por fases y el flujo totalmente paralelo con cola de tasks. Esto añade complejidad y de hecho causó el problema del quiz concurrente. Una tarea de diseño sería decidir por un enfoque unificado:

O bien utilizar siempre el flujo secuencial fase a fase para generar un tema completo (más sencillo de controlar orden), y reservar el flujo paralelo para casos multi-tema o generación masiva.

O mejorar el flujo paralelo para que respete las dependencias (como estamos ajustando) y entonces usar siempre ese para aprovechar la cola unificada de tasks.

En cualquiera de los casos, eliminar código duplicado o rutas de código alternativas reducirá bugs. Por ejemplo, si se logra que ParallelGenerationService maneje bien las dependencias, podría usarse también para un solo tema, evitando tener que mantener AutomaticGenerationService separado. O viceversa, quizás descartar el paralelo “batch” para generación de un tema y usarlo solo para escenarios de batch verdadero (múltiples temas a la vez). Esta decisión escaparía a la corrección inmediata, pero es una tarea a considerar para robustez futura.

Backend

Modelo de datos para contenido en diapositivas (subcontenido):
Introducir/habilitar en el backend la noción de diapositivas como unidades de contenido asociadas a un tema. Actualmente, es probable que exista una colección virtual_topic_contents donde cada registro corresponde a un contenido (antes podía ser todo el tema como un único contenido). Con la nueva arquitectura:

Asegurarse de que el modelo de VirtualTopicContent (o equivalente) tiene campo para parent_content_id o parent_topic_id para vincular diapositivas a su tema principal
GitHub
. Si no existe, extender el esquema. Este campo permitirá relacionar varias piezas (diapositivas, quiz) bajo un mismo tema.

Cuando el frontend envíe las diapositivas generadas, crear múltiples entries en la base de datos: una por diapositiva, cada una con su título, contenido (texto narrativo quizás combinado con puntos clave), tipo, etc., y con un campo parent_content_id apuntando al contenido teórico principal o un campo virtual_topic_id apuntando directamente al tema., y con un campo parent_content_id apuntando al contenido teórico principal o un campo virtual_topic_id apuntando directamente al tema. Se debe definir qué es el “padre”: podría ser el contenido teórico como tal (si se guarda el texto teórico como un Content separado), o simplemente todos comparten el mismo virtual_topic_id.

Guardar el orden de las diapositivas (campo order o similar) para mantener la secuencia original en la presentación. Esto probablemente ya esté contemplado en el campo order del contenido (muchos sistemas de contenido tienen orden para items). Esto probablemente ya esté contemplado en el campo order del contenido (muchos sistemas de contenido tienen orden para items).

Ejemplo: Al finalizar la generación, el frontend podría hacer una llamada POST enviando { topicId: X, contents: [ {type: "text", title: "...", content: "texto teórico completo"}, {type: "slide", title: "Diapositiva 1", content: "...", order: 1}, ..., {type: "quiz", content: {...quiz JSON...}} ] }. El backend recibiría esto y haría inserciones múltiples en virtual_topic_contents: uno para el texto, varios para diapositivas con parent al texto o al topic, y uno para quiz. El backend recibiría esto y haría inserciones múltiples en virtual_topic_contents: uno para el texto, varios para diapositivas con parent al texto o al topic, y uno para quiz.

No duplicar contenido teórico en cada slide: Las diapositivas no necesitan almacenar todo el texto teórico, solo su propio contenido. El campo parent_content_id servirá para que se pueda reconstruir el contexto si se necesita (por ejemplo, al mostrar todo junto). El campo parent_content_id servirá para que se pueda reconstruir el contexto si se necesita (por ejemplo, al mostrar todo junto).

Almacenamiento del Quiz como contenido interactivo:
Según el comentario en el código, ya no hay una colección separada para quizzes, sino que estos se tratan como otro tipo de TopicContent (content_type = "quiz")
GitHub
GitHub
. Por lo tanto:

Al recibir el quiz generado desde el frontend, insertar un registro en virtual_topic_contents con type = quiz asociado al mismo virtual_topic_id (y posiblemente con parent_content_id apuntando al contenido teórico principal también, si se decide agrupar todo bajo un contenido raíz).

Definir cómo almacenar las preguntas y opciones: probablemente en un campo JSON dentro de content o en campos estructurados (por simplicidad, puede guardarse tal cual el JSON generado por la IA, bajo una estructura validada). Asegurarse de validar/sanitizar ese JSON antes de guardarlo, ya que viene de un modelo generativo.

Establecer campos como title (ej. "Quiz de [Nombre del tema]"), número de preguntas (question_count), etc., si es necesario para facilitar queries. El quizPhaseService genera un objeto con preguntas, respuestas correctas y explicaciones
GitHub
GitHub
 – toda esa estructura debería guardarse íntegra.

Marcar este contenido quiz de forma distinguible, para que en la UI del estudiante se sepa que es un quiz interactivo (posiblemente hay ya una enumeración de tipos de contenido en backend/frontend).

Endpoint para registrar contenidos generados:
Implementar (o completar) el endpoint HTTP que permita al frontend guardar en la base los resultados de la generación automática. Es probable que exista algo como POST /virtual/topic/content o similar (en los archivos proporcionados vimos referencia a study_plan/topic/content en un comentario)
GitHub
. Si no está implementado:

Crear ruta en virtual_bp o content_bp para creación masiva de contenidos de un tema. Debe aceptar el payload con todas las piezas generadas (como en el ejemplo del punto 1) o múltiples llamadas para cada pieza. Lo más eficiente es una llamada con toda la estructura para evitar múltiples roundtrips.

En el servicio correspondiente (VirtualTopicService o ContentService), iterar sobre los contenidos recibidos:

Validar que el usuario que hace la petición es propietario/profesor del tema en cuestión (autorización).

Para cada contenido: asignar virtual_topic_id, generar IDs nuevos (si no vienen del cliente), setear timestamps, etc.

Insertar en virtual_topic_contents. Idealmente, hacer inserciones en lote si se utiliza PyMongo/MongoDB (insert_many) para todas las diapositivas en una sola operación.

Si se envió también el contenido teórico principal, guardarlo con tipo "text"/"theory".

Retornar una respuesta con éxito y quizás los IDs generados. Esto completa el ciclo: una vez el frontend genera todo con IA, llama a este endpoint para persistirlo.

Nota: si ya existe un endpoint para crear un contenido individual, se podría llamar múltiples veces, pero es mejor optimizar con uno solo para todo el módulo generado.

Manejar también actualizaciones: si un profesor regenera el contenido de un tema que ya tenía algo, podría querer sobreescribir. En tal caso, considerar si primero borrar contenidos antiguos de ese tema (excepto los manuales quizás) antes de insertar los nuevos generados. Esto es un detalle de UX/negocio a definir (quizás se versiona o se reemplaza completamente el contenido del tema al regenerar).

Tracking de progreso y completitud con contenidos múltiples:
Con la introducción de múltiples contenidos por tema (diapositivas, quiz, etc.), el backend debe asegurar que el sistema de progreso del estudiante se ajusta:

ContentResultService: verificar cómo calcula completitud. Probablemente antes un tema tenía un ContentResult cuando el estudiante lo terminaba. Ahora, ¿habrá un ContentResult por cada diapositiva? Lo más práctico es seguir teniendo un ContentResult unificado por tema, pero entonces la lógica de marcar completado un tema debería considerar todos sus subcontenidos completados. Por ejemplo, el estudiante debe ver todas las diapositivas y completar el quiz para marcar el tema al 100%.

Implementar en el backend (o frontend) la regla: si existen varios virtual_topic_contents en un tema, la completitud del tema puede ser un agregado de la completitud de cada parte. En submit_content_result (que ya es un endpoint unificado) se hace algo parecido: cuando un contenido llega al 100%, se marca completed y se podría recalcular el progreso del tema
GitHub
GitHub
. Habría que extender esa lógica para revisar: “¿Todos los contenidos de este topic están completed?”. Si sí, marcar el topic como completed.

Esto puede implicar que la colección de topics tenga un campo de progreso global, o quizás simplemente con que todos los interaction_tracking de cada content estén en completed. Sería útil agregar en VirtualTopicService un método para calcular % completado de un tema basado en sus contenidos (ej: 6 diapositivas + 1 quiz = 7 items, si el alumno completó 4, progreso ~57%). Esta funcionalidad mejora la adaptatividad y feedback al estudiante.

Migración/compatibilidad: Asegurarse de manejar los temas antiguos que solo tenían un content. Probablemente no haya problema, pero testear que el código no rompa si contentStructure.sections no existe, etc.

Registro de errores y métricas:
Añadir logs en puntos clave para facilitar depuración de esta nueva funcionalidad:

Cuando el profesor inicia una generación automática, loggear en backend “Generación iniciada para topic X por user Y”.

Tras guardar los contenidos generados, loggear cuántos contenidos se crearon (e.j. “Generación completada: 1 contenido teórico, N diapositivas, 1 quiz guardados para topic X”).

Si hay fallas (por ejemplo, error al parsear el JSON del quiz, o algún contenido vacío), capturarlos y devolver mensajes claros al frontend. Esto ayudará en pruebas de integración.

Dado que se integrará IA, monitorear posibles puntos de fallo: tamaño de contenidos, timeouts, etc., y reflejarlos en logs/errores manejados.

Implementando todas estas tareas, el sistema quedará alineado con los requerimientos iniciales:

La evaluación (quiz) solo comenzará cuando corresponda, una vez generadas las diapositivas (respetando la secuencia lógica y evitando condiciones de carrera).

Se utilizarán los 5 workers en la medida esperada, especialmente para agilizar la creación de diapositivas (que son múltiples elementos similares, ideales para paralelizar).

La interfaz de usuario mostrará correctamente el progreso y finalizará el estado “generando” tan pronto la tarea termine, habilitando la siguiente acción sin confusión. Los profesores verán cada fase marcada con check (o error si ocurrió) en tiempo real.

El backend soportará la nueva estructura de contenido en subunidades (diapositivas individuales y quiz), pudiendo almacenarlas y relacionarlas bajo el tema. Asimismo, el sistema de seguimiento de progreso reconocerá estos subcontenidos, de modo que la experiencia del estudiante sea consistente (ej.: puede marcar diapositiva a diapositiva vista, y al final completar el quiz para terminar el tema).

En caso de que hubiera un menú u otras secciones pendientes (lo de las apps de usuario en el menú), se habrán corregido para mostrar la información completa al usuario.

En conclusión, estas tareas abordan tanto las correcciones inmediatas de bug como ajustes arquitectónicos necesarios para que la generación de contenido con AI funcione de forma fluida y acorde a lo solicitado, integrándose perfectamente con la interfaz y la persistencia de datos del sistema. Cada modificación deberá ser probada rigurosamente (idealmente con los suites de pruebas automatizadas existentes y con pruebas manuales) para asegurar que cumplen el objetivo sin introducir regresiones. Con esto, SapiensAI podrá ofrecer a los usuarios la funcionalidad de generación automática de contenidos en diapositivas con evaluaciones, de manera confiable, rápida y ordenada, tal como se espera.