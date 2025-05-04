from typing import Tuple, List, Dict, Optional, Union
from bson import ObjectId
from datetime import datetime
import logging

from src.shared.database import get_db
from src.shared.constants import STATUS
from src.shared.standardization import VerificationBaseService, ErrorCodes
from src.shared.exceptions import AppException
from .models import Game, VirtualGame, GameTemplate, GameResult

class GameService(VerificationBaseService):
    def __init__(self):
        super().__init__(collection_name="games")

    def check_topic_exists(self, topic_id: str) -> bool:
        """
        Verifica si un tema existe.
        
        Args:
            topic_id: ID del tema a verificar
            
        Returns:
            bool: True si el tema existe, False en caso contrario
        """
        try:
            topic = get_db().topics.find_one({"_id": ObjectId(topic_id)})
            return topic is not None
        except Exception:
            return False
            
    def check_game_exists(self, game_id: str) -> bool:
        """
        Verifica si un juego existe.
        
        Args:
            game_id: ID del juego a verificar
            
        Returns:
            bool: True si el juego existe, False en caso contrario
        """
        try:
            game = self.collection.find_one({"_id": ObjectId(game_id)})
            return game is not None
        except Exception:
            return False

    def create_game(self, game_data: dict) -> Tuple[bool, str]:
        try:
            # Verificar que el tema existe
            if not self.check_topic_exists(game_data['topic_id']):
                return False, "Tema no encontrado"

            game = Game(**game_data)
            result = self.collection.insert_one(game.to_dict())
            return True, str(result.inserted_id)
        except Exception as e:
            return False, str(e)

    def get_game(self, game_id: str) -> Optional[Dict]:
        try:
            game = self.collection.find_one({"_id": ObjectId(game_id)})
            if not game:
                return None
            
            # Convertir ObjectId a string
            game["_id"] = str(game["_id"])
            game["topic_id"] = str(game["topic_id"])
            if game.get("creator_id"):
                game["creator_id"] = str(game["creator_id"])
            
            return game
        except Exception as e:
            print(f"Error al obtener juego: {str(e)}")
            return None

    def update_game(self, game_id: str, update_data: dict) -> Tuple[bool, str]:
        try:
            result = self.collection.update_one(
                {"_id": ObjectId(game_id)},
                {"$set": update_data}
            )
            
            if result.modified_count > 0:
                return True, "Juego actualizado con éxito"
            return False, "No se realizaron cambios o juego no encontrado"
        except Exception as e:
            print(f"Error al actualizar juego: {str(e)}")
            return False, str(e)

    def delete_game(self, game_id: str) -> Tuple[bool, str]:
        try:
            # Eliminar primero los juegos virtuales relacionados
            virtual_games = get_db().virtual_games.delete_many({"game_id": ObjectId(game_id)})
            
            # Ahora eliminar el juego
            result = self.collection.delete_one({"_id": ObjectId(game_id)})
            
            if result.deleted_count > 0:
                return True, f"Juego eliminado con éxito, {virtual_games.deleted_count} juegos virtuales relacionados eliminados"
            return False, "Juego no encontrado"
        except Exception as e:
            print(f"Error al eliminar juego: {str(e)}")
            return False, str(e)

    def get_games_by_topic(self, topic_id: str) -> List[Dict]:
        try:
            games = list(self.collection.find({"topic_id": ObjectId(topic_id)}))
            
            # Convertir ObjectId a string
            for game in games:
                game["_id"] = str(game["_id"])
                game["topic_id"] = str(game["topic_id"])
                if game.get("creator_id"):
                    game["creator_id"] = str(game["creator_id"])
                
            return games
        except Exception as e:
            print(f"Error al obtener juegos: {str(e)}")
            return []

    def delete_all_topic_games(self, topic_id: str) -> Tuple[int, int]:
        try:
            # Obtener todos los juegos asociados al tema
            games = list(self.collection.find({"topic_id": ObjectId(topic_id)}))
            game_ids = [game["_id"] for game in games]
            
            virtual_count = 0
            if game_ids:
                # Eliminar juegos virtuales relacionados con estos juegos
                virtual_result = get_db().virtual_games.delete_many({"game_id": {"$in": game_ids}})
                virtual_count = virtual_result.deleted_count
            
            # Eliminar los juegos
            if game_ids:
                games_result = self.collection.delete_many({"_id": {"$in": game_ids}})
                games_deleted = games_result.deleted_count
                return games_deleted, virtual_count
            
            return 0, 0
        except Exception as e:
            print(f"Error al eliminar todos los juegos del tema: {str(e)}")
            return 0, 0

    # Helper para convertir un Game en TopicContent
    def convert_game_to_content(self, game_id: str) -> Tuple[bool, str]:
        """
        Convierte un juego existente en un contenido asociado a su tema.
        """
        from src.study_plans.services import TopicContentService
        from src.study_plans.models import ContentTypes

        game = self.get_game(game_id)
        if not game:
            return False, "Juego no encontrado"

        topic_id = game["topic_id"]
        content_data = {
            "topic_id": topic_id,
            "content_type": ContentTypes.GAME,
            "content": {
                "game_id": game_id,
                "title": game.get("title", ""),
                "description": game.get("description", ""),
                "metadata": game.get("metadata", {})
            },
            "resources": [game_id],
            "learning_methodologies": [],
            "status": "active"
        }
        topic_content_service = TopicContentService()
        return topic_content_service.create_content(content_data)

    def toggle_evaluation_status(self, game_id: str) -> Tuple[bool, str, Optional[bool]]:
        """
        Cambia el estado booleano 'is_evaluation' de un juego.

        Args:
            game_id: ID del juego a modificar.

        Returns:
            Tuple[bool, str, Optional[bool]]: (Éxito, Mensaje, Nuevo estado de is_evaluation)
        """
        try:
            validate_object_id(game_id)
            game = self.collection.find_one({"_id": ObjectId(game_id)})
            
            if not game:
                return False, "Juego no encontrado", None
                
            # Obtener el estado actual y calcular el nuevo
            current_status = game.get("is_evaluation", False)
            new_status = not current_status
            
            # Actualizar en la base de datos
            result = self.collection.update_one(
                {"_id": ObjectId(game_id)},
                {"$set": {"is_evaluation": new_status, "updated_at": datetime.now()}}
            )
            
            if result.modified_count > 0:
                msg = f"Estado 'is_evaluation' cambiado a {new_status}"
                return True, msg, new_status
            else:
                # Esto podría pasar si el estado ya era el deseado o hubo un error
                return False, "No se pudo actualizar el estado del juego.", current_status
                
        except AppException as e:
            return False, e.message, None
        except Exception as e:
            return False, f"Error inesperado: {str(e)}", None

    def get_game_results(self, game_id: str, student_id: Optional[str] = None) -> Tuple[List[Dict], Optional[str]]:
        # TODO: Implementar la lógica para obtener los resultados del juego
        pass # Añadido para corregir IndentationError

class VirtualGameService(VerificationBaseService):
    def __init__(self):
        super().__init__(collection_name="virtual_games")

    def check_game_exists(self, game_id: str) -> bool:
        """
        Verifica si un juego existe.
        
        Args:
            game_id: ID del juego a verificar
            
        Returns:
            bool: True si el juego existe, False en caso contrario
        """
        try:
            game = get_db().games.find_one({"_id": ObjectId(game_id)})
            return game is not None
        except Exception:
            return False
            
    def check_virtual_game_exists(self, virtual_game_id: str) -> bool:
        """
        Verifica si un juego virtual existe.
        
        Args:
            virtual_game_id: ID del juego virtual a verificar
            
        Returns:
            bool: True si el juego virtual existe, False en caso contrario
        """
        try:
            game = self.collection.find_one({"_id": ObjectId(virtual_game_id)})
            return game is not None
        except Exception:
            return False

    def create_virtual_game(self, virtual_game_data: dict) -> Tuple[bool, str]:
        try:
            # Verificar que el juego base existe
            game = get_db().games.find_one({"_id": ObjectId(virtual_game_data['game_id'])})
            if not game:
                return False, "Juego base no encontrado"
                
            # Verificar que el estudiante existe
            student = get_db().users.find_one({"_id": ObjectId(virtual_game_data['student_id']), "role": "STUDENT"})
            if not student:
                return False, "Estudiante no encontrado"
                
            # Verificar que el tema virtual existe
            virtual_topic = get_db().virtual_topics.find_one({"_id": ObjectId(virtual_game_data['virtual_topic_id'])})
            if not virtual_topic:
                return False, "Tema virtual no encontrado"
                
            # Verificar si ya existe un juego virtual para este estudiante y juego
            existing = self.collection.find_one({
                "game_id": ObjectId(virtual_game_data['game_id']),
                "student_id": ObjectId(virtual_game_data['student_id'])
            })
            
            if existing:
                # Actualizar en lugar de crear uno nuevo
                virtual_game_data["created_at"] = existing["created_at"]
                virtual_game_data["updated_at"] = datetime.now()
                
                self.collection.update_one(
                    {"_id": existing["_id"]},
                    {"$set": virtual_game_data}
                )
                return True, str(existing["_id"])
            
            # Crear nuevo juego virtual
            virtual_game = VirtualGame(**virtual_game_data)
            result = self.collection.insert_one(virtual_game.to_dict())
            return True, str(result.inserted_id)
        except Exception as e:
            print(f"Error al crear juego virtual: {str(e)}")
            return False, str(e)

    def get_virtual_game(self, virtual_game_id: str) -> Optional[Dict]:
        try:
            virtual_game = self.collection.find_one({"_id": ObjectId(virtual_game_id)})
            if not virtual_game:
                return None
            
            # Convertir ObjectId a string
            virtual_game["_id"] = str(virtual_game["_id"])
            virtual_game["game_id"] = str(virtual_game["game_id"])
            virtual_game["student_id"] = str(virtual_game["student_id"])
            virtual_game["virtual_topic_id"] = str(virtual_game["virtual_topic_id"])
            
            return virtual_game
        except Exception as e:
            print(f"Error al obtener juego virtual: {str(e)}")
            return None

    def update_virtual_game(self, virtual_game_id: str, update_data: dict) -> Tuple[bool, str]:
        try:
            result = self.collection.update_one(
                {"_id": ObjectId(virtual_game_id)},
                {"$set": update_data}
            )
            
            if result.modified_count > 0:
                return True, "Juego virtual actualizado con éxito"
            return False, "No se realizaron cambios o juego virtual no encontrado"
        except Exception as e:
            print(f"Error al actualizar juego virtual: {str(e)}")
            return False, str(e)

    def get_student_games(self, student_id: str) -> List[Dict]:
        try:
            virtual_games = list(self.collection.find({"student_id": ObjectId(student_id)}))
            
            # Agregar información del juego base
            for game in virtual_games:
                game["_id"] = str(game["_id"])
                game["game_id"] = str(game["game_id"])
                game["student_id"] = str(game["student_id"])
                game["virtual_topic_id"] = str(game["virtual_topic_id"])
                
                # Obtener detalles del juego base
                base_game = get_db().games.find_one({"_id": ObjectId(game["game_id"])})
                if base_game:
                    game["base_game"] = {
                        "title": base_game.get("title", ""),
                        "description": base_game.get("description", ""),
                        "game_type": base_game.get("game_type", ""),
                        "difficulty": base_game.get("difficulty", "medium")
                    }
            
            return virtual_games
        except Exception as e:
            print(f"Error al obtener juegos del estudiante: {str(e)}")
            return []

    def update_game_progress(self, virtual_game_id: str, completion_status: str, score: float) -> Tuple[bool, str]:
        try:
            # Obtener registro actual para actualizar incrementalmente
            virtual_game = self.collection.find_one({"_id": ObjectId(virtual_game_id)})
            if not virtual_game:
                return False, "Juego virtual no encontrado"
                
            # Actualizar datos
            update_data = {
                "status": completion_status,
                "score": score,
                "completed_at": datetime.now() if completion_status == STATUS["COMPLETED"] else None,
                "updated_at": datetime.now()
            }
            
            result = self.collection.update_one(
                {"_id": ObjectId(virtual_game_id)},
                {"$set": update_data}
            )
            
            if result.modified_count > 0:
                return True, "Progreso del juego actualizado con éxito"
            return False, "No se realizaron cambios"
        except Exception as e:
            print(f"Error al actualizar progreso del juego: {str(e)}")
            return False, str(e) 

class GameTemplateService(VerificationBaseService):
    """
    Servicio para gestionar plantillas de juegos educativos.
    """
    def __init__(self):
        super().__init__(collection_name="game_templates")
        
    def create_template(self, template_data: dict) -> Tuple[bool, str]:
        """
        Crea una nueva plantilla de juego.
        
        Args:
            template_data: Datos de la plantilla
            
        Returns:
            Tupla con estado y mensaje/ID
        """
        try:
            # Verificar si ya existe una plantilla con el mismo nombre
            existing = self.collection.find_one({"name": template_data.get("name")})
            if existing:
                return False, "Ya existe una plantilla con ese nombre"
                
            # Crear la plantilla
            template = GameTemplate(**template_data)
            result = self.collection.insert_one(template.to_dict())
            
            return True, str(result.inserted_id)
        except Exception as e:
            logging.error(f"Error al crear plantilla de juego: {str(e)}")
            return False, str(e)
            
    def list_templates(self, game_type: str = None, tags: List[str] = None) -> List[Dict]:
        """
        Lista plantillas de juegos disponibles, opcionalmente filtradas.
        
        Args:
            game_type: Tipo de juego para filtrar (opcional)
            tags: Etiquetas para filtrar (opcional)
            
        Returns:
            Lista de plantillas
        """
        try:
            filter_query = {"status": "active"}
            if game_type:
                filter_query["game_type"] = game_type
                
            if tags:
                filter_query["tags"] = {"$in": tags}
                
            templates = list(self.collection.find(filter_query))
            
            # Convertir a formato serializable
            for template in templates:
                template = ensure_json_serializable(template)
                    
            return templates
        except Exception as e:
            logging.error(f"Error al listar plantillas de juegos: {str(e)}")
            return []
            
    def get_template(self, template_id: str) -> Optional[Dict]:
        """
        Obtiene una plantilla específica por su ID.
        
        Args:
            template_id: ID de la plantilla
            
        Returns:
            Datos de la plantilla o None si no existe
        """
        try:
            template = self.collection.find_one({"_id": ObjectId(template_id)})
            if not template:
                return None
                
            # Convertir a formato serializable
            template = ensure_json_serializable(template)
                
            return template
        except Exception as e:
            logging.error(f"Error al obtener plantilla: {str(e)}")
            return None
            
    def update_template(self, template_id: str, update_data: dict) -> Tuple[bool, str]:
        """
        Actualiza una plantilla existente.
        
        Args:
            template_id: ID de la plantilla
            update_data: Datos a actualizar
            
        Returns:
            Tupla con estado y mensaje
        """
        try:
            # Verificar que la plantilla existe
            template = self.collection.find_one({"_id": ObjectId(template_id)})
            if not template:
                return False, "Plantilla no encontrada"
                
            # Actualizar
            update_data["updated_at"] = datetime.now()
            result = self.collection.update_one(
                {"_id": ObjectId(template_id)},
                {"$set": update_data}
            )
            
            if result.modified_count > 0:
                return True, "Plantilla actualizada exitosamente"
            return False, "No se realizaron cambios"
        except Exception as e:
            logging.error(f"Error al actualizar plantilla: {str(e)}")
            return False, str(e)
            
    def generate_game_from_template(self, template_id: str, topic_id: str, template_variables: Dict, creator_id: str = None) -> Tuple[bool, Union[str, Dict]]:
        """
        Genera un juego basado en una plantilla.
        
        Args:
            template_id: ID de la plantilla
            topic_id: ID del tema al que se asociará el juego
            template_variables: Variables para personalizar la plantilla
            creator_id: ID del creador (opcional)
            
        Returns:
            Tupla con estado y ID del juego generado/mensaje de error
        """
        try:
            # Obtener la plantilla
            template = self.get_template(template_id)
            if not template:
                return False, "Plantilla no encontrada"
                
            # Obtener tema para validación
            topic = get_db().topics.find_one({"_id": ObjectId(topic_id)})
            if not topic:
                return False, "Tema no encontrado"
                
            # Validar variables requeridas
            schema = template.get("template_schema", {})
            required_vars = schema.get("required_variables", [])
            
            for var in required_vars:
                var_name = var.get("name", "")
                if var_name not in template_variables:
                    return False, f"Falta variable requerida: {var_name}"
            
            # Procesar código con variables
            code = template.get("default_code", "")
            for var_name, var_value in template_variables.items():
                # Reemplazar marcadores de posición (usando formato ${nombre_variable})
                code = code.replace(f"${{{var_name}}}", str(var_value))
            
            # Crear datos para el juego
            game_data = {
                "topic_id": topic_id,
                "title": template_variables.get("title", template.get("name")),
                "description": template_variables.get("description", template.get("description")),
                "game_type": template.get("game_type"),
                "code": code,
                "metadata": {
                    "template_id": template_id,
                    "template_variables": template_variables,
                    "template_name": template.get("name")
                },
                "creator_id": creator_id,
                "tags": template.get("tags", []),
                "difficulty": template_variables.get("difficulty", "medium")
            }
            
            # Si hay opciones adicionales, añadirlas
            for option in ["time_limit", "visual_style", "audio_enabled", 
                          "accessibility_options", "cognitive_adaptations"]:
                if option in template_variables:
                    game_data[option] = template_variables[option]
            
            # Crear el juego usando el servicio
            game_service = GameService()
            success, result = game_service.create_game(game_data)
            
            return success, result
        except Exception as e:
            logging.error(f"Error al generar juego desde plantilla: {str(e)}")
            return False, str(e)

class GameResultService(VerificationBaseService):
    """
    Servicio para gestionar resultados de sesiones de juego.
    """
    def __init__(self):
        super().__init__(collection_name="game_results")
        
    def record_result(self, result_data: dict) -> Tuple[bool, str]:
        """
        Registra un nuevo resultado de juego.
        
        Args:
            result_data: Datos del resultado
            
        Returns:
            Tupla con estado y mensaje/ID
        """
        try:
            # Verificar que el juego virtual existe
            virtual_game_id = result_data.get("virtual_game_id")
            virtual_game = get_db().virtual_games.find_one({"_id": ObjectId(virtual_game_id)})
            if not virtual_game:
                return False, "Juego virtual no encontrado"
                
            # Verificar que el estudiante existe
            student_id = result_data.get("student_id")
            student = get_db().users.find_one({"_id": ObjectId(student_id)})
            if not student:
                return False, "Estudiante no encontrado"
                
            # Crear el resultado
            game_result = GameResult(**result_data)
            result = self.collection.insert_one(game_result.to_dict())
            
            # Actualizar datos del juego virtual
            update_data = {
                "last_played": datetime.now(),
                "updated_at": datetime.now()
            }
            
            # Actualizar porcentaje de completado si es mayor al actual
            completion_percentage = result_data.get("completion_percentage", 0)
            if completion_percentage > virtual_game.get("completion_percentage", 0):
                update_data["completion_percentage"] = completion_percentage
                
            # Actualizar datos de rendimiento
            performance_data = virtual_game.get("performance_data", {})
            
            # Agregar puntuación a historial
            if "score_history" not in performance_data:
                performance_data["score_history"] = []
                
            if "score" in result_data and result_data["score"] is not None:
                performance_data["score_history"].append({
                    "date": datetime.now(),
                    "score": result_data["score"]
                })
                
                # Calcular mejor puntuación
                all_scores = [s.get("score", 0) for s in performance_data["score_history"] if s.get("score") is not None]
                if all_scores:
                    performance_data["best_score"] = max(all_scores)
                    performance_data["average_score"] = sum(all_scores) / len(all_scores)
            
            # Actualizar tiempo total de juego
            time_spent = result_data.get("time_spent", 0)
            if time_spent > 0:
                performance_data["total_time_spent"] = performance_data.get("total_time_spent", 0) + time_spent
                performance_data["sessions_count"] = performance_data.get("sessions_count", 0) + 1
            
            update_data["performance_data"] = performance_data
            
            # Aplicar actualización
            get_db().virtual_games.update_one(
                {"_id": ObjectId(virtual_game_id)},
                {"$set": update_data}
            )
            
            return True, str(result.inserted_id)
        except Exception as e:
            logging.error(f"Error al registrar resultado de juego: {str(e)}")
            return False, str(e)
            
    def get_student_results(self, student_id: str, virtual_game_id: str = None) -> List[Dict]:
        """
        Obtiene resultados de juegos de un estudiante.
        
        Args:
            student_id: ID del estudiante
            virtual_game_id: ID del juego virtual (opcional, para filtrar)
            
        Returns:
            Lista de resultados
        """
        try:
            filter_query = {"student_id": ObjectId(student_id)}
            if virtual_game_id:
                filter_query["virtual_game_id"] = ObjectId(virtual_game_id)
                
            results = list(self.collection.find(filter_query))
            
            # Convertir a formato serializable
            for result in results:
                result = ensure_json_serializable(result)
                
            return results
        except Exception as e:
            logging.error(f"Error al obtener resultados del estudiante: {str(e)}")
            return []
            
    def get_learning_analytics(self, student_id: str, topic_id: str = None) -> Dict:
        """
        Obtiene análisis de aprendizaje basado en resultados de juegos.
        
        Args:
            student_id: ID del estudiante
            topic_id: ID del tema (opcional, para filtrar)
            
        Returns:
            Análisis de aprendizaje
        """
        try:
            # Obtener todos los juegos virtuales del estudiante
            virtual_games_query = {"student_id": ObjectId(student_id)}
            
            # Si se proporciona un tema, primero buscar módulos virtuales del tema
            if topic_id:
                # Buscar temas virtuales asociados al tema
                virtual_topics = list(get_db().virtual_topics.find(
                    {"topic_id": ObjectId(topic_id)}
                ))
                
                if virtual_topics:
                    virtual_topic_ids = [vt["_id"] for vt in virtual_topics]
                    virtual_games_query["virtual_topic_id"] = {"$in": virtual_topic_ids}
            
            # Obtener juegos virtuales
            virtual_games = list(get_db().virtual_games.find(virtual_games_query))
            
            if not virtual_games:
                return {
                    "message": "No hay juegos virtuales para el estudiante y tema especificados",
                    "metrics": {}
                }
                
            # Obtener IDs de juegos virtuales
            virtual_game_ids = [vg["_id"] for vg in virtual_games]
            
            # Obtener resultados de juegos
            results = list(self.collection.find({
                "virtual_game_id": {"$in": virtual_game_ids}
            }))
            
            # Si no hay resultados, devolver métricas vacías
            if not results:
                return {
                    "total_games": len(virtual_games),
                    "games_played": 0,
                    "metrics": {}
                }
                
            # Calcular métricas
            metrics = {
                "total_games": len(virtual_games),
                "games_played": len(set(str(r["virtual_game_id"]) for r in results)),
                "total_time_spent": sum(r.get("time_spent", 0) for r in results),
                "average_completion": sum(r.get("completion_percentage", 0) for r in results) / len(results),
                "total_sessions": len(results)
            }
            
            # Calcular puntuaciones medias y mejores si hay datos disponibles
            scores = [r.get("score") for r in results if r.get("score") is not None]
            if scores:
                metrics["average_score"] = sum(scores) / len(scores)
                metrics["best_score"] = max(scores)
                metrics["lowest_score"] = min(scores)
            
            # Calcular progreso por tipo de juego
            game_type_progress = {}
            for vg in virtual_games:
                # Obtener el juego original para saber su tipo
                original_game = get_db().games.find_one({"_id": vg["game_id"]})
                if original_game:
                    game_type = original_game.get("game_type")
                    if game_type not in game_type_progress:
                        game_type_progress[game_type] = {
                            "total": 0,
                            "completed": 0,
                            "in_progress": 0,
                            "not_started": 0
                        }
                        
                    game_type_progress[game_type]["total"] += 1
                    
                    # Determinar estado según porcentaje de completado
                    completion = vg.get("completion_percentage", 0)
                    if completion >= 99:
                        game_type_progress[game_type]["completed"] += 1
                    elif completion > 0:
                        game_type_progress[game_type]["in_progress"] += 1
                    else:
                        game_type_progress[game_type]["not_started"] += 1
                        
            metrics["game_type_progress"] = game_type_progress
            
            # Análisis de tendencias de aprendizaje (mejora con el tiempo)
            if len(results) > 1:
                # Ordenar resultados por fecha
                sorted_results = sorted(results, key=lambda r: r.get("session_date", datetime.now()))
                
                # Comparar primer y último resultado
                first_result = sorted_results[0]
                last_result = sorted_results[-1]
                
                if first_result.get("score") is not None and last_result.get("score") is not None:
                    metrics["score_improvement"] = last_result.get("score") - first_result.get("score")
                    
            return {
                "student_id": student_id,
                "topic_id": topic_id,
                "metrics": metrics
            }
        except Exception as e:
            logging.error(f"Error al obtener análisis de aprendizaje: {str(e)}")
            return {"error": str(e), "metrics": {}} 