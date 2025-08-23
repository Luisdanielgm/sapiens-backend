# Guía de Implementación: API de Reinforcement Learning para SapiensAI

## 1. Introducción

Este documento describe la arquitectura y el plan de implementación para una API de Reinforcement Learning (RL) dedicada a la personalización de contenido en SapiensAI. Esta API funcionará como un servicio externo, alojado en un Virtual Private Server (VPS), para superar las limitaciones de backend de Vercel y permitir un procesamiento computacional intensivo.

El propósito de esta guía es proporcionar todos los detalles técnicos necesarios para construir e integrar esta API. Se asume que la implementación de los endpoints y la lógica de negocio en el backend de SapiensAI para consumir esta API queda a discreción del equipo de desarrollo.

## 2. Arquitectura General

El sistema se compondrá de dos servicios principales que se comunican a través de una API REST:

1.  **SapiensAI Backend (Vercel)**: La aplicación principal que gestiona la lógica de negocio, los datos de los usuarios y el contenido.
2.  **RL API (VPS)**: Un microservicio especializado en Python/Flask que alberga el modelo de RL, gestiona su entrenamiento y sirve las recomendaciones.

**Flujo de comunicación:**
-   Cuando SapiensAI necesita personalizar contenido para un estudiante, realiza una llamada a la `RL API` enviando el estado actual del estudiante.
-   La `RL API` procesa la información, utiliza el modelo de RL para decidir la mejor acción (qué tipo de contenido mostrar) y devuelve la recomendación.
-   Después de que el estudiante interactúa con el contenido, SapiensAI envía los resultados (`ContentResult`) a la `RL API` para que el modelo pueda aprender y actualizarse (entrenamiento incremental).

## 3. Stack Tecnológico Recomendado (VPS)

-   **Lenguaje**: Python 3.9+
-   **Framework API**: Flask o FastAPI (FastAPI es recomendado por su rendimiento y validación de datos automática con Pydantic).
-   **Cálculo Numérico**: NumPy, Pandas.
-   **Machine Learning**: Scikit-learn (para algoritmos base), o una librería de RL ligera.
-   **Cache en Memoria**: Redis (para almacenar temporalmente estados y predicciones).
-   **Servidor Web**: Gunicorn + Nginx.
-   **Sistema Operativo**: Linux (Ubuntu 22.04 LTS recomendado).

Un VPS con 4GB de RAM y 2 vCPU es suficiente para la fase inicial.

## 4. Modelo de Datos y Endpoints de la API

La `RL API` expondrá dos endpoints principales:

### Endpoint 1: Obtener Recomendación

-   **URL**: `POST /recommendation`
-   **Descripción**: Solicita una recomendación de contenido personalizada para un estudiante.
-   **Llamado por**: `sapiens-backend` justo antes de generar un nuevo módulo virtual o actividad para un estudiante. Reemplaza la lógica actual en `AdaptiveLearningService`.

**Request Body (`application/json`):**
```json
{
  "student_id": "string", // ID único del estudiante
  "session_context": { // Información del contexto actual
    "subject_id": "string",
    "topic_id": "string",
    "current_difficulty": "float" // Dificultad del último contenido, si aplica
  },
  "cognitive_profile": { // Perfil cognitivo actual del estudiante
    "learning_style": { // Ejemplo: VARK
      "visual": "float",
      "auditory": "float",
      "reading_writing": "float",
      "kinesthetic": "float"
    },
    "preferences": { // Preferencias actuales (leídas del perfil)
      "preferred_content_types": ["string"],
      "avoided_content_types": ["string"]
    }
  },
  "recent_history": [ // Opcional: últimos N ContentResult para un contexto más rico
    {
      "content_type": "string",
      "score": "float", // 0-1
      "engagement": "float", // 0-1
      "completion_rate": "float", // 0-1
      "attempts": "integer"
    }
  ]
}
```
*Análisis de Viabilidad*: El backend de SapiensAI tiene acceso a todos estos datos. `student_id` es trivial. El `cognitive_profile` se encuentra en la colección de perfiles. El `session_context` y `recent_history` (`ContentResult`) pueden ser recuperados por los servicios existentes (`ContentResultService`).

**Response Body (`application/json`):**
```json
{
  "recommended_action": {
    "content_type": "string", // e.g., 'video', 'quiz', 'interactive_simulation'
    "difficulty_adjustment": "float", // e.g., -0.1 (más fácil), 0.0 (igual), 0.1 (más difícil)
    "learning_methodology": "string" // e.g., 'gamification', 'project_based'
  },
  "prediction_id": "string", // Un ID único para esta predicción, para enlazarla con el feedback
  "confidence": "float" // Confianza del modelo en esta recomendación
}
```

### Endpoint 2: Enviar Feedback

-   **URL**: `POST /feedback`
-   **Descripción**: Envía el resultado de la interacción de un estudiante con un contenido para entrenar el modelo.
-   **Llamado por**: `sapiens-backend` después de que un `ContentResult` es creado o actualizado.

**Request Body (`application/json`):**
```json
{
  "prediction_id": "string", // El ID recibido en /recommendation
  "content_result": {
    "student_id": "string",
    "content_id": "string",
    "content_type": "string",
    "score": "float", // 0-1
    "feedback": "string", // Opcional: feedback textual del usuario
    "metrics": {
      "time_spent_seconds": "integer",
      "engagement": "float", // 0-1
      "completion_rate": "float", // 0-1
      "attempts": "integer",
      "difficulty": "float" // Dificultad objetiva del contenido
    }
  }
}
```
*Análisis de Viabilidad*: El modelo `ContentResult` en `src/content/models.py` contiene todos estos campos. El `ContentResultService` puede proveer estos datos fácilmente.

**Response Body (`application/json`):**
```json
{
  "status": "success",
  "message": "Feedback received and model update queued."
}
```

## 5. Algoritmo de Reinforcement Learning

Se propone un enfoque híbrido: un **modelo global** que aprende de todos los estudiantes, pero que se personaliza en tiempo real usando el **estado individual** de cada estudiante.

### Algoritmo Propuesto: Contextual Multi-Armed Bandit (Fase 1)

Este es un punto de partida excelente por su eficiencia y simplicidad.

-   **Contexto (Estado)**: El input del `POST /recommendation`. Es un vector que combina el perfil cognitivo, el contexto de la sesión y el historial reciente.
-   **Brazos (Arms)**: Las posibles acciones a tomar. Cada "brazo" es una combinación de `(content_type, difficulty_adjustment)`.
-   **Recompensa**: Una función calculada a partir del `ContentResult` recibido en `POST /feedback`.

## 5. Aprovechamiento del Perfil Cognitivo en el Modelo RL

El modelo RL puede aprovechar la información detallada del perfil cognitivo de múltiples maneras para mejorar significativamente la personalización:

### 4.1. Uso de Porcentajes de Learning Style

Los porcentajes de tipos de aprendizaje (visual, auditory, reading_writing, kinesthetic) se pueden usar para:

- **Ponderación de Recomendaciones**: Asignar mayor peso a contenidos que coincidan con el estilo predominante
- **Diversificación Inteligente**: Incluir ocasionalmente contenido de estilos secundarios para desarrollo integral
- **Adaptación Dinámica**: Ajustar las recomendaciones basándose en el rendimiento observado

```python
def calculate_learning_style_score(content_type, learning_style_percentages):
    # Mapeo de tipos de contenido a estilos de aprendizaje
    content_style_mapping = {
        'slides': {'visual': 0.8, 'reading_writing': 0.6},
        'video': {'visual': 0.9, 'auditory': 0.7},
        'quiz': {'reading_writing': 0.8, 'kinesthetic': 0.5},
        'simulation': {'kinesthetic': 0.9, 'visual': 0.6}
    }
    
    score = 0
    for style, weight in content_style_mapping.get(content_type, {}).items():
        score += (learning_style_percentages.get(style, 0) / 100) * weight
    
    return score
```

### 4.2. Consideración de Diagnósticos

Los diagnósticos específicos (ej. dislexia, TDAH) permiten:

- **Adaptaciones Específicas**: Aplicar estrategias conocidas para cada condición
- **Filtrado de Contenido**: Evitar formatos que puedan ser problemáticos
- **Tiempo Personalizado**: Ajustar duración estimada según las necesidades

### 4.3. Uso de Fortalezas y Dificultades Cognitivas

- **Fortalezas**: Aprovechar áreas fuertes para introducir conceptos complejos
- **Dificultades**: Proporcionar apoyo adicional y contenido adaptado
- **Progresión Gradual**: Construir desde fortalezas hacia áreas de mejora

### 4.4. Estrategias Recomendadas

Las estrategias con su efectividad pueden usarse para:

- **Priorización**: Aplicar estrategias con mayor efectividad primero
- **Combinación**: Usar múltiples estrategias complementarias
- **Evaluación**: Medir si las estrategias están funcionando

**Función de Recompensa Enriquecida con Rendimiento Histórico:**
```python
def calculate_reward(metrics, cognitive_profile, content_info, student_id=None):
    score = metrics.get('score', 0)  # 0-1
    completion_time = metrics.get('completion_time', 0)  # segundos
    interaction_count = metrics.get('interaction_count', 1)
    content_type = content_info.get('content_type', '')
    
    # Recompensa base por el score (reducida para dar espacio a mejora histórica)
    reward = score * 0.8
    
    # Factor de estilo de aprendizaje
    learning_style_score = calculate_learning_style_score(
        content_type, 
        cognitive_profile.get('learning_style', {})
    )
    reward += learning_style_score * 0.15  # Reducido de 0.2 a 0.15
    
    # Consideración de diagnósticos
    diagnosis = cognitive_profile.get('diagnosis', [])
    if 'dislexia_leve' in diagnosis and content_type == 'text_heavy':
        reward -= 0.3  # Penalización por contenido no adecuado
    
    # Factor de dificultades cognitivas
    difficulties = cognitive_profile.get('cognitive_difficulties', [])
    if 'procesamiento_textual_rapido' in difficulties:
        if completion_time > 0 and completion_time < 600:  # Completado rápido
            reward += 0.1  # Bonificación por adaptación exitosa
    
    # Factor de fortalezas cognitivas
    strengths = cognitive_profile.get('cognitive_strengths', [])
    if 'pensamiento_visual' in strengths and content_type in ['slides', 'video']:
        reward += 0.15  # Bonificación por aprovechar fortalezas
    
    # Penalización por tiempo excesivo
    expected_time = content_info.get('estimated_duration', 900)  # 15 min default
    if completion_time > expected_time * 2:
        reward -= 0.2
    
    # Bonificación por alta interacción (engagement)
    if interaction_count > 5:
        reward += 0.1
    
    # Factor de estrategias aplicadas
    applied_strategies = metrics.get('applied_strategies', [])
    recommended_strategies = cognitive_profile.get('recommended_strategies', [])
    
    for strategy in applied_strategies:
        for rec_strategy in recommended_strategies:
            if strategy == rec_strategy.get('strategy'):
                effectiveness = rec_strategy.get('effectiveness', 0.5)
                reward += effectiveness * 0.1
    
    # NUEVO: Factor de mejora respecto al rendimiento histórico
    if student_id:
        historical_improvement = calculate_historical_improvement_reward(
            student_id, content_type, score, metrics
        )
        reward += historical_improvement * 0.2  # 20% del peso total
    
    return max(0, min(1, reward))  # Clamp entre 0 y 1

def calculate_historical_improvement_reward(student_id, content_type, current_score, metrics):
    """
    Calcula recompensa adicional basada en la mejora respecto al rendimiento histórico
    """
    try:
        performance_metrics = get_student_performance_metrics(student_id)
        content_metrics = performance_metrics.content_type_performance.get(content_type, {})
        
        # Si no hay historial suficiente, dar recompensa neutral
        if content_metrics.get('total_interactions', 0) < 2:
            return 0.5  # Recompensa neutral para nuevos tipos de contenido
        
        # Comparar con rendimiento histórico promedio
        historical_avg_score = content_metrics.get('avg_score', 0.5)
        historical_success_rate = content_metrics.get('success_rate', 0.5)
        
        # Calcular mejora en puntuación
        score_improvement = (current_score - historical_avg_score) / max(historical_avg_score, 0.1)
        score_improvement = max(-1.0, min(1.0, score_improvement))  # Clamp entre -1 y 1
        
        # Calcular mejora en tasa de éxito
        current_success = 1.0 if current_score >= 0.7 else 0.0
        success_improvement = current_success - historical_success_rate
        
        # Bonificación por consistencia (si ya tenía buen rendimiento y lo mantiene)
        consistency_bonus = 0.0
        if historical_avg_score >= 0.8 and current_score >= 0.8:
            consistency_bonus = 0.3  # Bonifica mantener alto rendimiento
        
        # Bonificación extra por superar dificultades históricas
        breakthrough_bonus = 0.0
        if historical_success_rate < 0.5 and current_score >= 0.8:
            breakthrough_bonus = 0.5  # Gran bonificación por superar dificultades
        
        # Combinar factores de mejora
        improvement_reward = (
            score_improvement * 0.4 +
            success_improvement * 0.4 +
            consistency_bonus * 0.1 +
            breakthrough_bonus * 0.1
        )
        
        # Normalizar entre 0 y 1
        return max(0.0, min(1.0, (improvement_reward + 1.0) / 2.0))
        
    except Exception as e:
        print(f"Error calculando mejora histórica: {e}")
        return 0.5  # Fallback a recompensa neutral
```

### Evolución a Q-Learning (Fase 2)

Una vez que el sistema madure, se puede evolucionar a un modelo de Q-Learning para capturar secuencias de aprendizaje.

-   **Estado (State)**: Similar al contexto del bandit, pero puede ser discretizado para formar una Q-table.
-   **Acción (Action)**: Las mismas acciones.
-   **Q-table**: Una tabla que mapea `(estado, acción)` a un valor Q (la recompensa futura esperada).
-   **Ecuación de Bellman** para las actualizaciones.

## 6. Estrategia de Entrenamiento

El entrenamiento no es un evento único y masivo. Es un proceso continuo y ligero.

1.  **Entrenamiento en Tiempo Real (Online)**: Cada vez que se recibe un feedback (`POST /feedback`), el modelo se actualiza inmediatamente. Esta operación debe ser muy rápida (< 10ms). Para un bandit, es una simple actualización de los pesos del brazo elegido. Para Q-Learning, es actualizar un valor en la Q-table.
2.  **Consolidación por Lotes (Batch)**: Periódicamente (ej. cada hora), se pueden re-evaluar las actualizaciones recientes en un lote para estabilizar el aprendizaje.
3.  **Re-entrenamiento Profundo (Offline)**: Con menos frecuencia (ej. una vez al día o a la semana), se puede ejecutar un proceso de entrenamiento más profundo sobre todo el historial de datos para corregir derivas del modelo y encontrar patrones a largo plazo. Este proceso puede durar de 15 a 60 minutos.

**La predicción (`/recommendation`) siempre usa el modelo más actualizado y nunca se detiene por el entrenamiento.**

## 6.1. Aprendizaje Adaptativo Basado en Rendimiento

### Principio Fundamental

El modelo RL debe **aprender dinámicamente** de los resultados reales del estudiante, ajustando sus pesos y preferencias según el rendimiento observado. **Los tipos de contenido donde el estudiante demuestra mejor aprendizaje deben ser recomendados con mayor frecuencia.**

### Métricas de Rendimiento Clave

El modelo rastrea las siguientes métricas para cada tipo de contenido:

```python
class PerformanceMetrics:
    def __init__(self):
        self.content_type_performance = {
            'slides': {
                'success_rate': 0.0,      # % de contenidos completados exitosamente
                'avg_score': 0.0,         # Puntuación promedio obtenida
                'engagement_score': 0.0,  # Nivel de interacción promedio
                'completion_time_ratio': 0.0,  # Tiempo real vs tiempo estimado
                'total_interactions': 0,  # Número total de interacciones
                'weight': 0.25           # Peso inicial (se ajusta dinámicamente)
            },
            'quiz': {
                'success_rate': 0.0,
                'avg_score': 0.0,
                'engagement_score': 0.0,
                'completion_time_ratio': 0.0,
                'total_interactions': 0,
                'weight': 0.25
            },
            'video': {
                'success_rate': 0.0,
                'avg_score': 0.0,
                'engagement_score': 0.0,
                'completion_time_ratio': 0.0,
                'total_interactions': 0,
                'weight': 0.25
            },
            'interactive': {
                'success_rate': 0.0,
                'avg_score': 0.0,
                'engagement_score': 0.0,
                'completion_time_ratio': 0.0,
                'total_interactions': 0,
                'weight': 0.25
            }
        }
```

### Algoritmo de Ajuste de Pesos Dinámico

Cada vez que se recibe feedback, el modelo actualiza los pesos según el rendimiento:

```python
def update_content_type_weights(student_id, content_type, feedback_data):
    """
    Actualiza los pesos de tipos de contenido basándose en el rendimiento real
    """
    metrics = get_student_performance_metrics(student_id)
    
    # Calcular nueva métrica de rendimiento
    success = 1.0 if feedback_data['score'] >= 0.7 else 0.0
    engagement = calculate_engagement_score(feedback_data)
    time_efficiency = calculate_time_efficiency(feedback_data)
    
    # Actualizar métricas acumulativas
    current_metrics = metrics.content_type_performance[content_type]
    n = current_metrics['total_interactions']
    
    # Media móvil ponderada (da más peso a interacciones recientes)
    alpha = 0.3  # Factor de aprendizaje
    current_metrics['success_rate'] = (1 - alpha) * current_metrics['success_rate'] + alpha * success
    current_metrics['avg_score'] = (1 - alpha) * current_metrics['avg_score'] + alpha * feedback_data['score']
    current_metrics['engagement_score'] = (1 - alpha) * current_metrics['engagement_score'] + alpha * engagement
    current_metrics['completion_time_ratio'] = (1 - alpha) * current_metrics['completion_time_ratio'] + alpha * time_efficiency
    current_metrics['total_interactions'] += 1
    
    # Calcular nuevo peso basado en rendimiento combinado
    performance_score = (
        current_metrics['success_rate'] * 0.4 +
        current_metrics['avg_score'] * 0.3 +
        current_metrics['engagement_score'] * 0.2 +
        current_metrics['completion_time_ratio'] * 0.1
    )
    
    # Ajustar peso con suavizado
    current_metrics['weight'] = (1 - alpha) * current_metrics['weight'] + alpha * performance_score
    
    # Normalizar pesos para que sumen 1.0
    normalize_weights(metrics.content_type_performance)
    
    # Persistir métricas actualizadas
    save_student_performance_metrics(student_id, metrics)
    
    return metrics

def normalize_weights(content_performance):
    """
    Normaliza los pesos para que sumen 1.0
    """
    total_weight = sum(cp['weight'] for cp in content_performance.values())
    if total_weight > 0:
        for cp in content_performance.values():
            cp['weight'] /= total_weight
    else:
        # Fallback: pesos iguales
        equal_weight = 1.0 / len(content_performance)
        for cp in content_performance.values():
            cp['weight'] = equal_weight
```

### Recomendación Basada en Rendimiento

El algoritmo de recomendación utiliza los pesos dinámicos:

```python
def get_content_recommendation_with_performance(student_id, available_content, cognitive_profile):
    """
    Recomienda contenido priorizando tipos donde el estudiante tiene mejor rendimiento
    """
    metrics = get_student_performance_metrics(student_id)
    
    scored_content = []
    for content in available_content:
        content_type = content['content_type']
        
        # Score base del perfil cognitivo
        cognitive_score = calculate_cognitive_alignment_score(content, cognitive_profile)
        
        # Score de rendimiento histórico (peso dinámico)
        performance_weight = metrics.content_type_performance[content_type]['weight']
        
        # Score combinado (60% rendimiento histórico + 40% perfil cognitivo)
        combined_score = (performance_weight * 0.6) + (cognitive_score * 0.4)
        
        # Bonificación por alta tasa de éxito en este tipo de contenido
        success_rate = metrics.content_type_performance[content_type]['success_rate']
        if success_rate > 0.8:
            combined_score *= 1.2  # Bonificación del 20%
        
        # Penalización por bajo rendimiento histórico
        if success_rate < 0.3 and metrics.content_type_performance[content_type]['total_interactions'] > 3:
            combined_score *= 0.7  # Penalización del 30%
        
        scored_content.append({
            'content': content,
            'score': combined_score,
            'performance_weight': performance_weight,
            'cognitive_score': cognitive_score,
            'success_rate': success_rate
        })
    
    # Ordenar por score combinado (descendente)
    scored_content.sort(key=lambda x: x['score'], reverse=True)
    
    return scored_content[0]['content']  # Retornar el mejor contenido
```

### Ejemplo de Evolución de Pesos

**Escenario**: Estudiante con perfil visual (75%) pero que demuestra mejor rendimiento en contenido interactivo.

```python
# Estado inicial (basado solo en perfil cognitivo)
initial_weights = {
    'slides': 0.35,      # Alto por preferencia visual
    'video': 0.30,       # Alto por preferencia visual  
    'interactive': 0.20, # Medio
    'quiz': 0.15         # Bajo
}

# Después de 10 interacciones con feedback real
evolved_weights = {
    'interactive': 0.45, # ↑ Mejor rendimiento observado (85% éxito)
    'slides': 0.30,      # ↓ Rendimiento moderado (70% éxito)
    'video': 0.15,       # ↓ Bajo engagement observado (50% éxito)
    'quiz': 0.10         # ↓ Dificultades consistentes (30% éxito)
}

# El modelo ahora recomienda más contenido interactivo
# a pesar de que el perfil inicial sugería preferencia visual
```

### Beneficios del Aprendizaje Adaptativo

1. **Personalización Real**: Se basa en datos reales de rendimiento, no solo en perfiles estáticos
2. **Mejora Continua**: El modelo se vuelve más preciso con cada interacción
3. **Adaptación a Cambios**: Puede detectar cambios en las preferencias o habilidades del estudiante
4. **Optimización de Resultados**: Maximiza la probabilidad de éxito del estudiante
5. **Detección de Patrones**: Identifica tipos de contenido más efectivos para cada estudiante

### Ejemplos de Rastreo de Rendimiento

#### Ejemplo 1: Estudiante que Mejora en Videos

```python
# Historial de interacciones con videos
video_interactions = [
    {'score': 0.4, 'engagement': 0.3, 'completion_time_ratio': 1.8, 'timestamp': '2024-01-01'},
    {'score': 0.5, 'engagement': 0.4, 'completion_time_ratio': 1.6, 'timestamp': '2024-01-03'},
    {'score': 0.7, 'engagement': 0.6, 'completion_time_ratio': 1.2, 'timestamp': '2024-01-05'},
    {'score': 0.8, 'engagement': 0.8, 'completion_time_ratio': 1.0, 'timestamp': '2024-01-07'},
    {'score': 0.9, 'engagement': 0.9, 'completion_time_ratio': 0.9, 'timestamp': '2024-01-09'}
]

# Evolución del peso para videos
weight_evolution = {
    'initial': 0.20,  # Peso inicial bajo (perfil kinestésico)
    'after_2_interactions': 0.18,  # Disminuye por bajo rendimiento
    'after_3_interactions': 0.22,  # Empieza a mejorar
    'after_4_interactions': 0.28,  # Mejora significativa
    'after_5_interactions': 0.35   # Peso alto por excelente rendimiento
}

# El modelo ahora recomienda más videos a pesar del perfil inicial
```

#### Ejemplo 2: Detección de Dificultades Persistentes

```python
# Estudiante con dificultades consistentes en quizzes
quiz_performance = {
    'total_interactions': 8,
    'success_rate': 0.25,  # Solo 25% de éxito
    'avg_score': 0.45,     # Puntuación promedio baja
    'engagement_score': 0.3,  # Bajo engagement
    'weight': 0.08         # Peso muy reducido
}

# Acción del modelo: Reducir recomendaciones de quiz y sugerir contenido preparatorio
recommendation_strategy = {
    'quiz_frequency': 'muy_baja',  # Solo 8% de recomendaciones
    'preparatory_content': 'alta_prioridad',  # Slides explicativos primero
    'alternative_assessment': 'interactive',  # Usar contenido interactivo para evaluación
    'remedial_action': 'suggest_tutor_support'  # Sugerir apoyo adicional
}
```

#### Ejemplo 3: Adaptación a Cambios en Preferencias

```python
# Estudiante que inicialmente prefería slides pero ahora mejora con interactivos
learning_evolution = {
    'week_1_4': {
        'slides': {'weight': 0.45, 'success_rate': 0.8},
        'interactive': {'weight': 0.15, 'success_rate': 0.4}
    },
    'week_5_8': {
        'slides': {'weight': 0.35, 'success_rate': 0.7},  # Ligera disminución
        'interactive': {'weight': 0.25, 'success_rate': 0.6}  # Mejora gradual
    },
    'week_9_12': {
        'slides': {'weight': 0.25, 'success_rate': 0.65},
        'interactive': {'weight': 0.40, 'success_rate': 0.85}  # Ahora es el preferido
    }
}

# El modelo detecta y se adapta al cambio de preferencias
```

### Métricas de Evaluación del Modelo

```python
class ModelPerformanceMetrics:
    def __init__(self):
        self.metrics = {
            'recommendation_accuracy': 0.0,  # % de recomendaciones que resultan en éxito
            'learning_improvement_rate': 0.0,  # Tasa de mejora del estudiante
            'engagement_increase': 0.0,  # Aumento en engagement promedio
            'content_type_optimization': 0.0,  # Qué tan bien optimiza tipos de contenido
            'adaptation_speed': 0.0,  # Qué tan rápido se adapta a cambios
            'exploration_effectiveness': 0.0  # Efectividad de recomendaciones exploratorias
        }
    
    def calculate_recommendation_accuracy(self, student_id, time_period_days=30):
        """
        Calcula qué porcentaje de recomendaciones resultaron en interacciones exitosas
        """
        recommendations = get_student_recommendations(student_id, time_period_days)
        successful_interactions = 0
        total_recommendations = len(recommendations)
        
        for rec in recommendations:
            interaction = get_interaction_result(rec['content_id'], student_id)
            if interaction and interaction['score'] >= 0.7:
                successful_interactions += 1
        
        return successful_interactions / max(total_recommendations, 1)
    
    def calculate_learning_improvement_rate(self, student_id, time_period_days=30):
        """
        Calcula la tasa de mejora en el rendimiento del estudiante
        """
        interactions = get_student_interactions(student_id, time_period_days)
        if len(interactions) < 5:
            return 0.0
        
        # Dividir en primera y segunda mitad del período
        mid_point = len(interactions) // 2
        first_half_avg = sum(i['score'] for i in interactions[:mid_point]) / mid_point
        second_half_avg = sum(i['score'] for i in interactions[mid_point:]) / (len(interactions) - mid_point)
        
        improvement_rate = (second_half_avg - first_half_avg) / max(first_half_avg, 0.1)
        return max(-1.0, min(1.0, improvement_rate))
```

### Consideraciones de Implementación

- **Período de Adaptación**: Usar al menos 5-10 interacciones antes de confiar completamente en los pesos dinámicos
- **Balanceo Exploración/Explotación**: Mantener un 10-20% de recomendaciones exploratorias para descubrir nuevos patrones
- **Degradación Temporal**: Dar más peso a interacciones recientes (últimas 2-4 semanas)
- **Mínimo de Datos**: Requerir al menos 3 interacciones por tipo de contenido antes de ajustar pesos significativamente
- **Detección de Anomalías**: Identificar cambios súbitos en rendimiento que puedan indicar factores externos
- **Intervención Humana**: Alertar a educadores cuando el modelo detecta dificultades persistentes

## 7. Gestión de Datos y Persistencia en el VPS

El VPS necesita almacenar los artefactos del modelo y los logs.

**Estructura de Directorios Sugerida:**
```
/opt/sapiens-rl/
├── app.py             # Lógica de la API Flask/FastAPI
├── models/            # Modelos de RL persistidos
│   ├── contextual_bandit.pkl
│   └── q_table.npy
├── logs/              # Logs de la aplicación
│   ├── access.log
│   └── error.log
└── data/              # Historial de datos para re-entrenamiento
    └── feedback_history.csv
```

-   **Modelos**: El estado del modelo (pesos del bandit, Q-table) debe ser persistido en disco regularmente (ej. después de cada lote de actualizaciones) para evitar perder el aprendizaje si el servicio se reinicia. Se pueden usar `pickle` o `joblib`.
-   **Logs**: Usar rotación de logs (`logrotate`) para evitar que los archivos de log consuman todo el espacio en disco.
-   **Backups**: Configurar un cron job para realizar backups diarios de la carpeta `models/` y `data/` a una ubicación segura (ej. un bucket S3).

## 8. Consideraciones de Implementación

-   **Cold Start**: Para un estudiante nuevo, el modelo no tiene datos. Estrategias:
    1.  **Exploración Inicial**: Recomendar acciones aleatorias o las más populares globalmente durante las primeras N interacciones.
    2.  **Perfil Inicial**: Usar el perfil cognitivo inicial del estudiante para una primera recomendación basada en reglas simples.
-   **Seguridad**: Proteger los endpoints de la API con una clave de API (`X-API-KEY` en los headers) que solo conozcan el backend de SapiensAI y la RL API.
-   **Monitoreo**: Implementar un endpoint `/health` para verificar el estado del servicio. Monitorear el uso de CPU, RAM y disco del VPS. Registrar métricas clave como el tiempo de predicción y la recompensa promedio.


## Anexo: Datos Reales de Prueba para Testing

### Datos Reales Extraídos de la Base de Datos

Para facilitar las pruebas del RL API en el VPS, se proporcionan los siguientes datos reales extraídos de la base de datos de SapiensAI del usuario 'aiequipodigital@gmail.com':

#### 1. Perfil Cognitivo Completo (CognitiveProfile)

El modelo RL puede aprovechar información detallada del perfil cognitivo para personalizar mejor las recomendaciones. El modelo `CognitiveProfile` incluye los siguientes campos:

**Campos del Perfil Cognitivo:**
- **learning_style**: Diccionario con porcentajes (0-100) para cada tipo de aprendizaje:
  - `visual`: Aprendizaje visual (gráficos, diagramas, imágenes)
  - `auditory`: Aprendizaje auditivo (explicaciones verbales, música)
  - `reading_writing`: Aprendizaje lectoescritor (textos, notas)
  - `kinesthetic`: Aprendizaje kinestésico (práctica, movimiento)
- **diagnosis**: Lista de diagnósticos específicos (ej. dislexia, TDAH)
- **cognitive_strengths**: Lista de fortalezas cognitivas identificadas
- **cognitive_difficulties**: Lista de dificultades cognitivas identificadas
- **personal_context**: Contexto personal que afecta el aprendizaje
- **recommended_strategies**: Estrategias recomendadas específicas
- **profile**: Campo adicional para representación JSON completa

#### Ejemplo de Perfil Cognitivo Enriquecido

```json
{
  "_id": "67d8634d841411d3638cf9f3",
  "user_id": "67d8634d841411d3638cf9f1",
  "learning_style": {
    "visual": 75,
    "auditory": 45,
    "reading_writing": 60,
    "kinesthetic": 30
  },
  "diagnosis": ["dislexia_leve"],
  "cognitive_strengths": [
    "pensamiento_visual",
    "resolución_problemas",
    "creatividad"
  ],
  "cognitive_difficulties": [
    "procesamiento_textual_rapido",
    "memoria_trabajo_verbal"
  ],
  "personal_context": {
    "educational_background": "Licenciado en Ciencias y Artes Militares",
    "interests": ["Tecnología", "música"],
    "preferred_learning_style": "visual",
    "motivation_level": "high",
    "available_study_time": "2-3_hours_daily"
  },
  "recommended_strategies": [
    {
      "strategy": "visual_content_priority",
      "description": "Priorizar contenido visual y diagramático",
      "effectiveness": 0.85
    },
    {
      "strategy": "chunked_text_presentation",
      "description": "Presentar texto en fragmentos pequeños",
      "effectiveness": 0.70
    }
  ],
  "created_at": "2025-03-17T18:00:45.048000",
  "updated_at": "2025-04-30T15:24:12.627000",
  "user": {
    "name": "AITEAM DIGITAL",
    "email": "aiequipodigital@gmail.com",
    "picture": "https://lh3.googleusercontent.com/a/ACg8ocLJT5TTZPIZoTNqZYGqNfKWW9EUJrSjm5MzHNjV4s1RfmkWNg=s96-c"
  }
}
```

#### 2. Historial de Interacciones Reales (ContentResult)

```json
[
  {
    "_id": "68965bd01b0cbaa44630e8bc",
    "content_id": "689461f0bdb2a9494687753f",
    "student_id": "67d8634d841411d3638cf9f1",
    "score": 1.0,
    "feedback": "Contenido completado automáticamente",
    "metrics": {
      "content_type": "slides",
      "virtual_content_id": "68962761f0ac59f9c7ff9070",
      "auto_completed": true,
      "completion_time": 0,
      "interaction_count": 1,
      "personalization_applied": true
    },
    "session_type": "auto_completion",
    "recorded_at": "2025-08-08T20:19:28.694000"
  },
  {
    "_id": "68965e59e9a3cd2881eaaa56",
    "content_id": "6894441b2eb4213d8959b7f9",
    "student_id": "67d8634d841411d3638cf9f1",
    "score": 0.0,
    "feedback": "Contenido completado automáticamente",
    "metrics": {
      "content_type": "quiz",
      "virtual_content_id": "68962761f0ac59f9c7ff9071",
      "auto_completed": true,
      "completion_time": 0,
      "interaction_count": 1,
      "personalization_applied": true
    },
    "session_type": "auto_completion",
    "recorded_at": "2025-08-08T20:30:17.241000"
  },
  {
    "_id": "689df5037719435f11f23fb9",
    "content_id": "689dec077de1debba242af4b",
    "student_id": "67d8634d841411d3638cf9f1",
    "score": 1.0,
    "feedback": "Contenido completado automáticamente",
    "metrics": {
      "content_type": "slides",
      "virtual_content_id": "689df4e3764361c5d9604866",
      "auto_completed": true,
      "completion_time": 0,
      "interaction_count": 1,
      "personalization_applied": true
    },
    "session_type": "auto_completion",
    "recorded_at": "2025-08-14T14:38:59.719000"
  }
]
```

#### 3. Módulo Virtual Real (VirtualModule)

```json
{
  "_id": "68962761f0ac59f9c7ff906e",
  "study_plan_id": "6814591fa98ca4b5ee002f02",
  "module_id": "6814591fa98ca4b5ee002f03",
  "student_id": "67d8634d841411d3638cf9f1",
  "adaptations": {
    "cognitive_profile": {},
    "generation_method": "fast",
    "generated_at": "2025-08-08T16:35:45.021000"
  },
  "generated_by": "IA",
  "generation_status": "completed",
  "generation_progress": 100,
  "status": "active",
  "completion_status": "completed",
  "progress": 100,
  "completed_at": "2025-08-08T16:35:45.133000",
  "updated_at": "2025-08-14T05:36:54.611000"
}
```

### 2. Ejemplos de Peticiones a la API con Datos Reales

#### a. Petición al endpoint `/recommendation` (usando perfil cognitivo completo)

```json
{
  "student_id": "67d8634d841411d3638cf9f1",
  "cognitive_profile": {
    "learning_style": {
      "visual": 75,
      "auditory": 45,
      "reading_writing": 60,
      "kinesthetic": 30
    },
    "diagnosis": ["dislexia_leve"],
    "cognitive_strengths": [
      "pensamiento_visual",
      "resolución_problemas",
      "creatividad"
    ],
    "cognitive_difficulties": [
      "procesamiento_textual_rapido",
      "memoria_trabajo_verbal"
    ],
    "personal_context": {
      "educational_background": "Licenciado en Ciencias y Artes Militares",
      "interests": ["Tecnología", "música"],
      "preferred_learning_style": "visual",
      "motivation_level": "high",
      "available_study_time": "2-3_hours_daily"
    },
    "recommended_strategies": [
      {
        "strategy": "visual_content_priority",
        "description": "Priorizar contenido visual y diagramático",
        "effectiveness": 0.85
      },
      {
        "strategy": "chunked_text_presentation",
        "description": "Presentar texto en fragmentos pequeños",
        "effectiveness": 0.70
      }
    ],
    "user_info": {
      "name": "AITEAM DIGITAL",
      "email": "aiequipodigital@gmail.com"
    }
  },
  "interaction_history": [
    {
      "content_id": "689461f0bdb2a9494687753f",
      "score": 1.0,
      "content_type": "slides",
      "completion_time": 0,
      "interaction_count": 1,
      "completed": true,
      "auto_completed": true,
      "timestamp": "2025-08-08T20:19:28.694000"
    },
    {
      "content_id": "6894441b2eb4213d8959b7f9",
      "score": 0.0,
      "content_type": "quiz",
      "completion_time": 0,
      "interaction_count": 1,
      "completed": true,
      "auto_completed": true,
      "timestamp": "2025-08-08T20:30:17.241000"
    },
    {
      "content_id": "689dec077de1debba242af4b",
      "score": 1.0,
      "content_type": "slides",
      "completion_time": 0,
      "interaction_count": 1,
      "completed": true,
      "auto_completed": true,
      "timestamp": "2025-08-14T14:38:59.719000"
    }
  ],
  "available_content": [
    {
      "content_id": "689461f0bdb2a9494687753f",
      "content_type": "slides",
      "difficulty": "medium",
      "topic": "tecnologia_militar",
      "estimated_duration": 15
    },
    {
      "content_id": "6894441b2eb4213d8959b7f9",
      "content_type": "quiz",
      "difficulty": "easy",
      "topic": "fundamentos_tecnologia",
      "estimated_duration": 10
    },
    {
      "content_id": "689dec077de1debba242af4b",
      "content_type": "slides",
      "difficulty": "advanced",
      "topic": "sistemas_avanzados",
      "estimated_duration": 20
    }
  ]
}
```

#### b. Petición al endpoint `/feedback` (usando datos reales)

```json
{
  "student_id": "67d8634d841411d3638cf9f1",
  "content_id": "689461f0bdb2a9494687753f",
  "score": 1.0,
  "time_spent": 0,
  "completed": true,
  "interaction_details": {
    "attempts": 1,
    "hints_used": 0,
    "content_type": "slides",
    "difficulty": "medium",
    "auto_completed": true,
    "personalization_applied": true,
    "virtual_content_id": "68962761f0ac59f9c7ff9070"
  },
  "timestamp": "2025-08-08T20:19:28.694000"
 }
 ```

### 3. Archivo de Datos Completos

Todos los datos reales extraídos de la base de datos están disponibles en el archivo:

**`datos_reales_rl_api.json`**

Este archivo contiene:
- 1 usuario real del equipo AITEAM
- 1 perfil cognitivo completo
- 5 resultados de contenido (ContentResult)
- 2 módulos virtuales (VirtualModule)
- 0 planes de estudio (StudyPlan) - no se encontraron para este usuario

Estos datos pueden ser utilizados directamente para:
1. **Testing inicial** del RL API en el VPS
2. **Validación** de los endpoints `/recommendation` y `/feedback`
3. **Entrenamiento** de los modelos de RL con datos reales
4. **Benchmarking** del rendimiento del sistema

## 9. Perfil Cognitivo Enriquecido vs Básico

### 9.1. Comparación de Enfoques

| Aspecto | Perfil Básico | Perfil Enriquecido |
|---------|---------------|--------------------||
| **Información de Estilo** | Solo estilo preferido (ej. "visual") | Porcentajes detallados (visual: 75%, auditory: 45%, etc.) |
| **Diagnósticos** | No incluidos | Lista específica (dislexia, TDAH, etc.) |
| **Fortalezas/Dificultades** | No especificadas | Listas detalladas de capacidades cognitivas |
| **Estrategias** | Genéricas | Específicas con efectividad medida |
| **Personalización RL** | Básica, reglas simples | Avanzada, múltiples factores |
| **Precisión de Recomendaciones** | Moderada | Alta |
| **Adaptabilidad** | Limitada | Dinámica y contextual |

### 9.2. Beneficios del Perfil Enriquecido

#### Para el Modelo RL:
- **Mayor Precisión**: Más datos contextuales para mejores decisiones
- **Personalización Granular**: Ajustes específicos por condición/fortaleza
- **Función de Recompensa Rica**: Múltiples factores para evaluación
- **Adaptación Continua**: Aprendizaje basado en características específicas

#### Para el Estudiante:
- **Experiencia Más Personalizada**: Contenido adaptado a necesidades específicas
- **Mejor Rendimiento**: Aprovechamiento de fortalezas, apoyo en dificultades
- **Progreso Optimizado**: Rutas de aprendizaje más efectivas
- **Inclusión**: Adaptaciones para diferentes condiciones cognitivas

### 9.3. Implementación Gradual

**Fase 1: Perfil Básico**
- Usar solo `preferred_learning_style`
- Implementar recomendaciones simples
- Establecer baseline de rendimiento

**Fase 2: Perfil Intermedio**
- Agregar porcentajes de `learning_style`
- Incluir `diagnosis` básicos
- Mejorar función de recompensa

**Fase 3: Perfil Completo**
- Implementar todos los campos del `CognitiveProfile`
- Función de recompensa completa
- Estrategias personalizadas avanzadas

### 9.4. Consideraciones de Implementación

**Compatibilidad hacia atrás:**
```python
def get_learning_style_percentages(cognitive_profile):
    # Si tiene porcentajes detallados, usarlos
    if 'learning_style' in cognitive_profile and isinstance(cognitive_profile['learning_style'], dict):
        return cognitive_profile['learning_style']
    
    # Fallback: convertir estilo preferido a porcentajes
    preferred = cognitive_profile.get('preferred_learning_style', 'visual')
    return {
        'visual': 70 if preferred == 'visual' else 25,
        'auditory': 70 if preferred == 'auditory' else 25,
        'reading_writing': 70 if preferred == 'reading_writing' else 25,
        'kinesthetic': 70 if preferred == 'kinesthetic' else 25
    }
```

**Manejo de datos faltantes:**
- Valores por defecto para campos opcionales
- Degradación gradual de funcionalidad
- Logging para identificar perfiles incompletos

### 9.5. Métricas de Evaluación

Para medir la efectividad del perfil enriquecido:

- **Precisión de Recomendaciones**: Comparar tasas de éxito
- **Engagement**: Tiempo de interacción, completitud
- **Progreso de Aprendizaje**: Mejora en scores a lo largo del tiempo
- **Satisfacción**: Feedback directo del usuario
- **Adaptabilidad**: Velocidad de ajuste a nuevos patrones

---

**Nota**: Esta guía proporciona una base sólida para implementar el sistema de RL en SapiensAI utilizando **datos reales extraídos de la base de datos**. La arquitectura propuesta es escalable y permite evolucionar desde algoritmos simples hasta modelos más complejos según las necesidades y el crecimiento de la plataforma. Los datos del usuario 'aiequipodigital@gmail.com' proporcionan un caso de uso real para testing y validación del sistema.