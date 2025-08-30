# Guías de Plantillas - SapiensIA

## Índice
1. [Introducción](#introducción)
2. [Arquitectura del Sistema](#arquitectura-del-sistema)
3. [Convenciones de Marcadores](#convenciones-de-marcadores)
4. [Estructura de Plantillas](#estructura-de-plantillas)
5. [Ejemplos Prácticos](#ejemplos-prácticos)
6. [Mejores Prácticas](#mejores-prácticas)
7. [Integración con Contenido](#integración-con-contenido)
8. [Personalización y Mix VARK](#personalización-y-mix-vark)
9. [Troubleshooting](#troubleshooting)

## Introducción

El sistema de plantillas de SapiensIA permite crear contenido educativo interactivo y reutilizable mediante plantillas HTML que pueden ser personalizadas para diferentes temas y contextos educativos.

### Conceptos Clave
- **Template**: Plantilla global reutilizable con HTML, CSS y JavaScript
- **TemplateInstance**: Instancia específica de una plantilla para un tema
- **Marcadores**: Elementos especiales en el HTML que permiten personalización
- **Props**: Valores específicos que se aplican a los marcadores
- **Assets**: Recursos multimedia asociados a la plantilla

## Arquitectura del Sistema

### Modelos Principales

#### Template
```python
class Template:
    _id: ObjectId
    name: str                    # Nombre descriptivo
    owner_id: ObjectId          # Creador de la plantilla
    html: str                   # Código HTML/CSS/JS
    engine: str = "html"        # Motor de renderizado
    version: str = "1.0.0"      # Versión actual
    scope: str = "private"      # private, org, public
    status: str = "draft"       # draft, usable, certified
    props_schema: Dict          # Esquema de parámetros
    defaults: Dict              # Valores por defecto
    baseline_mix: Dict          # Mix VARK base
    capabilities: Dict          # Requisitos técnicos
    style_tags: List[str]       # Tags de estilo
    subject_tags: List[str]     # Tags de materia
    versions: List[Dict]        # Historial de versiones
```

#### TemplateInstance
```python
class TemplateInstance:
    _id: ObjectId
    template_id: ObjectId       # Referencia a Template
    topic_id: ObjectId          # Tema asociado
    creator_id: ObjectId        # Usuario que creó la instancia
    template_version: str       # Versión de plantilla usada
    parent_content_id: ObjectId # Vinculación con diapositiva
    props: Dict                 # Valores específicos
    assets: List[Dict]          # Recursos multimedia
    learning_mix: Dict          # Mix VARK personalizado
    status: str = "draft"       # Estado de la instancia
```

## Convenciones de Marcadores

### Tipos de Marcadores

#### 1. Parámetros (`data-sapiens-param`)
Permiten personalizar texto, colores, tamaños y otros valores.

```html
<!-- Texto personalizable -->
<h1 data-sapiens-param="title">Título por Defecto</h1>

<!-- Color personalizable -->
<div style="background: data-sapiens-param='background_color';">Contenido</div>

<!-- Tamaño personalizable -->
<div style="font-size: data-sapiens-param='font_size';">Texto</div>
```

#### 2. Assets (`data-sapiens-asset`)
Referencian recursos multimedia externos.

```html
<!-- Imagen -->
<img data-sapiens-asset="main_image" alt="Imagen principal" />

<!-- Audio -->
<audio data-sapiens-asset="background_music" controls></audio>

<!-- Video -->
<video data-sapiens-asset="tutorial_video" controls></video>
```

#### 3. Slots (`data-sapiens-slot`)
Áreas de contenido que pueden ser generadas por IA.

```html
<!-- Contenido de texto -->
<p data-sapiens-slot="instructions">Instrucciones por defecto</p>

<!-- Lista de elementos -->
<ul data-sapiens-slot="key_points">
    <li>Punto clave 1</li>
    <li>Punto clave 2</li>
</ul>
```

#### 4. Condicionales (`data-sapiens-if`)
Controlan la visibilidad de elementos.

```html
<!-- Mostrar solo si la condición es verdadera -->
<button data-sapiens-if="show_hints" onclick="showHints()">Mostrar Pistas</button>

<!-- Elemento opcional -->
<div data-sapiens-if="advanced_mode" class="advanced-content">
    Contenido avanzado
</div>
```

### Convenciones de Nomenclatura

#### Parámetros
- **Texto**: `title`, `subtitle`, `description`, `instructions`
- **Colores**: `primary_color`, `secondary_color`, `background_color`, `text_color`
- **Tamaños**: `font_size`, `button_size`, `container_width`, `image_height`
- **Configuración**: `max_attempts`, `time_limit`, `difficulty_level`

#### Assets
- **Imágenes**: `main_image`, `background_image`, `icon_[name]`
- **Audio**: `background_music`, `sound_effect_[name]`, `narration`
- **Video**: `intro_video`, `tutorial_video`, `example_[number]`

#### Slots
- **Contenido**: `instructions`, `description`, `summary`, `conclusion`
- **Listas**: `key_points`, `examples`, `steps`, `objectives`
- **Interactivo**: `question_text`, `feedback`, `explanation`

## Estructura de Plantillas

### Plantilla Básica

```html
<!DOCTYPE html>
<html lang="es">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title data-sapiens-param="title">Título de la Actividad</title>
    <style>
        /* Estilos CSS con parámetros personalizables */
        body {
            font-family: data-sapiens-param="font_family";
            background: data-sapiens-param="background_color";
            color: data-sapiens-param="text_color";
        }
        
        .container {
            max-width: data-sapiens-param="container_width";
            margin: 0 auto;
            padding: 20px;
        }
    </style>
</head>
<body>
    <div class="container">
        <h1 data-sapiens-param="title">Título Principal</h1>
        <p data-sapiens-slot="instructions">Instrucciones de la actividad</p>
        
        <!-- Contenido principal -->
        <div class="content">
            <!-- Elementos interactivos aquí -->
        </div>
        
        <!-- Controles opcionales -->
        <div class="controls" data-sapiens-if="show_controls">
            <button onclick="reset()">Reiniciar</button>
        </div>
    </div>
    
    <!-- Script con valores por defecto -->
    <script id="sapiens-defaults" type="application/json">
    {
        "title": "Mi Actividad",
        "font_family": "Arial, sans-serif",
        "background_color": "#ffffff",
        "text_color": "#333333",
        "container_width": "800px",
        "instructions": "Completa la actividad siguiendo las instrucciones.",
        "show_controls": true
    }
    </script>
    
    <script>
        // JavaScript de la actividad
        function reset() {
            // Lógica de reinicio
        }
    </script>
</body>
</html>
```

### Esquema de Props Automático

El sistema extrae automáticamente el esquema de props del HTML:

```json
{
    "type": "object",
    "properties": {
        "title": {
            "type": "string",
            "title": "Título",
            "description": "Título principal de la actividad",
            "default": "Mi Actividad"
        },
        "background_color": {
            "type": "string",
            "format": "color",
            "title": "Color de Fondo",
            "default": "#ffffff"
        },
        "main_image": {
            "type": "string",
            "format": "uri",
            "title": "Imagen Principal",
            "description": "Recurso requerido: main_image"
        }
    }
}
```

## Ejemplos Prácticos

### 1. Quiz Interactivo

```html
<!DOCTYPE html>
<html lang="es">
<head>
    <meta charset="UTF-8">
    <title data-sapiens-param="quiz_title">Quiz Interactivo</title>
    <style>
        .quiz-container {
            max-width: 800px;
            margin: 0 auto;
            background: data-sapiens-param="container_bg";
            border-radius: 10px;
            padding: 30px;
        }
        
        .question-card {
            background: white;
            padding: 20px;
            border-radius: 8px;
            margin-bottom: 20px;
            box-shadow: 0 2px 4px rgba(0,0,0,0.1);
        }
        
        .option {
            background: #f8f9fa;
            border: 2px solid #e9ecef;
            padding: 15px;
            margin: 10px 0;
            border-radius: 5px;
            cursor: pointer;
            transition: all 0.3s ease;
        }
        
        .option:hover {
            background: data-sapiens-param="hover_color";
        }
        
        .option.selected {
            border-color: data-sapiens-param="accent_color";
            background: data-sapiens-param="accent_color";
            color: white;
        }
    </style>
</head>
<body>
    <div class="quiz-container">
        <h1 data-sapiens-param="quiz_title">Quiz de Conocimientos</h1>
        <p data-sapiens-slot="instructions">Responde las siguientes preguntas seleccionando la opción correcta.</p>
        
        <div class="question-card">
            <h3 data-sapiens-param="question_1_text">¿Cuál es la respuesta correcta?</h3>
            <div class="option" data-option="1" data-sapiens-param="question_1_option_1">Opción A</div>
            <div class="option" data-option="2" data-sapiens-param="question_1_option_2">Opción B</div>
            <div class="option" data-option="3" data-sapiens-param="question_1_option_3">Opción C</div>
            <div class="option" data-option="4" data-sapiens-param="question_1_option_4">Opción D</div>
        </div>
        
        <button onclick="submitQuiz()" data-sapiens-if="show_submit">Enviar Respuestas</button>
        
        <div class="results" id="results" style="display: none;">
            <h3>Resultados</h3>
            <p data-sapiens-slot="feedback">¡Excelente trabajo!</p>
        </div>
    </div>
    
    <script id="sapiens-defaults" type="application/json">
    {
        "quiz_title": "Quiz Educativo",
        "container_bg": "#f0f8ff",
        "hover_color": "#e3f2fd",
        "accent_color": "#2196f3",
        "question_1_text": "¿Cuál es la capital de Francia?",
        "question_1_option_1": "Londres",
        "question_1_option_2": "París",
        "question_1_option_3": "Madrid",
        "question_1_option_4": "Roma",
        "question_1_correct": 2,
        "instructions": "Lee cada pregunta cuidadosamente y selecciona la respuesta correcta.",
        "feedback": "¡Felicitaciones! Has completado el quiz.",
        "show_submit": true
    }
    </script>
    
    <script>
        let selectedAnswers = {};
        
        // Manejar selección de opciones
        document.querySelectorAll('.option').forEach(option => {
            option.addEventListener('click', function() {
                const questionCard = this.closest('.question-card');
                const questionIndex = Array.from(questionCard.parentNode.children).indexOf(questionCard);
                
                // Remover selección anterior
                questionCard.querySelectorAll('.option').forEach(opt => {
                    opt.classList.remove('selected');
                });
                
                // Agregar selección actual
                this.classList.add('selected');
                selectedAnswers[questionIndex] = parseInt(this.dataset.option);
            });
        });
        
        function submitQuiz() {
            // Lógica de evaluación
            const correctAnswers = {
                0: parseInt(document.querySelector('[data-sapiens-param="question_1_correct"]').textContent || '2')
            };
            
            let score = 0;
            Object.keys(selectedAnswers).forEach(questionIndex => {
                if (selectedAnswers[questionIndex] === correctAnswers[questionIndex]) {
                    score++;
                }
            });
            
            // Mostrar resultados
            document.getElementById('results').style.display = 'block';
            
            // Enviar resultado al sistema
            if (window.sapiensAPI) {
                window.sapiensAPI.submitResult({
                    type: 'quiz',
                    score: score,
                    total: Object.keys(correctAnswers).length,
                    answers: selectedAnswers
                });
            }
        }
    </script>
</body>
</html>
```

### 2. Mapa Mental Interactivo

```html
<!DOCTYPE html>
<html lang="es">
<head>
    <meta charset="UTF-8">
    <title data-sapiens-param="title">Mapa Mental Interactivo</title>
    <style>
        body {
            font-family: Arial, sans-serif;
            margin: 0;
            padding: 20px;
            background: data-sapiens-param="background_color";
        }
        
        .mindmap-container {
            width: 100%;
            height: 600px;
            position: relative;
            border: 2px solid data-sapiens-param="border_color";
            border-radius: 10px;
            overflow: hidden;
        }
        
        .central-node {
            position: absolute;
            top: 50%;
            left: 50%;
            transform: translate(-50%, -50%);
            width: data-sapiens-param="central_node_size";
            height: data-sapiens-param="central_node_size";
            background: data-sapiens-param="central_node_color";
            border-radius: 50%;
            display: flex;
            align-items: center;
            justify-content: center;
            color: white;
            font-weight: bold;
            cursor: pointer;
            box-shadow: 0 4px 8px rgba(0,0,0,0.2);
        }
        
        .branch-node {
            position: absolute;
            background: data-sapiens-param="branch_color";
            color: white;
            padding: 10px 15px;
            border-radius: 20px;
            cursor: pointer;
            transition: all 0.3s ease;
        }
        
        .branch-node:hover {
            transform: scale(1.1);
        }
    </style>
</head>
<body>
    <div class="instructions">
        <h3>Instrucciones</h3>
        <p data-sapiens-slot="instructions">Haz clic en el nodo central para explorar los conceptos relacionados.</p>
    </div>
    
    <div class="mindmap-container" id="mindmapContainer">
        <div class="central-node" id="centralNode">
            <span data-sapiens-param="central_concept">Concepto Principal</span>
        </div>
    </div>
    
    <div class="controls" data-sapiens-if="show_controls">
        <button onclick="resetMindmap()">Reiniciar</button>
        <button onclick="expandAll()">Expandir Todo</button>
    </div>
    
    <script id="sapiens-defaults" type="application/json">
    {
        "title": "Mapa Mental Interactivo",
        "background_color": "#f5f5f5",
        "border_color": "#2196F3",
        "central_node_size": "120px",
        "central_node_color": "#2196F3",
        "branch_color": "#4CAF50",
        "central_concept": "Tema Principal",
        "branch_1": "Concepto 1",
        "branch_2": "Concepto 2",
        "branch_3": "Concepto 3",
        "branch_4": "Concepto 4",
        "branch_5": "Concepto 5",
        "instructions": "Explora el mapa mental haciendo clic en los nodos.",
        "show_controls": true
    }
    </script>
    
    <script>
        const branches = [
            { text: "{{branch_1}}", angle: 0, distance: 180 },
            { text: "{{branch_2}}", angle: 72, distance: 180 },
            { text: "{{branch_3}}", angle: 144, distance: 180 },
            { text: "{{branch_4}}", angle: 216, distance: 180 },
            { text: "{{branch_5}}", angle: 288, distance: 180 }
        ];
        
        function initializeMindmap() {
            // Lógica de inicialización del mapa mental
        }
        
        function resetMindmap() {
            // Lógica de reinicio
        }
        
        function expandAll() {
            // Lógica de expansión
        }
        
        // Inicializar al cargar
        document.addEventListener('DOMContentLoaded', initializeMindmap);
    </script>
</body>
</html>
```

## Mejores Prácticas

### 1. Diseño de Plantillas

#### Estructura Modular
- Separar CSS, HTML y JavaScript claramente
- Usar clases CSS reutilizables
- Implementar funciones JavaScript modulares

#### Responsividad
```css
/* Usar unidades relativas */
.container {
    width: data-sapiens-param="container_width";
    max-width: 100%;
    padding: data-sapiens-param="padding";
}

/* Media queries para diferentes dispositivos */
@media (max-width: 768px) {
    .container {
        padding: 10px;
    }
}
```

#### Accesibilidad
```html
<!-- Usar etiquetas semánticas -->
<main role="main">
    <section aria-label="Contenido principal">
        <h1 data-sapiens-param="title">Título</h1>
    </section>
</main>

<!-- Incluir atributos ARIA -->
<button aria-label="Enviar respuesta" onclick="submit()">Enviar</button>

<!-- Contraste de colores adecuado -->
<style>
    .text {
        color: data-sapiens-param="text_color";
        background: data-sapiens-param="bg_color";
        /* Asegurar contraste mínimo 4.5:1 */
    }
</style>
```

### 2. Parámetros y Configuración

#### Valores por Defecto Sensatos
```json
{
    "font_size": "16px",
    "line_height": "1.5",
    "primary_color": "#2196f3",
    "secondary_color": "#4caf50",
    "background_color": "#ffffff",
    "text_color": "#333333",
    "border_radius": "8px",
    "animation_duration": "0.3s"
}
```

#### Validación de Parámetros
```javascript
// Validar parámetros en JavaScript
function validateParams(params) {
    const defaults = {
        max_attempts: 3,
        time_limit: 300,
        difficulty: 'medium'
    };
    
    return Object.assign(defaults, params);
}
```

### 3. Interactividad

#### API de Comunicación
```javascript
// Comunicación con el sistema SapiensIA
if (window.sapiensAPI) {
    // Enviar progreso
    window.sapiensAPI.updateProgress({
        completed: true,
        score: 85,
        timeSpent: 120
    });
    
    // Solicitar pista
    window.sapiensAPI.requestHint({
        context: 'question_1',
        difficulty: 'medium'
    });
    
    // Reportar error
    window.sapiensAPI.reportError({
        type: 'validation',
        message: 'Respuesta inválida'
    });
}
```

#### Manejo de Estados
```javascript
class ActivityState {
    constructor() {
        this.currentStep = 0;
        this.answers = {};
        this.startTime = Date.now();
        this.attempts = 0;
    }
    
    saveState() {
        localStorage.setItem('activity_state', JSON.stringify(this));
    }
    
    loadState() {
        const saved = localStorage.getItem('activity_state');
        if (saved) {
            Object.assign(this, JSON.parse(saved));
        }
    }
}
```

### 4. Performance

#### Optimización de Assets
```html
<!-- Lazy loading para imágenes -->
<img data-sapiens-asset="large_image" 
     loading="lazy" 
     alt="Descripción" />

<!-- Preload para recursos críticos -->
<link rel="preload" 
      href="{{critical_font}}" 
      as="font" 
      type="font/woff2" 
      crossorigin>
```

#### Minimización de JavaScript
```javascript
// Usar funciones eficientes
const debounce = (func, wait) => {
    let timeout;
    return function executedFunction(...args) {
        const later = () => {
            clearTimeout(timeout);
            func(...args);
        };
        clearTimeout(timeout);
        timeout = setTimeout(later, wait);
    };
};

// Aplicar a eventos frecuentes
const handleResize = debounce(() => {
    // Lógica de redimensionamiento
}, 250);

window.addEventListener('resize', handleResize);
```

## Integración con Contenido

### Creación de Instancias

```python
# Crear instancia de plantilla
from src.content.template_integration_service import TemplateIntegrationService

service = TemplateIntegrationService()

# Crear contenido desde plantilla
success, content_id = service.create_content_from_template(
    template_id="template_123",
    topic_id="topic_456",
    props={
        "title": "Quiz de Matemáticas",
        "difficulty": "medium",
        "question_1_text": "¿Cuánto es 2 + 2?",
        "question_1_option_1": "3",
        "question_1_option_2": "4",
        "question_1_option_3": "5",
        "question_1_correct": 2
    },
    assets=[
        {
            "name": "main_image",
            "url": "https://example.com/image.jpg",
            "type": "image"
        }
    ],
    learning_mix={
        "V": 40,  # Visual
        "A": 20,  # Auditivo
        "K": 30,  # Kinestésico
        "R": 10   # Lectura/Escritura
    }
)
```

### Migración de Contenido Legacy

```python
# Migrar contenido existente a plantilla
success, message = service.migrate_content_to_template(
    content_id="content_789",
    template_id="template_123"
)

if success:
    print(f"Contenido migrado exitosamente: {message}")
else:
    print(f"Error en migración: {message}")
```

## Personalización y Mix VARK

### Configuración de Mix de Aprendizaje

```python
# Mix VARK para diferentes tipos de aprendizaje
mix_visual = {
    "V": 60,  # Énfasis en elementos visuales
    "A": 15,  # Mínimo audio
    "K": 20,  # Interactividad moderada
    "R": 5    # Texto mínimo
}

mix_auditivo = {
    "V": 20,  # Visuales de apoyo
    "A": 50,  # Énfasis en audio
    "K": 15,  # Interactividad básica
    "R": 15   # Texto de apoyo
}

mix_kinestesico = {
    "V": 25,  # Visuales de apoyo
    "A": 10,  # Audio mínimo
    "K": 55,  # Máxima interactividad
    "R": 10   # Texto mínimo
}

mix_lectura = {
    "V": 15,  # Visuales mínimos
    "A": 10,  # Audio mínimo
    "K": 20,  # Interactividad básica
    "R": 55   # Énfasis en texto
}
```

### Adaptación Automática

```javascript
// Adaptar plantilla según perfil del estudiante
function adaptTemplate(studentProfile, templateConfig) {
    const mix = studentProfile.learningMix;
    
    // Ajustar elementos visuales
    if (mix.V > 40) {
        document.body.classList.add('visual-enhanced');
        showMoreImages();
    }
    
    // Ajustar elementos auditivos
    if (mix.A > 40) {
        enableAudioNarration();
        addSoundEffects();
    }
    
    // Ajustar interactividad
    if (mix.K > 40) {
        enableDragAndDrop();
        addMoreInteractions();
    }
    
    // Ajustar contenido textual
    if (mix.R > 40) {
        showDetailedExplanations();
        addReadingMaterials();
    }
}
```

## Troubleshooting

### Problemas Comunes

#### 1. Marcadores No Reconocidos
```html
<!-- ❌ Incorrecto -->
<div data-sapiens-param="title">Título</div>

<!-- ✅ Correcto -->
<div data-sapiens-param="title">Título por defecto</div>
```

#### 2. Assets No Cargados
```html
<!-- ❌ Incorrecto -->
<img src="data-sapiens-asset='image'" />

<!-- ✅ Correcto -->
<img data-sapiens-asset="image" alt="Descripción" />
```

#### 3. JavaScript No Funcional
```javascript
// ❌ Incorrecto - usar parámetros directamente
const title = data-sapiens-param="title";

// ✅ Correcto - usar sistema de reemplazo
const title = "{{title}}";
```

### Debugging

#### Validación de Plantilla
```javascript
// Función de debug para validar marcadores
function debugTemplate() {
    const params = document.querySelectorAll('[data-sapiens-param]');
    const assets = document.querySelectorAll('[data-sapiens-asset]');
    const slots = document.querySelectorAll('[data-sapiens-slot]');
    
    console.log('Parámetros encontrados:', params.length);
    console.log('Assets encontrados:', assets.length);
    console.log('Slots encontrados:', slots.length);
    
    // Verificar defaults
    const defaultsScript = document.getElementById('sapiens-defaults');
    if (defaultsScript) {
        try {
            const defaults = JSON.parse(defaultsScript.textContent);
            console.log('Defaults válidos:', defaults);
        } catch (e) {
            console.error('Error en defaults JSON:', e);
        }
    }
}

// Ejecutar en desarrollo
if (window.location.hostname === 'localhost') {
    debugTemplate();
}
```

### Logs y Monitoreo

```javascript
// Sistema de logging para plantillas
class TemplateLogger {
    static log(level, message, data = {}) {
        const logEntry = {
            timestamp: new Date().toISOString(),
            level,
            message,
            templateId: window.templateId,
            instanceId: window.instanceId,
            data
        };
        
        console[level](message, logEntry);
        
        // Enviar a sistema de monitoreo
        if (window.sapiensAPI) {
            window.sapiensAPI.log(logEntry);
        }
    }
    
    static error(message, error) {
        this.log('error', message, { error: error.toString() });
    }
    
    static info(message, data) {
        this.log('info', message, data);
    }
}

// Uso
TemplateLogger.info('Template initialized', { version: '1.0.0' });
TemplateLogger.error('Failed to load asset', new Error('Network error'));
```

---

## Conclusión

Este sistema de plantillas proporciona una base sólida para crear contenido educativo interactivo y personalizable. Siguiendo estas guías y convenciones, los desarrolladores pueden crear plantillas robustas, reutilizables y adaptables a diferentes contextos educativos.

Para más información, consultar:
- [Documentación de API](./api_documentation.md)
- [Implementación Final](./implementacion_final.md)
- Ejemplos en `src/content/template_examples.py`