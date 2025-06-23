#!/usr/bin/env python3
"""
Script para configurar templates básicos para la generación rápida de módulos virtuales.
Ejecutar una vez para poblar la base de datos con templates predefinidos.
"""

import sys
import os
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from datetime import datetime
from src.shared.database import get_db
from src.virtual.models import ContentTemplate

def setup_basic_templates():
    """
    Configura templates básicos para diferentes tipos de contenido y metodologías.
    """
    db = get_db()
    templates_collection = db["content_templates"]
    
    # Templates básicos para generación rápida
    basic_templates = [
        # Templates de texto
        {
            "template_type": "content",
            "content_type": "text",
            "methodology": "visual",
            "template_data": {
                "content": "## {topic_name}\n\n{topic_description}\n\n### Conceptos Clave\n- Concepto 1: Descripción breve\n- Concepto 2: Descripción breve\n- Concepto 3: Descripción breve\n\n### Explicación Visual\n{visual_explanation}\n\n### Resumen\n{summary}",
                "placeholders": ["topic_name", "topic_description", "visual_explanation", "summary"],
                "structure": "header_concepts_visual_summary"
            },
            "usage_count": 0,
            "effectiveness_score": 0.7,
            "status": "active"
        },
        {
            "template_type": "content",
            "content_type": "text",
            "methodology": "kinesthetic",
            "template_data": {
                "content": "## {topic_name} - Aprende Haciendo\n\n{topic_description}\n\n### Actividad Práctica\n1. **Paso 1**: {step_1}\n2. **Paso 2**: {step_2}\n3. **Paso 3**: {step_3}\n\n### Reflexión\n- ¿Qué observaste durante la actividad?\n- ¿Cómo se relaciona con el concepto principal?\n\n### Aplicación\n{practical_application}",
                "placeholders": ["topic_name", "topic_description", "step_1", "step_2", "step_3", "practical_application"],
                "structure": "activity_based"
            },
            "usage_count": 0,
            "effectiveness_score": 0.8,
            "status": "active"
        },
        
        # Templates de diagramas
        {
            "template_type": "content",
            "content_type": "diagram",
            "methodology": "visual",
            "template_data": {
                "content": "<div class='diagram-container'><h3>{diagram_title}</h3><div class='diagram-placeholder'>[Diagrama: {diagram_description}]</div><p class='diagram-caption'>{caption}</p></div>",
                "placeholders": ["diagram_title", "diagram_description", "caption"],
                "structure": "visual_representation"
            },
            "usage_count": 0,
            "effectiveness_score": 0.9,
            "status": "active"
        },
        
        # Templates de ejercicios interactivos
        {
            "template_type": "content",
            "content_type": "interactive_exercise",
            "methodology": "kinesthetic",
            "template_data": {
                "content": {
                    "type": "drag_drop",
                    "title": "{exercise_title}",
                    "instructions": "{instructions}",
                    "items": [
                        {"id": 1, "text": "{item_1}", "category": "category_1"},
                        {"id": 2, "text": "{item_2}", "category": "category_2"},
                        {"id": 3, "text": "{item_3}", "category": "category_1"}
                    ],
                    "categories": [
                        {"id": "category_1", "name": "{category_1_name}"},
                        {"id": "category_2", "name": "{category_2_name}"}
                    ]
                },
                "placeholders": ["exercise_title", "instructions", "item_1", "item_2", "item_3", "category_1_name", "category_2_name"],
                "structure": "interactive_categorization"
            },
            "usage_count": 0,
            "effectiveness_score": 0.85,
            "status": "active"
        },
        
        # Templates para adaptaciones específicas
        {
            "template_type": "content",
            "content_type": "text",
            "methodology": "adhd_adapted",
            "template_data": {
                "content": "# 🎯 {topic_name}\n\n## ⚡ Dato Clave\n{key_fact}\n\n## 📝 En 3 Puntos\n1. **{point_1}**\n2. **{point_2}**\n3. **{point_3}**\n\n## 🏃‍♂️ Actividad Rápida (2 min)\n{quick_activity}\n\n## ✅ Lo Aprendido\n{summary}",
                "placeholders": ["topic_name", "key_fact", "point_1", "point_2", "point_3", "quick_activity", "summary"],
                "structure": "short_focused_blocks"
            },
            "usage_count": 0,
            "effectiveness_score": 0.9,
            "status": "active"
        },
        
        {
            "template_type": "content",
            "content_type": "audio",
            "methodology": "dyslexia_adapted",
            "template_data": {
                "content": {
                    "audio_script": "Hola, vamos a aprender sobre {topic_name}. {topic_explanation}. Los puntos más importantes son: {key_points}. Para recordar esto, piensa en {memory_aid}.",
                    "visual_support": "<div class='audio-support'><h3>🎧 {topic_name}</h3><div class='key-points'>{visual_key_points}</div><div class='memory-aid'>💡 {visual_memory_aid}</div></div>",
                    "duration_estimate": "3-5 minutos"
                },
                "placeholders": ["topic_name", "topic_explanation", "key_points", "memory_aid", "visual_key_points", "visual_memory_aid"],
                "structure": "audio_visual_support"
            },
            "usage_count": 0,
            "effectiveness_score": 0.85,
            "status": "active"
        }
    ]
    
    # Insertar templates si no existen
    inserted_count = 0
    for template_data in basic_templates:
        # Verificar si ya existe un template similar
        existing = templates_collection.find_one({
            "template_type": template_data["template_type"],
            "content_type": template_data["content_type"],
            "methodology": template_data["methodology"]
        })
        
        if not existing:
            template = ContentTemplate(**template_data)
            templates_collection.insert_one(template.to_dict())
            inserted_count += 1
            print(f"✅ Template creado: {template_data['content_type']} - {template_data['methodology']}")
        else:
            print(f"⚠️  Template ya existe: {template_data['content_type']} - {template_data['methodology']}")
    
    print(f"\n🎉 Configuración completada. {inserted_count} nuevos templates creados.")
    return inserted_count

def create_sample_module_templates():
    """
    Crea templates para estructuras completas de módulos.
    """
    db = get_db()
    templates_collection = db["content_templates"]
    
    module_templates = [
        {
            "template_type": "module",
            "content_type": "structure",
            "methodology": "balanced",
            "template_data": {
                "structure": {
                    "introduction": {
                        "type": "text",
                        "methodology": "visual",
                        "content": "Introducción al módulo {module_name}"
                    },
                    "core_content": {
                        "type": "mixed",
                        "components": [
                            {"type": "text", "methodology": "visual"},
                            {"type": "diagram", "methodology": "visual"},
                            {"type": "interactive_exercise", "methodology": "kinesthetic"}
                        ]
                    },
                    "practice": {
                        "type": "interactive_exercise",
                        "methodology": "kinesthetic",
                        "content": "Ejercicios prácticos"
                    },
                    "summary": {
                        "type": "text",
                        "methodology": "read_write",
                        "content": "Resumen y puntos clave"
                    }
                },
                "estimated_generation_time": 25
            },
            "usage_count": 0,
            "effectiveness_score": 0.8,
            "status": "active"
        }
    ]
    
    inserted_count = 0
    for template_data in module_templates:
        existing = templates_collection.find_one({
            "template_type": template_data["template_type"],
            "content_type": template_data["content_type"],
            "methodology": template_data["methodology"]
        })
        
        if not existing:
            template = ContentTemplate(**template_data)
            templates_collection.insert_one(template.to_dict())
            inserted_count += 1
            print(f"✅ Template de módulo creado: {template_data['methodology']}")
        else:
            print(f"⚠️  Template de módulo ya existe: {template_data['methodology']}")
    
    return inserted_count

def main():
    """
    Función principal para ejecutar la configuración de templates.
    """
    print("🚀 Configurando templates para generación virtual rápida...")
    print("=" * 60)
    
    try:
        # Configurar templates básicos de contenido
        content_templates = setup_basic_templates()
        
        print("\n" + "=" * 60)
        
        # Configurar templates de módulos
        module_templates = create_sample_module_templates()
        
        print(f"\n✨ Configuración finalizada exitosamente!")
        print(f"📊 Resumen:")
        print(f"   - Templates de contenido: {content_templates}")
        print(f"   - Templates de módulo: {module_templates}")
        print(f"   - Total: {content_templates + module_templates}")
        
    except Exception as e:
        print(f"❌ Error durante la configuración: {str(e)}")
        sys.exit(1)

 