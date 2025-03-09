from typing import Tuple, List, Dict
from datetime import datetime, timedelta
from bson import ObjectId

from src.shared.database import get_indigenous_db, get_db
from src.shared.standardization import BaseService, VerificationBaseService, ErrorCodes
from src.shared.exceptions import AppException
from .models import Translation, Language

class IndigenousVerificationBaseService(BaseService):
    """
    Clase base para servicios relacionados con lenguas indígenas.
    Usa la base de datos específica de lenguas indígenas pero mantiene
    acceso a la base de datos principal para verificaciones.
    """
    def __init__(self, collection_name: str):
        # No llamamos a super() porque usamos otra base de datos
        self.indigenous_db = get_indigenous_db()
        self.collection = self.indigenous_db[collection_name]
        self.collection_name = collection_name
        # Mantenemos acceso a la DB principal para verificaciones
        self.db = get_db()

    # Métodos de verificación heredados de VerificationBaseService
    def check_user_exists(self, user_id: str) -> bool:
        """
        Verifica si un usuario existe.
        
        Args:
            user_id: ID del usuario a verificar
            
        Returns:
            bool: True si el usuario existe, False en caso contrario
        """
        try:
            user_id_obj = ObjectId(user_id) if isinstance(user_id, str) else user_id
            user = self.db.users.find_one({"_id": user_id_obj})
            return user is not None
        except Exception:
            return False

class TranslationService(IndigenousVerificationBaseService):
    def __init__(self):
        super().__init__(collection_name="translations")

    def create_translation(self, translation_data: dict) -> Tuple[bool, str]:
        try:
            translation = Translation(**translation_data)
            result = self.collection.insert_one(translation.to_dict())
            return True, str(result.inserted_id)
        except Exception as e:
            return False, str(e)

    def get_translations(self, language_pair=None, type_data=None, dialecto=None) -> List[Dict]:
        try:
            query = {}
            if language_pair:
                query["language_pair"] = language_pair
            if type_data:
                query["type_data"] = type_data
            if dialecto:
                query["dialecto"] = dialecto

            translations = list(self.collection.find(query))
            
            # Convertir ObjectId a string para serialización
            for translation in translations:
                translation["_id"] = str(translation["_id"])
                
            return translations
        except Exception as e:
            print(f"Error al obtener traducciones: {str(e)}")
            return []

    def search_translations(self, query=None, filters=None) -> List[Dict]:
        try:
            search_query = {}
            
            if query:
                search_query["$or"] = [
                    {"español": {"$regex": query, "$options": "i"}},
                    {"traduccion": {"$regex": query, "$options": "i"}}
                ]
            
            if filters:
                # Aplicar filtros adicionales
                if 'language_pair' in filters and filters['language_pair']:
                    search_query["language_pair"] = filters['language_pair']
                    
                if 'dialecto' in filters and filters['dialecto']:
                    search_query["dialecto"] = filters['dialecto']
                    
                if 'type_data' in filters and filters['type_data']:
                    search_query["type_data"] = filters['type_data']
                    
                if 'desde' in filters and filters['desde']:
                    try:
                        fecha_desde = datetime.fromisoformat(filters['desde'].replace('Z', '+00:00'))
                        search_query["created_at"] = {"$gte": fecha_desde}
                    except:
                        # Si hay error en formato, ignorar este filtro
                        pass
                        
                if 'hasta' in filters and filters['hasta']:
                    try:
                        fecha_hasta = datetime.fromisoformat(filters['hasta'].replace('Z', '+00:00'))
                        if "created_at" in search_query:
                            search_query["created_at"]["$lte"] = fecha_hasta
                        else:
                            search_query["created_at"] = {"$lte": fecha_hasta}
                    except:
                        # Si hay error en formato, ignorar este filtro
                        pass
            
            # Realizar búsqueda en base de datos
            translations = list(self.collection.find(search_query).sort("created_at", -1))
            
            # Convertir ObjectId a string para serialización
            for translation in translations:
                translation["_id"] = str(translation["_id"])
                
            return translations
        except Exception as e:
            print(f"Error en búsqueda de traducciones: {str(e)}")
            return []

    def validate_language_pair(self, language_pair: str) -> bool:
        # Formato esperado: "es-<code>" donde <code> es el código del idioma indígena
        return language_pair.startswith("es-") and len(language_pair) > 3

    def bulk_create_translations(self, translations: List[Dict]) -> Tuple[bool, List[str]]:
        try:
            # Validar todos los language_pair
            for t in translations:
                if not self.validate_language_pair(t.get('language_pair', '')):
                    return False, ["Formato de language_pair inválido"]
            
            # Preparar documentos para inserción
            docs_to_insert = [Translation(**t).to_dict() for t in translations]
            result = self.collection.insert_many(docs_to_insert)
            
            # Retornar IDs generados
            return True, [str(id) for id in result.inserted_ids]
        except Exception as e:
            return False, [str(e)]

    def update_translation(self, translation_id: str, updates: Dict) -> Tuple[bool, str]:
        try:
            # Verificar si existe la traducción
            translation = self.collection.find_one({"_id": ObjectId(translation_id)})
            if not translation:
                return False, "Traducción no encontrada"
                
            # Actualizar la traducción
            updates["updated_at"] = datetime.now()
            result = self.collection.update_one(
                {"_id": ObjectId(translation_id)},
                {"$set": updates}
            )
            
            if result.modified_count > 0:
                return True, "Traducción actualizada con éxito"
            return False, "No se realizaron cambios"
        except Exception as e:
            return False, str(e)

    def delete_translation(self, translation_id: str) -> Tuple[bool, str]:
        try:
            # Verificar si existe la traducción
            translation = self.collection.find_one({"_id": ObjectId(translation_id)})
            if not translation:
                return False, "Traducción no encontrada"
                
            # Eliminar la traducción
            result = self.collection.delete_one({"_id": ObjectId(translation_id)})
            
            if result.deleted_count > 0:
                return True, "Traducción eliminada con éxito"
            return False, "No se pudo eliminar la traducción"
        except Exception as e:
            return False, str(e)

    def get_available_language_pairs(self) -> List[Dict]:
        try:
            # Obtener todos los language_pairs únicos
            pipeline = [
                {"$group": {"_id": "$language_pair"}},
                {"$project": {"language_pair": "$_id", "_id": 0}}
            ]
            
            results = list(self.collection.aggregate(pipeline))
            
            # Formatear resultados
            return [{"language_pair": r["language_pair"]} for r in results]
        except Exception as e:
            print(f"Error al obtener pares de idiomas: {str(e)}")
            return []

class LanguageService(IndigenousVerificationBaseService):
    def __init__(self):
        super().__init__(collection_name="languages")

    def add_language(self, language_data: dict) -> Tuple[bool, str]:
        try:
            language = Language(**language_data)
            result = self.collection.insert_one(language.to_dict())
            return True, str(result.inserted_id)
        except Exception as e:
            return False, str(e)

    def get_active_languages(self) -> List[Dict]:
        try:
            languages = list(self.collection.find({"status": "active"}))
            
            # Convertir ObjectId a string para serialización
            for language in languages:
                language["_id"] = str(language["_id"])
                
            return languages
        except Exception as e:
            print(f"Error al obtener idiomas: {str(e)}")
            return [] 