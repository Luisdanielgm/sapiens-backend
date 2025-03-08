from pymongo import MongoClient
from typing import Optional
import dotenv
from datetime import datetime
import os
import logging

dotenv.load_dotenv()

logger = logging.getLogger(__name__)

def get_config_value(key, default=None):
    """
    Obtiene un valor de configuración, intentando primero desde Flask current_app
    y cayendo en variables de entorno si no está disponible el contexto de la aplicación.
    """
    try:
        from flask import current_app
        if current_app:
            return current_app.config.get(key, os.getenv(key, default))
    except (ImportError, RuntimeError):
        # Si no estamos en un contexto de aplicación Flask o no está importado
        pass
    return os.getenv(key, default)

class DatabaseConnection:
    _instance: Optional[MongoClient] = None
    _db = None

    @classmethod
    def get_instance(cls) -> MongoClient:
        """Implementa patrón Singleton para la conexión"""
        if cls._instance is None:
            try:
                # Obtener la URL de conexión usando la función auxiliar
                mongo_uri = get_config_value('MONGO_DB_URI')
                if not mongo_uri:
                    logger.error("No se encontró la variable MONGO_DB_URI en la configuración")
                    raise ValueError("MONGO_DB_URI no está configurado")
                
                cls._instance = MongoClient(
                    mongo_uri,
                    # Agregar configuración de pool
                    maxPoolSize=10,
                    minPoolSize=5,
                    maxIdleTimeMS=60000
                )
                logger.info("Nueva conexión a MongoDB establecida")
            except Exception as e:
                logger.error(f"Error al conectar a MongoDB: {str(e)}")
                raise
        return cls._instance

    @classmethod
    def get_db(cls):
        """Obtiene la instancia de la base de datos"""
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
    _instance = None
    _db = None

    @classmethod
    def get_db(cls):
        if cls._db is None:
            client = DatabaseConnection.get_instance()
            # Obtener el nombre de la base de datos de lenguas indígenas
            indigenous_db_name = get_config_value('INDIGENOUS_DB_NAME', 'indigenous_languages')
            cls._db = client[indigenous_db_name]
        return cls._db

def get_indigenous_db():
    """Helper function para la BD de lenguas indígenas"""
    return IndigenousLanguagesDB.get_db()