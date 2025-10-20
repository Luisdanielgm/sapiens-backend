from pymongo import MongoClient, ASCENDING, DESCENDING, TEXT
from typing import Optional
import dotenv
from datetime import datetime
import os
import logging
import threading

dotenv.load_dotenv()

logger = logging.getLogger(__name__)

def get_config_value(key, default=None):
    """
    Obtiene un valor de configuración desde las variables de entorno.
    
    Args:
        key (str): La clave de la variable de entorno
        default: Valor por defecto si no se encuentra la variable
        
    Returns:
        El valor de la variable de entorno o el valor por defecto
    """
    value = os.getenv(key, default)
    if value is None:
        logger.warning(f"Variable de entorno '{key}' no encontrada")
    return value

class DatabaseConnection:
    _instance: Optional[MongoClient] = None
    _db = None
    _indexes_setup_complete = False
    _indexes_setup_lock = threading.Lock()
    _failed_indexes = set()  # Track which indexes failed to create
    _successful_indexes = set()  # Track successfully created indexes

    @classmethod
    def get_instance(cls) -> MongoClient:
        """Obtiene la instancia singleton del cliente MongoDB"""
        if cls._instance is None:
            # Obtener la URI de MongoDB usando la función auxiliar
            mongo_uri = get_config_value('MONGO_DB_URI')
            if not mongo_uri:
                logger.error("No se encontró la variable MONGO_DB_URI en la configuración")
                raise ValueError("MONGO_DB_URI no está configurado")

            logger.info("Configurando conexión a MongoDB...")
            
            # Configurar el cliente MongoDB con timeouts más largos
            cls._instance = MongoClient(
                mongo_uri,
                maxPoolSize=50,
                minPoolSize=5,
                maxIdleTimeMS=30000,
                connectTimeoutMS=20000,
                serverSelectionTimeoutMS=20000,
                socketTimeoutMS=20000,
                waitQueueTimeoutMS=10000
            )
            
            # Verificar la conexión
            try:
                cls._instance.admin.command('ping')
                logger.info("✓ Conexión a MongoDB establecida exitosamente")
            except Exception as e:
                logger.error(f"Error conectando a MongoDB: {str(e)}")
                cls._instance = None
                raise
                
        return cls._instance

    @classmethod
    def get_db(cls):
        """Obtiene la instancia de la base de datos"""
        if cls._db is None:
            with cls._indexes_setup_lock:
                # Double-check inside lock
                if cls._db is None:
                    # Obtener el nombre de la base de datos usando la función auxiliar
                    db_name = get_config_value('DB_NAME')
                    if not db_name:
                        logger.error("No se encontró la variable DB_NAME en la configuración")
                        raise ValueError("DB_NAME no está configurado")

                    cls._db = cls.get_instance()[db_name]
        return cls._db

def get_db():
    """Helper function para obtener la conexión a la BD"""
    return DatabaseConnection.get_db()

class IndigenousLanguagesDB:
    _db = None
    _lock = threading.Lock()

    @classmethod
    def get_db(cls):
        """Obtiene la instancia de la base de datos de lenguas indígenas"""
        if cls._db is None:
            with cls._lock:
                if cls._db is None:
                    db_name = get_config_value('INDIGENOUS_DB_NAME')
                    if not db_name:
                        logger.error("No se encontró la variable INDIGENOUS_DB_NAME en la configuración")
                        raise ValueError("INDIGENOUS_DB_NAME no está configurado")
                    cls._db = DatabaseConnection.get_instance()[db_name]
        return cls._db

def get_indigenous_db():
    """Helper function para obtener la conexión a la BD de lenguas indígenas"""
    return IndigenousLanguagesDB.get_db()

def setup_database_indexes():
    """
    Configura los índices necesarios en la base de datos para optimizar consultas frecuentes.
    
    VERSIÓN TEMPORAL: Deshabilitada para diagnóstico de problemas de conexión.
    """
    logger.info("setup_database_indexes() temporalmente deshabilitada para diagnóstico")
    DatabaseConnection._indexes_setup_complete = True
    return True

def reset_index_setup_tracking():
    """
    Resetea el estado de seguimiento de configuración de índices.
    
    Útil para:
    - Forzar recreación de todos los índices
    - Recuperación de estados inconsistentes
    - Testing y desarrollo

    Esta función es thread-safe y debe usarse con cuidado.
    """
    with DatabaseConnection._indexes_setup_lock:
        DatabaseConnection._indexes_setup_complete = False
        DatabaseConnection._failed_indexes.clear()
        DatabaseConnection._successful_indexes.clear()
        logger.info("Estado de seguimiento de configuración de índices reseteado.")

def get_index_setup_status():
    """
    Obtiene el estado actual de la configuración de índices.
    
    Returns:
        dict: Diccionario con información del estado de los índices
    """
    return {
        "setup_complete": DatabaseConnection._indexes_setup_complete,
        "failed_indexes_count": len(DatabaseConnection._failed_indexes),
        "successful_indexes_count": len(DatabaseConnection._successful_indexes),
        "failed_indexes": list(DatabaseConnection._failed_indexes),
        "successful_indexes": list(DatabaseConnection._successful_indexes)
    }