# Tareas de Backend - Sistema de Contenido

Este documento identifica y organiza específicamente las tareas que requieren implementación en el backend, extraídas del plan de implementación del sistema de contenido.

## 1. Refactorización de Configuración de API Keys y Modelos

### Backend – API Keys

**Prioridad: Alta** ⭐⭐⭐

- **Endpoint /users/me/api-keys**: Verificar que el endpoint recibe y guarda adecuadamente las nuevas claves. Tras el cambio del frontend, debería almacenar en `user.api_keys` el objeto con las claves cifradas. Probar que ahora `UserService.update_user` cifra y guarda (ver logs de "API keys encriptadas para usuario X").

- **Claves del sistema**: No se requiere cambio de backend, ya que las claves API del sistema (para OpenAI, Gemini, etc.) se gestionan en el entorno de la aplicación frontend (p. ej., en archivos .env). El backend no tiene conocimiento ni almacena estas claves.

### Backend – Workers

**Prioridad: Media** ⭐⭐

- **Preparación para contenidos generados**: No se requieren cambios directos de backend para el concepto de workers, ya que toda la generación con LLM se realiza en frontend. El backend solo debe estar preparado para recibir los contenidos generados.

## 2. Configuración e Inicialización de Workers Paralelos

### Backend – Soporte de contenidos individuales

**Prioridad: Alta** ⭐⭐⭐

- **Crear TopicContent individual (diapositivas)**: Modificar el endpoint `POST /api/content/` (ContentService) para que esté optimizado para recibir y crear un único TopicContent de tipo slide a la vez. El flujo de generación del frontend ahora realizará múltiples llamadas a este endpoint, una por cada diapositiva que se genere y guarde secuencialmente. El endpoint debe recibir y almacenar la estructura de la diapositiva (ej. content con el fragmento de texto, slide_template con el estilo, y el order).

- **Actualizar TopicContent individual**: Asegurarse de que el endpoint `PUT /api/content/{id}` funcione correctamente para recibir actualizaciones parciales. Este se usará para añadir primero el contenido HTML generado por la IA y, posteriormente, el texto narrativo a cada diapositiva ya creada.

- **Asignar orden**: El frontend será responsable de enviar el campo order secuencial en cada llamada POST al backend al crear las diapositivas "esqueleto". El modelo TopicContent ya soporta este campo.

- **Actualizar servicios backend**: Verificar en `content.services.py` que `get_contents_by_topic` ordene los resultados por el campo order para asegurar la secuencia correcta de las diapositivas.

## 3. Generación Automática de Contenido

### Backend – Recepción de