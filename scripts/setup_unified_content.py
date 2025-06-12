#!/usr/bin/env python3
"""
Script de configuración para el Sistema de Contenido Unificado.
Inicializa tipos de contenido y migra datos legacy si es necesario.
"""

import sys
import os
import argparse
from datetime import datetime

# Agregar el directorio raíz al path para importaciones
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from src.shared.database import get_db
from src.content.models import ContentType

def init_content_types():
    """
    Inicializa los tipos de contenido predefinidos.
    """
    db = get_db()
    content_types_collection = db.content_types
    
    # Tipos de contenido predefinidos
    content_types = [
        # Contenido Estático
        {
            "code": "text",
            "name": "Contenido de Texto",
            "category": "static",
            "subcategory": "text",
            "description": "Contenido textual con formato HTML",
            "template_schema": {
                "html_content": {"type": "string", "required": True},
                "style_config": {"type": "object", "required": False}
            },
            "cognitive_compatibility": {
                "visual": 0.7,
                "auditory": 0.3,
                "kinesthetic": 0.1
            },
            "accessibility_features": ["text_to_speech", "font_scaling", "high_contrast"],
            "rendering_config": {
                "supports_html": True,
                "supports_markdown": True,
                "allows_interactive_elements": False
            }
        },
        {
            "code": "diagram",
            "name": "Diagrama Interactivo",
            "category": "static",
            "subcategory": "diagram",
            "description": "Diagramas y gráficos interactivos",
            "template_schema": {
                "diagram_type": {"type": "string", "required": True},
                "diagram_data": {"type": "object", "required": True},
                "interaction_config": {"type": "object", "required": False}
            },
            "cognitive_compatibility": {
                "visual": 0.9,
                "auditory": 0.2,
                "kinesthetic": 0.6
            },
            "accessibility_features": ["alt_text", "keyboard_navigation", "color_blind_friendly"],
            "rendering_config": {
                "supports_svg": True,
                "supports_canvas": True,
                "supports_zoom": True
            }
        },
        {
            "code": "video",
            "name": "Contenido de Video",
            "category": "static",
            "subcategory": "video",
            "description": "Videos educativos con controles",
            "template_schema": {
                "video_url": {"type": "string", "required": True},
                "subtitles": {"type": "array", "required": False},
                "chapters": {"type": "array", "required": False}
            },
            "cognitive_compatibility": {
                "visual": 0.8,
                "auditory": 0.9,
                "kinesthetic": 0.3
            },
            "accessibility_features": ["subtitles", "audio_description", "playback_speed"],
            "rendering_config": {
                "supports_streaming": True,
                "supports_chapters": True,
                "supports_annotations": True
            }
        },
        {
            "code": "slides",
            "name": "Presentación de Diapositivas",
            "category": "static",
            "subcategory": "presentation",
            "description": "Presentaciones interactivas tipo diapositivas",
            "template_schema": {
                "slides": {"type": "array", "required": True},
                "navigation_config": {"type": "object", "required": False},
                "animation_config": {"type": "object", "required": False}
            },
            "cognitive_compatibility": {
                "visual": 0.9,
                "auditory": 0.6,
                "kinesthetic": 0.4
            },
            "accessibility_features": ["keyboard_navigation", "screen_reader", "auto_advance"],
            "rendering_config": {
                "supports_transitions": True,
                "supports_notes": True,
                "supports_fullscreen": True
            }
        },
        
        # Contenido Interactivo
        {
            "code": "game",
            "name": "Juego Educativo",
            "category": "interactive",
            "subcategory": "game",
            "description": "Juegos interactivos para aprendizaje",
            "template_schema": {
                "game_code": {"type": "string", "required": True},
                "game_type": {"type": "string", "required": True},
                "scoring_config": {"type": "object", "required": False},
                "difficulty_levels": {"type": "array", "required": False}
            },
            "cognitive_compatibility": {
                "visual": 0.8,
                "auditory": 0.5,
                "kinesthetic": 0.9
            },
            "accessibility_features": ["keyboard_controls", "colorblind_support", "reduced_motion"],
            "interaction_config": {
                "supports_scoring": True,
                "supports_levels": True,
                "supports_leaderboard": True,
                "tracks_progress": True
            },
            "rendering_config": {
                "supports_canvas": True,
                "supports_webgl": True,
                "requires_interaction": True
            }
        },
        {
            "code": "simulation",
            "name": "Simulación Interactiva",
            "category": "interactive",
            "subcategory": "simulation",
            "description": "Simulaciones para experimentación virtual",
            "template_schema": {
                "simulation_code": {"type": "string", "required": True},
                "simulation_type": {"type": "string", "required": True},
                "parameters": {"type": "object", "required": True},
                "output_config": {"type": "object", "required": False}
            },
            "cognitive_compatibility": {
                "visual": 0.7,
                "auditory": 0.4,
                "kinesthetic": 0.9
            },
            "accessibility_features": ["parameter_descriptions", "results_summary", "step_by_step"],
            "interaction_config": {
                "supports_parameters": True,
                "supports_reset": True,
                "supports_save_state": True,
                "tracks_experiments": True
            },
            "rendering_config": {
                "supports_real_time": True,
                "supports_3d": True,
                "supports_data_export": True
            }
        },
        {
            "code": "quiz",
            "name": "Cuestionario Interactivo",
            "category": "interactive",
            "subcategory": "quiz",
            "description": "Cuestionarios con retroalimentación inmediata",
            "template_schema": {
                "questions": {"type": "array", "required": True},
                "question_types": {"type": "array", "required": True},
                "feedback_config": {"type": "object", "required": False},
                "scoring_rules": {"type": "object", "required": False}
            },
            "cognitive_compatibility": {
                "visual": 0.6,
                "auditory": 0.7,
                "kinesthetic": 0.5
            },
            "accessibility_features": ["screen_reader", "keyboard_navigation", "extended_time"],
            "interaction_config": {
                "supports_multiple_attempts": True,
                "supports_partial_credit": True,
                "provides_feedback": True,
                "tracks_answers": True
            },
            "rendering_config": {
                "supports_multimedia": True,
                "supports_equations": True,
                "supports_drag_drop": True
            }
        },
        
        # Contenido Inmersivo (Para futuro)
        {
            "code": "ar_experience",
            "name": "Experiencia de Realidad Aumentada",
            "category": "immersive",
            "subcategory": "ar",
            "description": "Experiencias educativas en realidad aumentada",
            "template_schema": {
                "ar_scene": {"type": "object", "required": True},
                "markers": {"type": "array", "required": False},
                "interaction_objects": {"type": "array", "required": False}
            },
            "cognitive_compatibility": {
                "visual": 0.9,
                "auditory": 0.7,
                "kinesthetic": 0.95
            },
            "accessibility_features": ["voice_commands", "gesture_alternatives", "simplified_mode"],
            "interaction_config": {
                "requires_camera": True,
                "supports_gestures": True,
                "supports_voice": True,
                "tracks_spatial_data": True
            },
            "rendering_config": {
                "requires_webxr": True,
                "supports_3d": True,
                "supports_occlusion": True
            }
        },
        {
            "code": "virtual_lab",
            "name": "Laboratorio Virtual",
            "category": "immersive",
            "subcategory": "lab",
            "description": "Laboratorios virtuales para experimentación",
            "template_schema": {
                "lab_environment": {"type": "object", "required": True},
                "equipment": {"type": "array", "required": True},
                "procedures": {"type": "array", "required": True},
                "safety_config": {"type": "object", "required": False}
            },
            "cognitive_compatibility": {
                "visual": 0.8,
                "auditory": 0.6,
                "kinesthetic": 0.9
            },
            "accessibility_features": ["guided_mode", "text_descriptions", "alternative_procedures"],
            "interaction_config": {
                "supports_3d_interaction": True,
                "supports_physics": True,
                "tracks_procedures": True,
                "provides_guidance": True
            },
            "rendering_config": {
                "requires_webgl": True,
                "supports_physics": True,
                "supports_haptics": False
            }
        }
    ]
    
    print("🚀 Inicializando tipos de contenido...")
    
    for ct_data in content_types:
        existing = content_types_collection.find_one({"code": ct_data["code"]})
        
        if existing:
            print(f"✓ Tipo '{ct_data['code']}' ya existe - actualizando...")
            content_types_collection.update_one(
                {"code": ct_data["code"]},
                {"$set": {**ct_data, "updated_at": datetime.now()}}
            )
        else:
            print(f"✓ Creando tipo '{ct_data['code']}'...")
            # Insertar directamente el diccionario de datos para evitar errores de validación de modelo
            doc = {
                **ct_data,
                "created_at": datetime.now(),
                "updated_at": datetime.now()
            }
            content_types_collection.insert_one(doc)
    
    print(f"✅ {len(content_types)} tipos de contenido inicializados")

def create_collections():
    """
    Crea las colecciones necesarias para el sistema unificado.
    """
    db = get_db()
    
    collections_to_create = [
        "content_types",
        "content_results", 
        "content_templates",
        "virtual_topic_contents"  # Si no existe
    ]
    
    existing_collections = db.list_collection_names()
    
    print("📚 Verificando colecciones...")
    
    for collection_name in collections_to_create:
        if collection_name not in existing_collections:
            print(f"✓ Creando colección '{collection_name}'...")
            db.create_collection(collection_name)
        else:
            print(f"✓ Colección '{collection_name}' ya existe")
    
    # Crear índices importantes
    print("🔍 Creando índices...")
    
    # Índices para content_types
    db.content_types.create_index("code", unique=True)
    db.content_types.create_index([("category", 1), ("subcategory", 1)])
    
    # Índices para topic_contents (unificado)
    db.topic_contents.create_index([("topic_id", 1), ("content_type", 1)])
    db.topic_contents.create_index("content_type")
    db.topic_contents.create_index("status")
    
    # Índices para virtual_topic_contents
    db.virtual_topic_contents.create_index([("student_id", 1), ("content_id", 1)])
    db.virtual_topic_contents.create_index("virtual_topic_id")
    
    # Índices para content_results
    db.content_results.create_index([("student_id", 1), ("created_at", -1)])
    db.content_results.create_index("virtual_content_id")
    
    print("✅ Índices creados")

def verify_system():
    """
    Verifica que el sistema esté funcionando correctamente.
    """
    print("🔍 Verificando sistema...")
    
    try:
        from src.content.services import ContentService, ContentTypeService
        
        # Test básico de servicios
        content_type_service = ContentTypeService()
        content_service = ContentService()
        
        # Verificar que se pueden obtener tipos de contenido
        types = content_type_service.list_content_types()
        print(f"✓ {len(types)} tipos de contenido disponibles")
        
        # Verificar categorías
        static_types = content_type_service.list_content_types(category="static")
        interactive_types = content_type_service.list_content_types(category="interactive")
        immersive_types = content_type_service.list_content_types(category="immersive")
        
        print(f"✓ Contenido estático: {len(static_types)} tipos")
        print(f"✓ Contenido interactivo: {len(interactive_types)} tipos") 
        print(f"✓ Contenido inmersivo: {len(immersive_types)} tipos")
        
        print("✅ Sistema verificado exitosamente")
        
    except Exception as e:
        print(f"❌ Error en verificación: {str(e)}")
        return False
    
    return True

def migrate_legacy_data():
    """
    Migra datos del sistema legacy al sistema unificado.
    ¡CUIDADO! Esta función debe usarse con precaución.
    """
    print("⚠️  Función de migración no implementada en esta versión")
    print("   Para migrar datos legacy, contacta al equipo de desarrollo")

def main():
    parser = argparse.ArgumentParser(description="Configurar sistema de contenido unificado")
    parser.add_argument('--migrate-legacy', action='store_true', 
                       help='Migrar datos del sistema legacy (usar con precaución)')
    parser.add_argument('--verify-only', action='store_true',
                       help='Solo verificar el sistema sin inicializar')
    
    args = parser.parse_args()
    
    print("🎯 Sistema de Contenido Unificado - Configuración")
    print("=" * 50)
    
    if args.verify_only:
        success = verify_system()
        sys.exit(0 if success else 1)
    
    try:
        # Paso 1: Crear colecciones
        create_collections()
        
        # Paso 2: Inicializar tipos de contenido
        init_content_types()
        
        # Paso 3: Migrar datos legacy si se solicita
        if args.migrate_legacy:
            migrate_legacy_data()
        
        # Paso 4: Verificar sistema
        success = verify_system()
        
        if success:
            print("\n🎉 ¡Sistema de contenido unificado configurado exitosamente!")
            print("\nPróximos pasos:")
            print("1. El sistema está listo para usar")
            print("2. Endpoints disponibles en /api/content/")
            print("3. Crear contenido desde un solo endpoint")
            print("4. Revisar documentación en docs/SISTEMA_CONTENIDO_UNIFICADO.md")
        else:
            print("\n❌ Hubo errores en la configuración")
            sys.exit(1)
            
    except Exception as e:
        print(f"\n❌ Error durante la configuración: {str(e)}")
        sys.exit(1)

if __name__ == "__main__":
    main() 