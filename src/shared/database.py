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
    Obtiene un valor de configuración, intentando primero desde Flask current_app
    y cayendo en variables de entorno si no está disponible el contexto de la aplicación.
    """
    try:
        from flask import current_app
        return current_app.config.get(key, os.getenv(key, default))
    except (ImportError, RuntimeError):
        # Si no estamos en un contexto de aplicación Flask o no está importado
        pass
    return os.getenv(key, default)

class DatabaseConnection:
    _instance: Optional[MongoClient] = None
    _db = None
    _indexes_setup_complete = False
    _indexes_setup_lock = threading.Lock()
    _failed_indexes = set()  # Track which indexes failed to create
    _successful_indexes = set()  # Track successfully created indexes

    @classmethod
    def get_instance(cls) -> MongoClient:
        """Implementa patrón Singleton para la conexión"""
        if cls._instance is None:
            with cls._indexes_setup_lock:
                # Double-check inside lock
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
        if cls._db is None:
            with cls._lock:
                # Double-check inside lock
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

    Implementa un mecanismo de flag con thread safety para evitar que se ejecute múltiples veces.
    Ahora incluye seguimiento de índices fallidos para reintentar solo los que fallaron.
    """
    # Usar un lock para garantizar thread safety
    with DatabaseConnection._indexes_setup_lock:
        # Si no hay índices fallidos pendientes y ya se completó el setup, saltar
        if DatabaseConnection._indexes_setup_complete and not DatabaseConnection._failed_indexes:
            logger.debug("Los índices ya han sido configurados. Saltando setup_database_indexes.")
            return True

        # Si hay índices fallidos, solo reintentaremos esos
        if DatabaseConnection._failed_indexes:
            logger.info(f"Reintentando crear {len(DatabaseConnection._failed_indexes)} índices fallidos previamente.")
        elif DatabaseConnection._indexes_setup_complete:
            logger.debug("Todos los índices ya fueron creados exitosamente. Saltando setup.")
            return True

        try:
            # Obtener conexiones a las bases de datos
            db = get_db()
            indigenous_db = get_indigenous_db()

            # Helper function para índices simples con seguimiento de fallos
            def _create_simple_index(collection, keys, index_name=None, **kwargs):
                """Helper para crear índices simples con seguimiento de fallos"""
                identifier = index_name or f"{collection.name}_{str(keys)}"

                # Si estamos reintentando y este índice no falló, omitir
                if DatabaseConnection._failed_indexes and identifier not in DatabaseConnection._failed_indexes:
                    if identifier in DatabaseConnection._successful_indexes:
                        return  # Ya fue creado exitosamente
                    return  # No está en la lista de fallidos, omitir

                try:
                    collection.create_index(keys, **kwargs)
                    DatabaseConnection._successful_indexes.add(identifier)
                    DatabaseConnection._failed_indexes.discard(identifier)
                except Exception as e:
                    logger.error(f"Error creando índice {identifier} en {collection.name}: {str(e)}")
                    DatabaseConnection._failed_indexes.add(identifier)
                    DatabaseConnection._successful_indexes.discard(identifier)

            # Crear índices para la base de datos principal

            # Índices de usuarios
            _create_simple_index(db.users, [("email", ASCENDING)], "users_email_unique", unique=True)
            _create_simple_index(db.users, [("role", ASCENDING)], "users_role")

            # Índices de institutos
            _create_simple_index(db.institutes, [("email", ASCENDING)], "institutes_email")
            _create_simple_index(db.institutes, [("status", ASCENDING)], "institutes_status")

            # Índices de miembros del instituto
            # Primero eliminar el índice existente si existe
            existing_indexes = db.institute_members.index_information()
            if "institute_id_1_user_id_1" in existing_indexes:
                try:
                    db.institute_members.drop_index("institute_id_1_user_id_1")
                except Exception as e:
                    logger.warning(f"No se pudo eliminar el índice existente: {str(e)}")

            # Crear el nuevo índice con unique=True incluyendo workspace_type
            _create_simple_index(
                db.institute_members,
                [("institute_id", ASCENDING), ("user_id", ASCENDING), ("workspace_type", ASCENDING)],
                "institute_members_unique",
                unique=True
            )
            _create_simple_index(db.institute_members, [("user_id", ASCENDING)], "institute_members_user_id")
            _create_simple_index(db.institute_members, [("role", ASCENDING)], "institute_members_role")

            # Índices de programas educativos
            _create_simple_index(db.educational_programs, [("institute_id", ASCENDING)], "educational_programs_institute_id")
            _create_simple_index(db.educational_programs, [("name", TEXT)], "educational_programs_name_text")

            # Índices de planes de estudio
            # Eliminar índice antiguo si existe para evitar conflictos y warnings
            existing_indexes = db.study_plans_per_subject.index_information()
            if "idx_study_plans_subject_id" in existing_indexes:
                db.study_plans_per_subject.drop_index("idx_study_plans_subject_id")

            # Índices de planes de estudio
            _create_simple_index(db.study_plans_per_subject, [("subject_id", ASCENDING)], "study_plans_subject_id")
            # Nuevos índices para unificación de planes personales
            _create_simple_index(db.study_plans_per_subject, [("workspace_id", ASCENDING)], "study_plans_workspace_id")
            _create_simple_index(db.study_plans_per_subject, [("author_id", ASCENDING)], "study_plans_author_id")
            _create_simple_index(
                db.study_plans_per_subject,
                [("is_personal", ASCENDING), ("workspace_id", ASCENDING)],
                "study_plans_personal_workspace"
            )

            # Índices de planes de estudio
            # Eliminar índice antiguo de modules si existe para evitar conflictos y warnings
            existing_indexes = db.modules.index_information()
            if "idx_modules_study_plan_id" in existing_indexes:
                db.modules.drop_index("idx_modules_study_plan_id")
            # Crear índice de modules
            _create_simple_index(db.modules, [("study_plan_id", ASCENDING)], "modules_study_plan_id")

            # Índices de planes de estudio
            # Eliminar índice antiguo de topics si existe para evitar conflictos y warnings
            existing_indexes = db.topics.index_information()
            if "idx_topics_module_id" in existing_indexes:
                db.topics.drop_index("idx_topics_module_id")
            # Crear índice de topics
            _create_simple_index(db.topics, [("module_id", ASCENDING)], "topics_module_id")

            # Índices académicos
            _create_simple_index(db.academic_periods, [("institute_id", ASCENDING)], "academic_periods_institute_id")
            _create_simple_index(db.sections, [("academic_period_id", ASCENDING)], "sections_academic_period_id")
            _create_simple_index(db.subjects, [("name", TEXT)], "subjects_name_text")

            # Índices de clases
            _create_simple_index(db.classes, [("teacher_id", ASCENDING)], "classes_teacher_id")
            _create_simple_index(db.classes, [("subject_id", ASCENDING)], "classes_subject_id")
            _create_simple_index(db.classes, [("section_id", ASCENDING)], "classes_section_id")

            # Índices de miembros de clase
            try:
                db.class_members.drop_index("class_id_1_student_id_1")
            except Exception as e:
                logger.warning(f"No se pudo eliminar el índice existente de class_members: {str(e)}")

            # Crear índice parcial que solo aplica unique cuando student_id no es null
            _create_simple_index(
                db.class_members,
                [("class_id", ASCENDING), ("student_id", ASCENDING)],
                "class_members_unique",
                unique=True,
                partialFilterExpression={"student_id": {"$type": "string"}}
            )
            _create_simple_index(db.class_members, [("student_id", ASCENDING)], "class_members_student_id")

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
            _create_simple_index(
                db.institute_invitations,
                [("email", ASCENDING), ("institute_id", ASCENDING)],
                "institute_invitations_email_institute",
                unique=True,
                partialFilterExpression={"email": {"$type": "string"}}
            )
            _create_simple_index(
                db.institute_invitations,
                [("token", ASCENDING)],
                "institute_invitations_token",
                unique=True,
                partialFilterExpression={"token": {"$type": "string"}}
            )
            _create_simple_index(
                db.class_invitations,
                [("email", ASCENDING), ("class_id", ASCENDING)],
                "class_invitations_email_class",
                unique=True,
                partialFilterExpression={"email": {"$type": "string"}}
            )
            _create_simple_index(
                db.class_invitations,
                [("token", ASCENDING)],
                "class_invitations_token",
                unique=True,
                partialFilterExpression={"token": {"$type": "string"}}
            )

            # Índices para base de lenguas indígenas
            _create_simple_index(indigenous_db.languages, [("name", TEXT)], "indigenous_languages_name_text")
            _create_simple_index(indigenous_db.languages, [("region", ASCENDING)], "indigenous_languages_region")
            _create_simple_index(indigenous_db.content, [("language_id", ASCENDING)], "indigenous_content_language_id")

            # ------------------------------------------------------------
            # Índices específicos para optimizar consultas de contenido/slides
            # ------------------------------------------------------------
            try:
                content_coll = db.topic_contents
                existing_indexes = content_coll.index_information()
            except Exception as e:
                logger.error(f"No se pudo obtener información de índices de la colección topic_contents: {str(e)}")
                content_coll = None
                existing_indexes = {}

            def _ensure_index(coll, keys, name=None, **kwargs):
                """
                Helper local para crear índices con logging, medición de tiempo,
                manejo de conflictos y recreación si es necesario.
                Ahora incluye seguimiento de fallos para reintentos selectivos.
                - coll: colección
                - keys: lista de tuplas para la clave del índice
                - name: nombre explícito del índice
                - kwargs: opciones adicionales para create_index (partialFilterExpression, unique, etc.)
                """
                if coll is None:
                    logger.warning("Colección no disponible para crear índices.")
                    return None

                # Si estamos reintentando, solo procesar índices que fallaron previamente
                index_identifier = name or f"{coll.name}_{str(keys)}"
                if DatabaseConnection._failed_indexes and index_identifier not in DatabaseConnection._failed_indexes:
                    # Si este índice ya fue creado exitosamente, verificar que existe y retornar
                    if index_identifier in DatabaseConnection._successful_indexes:
                        try:
                            idx_info = coll.index_information()
                            if name and name in idx_info:
                                logger.debug(f"Índice '{name}' ya existe y fue marcado como exitoso en {coll.name}.")
                                return name
                        except Exception as e:
                            logger.warning(f"No se pudo verificar índice exitoso '{name}': {str(e)}")
                    # Si no está en la lista de fallidos y no fue creado exitosamente, omitir
                    return None

                try:
                    idx_info = coll.index_information()
                except Exception as e:
                    logger.warning(f"No se pudo leer index_information para {coll.name}: {str(e)}")
                    idx_info = {}

                # Si ya existe un índice con este nombre, registrar como exitoso
                if name and name in idx_info:
                    logger.debug(f"Índice '{name}' ya existe en {coll.name}.")
                    DatabaseConnection._successful_indexes.add(index_identifier)
                    DatabaseConnection._failed_indexes.discard(index_identifier)
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

                    # Marcar como exitoso y limpiar de fallidos
                    DatabaseConnection._successful_indexes.add(index_identifier)
                    DatabaseConnection._failed_indexes.discard(index_identifier)

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

                        # Marcar como exitoso tras reintento
                        DatabaseConnection._successful_indexes.add(index_identifier)
                        DatabaseConnection._failed_indexes.discard(index_identifier)

                        return created_name
                    except Exception as e2:
                        logger.error(f"No se pudo crear índice {name or keys} en {coll.name} tras reintento: {str(e2)}")
                        # Marcar como fallido para reintento futuro
                        DatabaseConnection._failed_indexes.add(index_identifier)
                        DatabaseConnection._successful_indexes.discard(index_identifier)
                        return None

            # Definir y crear índices demandados
            try:
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

                # Índices ÚNICOS para garantizar integridad de datos
                # Índice único para slides: (topic_id, content_type, order)
                _ensure_index(
                    content_coll,
                    [("topic_id", ASCENDING), ("content_type", ASCENDING), ("order", ASCENDING)],
                    name="idx_unique_topic_content_order",
                    background=True,
                    unique=True,
                    partialFilterExpression={"content_type": "slide"}
                )

                # Índice único parcial para reforzar unicidad de quiz: solo topic_id cuando content_type='quiz'
                _ensure_index(
                    content_coll,
                    [("topic_id", ASCENDING)],
                    name="idx_unique_topic_id_quiz",
                    background=True,
                    unique=True,
                    partialFilterExpression={"content_type": "quiz"}
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

                # Detectar y eliminar índices de texto existentes en topic_contents antes de crear el nuevo
                try:
                    existing_indexes = content_coll.index_information()
                    text_indexes_to_drop = []

                    # Detectar índices de texto existentes
                    for index_name, info in existing_indexes.items():
                        # MongoDB permite solo un índice de texto por colección
                        # Detectar índices de texto por weights o key con tipo 'text'
                        if info.get('weights') is not None or any(key[1] == 'text' for key in info.get('key', [])):
                            text_indexes_to_drop.append(index_name)
                            logger.info(f"Detectado índice de texto existente: '{index_name}' en topic_contents")

                    # Eliminar índices de texto existentes
                    for index_name in text_indexes_to_drop:
                        try:
                            content_coll.drop_index(index_name)
                            logger.info(f"Eliminado índice de texto existente '{index_name}' de topic_contents")
                        except Exception as e:
                            logger.warning(f"No se pudo eliminar el índice de texto '{index_name}': {str(e)}")

                except Exception as e:
                    logger.warning(f"Error detectando/eliminando índices de texto existentes: {str(e)}")

                # Índices de texto para búsquedas en title y full_text
                _ensure_index(
                    content_coll,
                    [("title", TEXT), ("content.full_text", TEXT)],
                    name="idx_text_title_content_full_text",
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

                logger.info("Índices específicos para colección 'topic_contents' creados/verificados correctamente.")
            except Exception as e:
                logger.error(f"Error creando índices específicos para 'topic_contents': {str(e)}")

            logger.info("Índices de base de datos configurados correctamente")

            # Marcar que los índices han sido configurados exitosamente solo si no hay fallidos
            if not DatabaseConnection._failed_indexes:
                DatabaseConnection._indexes_setup_complete = True
                logger.info("Todos los índices fueron creados exitosamente. Setup completado.")
            else:
                logger.warning(f"Setup completado con {len(DatabaseConnection._failed_indexes)} índices fallidos. Se reintentarán en la próxima llamada.")
                # Listar índices fallidos para debugging
                for failed_index in DatabaseConnection._failed_indexes:
                    logger.warning(f"Índice fallido pendiente de reintento: {failed_index}")

            return True

        except Exception as e:
            logger.error(f"Error configurando índices de base de datos: {str(e)}")
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
    Retorna el estado actual de la configuración de índices.

    Returns:
        dict: Información sobre el estado de configuración de índices
    """
    return {
        "setup_complete": DatabaseConnection._indexes_setup_complete,
        "failed_indexes_count": len(DatabaseConnection._failed_indexes),
        "successful_indexes_count": len(DatabaseConnection._successful_indexes),
        "failed_indexes": list(DatabaseConnection._failed_indexes),
        "successful_indexes": list(DatabaseConnection._successful_indexes)
    }