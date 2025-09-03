Plan de Implementación por Módulos (Corregido)
Dada la magnitud de los cambios, se propone abordar por bloques funcionales, asegurando que cada etapa deje el sistema estable. Se listan tareas concretas indicando (Frontend) o (Backend) donde corresponda:
1. Refactorización de Configuración de API Keys y Modelos
Frontend – Unificar Vista de Configuración:
Integrar vista de perfil y generación: Reutilizar el componente integral de configuración (IntegratedApiKeyConfiguration) tanto en el perfil del usuario como en la pestaña de configuración de generación de contenidos. En la pestaña “Configuración del Sistema” de TopicGenerations, reemplazar la sección actual de ApiKeyConfiguration por este componente unificado, de forma que el usuario vea una misma interfaz en ambos lugares.
Mostrar claves del sistema: Modificar ProviderPreferenceToggle y la lógica relacionada para distinguir entre API Key del sistema y del usuario. Incluir un indicador (ej. ícono de ojo) que permita al usuario ver la clave API completa actualmente en uso para cada proveedor (tanto la del sistema como la del usuario). Si el usuario no ha configurado su propia clave para un proveedor, mostrar que se usará la clave del sistema (y permitir visualizarla). Esto implica leer las variables de entorno públicas del frontend (ej. NEXT_PUBLIC_GEMINI_API_KEY).
Corregir guardado de keys: Arreglar el bug de formato al guardar claves. Ajustar apiKeyService.saveKey para enviar el payload anidando las claves bajo api_keys. Por ejemplo:
code
JavaScript
await fetchWithAuth('/users/me/api-keys', { 
     method: 'PUT', 
     body: JSON.stringify({ api_keys: currentKeys }) 
});
De esta manera el backend recibirá processed_data["api_keys"] y cifrará las claves correctamente.
Validación y estado: Mantener la validación de formato y prueba de clave mediante los endpoints de /llm/validate/* (esto ya existe). Asegurarse de actualizar el estado de validationResults después de guardar o remover una clave para retroalimentar al usuario con iconos de estado (check verde, etc.).
Backend – API Keys:
Endpoint /users/me/api-keys: Verificar que el endpoint recibe y guarda adecuadamente las nuevas claves. Tras el cambio del frontend, debería almacenar en user.api_keys el objeto con las claves cifradas. Probar que ahora UserService.update_user cifra y guarda (ver logs de "API keys encriptadas para usuario X").
Claves del sistema: No se requiere cambio de backend, ya que las claves API del sistema (para OpenAI, Gemini, etc.) se gestionan en el entorno de la aplicación frontend (p. ej., en archivos .env). El backend no tiene conocimiento ni almacena estas claves. La lógica del frontend es la única responsable de acceder a ellas.
Frontend – Configuración por Worker:
Eliminar preferencia por tipo: Deprecar o quitar la UI de ModelPreferenceSelector por tipo de contenido. En su lugar, introducir una sección de Configuración de Workers. Por ejemplo, en la interfaz integral agregar una pestaña “Workers” (en lugar de “Modelos por Contenido”) donde se liste Worker 1 a 5. Cada fila debe permitir:
Seleccionar el Proveedor/Modelo a usar (combinado en un solo dropdown). Se pueden listar modelos con el nombre legible incluyendo proveedor, e.g. “Gemini 2.5 Flash (Google)”, “GPT-4 (OpenAI)” etc. La lista de modelos disponibles ya existe en constantes.
Elegir la API Key a utilizar: un toggle “Usar mi clave” vs “Usar clave del sistema”. Si el usuario no ha provisto clave para ese proveedor y activa “clave propia”, mostrar un campo para ingresarla (o deshabilitar la opción indicando que no hay clave propia disponible). Mostrar junto al proveedor seleccionado los últimos 4-6 dígitos de la key correspondiente según la elección para confirmar (ej. “(Usando clave sistema ****1234)”).
Estado persistente: Decidir dónde guardar la configuración de workers. Puesto que es específica por usuario, puede almacenarse en el localStorage (e.g. clave sapiens_worker_prefs) para persistir: un array de 5 objetos { provider, model, useSystemKey }. Proveer funciones para cargar/guardar esta config.
Integración con generación: Actualizar el inicializador del pool de workers para usar la configuración elegida. Cada vez que se envíe una tarea a un worker, se debe utilizar el modelo y la API Key configurados para ese worker específico. Esto requiere integrar la lógica de generación IA dentro de workerPoolService en vez de simular con setTimeout.
Backend:
No se requieren cambios directos de backend para el concepto de workers, ya que toda la generación con LLM se realiza en frontend. El backend solo debe estar preparado para recibir los contenidos generados.
2. Configuración e Inicialización de Workers Paralelos
Frontend – Lógica de Worker Pool:
Ajustar tamaño del pool: Cambiar la configuración por defecto del pool a 5 workers en workerPoolService.createPool (propiedad maxWorkers).
Asignación de modelos por worker: Integrar la configuración del punto anterior aquí. Al crear cada worker, se le debe asociar la configuración de modelo/API Key que el usuario haya definido. Por defecto, los 5 workers utilizarán Gemini 2.5 Flash con la clave del sistema.
Integrar generación real: Reemplazar la simulación de processTask por llamadas reales a las funciones de generación de IA. El workerPoolService se convertirá en el orquestador principal que despacha tareas específicas (generar estilo, generar contenido de slide, generar texto narrativo) a los workers disponibles.
Marcar finalización de tareas: Ajustar completeTask y failTask del pool para que registren correctamente el resultado y emitan los eventos task_completed o task_failed hacia ParallelGenerationService. El result.data debe contener la información necesaria para el siguiente paso del flujo (ej. el ID de la diapositiva recién creada).
Backend – Soporte de contenidos individuales:
Crear TopicContent individual (diapositivas): Modificar el endpoint POST /api/content/ (ContentService) para que esté optimizado para recibir y crear un único TopicContent de tipo slide a la vez. El flujo de generación del frontend ahora realizará múltiples llamadas a este endpoint, una por cada diapositiva que se genere y guarde secuencialmente. El endpoint debe recibir y almacenar la estructura de la diapositiva (ej. content con el fragmento de texto, slide_template con el estilo, y el order).
Actualizar TopicContent individual: Asegurarse de que el endpoint PUT /api/content/{id} funcione correctamente para recibir actualizaciones parciales. Este se usará para añadir primero el contenido HTML generado por la IA y, posteriormente, el texto narrativo a cada diapositiva ya creada.
Asignar orden: El frontend será responsable de enviar el campo order secuencial en cada llamada POST al backend al crear las diapositivas "esqueleto". El modelo TopicContent ya soporta este campo.
Actualizar servicios backend: Verificar en content.services.py que get_contents_by_topic ordene los resultados por el campo order para asegurar la secuencia correcta de las diapositivas.
3. Generación Automática de Contenido Teórico, Diapositivas y Quiz (Flujo Corregido)
Esta sección detalla el nuevo flujo de generación secuencial y paralelo para garantizar que al pulsar "Generar Contenido" se produzcan todos los contenidos obligatorios correctamente.
Fase 1: Generación de Prerrequisitos
(Frontend) Generar Contenido Teórico: Se utiliza un worker para generar el texto teórico completo con IA. Esta operación es bloqueante para el resto del flujo de diapositivas. Una vez completado, se guarda en el Topic.
(Frontend) Generar Estilo de la Presentación: Simultáneamente (o inmediatamente después), se utiliza otro worker para generar el estilo visual (plantilla HTML/CSS, colores, degradados, iconos) para toda la presentación. El prompt se basará en el tema, módulo y plan de estudio. El resultado se mantiene en memoria en el frontend.
(Frontend) Particionar Contenido Teórico: Una vez generado el contenido teórico, se parte en fragmentos utilizando lógica de programación (sin IA, para evitar resúmenes o corrupción del texto). Se puede basar en títulos o subtítulos Markdown.
Fase 2: Creación y Guardado Secuencial de Diapositivas "Esqueleto"
(Frontend) Bucle de Guardado: Se itera sobre los fragmentos de texto. Por cada fragmento:
Se crea un objeto de diapositiva que contiene el fragmento de texto, el estilo generado en la Fase 1 y su número de orden.
Se realiza una llamada POST /api/content/ al backend para guardar esta diapositiva "esqueleto" en la base de datos.
Este proceso se repite para cada fragmento, asegurando que cada diapositiva se guarde individualmente antes de proceder a la siguiente.
Fase 3: Generación de Contenido Visual de Diapositivas (Paralelo)
(Frontend) Despacho a Workers: Una vez que todas las diapositivas "esqueleto" están guardadas, se despachan tareas al pool de 5 workers. Cada tarea consiste en:
Tomar el ID y el fragmento de texto de una diapositiva.
Utilizar un worker para generar el contenido visual (HTML, columnas, palabras clave, etc.) para esa diapositiva.
Una vez generado, realizar una llamada PUT /api/content/{id} para actualizar la diapositiva en la base de datos con el nuevo content_html.
Los workers tomarán las tareas de la cola a medida que se desocupen hasta completar todas las diapositivas.
Fase 4: Generación de Texto Narrativo (Paralelo)
(Frontend) Despacho a Workers: Similar a la fase anterior, se despachan nuevas tareas al pool de workers. Cada tarea consiste en:
Tomar el ID, el content_html y el fragmento de texto completo de una diapositiva ya generada.
Utilizar un worker para generar un texto narrativo amigable y detallado.
Realizar una llamada PUT /api/content/{id} para actualizar la diapositiva con el texto narrativo (ej. en el campo content.full_text).
Fase 5: Generación del Quiz (Oportunista)
(Frontend) Generación del Quiz: Una vez que un worker se desocupa y no quedan tareas de generación de diapositivas o textos narrativos, puede tomar la tarea de generar la evaluación (quiz) para el tema. Esto asegura que el quiz se genere en paralelo tan pronto como haya recursos disponibles, pero siempre después de que el contenido teórico base esté listo.
4. Visualización de Diapositivas y Módulo Virtual
(Frontend) Visor en Generación de Contenido (Profesor):
Mostrar lista de diapositivas generadas: Corregir el componente TopicContentViewer.tsx para que itere sobre topic.contents y renderice cada contenido de tipo 'slide' como una entrada individual. La causa probable del error actual ("las diapositivas actuales ni siquiera se muestran") es que el visor espera un único contenido de tipo 'slides'.
Implementar un visor de carrusel: Agrupar todas las TopicContent de tipo 'slide' y mostrarlas en un visor secuencial con botones de Siguiente/Anterior.
Incluir texto narrativo: En el visor del profesor, mostrar el texto narrativo de cada diapositiva en una sección designada.
(Frontend) Módulo Virtual (Estudiante):
Secuencia estructurada: Actualizar la lógica que construye el VirtualTopicContent para ordenar los contenidos estrictamente por el campo order. El flujo debe ser: diapositivas 1..N, luego contenidos opcionales, y finalmente el quiz.
Navegación entre modales: Asegurar que la navegación (SlideNavigation) funcione correctamente entre modales de diapositivas individuales y que, al finalizar la última, avance al siguiente tipo de contenido.
(Backend) Virtual Module:
ContentResult tracking: Verificar que el modelo ContentResult y el endpoint /virtual/content-result estén preparados para recibir y almacenar resultados por cada content_id de diapositiva individual, permitiendo un seguimiento granular del progreso del estudiante.
5. Integración de Plantillas Interactivas con Diapositivas
(Frontend) UI de Plantillas en Generación de Contenido:
Galería y Adaptación: En la vista de diapositivas, añadir un botón "Agregar Actividad Interactiva". Al pulsarlo, mostrar una galería de plantillas.
Flujo de Adaptación con IA: Junto a cada plantilla, mostrar un botón "Adaptar". Al hacer clic:
La IA recibe la plantilla y el contexto del tema/diapositiva.
Se genera una nueva plantilla adaptada (un fork o clon) con el contenido del tema. La plantilla original no se modifica.
Esta nueva plantilla adaptada aparece en la lista, marcada como lista para usar.
Creación de Contenido de Instancia: Al seleccionar una plantilla ya adaptada, se crea un nuevo TopicContent de tipo interactivo (render_engine: 'html_template') y se inserta en la secuencia después de la diapositiva actual, asignándole un order intermedio (ej. slide.order + 0.5).
(Backend) Soporte de Plantillas Interactivas:
Fork y Adaptación: Asegurarse de que existan los endpoints para clonar una plantilla (/templates/fork) y para crear un TopicContent a partir de una instancia de plantilla.
Guardar order: El backend debe respetar y guardar correctamente el order decimal para posicionar la actividad interactiva entre dos diapositivas.
6. Personalización Adaptativa (Markers y RL)
(Backend) Refuerzo Adaptativo:
Actualizar ContentResult para nuevos tipos: Garantizar que el modelo RL en adaptiveLearningService pueda procesar resultados de content_result para cada diapositiva individual, permitiendo un aprendizaje más granular sobre la efectividad de cada una.
(Backend) Markers de personalización:
Verificar e integrar la llamada a personalizationService.apply_markers(content, student) durante la creación del VirtualModule para que los placeholders (ej. {{student.nombre}}) en cualquier tipo de contenido (diapositivas, plantillas) se reemplacen dinámicamente.