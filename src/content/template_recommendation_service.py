import json
import logging
from typing import Dict, List, Optional, Any, Tuple
from bson import ObjectId
from datetime import datetime

from src.shared.database import get_db
from .template_services import TemplateService
from src.personalization.services import AdaptivePersonalizationService

class TemplateRecommendationService:
    """
    Servicio para recomendar plantillas de IA basadas en el contenido de diapositivas específicas.
    Implementa lógica de recomendación inteligente considerando:
    - Coincidencia de tags temáticos
    - Balance de estilos de aprendizaje (VARK)
    - Variedad de tipos de contenido
    - Duración y complejidad apropiada
    """
    
    def __init__(self):
        self.db = get_db()
        self.template_service = TemplateService()
        self.personalization_service = AdaptivePersonalizationService()
        self.templates_collection = self.db.templates
        self.content_collection = self.db.topic_contents
        
    def recommend_templates_for_slides(self, topic_id: str, user_id: str, 
                                     max_recommendations: int = 3) -> Dict[str, List[Dict]]:
        """
        Recomienda plantillas para cada diapositiva de un tema.
        
        Args:
            topic_id: ID del tema
            user_id: ID del usuario/profesor
            max_recommendations: Máximo de recomendaciones por diapositiva
            
        Returns:
            Dict con slide_id como clave y lista de recomendaciones como valor
        """
        try:
            # Obtener todas las diapositivas del tema
            slides = self._get_topic_slides(topic_id)
            if not slides:
                return {}
            
            # Obtener plantillas disponibles para el usuario
            available_templates = self._get_available_templates(user_id)
            if not available_templates:
                return {}
            
            # Obtener información del tema para contexto
            topic_info = self._get_topic_context(topic_id)
            
            recommendations = {}
            used_templates = set()  # Para evitar repetir plantillas
            vark_balance = {"V": 0, "A": 0, "K": 0, "R": 0}  # Balance acumulado
            
            for i, slide in enumerate(slides):
                slide_id = str(slide["_id"])
                
                # Analizar contenido de la diapositiva
                slide_analysis = self._analyze_slide_content(slide)
                
                # Generar recomendaciones para esta diapositiva
                slide_recommendations = self._generate_slide_recommendations(
                    slide=slide,
                    slide_analysis=slide_analysis,
                    available_templates=available_templates,
                    topic_context=topic_info,
                    used_templates=used_templates,
                    current_vark_balance=vark_balance,
                    slide_position=i + 1,
                    total_slides=len(slides),
                    max_recommendations=max_recommendations
                )
                
                recommendations[slide_id] = slide_recommendations
                
                # Actualizar templates usados y balance VARK
                for rec in slide_recommendations:
                    if rec.get("selected", False):
                        used_templates.add(rec["template_id"])
                        template_vark = rec.get("baseline_mix", {})
                        for key in vark_balance:
                            vark_balance[key] += template_vark.get(key, 0)
            
            logging.info(f"Generated recommendations for {len(slides)} slides in topic {topic_id}")
            return recommendations
            
        except Exception as e:
            logging.error(f"Error generating template recommendations: {str(e)}")
            raise e
    
    def _calculate_rl_boost(self, template_id: str, slide_index: int, rl_recommendations: Dict) -> float:
        """
        Calcula el impulso de puntuación basado en las recomendaciones del sistema RL.
        
        Args:
            template_id: ID de la plantilla
            slide_index: Índice de la diapositiva actual
            rl_recommendations: Recomendaciones del sistema RL
            
        Returns:
            float: Impulso de puntuación (0.0 a 0.3)
        """
        try:
            boost = 0.0
            
            # Boost basado en preferencias de plantillas del RL
            template_preferences = rl_recommendations.get("template_preferences", {})
            if template_id in template_preferences:
                preference_score = template_preferences[template_id]
                boost += preference_score * 0.2  # Máximo 0.2 de boost
            
            # Boost basado en recomendaciones específicas por posición
            position_recommendations = rl_recommendations.get("position_recommendations", {})
            position_key = f"slide_{slide_index}"
            if position_key in position_recommendations:
                position_prefs = position_recommendations[position_key]
                if template_id in position_prefs:
                    boost += position_prefs[template_id] * 0.1  # Máximo 0.1 adicional
            
            # Boost basado en el nivel de confianza del RL
            confidence = rl_recommendations.get("confidence_score", 0.5)
            boost *= confidence  # Reducir boost si la confianza es baja
            
            # Limitar el boost máximo
            return min(boost, 0.3)
            
        except Exception as e:
            logging.error(f"Error calculating RL boost: {str(e)}")
            return 0.0
    
    def _get_topic_slides(self, topic_id: str) -> List[Dict]:
        """
        Obtiene todas las diapositivas de un tema ordenadas por 'order'.
        """
        try:
            slides = list(self.content_collection.find({
                "topic_id": ObjectId(topic_id),
                "content_type": "slide"
            }).sort("order", 1))
            
            return slides
            
        except Exception as e:
            logging.error(f"Error getting topic slides: {str(e)}")
            return []
    
    def _get_available_templates(self, user_id: str = None) -> List[Dict]:
        """
        Obtiene plantillas disponibles para el usuario (propias + públicas).
        """
        try:
            # Plantillas del usuario + plantillas públicas
            if user_id:
                query = {
                    "$or": [
                        {"owner_id": ObjectId(user_id)},
                        {"scope": "public", "status": {"$in": ["usable", "certified"]}}
                    ]
                }
            else:
                query = {"scope": "public", "status": {"$in": ["usable", "certified"]}}
            
            templates = list(self.templates_collection.find(query))
            return templates
            
        except Exception as e:
            logging.error(f"Error getting available templates: {str(e)}")
            return []
    
    def _get_topic_context(self, topic_id: str) -> Dict:
        """
        Obtiene información contextual del tema.
        """
        try:
            # Obtener información del tema desde la colección topics
            topic = self.db.topics.find_one({"_id": ObjectId(topic_id)})
            if not topic:
                return {}
            
            return {
                "title": topic.get("title", ""),
                "subject": topic.get("subject", ""),
                "difficulty_level": topic.get("difficulty_level", "medium"),
                "tags": topic.get("tags", []),
                "target_audience": topic.get("target_audience", "general")
            }
            
        except Exception as e:
            logging.error(f"Error getting topic context: {str(e)}")
            return {}
    
    def _analyze_slide_content(self, slide: Dict) -> Dict:
        """
        Analiza el contenido de una diapositiva para determinar sus características.
        """
        try:
            content = slide.get("content", "")
            if isinstance(content, dict):
                content = json.dumps(content)
            elif not isinstance(content, str):
                content = str(content)
            
            analysis = {
                "content_length": len(content),
                "has_images": "img" in content.lower() or "image" in content.lower(),
                "has_code": "code" in content.lower() or "```" in content,
                "has_math": any(symbol in content for symbol in ["=", "+", "-", "*", "/", "^", "∑", "∫"]),
                "complexity": self._estimate_complexity(content),
                "main_topics": self._extract_keywords(content),
                "estimated_duration": self._estimate_reading_time(content)
            }
            
            return analysis
            
        except Exception as e:
            logging.error(f"Error analyzing slide content: {str(e)}")
            return {}
    
    def _estimate_complexity(self, content: str) -> str:
        """
        Estima la complejidad del contenido basada en longitud y características.
        """
        if len(content) < 200:
            return "low"
        elif len(content) < 800:
            return "medium"
        else:
            return "high"
    
    def _extract_keywords(self, content: str) -> List[str]:
        """
        Extrae palabras clave del contenido de la diapositiva.
        """
        # Implementación básica - en producción se podría usar NLP más avanzado
        import re
        
        # Remover HTML y caracteres especiales
        clean_content = re.sub(r'<[^>]+>', '', content)
        clean_content = re.sub(r'[^\w\s]', ' ', clean_content)
        
        # Extraer palabras de más de 4 caracteres
        words = [word.lower() for word in clean_content.split() if len(word) > 4]
        
        # Retornar las 5 palabras más comunes (simplificado)
        from collections import Counter
        common_words = Counter(words).most_common(5)
        return [word for word, count in common_words]
    
    def _estimate_reading_time(self, content: str) -> int:
        """
        Estima el tiempo de lectura en segundos.
        """
        # Promedio de 200 palabras por minuto
        word_count = len(content.split())
        reading_time_minutes = word_count / 200
        return max(30, int(reading_time_minutes * 60))  # Mínimo 30 segundos
    
    def get_template_recommendations_for_topic(self, topic_id: str, student_id: str = None) -> Tuple[bool, Dict]:
        """
        Genera recomendaciones de plantillas para cada diapositiva de un tema
        usando personalización adaptativa con RL
        
        Args:
            topic_id: ID del tema
            student_id: ID del estudiante (opcional, para personalización)
            
        Returns:
            Tuple[bool, Dict]: (éxito, recomendaciones por diapositiva)
        """
        try:
            # 1. Obtener diapositivas del tema
            slides = self._get_topic_slides(topic_id)
            if not slides:
                return False, {"error": "No se encontraron diapositivas para el tema"}
            
            # 2. Obtener plantillas disponibles
            available_templates = self._get_available_templates()
            if not available_templates:
                return False, {"error": "No hay plantillas disponibles"}
            
            # 3. Obtener contexto del tema
            topic_context = self._get_topic_context(topic_id)
            
            # 4. Obtener recomendaciones adaptativas del sistema RL si hay estudiante
            rl_recommendations = None
            if student_id:
                success, rl_result = self.personalization_service.get_adaptive_recommendations(
                    student_id=student_id,
                    topic_id=topic_id,
                    context_data={
                        "request_type": "template_recommendation",
                        "total_slides": len(slides),
                        "topic_context": topic_context
                    }
                )
                if success:
                    rl_recommendations = rl_result
                    logging.info(f"Recomendaciones RL obtenidas para estudiante {student_id}")
                else:
                    logging.warning(f"No se pudieron obtener recomendaciones RL: {rl_result.get('error')}")
            
            # 5. Obtener perfil del estudiante para análisis adicional
            student_profile = None
            if student_id:
                student_profile = self._get_student_profile(student_id)
            
            # 6. Generar recomendaciones para cada diapositiva
            recommendations = {}
            for i, slide in enumerate(slides):
                slide_recommendations = self._generate_slide_recommendations(
                    slide, available_templates, topic_context, student_profile, rl_recommendations, i
                )
                recommendations[str(slide["_id"])] = slide_recommendations
            
            return True, {
                "topic_id": topic_id,
                "total_slides": len(slides),
                "recommendations": recommendations,
                "rl_enhanced": rl_recommendations is not None,
                "confidence_score": rl_recommendations.get("confidence_score", 0.5) if rl_recommendations else 0.5,
                "generated_at": datetime.now().isoformat()
            }
            
        except Exception as e:
            logging.error(f"Error generando recomendaciones de plantillas: {str(e)}")
            return False, {"error": "Error interno del servidor", "message": str(e)}
    
    def _generate_slide_recommendations(self, slide: Dict, available_templates: List[Dict], 
                                       topic_context: Dict, student_profile: Dict = None,
                                       rl_recommendations: Dict = None, slide_index: int = 0) -> Dict:
        """
        Genera recomendaciones de plantillas para una diapositiva específica
        incorporando recomendaciones del sistema RL
        """
        try:
            # Analizar contenido de la diapositiva
            slide_analysis = self._analyze_slide_content(slide)
            
            # Calcular compatibilidad con cada plantilla
            template_scores = []
            for template in available_templates:
                compatibility_score = self._calculate_template_compatibility(
                    slide_analysis, template, topic_context, student_profile
                )
                
                # Aplicar boost del sistema RL si está disponible
                rl_boost = 0.0
                if rl_recommendations and "template_preferences" in rl_recommendations:
                    template_id = str(template["_id"])
                    rl_boost = self._calculate_rl_boost(
                        template_id, slide_index, rl_recommendations
                    )
                
                final_score = compatibility_score["total_score"] + rl_boost
                
                template_scores.append({
                    "template_id": str(template["_id"]),
                    "template_name": template["name"],
                    "compatibility_score": compatibility_score["total_score"],
                    "rl_boost": rl_boost,
                    "final_score": final_score,
                    "score_breakdown": compatibility_score["breakdown"],
                    "recommended_props": self._generate_template_props(
                        slide, template, compatibility_score
                    )
                })
            
            # Ordenar por puntuación final (compatibilidad + RL)
            template_scores.sort(key=lambda x: x["final_score"], reverse=True)
            
            # Seleccionar top 3 recomendaciones
            top_recommendations = template_scores[:3]
            
            return {
                "slide_id": str(slide["_id"]),
                "slide_title": slide.get("title", "Sin título"),
                "slide_index": slide_index,
                "slide_analysis": slide_analysis,
                "recommendations": top_recommendations,
                "total_templates_analyzed": len(available_templates),
                "rl_enhanced": rl_recommendations is not None
            }
            
        except Exception as e:
            logging.error(f"Error generating slide recommendations: {str(e)}")
            return {
                "slide_id": str(slide["_id"]),
                "error": str(e),
                "recommendations": []
            }
    
    def _calculate_compatibility_score(self, template: Dict, slide_analysis: Dict,
                                     topic_context: Dict, current_vark_balance: Dict,
                                     slide_position: int, total_slides: int) -> float:
        """
        Calcula un score de compatibilidad entre una plantilla y una diapositiva.
        """
        try:
            score = 0.0
            
            # 1. Coincidencia de tags temáticos (30%)
            template_subject_tags = set(template.get("subject_tags", []))
            topic_tags = set(topic_context.get("tags", []))
            if template_subject_tags and topic_tags:
                tag_overlap = len(template_subject_tags.intersection(topic_tags))
                tag_score = tag_overlap / max(len(template_subject_tags), len(topic_tags))
                score += tag_score * 0.3
            
            # 2. Balance VARK (25%)
            template_vark = template.get("baseline_mix", {})
            vark_score = self._calculate_vark_balance_score(template_vark, current_vark_balance)
            score += vark_score * 0.25
            
            # 3. Complejidad apropiada (20%)
            slide_complexity = slide_analysis.get("complexity", "medium")
            complexity_score = self._calculate_complexity_match(template, slide_complexity)
            score += complexity_score * 0.2
            
            # 4. Duración apropiada (15%)
            slide_duration = slide_analysis.get("estimated_duration", 60)
            template_duration = self._estimate_template_duration(template)
            duration_score = self._calculate_duration_match(slide_duration, template_duration)
            score += duration_score * 0.15
            
            # 5. Posición en secuencia (10%)
            position_score = self._calculate_position_score(template, slide_position, total_slides)
            score += position_score * 0.1
            
            return min(1.0, score)  # Normalizar a [0, 1]
            
        except Exception as e:
            logging.error(f"Error calculating compatibility score: {str(e)}")
            return 0.0
    
    def _calculate_vark_balance_score(self, template_vark: Dict, current_balance: Dict) -> float:
        """
        Calcula score basado en balance VARK para promover variedad.
        """
        try:
            if not template_vark or not current_balance:
                return 0.5  # Score neutro
            
            # Encontrar el estilo menos usado hasta ahora
            min_used_style = min(current_balance.values())
            
            # Premiar plantillas que fortalezcan estilos poco usados
            template_max_style = max(template_vark.values())
            template_dominant_style = max(template_vark, key=template_vark.get)
            
            if current_balance.get(template_dominant_style, 0) == min_used_style:
                return 1.0  # Excelente balance
            elif current_balance.get(template_dominant_style, 0) < sum(current_balance.values()) / 4:
                return 0.8  # Buen balance
            else:
                return 0.3  # Balance regular
                
        except Exception as e:
            logging.error(f"Error calculating VARK balance score: {str(e)}")
            return 0.5
    
    def _calculate_complexity_match(self, template: Dict, slide_complexity: str) -> float:
        """
        Calcula compatibilidad basada en complejidad.
        """
        # Inferir complejidad de la plantilla basada en sus características
        template_html = template.get("html", "")
        if isinstance(template.get("versions"), list) and template["versions"]:
            template_html = template["versions"][-1].get("html", "")
        
        template_complexity = "low"
        if len(template_html) > 1000 or "javascript" in template_html.lower():
            template_complexity = "high"
        elif len(template_html) > 500:
            template_complexity = "medium"
        
        # Matriz de compatibilidad
        compatibility_matrix = {
            ("low", "low"): 1.0,
            ("low", "medium"): 0.7,
            ("low", "high"): 0.3,
            ("medium", "low"): 0.8,
            ("medium", "medium"): 1.0,
            ("medium", "high"): 0.8,
            ("high", "low"): 0.4,
            ("high", "medium"): 0.7,
            ("high", "high"): 1.0
        }
        
        return compatibility_matrix.get((slide_complexity, template_complexity), 0.5)
    
    def _calculate_duration_match(self, slide_duration: int, template_duration: int) -> float:
        """
        Calcula compatibilidad basada en duración estimada.
        """
        # Duración total no debe exceder 5 minutos por diapositiva
        total_duration = slide_duration + template_duration
        if total_duration > 300:  # 5 minutos
            return 0.2
        elif total_duration > 180:  # 3 minutos
            return 0.6
        else:
            return 1.0
    
    def _calculate_position_score(self, template: Dict, position: int, total_slides: int) -> float:
        """
        Calcula score basado en la posición de la diapositiva en la secuencia.
        """
        # Plantillas más interactivas al final, más informativas al principio
        template_style_tags = template.get("style_tags", [])
        
        if position <= total_slides * 0.3:  # Primeras diapositivas
            if "informative" in template_style_tags or "theoretical" in template_style_tags:
                return 1.0
            elif "interactive" in template_style_tags:
                return 0.6
        elif position >= total_slides * 0.7:  # Últimas diapositivas
            if "interactive" in template_style_tags or "game" in template_style_tags:
                return 1.0
            elif "assessment" in template_style_tags:
                return 0.9
        else:  # Diapositivas del medio
            return 0.8  # Score neutro
        
        return 0.7  # Score por defecto
    
    def _estimate_template_duration(self, template: Dict) -> int:
        """
        Estima la duración de una plantilla en segundos.
        """
        # Estimación básica basada en complejidad y tipo
        style_tags = template.get("style_tags", [])
        
        if "game" in style_tags:
            return 120  # 2 minutos
        elif "quiz" in style_tags:
            return 90   # 1.5 minutos
        elif "simulation" in style_tags:
            return 180  # 3 minutos
        else:
            return 60   # 1 minuto por defecto
    
    def _generate_reasoning(self, template: Dict, slide_analysis: Dict, score: float) -> str:
        """
        Genera una explicación de por qué se recomienda esta plantilla.
        """
        reasons = []
        
        if score > 0.8:
            reasons.append("Excelente compatibilidad")
        elif score > 0.6:
            reasons.append("Buena compatibilidad")
        else:
            reasons.append("Compatibilidad moderada")
        
        style_tags = template.get("style_tags", [])
        if "interactive" in style_tags:
            reasons.append("contenido interactivo")
        if "visual" in style_tags:
            reasons.append("enfoque visual")
        if "game" in style_tags:
            reasons.append("gamificación")
        
        return ", ".join(reasons)
    
    def apply_recommendations(self, topic_id: str, recommendations: Dict[str, List[Dict]], 
                            user_id: str) -> Tuple[bool, str]:
        """
        Aplica las recomendaciones seleccionadas creando instancias de plantillas.
        
        Args:
            topic_id: ID del tema
            recommendations: Diccionario con recomendaciones por slide_id
            user_id: ID del usuario
            
        Returns:
            Tuple[bool, str]: (éxito, mensaje)
        """
        try:
            created_instances = 0
            
            for slide_id, slide_recommendations in recommendations.items():
                for rec in slide_recommendations:
                    if rec.get("selected", False):
                        # Crear instancia de plantilla
                        success, result = self.template_service.create_content_instance(
                            template_id=rec["template_id"],
                            parent_content_id=slide_id,
                            topic_id=topic_id,
                            creator_id=user_id,
                            instance_props={}
                        )
                        
                        if success:
                            created_instances += 1
                            logging.info(f"Created template instance for slide {slide_id}")
                        else:
                            logging.warning(f"Failed to create instance for slide {slide_id}: {result}")
            
            if created_instances > 0:
                return True, f"Se crearon {created_instances} instancias de plantillas"
            else:
                return False, "No se crearon instancias de plantillas"
                
        except Exception as e:
            logging.error(f"Error applying recommendations: {str(e)}")
            return False, f"Error aplicando recomendaciones: {str(e)}"
    
    def submit_template_feedback(self, student_id: str, topic_id: str, slide_id: str, 
                               template_id: str, feedback_data: Dict) -> Tuple[bool, str]:
        """
        Envía feedback sobre el uso de una plantilla al sistema RL para mejorar futuras recomendaciones.
        
        Args:
            student_id: ID del estudiante
            topic_id: ID del tema
            slide_id: ID de la diapositiva
            template_id: ID de la plantilla utilizada
            feedback_data: Datos de feedback (tiempo, interacciones, completitud, etc.)
            
        Returns:
            Tuple[bool, str]: (éxito, mensaje)
        """
        try:
            # Preparar datos de feedback para el sistema RL
            rl_feedback = {
                "student_id": student_id,
                "topic_id": topic_id,
                "slide_id": slide_id,
                "template_id": template_id,
                "feedback_type": "template_usage",
                "engagement_score": feedback_data.get("engagement_score", 0.5),
                "completion_time": feedback_data.get("completion_time", 0),
                "interaction_count": feedback_data.get("interaction_count", 0),
                "completion_rate": feedback_data.get("completion_rate", 0.0),
                "difficulty_rating": feedback_data.get("difficulty_rating", 3),
                "satisfaction_score": feedback_data.get("satisfaction_score", 0.5),
                "timestamp": datetime.now().isoformat()
            }
            
            # Enviar feedback al sistema de personalización adaptativa
            success, result = self.personalization_service.submit_learning_feedback(
                student_id=student_id,
                feedback_data=rl_feedback
            )
            
            if success:
                logging.info(f"Feedback de plantilla enviado exitosamente para estudiante {student_id}")
                return True, "Feedback enviado exitosamente"
            else:
                logging.warning(f"Error enviando feedback de plantilla: {result}")
                return False, f"Error enviando feedback: {result}"
                
        except Exception as e:
            logging.error(f"Error submitting template feedback: {str(e)}")
            return False, f"Error enviando feedback: {str(e)}"
    
    def _get_student_profile(self, student_id: str) -> Dict:
        """
        Obtiene el perfil del estudiante para personalización.
        """
        try:
            student = self.db.students.find_one({"_id": ObjectId(student_id)})
            if not student:
                return {}
            
            return {
                "learning_style": student.get("learning_style", {}),
                "performance_history": student.get("performance_history", []),
                "preferences": student.get("preferences", {}),
                "difficulty_level": student.get("difficulty_level", "medium")
            }
            
        except Exception as e:
            logging.error(f"Error getting student profile: {str(e)}")
            return {}