# RL Tutor Tool Tests - Herramienta de Tutoría con Aprendizaje por Refuerzo

Este documento contiene comandos `curl` para probar la herramienta de tutoría con aprendizaje por refuerzo `rl_tutor_tool`, que proporciona recomendaciones personalizadas de contenido educativo basadas en perfiles cognitivos y feedback de estudiantes.

## Configuración del MSP Group

**Endpoint:** `http://149.50.139.104:8000/api/tools/msp/execute`  
**Group:** `rl_tutor_tool`  
**Herramientas Disponibles:**
- `get_recommendation` (obtener recomendación personalizada de contenido)
- `submit_feedback` (enviar feedback de sesión de aprendizaje)

**Action:** `execute` (protocolo MSP estándar)

---

# TESTS DE RECOMENDACIONES PERSONALIZADAS

## Test 1: Recomendación para perfil visual con dislexia leve

**Descripción:** Obtener recomendación para usuario con perfil cognitivo visual y dislexia leve  
**Usuario:** AITEAM DIGITAL (datos reales del sistema)  
**Perfil:** Visual dominante (75%), dislexia leve, fortalezas en pensamiento visual  
**Contexto:** Sesión de aprendizaje con contenido de slides

```bash
curl -X POST "http://149.50.139.104:8000/api/tools/msp/execute" \
  -H "Content-Type: application/json" \
  -d '{
    "group": "rl_tutor_tool",
    "tool": "get_recommendation",
    "action": "execute",
    "arguments": {
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
        }
      },
      "session_context": {
        "current_topic": "Fundamentos de Machine Learning",
        "difficulty_level": "intermediate",
        "session_duration": 45,
        "previous_performance": 0.85,
        "content_type_preference": "slides",
        "time_of_day": "morning"
      },
      "recent_history": [
        {
          "content_type": "slides",
          "score": 1.0,
          "completion_time": 0,
          "interaction_count": 1,
          "feedback": "Contenido completado automáticamente",
          "timestamp": "2025-08-08T20:19:28.694000"
        },
        {
          "content_type": "diagram",
          "score": 1.0,
          "completion_time": 0,
          "interaction_count": 1,
          "feedback": "Contenido completado automáticamente",
          "timestamp": "2025-08-08T20:25:57.583000"
        }
      ]
    }
  }'
```

## Test 2: Recomendación para sesión con bajo rendimiento previo

**Descripción:** Obtener recomendación cuando el estudiante tuvo bajo rendimiento en quiz  
**Escenario:** Usuario falló en quiz anterior, necesita refuerzo  
**Estrategia esperada:** Contenido más visual y fragmentado

```bash
curl -X POST "http://149.50.139.104:8000/api/tools/msp/execute" \
  -H "Content-Type: application/json" \
  -d '{
    "group": "rl_tutor_tool",
    "tool": "get_recommendation",
    "action": "execute",
    "arguments": {
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
          "resolución_problemas"
        ],
        "cognitive_difficulties": [
          "procesamiento_textual_rapido",
          "memoria_trabajo_verbal"
        ]
      },
      "session_context": {
        "current_topic": "Algoritmos de Clasificación",
        "difficulty_level": "intermediate",
        "session_duration": 30,
        "previous_performance": 0.0,
        "content_type_preference": "quiz",
        "time_of_day": "afternoon",
        "struggling_areas": ["conceptos_teoricos", "aplicacion_practica"]
      },
      "recent_history": [
        {
          "content_type": "quiz",
          "score": 0.0,
          "completion_time": 0,
          "interaction_count": 1,
          "feedback": "Contenido completado automáticamente",
          "timestamp": "2025-08-08T20:30:17.241000"
        },
        {
          "content_type": "slides",
          "score": 1.0,
          "completion_time": 0,
          "interaction_count": 1,
          "timestamp": "2025-08-08T20:19:28.694000"
        }
      ]
    }
  }'
```

## Test 3: Recomendación para sesión de repaso

**Descripción:** Obtener recomendación para sesión de repaso con buen historial  
**Escenario:** Usuario con buen rendimiento, sesión de consolidación  
**Estrategia esperada:** Contenido más desafiante o práctico

```bash
curl -X POST "http://149.50.139.104:8000/api/tools/msp/execute" \
  -H "Content-Type: application/json" \
  -d '{
    "group": "rl_tutor_tool",
    "tool": "get_recommendation",
    "action": "execute",
    "arguments": {
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
        ]
      },
      "session_context": {
        "current_topic": "Redes Neuronales",
        "difficulty_level": "advanced",
        "session_duration": 60,
        "previous_performance": 0.92,
        "content_type_preference": "interactive",
        "time_of_day": "evening",
        "session_type": "review"
      },
      "recent_history": [
        {
          "content_type": "slides",
          "score": 1.0,
          "completion_time": 0,
          "interaction_count": 1,
          "timestamp": "2025-08-14T14:38:59.719000"
        },
        {
          "content_type": "diagram",
          "score": 1.0,
          "completion_time": 0,
          "interaction_count": 1,
          "timestamp": "2025-08-14T14:39:06.604000"
        },
        {
          "content_type": "quiz",
          "score": 0.8,
          "completion_time": 180,
          "interaction_count": 5,
          "timestamp": "2025-08-14T14:35:00.000000"
        }
      ]
    }
  }'
```

## Test 4: Recomendación para perfil auditivo

**Descripción:** Obtener recomendación para usuario con preferencia auditiva  
**Escenario:** Usuario con estilo de aprendizaje auditivo dominante  
**Estrategia esperada:** Contenido con componentes de audio o explicaciones verbales

```bash
curl -X POST "http://149.50.139.104:8000/api/tools/msp/execute" \
  -H "Content-Type: application/json" \
  -d '{
    "group": "rl_tutor_tool",
    "tool": "get_recommendation",
    "action": "execute",
    "arguments": {
      "student_id": "test_user_auditory",
      "cognitive_profile": {
        "learning_style": {
          "visual": 30,
          "auditory": 85,
          "reading_writing": 40,
          "kinesthetic": 25
        },
        "diagnosis": [],
        "cognitive_strengths": [
          "procesamiento_auditivo",
          "memoria_verbal",
          "comprension_oral"
        ],
        "cognitive_difficulties": [
          "procesamiento_visual_rapido"
        ],
        "personal_context": {
          "preferred_learning_style": "auditory",
          "motivation_level": "medium",
          "available_study_time": "1-2_hours_daily"
        }
      },
      "session_context": {
        "current_topic": "Procesamiento de Lenguaje Natural",
        "difficulty_level": "beginner",
        "session_duration": 30,
        "previous_performance": 0.75,
        "content_type_preference": "audio",
        "time_of_day": "morning"
      },
      "recent_history": [
        {
          "content_type": "audio",
          "score": 0.9,
          "completion_time": 1200,
          "interaction_count": 3,
          "timestamp": "2025-08-14T10:00:00.000000"
        }
      ]
    }
  }'
```

---

# TESTS DE ENVÍO DE FEEDBACK

## Test 5: Feedback positivo de sesión exitosa

**Descripción:** Enviar feedback de una sesión exitosa con slides  
**Escenario:** Usuario completó exitosamente contenido visual  
**Métricas:** Alto score, tiempo razonable, múltiples interacciones

```bash
curl -X POST "http://149.50.139.104:8000/api/tools/msp/execute" \
  -H "Content-Type: application/json" \
  -d '{
    "group": "rl_tutor_tool",
    "tool": "submit_feedback",
    "action": "execute",
    "arguments": {
      "student_id": "67d8634d841411d3638cf9f1",
      "session_data": {
        "prediction_id": "67d8634d841411d3638cf9f1|visual_profile|slides",
        "content_id": "689461f0bdb2a9494687753f",
        "content_type": "slides",
        "recommended_strategy": "visual_content_priority",
        "session_duration": 1800,
        "topic": "Fundamentos de Machine Learning"
      },
      "performance_metrics": {
        "score": 1.0,
        "completion_time": 1650,
        "interaction_count": 8,
        "engagement_level": 0.9,
        "difficulty_rating": 3,
        "satisfaction_rating": 5
      },
      "learning_outcomes": {
        "concepts_understood": [
          "supervised_learning",
          "unsupervised_learning",
          "model_evaluation"
        ],
        "skills_acquired": [
          "data_preprocessing",
          "model_selection"
        ],
        "areas_for_improvement": []
      },
      "contextual_factors": {
        "time_of_day": "morning",
        "environment": "quiet",
        "device_type": "desktop",
        "distractions": "none"
      }
    }
  }'
```

## Test 6: Feedback de sesión con dificultades

**Descripción:** Enviar feedback de sesión donde el usuario tuvo dificultades  
**Escenario:** Usuario luchó con quiz, necesita ajuste de estrategia  
**Métricas:** Bajo score, tiempo excesivo, pocas interacciones

```bash
curl -X POST "http://149.50.139.104:8000/api/tools/msp/execute" \
  -H "Content-Type: application/json" \
  -d '{
    "group": "rl_tutor_tool",
    "tool": "submit_feedback",
    "action": "execute",
    "arguments": {
      "student_id": "67d8634d841411d3638cf9f1",
      "session_data": {
        "prediction_id": "67d8634d841411d3638cf9f1|struggling_profile|quiz",
        "content_id": "6894441b2eb4213d8959b7f9",
        "content_type": "quiz",
        "recommended_strategy": "chunked_text_presentation",
        "session_duration": 2400,
        "topic": "Algoritmos de Clasificación"
      },
      "performance_metrics": {
        "score": 0.3,
        "completion_time": 2200,
        "interaction_count": 2,
        "engagement_level": 0.4,
        "difficulty_rating": 5,
        "satisfaction_rating": 2,
        "attempts_count": 3
      },
      "learning_outcomes": {
        "concepts_understood": [
          "basic_classification"
        ],
        "skills_acquired": [],
        "areas_for_improvement": [
          "decision_trees",
          "svm_concepts",
          "model_comparison"
        ]
      },
      "contextual_factors": {
        "time_of_day": "afternoon",
        "environment": "noisy",
        "device_type": "mobile",
        "distractions": "high"
      },
      "user_feedback": {
        "difficulty_comments": "Las preguntas eran muy complejas",
        "strategy_effectiveness": 0.3,
        "preferred_alternative": "more_visual_content"
      }
    }
  }'
```

## Test 7: Feedback de sesión con diagrama

**Descripción:** Enviar feedback de sesión exitosa con contenido visual (diagrama)  
**Escenario:** Usuario con perfil visual completó diagrama exitosamente  
**Métricas:** Excelente rendimiento con contenido visual

```bash
curl -X POST "http://149.50.139.104:8000/api/tools/msp/execute" \
  -H "Content-Type: application/json" \
  -d '{
    "group": "rl_tutor_tool",
    "tool": "submit_feedback",
    "action": "execute",
    "arguments": {
      "student_id": "67d8634d841411d3638cf9f1",
      "session_data": {
        "prediction_id": "67d8634d841411d3638cf9f1|visual_profile|diagram",
        "content_id": "689443c32eb4213d8959b7f6",
        "content_type": "diagram",
        "recommended_strategy": "visual_content_priority",
        "session_duration": 900,
        "topic": "Arquitecturas de Redes Neuronales"
      },
      "performance_metrics": {
        "score": 1.0,
        "completion_time": 780,
        "interaction_count": 12,
        "engagement_level": 0.95,
        "difficulty_rating": 2,
        "satisfaction_rating": 5,
        "zoom_interactions": 8,
        "annotation_count": 4
      },
      "learning_outcomes": {
        "concepts_understood": [
          "cnn_architecture",
          "layer_connections",
          "data_flow"
        ],
        "skills_acquired": [
          "diagram_interpretation",
          "architecture_analysis"
        ],
        "areas_for_improvement": []
      },
      "contextual_factors": {
        "time_of_day": "morning",
        "environment": "quiet",
        "device_type": "tablet",
        "distractions": "none"
      },
      "user_feedback": {
        "strategy_effectiveness": 0.9,
        "content_quality_rating": 5,
        "visual_clarity_rating": 5
      }
    }
  }'
```

## Test 8: Feedback de sesión parcialmente completada

**Descripción:** Enviar feedback de sesión que no fue completada totalmente  
**Escenario:** Usuario abandonó sesión por falta de tiempo  
**Métricas:** Progreso parcial, tiempo limitado

```bash
curl -X POST "http://149.50.139.104:8000/api/tools/msp/execute" \
  -H "Content-Type: application/json" \
  -d '{
    "group": "rl_tutor_tool",
    "tool": "submit_feedback",
    "action": "execute",
    "arguments": {
      "student_id": "67d8634d841411d3638cf9f1",
      "session_data": {
        "prediction_id": "67d8634d841411d3638cf9f1|kinesthetic_profile|interactive",
        "content_id": "content_interactive_001",
        "content_type": "interactive",
        "recommended_strategy": "kinesthetic_engagement",
        "session_duration": 1200,
        "topic": "Optimización de Algoritmos",
        "completion_percentage": 0.6
      },
      "performance_metrics": {
        "score": 0.7,
        "completion_time": 1200,
        "interaction_count": 5,
        "engagement_level": 0.6,
        "difficulty_rating": 4,
        "satisfaction_rating": 3,
        "session_abandoned": true,
        "abandonment_reason": "time_constraint"
      },
      "learning_outcomes": {
        "concepts_understood": [
          "basic_optimization",
          "gradient_descent"
        ],
        "skills_acquired": [
          "parameter_tuning"
        ],
        "areas_for_improvement": [
          "advanced_optimization",
          "convergence_analysis"
        ]
      },
      "contextual_factors": {
        "time_of_day": "evening",
        "environment": "moderate_noise",
        "device_type": "desktop",
        "distractions": "time_pressure"
      },
      "user_feedback": {
        "time_availability": "insufficient",
        "content_pacing": "too_fast",
        "strategy_effectiveness": 0.6
      }
    }
  }'
```

## Test 9: Verificar configuración del grupo rl_tutor_tool

**Descripción:** Verificar que el grupo MSP esté correctamente configurado y disponible

```bash
curl -X GET "http://149.50.139.104:8000/api/tools/msp/info/group/rl_tutor_tool" \
  -H "Content-Type: application/json"
```

---

# RESPUESTAS ESPERADAS

## Estructura de Respuesta para get_recommendation

```json
{
  "status": "success",
  "result": {
    "recommendation": {
      "content_type": "slides",
      "difficulty_level": "intermediate",
      "estimated_duration": 30,
      "learning_strategy": "visual_content_priority",
      "confidence_score": 0.85
    },
    "personalization": {
      "adapted_for_profile": true,
      "cognitive_considerations": [
        "dislexia_leve",
        "pensamiento_visual"
      ],
      "recommended_adaptations": [
        "chunked_text_presentation",
        "visual_emphasis",
        "reduced_text_density"
      ]
    },
    "rl_insights": {
      "state_representation": "visual_high_performance",
      "action_taken": "recommend_visual_content",
      "expected_reward": 0.82,
      "exploration_factor": 0.1
    },
    "session_guidance": {
      "optimal_break_intervals": [15, 30],
      "interaction_suggestions": [
        "highlight_key_concepts",
        "use_visual_annotations"
      ],
      "progress_monitoring": {
        "check_understanding_at": ["25%", "50%", "75%"],
        "adaptation_triggers": ["low_engagement", "high_error_rate"]
      }
    }
  }
}
```

## Estructura de Respuesta para submit_feedback

```json
{
  "status": "success",
  "result": {
    "feedback_processed": true,
    "model_updated": true,
    "learning_insights": {
      "strategy_effectiveness": 0.9,
      "performance_improvement": 0.15,
      "optimal_content_type": "slides",
      "recommended_adjustments": [
        "maintain_visual_focus",
        "increase_interaction_frequency"
      ]
    },
    "rl_model_updates": {
      "q_value_updates": 3,
      "state_transitions_recorded": 1,
      "reward_calculated": 0.88,
      "policy_adjustment": "minor_improvement"
    },
    "next_session_recommendations": {
      "suggested_content_type": "diagram",
      "difficulty_adjustment": "maintain",
      "duration_recommendation": 35,
      "strategy_refinements": [
        "emphasize_visual_elements",
        "reduce_text_complexity"
      ]
    },
    "cognitive_profile_updates": {
      "learning_style_confidence": {
        "visual": 0.92,
        "auditory": 0.45,
        "reading_writing": 0.58,
        "kinesthetic": 0.28
      },
      "strategy_effectiveness_scores": {
        "visual_content_priority": 0.89,
        "chunked_text_presentation": 0.72
      }
    }
  }
}
```

## Parámetros de Entrada

### get_recommendation

#### Parámetros Requeridos
- **user_id**: Identificador único del usuario (string)
- **cognitive_profile**: Perfil cognitivo del usuario (object)
  - **learning_style**: Puntuaciones de estilos de aprendizaje (object)
    - **visual**: Puntuación visual 0-100 (number)
    - **auditory**: Puntuación auditiva 0-100 (number)
    - **reading_writing**: Puntuación lectura/escritura 0-100 (number)
    - **kinesthetic**: Puntuación kinestésica 0-100 (number)
  - **diagnosis**: Lista de diagnósticos cognitivos (array)
  - **cognitive_strengths**: Fortalezas cognitivas (array)
  - **cognitive_difficulties**: Dificultades cognitivas (array)

#### Parámetros Opcionales
- **session_context**: Contexto de la sesión actual (object)
  - **current_topic**: Tema actual (string)
  - **difficulty_level**: Nivel de dificultad (string)
  - **session_duration**: Duración planificada en minutos (number)
  - **previous_performance**: Rendimiento previo 0-1 (number)
  - **content_type_preference**: Tipo de contenido preferido (string)
  - **time_of_day**: Momento del día (string)
- **recent_history**: Historial reciente de sesiones (array)

### submit_feedback

#### Parámetros Requeridos
- **user_id**: Identificador único del usuario (string)
- **session_data**: Datos de la sesión (object)
  - **content_id**: ID del contenido (string)
  - **content_type**: Tipo de contenido (string)
  - **recommended_strategy**: Estrategia recomendada (string)
  - **session_duration**: Duración de la sesión en segundos (number)
- **performance_metrics**: Métricas de rendimiento (object)
  - **score**: Puntuación 0-1 (number)
  - **completion_time**: Tiempo de completación en segundos (number)
  - **interaction_count**: Número de interacciones (number)
  - **engagement_level**: Nivel de engagement 0-1 (number)

#### Parámetros Opcionales
- **learning_outcomes**: Resultados de aprendizaje (object)
- **contextual_factors**: Factores contextuales (object)
- **user_feedback**: Feedback directo del usuario (object)

## Casos de Error Comunes

- **400 Bad Request**: Datos de entrada inválidos o faltantes
- **422 Unprocessable Entity**: Formato de perfil cognitivo incorrecto
- **500 Internal Server Error**: Error en el modelo de RL o procesamiento
- **404 Not Found**: Usuario no encontrado en el sistema

---

**Nota:** Todos los tests utilizan datos reales del sistema AITEAM para demostrar diferentes escenarios de personalización educativa, desde recomendaciones básicas hasta feedback complejo con múltiples métricas de rendimiento.