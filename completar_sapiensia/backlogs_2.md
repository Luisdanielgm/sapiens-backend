Módulos Virtuales Personalizados y Generación Progresiva
Backlog del Cliente:
Ok, te voy a comentar otra cosa que tiene que ver con los módulos virtuales Lamentablemente se ha perdido mucho el contexto de las características O mejor dicho, muchas de las características que se querían para el módulo Lo que te pasé resumido, quizás no abarque todo lo que se quiere O todas las directrices que se dieron Una de ellas era que los módulos virtuales tenían que ser Construidos progresivamente, por ejemplo Vamos a describirte textualmente cómo sería una interacción con un módulo... Cuando el alumno presiona el módulo Si este módulo no ha sido creado Por primera vez se está creando Él carga, comienza a cargar Personaliza este tema O este módulo, estos contenidos virtuales, perdón... La cola de procesamiento para crear, que es que cuando un módulo virtual se puede crear solamente si ya hay temas para virtualización, es decir, que se han publicado para virtualización, que sí cumplen los requisitos de tener tipo de contenido, ¿no? Si un módulo tiene todos sus temas listos para virtualización, este va a crear primero los tres primeros módulos, los tres primeros temas virtualizados, entonces, ¿por qué los tres primeros? Porque va a crear uno y dos van a estar listos para ser usados. Cuando pase al segundo tema, entonces el tema cuatro va a ser virtualizado, ¿por qué? Siempre tienen que haber dos temas en cola. Cuando se pase al siguiente módulo, al siguiente tema del alumno, automáticamente se comienza a crear por detrás, se comienza a crear o a virtualizar el siguiente tema. Y así siempre van a tener dos temas en cola virtualizados. Entonces, esto siempre va a ocurrir sin que el alumno se dé cuenta. La única vez que el alumno va a tener que esperar para que un módulo se virtualice es la primera vez que se van a crear los tres primeros módulos. Y es más, se puede crear el primer tema, perdón, y luego que se están creando los otros dos temas, pero el alumno ya puede acceder al primer tema mientras por detrás se están creando, virtualizando los dos temas siguientes... Al ya tener, estar en faltar dos temas, nada más del módulo para virtualizar, ya virtualizado para completar, y el siguiente módulo ya tiene temas virtualizados, entonces se cumple la misma regla, pero se van a comenzar a virtualizar los temas del otro módulo. ¿Por qué? Porque ya se están acabando los temas del módulo y siempre tenemos que tener dos módulos por delante.
La sección de cada modotema virtual tiene que incluir una evaluación, por eso es que en los tipos de contenido para un tema ser habilitado tiene que incluir la evaluación, tiene que incluir un template de pensamiento crítico, todos los contenidos tienen que ser interactivos.
Requerimiento Consolidado: Cada curso tiene un plan de estudios (Study Plan) con módulos y temas creados por el profesor. Para cada alumno, el sistema genera un Módulo Virtual por cada módulo del plan, adaptado a su perfil. Los módulos virtuales se crean progresivamente: al iniciar un módulo virtual por primera vez, se generan los contenidos del primer tema para acceso inmediato y, en segundo plano, los de los siguientes 2 temas para tener siempre un “colchón” de temas disponibles. A medida que el alumno avanza, el sistema debe mantener al menos dos temas futuros ya virtualizados. Si un módulo casi termina (el alumno supera ~80% de progreso), automáticamente comienza la virtualización de los temas del siguiente módulo del plan, asegurando que siempre haya dos módulos por delante listos.
Regla de Negocio para Habilitación: Un tema solo puede habilitarse para virtualización si cumple con los siguientes requisitos:
Incluye al menos un contenido de tipo evaluación.
Incluye al menos una plantilla de pensamiento crítico.
Todos sus contenidos asociados son de naturaleza interactiva.
Cola de Generación Progresiva
Requerimiento Consolidado: La creación de módulos/temas virtuales debe manejarse con una cola de tareas (VirtualGenerationTask) para procesar en segundo plano la generación por IA sin bloquear la experiencia del usuario. Las tareas pueden ser de tipo “generate”, “update” o “enhance”, con prioridades. El sistema debe encolar tareas automáticamente (ej. al llegar a 80% de un tema) y gestionar reintentos en caso de fallos.
Personalización de Contenidos y Perfil Cognitivo
Backlog del Cliente:
ok la falta de personalización todavía falta que evalúe cómo se están personalizando los recursos los contenidos necesito que ese tema lo separe de todo lo que te he dicho y lo abarques de forma individual la personalización de los módulos virtuales de los temas virtuales y los contenidos virtuales... Revisa cómo funciona la personalización... quiero que revises esa parte Cómo hay dos formas de personalización La personalización de elección de tipos de contenido... Y la otra personalización es a nivel de contenido... el contenido muchas veces es código Esta personalización es a nivel de solo los tipos de contenido Que son códigos, son formatos JSON... Después que se integren los nuevos tipos de contenidos, se van a elegir solo los tipos de contenidos que se adapten al perfil cognitivo, vas a revisar la estructura del perfil cognitivo... hay tipos de contenidos que van a abarcar el tema completo y hay otro tipo de contenidos que solo se van a enfocar en una parte del tema... un video que abarque todo el contenido... pero por lo menos un juego de las mutaciones puede abarcar un concepto... tienes que tenerla en cuenta cuando personalices eligiendo los tipos de contenidos... no vayas a poner todos los contenidos que abarquen nada más una parte del tema, y el resto del tema, ningún contenido lo toca... la directriz era que se intercalaran las diapositivas entre los tipos de contenido para que explicaran un contenido y después una parte del tema y luego un juego o una dinámica, esa era la idea, pero aún no se intercala.
Requerimiento Consolidado: El sistema debe adaptar los contenidos según el perfil de aprendizaje de cada estudiante. Esto incluye:
Selección de Tipos de Contenido: Se elige un conjunto equilibrado de contenidos (ej. ~6 por tema) que se adapten al CognitiveProfile del alumno. Se debe asegurar un balance: debe haber al menos un contenido “completo” (que cubra todo el tema, como un texto o video), mientras que otros contenidos interactivos (juegos, diagramas) pueden enfocarse en subtemas concretos. En conjunto, deben cubrir todo el material sin dejar lagunas.
Adaptación a Nivel de Contenido: Para contenidos específicos como texto o código, se pueden personalizar fragmentos según el contexto del estudiante.
Intercalación de Contenidos: El sistema debe ordenar y presentar los contenidos de forma intercalada para crear una experiencia de aprendizaje dinámica (ej. diapositiva -> juego -> diapositiva -> diagrama), en lugar de agruparlos por tipo.
El modelo CognitiveProfile del estudiante (que almacena estilos VARK, diagnósticos, intereses) es la base para esta personalización.
Motor de Personalización Adaptativa (Aprendizaje por Refuerzo)
Backlog del Cliente:
Ok, otra cosa de personalización que quiero que incluyamos hasta ahora es el perfil cognitivo... quiero hacer otro motor de personalización, pero que no va a eliminar el anterior, es decir, lo va a complementar. Esto es que por el Content Results, con una guía de aprendizaje por refuerzo, se puede alimentar esta guía de aprendizaje por refuerzo y las evaluaciones, los tipos de contenido que tengan mejor resultado, son las que van a alimentar este perfil del estudiante... Lo que va a alimentar esta guía va a ser el resultado de la ponderación de los resultados de los contenidos por usuario. Es decir, el que tenga mejor resultado porque el estudiante aprendió mejor con ese tipo de contenido... quizás una pregunta al usuario al final de los temas o los módulos, cómo te encantó aprender mejor con este tipo de recursos, con qué, y así.
Otra cosa que necesito hacer para la personalización en la parte del aprendizaje por refuerzo, vamos a hacerlo en dos etapas. La primera personalización que vamos a hacer con Content Results, lo que vamos a hacer es, matemáticamente o estadísticamente, sin integrar Inteligencia Artificial por los momentos, porque estamos usando Vercel, y lastimosamente Vercel no tiene serverless, entonces vamos a hacer algo, vamos a dejar bien claro en la documentación, y en este servicio, es decir, vamos a crear un servicio en el backend, que sería el que estime, o el que haga esta personalización por refuerzo, pero vamos a dejar establecido en un comentario, bien clarito, que por los momentos se va a utilizar matemática o estadística, para sacar los contenidos que se van a usar. Este Content Results, cuando obtengamos todos los Content Results del usuario, necesito que ahora, como vamos a manejar esto por plantillas, los tipos de contenido ahora van a ser plantillas, lo que necesito es que, con la descripción de estos tipos de contenidos, de estas plantillas, las etiquetas que se tengan de ellos, se saque una estimación, matemáticamente o estadísticamente, de los contenidos que más benefician al alumno. O puede ser un análisis de, ah, bueno, se usan más visuales y auditivos, sobre todo los que usan voz, los que usan los videos, sobre todo los que tienen que escribir, o los que tienen que hacer esto, los de tipo diagrama, o los de tipo interacción de simulación, así pues. Pero vamos a hacerlo con los resultados como teníamos estimado hacer el de aprendizaje por refuerzo. Pero, en vez de aprendizaje por refuerzo, vamos a utilizar eso por los momentos. Ya la segunda etapa va a ser, vamos a utilizar el modelo de inteligencia artificial y aprendizaje por refuerzo. Pero lo que quiero es que dejen claro en ese servicio que vamos a crear, el backing, de que va a constar de dos etapas y por los momentos se va a utilizar así. Va a funcionar de esa manera.
Requerimiento Consolidado: Además del perfil estático, el sistema incorporará un motor adaptativo que aprende de los ContentResult. Se implementará en dos fases:
Fase 1 (Motor Estadístico): Se creará un servicio en el backend que operará sin IA. Este servicio analizará el historial completo de ContentResult de un alumno. Correlacionará las puntuaciones obtenidas con las características de las plantillas de contenido correspondientes (ej. styleTags, subjectTags, baselineMix V-A-K-R). A través de un análisis estadístico, determinará qué tipos de interacciones y formatos (ej. "muy visual", "basado en texto", "simulaciones kinestésicas") generan mejores resultados para el alumno, ajustando las recomendaciones futuras. El código de este servicio debe incluir un comentario destacado explicando que es una implementación de Fase 1, limitada por la infraestructura actual, y que está diseñada para ser reemplazada por un modelo de RL.
Fase 2 (Motor de Aprendizaje por Refuerzo): En el futuro, el motor estadístico será reemplazado por un modelo de aprendizaje por refuerzo (RL) para una optimización más profunda y dinámica de la personalización, pudiendo incluir feedback subjetivo del alumno.
Tipos de Contenido Educativo (Visión Previa)
Backlog del Cliente:
Quisiera que hubieran más contenidos. Más tipos de contenidos diferentes que se adapten, quiero aumentar la cantidad de contenidos... quiero que también busques otros tipos de contenido, como ya te dije, que se puedan integrar. Incluso tipos de contenido que sean dinámicas como tipo juego, de completación, puede ser de completación, puede ser matemáticas, ejercicios matemáticos, es decir, y glosarios... tenemos que buscar más tipos de contenido evaluativo, así como quiz, pero que sean más dinámicos o más, que no sean tan tradicionales como el quiz. Incluso Gemini Live es uno de ellos.
Requerimiento Consolidado: La plataforma debe soportar y buscar activamente ampliar su catálogo de tipos de contenido, especialmente formatos dinámicos y de evaluación formativa no tradicionales como GEMINI_LIVE (conversaciones con IA), ejercicios de programación con auto-verificación, ejercicios matemáticos y glosarios interactivos. (Nota: Este requerimiento es la base para el nuevo sistema de plantillas).
Generación Automática de Contenidos con Múltiples Modelos (Aceleración)
Backlog del Cliente:
En la generación de los tipos de contenido o de los contenidos en la vista del profesor... quiero que no se cree uno por uno, sino que los crees de tres en tres. Es decir, mientras que se está generando con un modelo, se está generando el diagrama, con otro modelo se está generando la evaluación y con otro modelo se está generando el texto, por poner un ejemplo... siempre tienen que haber tres modelos disponibles para estar generando al mismo tiempo tres cosas... Si falla un modelo generando un tipo de contenido, ese tipo de contenido se le va a asignar a otro modelo... Si recargo la página o si me voy a otro sitio, la generación de contenido siga y aparezcan... esos mensajitos que dicen que se está generando el contenido.
Como no se piensa eliminar toda la parte de la lógica de los contenidos y todo eso, lo que necesito es que todos los contenidos ahora, ahorita cuando se presiona el botón de contenido en general, contenido teórico, nada más se generan como tres tipos de contenidos, necesito que todos los contenidos disponibles, incluyendo la parte de texto y eso también se genera automáticamente, y que los TWAS cuando se comience a generar, se muestren los TWAS de cada uno de los contenidos generando el momento, y si son las diapositivas se genere uno de las diapositivas, pero se muestra diapositiva 1, generando diapositiva 2, generando diapositiva 3, así, en la presentación, necesito que tengan una X para quitar el TWAS de ser necesario, y que cuando se genere contenido teórico se quite, y que es nada más lo que se está generando en el momento.
En la generación de contenido, que todavía no lo vamos a eliminar, eso todavía no se va a eliminar, ni se va a modificar ni nada, ahí lo que necesito es que cuando se estén generando, cuando se genere el contenido teórico, que se comiencen a generar todos los contenidos que se faltan, esos contenidos necesito que se generen simultáneamente, no uno por uno, sino de 5 en 5, si hacen falta las diapositivas, se generan las 5 láminas de la diapositiva. ¿Cómo quiero que esto ocurra? Bueno, agarramos los modelos que estamos utilizando y generamos, si son 5, si hay 3 modelos nada más disponibles, vamos a crear un archivo de servicios o algo donde podamos tener los 5 hilos y podemos cambiar el modelo que queremos utilizar en esos 5 hilos. Van a ir simultáneamente, es decir, si tengo 3 nada más para crear, uso 3 hilos, si tengo 6 o 7, se usan los 5 hilos primero y apenas termino un hilo de trabajar en un contenido, comienza a trabajar en los que hacen falta. Tienen que ser simultáneos y asíncronos, es decir, trabajar todos por su lado, esto es para reducir el tiempo en el que se quedan los contenidos y tienen que ser configurables, como te digo, que en el código se pueda configurar que modelo van a trabajar con cada hilo. Por ejemplo, incluso podría ser que trabajemos con Gemini 2.5 Flash en 2 hilos o en 3 hilos, quiere decir que se van a hacer 3 peticiones a Gemini al mismo tiempo y 2 se las vamos a hacer a Open Router, entonces 2 nada más se van a hacer a Open Router simultáneamente. Entonces tienen que ir por orden, hilo 1, 2, 3, 4, 5, si termina el 2 de trabajar y todavía queda un contenido, el 2 comienza a trabajar, si termina el 2 y el 4 y hay una tarea todavía sin resolver, entonces el hilo 2 es el que comienza a trabajar.
Requerimiento Consolidado: Para poblar rápidamente los contenidos de un tema en la vista del profesor (sistema legacy), el sistema debe:
Generación Masiva: Al solicitar la generación del contenido teórico, el sistema debe disparar automáticamente la generación de todos los demás tipos de contenido disponibles para ese tema.
Pool de Hilos Asíncronos: La generación se gestionará mediante un pool de 5 hilos (workers) asíncronos que operarán en paralelo. Si hay más de 5 tareas, se encolarán y serán tomadas por el primer hilo que quede libre.
Configuración de Modelos por Hilo: Se creará un archivo de configuración en el backend que permitirá asignar un modelo de IA específico a cada uno de los 5 hilos (ej. Hilo 1: Gemini Pro, Hilo 2: Gemini Flash, Hilo 3: OpenRouter/Mistral, etc.). Esto permite una gestión flexible y distribuida de las peticiones a las APIs.
Notificaciones Persistentes y Granulares (Toasts):
La interfaz debe mostrar notificaciones de progreso (toasts) para cada contenido que se está generando (ej. "Generando Diapositiva 1/5", "Generando Quiz...", "Generando Diagrama...").
Cada toast debe incluir un botón de cierre (X).
El toast inicial ("Generando contenido teórico...") debe desaparecer una vez que los toasts de la generación paralela aparecen.
Las notificaciones deben persistir en la UI incluso si el usuario recarga la página o navega a otra sección.
Gestión de Fallos: Si la generación de un contenido por un hilo falla, la tarea debe reintentarse asignándola a otro hilo disponible.
Contenido Teórico con Principios Fundamentales
Backlog del Cliente:
También intentar que las explicaciones y la generación del texto y del contenido... tratar de hacerlo desde el principio fundamental de las cosas... Estamos usando el método Feynman... es tratar de explicar, por ejemplo... si yo aprendo cuál es el principio fundamental... yo puedo crear incluso recetas nuevas de pan.
Requerimiento Consolidado: Los contenidos de tipo texto explicativo deben generarse siguiendo la metodología de "primeros principios" / Feynman para garantizar una comprensión conceptual profunda en lugar de la memorización.
Desbloqueo, Seguimiento de Progreso y Actualizaciones de Módulos en Curso
Backlog del Cliente:
También revisa los marcadores de progreso, los marcadores como leído, el desbloqueo de los temas, el desbloqueo de los contenidos... Ok, algo importante es que tenemos que definir cómo se manejan las actualizaciones en los módulos virtuales... yo ahora en un módulo virtual... acabo de añadir un nuevo tipo de contenido que yo quiero que el alumno lo tenga, pero ya el alumno comenzó el tema virtual... ¿Qué me recomiendas?
Requerimiento Consolidado: La navegación sigue una secuencia lineal-condicional, desbloqueando ítems al completar el anterior. El progreso se registra a nivel de contenido, tema y módulo. Se debe definir una política para manejar cambios del profesor en módulos que los alumnos ya tienen en curso.
Política Propuesta:
Añadir contenido: El nuevo contenido se agrega al final de la lista de contenidos no vistos para todos los alumnos en curso.
Editar contenido: Las actualizaciones solo se reflejarán para los alumnos que aún no han visto ese contenido. El ContentResult de quien ya lo completó no se ve afectado.
Eliminar contenido: El contenido se elimina para los alumnos que no lo han visto. Para los que ya lo vieron, se mantiene el registro en su ContentResult pero el contenido deja de ser visible.
Gestión de Resultados de Contenido (ContentResult)
Backlog del Cliente:
Quiero saber si en Content Results se guardan los resultados de cada tipo de contenido, sea lo que sea Claro, yo estaba estableciendo que si era un contenido evaluativo, un contenido de un quiz o de un juego Se pudiera evaluar, pero esto cambiaría si es una lectura, si es una lectura, obviamente 100%... quiero que veas si el content result debería estar asociado al contenido virtual, lo que me parece. Pero investiga a ver con quién está asociado, si con el contenido o el contenido virtual.
Requerimiento Consolidado: Cada interacción del alumno con un contenido genera un ContentResult. Este modelo unifica los resultados (puntuación de quiz, completitud de lectura, etc.). Crucialmente, el ContentResult debe estar asociado directamente al VirtualTopicContent específico del alumno, para reflejar su interacción única y personalizada. Para contenidos no evaluativos como lecturas, se registrará un 100% al completarse. Para juegos o quizzes, la puntuación obtenida será el resultado.
Recursos, Entregables y Evaluaciones del Plan de Estudio
Backlog del Cliente:
Las evaluaciones... pueden ser evaluaciones asociadas no solo al tema, sino que pueden estar asociadas a varios temas... tiene que haber esa flexibilidad... el resultado de esas evaluaciones que están en el plan de estudio, tú puedes decidir si la ponderación la colocas manualmente... podría ser el resultado de un Content Result o de varios Content Result... Y es la tercera forma de ponderar una evaluación, es hacerla mediante un entregable... este es un nuevo tipo de recurso, que es un recurso entregable... hay otro tipo de recurso adicional... el recurso de la evaluación, es decir, el profesor asigna... un recurso que sea de apoyo a la evaluación como una rúbrica... el alumno lo descarga, y ahora ese recurso el Excel lo va a subir de nuevo, pero ya como entregable.
Requerimiento Consolidado: El sistema de evaluaciones formales del plan de estudio debe ser flexible y robusto.
Asociación Flexible (Many-to-Many): Una Evaluation debe poder asociarse a múltiples Topics, incluso si estos pertenecen a diferentes Modules, permitiendo evaluaciones transversales.
Ciclo de Vida de Recursos y Entregables: Se distinguen dos tipos de recursos:
Recurso de Apoyo (Plantilla): Un archivo proporcionado por el profesor (ej. rúbrica, PDF con instrucciones, archivo Excel con preguntas).
Entregable: El archivo subido por el alumno como respuesta. El flujo es: el alumno descarga el Recurso de Apoyo, lo trabaja y sube su versión final como Entregable.
Métodos de Calificación: La calificación de una Evaluation puede obtenerse de tres formas:
Manual: El profesor ingresa la nota directamente.
Automática por Contenido: La nota se calcula a partir del resultado de uno o varios ContentResult.
Basada en Entregable: El alumno sube un archivo que el profesor califica.
Módulo de Corrección Automática de Exámenes y Código
Backlog del Cliente:
Vamos a crear un nuevo módulo pero de revisión de exámenes... el profesor va a subir una foto a la aplicación... esa imagen se va a procesar con inteligencia artificial y automáticamente va a dar el resultado... el profesor puede decidir si los evalúa a él o si los evalúa automáticamente este criterio de evaluación... para ejercicios de programación... el alumno podría subir archivos HTML de Python... y la guía podría evaluarlo... o incluso podría ejecutar el programa en un pequeño sandbox.
Requerimiento Consolidado: Implementar un módulo para agilizar la corrección de pruebas (fotos, PDF), ensayos o código.
Flujo: El profesor sube la entrega del alumno y una rúbrica detallada. La IA procesa, califica y genera feedback.
Integración con Entregables: Este módulo se integra con el sistema de entregables. Si un profesor define una rúbrica para una tarea de tipo entregable, el sistema puede desencadenar la corrección por IA automáticamente cuando el alumno sube su archivo.
Revisión del Profesor: El profesor siempre tiene la última palabra y puede revisar, ajustar o anular la calificación de la IA.
Evaluación de Código: El sistema se extenderá para evaluar código ejecutándolo en un sandbox seguro y verificando que el resultado sea el esperado.
Sistema de Workspaces Unificado (en lugar de Multi-instituto)
Backlog del Cliente:
Un profesor puede estar en varios institutos... me han preguntado cómo ellos pueden utilizarlo para estudiar por su propia cuenta... he pensado en crear una suscripción... se cree un instituto general... que el instituto va a ser algo así como Academia Sapiens... Este mismo sistema me gustaría que lo tenga el profesor, pero en este caso, por si el profesor quiere dar una clase, quiere dar clases particulares.
Requerimiento Consolidado: ✅ COMPLETAMENTE IMPLEMENTADO Y OPERATIVO. El sistema ha migrado a un modelo de workspaces unificado. Un usuario puede operar en múltiples contextos (institucional, profesor particular, estudiante autodidacta) con una sola cuenta, gestionado a través de un selector de workspaces. Los usuarios individuales operan dentro de un workspace genérico "Academia Sapiens".
Marketplace de Cursos, Landing Page y Suscripciones
Backlog del Cliente:
Yo quiero que los planes de estudio... se puedan publicar, hacer público... SAPIEN va a tener un marketplace, y en ese marketplace, los cursos pueden tener costo... Tienen que tener en cuenta también el landing page de esta página... que el índex sea la ruta del landing page... Y quiero establecer un método de pago, un sistema de pago.
Requerimiento Consolidado: Habilitar un "Marketplace" donde los profesores puedan publicar sus planes de estudio para que otros usuarios se inscriban (gratis o pagando). La aplicación debe tener una Landing Page pública como ruta principal (/), con información y botones de registro/login. Se planea integrar un sistema de pago para gestionar suscripciones.
Gestión de API Keys de Usuario
Backlog del Cliente:
Quiero que las API se puedan configurar también, el usuario tenga en su opción de perfil, también que él pueda meter su API propia. Si el usuario no tiene API propia en su perfil, entonces lo que se hace es que se usa la del sistema, es decir, las claves de API, por lo menos la de Gemini, la de GRUB, ah, bueno, el usuario no ingresó la de él, se usa la del sistema de Gemini que ya está definido.
Requerimiento Consolidado: Implementar una sección en el perfil del usuario para que pueda introducir sus propias claves de API (ej. Gemini, Groq, OpenRouter). Al realizar una llamada a un modelo de IA, el sistema deberá:
Verificar si el usuario ha proporcionado su propia clave para ese proveedor.
Si existe, usar la clave del usuario.
Si no existe, usar la clave global del sistema como fallback.
Aplicación Móvil y Mejoras Generales de Interfaz
Backlog del Cliente:
Vamos a ir poco a poco creando una aplicación móvil hecha con React Native... Lo primero que va a hacer la aplicación... es que se puedan corregir los exámenes... Ok, ahora vamos a hablar de cosas más pequeñas... Una es la responsibilidad y el tema claro y oscuro... Eliminación de los archivos obsoletos, chequear que todas las peticiones a la API usen el Fetch Wish Without... Mejorar la eficiencia y rendimiento de la app... Los visores y los sandbox de contenido tienen que ser perfectos.
Requerimiento Consolidado: Desarrollar una app móvil (React Native), priorizando inicialmente la corrección de exámenes con IA para profesores y el cursado de módulos virtuales para alumnos. La plataforma web debe ser completamente responsiva, con tema claro/oscuro, código limpio y rendimiento optimizado. Los visores de contenido y sandboxes deben ser robustos y sin fugas de estilo.
Autenticación, Navegación y Dashboards
Backlog del Cliente:
Debemos agregar una autenticación con usuario y contraseña, correo y contraseña, y recuperación de contraseña... En la vista del alumno, en el Sidebar... no se está mostrando los módulos ni los temas... en las estadísticas que se muestran en los dashboards... hay cosas como el control de asistencia, que no creo que sea prudente llevarlo aquí... ya podríamos ir dando datos reales en el dashboard.
Requerimiento Consolidado: Añadir autenticación tradicional con email/contraseña y recuperación de contraseña, reutilizando la lógica de Google Auth. Corregir el bug del Sidebar del estudiante para que muestre los módulos y temas virtuales. Conectar los dashboards de todos los roles a datos reales del backend (progreso, calificaciones), reevaluando métricas no aplicables como el control de asistencia.
Plantillas de Juegos y Simulaciones:
Backlog del Cliente: A mí me gustaría guardar estos juegos como plantillas... hay un marketplace después de plantillas de juegos... la sección de generación de juegos y simulaciones es para generar juegos y simulaciones crudo o la base Que sería la plantilla... se puede utilizar para generar juegos solo cambiando algunas cosas.
Requerimiento: Crear una sección para generar plantillas de juegos/simulaciones. Un profesor puede crear una plantilla base y guardarla. Otros profesores pueden reutilizarla desde un "marketplace de plantillas" para adaptarla a sus propios temas. (Nota: Este requerimiento evoluciona hacia el sistema completo de Marketplace de Plantillas).
Lenguas Indígenas y Diccionarios:
Backlog del Cliente: Tampoco quiero que deje por fuera lo que es las lenguas indígenas y diccionarios. Revísalo simplemente.
Requerimiento: Revisar la funcionalidad existente y determinar los pasos finales para su completitud.
Herramientas de Concentración:
Backlog del Cliente: Las de Pomodoro... Pomodoro, Ruido y Canciones de Concentración... quiero que revises y qué más se podría implementar.
Requerimiento: Finalizar y pulir la interfaz del temporizador Pomodoro y los sonidos de concentración.
Eliminación en Cascada (Finalización):
Backlog del Cliente: La lógica de eliminación encascada no está terminada. Hay que terminarla tanto en el backend como en el frontend.
Requerimiento: Completar y probar rigurosamente la lógica de eliminación en cascada para evitar datos huérfanos.
Backlog del Cliente (Textual):
Voy directo: no se elimina topic_contents. Encima de él montamos plantillas e instancias sin romper compatibilidad. Reutilizamos la vista de “juegos y simulaciones” como una sola vista enfocada en: buscar, listar MIS plantillas, crear nuevas, editar, probar personalización en vivo, publicar/privatizar y abrir previsualizaciones en ventana aparte. El Marketplace público, por ahora, muestra solo plantillas publicadas.
Ok, entonces bueno, lo de los Marketplace educativos, entonces que funcionan como platillos iterables, en 3D, SVG, con código. Como ya lo dije, donde cada contenido no se especializa en un solo aprendizaje visual y netérico, sino que cambia un porcentaje de todo.
1) Modelo de datos
1.1 templates (plantillas globales o forks; nunca ligadas a topics)
code
Json
{
  "_id": "tpl_mindmap_v1",
  "name": "Mindmap Interactivo",
  "ownerId": "user_123",                 // autor/propietario
  "scope": "private",                    // private | public | org
  "status": "draft",                     // draft | usable | certified
  "personalization": {
    "isExtracted": false,               // ¿se extrajeron marcadores?
    "extractedAt": null
  },
  "engine": "html",                      // siempre HTML
  "version": "1.0.0",                    // semver
  "forkOf": null,                        // id de plantilla madre si es fork
  "html": "<!DOCTYPE html>...</html>",   // código estándar de la plantilla
  "propsSchema": { },                    // JSON Schema de params
  "defaults": { },                       // opcional (por si no van inline)
  "baselineMix": { "V":60,"A":10,"K":20,"R":10 },
  "capabilities": { "audio":false, "mic":false, "camera":false },
  "styleTags": ["interactivo","diagrama"],       // etiquetas de estilo/forma
  "subjectTags": ["astronomía","biología"]       // etiquetas temáticas
}
Estados: draft, usable, certified.
Visibilidad: scope controla si aparece en Marketplace público (public) o solo en “Mis plantillas”.
1.2 template_instances (contenido del profesor, ligado a un topic)
code
Json
{
  "_id": "inst_456",
  "templateId": "tpl_mindmap_v1",
  "templateVersion": "1.0.0",   // pin de versión
  "topicId": "topic_abc",       // instancia ligada a un topic
  "props": { },                 // parámetros de la instancia
  "assets": [{ "id":"bg","src":"/cdn/bg.png" }],
  "learningMix": { "mode":"auto","V":70,"A":10,"K":15,"R":5 },
  "status": "draft"             // publicación del contenido, no de la plantilla
}
1.3 topic_contents (se mantiene; fachada estable)
Se agregan campos (no rompemos nada):
code
Json
{
  "_id": "content_abc",
  "topic_id": "topic_abc",
  "content_type": "diagram",                 // legacy
  "content": { /* legacy */ },
  "render_engine": "legacy",                 // legacy | html_template
  "instanceId": "inst_456",                  // si usa plantilla
  "templateId": "tpl_mindmap_v1",
  "templateVersion": "1.0.0",
  "learningMix": { "V":70,"A":10,"K":15,"R":5 }, // cache para filtros
  "status": "draft"
}
1.4 virtual_topic_contents (vista del alumno; ya existente)
Añadimos (opcional) instanceId para resolver más rápido:
code
Json
{
  "_id": "vtc_999",
  "content_id": "content_abc",
  "instanceId": "inst_456",
  "student_id": "stu_123",
  "overrides": {
    "props": { "accentColor":"#2244ff" },
    "assets": [{ "id":"avatar","src":"/cdn/avatars/s_123.png" }],
    "difficultyAdjustment": 1,
    "vakHints": { "preferA": true }
  },
  "status": "active"
}
2) Niveles de personalización
De Contenido (instancia): cambia props/activos/textos; no toca el código.
De Plantilla (fork): clona la plantilla a tu propiedad y sí puedes modificar código y schema. Nunca se liga a topics.
Virtual (alumno): overlay por estudiante (no cambia instancia ni plantilla).
3) Marcadores y extracción
Convenciones dentro del HTML de la plantilla:
Param: data-sapiens-param="accentColor"
Asset: data-sapiens-asset="background"
Slot texto: data-sapiens-slot="introText"
Vars alumno: {{student.firstName}}
Condición: data-sapiens-if="student.level>=2"
Defaults inline: <script id="sapiens-defaults" type="application/json">{...}</script>
Extractor (pipeline): Lee data-sapiens-*, sugiere params por heurística, autor confirma, se genera propsSchema y se marca personalization.isExtracted = true.
Prueba de personalización (live): Panel para meter valores y ver cambios en tiempo real en preview, sin persistir.
4) V-A-K-R en todos los niveles
Plantilla: baselineMix obligatorio.
Instancia: cálculo auto por heurística + override manual.
Virtual: ajuste según perfil.
Marketplace: filtros por mix, badges “Muy visual”, “Auditivo alto”, etc.
5) UI — Reutilizar “Juegos y simulaciones” como “Mis Plantillas”
5.1 Una sola vista (lista + buscador): Header “Mis plantillas”, filtros rápidos, botón “Nueva plantilla”, grid de cards (solo del autor) con mini preview, badges, toggle Publicar/Privada, y botones: Usar, Ver, Editar, Clonar.
Importante: el código no se muestra por defecto, se ve un placeholder y se carga en modo avanzado (lazy-load).
5.2 Crear nueva plantilla (flujo): Click “Nueva plantilla” → card temporal → se abre ventana de preview dedicada → en vista principal, botones para: Extraer marcadores, Probar personalización, Guardar, etc.
5.3 Previsualización en ventana nueva: Siempre en iframe sandbox + CSP. Canal postMessage para comunicación.
6) Marketplace público (solo plantillas)
Ruta separada que lista todas las plantillas scope=public (usable o certified).
Filtros y acciones: Ver, Clonar, Usar.
7) Integración con topic_contents y transición suave
7.1 Reglas de resolución de render: render_engine determina si se usa el render legacy o el de html_template (basado en instanceId o templateId).
7.2 Uso dentro de diapositivas (slides) en Fase 1: Embed de un iframe con la instanceId.
7.3 Migración: Al pulsar “Usar como contenido”, se crea template_instance y se actualizan los campos en topic_contents para usar el nuevo motor.
8) APIs mínimas
Plantillas: POST /templates, GET /templates, POST /templates/:id/fork, PUT /templates/:id, POST /templates/:id/extract.
Instancias: POST /template-instances, GET /template-instances/:id, PUT /template-instances/:id, POST /template-instances/:id/publish.
Preview/Render: GET /preview/template/:templateId, GET /preview/instance/:instanceId.
Virtual: POST /virtual-contents, GET /virtual-contents/:id.
Contenido (fachada): GET /api/content/:id, PUT /api/content/:id.
Búsqueda/Marketplace: GET /api/marketplace/templates.
9) Seguridad y rendimiento
iframe sandbox + CSP estricta, código oculto (lazy-load), cache, previews en ventana aparte, validaciones.
10) Índices sugeridos
templates: { ownerId:1, scope:1, status:1, name: "text" }, { styleTags:1 }, { subjectTags:1 }
template_instances: { topicId:1 }, { templateId:1, templateVersion:1 }
topic_contents: { render_engine:1 }, { instanceId:1 }, { learningMix.V:-1 }
11) Heurística V-A-K-R (inicial)
Audio/TTS: +A20. Drag/slider: +K25, +V10. Texto largo: +R15. Gráficos: +V20. Normalizar a 100 y permitir override manual.
12) Pseudocódigo esencial (Se omite por brevedad en este documento final, pero la lógica está definida en el backlog del cliente).
13) Backlog por hitos (transición suave)
Hito A — Mis Plantillas (vista única): Listado, buscador, filtros, cards, acciones.
Hito B — Motor HTML + Extractor + Prueba Live: Runtime en iframe, extractor de marcadores, panel de prueba live.
Hito C — Instancias y Fijado de versión: Crear template_instance y actualizar topic_contents.
Hito D — Marketplace público (solo plantillas): Listado público filtrable.
Hito E — Slides + Embed: Bloque para embeber instancias en diapositivas.
Hito F — Certificación: Flujo de validación y estado certified.
14) Criterios de aceptación (clave)
topic_contents permanece como fachada. Plantillas no se ligan a topics, solo instancias. Dos niveles: instancia (props) vs fork (código). Preview en ventana nueva. Código oculto por defecto. V-A-K-R en todos los niveles.
15) Etiquetas
styleTags: interactivo, diagrama, quiz, slides, etc.
subjectTags: astronomía, biología, aviación, etc.
2. Estado Actual y Plan de Implementación Actualizado
(Sección eliminada para dar paso al nuevo Plan de Implementación)
3. Plan de Implementación Actualizado
A continuación se presenta el plan de trabajo actualizado, reestructurado para integrar todos los nuevos requerimientos, priorizando la transición suave al sistema de plantillas y la corrección de incoherencias críticas.
Tiempo estimado: 4-5 semanas
Correcciones de Backend Fundamentales:
B: Corregir la asociación del modelo ContentResult para que apunte a VirtualTopicContent. (Máxima prioridad técnica).
B: Corregir el bug en trigger_next_topic (cambiar progress < 0.8 por progress < 80).
F/B: Alinear los endpoints de Perfil Cognitivo (/api/profiles/cognitive) y Verificación de Usuario (/api/users/check).
Fundamentos del Ecosistema de Plantillas (Backend):
B: Implementar en la base de datos los nuevos modelos: templates y template_instances con todos los campos especificados.
B: Modificar los modelos existentes topic_contents y virtual_topic_contents para añadir los campos render_engine, instanceId, templateId, templateVersion, learningMix (cacheado) y overrides, asegurando la retrocompatibilidad.
B: Crear las APIs mínimas para el CRUD de plantillas: POST /api/templates, GET /api/templates?owner=me..., PUT /api/templates/:id.
Autenticación y Dashboards:
F/B: Implementar la autenticación con email/contraseña y el flujo de recuperación de contraseña.
F/B: Conectar los indicadores de los dashboards a los datos reales del backend (progreso, calificaciones), eliminando métricas obsoletas como el control de asistencia.
Corrección de Bugs de UI:
F: Implementar la lógica en el Sidebar del Alumno para manejar el caso de no tener módulos virtuales generados, ofreciendo iniciar la generación.
Tiempo estimado: 4-5 semanas
UI "Mis Plantillas" y Flujo de Creación (Hitos A y B):
F: Reutilizar y rediseñar la vista de "Juegos y Simulaciones" como "Mis Plantillas". Implementar el listado, buscador, filtros, y la card de plantilla con sus badges, toggles y botones de acción (Ver, Editar, Clonar, Usar).
F/B: Implementar el flujo completo de creación de plantillas, incluyendo la previsualización en ventana nueva (/preview/template/:id) y el editor de código con carga lazy.
B: Desarrollar el servicio Extractor de Marcadores (POST /api/templates/:id/extract) que parsea el HTML y genera/actualiza el propsSchema.
F: Implementar el panel "Probar personalización (live)" que se comunica con el iframe de preview vía postMessage para aplicar cambios de props en tiempo real sin guardarlos.
Instancias y Sistema de Evaluaciones Completo (Hito C):
B: Modificar el modelo Evaluation para permitir la asociación Many-to-Many con Topics.
F/B: Implementar el flujo de "Usar como contenido", que crea una TemplateInstance (POST /api/template-instances) y actualiza el TopicContent correspondiente para usar render_engine: 'html_template'.
F/B: Implementar el ciclo de vida completo de Recurso-Plantilla -> Descarga -> Entrega para las evaluaciones.
Vistas de Profesor Individual:
F: Crear las páginas /teacher/private-classes y /teacher/private-students.
B: Adaptar memberService.ts para soportar la inscripción directa.
Tiempo estimado: 3-4 semanas
Motor de Personalización Estadístico (Fase 1 de RL):
B: Crear el servicio backend que, a partir del historial de ContentResult de un usuario, analiza estadísticamente el rendimiento contra los tags y mix V-A-K-R de las plantillas para refinar el perfil cognitivo del alumno. Dejar documentado en el código su propósito transitorio.
Mejoras en Generación de Contenido Legacy:
B: Refactorizar el servicio de generación de contenido para usar un pool configurable de 5 hilos asíncronos, con asignación de modelos por hilo definida en un archivo de configuración.
F: Implementar las notificaciones (toasts) granulares y persistentes con botón de cierre para el proceso de generación de contenido.
Integración de IA y Gestión de APIs:
F/B: Implementar la sección en el perfil de usuario para que pueda introducir sus propias API Keys. Modificar los servicios de IA para usar estas claves como prioridad sobre las del sistema.
B/F: Conectar el servicio de subida de entregas con el CorrectionService para disparar la corrección automática por IA.
Tiempo estimado: 3-4 semanas
Lanzamiento del Marketplace Público y Funciones Avanzadas (Hitos D, E, F):
F/B: Desarrollar la vista pública del Marketplace (GET /api/marketplace/templates?scope=public...).
F/B: Implementar la capacidad de embeber instancias de plantillas dentro de diapositivas (iframe).
B: Implementar el flujo de "Certificación" para plantillas, con las validaciones correspondientes.
Finalización de Funcionalidades Pendientes:
F/B: Finalizar y pulir las Herramientas de Concentración (Pomodoro) y revisar el soporte a Lenguas Indígenas.
B/F: Completar y probar exhaustivamente la lógica de eliminación en cascada en todo el sistema.
Vistas de Estudiante Individual y App Móvil:
F: Crear las páginas /student/learning, /student/study-plan y /student/progress.
QA/Mobile: Iniciar el desarrollo de la aplicación móvil, comenzando con las funcionalidades priorizadas.
Conclusión del Análisis
El sistema SapiensIA ha alcanzado un estado de madurez significativo. La integración textual del nuevo backlog ha clarificado requerimientos críticos y ha definido una nueva arquitectura de contenido basada en Plantillas e Instancias. Esta arquitectura, diseñada para una transición suave, es la piedra angular del futuro de la plataforma.
La máxima prioridad ahora es doble:
Corregir la lógica fundamental del backend (asociación de ContentResult, flexibilidad de Evaluation) para alinearla con la visión del cliente.
Construir los cimientos del ecosistema de plantillas, tanto en el backend (modelos, APIs) como en el frontend (vista "Mis Plantillas"), ya que la mayoría de las nuevas funcionalidades dependen de él.
Este plan de implementación actualizado y detallado sirve como una hoja de ruta precisa para ejecutar esta visión.