import unittest
from unittest.mock import Mock, patch
from datetime import datetime
from bson import ObjectId

import sys
import os
# Añadir el directorio raíz al path
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..', '..')))

from src.virtual.services import FastVirtualModuleGenerator

class TestVirtualPersonalization(unittest.TestCase):
    """
    Tests para la funcionalidad de personalización de contenidos virtuales
    """
    
    def setUp(self):
        """Configurar datos de prueba"""
        # Mock de la base de datos para evitar dependencias
        self.generator = FastVirtualModuleGenerator()
        
        # Perfil cognitivo de prueba - estudiante visual con dislexia
        self.cognitive_profile_visual_dyslexia = {
            "learning_style": {
                "visual": 0.8,
                "auditory": 0.3,
                "kinesthetic": 0.4,
                "reading_writing": 0.2
            },
            "diagnosis": ["dislexia"],
            "profile": {
                "vak_scores": {
                    "visual": 0.8,
                    "auditory": 0.3,
                    "kinesthetic": 0.4,
                    "reading_writing": 0.2
                },
                "learning_disabilities": {
                    "dyslexia": True,
                    "adhd": False
                }
            }
        }
        
        # Perfil kinestésico con ADHD
        self.cognitive_profile_kinesthetic_adhd = {
            "learning_style": {
                "visual": 0.4,
                "auditory": 0.3,
                "kinesthetic": 0.9,
                "reading_writing": 0.3
            },
            "diagnosis": ["ADHD"],
            "profile": {
                "vak_scores": {
                    "visual": 0.4,
                    "auditory": 0.3,
                    "kinesthetic": 0.9,
                    "reading_writing": 0.3
                },
                "learning_disabilities": {
                    "dyslexia": False,
                    "adhd": True
                }
            }
        }
        
        # Contenidos de ejemplo
        self.sample_contents = [
            {"_id": ObjectId(), "content_type": "text", "content": "Texto educativo"},
            {"_id": ObjectId(), "content_type": "slides", "content": "Presentación"},
            {"_id": ObjectId(), "content_type": "video", "content": "Video explicativo"},
            {"_id": ObjectId(), "content_type": "diagram", "content": "Diagrama conceptual"},
            {"_id": ObjectId(), "content_type": "game", "content": "Juego educativo"},
            {"_id": ObjectId(), "content_type": "audio", "content": "Audio explicativo"},
            {"_id": ObjectId(), "content_type": "quiz", "content": "Cuestionario"},
            {"_id": ObjectId(), "content_type": "interactive_exercise", "content": "Ejercicio interactivo"}
        ]
    
    def test_select_personalized_contents_visual_dyslexia(self):
        """Test personalización para estudiante visual con dislexia"""
        selected = self.generator._select_personalized_contents(
            self.sample_contents, self.cognitive_profile_visual_dyslexia
        )
        
        # Verificar que se seleccionaron contenidos
        self.assertGreater(len(selected), 0)
        self.assertLessEqual(len(selected), 6)
        
        # Verificar que hay al menos un contenido completo
        complete_types = ["text", "slides", "video", "feynman", "story", "summary", "narrated_presentation"]
        has_complete = any(c.get("content_type") in complete_types for c in selected)
        self.assertTrue(has_complete, "Debe haber al menos un contenido completo")
        
        # Para dislexia, debe priorizar contenidos visuales y evitar solo texto
        content_types = [c.get("content_type") for c in selected]
        visual_content_count = sum(1 for ct in content_types if ct in ["diagram", "video", "slides"])
        self.assertGreater(visual_content_count, 0, "Debe incluir contenidos visuales para estudiantes con dislexia")
    
    def test_select_personalized_contents_kinesthetic_adhd(self):
        """Test personalización para estudiante kinestésico con ADHD"""
        selected = self.generator._select_personalized_contents(
            self.sample_contents, self.cognitive_profile_kinesthetic_adhd
        )
        
        # Verificar que se seleccionaron contenidos
        self.assertGreater(len(selected), 0)
        self.assertLessEqual(len(selected), 6)
        
        # Para ADHD y kinestésico, debe priorizar contenidos interactivos
        content_types = [c.get("content_type") for c in selected]
        interactive_count = sum(1 for ct in content_types if ct in ["game", "interactive_exercise", "simulation"])
        self.assertGreater(interactive_count, 0, "Debe incluir contenidos interactivos para estudiantes kinestésicos con ADHD")
    
    def test_select_by_vak_preference(self):
        """Test selección de contenido completo por preferencia VAK"""
        # Contenidos completos de prueba
        complete_contents = [
            {"_id": ObjectId(), "content_type": "text", "content": "Texto"},
            {"_id": ObjectId(), "content_type": "video", "content": "Video"},
            {"_id": ObjectId(), "content_type": "audio", "content": "Audio"}
        ]
        
        # Estudiante visual fuerte
        selected = self.generator._select_by_vak_preference(complete_contents, 0.9, 0.2, 0.3, 0.2)
        self.assertEqual(selected["content_type"], "video")
        
        # Estudiante auditivo fuerte  
        selected = self.generator._select_by_vak_preference(complete_contents, 0.2, 0.9, 0.3, 0.2)
        self.assertEqual(selected["content_type"], "audio")
        
        # Estudiante de lectura fuerte
        selected = self.generator._select_by_vak_preference(complete_contents, 0.2, 0.2, 0.9, 0.2)
        self.assertEqual(selected["content_type"], "text")
    
    def test_generate_content_personalization(self):
        """Test generación de datos de personalización"""
        content = {"_id": ObjectId(), "content_type": "video", "content": "Video educativo"}
        
        personalization = self.generator._generate_content_personalization(
            content, self.cognitive_profile_visual_dyslexia
        )
        
        # Verificar estructura básica
        self.assertTrue(personalization["adapted_for_profile"])
        self.assertTrue(personalization["sync_generated"])
        self.assertEqual(personalization["content_type"], "video")
        
        # Verificar adaptaciones VAK
        vak_adaptation = personalization["vak_adaptation"]
        self.assertTrue(vak_adaptation["visual_emphasis"])  # Score visual > 0.6
        self.assertFalse(vak_adaptation["audio_support"])   # Score auditivo < 0.6
        
        # Verificar adaptaciones de accesibilidad
        accessibility = personalization["accessibility_adaptations"]
        self.assertTrue(accessibility["dyslexia_friendly"])
        self.assertFalse(accessibility["adhd_optimized"])
    
    def test_calculate_difficulty_adjustment(self):
        """Test cálculo de ajuste de dificultad"""
        # Perfil con dificultades
        profile_with_difficulties = {
            "cognitive_difficulties": ["memoria", "atención"],
            "cognitive_strengths": []
        }
        
        adjustment = self.generator._calculate_difficulty_adjustment(profile_with_difficulties)
        self.assertLess(adjustment, 0, "Dificultades deben reducir la dificultad")
        
        # Perfil con fortalezas
        profile_with_strengths = {
            "cognitive_difficulties": [],
            "cognitive_strengths": ["análisis", "síntesis"]
        }
        
        adjustment = self.generator._calculate_difficulty_adjustment(profile_with_strengths)
        self.assertGreater(adjustment, 0, "Fortalezas deben aumentar la dificultad")
    
    def test_estimate_content_time(self):
        """Test estimación de tiempo de contenido"""
        content_text = {"content_type": "text"}
        content_game = {"content_type": "game"}
        
        # Tiempo normal
        time_normal = self.generator._estimate_content_time(content_text, {})
        self.assertEqual(time_normal, 10)  # Tiempo base para texto
        
        # Tiempo con dislexia (debe aumentar para texto)
        time_dyslexia = self.generator._estimate_content_time(
            content_text, self.cognitive_profile_visual_dyslexia
        )
        self.assertGreater(time_dyslexia, time_normal)
        
        # Tiempo para juego con ADHD
        time_adhd = self.generator._estimate_content_time(
            content_game, self.cognitive_profile_kinesthetic_adhd
        )
        self.assertEqual(time_adhd, 15)  # Tiempo base para juego (no afectado por ADHD)
    
    def test_minimum_content_selection(self):
        """Test que siempre se seleccionen al menos 3 contenidos"""
        # Solo 2 contenidos disponibles
        minimal_contents = self.sample_contents[:2]
        
        selected = self.generator._select_personalized_contents(
            minimal_contents, self.cognitive_profile_visual_dyslexia
        )
        
        # Debe devolver todos los disponibles aunque sean menos de 3
        self.assertEqual(len(selected), 2)
    
    def test_maximum_content_selection(self):
        """Test que no se seleccionen más de 6 contenidos"""
        # Muchos contenidos disponibles
        many_contents = self.sample_contents * 3  # 24 contenidos
        
        selected = self.generator._select_personalized_contents(
            many_contents, self.cognitive_profile_visual_dyslexia
        )
        
        # No debe exceder 6 contenidos
        self.assertLessEqual(len(selected), 6)

if __name__ == '__main__':
    unittest.main() 