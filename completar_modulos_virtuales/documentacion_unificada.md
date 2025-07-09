# Documentación Unificada para Módulos Virtuales Progresivos

## 1. Resumen del Sistema Actual y Problemas Detectados

### Estructura Curricular y Modelos
- **Jerarquía**: El sistema se organiza en `Planes de Estudio` → `Módulos` → `Temas` → `Contenidos`.
- **Unificación de Contenidos**: Se ha avanzado en la unificación de `Juegos`, `Simulaciones` y `Quizzes` bajo un modelo `TopicContent` con un campo `content_type`. En la capa virtual, `VirtualTopicContent` adapta estos contenidos para cada alumno.
- **Evaluaciones y Resultados Separados**: Aunque las evaluaciones se planifican en el modelo `Evaluation`, los resultados de interacciones (quizzes, juegos) se almacenan en colecciones separadas (`QuizResult`, `GameResult`), mientras que un modelo `ContentResult` más genérico también existe, creando duplicidad.
- **Recursos**: Los recursos (archivos, enlaces) se asocian a los temas mediante `TopicResource`, una colección separada de `TopicContent`.

### Generación Progresiva
- **A Nivel de Módulo (Implementada)**:
    - Un flag `ready_for_virtualization` en cada `Módulo` controla su disponibilidad.
    - La API `POST /virtual/progressive-generation` encola hasta 3 módulos habilitados: genera el primero de inmediato y deja los dos siguientes en cola, implementando la lógica "dos por delante".
    - La API `POST /virtual/trigger-next-generation` se activa cuando el alumno supera el 80% de progreso en un módulo, encolando el siguiente disponible.
- **A Nivel de Tema (No implementada)**:
    - La función `_generate_virtual_topics_fast` crea **todos** los temas de un módulo a la vez.
    - No existe un flag de "tema habilitado" ni un endpoint `trigger-next-topic` para una progresión interna similar a la de los módulos. Esto causa que se generen temas vacíos si el profesor no ha completado todo el contenido del módulo.

### Sincronización de Contenido y Cola de Tareas
- **Falta de Sincronización Automática**: Existe una cola de tareas (`VirtualGenerationTask`) que maneja tareas de tipo `generate` y `update`. Sin embargo, la lógica para las tareas `update` está vacía. Como resultado, los cambios que un profesor realiza en el contenido de un módulo (ej. corregir un texto, añadir un recurso) **no se propagan automáticamente** a los módulos virtuales ya generados para los estudiantes.

### Problemas en la Interfaz de Usuario (UI)
- **Toggle de Habilitación Duplicado**: El control para marcar un módulo como `ready_for_virtualization` aparece en dos lugares distintos de la interfaz del profesor (Panel de Planes y Generación de Contenido), causando confusión y posibles desincronizaciones de estado.
- **Experiencia del Alumno Fragmentada**: El contenido de un tema (teoría, videos, juegos, quizzes) se presenta al alumno de forma separada, sin un flujo secuencial integrado. El alumno tampoco recibe notificaciones en tiempo real sobre la disponibilidad de nuevo contenido, necesitando recargar la página para ver actualizaciones.

---

## 2. Nueva Propuesta Unificada: Cambios Principales

Para abordar las deficiencias, se propone una estrategia integral basada en la "Regla de Resultados Unificados": **toda interacción del alumno genera un `ContentResult` único**.

- **Contenidos estáticos (lectura, video)**: Al ser visualizados, generan un `ContentResult` con `score = 100%` y `auto_passed = true`.
- **Contenidos interactivos (quiz, juego)**: Generan un `ContentResult` con la puntuación real obtenida.
- **Evaluaciones formales (entregables)**: Se manejan como un `TopicContent` de tipo "assignment", y su calificación manual se registra en un `ContentResult` con campos como `manual_score` y `graded_by`.

Esta regla es el pilar para las siguientes mejoras:

### A. Publicación Granular de Temas
- **Problema**: No se puede liberar un módulo parcialmente.
- **Solución**:
    1.  Añadir un campo booleano `published` al modelo `Topic`.
    2.  Modificar la lógica de generación (`_generate_virtual_topics_fast`) para que solo incluya temas con `published = true`.
    3.  El profesor podrá marcar un módulo como `ready_for_virtualization` aunque no todos los temas estén publicados. El sistema solo generará los que sí lo estén.

### B. Generación Progresiva Dentro de Módulos (Temas “dos por delante”)
- **Problema**: Todos los temas de un módulo se generan a la vez, abrumando al alumno.
- **Solución**:
    1.  **Lote Inicial**: Al generar un módulo virtual, crear solo un lote inicial de N temas (ej. N=2).
    2.  **Nuevo Endpoint**: Crear `POST /virtual/trigger-next-topic`. El frontend lo llamará cuando el alumno complete un tema (>80% de progreso) para generar el siguiente tema publicado.
    3.  **Estado de Bloqueo**: Utilizar un campo (`locked` o `status`) en `VirtualTopic` para indicar qué temas aún no son accesibles, permitiendo a la UI mostrarlos como "bloqueados" o "próximamente".

### C. Unificación de Quizzes y Evaluaciones como Contenidos
- **Problema**: Modelos y colecciones duplicadas para quizzes (`Quiz`, `QuizResult`) y evaluaciones (`Evaluation`).
- **Solución**:
    1.  **Quizzes como `TopicContent`**: Eliminar el modelo `Quiz`. Un quiz se representará como un `TopicContent` con `content_type = "quiz"`. Las preguntas y respuestas se almacenarán en `content_data`.
    2.  **Evaluaciones como `TopicContent`**: Las evaluaciones formales (proyectos, tareas) se representarán como `TopicContent` de tipo "assignment". Los metadatos (peso, fecha de entrega) pueden almacenarse en el propio `TopicContent` o mantener el modelo `Evaluation` solo para planificación.
    3.  **Alcance Flexible**: Un `TopicContent` evaluativo podrá asociarse a uno o varios temas, o a un módulo completo, apareciendo al final del último tema correspondiente en la secuencia del alumno.

### D. Unificación de Resultados y Progreso (Solo `ContentResult`)
- **Problema**: Múltiples colecciones de resultados (`QuizResult`, `GameResult`, `ContentResult`).
- **Solución**:
    1.  **Eliminar Colecciones Específicas**: Depreciar y migrar `QuizResult`, `GameResult`, etc., a `ContentResult`.
    2.  **Unificar Endpoints**: Crear un endpoint genérico `/api/content/{virtual_content_id}/submit-result` para registrar todas las interacciones.
    3.  **Cálculo de Progreso Centralizado**: Con todos los resultados en una sola colección, el progreso del alumno en un tema o módulo se calcula de forma sencilla y consistente.

### E. Sincronización Automática de Cambios de Contenido
- **Problema**: Los cambios del profesor no se reflejan en los módulos virtuales ya generados.
- **Solución**:
    1.  **Detectar Cambios**: Al editar un `Topic` o `TopicContent`, un `ContentChangeDetector` debe identificar las modificaciones.
    2.  **Encolar Tareas `update`**: Por cada `VirtualModule` afectado, encolar una tarea de tipo `update` en `VirtualGenerationTask`.
    3.  **Procesar Tareas `update`**: Implementar la lógica en la cola para que, ante un cambio:
        - **Contenido modificado**: Se actualice el `VirtualTopicContent` correspondiente (refrescando la referencia o regenerando la adaptación).
        - **Nuevo contenido añadido**: Se inserte el nuevo `VirtualTopicContent` en los `VirtualTopic` de los alumnos.
    4.  **Notificaciones en Tiempo Real**: Usar WebSockets o polling para notificar al alumno en la UI sobre el contenido actualizado ("El profesor ha añadido un nuevo recurso al Tema 2").

### F. Depuración y Simplificación de Modelos de Datos
- **Problema**: Redundancia y complejidad en los modelos.
- **Solución**:
    1.  **Fusionar `VirtualTopicContent` en `VirtualTopic`**: Almacenar los contenidos virtuales como un array de subdocumentos dentro del `VirtualTopic`. Esto elimina una colección y simplifica las consultas.
    2.  **Eliminar `TopicResource`**: Integrar todos los recursos (PDFs, enlaces) como `TopicContent` con el tipo adecuado (ej. "file", "link").
    3.  **Eliminar Campos Redundantes**: Suprimir campos duplicados como `name` y `description` en los modelos virtuales si pueden ser referenciados desde el original.

### G. Presentación Unificada e Interactiva en la UI
- **Problema**: Experiencia de aprendizaje fragmentada.
- **Solución**:
    1.  **Componente `InteractiveSlideView`**: Crear un visor tipo carrusel o "diapositivas" que presente cada `VirtualTopicContent` de forma secuencial y a pantalla completa.
    2.  **Renderizado por Tipo**: El componente renderizará cada slide según su `content_type` (texto, video, juego en un `<iframe>`, quiz interactivo, etc.).
    3.  **Bloqueo Secuencial (Gating)**: El botón "Siguiente" se mantendrá deshabilitado hasta que el alumno complete la interacción con la slide actual (ej. terminar de leer, ver un video, enviar un quiz).
    4.  **Teoría como Contenido**: Migrar el campo `theory_content` del modelo `Topic` para que sea el primer `TopicContent` de tipo "text" en la secuencia, unificando todo el flujo.

---

## 3. Implementación y Viabilidad de la Solución Propuesta

Las estrategias propuestas son complementarias y configuran un rediseño coherente.

- **Viabilidad Técnica**: La solución es factible. La unificación de modelos simplifica la arquitectura, la lógica de progresión reutiliza patrones existentes y la nueva UI se puede construir con tecnologías frontend modernas. Las migraciones de datos deben planificarse cuidadosamente.
- **Rendimiento**: La fusión de colecciones (`VirtualTopicContent` en `VirtualTopic`) reduce el número de consultas a la base de datos, lo que puede mejorar el rendimiento. La carga de trabajo de la sincronización se distribuye en tareas asíncronas en la cola.
- **Plan de Acción por Fases**:
    - **Fase 1 (Backend - 1-2 semanas)**: Actualización de modelos de datos, migración de `Quiz` a `TopicContent` y unificación de resultados en `ContentResult`.
    - **Fase 2 (Backend - 2 semanas)**: Implementación de la generación progresiva de temas (`trigger-next-topic`) y la lógica de sincronización de cambios (tareas `update`).
    - **Fase 3 (Frontend - 2-3 semanas)**: Desarrollo del componente `InteractiveSlideView`, la navegación secuencial y la recepción de notificaciones en tiempo real.
    - **Fase 4 (Frontend - 1 semana)**: Implementación de validaciones de avance (umbrales de progreso) y feedback al usuario.
    - **Fase 5 (Full Stack - 1-2 semanas)**: Pruebas integrales de extremo a extremo, testing de regresión y despliegue coordinado.

---

## 4. Tareas Deducidas

### 🛠️ Tareas para Backend

1.  **Publicación granular de Temas**:
    - Añadir booleano `published` al modelo `Topic`.
    - Modificar `_generate_virtual_topics_fast` para filtrar solo `Topic` con `published = true`.
    - Ajustar `get_virtualization_readiness` para reportar temas pendientes de publicar.

2.  **Generación progresiva interna de Temas**:
    - Dividir la generación de temas en un lote inicial (N=2).
    - Crear endpoint `POST /virtual/trigger-next-topic` que genere el siguiente tema al alcanzar >80% de progreso en el actual.
    - Añadir campo `locked` o usar `completion_status` en `VirtualTopic` para bloquear temas no generados.

3.  **Unificación de Quizzes y Evaluaciones**:
    - Transformar el modelo `Quiz` en un `TopicContent` con `content_type = "quiz"`.
    - Migrar preguntas a `content_data`.
    - Representar evaluaciones formales (`Evaluation`) como `TopicContent` de tipo "assignment".
    - Eliminar colecciones y rutas de `quizzes` y `quiz_results`.

4.  **Unificación de Resultados en `ContentResult`**:
    - Depreciar y migrar datos de `QuizResult`, `GameResult`, etc., a `ContentResult`.
    - Ajustar endpoints de envío de resultados para que todos creen registros en `ContentResult`.
    - Implementar lógica para que contenidos estáticos generen `ContentResult` con `score = 100`, `auto_passed = true` al ser vistos.

5.  **Sincronización automática de Cambios**:
    - Implementar la lógica de la rama `task_type == "update"` en `process_generation_queue`.
    - Al editar `Topic` o `TopicContent`, encolar tareas `update` para cada `VirtualModule` afectado.
    - La tarea `update` debe actualizar `VirtualTopicContent` existentes o añadir los nuevos.

6.  **Depuración y Migraciones de Modelo**:
    - Fusionar `VirtualTopicContent` como un array de subdocumentos dentro de `VirtualTopic`.
    - Eliminar la colección `TopicResource`, migrando sus datos a `TopicContent`.
    - Suprimir campos redundantes (`name`, `description`) de `VirtualModule`/`VirtualTopic`.
    - Revisar y optimizar índices en colecciones virtuales.

### 🎨 Tareas para Frontend

1.  **Simplificar Toggle de habilitación de Módulos**:
    - Eliminar el control de habilitación del Panel de Planes; dejar solo un indicador de solo lectura.
    - Mantener el único control en la vista de Generación de Contenido, con feedback de completitud.

2.  **Desarrollar componente `InteractiveSlideView`**:
    - Crear componente que recorra los `VirtualTopicContent` ordenados.
    - Renderizar cada slide según `content_type` (texto, video, juego, quiz).
    - Añadir un mapa de navegación lateral o barra de progreso de las slides.

3.  **Implementar desbloqueo progresivo y notificaciones**:
    - Consumir el campo `locked` para mostrar candados en temas/slides no accesibles.
    - Integrar WebSockets o polling para notificar al alumno sobre:
        - Nuevos temas/módulos habilitados por el profesor.
        - Estado de la cola de generación ("Módulo 4 en proceso...").
        - Contenido actualizado por el profesor.

4.  **Validaciones y Feedback de Avance**:
    - Deshabilitar llamadas a `trigger-next-topic` en la UI hasta que se alcance el umbral de progreso.
    - Mostrar mensajes contextuales: "Completa el 80% del Tema 2 para desbloquear el Tema 3".
    - Añadir tooltips explicando el flujo progresivo.

---

## 5. 🚀 Guía de Integración para Frontend

A continuación se detalla cómo el frontend debe interactuar con el API para implementar el nuevo flujo.

#### **1. Flujo del Profesor (Gestión de Contenido)**

**Paso 1: Mostrar el Estado de Publicación de un Módulo**
*   **Endpoint**: `GET /api/study_plan/module/<module_id>/topics/publication-status`
*   **Uso**: Al entrar a la vista de un módulo, llamar para saber qué temas están publicados.

**Paso 2: Permitir la Publicación de Temas**
*   **Publicar un solo tema**: `PUT /api/study_plan/topic/<topic_id>/publish` (Payload: `{"published": true}`)
*   **Publicar varios temas**: `PUT /api/study_plan/module/<module_id>/topics/publish-batch` (Payload: `{"topic_ids": ["..."], "published": true}`)
*   **Auto-publicar temas con contenido**: `POST /api/study_plan/module/<module_id>/topics/auto-publish`

**Paso 3: Habilitar el Módulo para los Estudiantes (Interruptor Maestro)**
*   **Endpoint**: `PUT /api/study_plan/module/<module_id>/virtualization-settings`
*   **Payload**: `{"ready_for_virtualization": true}`

---

#### **2. Flujo del Estudiante (Aprendizaje Progresivo)**

**Paso 1: Iniciar el Curso por Primera Vez**
*   **Endpoint**: `POST /api/virtual/progressive-generation`
*   **Payload**: `{"student_id": "...", "plan_id": "..."}`
*   **Respuesta**: Devuelve el primer módulo generado y encola los dos siguientes.

**Paso 2: Desbloquear el Siguiente Módulo**
*   **Endpoint**: `POST /api/virtual/trigger-next-generation`
*   **Payload**: `{"current_module_id": "...", "student_id": "...", "progress": 85}`
*   **Uso**: Llamar cuando el progreso del estudiante en un módulo supera el 80%.

**Paso 3: Desbloquear el Siguiente Tema (¡El Disparador del Progreso Interno!)**
*   **Endpoint**: `POST /api/virtual/trigger-next-topic`
*   **Payload**: `{"current_topic_id": "...", "student_id": "...", "progress": 85}`
*   **Uso**: Llamar cuando el progreso del estudiante en un tema supera el 80%.
*   **Acción del Frontend**: Actualizar la UI para mostrar los nuevos temas desbloqueados.

---

#### **3. Sincronización Automática (Contexto para Frontend)**

El backend maneja la detección y aplicación de cambios de contenido de forma automática a través de la cola de tareas. El frontend no necesita llamar a endpoints específicos para esto. Sin embargo, para una experiencia en tiempo real, se recomienda implementar **WebSockets o polling periódico** para notificar al usuario sobre contenido nuevo o actualizado sin necesidad de recargar la página. 