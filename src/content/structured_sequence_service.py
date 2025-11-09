from typing import List, Dict, Optional, Tuple
from datetime import datetime
import logging
from bson import ObjectId
from pymongo.database import Database
from src.content.models import ContentTypes

class StructuredSequenceService:
    """
    Servicio para manejar la secuencia estructurada de contenidos:
    diapositivas → contenidos opcionales → evaluación
    
    Reemplaza el sistema de intercalación aleatoria con una secuencia predecible y estructurada.
    """
    
    def __init__(self, db: Database):
        self.db = db
        self.collection = db.topic_contents
        
    def get_structured_content_sequence(self, topic_id: str, student_id: str = None) -> List[Dict]:
        """
        Obtiene la secuencia estructurada de contenidos para un tema.
        
        Secuencia:
        1. Diapositivas individuales (content_type='slide') en orden secuencial
        2. Contenidos opcionales asociados a cada diapositiva (parent_content_id)
        3. Contenidos de evaluación al final
        
        Args:
            topic_id: ID del tema
            student_id: ID del estudiante (para personalización futura)
            
        Returns:
            Lista ordenada de contenidos siguiendo la secuencia estructurada
        """
        try:
            # 1. Obtener todas las diapositivas ordenadas
            slides = self._get_slides_in_order(topic_id)
            
            # 2. Obtener contenidos opcionales asociados a diapositivas
            optional_contents = self._get_optional_contents(topic_id)
            
            # 3. Obtener contenidos de evaluación
            evaluation_contents = self._get_evaluation_contents(topic_id)
            
            # 4. Construir secuencia estructurada
            structured_sequence = []
            
            # Insertar diapositivas con sus contenidos opcionales
            for slide in slides:
                # Agregar la diapositiva
                structured_sequence.append(slide)
                
                # Agregar contenidos opcionales asociados a esta diapositiva
                slide_id = slide["_id"]
                associated_contents = [
                    content for content in optional_contents 
                    if content.get("parent_content_id") == slide_id
                ]
                
                # Ordenar contenidos asociados por order si existe
                associated_contents.sort(key=lambda x: x.get("order", 999))

                parent_order = slide.get("order")
                if parent_order is None:
                    # Si la diapositiva no tiene order explícito, calcularlo a partir de la posición actual
                    parent_order = len(structured_sequence)

                for idx, content in enumerate(associated_contents):
                    try:
                        base_order = float(parent_order)
                    except (TypeError, ValueError):
                        base_order = float(len(structured_sequence))
                    # Insertar inmediatamente después de la diapositiva usando fracciones
                    intercalated_order = base_order + (idx + 1) / 100.0
                    content["order"] = intercalated_order
                    content["_intercalated_parent_order"] = base_order

                structured_sequence.extend(associated_contents)
            
            # Agregar contenidos de evaluación al final
            evaluation_contents.sort(key=lambda x: x.get("order", 999))
            structured_sequence.extend(evaluation_contents)
            
            logging.info(f"Secuencia estructurada generada: {len(structured_sequence)} contenidos para tema {topic_id}")
            return structured_sequence
            
        except Exception as e:
            logging.error(f"Error generando secuencia estructurada: {str(e)}")
            return []
    
    def _get_slides_in_order(self, topic_id: str) -> List[Dict]:
        """
        Obtiene todas las diapositivas individuales ordenadas por el campo 'order'.
        """
        try:
            query = {
                "topic_id": ObjectId(topic_id),
                "content_type": ContentTypes.SLIDE,
                "status": {"$in": ["draft", "active", "published", "narrative_ready", "skeleton", "html_ready"]}
            }
            
            slides = list(self.collection.find(query).sort("order", 1))
            
            # Convertir ObjectIds a strings
            for slide in slides:
                slide["_id"] = str(slide["_id"])
                slide["topic_id"] = str(slide["topic_id"])
                if slide.get("creator_id"):
                    slide["creator_id"] = str(slide["creator_id"])
                if slide.get("parent_content_id"):
                    slide["parent_content_id"] = str(slide["parent_content_id"])
            
            return slides
            
        except Exception as e:
            logging.error(f"Error obteniendo diapositivas: {str(e)}")
            return []
    
    def _get_optional_contents(self, topic_id: str) -> List[Dict]:
        """
        Obtiene contenidos opcionales que están asociados a diapositivas (tienen parent_content_id).
        """
        try:
            # Tipos de contenido que pueden ser opcionales (no diapositivas ni evaluaciones)
            optional_types = [
                ContentTypes.TEXT, ContentTypes.FEYNMAN, ContentTypes.STORY,
                ContentTypes.EXAMPLES, ContentTypes.DIAGRAM, ContentTypes.INFOGRAPHIC,
                ContentTypes.VIDEO, ContentTypes.AUDIO, ContentTypes.GAME,
                ContentTypes.SIMULATION, ContentTypes.INTERACTIVE_EXERCISE,
                ContentTypes.FLASHCARDS, ContentTypes.MINI_GAME
            ]
            
            query = {
                "topic_id": ObjectId(topic_id),
                "content_type": {"$in": optional_types},
                "parent_content_id": {"$exists": True, "$ne": None},
                "status": {"$in": ["draft", "active", "published", "narrative_ready", "skeleton", "html_ready"]}
            }
            
            contents = list(self.collection.find(query))
            
            # Convertir ObjectIds a strings
            for content in contents:
                content["_id"] = str(content["_id"])
                content["topic_id"] = str(content["topic_id"])
                if content.get("creator_id"):
                    content["creator_id"] = str(content["creator_id"])
                if content.get("parent_content_id"):
                    content["parent_content_id"] = str(content["parent_content_id"])
            
            return contents
            
        except Exception as e:
            logging.error(f"Error obteniendo contenidos opcionales: {str(e)}")
            return []
    
    def _get_evaluation_contents(self, topic_id: str) -> List[Dict]:
        """
        Obtiene contenidos de evaluación que van al final de la secuencia.
        """
        try:
            evaluation_types = [
                ContentTypes.QUIZ, ContentTypes.EXAM, ContentTypes.PROJECT,
                ContentTypes.FORMATIVE_TEST, ContentTypes.PEER_REVIEW,
                ContentTypes.PORTFOLIO, ContentTypes.RUBRIC
            ]
            
            query = {
                "topic_id": ObjectId(topic_id),
                "content_type": {"$in": evaluation_types},
                "status": {"$in": ["draft", "active", "published", "narrative_ready", "skeleton", "html_ready"]}
            }
            
            contents = list(self.collection.find(query))
            
            # Convertir ObjectIds a strings
            for content in contents:
                content["_id"] = str(content["_id"])
                content["topic_id"] = str(content["topic_id"])
                if content.get("creator_id"):
                    content["creator_id"] = str(content["creator_id"])
                if content.get("parent_content_id"):
                    content["parent_content_id"] = str(content["parent_content_id"])
            
            return contents
            
        except Exception as e:
            logging.error(f"Error obteniendo contenidos de evaluación: {str(e)}")
            return []
    
    def validate_sequence_integrity(self, topic_id: str) -> Tuple[bool, List[str]]:
        """
        Valida la integridad de la secuencia estructurada.
        
        Verifica:
        - Que existan diapositivas con orden secuencial
        - Que los parent_content_id apunten a diapositivas válidas
        - Que no haya gaps en la numeración de orden
        
        Returns:
            Tuple[bool, List[str]]: (es_válida, lista_de_errores)
        """
        try:
            errors = []
            
            # 1. Verificar que existan diapositivas
            slides = self._get_slides_in_order(topic_id)
            if not slides:
                errors.append("No se encontraron diapositivas para el tema")
                return False, errors
            
            # 2. Verificar orden secuencial de diapositivas
            slide_orders = [slide.get("order", 0) for slide in slides]
            slide_orders.sort()
            
            for i, order in enumerate(slide_orders):
                expected_order = i + 1  # Orden esperado: 1, 2, 3...
                if order != expected_order:
                    errors.append(f"Gap en orden de diapositivas: esperado {expected_order}, encontrado {order}")
            
            # 3. Verificar parent_content_id válidos
            slide_ids = {slide["_id"] for slide in slides}
            optional_contents = self._get_optional_contents(topic_id)
            
            for content in optional_contents:
                parent_id = content.get("parent_content_id")
                if parent_id and parent_id not in slide_ids:
                    errors.append(f"Contenido {content['_id']} tiene parent_content_id inválido: {parent_id}")
            
            # 4. Verificar que no haya contenidos huérfanos de tipo slide
            orphan_slides = self.collection.find({
                "topic_id": ObjectId(topic_id),
                "content_type": ContentTypes.SLIDE,
                "order": {"$exists": False},
                "status": {"$in": ["draft", "active", "published", "narrative_ready", "skeleton", "html_ready"]}
            })
            
            orphan_count = orphan_slides.count()
            if orphan_count > 0:
                errors.append(f"Se encontraron {orphan_count} diapositivas sin orden definido")
            
            is_valid = len(errors) == 0
            return is_valid, errors
            
        except Exception as e:
            logging.error(f"Error validando integridad de secuencia: {str(e)}")
            return False, [f"Error interno: {str(e)}"]
    
    def reorder_slides(self, topic_id: str, slide_order_mapping: Dict[str, int]) -> Tuple[bool, str]:
        """
        Reordena las diapositivas según un mapeo de ID a orden.
        
        Args:
            topic_id: ID del tema
            slide_order_mapping: Dict {slide_id: new_order}
            
        Returns:
            Tuple[bool, str]: (éxito, mensaje)
        """
        try:
            updated_count = 0
            
            for slide_id, new_order in slide_order_mapping.items():
                result = self.collection.update_one(
                    {
                        "_id": ObjectId(slide_id),
                        "topic_id": ObjectId(topic_id),
                        "content_type": ContentTypes.SLIDE
                    },
                    {
                        "$set": {
                            "order": new_order,
                            "updated_at": datetime.now()
                        }
                    }
                )
                
                if result.modified_count > 0:
                    updated_count += 1
            
            if updated_count > 0:
                return True, f"Se reordenaron {updated_count} diapositivas exitosamente"
            else:
                return False, "No se pudo reordenar ninguna diapositiva"
                
        except Exception as e:
            logging.error(f"Error reordenando diapositivas: {str(e)}")
            return False, f"Error interno: {str(e)}"
    
    def get_sequence_statistics(self, topic_id: str) -> Dict:
        """
        Obtiene estadísticas de la secuencia estructurada.
        
        Returns:
            Dict con estadísticas de la secuencia
        """
        try:
            slides = self._get_slides_in_order(topic_id)
            optional_contents = self._get_optional_contents(topic_id)
            evaluation_contents = self._get_evaluation_contents(topic_id)
            
            # Contar contenidos opcionales por diapositiva
            slide_content_count = {}
            for content in optional_contents:
                parent_id = content.get("parent_content_id")
                if parent_id:
                    slide_content_count[parent_id] = slide_content_count.get(parent_id, 0) + 1
            
            return {
                "total_slides": len(slides),
                "total_optional_contents": len(optional_contents),
                "total_evaluation_contents": len(evaluation_contents),
                "total_sequence_length": len(slides) + len(optional_contents) + len(evaluation_contents),
                "slides_with_optional_content": len(slide_content_count),
                "avg_optional_contents_per_slide": (
                    sum(slide_content_count.values()) / len(slide_content_count)
                    if slide_content_count else 0
                ),
                "slide_content_distribution": slide_content_count
            }
            
        except Exception as e:
            logging.error(f"Error obteniendo estadísticas de secuencia: {str(e)}")
            return {}
