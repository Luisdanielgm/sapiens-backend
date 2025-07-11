# Documentación Unificada para Módulos Virtuales Progresivos (Actualizada)

## 1. Resumen del Sistema y Arquitectura

### Estructura Curricular y Modelos
- **Jerarquía**: El sistema se organiza en `Planes de Estudio` → `Módulos` → `Temas` → `Contenidos`.
- **Contenido Unificado**: Todos los tipos de contenido (`Juegos`, `Simulaciones`, `Quizzes`, `Diapositivas`, etc.) se almacenan en el modelo `TopicContent`.
- **Modelos Virtuales**: Para cada estudiante, se generan `VirtualModule`, `VirtualTopic` y `VirtualTopicContent`, que son instancias personalizadas del contenido original.

### Generación Progresiva
- **A Nivel de Módulo (Implementada)**: El sistema utiliza una estrategia "dos por delante", generando el primer módulo disponible y encolando los dos siguientes. Se activa con `POST /virtual/trigger-next-generation`.
- **A Nivel de Tema (Implementada)**: Dentro de un módulo, se aplica una estrategia "dos por delante" para los temas. El frontend llama a `POST /virtual/trigger-next-topic` para desbloquear el siguiente lote de temas cuando el estudiante alcanza un 80% de progreso.

### Sincronización de Contenido
- **Sincronización Automática (Implementada)**: Existe una cola de tareas (`VirtualGenerationTask`) que procesa tareas de tipo `generate` y `update`. Cuando un profesor modifica un `Topic` o `TopicContent`, se encolan tareas `update` que se aplican automáticamente a los módulos virtuales de los estudiantes.

---

## 2. Nueva Propuesta Unificada: Responsabilidades y Flujo

### 2.1. División de Responsabilidades (Backend vs. Frontend)

Esta es la nueva arquitectura de responsabilidades para el procesamiento de contenido:

| Área | Qué Procesa | Dónde Ocurre |
| :--- | :--- | :--- |
| **Back-end** | • Exponer datos crudos y campos auxiliares<br>• Almacenar `slide_template` y `personalization_markers`<br>• Controlar el estado de bloqueo (`locked`) de los temas<br>• Gestionar la progresión y la cola de tareas | • Servicios y modelos Python/MongoDB |
| **Front-end**| • **Lógica de IA para personalizar marcadores**<br>• **Separación y renderizado de plantillas de slide vs. láminas**<br>• Reemplazo dinámico de marcadores en el HTML/JS/CSS<br>• Intercalado de slides y contenidos según orden | • En los componentes React/JS que consumen la API |

### 2.2. Flujo de Presentación de Contenido

1.  **Backend Prepara Datos**: El backend expone la lista de `VirtualTopicContent` ordenados. Para cada contenido, provee:
    *   El contenido original (`original_content`).
    *   Los marcadores de personalización (`original_personalization_markers`).
    *   La plantilla de la diapositiva, si aplica (`original_slide_template`).
2.  **Frontend Orquesta la Experiencia**:
    *   **Recibe los datos** del backend.
    *   **Llama a la IA**: Utiliza el `original_personalization_markers` para generar los valores personalizados.
    *   **Reconstruye el Contenido**: Inyecta los valores de la IA en el contenido original.
    *   **Separa las Diapositivas**: Si el contenido es de tipo `slides`, el frontend lo divide en láminas individuales.
    *   **Aplica Plantilla**: Renderiza cada lámina individual sobre el fondo y estilos del `original_slide_template`.
    *   **Intercala y Presenta**: Muestra la secuencia final de contenidos (láminas, quizzes, diagramas) al estudiante.

---

## 3. Tareas Deducidas (Estado Actual)

### ✅ Tareas de Backend (Implementadas)

1.  **Publicación granular de Temas**:
    - ✅ Añadido booleano `published` al modelo `Topic`.
    - ✅ Modificado `_generate_virtual_topics_fast` para filtrar solo `Topic` con `published = true`.
    - ✅ Endpoints de publicación (`/publication-status`, `/publish-batch`, `/auto-publish`) funcionan.

2.  **Generación progresiva interna de Temas**:
    - ✅ Lógica de generación de temas en un lote inicial (N=2) implementada.
    - ✅ Endpoint `POST /virtual/trigger-next-topic` creado y funcionando.
    - ✅ Añadido campo `locked: bool` a `VirtualTopic` para controlar el acceso.

3.  **Sincronización automática de Cambios**:
    - ✅ Implementada la lógica de la rama `task_type == "update"` en `process_generation_queue`.
    - ✅ El sistema detecta cambios en `TopicContent` y encola tareas de actualización.

4.  **Soporte para Plantillas de Diapositivas**:
    - ✅ Agregado el campo `slide_template` al modelo `TopicContent`.
    - ✅ APIs de contenido exponen `slide_template` junto con `personalization_markers`.
    - ✅ Implementadas validaciones para asegurar que los `slides` incluyan una plantilla.

### 🎨 Tareas para Frontend (Pendientes)

1.  **Implementar Desbloqueo Progresivo y Notificaciones**:
    - Consumir el campo `locked` de `VirtualTopic` para mostrar candados en temas no accesibles.
    - Llamar a `POST /virtual/trigger-next-topic` cuando el progreso de un tema supere el 80%.
    - **Opcional**: Integrar WebSockets o polling para notificar al alumno sobre contenido nuevo o actualizado en tiempo real.

2.  **Desarrollar componente `InteractiveSlideView`**:
    - Crear componente que reciba la lista de `VirtualTopicContent` del backend.
    - **Llamar a la IA** para procesar `original_personalization_markers`.
    - **Separar el contenido** de `slides` en láminas individuales.
    - **Aplicar `original_slide_template`** como fondo/estilo a cada lámina.
    - **Intercalar** las láminas con otros tipos de contenido (`quiz`, `diagram`) en una única secuencia navegable.
    - Renderizar cada elemento de la secuencia según su `content_type`.

3.  **Validaciones y Feedback de Avance**:
    - Deshabilitar el botón "siguiente" en la UI hasta que se complete una slide/actividad.
    - Mostrar mensajes contextuales: "Completa el 80% del Tema 2 para desbloquear el Tema 3".

---

## 4. 🚀 Guía de Integración para Frontend (Actualizada)

A continuación se detalla cómo el frontend debe interactuar con el API para implementar el nuevo flujo.

### **1. Obtener Contenido de un Tema Virtual**

- **Endpoint**: `GET /api/virtual/topic/<virtual_topic_id>/contents`
- **Uso**: Es el endpoint principal para obtener la lista de contenidos ordenados de un tema.
- **Respuesta Clave**: El frontend recibirá un array de objetos. Cada objeto de tipo `virtual_content` contendrá:
    - `_id`: ID del contenido virtual.
    - `original_content`: El contenido HTML o JSON original.
    - `original_interactive_data`: Datos para contenidos interactivos.
    - `original_content_type`: El tipo de contenido (`slides`, `quiz`, `diagram`, etc.).
    - `locked`: Booleano que indica si el tema al que pertenece está bloqueado.
    - `original_personalization_markers`: Un objeto con los segmentos estáticos y marcadores `{{...}}` para ser procesados por la IA del frontend.
    - `original_slide_template`: Un objeto con la plantilla de fondo y estilos para aplicar a los contenidos de tipo `slides`.

**Ejemplo de Payload de Respuesta para un `VirtualTopicContent` de tipo `slides`:**
```json
{
  "_id": "63f7b2c...",
  "virtual_topic_id": "63f7b2a...",
  "content_id": "63f7b2d...",
  "student_id": "63f7b2e...",
  "source_type": "virtual_content",
  "original_content": "<div><h1>Título Slide 1</h1><p>Contenido con un {{marcador}}.</p></div><div><h2>Título Slide 2</h2><p>Otro contenido.</p></div>",
  "original_interactive_data": {},
  "original_content_type": "slides",
  "original_personalization_markers": {
    "segments": [
      { "type": "static", "content": "<div><h1>Título Slide 1</h1><p>Contenido con un " },
      { "type": "marker", "id": "marcador" },
      { "type": "static", "content": ".</p></div><div><h2>Título Slide 2</h2><p>Otro contenido.</p></div>" }
    ]
  },
  "original_slide_template": {
    "background": { "type": "color", "value": "#ffffff" },
    "styles": { "font_family": "Arial", "text_color": "#333333" }
  }
}
```

### **2. Desbloquear el Siguiente Tema**

- **Endpoint**: `POST /api/virtual/trigger-next-topic`
- **Uso**: Llamar cuando el progreso de un estudiante en un tema supera el 80%. Esto le indica al backend que genere el siguiente lote de temas y los marque como desbloqueados (`locked: false`).
- **Payload de Envío**:
  ```json
  {
      "current_topic_id": "ID_DEL_VIRTUAL_TOPIC_ACTUAL",
      "student_id": "ID_DEL_ESTUDIANTE",
      "progress": 85
  }
  ```
- **Acción del Frontend**: Tras una respuesta exitosa, volver a pedir los temas del módulo para refrescar la lista y mostrar los nuevos temas desbloqueados.

### **3. Marcar Contenido como Completado**

- **Endpoint**: `POST /api/virtual/contents/<virtual_content_id>/auto-complete`
- **Uso**: Cuando el estudiante visualiza un contenido estático (como una lámina de una diapositiva), el frontend debe llamar a este endpoint para marcarlo como completado. Esto actualiza el progreso general del tema.
- **Payload de Envío**:
  ```json
  {
      "student_id": "ID_DEL_ESTUDIANTE"
  }
  ```

### **4. Flujo de Trabajo Recomendado para el Frontend**

1.  **Cargar Módulo**: Obtener la lista de temas virtuales de un módulo. Usar el campo `locked` para mostrar cuáles están accesibles.
2.  **Cargar Tema**: Al seleccionar un tema desbloqueado, llamar a `GET /api/virtual/topic/<id>/contents`.
3.  **Procesar Contenido**:
    - Iterar sobre la lista de contenidos recibida.
    - Para cada uno, usar `original_personalization_markers` y llamar a la **IA del frontend** para obtener los valores personalizados.
    - Reconstruir el `original_content` con los valores de la IA.
    - Si `original_content_type` es `slides`, usar un parser de HTML para dividir el `original_content` en láminas individuales.
    - Crear una secuencia final para la UI, intercalando las láminas individuales con los demás contenidos (quizzes, diagramas, etc.).
4.  **Renderizar Secuencia**:
    - Usar un componente tipo carrusel (`InteractiveSlideView`).
    - Para cada lámina, aplicar los estilos y el fondo definidos en `original_slide_template`.
    - Para cada elemento, al ser completado, llamar a `/auto-complete`.
5.  **Monitorear Progreso**:
    - Calcular el progreso del tema basado en los contenidos completados.
    - Cuando el progreso supere el 80%, habilitar el botón para llamar a `/trigger-next-topic`.
    
Este flujo delega la lógica de presentación y personalización al frontend, mientras que el backend proporciona una API robusta con todos los datos necesarios. 