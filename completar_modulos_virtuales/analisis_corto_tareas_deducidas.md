Análisis Completo de la Investigación y Nuevas Recomendaciones
1. Estado Actual y Hallazgos Clave
Estructura Curricular y Modelos
Plan de Estudio → Módulos → Temas → Contenidos
Un Plan agrupa Módulos; cada Módulo incluye varios Temas, y cada Tema múltiples instancias de TopicContent (texto, video, simulación, quiz).

Unificación parcial de contenidos
Juegos, simulaciones y quizzes dejaron de ser colecciones separadas y se almacenan en topic_contents con un campo content_type. En la capa virtual, VirtualTopicContent replica o adapta esos contenidos para cada alumno.

Evaluaciones y resultados
Aunque las evaluaciones del plan se modelan en Evaluation, los resultados interactivos de quizzes y juegos viven en colecciones independientes (QuizResult, GameResult), mientras que el histórico de interacciones con contenidos está en ContentResult.

Generación Progresiva
Módulos

Un flag ready_for_virtualization en el módulo indica si el profesor lo ha habilitado.

POST /virtual/progressive-generation encola hasta 3 módulos (genera el primero “al vuelo” y deja 2 en cola).

POST /virtual/trigger-next-generation se dispara al superar el 80 % de avance en el módulo actual, encolando el siguiente módulo, manteniendo siempre “dos módulos por delante”.

Temas

_generate_virtual_topics_fast crea todos los temas del módulo de una vez (sin respetar la idea de generar solo los primeros 2 y luego “dos por delante”).

No existe un flag de “tema habilitado” ni un endpoint equivalente a trigger-next-topic para progresión interna.

Sincronización y Cola de Tareas
Actualizaciones de contenido

La infraestructura de cola maneja tareas generate (generación de módulos) y update (actualización de módulos existentes), pero el branch update está vacío: los cambios del profesor no llegan automáticamente a los módulos generados.

Toggle de habilitación redundante

El checkbox de ready_for_virtualization existe en dos vistas diferentes (Panel de Planes y Generación de Contenido), lo que genera confusión y posibles desincronizaciones en UI.

Experiencia del alumno

La vista actual presenta por separado teoría, videos, juegos y quizzes.

El alumno no sabe si los siguientes módulos o temas están en cola o recién habilitados a menos que recargue manualmente.

2. Nueva Regla de Resultados Unificados
El usuario ha indicado que todos los contenidos (incluso diapositivas, lecturas o videos) deben generar un único tipo de resultado (ContentResult), con reglas:

Contenidos estáticos (diapositivas/lectura/video): ver una vez → score = 100 %, auto_passed = true.

Contenidos interactivos (quizzes, juegos): score real del quiz o puntaje del juego.

Evaluaciones formales del plan (entregables/manuales): asociadas a un recurso de tipo "assignment" y calificadas manualmente → manual_score + graded_by.

Este nuevo esquema refuerza la unificación: un solo modelo de resultado para todos los tipos de interacción.

3. Concordancia de Recomendaciones y Tareas
Las recomendaciones previamente identificadas (publicación granular, progresión interna de temas, unificación de quizzes como contenido, sincronización de cambios, depuración de modelos, mejoras de UI) encajan de manera natural con la nueva regla de resultados unificados. De hecho, muchos puntos se ven reforzados:

Unificación de esquemas: ya se sugería eliminar modelos especializados de quizzes y resultados; ahora se extiende a todo tipo de contenido.

Simplificación de lógica: con un único flujo de registro de resultados, podemos centralizar validaciones y cálculos de progreso.

Mejor experiencia: el alumno ve un único feed de contenidos y su puntuación, sin saltos de modelo ni colecciones.

Tareas con Contexto Extendido
A. Backend
Publicación Granular de Temas
Contexto: Hoy sólo existe un flag global por módulo. Si un profesor marca listo un módulo con 5 temas y sólo completó 3, el sistema genera los 5 temas virtuales, dejando 2 vacíos o con placeholders.
Tarea:

Añadir booleano enabled en el modelo Topic.

Modificar _generate_virtual_topics_fast para filtrar solo temas con enabled = true.

Ajustar el endpoint get_virtualization_readiness para reportar cuántos temas están pendientes de habilitar.

Progresión Interna de Temas en Módulos Virtuales
Contexto: La lógica actual genera todos los temas de un módulo de una vez, sin respetar la regla “dos temas por delante” que existe entre módulos.
Tarea:

Dividir la generación de temas en dos fases:

Lote inicial de N temas (p. ej. 2).

Nuevo endpoint POST /virtual/trigger-next-topic que, al completarse un tema (p.ej. 80 % de avance), encole/generar el siguiente tema habilitado.

Añadir campos locked (o reutilizar completion_status) en VirtualTopic para bloquear temas no liberados.

Unificación de Quizzes y Evaluaciones como Contenido
Contexto: Actualmente los quizzes virtuales (Quiz, QuizResult) y las evaluaciones formales (Evaluation) utilizan esquemas paralelos y colecciones distintas.
Tarea:

Transformar el modelo Quiz en un TopicContent de tipo "quiz" en topic_contents.

Migrar datos de QuizResult, GameResult y otros resultados específicos a ContentResult, añadiendo campos opcionales quiz_score, game_score.

Eliminar modelos, rutas y colecciones de quizzes independientes en el backend y en la capa virtual.

Unificación de Resultados: Sólo ContentResult
Contexto: Se desea que cada contenido (estático o interactivo) genere un único resultado.
Tarea:

Quitar las colecciones QuizResult, GameResult, etc.

Ajustar la lógica de creación de resultados:

Para contenidos estáticos (slides, lecturas, videos): al primer “visto” desde frontend, crear un ContentResult con score = 100, auto_passed = true.

Para quizzes/juegos: al completar, registrar el puntaje en score.

Para evaluaciones formales del plan: vincularlas a un TopicContent de tipo "assignment", y al calificar, guardar manual_score y graded_by.

Refactorizar servicios y controladores (/api/virtual/content-result) para manejar todos los casos.

Sincronización Automática de Cambios
Contexto: Los alumnos no ven actualizaciones de contenido tras ediciones del profesor. La cola de tareas update está vacía.
Tarea:

Completar el branch task_type == "update" en process-queue:

Detectar VirtualTopicContent relacionados con un TopicContent modificado.

Re-generar o actualizar automáticamente esos contenidos en cada VirtualModule activo.

En el detector de cambios (ContentChangeDetector), encolar tareas de actualización tras guardar cambios en temas o recursos.

Depuración y Migraciones de Modelo
Contexto: Hay colecciones separadas y campos duplicados que dificultan el mantenimiento.
Tarea:

Evaluar fusionar VirtualTopicContent como subdocumentos dentro de cada VirtualTopic, simplificando la lectura de un tema completo en una sola consulta.

Eliminar campos redundantes (nombre, descripción) cuando no sean estrictamente necesarios.

Revisar y optimizar índices para acelerar búsquedas de módulos virtuales y contenidos.

B. Frontend
Toggle de Habilitación en Generación de Contenido
Contexto: Hoy el profesor ve dos toggles en el Panel de Planes y en Generación de Contenido, lo que genera confusión. El panel de Planes no edita contenido.
Tarea:

Eliminar el control de ready_for_virtualization en el Panel de Planes.

Mantener el checkbox ready_for_virtualization solo en la vista de Generación de Contenido, junto con feedback de readiness (porcentaje, temas faltantes).

En el Panel de Planes, mostrar solo un indicador read-only del estado del módulo.

Componente “Diapositiva Interactiva”
Contexto: La experiencia actual dispersa teoría, videos, juegos y quizzes. Se quiere un recorrido secuencial e inmersivo.
Tarea:

Crear InteractiveSlideView que recorra VirtualTopicContent ordenados por un campo order.

Renderizar cada contenido (texto, video incrustado, simulación en <iframe>, quiz) como una lámina a pantalla completa.

Añadir un mini-mapa lateral de progreso de slides, bloqueando futuras hasta completar la actual.

Desbloqueo Progresivo y Notificaciones
Contexto: El alumno no sabe si los siguientes módulos o temas están listos o en cola.
Tarea:

Consumir un campo locked en VirtualTopic y VirtualTopicContent para bloquear visualmente temas y slides aún no liberados.

Implementar WebSockets o polling ligero para:

Notificar al alumno cuando el profesor habilite un nuevo tema o módulo.

Mostrar el estado de la cola de generación (“Módulo 4 en proceso”).

Feedback de Avance y Validaciones
Contexto: Se debe guiar al alumno para que no llame prematuramente a los endpoints de generación.
Tarea:

Validar en UI que no se invoque trigger-next-topic o trigger-next-generation antes de superar el umbral (e.g. 80 %).

Mostrar mensajes claros: “Has completado 65 % del Tema 2; completa el 80 % para liberar el Tema 3.”

4. Plan de Acción
Fase	Objetivo	Duración	Responsable
1	Modelado, migraciones de datos y resultados	1–2 semanas	Backend
- Añadir Topic.enabled		
- Unificación de resultados en ContentResult		
- Migrar Quiz → TopicContent		
2	Generación progresiva interna	2 semanas	Backend
- Lote inicial de Temas + trigger-next-topic		
- Cola de actualizaciones completas		
3	UX interactivo y desbloqueos	2–3 semanas	Frontend
- InteractiveSlideView		
- Notificaciones en tiempo real		
4	Validaciones y feedback de avance	1 semana	Frontend
- Umbrales y mensajes claros		
5	Pruebas integrales & despliegue	1–2 semanas	Full Stack
- QA de flujos y sincronización