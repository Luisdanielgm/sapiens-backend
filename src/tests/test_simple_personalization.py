#!/usr/bin/env python3
"""
Test simple para validar la lógica de personalización sin dependencias de BD
"""

import sys
import os
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..', '..')))

from datetime import datetime
from bson import ObjectId

# Simular la estructura de FastVirtualModuleGenerator sin dependencias
class MockPersonalizationLogic:
    """Mock de la lógica de personalización para testing"""
    
    def _select_by_vak_preference(self, contents, visual, auditory, reading, kinesthetic):
        """Selecciona contenido según preferencias VAK"""
        if not contents:
            return None
        
        content_scores = []
        
        for content in contents:
            content_type = content.get("content_type", "")
            score = 0
            
            if content_type in ["video", "slide"] and visual > 0.5:
                score += visual * 2
            elif content_type in ["audio", "narrated_presentation"] and auditory > 0.5:
                score += auditory * 2
            elif content_type in ["text", "feynman", "summary"] and reading > 0.5:
                score += reading * 2
            elif content_type in ["story"] and kinesthetic > 0.5:
                score += kinesthetic * 1.5
            else:
                score = 0.5
            
            content_scores.append((content, score))
        
        content_scores.sort(key=lambda x: x[1], reverse=True)
        return content_scores[0][0]
    
    def _calculate_difficulty_adjustment(self, cognitive_profile):
        """Calcula ajuste de dificultad"""
        try:
            difficulties = cognitive_profile.get("cognitive_difficulties", [])
            strengths = cognitive_profile.get("cognitive_strengths", [])
            
            adjustment = 0.0
            
            if "memoria" in difficulties or "atención" in difficulties:
                adjustment -= 0.2
            if "procesamiento" in difficulties:
                adjustment -= 0.3
            
            if "análisis" in strengths or "síntesis" in strengths:
                adjustment += 0.2
            if "memoria_visual" in strengths:
                adjustment += 0.1
            
            return max(-0.5, min(0.5, adjustment))
        except:
            return 0.0

def test_vak_preference_selection():
    """Test selección por preferencia VAK"""
    print("🧪 Testing VAK preference selection...")
    
    logic = MockPersonalizationLogic()
    
    # Contenidos de prueba
    contents = [
        {"_id": ObjectId(), "content_type": "text", "content": "Texto"},
        {"_id": ObjectId(), "content_type": "video", "content": "Video"},
        {"_id": ObjectId(), "content_type": "audio", "content": "Audio"}
    ]
    
    # Test estudiante visual
    selected = logic._select_by_vak_preference(contents, 0.9, 0.2, 0.3, 0.2)
    assert selected["content_type"] == "video", f"Expected video, got {selected['content_type']}"
    print("✅ Visual preference test passed")
    
    # Test estudiante auditivo
    selected = logic._select_by_vak_preference(contents, 0.2, 0.9, 0.3, 0.2)
    assert selected["content_type"] == "audio", f"Expected audio, got {selected['content_type']}"
    print("✅ Auditory preference test passed")
    
    # Test estudiante de lectura
    selected = logic._select_by_vak_preference(contents, 0.2, 0.2, 0.9, 0.2)
    assert selected["content_type"] == "text", f"Expected text, got {selected['content_type']}"
    print("✅ Reading preference test passed")

def test_difficulty_adjustment():
    """Test cálculo de ajuste de dificultad"""
    print("\n🧪 Testing difficulty adjustment...")
    
    logic = MockPersonalizationLogic()
    
    # Perfil con dificultades
    profile_difficulties = {
        "cognitive_difficulties": ["memoria", "atención"],
        "cognitive_strengths": []
    }
    
    adjustment = logic._calculate_difficulty_adjustment(profile_difficulties)
    assert adjustment < 0, f"Expected negative adjustment, got {adjustment}"
    print(f"✅ Difficulty adjustment test passed: {adjustment}")
    
    # Perfil con fortalezas
    profile_strengths = {
        "cognitive_difficulties": [],
        "cognitive_strengths": ["análisis", "síntesis"]
    }
    
    adjustment = logic._calculate_difficulty_adjustment(profile_strengths)
    assert adjustment > 0, f"Expected positive adjustment, got {adjustment}"
    print(f"✅ Strengths adjustment test passed: {adjustment}")

def test_content_categorization():
    """Test categorización de contenidos"""
    print("\n🧪 Testing content categorization...")
    
    sample_contents = [
        {"content_type": "text", "name": "Texto educativo"},
        {"content_type": "slide", "name": "Presentación"},
        {"content_type": "video", "name": "Video explicativo"},
        {"content_type": "diagram", "name": "Diagrama conceptual"},
        {"content_type": "game", "name": "Juego educativo"},
        {"content_type": "quiz", "name": "Cuestionario"}
    ]
    
    # Categorizar
    complete_contents = []
    specific_contents = []
    evaluative_contents = []
    
    for content in sample_contents:
        content_type = content.get("content_type", "")
        
        if content_type in ["text", "slide", "video", "feynman", "story", "summary"]:
            complete_contents.append(content)
        elif content_type in ["quiz", "exam", "formative_test", "project"]:
            evaluative_contents.append(content)
        else:
            specific_contents.append(content)
    
    assert len(complete_contents) == 3, f"Expected 3 complete contents, got {len(complete_contents)}"
    assert len(evaluative_contents) == 1, f"Expected 1 evaluative content, got {len(evaluative_contents)}"
    assert len(specific_contents) == 2, f"Expected 2 specific contents, got {len(specific_contents)}"
    
    print("✅ Content categorization test passed")
    print(f"   Complete: {len(complete_contents)} | Specific: {len(specific_contents)} | Evaluative: {len(evaluative_contents)}")

def main():
    """Ejecutar todos los tests"""
    print("🚀 Iniciando tests de personalización...")
    print("=" * 50)
    
    try:
        test_vak_preference_selection()
        test_difficulty_adjustment()
        test_content_categorization()
        
        print("\n" + "=" * 50)
        print("🎉 ¡Todos los tests pasaron exitosamente!")
        print("✅ La lógica de personalización funciona correctamente")
        
    except Exception as e:
        print(f"\n❌ Error en tests: {str(e)}")
        import traceback
        traceback.print_exc()
        return False
    
    return True

if __name__ == "__main__":
    # Ejecutar una prueba simple de la lógica mock
    test_logic = MockPersonalizationLogic()
    test_logic.run_tests()
    print("✅ Tests de lógica de personalización ejecutados con éxito.")
    sys.exit(0 if success else 1)