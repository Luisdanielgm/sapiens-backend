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

    Esta función debe llamarse durante la inicialización de la aplicación para asegurar
    que todos los índices estén configurados correctamente.

    Implementa un mecanismo de flag con thread safety para evitar que se ejecute múltiples veces.
    """
    # Usar un lock para garantizar thread safety
    with DatabaseConnection._indexes_setup_lock:
        # Verificar si ya se han configurado los índices
        if DatabaseConnection._indexes_setup_complete:
            logger.debug("Los índices ya han sido configurados. Saltando setup_database_indexes.")
            return True

        try:
            logger.info("Iniciando configuración de índices de base de datos...")
            
            # Obtener conexiones a las bases de datos
            db = get_db()
            indigenous_db = get_indigenous_db()
            
            # Función helper para crear índices con manejo de errores
            def _ensure_index(collection, keys, name=None, **kwargs):
                """Helper para crear índices con logging y manejo de errores"""
                try:
                    start_time = datetime.utcnow()
                    
                    # Verificar si el índice ya existe
                    existing_indexes = collection.index_information()
                    if name and name in existing_indexes:
                        logger.debug(f"Índice '{name}' ya existe en {collection.name}")
                        return name

                    # Detectar si ya existe un índice equivalente (importante para índices de texto)
                    keys_tuple = tuple(keys)
                    has_text_keys = any(direction == TEXT for _, direction in keys)
                    desired_text_fields = {field for field, direction in keys if direction == TEXT}

                    for existing_name, info in existing_indexes.items():
                        existing_key = tuple(info.get('key', []))

                        # Índices regulares: comparar las llaves tal cual
                        if existing_key == keys_tuple:
                            logger.debug(
                                f"Índice '{existing_name}' en {collection.name} ya cubre las claves {keys_tuple}; no se recreará"
                            )
                            return existing_name

                        # Índices de texto: pymongo reporta claves internas (_fts, _ftsx); comparar por weights
                        if has_text_keys:
                            weights = info.get('weights')
                            if weights and set(weights.keys()) == desired_text_fields:
                                logger.debug(
                                    f"Índice de texto '{existing_name}' en {collection.name} ya cubre los campos {desired_text_fields}; no se recreará"
                                )
                                return existing_name
                    
                    # Crear el índice
                    created_name = collection.create_index(keys, name=name, **kwargs)
                    duration = (datetime.utcnow() - start_time).total_seconds()
                    logger.info(f"Índice '{created_name}' creado en {collection.name} ({duration:.3f}s)")
                    return created_name
                    
                except Exception as e:
                    logger.error(f"Error creando índice {name or keys} en {collection.name}: {str(e)}")
                    # Intentar resolver conflictos eliminando índices duplicados
                    try:
                        existing_indexes = collection.index_information()
                        keys_tuple = tuple(keys)
                        
                        # Buscar índices con las mismas keys
                        for idx_name, info in existing_indexes.items():
                            if 'key' in info and tuple(info['key']) == keys_tuple:
                                logger.info(f"Eliminando índice conflictivo '{idx_name}' en {collection.name}")
                                collection.drop_index(idx_name)
                        
                        # Reintentar creación
                        created_name = collection.create_index(keys, name=name, **kwargs)
                        logger.info(f"Índice '{created_name}' creado tras resolver conflicto en {collection.name}")
                        return created_name
                        
                    except Exception as e2:
                        logger.error(f"No se pudo crear índice {name or keys} en {collection.name} tras reintento: {str(e2)}")
                        return None
            
            # Crear índices para la base de datos principal
            
            # Índices de usuarios
            _ensure_index(db.users, [("email", ASCENDING)], name="idx_users_email", unique=True)
            _ensure_index(db.users, [("role", ASCENDING)], name="idx_users_role")
            
            # Índices de institutos
            _ensure_index(db.institutes, [("email", ASCENDING)], name="idx_institutes_email")
            _ensure_index(db.institutes, [("status", ASCENDING)], name="idx_institutes_status")
            
            # Índices de miembros del instituto
            _ensure_index(db.institute_members, [
                ("institute_id", ASCENDING),
                ("user_id", ASCENDING),
                ("workspace_type", ASCENDING)
            ], name="idx_institute_members_unique", unique=True)
            _ensure_index(db.institute_members, [("user_id", ASCENDING)], name="idx_institute_members_user")
            _ensure_index(db.institute_members, [("role", ASCENDING)], name="idx_institute_members_role")
            
            # Índices de programas educativos
            _ensure_index(db.educational_programs, [("institute_id", ASCENDING)], name="idx_educational_programs_institute")
            _ensure_index(db.educational_programs, [("name", TEXT)], name="idx_educational_programs_text")
            
            # Índices de planes de estudio
            _ensure_index(db.study_plans_per_subject, [("subject_id", ASCENDING)], name="idx_study_plans_subject")
            _ensure_index(db.study_plans_per_subject, [("workspace_id", ASCENDING)], name="idx_study_plans_workspace")
            _ensure_index(db.study_plans_per_subject, [("author_id", ASCENDING)], name="idx_study_plans_author")
            _ensure_index(db.study_plans_per_subject, [("is_personal", ASCENDING), ("workspace_id", ASCENDING)], name="idx_study_plans_personal_workspace")
            
            # Índices de módulos
            _ensure_index(db.modules, [("study_plan_id", ASCENDING)], name="idx_modules_study_plan")
            
            # Índices de temas
            _ensure_index(db.topics, [("module_id", ASCENDING)], name="idx_topics_module")
            
            # Índices académicos
            _ensure_index(db.academic_periods, [("institute_id", ASCENDING)], name="idx_academic_periods_institute")
            _ensure_index(db.sections, [("academic_period_id", ASCENDING)], name="idx_sections_academic_period")
            _ensure_index(db.subjects, [("name", TEXT)], name="idx_subjects_text")
            
            # Índices de clases
            _ensure_index(db.classes, [("teacher_id", ASCENDING)], name="idx_classes_teacher")
            _ensure_index(db.classes, [("subject_id", ASCENDING)], name="idx_classes_subject")
            _ensure_index(db.classes, [("section_id", ASCENDING)], name="idx_classes_section")
            
            # Índices de miembros de clase
            _ensure_index(db.class_members, [("class_id", ASCENDING), ("student_id", ASCENDING)], 
                         name="idx_class_members_unique", unique=True,
                         partialFilterExpression={"student_id": {"$type": "string"}})
            _ensure_index(db.class_members, [("student_id", ASCENDING)], name="idx_class_members_student")
            
            # Índices de invitaciones
            _ensure_index(db.institute_invitations, [("email", ASCENDING), ("institute_id", ASCENDING)],
                         name="idx_institute_invitations_unique", unique=True,
                         partialFilterExpression={"email": {"$type": "string"}})
            _ensure_index(db.institute_invitations, [("token", ASCENDING)],
                         name="idx_institute_invitations_token", unique=True,
                         partialFilterExpression={"token": {"$type": "string"}})
            
            _ensure_index(db.class_invitations, [("email", ASCENDING), ("class_id", ASCENDING)],
                         name="idx_class_invitations_unique", unique=True,
                         partialFilterExpression={"email": {"$type": "string"}})
            _ensure_index(db.class_invitations, [("token", ASCENDING)],
                         name="idx_class_invitations_token", unique=True,
                         partialFilterExpression={"token": {"$type": "string"}})
            
            # Índices para contenido de temas (topic_contents)
            content_coll = db.topic_contents
            
            # Índices básicos
            _ensure_index(content_coll, [("topic_id", ASCENDING)], name="idx_topic_contents_topic")
            _ensure_index(content_coll, [("content_type", ASCENDING)], name="idx_topic_contents_type")
            _ensure_index(content_coll, [("status", ASCENDING)], name="idx_topic_contents_status")
            
            # Índices compuestos para optimizar consultas frecuentes
            _ensure_index(content_coll, [("topic_id", ASCENDING), ("content_type", ASCENDING), ("order", ASCENDING)],
                         name="idx_topic_content_type_order")
            _ensure_index(content_coll, [("topic_id", ASCENDING), ("status", ASCENDING)],
                         name="idx_topic_status")
            _ensure_index(content_coll, [("content_type", ASCENDING), ("status", ASCENDING)],
                         name="idx_content_type_status")
            
            # Índices únicos para garantizar integridad
            _ensure_index(content_coll, [("topic_id", ASCENDING), ("content_type", ASCENDING)],
                         name="idx_unique_topic_content_quiz", unique=True,
                         partialFilterExpression={"content_type": "quiz"})
            
            # Índices para base de lenguas indígenas
            _ensure_index(indigenous_db.languages, [("name", TEXT)], name="idx_languages_text")
            _ensure_index(indigenous_db.languages, [("region", ASCENDING)], name="idx_languages_region")
            _ensure_index(indigenous_db.content, [("language_id", ASCENDING)], name="idx_indigenous_content_language")
            
            # Marcar como completado
            DatabaseConnection._indexes_setup_complete = True
            logger.info("✓ Configuración de índices de base de datos completada exitosamente")
            return True
            
        except Exception as e:
            logger.error(f"Error durante la configuración de índices: {str(e)}")
            return False

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
