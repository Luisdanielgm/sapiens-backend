from typing import List, Dict, Optional, Tuple, Any
from datetime import datetime
import logging
from bson import ObjectId
from pymongo.database import Database
from src.content.models import ContentTypes, TopicContent

class EmbeddedContentService:
    """
    Servicio para manejar contenido embebido vs separado en diapositivas.
    
    Funcionalidades:
    - Determinar si un contenido debe ser embebido o separado
    - Gestionar la inserción de contenido embebido en diapositivas
    - Manejar la secuencia de contenidos separados
    - Optimizar la experiencia de aprendizaje según el tipo de contenido
    """
    
    def __init__(self, db: Database):
        self.db = db
        self.collection = db.topic_contents
        
        # Tipos de contenido que pueden ser embebidos
        self.embeddable_types = {
            ContentTypes.TEXT: {'max_length': 500, 'embed_priority': 'high'},
            ContentTypes.EXAMPLES: {'max_length': 300, 'embed_priority': 'high'},
            ContentTypes.DIAGRAM: {'max_length': None, 'embed_priority': 'medium'},
            ContentTypes.INFOGRAPHIC: {'max_length': None, 'embed_priority': 'low'},
            ContentTypes.FLASHCARDS: {'max_length': None, 'embed_priority': 'medium'},
            ContentTypes.INTERACTIVE_EXERCISE: {'max_length': None, 'embed_priority': 'low'}
        }
        
        # Tipos que siempre deben ser separados
        self.separate_only_types = {
            ContentTypes.VIDEO, ContentTypes.AUDIO, ContentTypes.GAME,
            ContentTypes.SIMULATION, ContentTypes.QUIZ, ContentTypes.EXAM,
            ContentTypes.PROJECT, ContentTypes.MINI_GAME
        }
    
    def analyze_content_embedding_strategy(self, slide_id: str, content_id: str) -> Dict[str, Any]:
        """
        Analiza si un contenido debe ser embebido o separado de una diapositiva.
        
        Args:
            slide_id: ID de la diapositiva
            content_id: ID del contenido a analizar
            
        Returns:
            Dict con la estrategia recomendada y razones
        """
        try:
            # Obtener información del contenido
            content = self.collection.find_one({"_id": ObjectId(content_id)})
            if not content:
                return {'strategy': 'error', 'reason': 'Contenido no encontrado'}
            
            slide = self.collection.find_one({"_id": ObjectId(slide_id)})
            if not slide:
                return {'strategy': 'error', 'reason': 'Diapositiva no encontrada'}
            
            content_type = content.get('content_type')
            content_data = content.get('content', {})
            
            # Verificar si el tipo puede ser embebido
            if content_type in self.separate_only_types:
                return {
                    'strategy': 'separate',
                    'reason': f'Tipo {content_type} requiere presentación separada',
                    'confidence': 1.0
                }
            
            if content_type not in self.embeddable_types:
                return {
                    'strategy': 'separate',
                    'reason': f'Tipo {content_type} no soporta embedding',
                    'confidence': 0.8
                }
            
            # Analizar características del contenido
            embed_config = self.embeddable_types[content_type]
            analysis = self._analyze_content_characteristics(content_data, embed_config)
            
            # Analizar la diapositiva actual
            slide_analysis = self._analyze_slide_capacity(slide)
            
            # Determinar estrategia final
            strategy = self._determine_embedding_strategy(analysis, slide_analysis, embed_config)
            
            return strategy
            
        except Exception as e:
            logging.error(f"Error analizando estrategia de embedding: {str(e)}")
            return {'strategy': 'error', 'reason': f'Error interno: {str(e)}'}
    
    def _analyze_content_characteristics(self, content_data: Any, embed_config: Dict) -> Dict:
        """
        Analiza las características del contenido para determinar si es apto para embedding.
        """
        analysis = {
            'size_score': 0.0,
            'complexity_score': 0.0,
            'interactivity_score': 0.0
        }
        
        # Analizar tamaño del contenido
        if isinstance(content_data, str):
            content_length = len(content_data)
            max_length = embed_config.get('max_length')
            
            if max_length:
                analysis['size_score'] = max(0, 1 - (content_length / max_length))
            else:
                analysis['size_score'] = 0.5  # Neutral para contenido sin límite
        
        elif isinstance(content_data, dict):
            # Analizar complejidad estructural
            nested_levels = self._count_nested_levels(content_data)
            analysis['complexity_score'] = max(0, 1 - (nested_levels / 5))  # Máximo 5 niveles
            
            # Verificar interactividad
            if any(key in content_data for key in ['interactive', 'buttons', 'inputs', 'quiz']):
                analysis['interactivity_score'] = 0.3  # Reduce aptitud para embedding
            else:
                analysis['interactivity_score'] = 0.8
        
        return analysis
    
    def _analyze_slide_capacity(self, slide: Dict) -> Dict:
        """
        Analiza la capacidad de la diapositiva para aceptar contenido embebido.
        """
        slide_content = slide.get('content', {})
        
        analysis = {
            'current_density': 0.0,
            'available_space': 1.0,
            'layout_compatibility': 0.5
        }
        
        # Estimar densidad actual del contenido
        if isinstance(slide_content, str):
            content_length = len(slide_content)
            analysis['current_density'] = min(1.0, content_length / 1000)  # Normalizar a 1000 chars
        
        elif isinstance(slide_content, dict):
            # Contar elementos en la diapositiva
            element_count = len(slide_content.keys())
            analysis['current_density'] = min(1.0, element_count / 10)  # Máximo 10 elementos
        
        # Calcular espacio disponible
        analysis['available_space'] = max(0, 1 - analysis['current_density'])
        
        # Verificar compatibilidad de layout
        slide_template = slide.get('slide_template', {})
        if slide_template.get('supports_embedding', False):
            analysis['layout_compatibility'] = 1.0
        elif slide_template.get('layout') in ['two-column', 'sidebar']:
            analysis['layout_compatibility'] = 0.8
        
        return analysis
    
    def _determine_embedding_strategy(self, content_analysis: Dict, slide_analysis: Dict, embed_config: Dict) -> Dict:
        """
        Determina la estrategia final de embedding basada en los análisis.
        """
        # Calcular puntuación de embedding
        embed_score = (
            content_analysis['size_score'] * 0.3 +
            content_analysis['complexity_score'] * 0.2 +
            content_analysis['interactivity_score'] * 0.2 +
            slide_analysis['available_space'] * 0.2 +
            slide_analysis['layout_compatibility'] * 0.1
        )
        
        # Aplicar prioridad del tipo de contenido
        priority_multiplier = {
            'high': 1.2,
            'medium': 1.0,
            'low': 0.8
        }.get(embed_config.get('embed_priority', 'medium'), 1.0)
        
        final_score = embed_score * priority_multiplier
        
        # Determinar estrategia
        if final_score >= 0.7:
            strategy = 'embed'
            reason = 'Contenido óptimo para embedding'
        elif final_score >= 0.4:
            strategy = 'conditional_embed'
            reason = 'Embedding posible con ajustes'
        else:
            strategy = 'separate'
            reason = 'Mejor experiencia como contenido separado'
        
        return {
            'strategy': strategy,
            'reason': reason,
            'confidence': final_score,
            'embed_score': embed_score,
            'priority_multiplier': priority_multiplier,
            'analysis_details': {
                'content': content_analysis,
                'slide': slide_analysis
            }
        }
    
    def embed_content_in_slide(self, slide_id: str, content_id: str, embed_position: str = 'bottom') -> Tuple[bool, str]:
        """
        Embebe un contenido dentro de una diapositiva.
        
        Args:
            slide_id: ID de la diapositiva
            content_id: ID del contenido a embeber
            embed_position: Posición donde embeber ('top', 'bottom', 'sidebar')
            
        Returns:
            Tuple[bool, str]: (éxito, mensaje)
        """
        try:
            # Verificar estrategia de embedding
            strategy = self.analyze_content_embedding_strategy(slide_id, content_id)
            
            if strategy['strategy'] == 'error':
                return False, strategy['reason']
            
            if strategy['strategy'] == 'separate':
                return False, f"Contenido no apto para embedding: {strategy['reason']}"
            
            # Obtener contenidos
            slide = self.collection.find_one({"_id": ObjectId(slide_id)})
            content = self.collection.find_one({"_id": ObjectId(content_id)})
            
            if not slide or not content:
                return False, "Diapositiva o contenido no encontrado"
            
            # Crear estructura embebida
            embedded_structure = self._create_embedded_structure(
                slide.get('content', {}),
                content.get('content', {}),
                content.get('content_type'),
                embed_position
            )
            
            # Actualizar diapositiva
            result = self.collection.update_one(
                {"_id": ObjectId(slide_id)},
                {
                    "$set": {
                        "content": embedded_structure,
                        "updated_at": datetime.now()
                    },
                    "$addToSet": {
                        "embedded_content_ids": ObjectId(content_id)
                    }
                }
            )
            
            if result.modified_count > 0:
                # Marcar contenido como embebido
                self.collection.update_one(
                    {"_id": ObjectId(content_id)},
                    {
                        "$set": {
                            "status": "embedded",
                            "embedded_in_slide": ObjectId(slide_id),
                            "updated_at": datetime.now()
                        }
                    }
                )
                
                return True, "Contenido embebido exitosamente"
            else:
                return False, "No se pudo actualizar la diapositiva"
                
        except Exception as e:
            logging.error(f"Error embebiendo contenido: {str(e)}")
            return False, f"Error interno: {str(e)}"
    
    def _create_embedded_structure(self, slide_content: Dict, embed_content: Any, content_type: str, position: str) -> Dict:
        """
        Crea la estructura de contenido embebido.
        """
        # Estructura base de la diapositiva
        if not isinstance(slide_content, dict):
            slide_content = {'main_content': slide_content}
        
        # Preparar contenido a embeber
        embedded_section = {
            'type': content_type,
            'content': embed_content,
            'embedded_at': datetime.now().isoformat(),
            'position': position
        }
        
        # Insertar según posición
        if position == 'top':
            slide_content['embedded_top'] = embedded_section
        elif position == 'bottom':
            slide_content['embedded_bottom'] = embedded_section
        elif position == 'sidebar':
            slide_content['embedded_sidebar'] = embedded_section
        else:
            # Posición por defecto
            slide_content['embedded_content'] = embedded_section
        
        return slide_content
    
    def extract_embedded_content(self, slide_id: str, content_id: str) -> Tuple[bool, str]:
        """
        Extrae un contenido embebido y lo convierte en contenido separado.
        
        Args:
            slide_id: ID de la diapositiva
            content_id: ID del contenido a extraer
            
        Returns:
            Tuple[bool, str]: (éxito, mensaje)
        """
        try:
            slide = self.collection.find_one({"_id": ObjectId(slide_id)})
            if not slide:
                return False, "Diapositiva no encontrada"
            
            slide_content = slide.get('content', {})
            
            # Buscar y remover contenido embebido
            extracted_content = None
            updated_content = slide_content.copy()
            
            for position in ['embedded_top', 'embedded_bottom', 'embedded_sidebar', 'embedded_content']:
                if position in updated_content:
                    embedded_section = updated_content[position]
                    if str(content_id) in str(embedded_section):  # Búsqueda aproximada
                        extracted_content = embedded_section
                        del updated_content[position]
                        break
            
            if not extracted_content:
                return False, "Contenido embebido no encontrado en la diapositiva"
            
            # Actualizar diapositiva
            self.collection.update_one(
                {"_id": ObjectId(slide_id)},
                {
                    "$set": {
                        "content": updated_content,
                        "updated_at": datetime.now()
                    },
                    "$pull": {
                        "embedded_content_ids": ObjectId(content_id)
                    }
                }
            )
            
            # Restaurar contenido como separado
            self.collection.update_one(
                {"_id": ObjectId(content_id)},
                {
                    "$set": {
                        "status": "active",
                        "updated_at": datetime.now()
                    },
                    "$unset": {
                        "embedded_in_slide": ""
                    }
                }
            )
            
            return True, "Contenido extraído y convertido a separado exitosamente"
            
        except Exception as e:
            logging.error(f"Error extrayendo contenido embebido: {str(e)}")
            return False, f"Error interno: {str(e)}"
    
    def get_embedding_recommendations(self, topic_id: str) -> List[Dict]:
        """
        Obtiene recomendaciones de embedding para todos los contenidos de un tema.
        
        Args:
            topic_id: ID del tema
            
        Returns:
            Lista de recomendaciones de embedding
        """
        try:
            recommendations = []
            
            # Obtener todas las diapositivas del tema
            slides = list(self.collection.find({
                "topic_id": ObjectId(topic_id),
                "content_type": ContentTypes.SLIDE,
                "status": {"$in": ["draft", "active", "published"]}
            }).sort("order", 1))
            
            # Obtener contenidos opcionales
            optional_contents = list(self.collection.find({
                "topic_id": ObjectId(topic_id),
                "parent_content_id": {"$exists": True, "$ne": None},
                "status": {"$in": ["draft", "active", "published"]}
            }))
            
            # Analizar cada combinación diapositiva-contenido
            for slide in slides:
                slide_id = str(slide["_id"])
                
                # Contenidos asociados a esta diapositiva
                associated_contents = [
                    content for content in optional_contents
                    if str(content.get("parent_content_id")) == slide_id
                ]
                
                for content in associated_contents:
                    content_id = str(content["_id"])
                    strategy = self.analyze_content_embedding_strategy(slide_id, content_id)
                    
                    recommendations.append({
                        "slide_id": slide_id,
                        "slide_title": slide.get("content", {}).get("title", f"Diapositiva {slide.get('order', '?')}"),
                        "content_id": content_id,
                        "content_type": content.get("content_type"),
                        "strategy": strategy["strategy"],
                        "reason": strategy["reason"],
                        "confidence": strategy.get("confidence", 0.0),
                        "recommended_position": self._suggest_embed_position(strategy)
                    })
            
            return recommendations
            
        except Exception as e:
            logging.error(f"Error obteniendo recomendaciones de embedding: {str(e)}")
            return []
    
    def _suggest_embed_position(self, strategy: Dict) -> str:
        """
        Sugiere la mejor posición para embeber contenido basada en el análisis.
        """
        if strategy["strategy"] not in ["embed", "conditional_embed"]:
            return "none"
        
        slide_analysis = strategy.get("analysis_details", {}).get("slide", {})
        
        # Lógica simple de posicionamiento
        if slide_analysis.get("layout_compatibility", 0) > 0.8:
            return "sidebar"
        elif slide_analysis.get("available_space", 0) > 0.6:
            return "bottom"
        else:
            return "top"
    
    def _count_nested_levels(self, data: Dict, current_level: int = 0) -> int:
        """
        Cuenta los niveles de anidamiento en una estructura de datos.
        """
        if not isinstance(data, dict):
            return current_level
        
        max_level = current_level
        for value in data.values():
            if isinstance(value, dict):
                level = self._count_nested_levels(value, current_level + 1)
                max_level = max(max_level, level)
        
        return max_level
    
    def get_embedding_statistics(self, topic_id: str) -> Dict:
        """
        Obtiene estadísticas de embedding para un tema.
        
        Args:
            topic_id: ID del tema
            
        Returns:
            Dict con estadísticas de embedding
        """
        try:
            # Contar contenidos por estado de embedding
            embedded_count = self.collection.count_documents({
                "topic_id": ObjectId(topic_id),
                "status": "embedded"
            })
            
            separate_count = self.collection.count_documents({
                "topic_id": ObjectId(topic_id),
                "parent_content_id": {"$exists": True, "$ne": None},
                "status": {"$in": ["draft", "active", "published"]}
            })
            
            total_slides = self.collection.count_documents({
                "topic_id": ObjectId(topic_id),
                "content_type": ContentTypes.SLIDE,
                "status": {"$in": ["draft", "active", "published"]}
            })
            
            return {
                "total_slides": total_slides,
                "embedded_contents": embedded_count,
                "separate_contents": separate_count,
                "total_optional_contents": embedded_count + separate_count,
                "embedding_ratio": embedded_count / (embedded_count + separate_count) if (embedded_count + separate_count) > 0 else 0,
                "avg_contents_per_slide": (embedded_count + separate_count) / total_slides if total_slides > 0 else 0
            }
            
        except Exception as e:
            logging.error(f"Error obteniendo estadísticas de embedding: {str(e)}")
            return {}