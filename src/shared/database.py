from pymongo import MongoClient, ASCENDING, DESCENDING, TEXT
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

def setup_database_indexes():
    """
    Configura los índices necesarios en la base de datos para optimizar consultas frecuentes.
    
    Esta función debe llamarse durante la inicialización de la aplicación para asegurar
    que todos los índices estén configurados correctamente.
    """
    try:
        # Obtener conexiones a las bases de datos
        db = get_db()
        indigenous_db = get_indigenous_db()
        
        # Crear índices para la base de datos principal
        
        # Índices de usuarios
        db.users.create_index([("email", ASCENDING)], unique=True)
        db.users.create_index([("role", ASCENDING)])
        
        # Índices de institutos
        db.institutes.create_index([("email", ASCENDING)])
        db.institutes.create_index([("status", ASCENDING)])
        
        # Índices de miembros del instituto
        db.institute_members.create_index([("institute_id", ASCENDING), ("user_id", ASCENDING)], unique=True)
        db.institute_members.create_index([("user_id", ASCENDING)])
        db.institute_members.create_index([("role", ASCENDING)])
        
        # Índices de programas educativos
        db.educational_programs.create_index([("institute_id", ASCENDING)])
        db.educational_programs.create_index([("name", TEXT)]) 
        
        # Índices académicos
        db.academic_periods.create_index([("institute_id", ASCENDING)])
        db.sections.create_index([("academic_period_id", ASCENDING)])
        db.subjects.create_index([("name", TEXT)])
        
        # Índices de clases
        db.classes.create_index([("teacher_id", ASCENDING)])
        db.classes.create_index([("subject_id", ASCENDING)])
        db.classes.create_index([("section_id", ASCENDING)])
        db.class_members.create_index([("class_id", ASCENDING), ("student_id", ASCENDING)], unique=True)
        db.class_members.create_index([("student_id", ASCENDING)])
        
        # Índices de invitaciones
        db.institute_invitations.create_index([("email", ASCENDING), ("institute_id", ASCENDING)], unique=True)
        db.institute_invitations.create_index([("token", ASCENDING)], unique=True)
        db.class_invitations.create_index([("email", ASCENDING), ("class_id", ASCENDING)], unique=True)
        db.class_invitations.create_index([("token", ASCENDING)], unique=True)
        
        # Índices de contenido individual de estudiantes
        db.student_individual_content.create_index([("student_id", ASCENDING), ("class_id", ASCENDING)])
        
        # Índices de planes de estudio
        db.study_plans_per_subject.create_index([("subject_id", ASCENDING)])
        db.modules.create_index([("study_plan_id", ASCENDING)])
        db.topics.create_index([("module_id", ASCENDING)])
        
        # Índices de recursos
        db.resources.create_index([("created_by", ASCENDING)])
        db.resources.create_index([("folder_id", ASCENDING)])
        db.resources.create_index([("type", ASCENDING)])
        db.resources.create_index([("name", TEXT), ("description", TEXT), ("tags", TEXT)])
        
        # Índices de carpetas de recursos
        db.resource_folders.create_index([("created_by", ASCENDING)])
        db.resource_folders.create_index([("parent_id", ASCENDING)])
        db.resource_folders.create_index([("name", TEXT)])
        
        # Índices para la base de datos de lenguas indígenas
        
        # Índices para traducciones
        indigenous_db.translations.create_index([("language_pair", ASCENDING)], background=True)
        indigenous_db.translations.create_index([("type_data", ASCENDING)], background=True)
        indigenous_db.translations.create_index([("created_at", DESCENDING)], background=True)
        indigenous_db.translations.create_index([("español", TEXT), ("traduccion", TEXT)], 
                                              background=True, default_language="spanish")
        
        # Índices para verificaciones
        indigenous_db.verificaciones.create_index([("translation_id", ASCENDING)], background=True)
        indigenous_db.verificaciones.create_index([("verificador_id", ASCENDING)], background=True)
        
        # Configuración exitosa
        logger.info("Índices de base de datos configurados correctamente")
        return True
        
    except Exception as e:
        logger.error(f"Error al configurar índices de la base de datos: {str(e)}")
        return False