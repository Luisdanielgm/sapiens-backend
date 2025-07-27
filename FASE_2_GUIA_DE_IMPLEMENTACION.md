# 🚀 FASE 2: Guía de Implementación Completa para Mejoras de la Plataforma

## 1. Objetivo General

Esta fase se centra en expandir y robustecer la plataforma SapiensAI, moviéndola de un núcleo funcional a una aplicación más completa, segura y escalable. Las mejoras abarcan desde la autenticación de usuarios hasta la eficiencia en la creación de contenido y el soporte para nuevos modelos de uso.

---

## 2. Guía de Implementación por Funcionalidad

A continuación se detalla cada nueva funcionalidad, explicando las responsabilidades del backend (ya implementadas) y las tareas pendientes para el frontend.

### **2.1 Autenticación con Email y Contraseña (¡NUEVO!)**

- **Objetivo**: Permitir que los usuarios se registren e inicien sesión directamente en la plataforma sin depender de proveedores externos como Google.
- **Estado del Backend**: **¡Implementado!**

#### **Guía para el Frontend:**

1.  **Formulario de Registro**:
    *   Crear un nuevo formulario de registro que solicite `nombre`, `email`, `contraseña` y `rol`.
    *   Al enviar, realizar una llamada al nuevo endpoint:
        *   **Endpoint**: `POST /api/users/register`
        *   **Body (JSON)**: `{ "name": "...", "email": "...", "password": "...", "role": "student" }`
        *   **Respuesta Exitosa**: El backend devolverá un `token` de sesión y el objeto `user`. El frontend debe guardar este token y redirigir al usuario a su dashboard, ya autenticado.
        *   **Manejo de Errores**: El endpoint validará si el email ya existe y devolverá un error `409 Conflict` (código `ALREADY_EXISTS`) que la UI debe mostrar al usuario.

2.  **Formulario de Inicio de Sesión (Lógica Actualizada)**:
    *   El frontend debe manejar **dos flujos de login** que apuntan al **mismo endpoint**. La diferencia está en el `body` de la petición.

    *   **CASO A: Login con Email y Contraseña**
        *   Cuando el usuario ingresa su correo y contraseña y hace clic en "Iniciar Sesión":
        *   **Endpoint**: `POST /api/users/login`
        *   **Body (JSON)**:
            ```json
            {
              "email": "usuario@ejemplo.com",
              "password": "la_contraseña_del_usuario"
            }
            ```

    *   **CASO B: Login con Google**
        *   Cuando el usuario hace clic en "Iniciar Sesión con Google" y la librería de Google devuelve el token/credencial:
        *   **Endpoint**: `POST /api/users/login`
        *   **Body (JSON)**:
            ```json
            {
              "email": "email_del_usuario_google@gmail.com",
              "credential": "el_token_o_credencial_recibido_de_google"
            }
            ```
    *   **Respuesta del Backend**: En ambos casos, si el login es exitoso, la respuesta del backend será idéntica: un `token` JWT y el objeto `user`.
        ```json
        {
          "token": "ey...",
          "user": { "id": "...", "name": "...", "email": "...", "role": "..." }
        }
        ```

### **2.2 Generación Paralela de Contenidos (Asíncrona)**

- **Objetivo**: Mejorar drásticamente la velocidad y la experiencia de usuario durante la generación de contenido, permitiendo procesar múltiples tipos de contenido simultáneamente.
- **Estado del Backend**: **¡Implementado!**

#### **Guía para el Frontend:**

1.  **Iniciar la Tarea en Lote**: Llamar a `POST /api/content/generate-batch` con los `content_types` seleccionados. El backend responderá inmediatamente con un `task_id`.
2.  **Ejecutar Llamadas a la IA en Paralelo**: El frontend es responsable de realizar las llamadas a los LLMs para cada tipo de contenido.
3.  **Guardar Contenido y Actualizar Estado**:
    *   Guardar cada contenido generado usando el endpoint `POST /api/content/`.
    *   *(Mejora Futura)*: Notificar al backend la completitud de cada sub-tarea.
4.  **Consultar Progreso y Actualizar UI**: Hacer *polling* a `GET /api/content/generation-task/<task_id>` para obtener el progreso y actualizar la interfaz en tiempo real, mostrando qué contenidos están listos y cuáles siguen en proceso.
5.  **Manejar Recuperación de Sesión**: Si el usuario recarga, usar el `task_id` (guardado en `localStorage`) para consultar el estado y reanudar las generaciones pendientes.

### **2.3 Nuevos Tipos de Contenido (¡NUEVO!)**

- **Objetivo**: Expandir la variedad pedagógica de la plataforma soportando nuevos formatos interactivos.
- **Estado del Backend**: **¡Implementado!** El backend ahora puede almacenar y servir los siguientes nuevos `content_type`: `flashcards`, `gemini_live` (conversacional), `interactive_exercise`, `glossary`.

#### **Guía para el Frontend:**

1.  **Añadir Opciones en la UI**: El profesor, al crear contenido, ahora debe ver las opciones para generar estos nuevos tipos.
2.  **Crear "Visores" de Contenido**: El frontend necesita desarrollar los componentes de React para renderizar e interactuar con cada nuevo tipo:
    *   **Visor de `flashcards`**: Un componente que muestre una tarjeta, con un botón o acción para "voltearla" y ver la respuesta.
    *   **Componente `gemini_live`**: Una interfaz de chat conversacional para la interacción con la IA.
    *   **Visor de `interactive_exercise`**: Un componente genérico que pueda renderizar diferentes tipos de ejercicios (ej: rellenar espacios, arrastrar y soltar).
    *   **Visor de `glossary`**: Un componente que muestre una lista de términos y definiciones de manera clara.
3.  **Integración con `ContentResult`**: Para los tipos evaluativos (`flashcards`, `gemini_live`), el frontend debe llamar a `POST /api/virtual/content-result` al finalizar la interacción para guardar el resultado del estudiante.

### **2.4 Multi-Instituto para Profesores (¡NUEVO!)**

- **Objetivo**: Permitir que un solo usuario (profesor) pueda pertenecer y trabajar en múltiples institutos desde una única cuenta.
- **Estado del Backend**: **¡Implementado!** El modelo `InstituteMember` ya soporta que un `user_id` esté en múltiples institutos. El token de sesión (JWT) **no** contiene un `institute_id` fijo, por lo que es agnóstico al contexto.

#### **Guía para el Frontend:**

1.  **Selector de Contexto de Instituto**:
    *   Después del login, si se detecta que un profesor pertenece a más de un instituto, el frontend debe mostrar una UI (ej: un modal o una página intermedia) que le pida al usuario **seleccionar en qué instituto desea trabajar** durante esa sesión.
    *   La lista de institutos a los que pertenece un usuario se puede obtener de su perfil o de un endpoint específico.
2.  **Almacenamiento del Contexto**:
    *   Una vez que el profesor selecciona un instituto, el frontend debe **guardar el `institute_id` seleccionado en el estado global de la aplicación** (ej: en un Context de React, Redux, etc.) y posiblemente en `localStorage` para persistencia.
3.  **Filtrado en las Peticiones**:
    *   A partir de ese momento, **todas las llamadas a la API** que listen recursos de un instituto (cursos, estudiantes, etc.) deben incluir el `institute_id` seleccionado como un parámetro en la URL o en el query string. Por ejemplo: `GET /api/study_plan/assignments?institute_id=...`. El backend ya está preparado para filtrar los datos según este parámetro.

### **2.5 Soporte para Usuarios Individuales (¡NUEVO!)**

- **Objetivo**: Permitir que estudiantes o profesores independientes usen SapiensAI para sus propios fines de estudio o enseñanza sin pertenecer a una institución formal.
- **Estado del Backend**: **¡Implementado!** Se ha creado una lógica para un "Instituto Genérico" llamado "Academia Sapiens".

#### **Guía para el Frontend:**

1.  **Flujo de Registro Individual**:
    *   En la página de registro, debe haber opciones claras: "Registrarse como Institución", "Registrarse como Profesor Particular", "Registrarse para Estudiar por mi Cuenta".
2.  **Lógica para "Profesor Particular"**:
    *   Al registrarse con este rol, el frontend debe llamar a `POST /api/users/register`. El backend automáticamente creará un "mini-instituto" personal para este profesor, donde él será el administrador y único miembro.
    *   La UI debe guiarlo directamente a la vista de profesor para que pueda empezar a crear sus cursos y planes de estudio.
3.  **Lógica para "Estudiante Individual"**:
    *   Al registrarse, el backend lo asociará al instituto genérico "Academia Sapiens".
    *   La UI debe llevarlo a un flujo simplificado donde pueda **subir un documento o describir un tema** para que el sistema le genere automáticamente un plan de estudios y un módulo virtual. Este flujo es similar al de un profesor, pero enfocado en un solo estudiante.

---

Este documento ahora sirve como una guía completa para que el equipo de frontend implemente todas las funcionalidades de la Fase 2. 