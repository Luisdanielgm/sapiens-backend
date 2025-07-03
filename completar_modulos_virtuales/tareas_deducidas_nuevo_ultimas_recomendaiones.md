🛠️ Tareas para Backend
1. Publicación granular de Temas
Contexto: Hoy solo existe un flag global (ready_for_virtualization) por módulo. Si un profesor marca listo un módulo con 5 temas pero solo completó 3, la generación crea los 5 temas virtuales (los 2 restantes quedan vacíos o con placeholders).
Detalle de la tarea:

Añadir un booleano enabled (o published) al modelo Topic.

Modificar _generate_virtual_topics_fast para filtrar solo Topic con enabled = true.

Extender el endpoint get_virtualization_readiness para reportar cuántos temas habilitados faltan publicar.

Ajustar la lógica que permite marcar ready_for_virtualization = true aunque falten temas, siempre y cuando al menos 1 tema esté publicado.

2. Generación progresiva interna de Temas
Contexto: La lógica actual genera todos los temas de un módulo de una vez, sin respetar la regla “dos temas por delante” que existe para los módulos. Queremos un flujo similar dentro de cada módulo.
Detalle de la tarea:

Dividir la generación de temas en lote inicial de N (por ejemplo, 2) dentro de _generate_virtual_topics_fast.

Crear un nuevo endpoint POST /virtual/trigger-next-topic que, al completarse un tema (> 80 % progreso), encole o genere el siguiente Topic habilitado.

Añadir un campo locked (o reutilizar completion_status) en VirtualTopic para bloquear automáticamente los temas aún no generados.

3. Unificación de Quizzes y Evaluaciones como Contenidos
Contexto: Actualmente los quizzes virtuales (Quiz) y las evaluaciones formales (Evaluation) viven en colecciones distintas con modelos paralelos. Esto duplica esfuerzo y complica la consistencia.
Detalle de la tarea:

Transformar el modelo Quiz en un TopicContent con content_type = "quiz". Migrar preguntas y lógica de presentación a content_data.

Representar las evaluaciones formales como TopicContent de tipo "assignment" (instrucciones + metadatos de peso/fecha).

Eliminar las colecciones y rutas específicas de quizzes y quiz_results, redirigiendo todo a las APIs de topic_contents y content-results.

Actualizar los controladores para gestionar creación, edición y lectura de quizzes/assignments vía el mismo flujo que otros contenidos.

4. Unificación de Resultados en un solo modelo (ContentResult)
Contexto: Hay QuizResult, GameResult, EvaluationResult y ContentResult actuando por separado. Necesitamos un único esquema para registrar TODO tipo de interacción.
Detalle de la tarea:

Depreciar y migrar datos de QuizResult, GameResult, etc., a ContentResult, añadiendo campos opcionales (quiz_score, game_score, manual_score, graded_by).

Ajustar los endpoints de resultado (/api/quiz/…/submit, /api/game/…/submit) para que creen registros en ContentResult.

Implementar lógica genérica en /api/virtual/content-result para:

Contenidos estáticos → al primer “visto”, crear ContentResult con score = 100, auto_passed = true.

Contenidos interactivos → registrar score real.

Assignments manuales → guardar calificación en manual_score, graded_by.

5. Sincronización automática de Cambios de Contenido
Contexto: La cola de tareas maneja generate correctamente, pero el branch update está vacío: los cambios posteriores del profesor no se propagan a los módulos virtuales.
Detalle de la tarea:

En el detector de cambios (ContentChangeDetector), al editar un Topic o TopicContent, encolar tareas update por cada VirtualModule afectado (o por cada alumno).

Implementar en process_generation_queue la rama task_type == "update":

Para contenidos modificados, actualizar los VirtualTopicContent que referencian al content_id cambiado (sobrescribir adapted_content o invalidar copia).

Para nuevos contenidos insertados, crear los VirtualTopicContent faltantes en los módulos ya generados.

Para temas recientemente publicados, invocar internamente la lógica de “trigger-next-topic” para generarlos.

Registrar en VirtualModule.updates un historial de acciones aplicadas (p. ej. fechas y tipo de cambio).

6. Depuración y Migraciones de Modelo
Contexto: Existen colecciones y campos duplicados que dificultan el mantenimiento (p. ej. TopicResource, campos redundantes en VirtualModule, VirtualTopic).
Detalle de la tarea:

Evaluar fusionar VirtualTopicContent como array de subdocumentos dentro de cada VirtualTopic (evita consultas cruzadas).

Eliminar la colección TopicResource migrando sus datos a TopicContent.

Suprimir campos redundantes (name, description) de VirtualModule/VirtualTopic cuando ya se gestionen en contenidos.

Revisar y optimizar índices en colecciones virtuales (student_id, module_id, status) para asegurar consultas ágiles.

🎨 Tareas para Frontend
1. Simplificar Toggle de habilitación de Módulos
Contexto: Hoy el profesor ve dos toggles distintos para el mismo flag ready_for_virtualization (en Panel de Planes y en Generación de Contenido), generando confusión y desincronizaciones.
Detalle de la tarea:

Eliminar el control de habilitación en el Panel de Planes; dejar solo un indicador read-only que muestre el estado actual.

Mantener el checkbox en Generación de Contenido (con feedback de readiness: % completitud, temas faltantes).

Asegurar que al togglear en esta vista se refresque inmediatamente en todo el frontend (sin necesidad de recarga manual).

2. Desarrollar componente “InteractiveSlideView”
Contexto: La experiencia del alumno hoy fragmenta teoría, videos, juegos y quizzes como secciones independientes. Queremos un recorrido secuencial tipo diapositivas.
Detalle de la tarea:

Crear InteractiveSlideView que recorra los VirtualTopicContent ordenados por un campo order.

Renderizar cada slide según content_type:

Texto enriquecido → componente <RichText/>

Video → <iframe> o reproductor embebido

Juego/Simulación → <iframe> o contenedor interactivo

Quiz/Assignment → formulario o área de entrega

Añadir un mini-mapa lateral o barra de progreso de slides, indicando cuáles están completadas, bloqueadas o pendientes.

3. Implementar desbloqueo progresivo y notificaciones
Contexto: El alumno no sabe cuándo nuevos módulos o temas pasan a estar disponibles, ni qué slides aún no puede ver.
Detalle de la tarea:

Consumir el campo locked en VirtualTopic/VirtualTopicContent para mostrar candados en temas/slides no accesibles.

Integrar WebSockets (o polling ligero) con el backend para:

Notificar al alumno cuando el profesor habilite un nuevo tema o módulo.

Informar el estado de la cola de generación (“Módulo 4 en proceso”).

Refrescar dinámicamente la interfaz para desbloquear slides o temas en cuanto estén listos.

4. Validaciones y Feedback de Avance
Contexto: Es fundamental guiar al alumno para que no invoque trigger-next-topic o trigger-next-generation antes de tiempo, y mostrarle claramente su progreso.
Detalle de la tarea:

En la UI, deshabilitar llamadas a trigger-next-topic hasta que el alumno alcance el umbral configurado (p. ej. > 80 % completitud del tema).

Mostrar mensajes contextuales:

“Has completado el 65 % del Tema 2; alcanza el 80 % para liberar el Tema 3.”

“Debes ver toda la diapositiva actual antes de continuar.”

Añadir tooltips o modales breves explicando el flujo progresivo y el significado de cada indicador de estado.