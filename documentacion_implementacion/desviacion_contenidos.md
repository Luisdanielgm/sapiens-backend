Informe de Diagnóstico y Plan de Mejora del Sistema de Generación Automática de Contenido
Análisis de la Implementación Actual

El sistema de generación de contenido automático (vista de profesor) opera en varias fases secuenciales, utilizando un pool de hasta 5 workers para tareas en paralelo controlado. Actualmente, el flujo de generación es el siguiente:

Fase 1 – Contenido teórico: Se genera el texto teórico completo del tema usando IA (LLM). Esta fase es secuencial (usa los workers con concurrencia 1), ya que primero obtiene el texto teórico, luego (usando el resultado) genera el estilo de presentación global (plantilla de diapositivas), y finalmente determina la estructura de secciones
GitHub
. Cada sub-tarea espera a la anterior antes de continuar.

Fase 2 – Plan o “esqueleto” de diapositivas: Con el contenido teórico y la estructura generada, se calculan las diapositivas necesarias. Problema: Actualmente esta etapa sigue siendo secuencial por sección (genera las diapositivas de la sección 1, luego sección 2, etc.) en lugar de paralelizar
GitHub
. Incluso se llega a crear un pool de 1 worker por sección, desaprovechando la posibilidad de múltiples workers en paralelo
GitHub
. Al final de esta fase se obtienen las diapositivas “esqueleto” con títulos, tipo (introducción, contenido, conclusión, etc.) y puntos clave de cada una.

Fase 3 – Contenido visual (imágenes/diagramas): Para cada diapositiva planificada, se generan elementos visuales (diagramas, imágenes ilustrativas, etc.). En la implementación actual, esta fase se lanza en paralelo nativo en el frontend – es decir, se dispara una promesa por cada diapositiva con Promise.allSettled sin pasar por la cola de workers
GitHub
. Todas las peticiones de visuales ocurren simultáneamente (limitadas solo por el navegador o la API externa), lo que significa que no se está usando el control de concurrencia del pool en esta etapa.

Fase 4 – Texto narrativo de las diapositivas: Similar a la fase visual, para cada diapositiva se genera en paralelo un texto narrativo ampliado que servirá como voz narrativa o explicación de la diapositiva
GitHub
. Nuevamente, el código actual lanza todas las peticiones de narrativa a la vez (paralelo nativo), en lugar de utilizar la cola de workers.

Fase 5 – Evaluación (quiz): Finalmente, se genera un conjunto de preguntas tipo quiz basado en el contenido teórico del tema. En el flujo secuencial estándar, esta generación del quiz se realiza después de completar todas las diapositivas, como una fase final única
GitHub
. Es una sola tarea (por ejemplo, “generar 5 preguntas”) que llama al modelo IA para contenido de tipo "quiz". En modo estrictamente secuencial, el quiz solo inicia tras finalizar las fases previas, cumpliendo el orden requerido
GitHub
.

Mecanismo de Workers y Concurrencia: El sistema dispone de un pool de 5 workers para distribuir tareas de IA en paralelo controlado
GitHub
. Un “dispatcher” (el worker-1) se encarga de asignar nuevas tareas a los demás workers disponibles, recorriendo los IDs en orden ascendente
GitHub
GitHub
. Teóricamente, hasta 5 tareas podrían ejecutarse en simultáneo si hay suficientes peticiones pendientes. Existe además una configuración de prioridad por tipo de tarea cuando se usa el modo paralelo por lotes: actualmente slide tiene peso 3, diagram peso 2 y quiz peso 1 (el más bajo)
GitHub
. Adicionalmente, se etiquetan tareas con prioridades cualitativas (high, medium, low), donde el quiz se maneja con prioridad más baja
GitHub
. Esto significa que el algoritmo del dispatcher en principio ordena las tareas pendientes dando preferencia a diapositivas y visuales antes que a la evaluación
GitHub
, intentando que el quiz quede al final de la cola.

Modos de Orquestación: Se han identificado dos modos en el código actual:

Modo secuencial por fases: Gestionado por AutomaticGenerationService, sigue estrictamente el orden de fases mencionado, esperando que cada fase termine antes de iniciar la siguiente
GitHub
. Este sería el flujo esperado cuando un profesor presiona “Generar contenido” y quiere que automáticamente se ejecute todo paso a paso (teoría → slides → visuales → narrativa → quiz).

Modo paralelo por tareas (batch): Gestionado por ParallelGenerationService (usado en ParallelGenerationControls.tsx en el frontend). En este modo, se encolan de golpe múltiples tareas de diferentes tipos en el pool de workers
GitHub
. Por ejemplo, al generar contenido de un tema, se crean tareas para cada diapositiva, sus visuales e incluso el quiz, todas prácticamente al mismo tiempo. Estas tareas conviven en la cola con sus prioridades asignadas. En esta configuración, las tareas de slide tienen mayor prioridad que quiz
GitHub
, con la intención de que las diapositivas se atiendan primero. Importante: en la implementación actual, aunque el peso/prioridad del quiz es menor, todas las tareas (incluyendo el quiz) se encolan desde el inicio del proceso
GitHub
.

Configuración de concurrencia actual: El pool de workers se inicializa con maxWorkers: 5, pero tiene maxConcurrentTasks: 2 por defecto
GitHub
. En otras palabras, aunque existen 5 threads de worker, el dispatcher intentará no ejecutar más de 2 tareas simultáneamente. Esta limitación de concurrencia fue quizás establecida para no sobrecargar la API de IA, pero impide aprovechar plenamente los 5 workers disponibles en paralelo, contradiciendo la expectativa de “5 tareas a la vez” en las fases intensivas.

Problemas Identificados

Del análisis de código y comportamiento actual, emergen varios desviaciones respecto a los requerimientos originales:

Inicio prematuro de la generación del Quiz (en modo paralelo): Existe riesgo de que la tarea de quiz comience concurrentemente con las últimas diapositivas, en lugar de después. Esto ocurre porque en el flujo paralelo el quiz se encola junto a las demás tareas desde el principio. Si, por ejemplo, hay pocas diapositivas (ej. 2) y 5 workers disponibles, el dispatcher asigna esas 2 tareas de diapositiva inmediatamente a worker-1 y worker-2. En ese momento quedan workers libres (3,4,5) y la tarea de quiz ya está en la cola (aunque con menor prioridad). Un worker libre podría tomar el quiz tan pronto detecte que no hay más tareas de slide pendientes de asignar, aunque aún se estén ejecutando diapositivas
GitHub
. Es decir, el sistema de prioridades no garantiza al 100% el orden deseado sin una dependencia explícita: el quiz espera a que no queden slides por asignar, pero no necesariamente a que todas hayan finalizado
GitHub
. Esto concuerda con la observación de que el quiz “se estaba generando primero” o simultáneo a las últimas diapositivas, violando el requisito de secuenciación estricta.

Subutilización de los 5 workers en la generación de diapositivas: Durante la fase crítica de creación del contenido de las diapositivas (que incluye múltiples llamadas costosas al modelo IA), el código no está aprovechando el paralelismo disponible. Como se describió, procesa las secciones una por una secuencialmente
GitHub
. Aunque haya 5 workers inicializados, solo uno trabaja a la vez en esta etapa. Adicionalmente, la configuración global de maxConcurrentTasks: 2 impone otro cuello de botella: incluso en el modo paralelo, posiblemente nunca haya más de 2 tareas corriendo en simultáneo
GitHub
. En resumen, hay restricciones artificiales (secuencialidad por sección y límite de concurrencia) que impiden alcanzar el “máximo paralelismo” esperado.

La interfaz (UI) no actualiza el estado al completar las tareas: Se ha detectado que, tras terminar una fase o incluso toda la generación, la UI sigue mostrando un indicador (toast o spinner) “como si estuviese generando” indefinidamente. Esto sugiere un problema de sincronización entre la finalización de tareas y la retroalimentación visual
GitHub
. Posibles causas identificadas:

La lógica que inicia la siguiente fase automáticamente podría no estar siendo invocada. Por ejemplo, tras completar la generación del contenido teórico, debería dispararse la generación del plan de diapositivas sin intervención del usuario. Si esto no sucede, el sistema parece quedarse esperando y el indicador de progreso no cambia
GitHub
GitHub
.

Alternativamente, la UI podría no estar escuchando el evento correcto de finalización para actualizar el estado. El código contempla eventos como onGenerationCompleted o onPhaseCompleted en los servicios de generación, pero quizás la interfaz no los está suscribiendo o manejando apropiadamente
GitHub
. Como consecuencia, el usuario ve el proceso “atorado” en pantalla aunque internamente ya haya concluido una fase (o todo el proceso).

Orden de asignación de workers distinto al esperado: Si bien es un detalle menor, notamos que la implementación actual asigna siempre al worker libre de menor ID primero (por ejemplo, si están libres el 2 y el 4, asigna el 2)
GitHub
. Esto contrasta con alguna descripción previa que sugería lo opuesto. Aunque este detalle no afecta mayormente la funcionalidad, conviene confirmarlo con la intención de diseño. En principio, no impacta al usuario final, pero lo destacamos por transparencia.

Menú de “apps” de usuario no mostrando todas las aplicaciones: (Hallazgo secundario) En la conversación se mencionó que en el menú lateral no se estaban montando todas las aplicaciones del usuario (solo algunas predeterminadas), y que no haría falta usar clone ni datum para ello. No hay mucho código al respecto en este análisis, pero se infiere que es una funcionalidad pendiente en el frontend: cargar dinámicamente en el menú todas las aplicaciones disponibles para el usuario logueado. Esto parece un asunto de configuración o permisos en la UI que habría que revisar
GitHub
. Lo anotamos aunque no está directamente relacionado con la generación de contenido.

En resumen, los problemas principales se centran en la secuenciación y paralelismo: el quiz no debería arrancar hasta después de las diapositivas; los 5 workers deberían emplearse de forma más agresiva en la parte pesada (generar múltiples diapositivas); y la interfaz debe reflejar al instante el progreso, evitando quedarse en estado “cargando” cuando ya terminó. Adicionalmente, hay un tema de carga de aplicaciones de usuario en el menú que se debe resolver, y convendría eliminar o refactorizar el código legado que ya no se use (como las referencias a content_type "slides" en vez de "slide").

Plan de Implementación

A continuación, se proponen tareas concretas para alinear el sistema con los requerimientos esperados. Se dividen en tareas de Frontend (orquestación de generación y mejoras de UI) y tareas de Backend (persistencia y modelo de datos), enumeradas con suficiente contexto:

Frontend

Asegurar que la generación del Quiz inicia solo tras completar las diapositivas:

Postergar encolado del quiz: Modificar la lógica del ParallelGenerationService (flujo paralelo) para no encolar inmediatamente la tarea de quiz junto con las diapositivas. Una estrategia es dividir el proceso en dos etapas: primero encolar únicamente las tareas de slide (y diagramas si aplican) y dejar que comiencen a procesarse; luego, cuando estas estén por terminar, agregar la tarea de quiz. Por ejemplo, se puede escuchar un evento o condición (ej. “cuando solo queden N diapositivas pendientes”) y entonces insertar la tarea del quiz en la cola
GitHub
. Así el quiz no competirá por workers hasta que realmente deba ejecutarse al final.

Introducir dependencia en el dispatcher: Alternativamente (o complementariamente), implementar lógica en el despachador de tareas para que, mientras existan tareas de diapositiva en curso o en cola, no asigne la tarea de quiz aunque esté presente. Esto podría hacerse en la función que selecciona la siguiente tarea (getNextTask()), detectando si la siguiente en cola es de tipo quiz y todavía hay diapositivas en ejecución; de ser así, saltarla temporalmente
GitHub
. Esta opción agrega complejidad pero garantiza estrictamente que el quiz solo arranque cuando no queda ninguna diapositiva pendiente (ni en cola ni en ejecución).
Implementando cualquiera de estas medidas (o ambas), el quiz no se generará prematuramente. Deberá probarse con diferentes escenarios (pocas diapositivas vs. muchas) para verificar que el quiz realmente espera hasta el final.

Incrementar la utilización del pool de 5 workers en la generación de diapositivas:

Paralelizar la generación del “esqueleto” de diapositivas: En la fase de creación de diapositivas a partir de secciones, reemplazar el enfoque secuencial por uno paralelo. Si un tema tiene, digamos, 5 secciones derivadas del contenido teórico, se podrían lanzar hasta 5 tareas concurrentes (una por sección) en el pool de workers
GitHub
. Cada tarea generaría las diapositivas de su sección de forma independiente. Habrá que ajustar la recopilación de resultados (por ejemplo, combinar las diapositivas generadas de todas las tareas para reconstruir el flujo completo en el orden correcto una vez terminen). Esto aprovechará todos los workers disponibles desde el inicio de la fase de diapositivas.

Aumentar maxConcurrentTasks del pool: Revisar la configuración global del workerPoolService. Para realmente usar los 5 workers simultáneamente, establecer maxConcurrentTasks: 5 (en lugar de 2)
GitHub
GitHub
. De este modo, el dispatcher podrá asignar tareas a los 5 workers sin limitación artificial (actualmente solo permitiría ~2 concurrentes). Habrá que probar el impacto en la API de IA para asegurar que soporta ese paralelismo; pero si se busca la máxima velocidad, este cambio es necesario para cumplir lo de “poner a trabajar a los 5”.

Verificar distribución balanceada: Con lo anterior, el dispatcher ya se encargará de repartir las tareas entre workers libres en orden ascendente de ID
GitHub
. No obstante, confirmar con pruebas que si hay, por ejemplo, 10 diapositivas por generar, el sistema efectivamente asigna 5 al inicio (ocupando los 5 workers) y conforme se libere uno vaya asignando las restantes. La clave es remover cualquier lógica residual de “sección por sección” para que todas las diapositivas independientes puedan despacharse en paralelo
GitHub
.

Corrección de la actualización de estado y notificaciones en la UI:

Suscribirse a eventos de generación: En el componente que inicia la generación (por ejemplo, ParallelGenerationControls.tsx o similar), agregar suscriptores a los eventos que emite el servicio de generación automática. Especialmente manejar onPhaseCompleted, onGenerationCompleted y onGenerationFailed. Al recibir el evento de generación completada, la interfaz debe:

Ocultar o actualizar cualquier toast/spinner de “Generando…” que siga visible (cambiar el ícono a éxito y el mensaje a “Generación completada”, por ejemplo)
GitHub
GitHub
.

Marcar visualmente cada fase como completada en el panel de estatus (e.g., si hay un GenerationStatusPanel con indicadores para teoría, slides, quiz, ponerlos en estado success cuando terminen)
GitHub
.

Rehabilitar botones o acciones que estaban deshabilitados durante la generación. Por ejemplo, reactivar el botón de “Generar contenido” (o “Regenerar”) para permitir lanzarlo de nuevo sin refrescar la página
GitHub
. También permitir la navegación entre diapositivas si estaba bloqueada.

Asegurarse de actualizar el estado global de generación (ej. currentJob) a null o completed una vez termina, de forma que canStart vuelva a ser true inmediatamente
GitHub
. Esto quitará la apariencia de que el botón sigue bloqueado tras finalizar la generación.

Encadenamiento automático de fases (en flujo secuencial): Si se mantiene un modo secuencial fase-por-fase (como el AutomaticGenerationService actual), revisar que tras completar cada fase se invoca a la siguiente automáticamente sin requerir múltiples clics. Idealmente, un solo clic en “Generar contenido teórico” debería desencadenar todo el pipeline hasta el quiz, mostrando el progreso paso a paso. Si actualmente el profesor tiene que hacer clic nuevamente para “Generar diapositivas” luego de la teoría, eso debe automatizarse (o presentarse como pasos muy claros). Revisar la función executePhases del servicio para asegurarse de este flujo continuo
GitHub
.

Manejo de notificaciones (toasts): Verificar si las notificaciones de progreso persistentes se cierran o cambian de estado cuando corresponden. Por ejemplo, usar una notificación tipo “Proceso finalizado” que reemplace al de “En progreso” una vez onGenerationCompleted ocurra
GitHub
. Si las toasts son manejadas por un estado interno, actualizar/limpiar ese estado al terminar para que no queden “pegadas”.

Montar todas las aplicaciones del usuario en el menú lateral:

Identificar el código donde se construye el menú de aplicaciones en la UI (podría ser un componente de menú o parte del estado global tras login). Asegurarse de que se carguen todas las apps a las que el usuario tiene acceso, en lugar de una lista fija. Puede requerir una llamada al backend para obtener las apps habilitadas o leer una configuración completa.

El comentario “no hace falta usar clone ni datum para eso” sugiere que quizás se estaban filtrando o limitando las apps innecesariamente. Hay que eliminar cualquier condición que excluya apps personalizadas del usuario. Si el usuario tiene, por ejemplo, 5 aplicaciones disponibles, todas deben mostrarse.

Probar después del cambio que, al iniciar sesión con distintos usuarios, el menú refleje correctamente las herramientas o módulos disponibles para cada uno
GitHub
. Esta tarea es más de asegurar consistencia en la UI y no afecta la generación de contenido, pero fue solicitada.

(Opcional) Unificar o simplificar el flujo de generación:
Actualmente existen dos rutas de código paralelas (secuencial vs. paralelo) que aumentan la complejidad y dieron lugar a inconsistencias. Sería valioso a mediano plazo decidir por un enfoque unificado:

O bien usar siempre el flujo secuencial fase a fase para la generación de un solo tema (más fácil de controlar el orden estricto), y reservar el modo paralelo solo para escenarios de batch real (por ejemplo, generar múltiples temas en simultáneo).

O mejorar el flujo paralelo introduciendo las dependencias arriba mencionadas, de forma que respete completamente el orden lógico, y entonces adoptarlo también para generación de un solo tema.

Cualquiera sea la decisión, eliminar código duplicado hará el sistema más mantenible y reducirá bugs. Por ejemplo, si ParallelGenerationService se hace robusto con control de dependencias, podría reemplazar al secuencial, unificando todo en un solo pipeline de generación
GitHub
. Esta unificación excede la corrección inmediata, pero se recomienda considerarla una vez resueltos los bugs urgentes.

Backend

Modelo de datos para contenido por diapositivas:

Verificar/Agregar campo de relación padre: Asegurarse de que el modelo de contenido (TopicContent o VirtualTopicContent) soporte enlazar diapositivas individuales con su tema o contenido principal. Por la documentación, debería existir un campo parent_content_id o similar
GitHub
. Si no está aún, añadirlo. Alternativamente, podría usarse un campo topic_id para todas las diapositivas del tema y un campo especial para marcar el contenido teórico principal. Lo importante es que podamos relacionar varias diapositivas y quizzes a un mismo tema.

Guardar cada diapositiva como contenido separado: Cuando el frontend envíe las diapositivas generadas, el backend debe crear múltiples registros en la colección (uno por diapositiva, más el quiz, etc.). Cada registro con su content_type ("slide", "quiz", etc.), título, orden, y datos correspondientes
GitHub
. Por ejemplo, si un tema genera 1 contenido teórico, 5 diapositivas y 1 quiz, habría que insertar 7 documentos de contenido. Usar el campo de relación (parent o topic) para vincularlos bajo el mismo tema.

No duplicar el texto teórico completo en cada diapositiva: Las diapositivas solo deben almacenar su propio fragmento de contenido (y posiblemente el texto narrativo de esa diapositiva). No guardar todo el contenido teórico en cada slide. Si se necesita contexto completo, para eso está la relación de parent o la referencia al tema principal
GitHub
. Esto ahorra espacio y evita inconsistencias. El contenido teórico completo puede guardarse como un TopicContent separado de tipo "text" o "theory" (si así se define), y las slides referencian a ese. En la base actual, hemos visto que cada slide guarda un JSON con su título, fragmento de markdown, narrative_text, etc., bajo content – eso está bien, pero asegurarse de separar concern: slide_template (estilos globales) se puede repetir en cada slide para render, aunque quizás sea más eficiente almacenarlo una vez a nivel del tema.

Almacenamiento del Quiz como contenido interactivo:

Representar el quiz también como un contenido individual en la base de datos. Es decir, insertar un TopicContent con content_type = "quiz" asociado al mismo topic_id o parent_content_id que las diapositivas
GitHub
. De esta forma, el quiz se integra al sistema de contenidos unificado.

En el campo content de ese registro, almacenar la estructura JSON de las preguntas generadas. Probablemente el servicio de generación de quiz ya devuelve un objeto con preguntas, opciones, respuestas correctas y explicaciones. Guardar ese objeto tal cual (quizá dentro de un campo content_data o similar), validando que cumpla el formato esperado
GitHub
. Por ejemplo, incluir también un título descriptivo (ej. "title": "Quiz - Nombre del Tema") y quizás un conteo de preguntas (question_count) para facilidad de consulta
GitHub
.

Asegurarse de marcar claramente este contenido para que la UI lo reconozca como quiz interactivo. Ya existe seguramente una enumeración de tipos de contenido y quiz debe ser uno de ellos. Así, en la interfaz del estudiante se podrá mostrar adecuadamente (un botón para iniciar quiz, etc.).

Endpoint para registrar contenidos generados automáticamente:

Implementar (o completar si existe parcialmente) un endpoint HTTP en el backend para que el frontend envíe todos los contenidos generados de un tema y se persistan de una vez. El diseño podría ser un POST a /api/content/bulk o similar, que reciba un payload con el topic_id y una lista de contenidos. De hecho, ya existe un endpoint genérico POST /api/content/ para crear contenido individual
GitHub
, pero conviene uno optimizado para creación masiva.

En este endpoint, iterar sobre la lista de contenidos recibidos y hacer inserciones en la colección. Validar que el usuario tenga permiso (rol profesor o admin y sea dueño del topic)
GitHub
. Asignar los campos necesarios: topic_id (el tema en cuestión), order (según el orden dado), generar nuevos IDs si no vienen, timestamps, etc.
GitHub
.

Usar operaciones en lote (por ejemplo, insert_many en Mongo) para insertar todas las diapositivas de una sola vez
GitHub
. Esto es más eficiente que múltiples llamadas separadas.

Manejar el contenido teórico principal: si el flujo lo contempla, también podría enviarse y guardarse como un contenido de tipo texto (por ejemplo content_type: "text" o "theory"). Alternativamente, puede que el contenido teórico no se guarde como content independiente si solo sirve para generar las slides – pero sería útil almacenarlo para referencia. Decidir esta parte según la lógica de negocio (posiblemente se guarda como una diapositiva de tipo especial, o simplemente como campo parent en el quiz).

Retornar una respuesta apropiada al frontend, idealmente con los IDs generados para cada contenido (o un indicador de éxito por cada uno)
GitHub
. De este modo, el frontend podría actualizar su estado local si necesitara los IDs (por ejemplo, para enlazar recursos posteriormente).

Nota: Si ya existe un endpoint para crear contenido individual, el frontend podría llamarlo repetidamente para cada slide y quiz. Sin embargo, eso sería menos eficiente y más propenso a errores a mitad de camino. Mejor implementar la creación masiva para la generación automática.

Regeneración de contenido y limpieza previa:

Definir cómo se manejará si un profesor regenera el contenido de un tema que ya tenía diapositivas y quiz guardados. Una estrategia es sobrescribir completamente: antes de guardar los nuevos contenidos, borrar (o marcar como obsoletos) los contenidos previos generados automáticamente para ese tema, para no duplicar. Esto implica quizás eliminar todos los TopicContent de ese topic que tengan cierto flag (p.ej. un campo ai_credits: true o tipo slide/quiz generados automáticamente).

Alternativamente, se podrían versionar los contenidos o conservar manualmente creados. Este es un detalle de UX/negocio a acordar. Probablemente lo esperado es que al regenerar, reemplace lo anterior. Por lo tanto, implementar esa limpieza: al iniciar una nueva generación, el backend podría eliminar los contenidos viejos del tema (quizás exceptuando los añadidos manualmente por el profesor, si aplica). Si se hace del lado frontend, al enviar el POST de nuevos contenidos podría incluir una bandera “replace”: true.

En cualquier caso, documentar esta decisión y asegurarse de que el endpoint lo soporte sin dejar datos huérfanos. Esto prevendrá que se acumulen múltiples sets de diapositivas para un mismo tema en la base.

Ajustar el seguimiento de progreso con múltiples contenidos por tema:

Con la introducción de varios contenidos por tema (diapositivas, quiz, etc.), revisar cómo el sistema marca un tema como completado para el estudiante. Antes, un tema con un solo contenido podía marcarse completo cuando ese contenido llegaba al 100% visto. Ahora, se debería requerir que todas las diapositivas sean vistas y el quiz realizado para considerar el tema terminado al 100%.

En ContentResultService o donde se calculen los resultados, implementar la lógica de agregación: por ejemplo, si un tema tiene 6 diapositivas y 1 quiz (7 ítems en total), el progreso del tema podría ser la fracción de ítems completados por el estudiante
GitHub
. Podría bastar con que cuando un contenido individual se marca como completado, el sistema cheque si todos los contenidos de ese topic lo están, y entonces marcar el topic como completo. O mantener un campo de porcentaje de avance del topic sumando los avances individuales.

Este cambio asegurará que la experiencia del alumno sea consistente con la nueva estructura: que el sistema sepa que un tema ahora es un conjunto de piezas y no solo una. También hay que verificar compatibilidad con temas antiguos (los que siguen teniendo un solo contenido "legacy") – en esos casos la lógica debería seguir funcionando (un único item = progreso del tema directamente basado en ese item)
GitHub
.

Registro de logs y manejo de errores en la generación:

Añadir logs en puntos clave del backend para facilitar depuración y monitoreo de la funcionalidad de generación automática. Por ejemplo, al iniciar la generación (cuando el profesor presiona el botón y quizás se llama al endpoint para obtener el prompt o similar) loguear algo como “Generación AI iniciada para topic X por user Y”. Al finalizar y guardar, loguear “Generación completada: N diapositivas + 1 quiz guardados para topic X”
GitHub
. Esto ayudará a trazar el flujo en entornos de prueba y producción.

Robustecer el manejo de errores: si la IA devuelve un JSON malformado (por ejemplo, en el quiz), o si alguna diapositiva viene vacía, el backend debe capturar eso. Devolver mensajes de error claros al frontend en caso de fallos, para que la UI pueda notificar al profesor (“La generación falló en la diapositiva 4, reintente”, etc.)
GitHub
. También sanitizar el contenido generado antes de guardarlo por seguridad (evitar HTML malicioso en el JSON, por ejemplo).

Monitorear performance: la generación con IA puede ser lenta o fallar por timeouts. Sería útil instrumentar tiempos de respuesta o contadores de uso de la API (AI credits) para asegurar que todo entra en los límites y, si no, que se informe correctamente.

Depuración de código legado:

A medida que se implemente lo anterior, retirar referencias obsoletas al sistema antiguo de content_type = "slides" (contenido monolítico). Por ejemplo, hay condiciones en el código que aún revisan si content_type es "slides" (plural) vs "slide"
GitHub
. Si la migración a diapositivas individuales es total, esas bifurcaciones de código pueden limpiarse para reducir complejidad.

Ejecutar el script de migración (migrate_slides_to_individual.py) en los datos si no se ha hecho, para convertir contenidos legacy en múltiples slides. Confirmar que ninguna funcionalidad crítica dependa ya del formato antiguo antes de eliminarlo.

Esto mantendrá el código más claro y asegurará que no haya comportamientos inesperados por compatibilidad con formatos viejos.

Conclusiones

Implementando las tareas anteriores, el sistema quedará alineado con los requerimientos iniciales y se resolverán los inconvenientes observados:

El quiz se generará estrictamente al final, una vez listas todas las diapositivas, respetando la secuencia lógica y evitando condiciones de carrera
GitHub
GitHub
.

Los 5 workers se utilizarán en la medida esperada, acelerando la creación de diapositivas (múltiples a la vez) y reduciendo el tiempo total de generación
GitHub
GitHub
.

La interfaz de usuario reflejará correctamente el progreso: los indicadores de carga desaparecerán en cuanto termine cada fase, se marcarán los checks de éxito y el botón de generar quedará habilitado de nuevo inmediatamente
GitHub
GitHub
. El profesor verá cada etapa completada en tiempo real, sin toasts colgados.

El backend soportará la nueva estructura de sub-contenidos (diapositivas individuales y quiz) bajo un tema, almacenándolos adecuadamente y relacionándolos. El sistema de seguimiento de progreso reconocerá estos subcontenidos, asegurando que la experiencia del estudiante sea consistente (por ejemplo, deberá recorrer todas las diapositivas y completar el quiz para finalizar el tema)
GitHub
.

Adicionalmente, se corregirá el detalle del menú de aplicaciones de usuario para mostrar todas las herramientas disponibles, mejorando la navegación en la plataforma.

En conclusión, estas mejoras atienden tanto las correcciones inmediatas de bugs como ajustes arquitectónicos de fondo para que la generación automática de contenido con IA funcione de forma fluida, rápida y ordenada, cumpliendo con lo esperado. Cada modificación deberá ser probada rigurosamente (pruebas unitarias y pruebas manuales) para garantizar que cumplen su objetivo sin introducir regresiones. Con este plan implementado, SapiensAI podrá ofrecer a los profesores una experiencia confiable al generar presentaciones en diapositivas y quizzes de manera automática, optimizando el flujo de trabajo educativo.