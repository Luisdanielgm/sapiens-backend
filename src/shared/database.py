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
        # Primero eliminar el índice existente si existe
        existing_indexes = db.institute_members.index_information()
        if "institute_id_1_user_id_1" in existing_indexes:
            try:
                db.institute_members.drop_index("institute_id_1_user_id_1")
            except Exception as e:
                logger.warning(f"No se pudo eliminar el índice existente: {str(e)}")
            
        # Crear el nuevo índice con unique=True incluyendo workspace_type
        db.institute_members.create_index([
            ("institute_id", ASCENDING),
            ("user_id", ASCENDING),
            ("workspace_type", ASCENDING)
        ], unique=True)
        db.institute_members.create_index([("user_id", ASCENDING)])
        db.institute_members.create_index([("role", ASCENDING)])
        
        # Índices de programas educativos
        db.educational_programs.create_index([("institute_id", ASCENDING)])
        db.educational_programs.create_index([("name", TEXT)])
        
        # Índices de planes de estudio
        # Eliminar índice antiguo si existe para evitar conflictos y warnings
        existing_indexes = db.study_plans_per_subject.index_information()
        if "idx_study_plans_subject_id" in existing_indexes:
            db.study_plans_per_subject.drop_index("idx_study_plans_subject_id")
        
        # Índices de planes de estudio
        db.study_plans_per_subject.create_index([("subject_id", ASCENDING)])
        # Nuevos índices para unificación de planes personales
        db.study_plans_per_subject.create_index([("workspace_id", ASCENDING)])
        db.study_plans_per_subject.create_index([("author_id", ASCENDING)])
        db.study_plans_per_subject.create_index([("is_personal", ASCENDING), ("workspace_id", ASCENDING)])
        
        # Índices de planes de estudio
        # Eliminar índice antiguo de modules si existe para evitar conflictos y warnings
        existing_indexes = db.modules.index_information()
        if "idx_modules_study_plan_id" in existing_indexes:
            db.modules.drop_index("idx_modules_study_plan_id")
        # Crear índice de modules
        db.modules.create_index([("study_plan_id", ASCENDING)])
        
        # Índices de planes de estudio
        # Eliminar índice antiguo de topics si existe para evitar conflictos y warnings
        existing_indexes = db.topics.index_information()
        if "idx_topics_module_id" in existing_indexes:
            db.topics.drop_index("idx_topics_module_id")
        # Crear índice de topics
        db.topics.create_index([("module_id", ASCENDING)])
        
        # Índices académicos
        db.academic_periods.create_index([("institute_id", ASCENDING)])
        db.sections.create_index([("academic_period_id", ASCENDING)])
        db.subjects.create_index([("name", TEXT)])
        
        # Índices de clases
        db.classes.create_index([("teacher_id", ASCENDING)])
        db.classes.create_index([("subject_id", ASCENDING)])
        db.classes.create_index([("section_id", ASCENDING)])
        
        # Índices de miembros de clase
        try:
            db.class_members.drop_index("class_id_1_student_id_1")
        except Exception as e:
            logger.warning(f"No se pudo eliminar el índice existente de class_members: {str(e)}")
            
        # Crear índice parcial que solo aplica unique cuando student_id no es null
        db.class_members.create_index(
            [("class_id", ASCENDING), ("student_id", ASCENDING)],
            unique=True,
            partialFilterExpression={"student_id": {"$type": "string"}}
        )
        db.class_members.create_index([("student_id", ASCENDING)])
        
        # Índices de invitaciones
        try:
            db.institute_invitations.drop_index("email_1_institute_id_1")
        except Exception as e:
            logger.warning(f"No se pudo eliminar el índice existente de institute_invitations: {str(e)}")
            
        try:
            db.institute_invitations.drop_index("token_1")
        except Exception as e:
            logger.warning(f"No se pudo eliminar el índice token de institute_invitations: {str(e)}")
            
        try:
            db.class_invitations.drop_index("email_1_class_id_1")
        except Exception as e:
            logger.warning(f"No se pudo eliminar el índice existente de class_invitations: {str(e)}")
            
        try:
            db.class_invitations.drop_index("token_1")
        except Exception as e:
            logger.warning(f"No se pudo eliminar el índice token de class_invitations: {str(e)}")
        
        # Crear los nuevos índices
        db.institute_invitations.create_index(
            [("email", ASCENDING), ("institute_id", ASCENDING)],
            unique=True,
            partialFilterExpression={"email": {"$type": "string"}}
        )
        db.institute_invitations.create_index(
            [("token", ASCENDING)],
            unique=True,
            partialFilterExpression={"token": {"$type": "string"}}
        )
        db.class_invitations.create_index(
            [("email", ASCENDING), ("class_id", ASCENDING)],
            unique=True,
            partialFilterExpression={"email": {"$type": "string"}}
        )
        db.class_invitations.create_index(
            [("token", ASCENDING)],
            unique=True,
            partialFilterExpression={"token": {"$type": "string"}}
        )
        
        # Índices para base de lenguas indígenas
        indigenous_db.languages.create_index([("name", TEXT)])
        indigenous_db.languages.create_index([("region", ASCENDING)])
        indigenous_db.content.create_index([("language_id", ASCENDING)])

        # ------------------------------------------------------------
        # Índices específicos para optimizar consultas de contenido/slides
        # ------------------------------------------------------------
        try:
            content_coll = db.content
            existing_indexes = content_coll.index_information()
        except Exception as e:
            logger.error(f"No se pudo obtener información de índices de la colección content: {str(e)}")
            content_coll = None
            existing_indexes = {}

        def _ensure_index(coll, keys, name=None, **kwargs):
            """
            Helper local para crear índices con logging, medición de tiempo,
            manejo de conflictos y recreación si es necesario.
            - coll: colección
            - keys: lista de tuplas para la clave del índice
            - name: nombre explícito del índice
            - kwargs: opciones adicionales para create_index (partialFilterExpression, unique, etc.)
            """
            if coll is None:
                logger.warning("Colección no disponible para crear índices.")
                return None

            try:
                idx_info = coll.index_information()
            except Exception as e:
                logger.warning(f"No se pudo leer index_information para {coll.name}: {str(e)}")
                idx_info = {}

            # Si ya existe un índice con este nombre, no intentamos recrearlo
            if name and name in idx_info:
                logger.debug(f"Índice '{name}' ya existe en {coll.name}.")
                return name

            # Buscar índices con las mismas keys (mismo orden)
            keys_tuple = tuple(keys)
            existing_same_key = None
            for iname, info in idx_info.items():
                # info['key'] is a list of tuples like [('topic_id', 1), ('order', 1)]
                if 'key' in info:
                    existing_key = tuple(info['key'])
                    if existing_key == keys_tuple:
                        existing_same_key = iname
                        break

            # Si existe un índice con las mismas keys pero diferente nombre, eliminarlo para unificar
            if existing_same_key and name and existing_same_key != name:
                try:
                    logger.info(f"Eliminando índice existente '{existing_same_key}' en {coll.name} para recrear con nombre '{name}'")
                    coll.drop_index(existing_same_key)
                except Exception as e:
                    logger.warning(f"No se pudo eliminar el índice '{existing_same_key}': {str(e)}")

            # Crear el índice y medir tiempo
            try:
                start_ts = datetime.utcnow()
                created_name = coll.create_index(keys, name=name, **kwargs)
                duration = (datetime.utcnow() - start_ts).total_seconds()
                logger.info(f"Índice '{created_name}' creado en {coll.name} en {duration:.3f}s (keys={keys}, options={kwargs})")
                # Verificación simple
                try:
                    new_info = coll.index_information()
                    if created_name not in new_info:
                        logger.warning(f"Índice '{created_name}' no aparece en index_information() tras creación.")
                except Exception as e:
                    logger.warning(f"No se pudo verificar index_information tras crear índice '{created_name}': {str(e)}")
                return created_name
            except Exception as e:
                # Intentar detectar conflicto por índice existente y recrearlo
                logger.warning(f"Error creando índice {name or keys} en {coll.name}: {str(e)}. Intentando resolver conflictos...")
                try:
                    # Intentar eliminar índices con las mismas keys (si existen)
                    for iname, info in idx_info.items():
                        if 'key' in info and tuple(info['key']) == keys_tuple:
                            try:
                                logger.info(f"Eliminando índice conflictivo '{iname}' en {coll.name}")
                                coll.drop_index(iname)
                            except Exception as ex:
                                logger.warning(f"No se pudo eliminar índice conflictivo '{iname}': {str(ex)}")
                    # Reintentar creación
                    start_ts = datetime.utcnow()
                    created_name = coll.create_index(keys, name=name, **kwargs)
                    duration = (datetime.utcnow() - start_ts).total_seconds()
                    logger.info(f"Índice '{created_name}' creado en {coll.name} en reintento ({duration:.3f}s)")
                    return created_name
                except Exception as e2:
                    logger.error(f"No se pudo crear índice {name or keys} en {coll.name} tras reintento: {str(e2)}")
                    return None

        # Definir y crear índices demandados
        try:
            # Índice compuesto: topic_id + content_type + order
            _ensure_index(
                content_coll,
                [("topic_id", ASCENDING), ("content_type", ASCENDING), ("order", ASCENDING)],
                name="idx_topic_content_type_order",
                background=True
            )

            # Índice para filtros rápidos por estado: topic_id + status
            _ensure_index(
                content_coll,
                [("topic_id", ASCENDING), ("status", ASCENDING)],
                name="idx_topic_status",
                background=True
            )

            # Índice global por content_type + status
            _ensure_index(
                content_coll,
                [("content_type", ASCENDING), ("status", ASCENDING)],
                name="idx_content_type_status",
                background=True
            )

            # Índice compuesto completo: topic_id + content_type + status + order
            _ensure_index(
                content_coll,
                [("topic_id", ASCENDING), ("content_type", ASCENDING), ("status", ASCENDING), ("order", ASCENDING)],
                name="idx_topic_content_type_status_order",
                background=True
            )

            # Índice para consultas agrupadas por parent_content_id + order
            _ensure_index(
                content_coll,
                [("parent_content_id", ASCENDING), ("order", ASCENDING)],
                name="idx_parent_content_order",
                background=True
            )

            # Índices parciales dirigidos a slides (optimiza espacio y velocidad para consultas de slides)
            _ensure_index(
                content_coll,
                [("topic_id", ASCENDING), ("order", ASCENDING)],
                name="idx_slide_topic_order_partial",
                background=True,
                partialFilterExpression={"content_type": "slide"}
            )

            _ensure_index(
                content_coll,
                [("parent_content_id", ASCENDING), ("order", ASCENDING)],
                name="idx_slide_parent_order_partial",
                background=True,
                partialFilterExpression={"content_type": "slide"}
            )

            # Índices de texto para búsquedas en title y full_text
            _ensure_index(
                content_coll,
                [("title", TEXT), ("full_text", TEXT)],
                name="idx_text_title_full_text",
                background=True
            )

            # Índices temporales para consultas por progreso/tiempo
            _ensure_index(
                content_coll,
                [("created_at", ASCENDING)],
                name="idx_content_created_at",
                background=True
            )
            _ensure_index(
                content_coll,
                [("updated_at", ASCENDING)],
                name="idx_content_updated_at",
                background=True
            )

            logger.info("Índices específicos para colección 'content' creados/verificados correctamente.")
        except Exception as e:
            logger.error(f"Error creando índices específicos para 'content': {str(e)}")

        logger.info("Índices de base de datos configurados correctamente")
        return True

    except Exception as e:
        logger.error(f"Error configurando índices de base de datos: {str(e)}")
        return False