# 🚀 FASE 3: Guía de Implementación para Extensiones Avanzadas

## 1. Objetivo General

La Fase 3 se enfoca en llevar a SapiensAI al siguiente nivel mediante la integración de funcionalidades de alto valor añadido basadas en Inteligencia Artificial y la creación de un ecosistema de contenido. Las características de esta fase son las que diferenciarán a la plataforma y ofrecerán herramientas innovadoras tanto a profesores como a estudiantes.

---

## 2. Guía de Implementación por Funcionalidad

### **2.1 Corrección Automática de Exámenes con IA (En Progreso)**

- **Objetivo**: Ahorrar tiempo a los profesores automatizando la corrección de exámenes escritos (ensayos, respuestas cortas, etc.), ya sean subidos como imagen o documento.
- **Flujo de Usuario**:
  1.  El profesor define una evaluación de tipo "Entrega" y adjunta una **rúbrica** o un documento con las **respuestas correctas**.
  2.  El estudiante sube su examen completado (ej: una foto de su hoja de respuestas).
  3.  El profesor, desde su panel, activa la "Corrección con IA" para esa entrega.
  4.  El sistema procesa el documento, lo califica y presenta al profesor una **nota sugerida** y un **feedback detallado**, que el profesor puede revisar, editar y aprobar.

#### **Responsabilidades del Backend (¡Implementado!):**

1.  **Servicio de Orquestación y Estado (`CorrectionService`)**: El backend ahora actúa como un **gestor de estado**. No ejecuta la IA, pero provee la infraestructura para dar seguimiento a cada paso del proceso.
2.  **Procesamiento Asíncrono**: El proceso sigue siendo asíncrono. El frontend inicia la tarea y el backend le da un `task_id` para que pueda consultar el estado cuando lo necesite, sin bloquear la interfaz.
3.  **Nuevos Endpoints**:
    *   `POST /api/correction/start`: Para iniciar una nueva tarea de corrección y obtener un `task_id`.
    *   `GET /api/correction/task/<task_id>`: Para consultar el estado y el resultado de la corrección.
    *   `PUT /api/correction/task/<task_id>`: **(NUEVO)** Para que el frontend pueda actualizar el estado de la tarea (ej: `status: 'ocr_processing'`) y guardar los resultados (`ocr_extracted_text`, `suggested_grade`, etc.).

#### **Guía para el Frontend (Flujo de Trabajo Corregido):**

1.  **Paso 1: Iniciar la Tarea (Backend)**
    *   Cuando el profesor activa la corrección, el frontend primero llama a `POST /api/correction/start` para registrar la tarea en el backend y obtener el `task_id`.

2.  **Paso 2: Ejecutar OCR (Frontend)**
    *   El frontend obtiene el archivo de la entrega (probablemente vía `GET /api/resources/...`).
    *   Envía el archivo a un servicio de OCR **desde el cliente**.
    *   Una vez que recibe el texto, lo notifica al backend: `PUT /api/correction/task/<task_id>` con `{ "status": "ocr_processing", "ocr_extracted_text": "..." }`.

3.  **Paso 3: Ejecutar Calificación con LLM (Frontend)**
    *   El frontend obtiene el contenido de la rúbrica (otro `GET /api/resources/...`).
    *   Construye el prompt y lo envía al LLM **desde el cliente**.

4.  **Paso 4: Guardar Resultado Final (Backend)**
    *   Cuando el LLM responde, el frontend guarda el resultado final en la tarea: `PUT /api/correction/task/<task_id>` con `{ "status": "completed", "suggested_grade": 95.5, "feedback": "..." }`.

5.  **Paso 5: Mostrar Resultados (Frontend)**
    *   El frontend puede consultar en cualquier momento el endpoint `GET /api/correction/task/<task_id>` para obtener el estado más reciente y mostrarlo en la UI, permitiendo al profesor revisar, editar y confirmar la calificación.

---

### **2.2 Marketplace de Plantillas de Cursos y Juegos (Próximamente)**

- **Objetivo**: Crear un ecosistema donde los profesores puedan compartir y reutilizar contenido de alta calidad.
- **Flujo de Usuario**:
  1.  Un profesor crea un juego interactivo o un plan de estudios completo que le funciona muy bien.
  2.  Decide "Publicar como Plantilla" en el Marketplace de SapiensAI.
  3.  Otro profesor puede explorar el Marketplace, encontrar esa plantilla, previsualizarla y, con un clic, importarla a su propia clase para adaptarla a sus necesidades.

#### **Responsabilidades del Backend (Próximamente):**
- **Nuevos Modelos**: `GameTemplate`, `CourseTemplate`.
- **Sistema de Publicación**: Lógica para clonar y anonimizar contenido para convertirlo en una plantilla reutilizable.
- **Endpoints del Marketplace**: API para buscar, filtrar y obtener plantillas.

---

### **2.3 Sistema de Suscripciones y Pagos (Próximamente)**

- **Objetivo**: Monetizar el uso de la plataforma para usuarios individuales e institutos.
- **Flujo de Usuario**: Un nuevo usuario o administrador de instituto puede seleccionar un plan de suscripción (ej: Básico, Pro, Institucional) y realizar el pago a través de una pasarela integrada.

#### **Responsabilidades del Backend (Próximamente):**
- **Integración con Stripe**: Manejo seguro de pagos.
- **Modelos de Planes**: Lógica para definir límites y características de cada plan.
- **Webhooks**: Para gestionar eventos de la pasarela de pago (pagos correctos, fallidos, renovaciones). 