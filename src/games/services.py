from typing import Tuple, List, Dict, Optional
from bson import ObjectId
from datetime import datetime

from src.shared.database import get_db
from src.shared.constants import STATUS
from src.shared.standardization import VerificationBaseService, ErrorCodes
from src.shared.exceptions import AppException
from .models import Game, VirtualGame

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