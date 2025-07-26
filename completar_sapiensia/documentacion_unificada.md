# Documentación Unificada para Módulos Virtuales Progresivos (Arquitectura Frontend-Driven)

## 1. Resumen del Sistema y Arquitectura

### Estructura Curricular y Modelos
- **Jerarquía**: El sistema se organiza en `Planes de Estudio` → `Módulos` → `Temas` → `Contenidos`.
- **Contenido Original**: El `TopicContent` almacena el contenido base creado por los profesores, incluyendo marcadores de personalización (`personalization_markers`) y plantillas de diapositivas (`slide_template`).
- **Contenido Virtual**: Para cada estudiante, se generan `VirtualModule`, `VirtualTopic` y `VirtualTopicContent`, que son instancias que referencian el contenido original.

### Orquestación y Personalización (Frontend-Driven)
- **Responsabilidad del Frontend**: Toda la lógica de procesamiento avanzado, personalización y secuenciación pedagógica reside en el frontend.
- **Motor de Orquestación**: Se utiliza un hook (`useTopicOrchestrator`) que, al recibir el contenido de un tema, realiza las siguientes acciones:
    1.  **Fragmentación**: Divide el contenido de tipo `slides` (recibido como un único bloque HTML) en láminas individuales usando un parser de DOM.
    2.  **Secuenciación con IA**: Envía un resumen de todos los contenidos fragmentados a un servicio de IA para que determine el orden pedagógico más efectivo.
    3.  **Personalización con IA**: Un segundo hook (`useContentPersonalization`) toma cada contenido individual y, usando los `personalization_markers`, llama a otro servicio de IA para reemplazar los marcadores con valores adaptados al perfil del estudiante.
- **Carga Progresiva**: Para optimizar la experiencia de usuario, el contenido se muestra inmediatamente en un orden por defecto, y la secuencia ordenada por la IA se aplica en segundo plano, reordenando la vista de forma fluida y sin bloqueos.

---

## 2. Nueva Arquitectura de Responsabilidades (Implementada)

| Área | Qué Procesa | Dónde Ocurre |
| :--- | :--- | :--- |
| **Back-end** | • Servir como un almacén de datos crudos.<br>• Exponer `original_content`, `personalization_markers` y `slide_template`.<br>• Gestionar el estado de bloqueo (`locked`) de los temas y la progresión entre módulos. | • Servicios y modelos Python/MongoDB |
| **Front-end**| • **Fragmentación** de contenido (e.g., dividir HTML de slides).<br>• **Lógica de IA para secuenciación pedagógica** (ordenar láminas y contenidos).<br>• **Lógica de IA para personalizar marcadores** con base en el perfil del estudiante.<br>• **Renderizado de plantillas de slide** (`slide_template`).<br>• Reemplazo dinámico de marcadores e inyección de contenido personalizado. | • Hooks de React (`useTopicOrchestrator`, `useContentPersonalization`).<br>• Servicios de IA del frontend (`sequencingService`, `personalizationService`). |

---

## 3. Flujo de Presentación de Contenido (Implementado)

1.  **Frontend Solicita Datos**: El componente `VirtualModule/index.tsx` llama al API para obtener la lista de `VirtualTopicContent` cruda de un tema.
2.  **Orquestación en el Frontend**:
    *   El hook `useTopicOrchestrator` recibe los datos.
    *   **Fragmenta** el contenido de las diapositivas en láminas individuales.
    *   Muestra inmediatamente el contenido fragmentado en la UI.
    *   **En segundo plano**, llama al `sequencingService` para obtener el orden pedagógico de los fragmentos.
    *   Una vez que la IA responde, **reordena** fluidamente los contenidos en la vista.
3.  **Personalización y Renderizado**:
    *   El componente `InteractiveSlideView` renderiza la lista de contenidos (ya ordenada).
    *   Su hijo, `ContentRenderer`, utiliza el hook `useContentPersonalization` para cada elemento.
    *   Este hook llama al servicio de IA de personalización para reemplazar los `{{marcadores}}`.
    *   Aplica la `slide_template` como fondo/estilo al contenedor.
    *   Renderiza el contenido final, ya personalizado, fragmentado y ordenado.

---

## 4. Guía de Integración para Frontend (Actualizada)

### **1. Obtener Contenido de un Tema Virtual**
- **Endpoint**: `GET /api/virtual/topic/<virtual_topic_id>/contents`
- **Respuesta Clave**: El frontend recibe un array de `VirtualTopicContent`. Cada objeto debe contener:
    - `original_content`: El contenido HTML o JSON crudo.
    - `original_personalization_markers`: Objeto con los segmentos para ser procesados por la IA del frontend.
    - `original_slide_template`: Objeto con la plantilla de estilos.
    - `locked`: Booleano para el control de acceso.

### **2. Desbloquear el Siguiente Tema**
- **Endpoint**: `POST /api/virtual/trigger-next-topic`
- **Uso**: Se llama cuando el progreso de un estudiante en un tema supera el 80%.
- **Acción del Frontend**: Tras una respuesta exitosa, refrescar la lista de temas del módulo para mostrar los nuevos temas desbloqueados.

### **3. Flujo de Trabajo del Frontend (Implementado)**

1.  **Cargar Módulo**: Obtener la lista de temas. Usar `locked` para la UI.
2.  **Cargar Tema y Orquestar**:
    *   Al seleccionar un tema, obtener sus contenidos.
    *   El hook `useTopicOrchestrator` se encarga automáticamente de **fragmentar** y **llamar a la IA para ordenar**.
3.  **Renderizar Secuencia**:
    *   `InteractiveSlideView` recibe la lista ordenada.
    *   `ContentRenderer` y `useContentPersonalization` **llaman a la IA para personalizar** cada elemento sobre la marcha.
    *   Se aplica la `slide_template` y se renderiza el contenido final.
4.  **Monitorear Progreso y Desbloquear**:
    *   Se calcula el progreso basado en los contenidos completados.
    *   Al superar el 80%, se habilita la llamada a `/trigger-next-topic`.

Este flujo delega completamente la lógica de presentación, ordenamiento y personalización al frontend, mientras que el backend proporciona una API robusta y simple con los datos necesarios. 