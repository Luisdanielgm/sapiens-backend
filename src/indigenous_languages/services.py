from typing import Tuple, List, Dict
from datetime import datetime, timedelta
from bson import ObjectId

from src.shared.database import get_indigenous_db, get_db
from src.shared.standardization import BaseService, VerificationBaseService, ErrorCodes
from src.shared.exceptions import AppException
from src.shared.logging import log_error, log_info, log_debug
from .models import Translation, Language, Verificador, Verificacion

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

    def get_translations(self, language_pair=None, type_data=None, dialecto=None, filters=None) -> List[Dict]:
        try:
            query = {}
            if language_pair:
                query["language_pair"] = language_pair
            if type_data:
                query["type_data"] = type_data
            if dialecto:
                query["dialecto"] = dialecto
                
            # Aplicar filtros adicionales relacionados con verificaciones
            if filters:
                # Filtro por número mínimo de verificaciones
                if 'min_verificaciones' in filters and isinstance(filters['min_verificaciones'], int):
                    query["verificaciones_count"] = {"$gte": filters['min_verificaciones']}

            translations = list(self.collection.find(query))
            
            # Convertir ObjectId a string para serialización
            for translation in translations:
                translation["_id"] = str(translation["_id"])
                
            # Si se solicita incluir verificaciones o se filtra por verificador específico
            verificador_id = filters and filters.get('verificador_id')
            include_verificaciones = filters and filters.get('include_verificaciones', False)
            
            if verificador_id or include_verificaciones:
                # Crear instancia del servicio de verificaciones
                from .services import VerificacionService
                verificacion_service = VerificacionService()
                
                # Filtrar por verificador específico
                if verificador_id:
                    verificacion_collection = verificacion_service.collection
                    verificaciones = list(verificacion_collection.find({"verificador_id": verificador_id}))
                    
                    translation_ids_verificadas = [v["translation_id"] for v in verificaciones]
                    translations = [t for t in translations if str(t["_id"]) in translation_ids_verificadas]
                
                # Enriquecer con verificaciones
                if include_verificaciones:
                    for translation in translations:
                        translation_id = translation["_id"]
                        verificaciones = verificacion_service.get_verificaciones_by_translation(translation_id)
                        translation["verificaciones"] = verificaciones
                
            return translations
        except Exception as e:
            print(f"Error al obtener traducciones: {str(e)}")
            return []
            
    def search_translations(self, query=None, filters=None) -> List[Dict]:
        try:
            search_query = {}
            index_hint = None
            
            if query:
                search_query["$or"] = [
                    {"español": {"$regex": query, "$options": "i"}},
                    {"traduccion": {"$regex": query, "$options": "i"}}
                ]
            
            if filters:
                # Aplicar filtros adicionales
                if 'language_pair' in filters and filters['language_pair']:
                    search_query["language_pair"] = filters['language_pair']
                    index_hint = "language_pair_1"  # Sugerencia de índice para optimización
                    
                if 'dialecto' in filters and filters['dialecto']:
                    search_query["dialecto"] = filters['dialecto']
                    
                if 'type_data' in filters and filters['type_data']:
                    search_query["type_data"] = filters['type_data']
                
                # Filtro por número mínimo de verificaciones
                if 'min_verificaciones' in filters and isinstance(filters['min_verificaciones'], int):
                    search_query["verificaciones_count"] = {"$gte": filters['min_verificaciones']}
                
                # Procesamiento de filtros de created_at
                self._apply_date_filter(
                    search_query=search_query,
                    field_name="created_at",
                    exact_date=filters.get('created_at'),
                    desde=filters.get('desde_created'),
                    hasta=filters.get('hasta_created')
                )
                
                # Procesamiento de filtros de updated_at
                self._apply_date_filter(
                    search_query=search_query,
                    field_name="updated_at",
                    exact_date=filters.get('updated_at'),
                    desde=filters.get('desde_updated'),
                    hasta=filters.get('hasta_updated')
                )
            
            log_debug(f"Consulta de búsqueda final: {search_query}", "indigenous_languages.services")
            
            # Realizar búsqueda en base de datos con límite para evitar sobrecarga
            cursor = self.collection.find(search_query).sort("created_at", -1).limit(100)
            
            # Aplicar hint de índice si existe
            if index_hint:
                try:
                    cursor = cursor.hint(index_hint)
                except Exception:
                    # Si el índice no existe, continuar sin hint
                    pass
            
            translations = list(cursor)
            
            # Convertir ObjectId a string para serialización
            for translation in translations:
                translation["_id"] = str(translation["_id"])
                
            # Si se solicita incluir verificaciones o se filtra por verificador específico
            include_verificaciones = filters and filters.get('include_verificaciones', False)
            verificador_id = filters and filters.get('verificador_id')
            
            if include_verificaciones or verificador_id:
                # Crear instancia del servicio de verificaciones si es necesario
                from .services import VerificacionService
                verificacion_service = VerificacionService()
                
                # Filtrar por verificador específico si se solicita
                if verificador_id:
                    # Obtener traducciones verificadas por este verificador
                    verificacion_collection = verificacion_service.collection
                    verificaciones = list(verificacion_collection.find({"verificador_id": verificador_id}))
                    
                    translation_ids_verificadas = [str(v["translation_id"]) for v in verificaciones]
                    translations = [t for t in translations if t["_id"] in translation_ids_verificadas]
                
                # Enriquecer con verificaciones si se solicita (limitar número para evitar carga excesiva)
                if include_verificaciones:
                    for translation in translations:
                        translation_id = translation["_id"]
                        verificaciones = verificacion_service.get_verificaciones_by_translation(translation_id)
                        translation["verificaciones"] = verificaciones
            
            log_info(f"Búsqueda completada: {len(translations)} resultados encontrados", "indigenous_languages.services")
            return translations
        except Exception as e:
            log_error("Error en búsqueda de traducciones", e, "indigenous_languages.services")
            return []

    def _apply_date_filter(self, search_query, field_name, exact_date=None, desde=None, hasta=None):
        """
        Aplica filtros de fecha a un campo específico
        
        Args:
            search_query: El diccionario de consulta de MongoDB
            field_name: Nombre del campo de fecha (created_at o updated_at)
            exact_date: Fecha exacta para filtrar
            desde: Fecha de inicio
            hasta: Fecha de fin
        """
        try:
            # Si se especifica una fecha exacta
            if exact_date:
                try:
                    # Convertir a fecha y asegurar que busque todo el día
                    fecha_str = exact_date
                    if 'T' not in fecha_str:  # Formato simple YYYY-MM-DD
                        fecha_inicio = datetime.fromisoformat(f"{fecha_str}T00:00:00")
                        fecha_fin = datetime.fromisoformat(f"{fecha_str}T23:59:59.999")
                        search_query[field_name] = {"$gte": fecha_inicio, "$lte": fecha_fin}
                        log_debug(f"Filtro exacto aplicado a {field_name}: {fecha_inicio} - {fecha_fin}", "indigenous_languages.services")
                    else:
                        # Es una fecha-hora completa
                        # Normalizamos el formato (reemplazar Z por +00:00 si es necesario)
                        if fecha_str.endswith('Z'):
                            fecha_str = fecha_str.replace('Z', '+00:00')
                        
                        # Si es formato ISO completo pero sin zona horaria, añadir UTC
                        if 'T' in fecha_str and '+' not in fecha_str and '-' not in fecha_str[10:]:
                            fecha_str = f"{fecha_str}+00:00"
                            
                        fecha = datetime.fromisoformat(fecha_str)
                        search_query[field_name] = fecha
                        log_debug(f"Filtro exacto aplicado a {field_name}: {fecha}", "indigenous_languages.services")
                except Exception as e:
                    log_error(f"Error al procesar fecha exacta '{field_name}'", e, "indigenous_languages.services")
                return
                
            # Inicializar el diccionario de rango si se usa desde o hasta
            if desde or hasta:
                if field_name not in search_query:
                    search_query[field_name] = {}
            
            # Aplicar filtro desde
            if desde:
                try:
                    fecha_str = desde
                    if 'T' not in fecha_str:  # Formato simple YYYY-MM-DD
                        fecha_str = f"{fecha_str}T00:00:00"
                    
                    # Normalizamos el formato (reemplazar Z por +00:00 si es necesario)
                    if fecha_str.endswith('Z'):
                        fecha_str = fecha_str.replace('Z', '+00:00')
                    
                    # Si es formato ISO completo pero sin zona horaria, añadir UTC
                    if 'T' in fecha_str and '+' not in fecha_str and '-' not in fecha_str[10:]:
                        fecha_str = f"{fecha_str}+00:00"
                        
                    fecha_desde = datetime.fromisoformat(fecha_str)
                    search_query[field_name]["$gte"] = fecha_desde
                    log_debug(f"Filtro desde aplicado a {field_name}: {fecha_desde}", "indigenous_languages.services")
                except Exception as e:
                    log_error(f"Error al procesar 'desde' para {field_name}", e, "indigenous_languages.services")
            
            # Aplicar filtro hasta
            if hasta:
                try:
                    fecha_str = hasta
                    if 'T' not in fecha_str:  # Formato simple YYYY-MM-DD
                        fecha_str = f"{fecha_str}T23:59:59.999"
                    
                    # Normalizamos el formato (reemplazar Z por +00:00 si es necesario)
                    if fecha_str.endswith('Z'):
                        fecha_str = fecha_str.replace('Z', '+00:00')
                    
                    # Si es formato ISO completo pero sin zona horaria, añadir UTC
                    if 'T' in fecha_str and '+' not in fecha_str and '-' not in fecha_str[10:]:
                        fecha_str = f"{fecha_str}+00:00"
                        
                    fecha_hasta = datetime.fromisoformat(fecha_str)
                    search_query[field_name]["$lte"] = fecha_hasta
                    log_debug(f"Filtro hasta aplicado a {field_name}: {fecha_hasta}", "indigenous_languages.services")
                except Exception as e:
                    log_error(f"Error al procesar 'hasta' para {field_name}", e, "indigenous_languages.services")
                    
        except Exception as e:
            log_error(f"Error general al aplicar filtros de fecha a {field_name}", e, "indigenous_languages.services")

    def validate_language_pair(self, language_pair: str) -> bool:
        # Formato esperado: "español-<code>" donde <code> es el código del idioma indígena
        return language_pair.startswith("español-") and len(language_pair) > 8  # "español-" tiene 8 caracteres

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
            updates["updated_at"] = datetime.utcnow()
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

class VerificadorService(IndigenousVerificationBaseService):
    def __init__(self):
        super().__init__('verificadores')
        
    def create_verificador(self, verificador_data: dict) -> Tuple[bool, str]:
        try:
            verificador = Verificador(**verificador_data)
            result = self.collection.insert_one(verificador.to_dict())
            return True, str(result.inserted_id)
        except Exception as e:
            return False, str(e)
            
    def get_verificadores(self, etnia=None, tipo=None, activo=True) -> List[Dict]:
        try:
            query = {"activo": activo}
            if etnia:
                query["etnia"] = etnia
            if tipo:
                query["tipo"] = tipo
                
            verificadores = list(self.collection.find(query))
            
            # Convertir ObjectId a string para serialización
            for verificador in verificadores:
                verificador["_id"] = str(verificador["_id"])
                
            return verificadores
        except Exception as e:
            print(f"Error al obtener verificadores: {str(e)}")
            return []
            
    def update_verificador(self, verificador_id: str, updates: Dict) -> Tuple[bool, str]:
        try:
            # Verificar si existe
            verificador = self.collection.find_one({"_id": ObjectId(verificador_id)})
            if not verificador:
                return False, "Verificador no encontrado"
                
            # Actualizar
            updates["updated_at"] = datetime.utcnow()
            result = self.collection.update_one(
                {"_id": ObjectId(verificador_id)},
                {"$set": updates}
            )
            
            if result.modified_count > 0:
                return True, "Verificador actualizado con éxito"
            return False, "No se realizaron cambios"
        except Exception as e:
            return False, str(e)
            
    def delete_verificador(self, verificador_id: str) -> Tuple[bool, str]:
        try:
            # Desactivar en lugar de eliminar
            result = self.collection.update_one(
                {"_id": ObjectId(verificador_id)},
                {"$set": {"activo": False, "updated_at": datetime.utcnow()}}
            )
            
            if result.modified_count > 0:
                return True, "Verificador desactivado con éxito"
            return False, "No se realizaron cambios"
        except Exception as e:
            return False, str(e)

class VerificacionService(IndigenousVerificationBaseService):
    def __init__(self):
        super().__init__('verificaciones')
        self.translation_service = TranslationService()
        self.verificador_service = VerificadorService()
        
    def add_verificacion(self, verificacion_data: dict) -> Tuple[bool, str]:
        try:
            # Verificar que exista la traducción
            translation_id = verificacion_data.get('translation_id')
            translation = self.translation_service.collection.find_one({"_id": ObjectId(translation_id)})
            if not translation:
                return False, "Traducción no encontrada"
                
            # Verificar que exista el verificador
            verificador_id = verificacion_data.get('verificador_id')
            verificador = self.verificador_service.collection.find_one({"_id": ObjectId(verificador_id)})
            if not verificador:
                return False, "Verificador no encontrado"
            
            # Verificar que no exista ya esta verificación
            existing = self.collection.find_one({
                "translation_id": translation_id,
                "verificador_id": verificador_id
            })
            if existing:
                return False, "Esta verificación ya existe"
                
            # Crear verificación
            verificacion = Verificacion(**verificacion_data)
            result = self.collection.insert_one(verificacion.to_dict())
            
            # Actualizar contador de verificaciones en la traducción
            self.translation_service.collection.update_one(
                {"_id": ObjectId(translation_id)},
                {"$inc": {"verificaciones_count": 1}}
            )
            
            return True, str(result.inserted_id)
        except Exception as e:
            return False, str(e)
            
    def get_verificaciones_by_translation(self, translation_id: str) -> List[Dict]:
        try:
            # Buscar verificaciones
            verificaciones = list(self.collection.find({"translation_id": translation_id}))
            
            # Enriquecer con datos del verificador
            for v in verificaciones:
                v["_id"] = str(v["_id"])
                verificador = self.verificador_service.collection.find_one({"_id": ObjectId(v["verificador_id"])})
                if verificador:
                    verificador["_id"] = str(verificador["_id"])
                    v["verificador"] = verificador
                    
            return verificaciones
        except Exception as e:
            print(f"Error al obtener verificaciones: {str(e)}")
            return []
            
    def remove_verificacion(self, verificacion_id: str) -> Tuple[bool, str]:
        try:
            # Buscar la verificación
            verificacion = self.collection.find_one({"_id": ObjectId(verificacion_id)})
            if not verificacion:
                return False, "Verificación no encontrada"
                
            # Eliminar verificación
            result = self.collection.delete_one({"_id": ObjectId(verificacion_id)})
            
            # Actualizar contador en la traducción
            if result.deleted_count > 0:
                self.translation_service.collection.update_one(
                    {"_id": ObjectId(verificacion["translation_id"])},
                    {"$inc": {"verificaciones_count": -1}}
                )
                return True, "Verificación eliminada con éxito"
            
            return False, "No se realizaron cambios"
        except Exception as e:
            return False, str(e)
            
    def get_top_verified_translations(self, limit: int = 10) -> List[Dict]:
        try:
            # Obtener traducciones con más verificaciones
            translations = list(self.translation_service.collection.find().sort("verificaciones_count", -1).limit(limit))
            
            # Convertir ObjectId a string
            for t in translations:
                t["_id"] = str(t["_id"])
                
            return translations
        except Exception as e:
            print(f"Error al obtener traducciones verificadas: {str(e)}")
            return [] 