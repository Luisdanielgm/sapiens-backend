#!/usr/bin/env python3
"""
Script para configurar índices únicos en la colección topic_contents.
Garantiza integridad de datos para slides y quizzes en el sistema de contenido de temas.

Ejecutar después de implementar Fase 3 (upsert idempotente) para reforzar la integridad
a nivel de base de datos.
"""

import sys
import os
import logging
import argparse
from typing import Tuple, Dict, List
from pymongo import ASCENDING
from pymongo.errors import OperationFailure, PyMongoError
from bson import ObjectId

# Agregar path para importar módulos del proyecto
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from src.shared.database import get_db

# Configurar logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s',
    datefmt='%Y-%m-%d %H:%M:%S'
)
logger = logging.getLogger(__name__)

def check_for_duplicates() -> Tuple[bool, Dict]:
    """
    Verifica si existen duplicados que impedirían crear índices únicos.
    
    Returns:
        Tuple[bool, Dict]: (puede_continuar, reporte_duplicados)
    """
    db = get_db()
    collection = db.topic_contents
    
    reporte = {
        "slides_duplicados": [],
        "quizzes_duplicados": []
    }
    
    print("🔍 Verificando duplicados existentes...")
    print("=" * 60)
    
    # Verificar slides duplicados
    try:
        pipeline_slides = [
            {"$match": {"content_type": "slide"}},
            {"$group": {
                "_id": {"topic_id": "$topic_id", "order": "$order"},
                "count": {"$sum": 1},
                "ids": {"$push": "$_id"}
            }},
            {"$match": {"count": {"$gt": 1}}}
        ]

        slides_duplicados = list(collection.aggregate(pipeline_slides))
        if slides_duplicados:
            print(f"⚠️  Encontrados {len(slides_duplicados)} grupos de slides duplicados:")
            for dup in slides_duplicados:
                ids = dup["ids"]
                print(f"   - Topic: {dup['_id']['topic_id']}, Order: {dup['_id']['order']}, Count: {dup['count']}, IDs: {ids}")
                reporte["slides_duplicados"].append({
                    "topic_id": dup["_id"]["topic_id"],
                    "content_type": "slide",  # Siempre es slide debido al filtro
                    "order": dup["_id"]["order"],
                    "count": dup["count"],
                    "ids": ids
                })
        else:
            print("✅ No se encontraron slides duplicados")
            
    except PyMongoError as e:
        logger.error(f"Error verificando slides duplicados: {str(e)}")
        return False, reporte
    
    # Verificar quizzes duplicados
    try:
        pipeline_quizzes = [
            {"$match": {"content_type": "quiz"}},
            {"$group": {
                "_id": "$topic_id",
                "count": {"$sum": 1},
                "ids": {"$push": "$_id"}
            }},
            {"$match": {"count": {"$gt": 1}}}
        ]
        
        quizzes_duplicados = list(collection.aggregate(pipeline_quizzes))
        if quizzes_duplicados:
            print(f"⚠️  Encontrados {len(quizzes_duplicados)} topics con múltiples quizzes:")
            for dup in quizzes_duplicados:
                ids = dup["ids"]
                print(f"   - Topic: {dup['_id']}, Count: {dup['count']}, IDs: {ids}")
                reporte["quizzes_duplicados"].append({
                    "topic_id": dup["_id"],
                    "count": dup["count"],
                    "ids": ids
                })
        else:
            print("✅ No se encontraron quizzes duplicados")
            
    except PyMongoError as e:
        logger.error(f"Error verificando quizzes duplicados: {str(e)}")
        return False, reporte
    
    puede_continuar = len(reporte["slides_duplicados"]) == 0 and len(reporte["quizzes_duplicados"]) == 0
    
    if not puede_continuar:
        print("\n⚠️  ADVERTENCIA: Se encontraron duplicados existentes.")
        print("   La creación de índices únicos fallará si no se limpian primero.")
        print("   Recomendación: Ejecutar script de limpieza antes de crear índices.")
    
    return puede_continuar, reporte

def create_topic_content_unique_indexes(drop_existing: bool = False) -> int:
    """
    Crea los índices únicos para topic_contents.
    
    Args:
        drop_existing: Si True, elimina índices existentes antes de crear
        
    Returns:
        int: Número de índices creados exitosamente
    """
    db = get_db()
    collection = db.topic_contents
    indexes_created = 0
    
    print("\n🚀 Creando índices únicos...")
    print("=" * 60)
    
    # Índice 1: Slides únicos por (topic_id, content_type, order)
    try:
        # Preservar índice general idx_topic_content_type_order para queries no-slide
        # Solo eliminar si hay un hard conflict (índice único con mismo nombre y claves)
        try:
            existing_indexes = collection.list_indexes()
            for index in existing_indexes:
                if index.get("name") == "idx_topic_content_type_order":
                    index_keys = dict(index.get("key", {}))
                    expected_keys = {"topic_id": 1, "content_type": 1, "order": 1}
                    if index_keys == expected_keys and index.get("unique", False):
                        print("   - Detectado índice único con nombre 'idx_topic_content_type_order'")
                        print("   - Eliminando índice único conflictivo para preservar índice general")
                        collection.drop_index("idx_topic_content_type_order")
                        print("   - ✅ Índice único conflictivo eliminado")

                        # Crear índice general no-único para reemplazarlo
                        collection.create_index(
                            [("topic_id", ASCENDING), ("content_type", ASCENDING), ("order", ASCENDING)],
                            name="idx_topic_content_type_order",
                            unique=False,
                            background=True
                        )
                        print("   - ✅ Índice general no-único recreado para queries no-slide")
                        break
        except Exception as e:
            print(f"   - ⚠️  No se pudo verificar índices existentes: {str(e)}")

        # Asegurar que el índice general exista para óptimo rendimiento de queries no-slide
        try:
            existing_indexes = collection.list_indexes()
            general_index_exists = False
            general_index_valid = False

            # Verificar si existe y validar su definición según los requisitos del comentario
            for idx in existing_indexes:
                if idx.get("name") == "idx_topic_content_type_order":
                    general_index_exists = True

                    # Validar definición del índice según los requisitos del comentario
                    index_keys = dict(idx.get("key", {}))
                    expected_keys = {"topic_id": 1, "content_type": 1, "order": 1}
                    is_unique = idx.get("unique", False)
                    has_partial_filter = "partialFilterExpression" in idx

                    # Validar que cumpla con todos los requisitos: key, unique=False, sin partialFilterExpression
                    if (index_keys == expected_keys and
                        not is_unique and
                        not has_partial_filter):
                        general_index_valid = True
                        print("   - ✅ Índice general idx_topic_content_type_order ya existe con definición correcta (preservado para performance)")
                    else:
                        print(f"   - ⚠️  Índice general idx_topic_content_type_order existe con definición incorrecta:")
                        print(f"      - Keys esperadas: {expected_keys}, encontradas: {index_keys}")
                        print(f"      - Unique esperado: False, encontrado: {is_unique}")
                        print(f"      - PartialFilterExpression esperado: None, encontrado: {idx.get('partialFilterExpression', 'None')}")

                        # Eliminar y recrear con definición correcta en ese mismo bloque
                        try:
                            collection.drop_index("idx_topic_content_type_order")
                            print("   -   Índice incorrecto eliminado")

                            collection.create_index(
                                [("topic_id", ASCENDING), ("content_type", ASCENDING), ("order", ASCENDING)],
                                name="idx_topic_content_type_order",
                                unique=False,
                                background=True
                            )
                            print("   - ✅ Índice general recreado con definición correcta para queries no-slide")
                            general_index_valid = True
                        except Exception as recreate_error:
                            print(f"   - ❌ Error recreando índice: {str(recreate_error)}")

                    break

            if not general_index_exists:
                collection.create_index(
                    [("topic_id", ASCENDING), ("content_type", ASCENDING), ("order", ASCENDING)],
                    name="idx_topic_content_type_order",
                    unique=False,
                    background=True
                )
                print("   - ✅ Índice general no-único creado para queries no-slide")
                general_index_valid = True

        except Exception as e:
            print(f"   - ⚠️  No se pudo asegurar índice general: {str(e)}")


        # Verificar si existe un índice con el mismo nombre pero diferente definición
        try:
            existing_indexes = collection.list_indexes()
            conflicting_index_found = False

            for index in existing_indexes:
                if index.get("name") == "idx_unique_slide_topic_order":
                    # Comparar definición con la esperada
                    index_keys = dict(index.get("key", {}))
                    expected_keys = {"topic_id": 1, "order": 1}
                    expected_unique = True
                    expected_partial_filter = {"content_type": "slide"}

                    actual_unique = index.get("unique", False)
                    actual_partial_filter = index.get("partialFilterExpression")

                    # Verificar si hay diferencias en clave, unique o partialFilterExpression
                    keys_match = index_keys == expected_keys
                    unique_match = actual_unique == expected_unique
                    partial_match = actual_partial_filter == expected_partial_filter

                    if not (keys_match and unique_match and partial_match):
                        # Hay conflicto - el índice existe con diferente definición
                        print("   - ⚠️  Detectado índice con mismo nombre pero diferente definición:")
                        print(f"     • Nombre: idx_unique_slide_topic_order")
                        print(f"     • Keys: {index_keys} (esperado: {expected_keys}) - {'✅' if keys_match else '❌'}")
                        print(f"     • Unique: {actual_unique} (esperado: {expected_unique}) - {'✅' if unique_match else '❌'}")
                        print(f"     • Partial Filter: {actual_partial_filter} (esperado: {expected_partial_filter}) - {'✅' if partial_match else '❌'}")

                        if drop_existing:
                            print("   - 🗑️  Eliminando índice conflictivo (--drop-existing)")
                            try:
                                collection.drop_index("idx_unique_slide_topic_order")
                                print("   - ✅ Índice conflictivo eliminado exitosamente")
                                conflicting_index_found = True
                            except OperationFailure as e:
                                print(f"   - ❌ Error eliminando índice conflictivo: {str(e)}")
                                raise
                        else:
                            print("   - ❌ Conflicto detectado. Use --drop-existing para recrear el índice con la definición correcta")
                            raise OperationFailure("Index already exists with different options", 85)  # MongoDB code 85 for IndexOptionsConflict

                    else:
                        print("   - ✅ Índice idx_unique_slide_topic_order ya existe con definición correcta")
                        indexes_created += 1  # Contar como ya existente
                        conflicting_index_found = True

                    break

        except OperationFailure as e:
            if "already exists with different options" in str(e):
                print(f"❌ Error de conflicto de índice: {str(e)}")
                print("   - Solución: Use --drop-existing para eliminar y recrear el índice")
                sys.exit(1)
            else:
                raise

        # Si no hay conflicto o el índice no existe, crearlo
        if not conflicting_index_found or drop_existing:
            if drop_existing:
                # Eliminar cualquier índice con las mismas claves sin filtro, EXCEPTO el índice general
                try:
                    indexes = list(collection.list_indexes())
                    for index in indexes:
                        if (dict(index.get('key', {})) == {'topic_id': 1, 'order': 1} and
                            not index.get("partialFilterExpression") and
                            index.get("name") != "idx_topic_content_type_order"):
                            collection.drop_index(index["name"])
                            print(f"   - Eliminado índice sin filtro (excepto índice general): {index['name']}")
                            break
                except OperationFailure:
                    # No matching index found, which is fine
                    pass

                collection.create_index(
                [("topic_id", ASCENDING), ("order", ASCENDING)],
                name="idx_unique_slide_topic_order",
                unique=True,
                partialFilterExpression={"content_type": "slide"},
                background=True
            )
        print("✅ Índice único parcial creado: idx_unique_slide_topic_order")
        print("   - Keys: (topic_id, order)")
        print("   - Unique: True")
        print("   - Partial: content_type='slide'")
        print("   - Background: True")
        indexes_created += 1
        
    except Exception as e:
        error_msg = str(e)
        if "11000" in error_msg or "duplicate key" in error_msg.lower():
            print("❌ Error: Índice único parcial no se puede crear debido a duplicados existentes")
            print("   - Limpie duplicados primero o use --force si ya los limpió")
        else:
            print(f"❌ Error creando índice único de slides: {error_msg}")
    
    # Índice 2: Quiz único por topic (parcial)
    try:
        # Verificar si existe un índice con el mismo nombre pero diferente definición para quiz
        try:
            existing_indexes = collection.list_indexes()
            conflicting_quiz_index_found = False

            for index in existing_indexes:
                if index.get("name") == "idx_unique_quiz_per_topic":
                    # Comparar definición con la esperada
                    index_keys = dict(index.get("key", {}))
                    expected_keys = {"topic_id": 1}
                    expected_unique = True
                    expected_partial_filter = {"content_type": "quiz"}

                    actual_unique = index.get("unique", False)
                    actual_partial_filter = index.get("partialFilterExpression")

                    # Verificar si hay diferencias en clave, unique o partialFilterExpression
                    keys_match = index_keys == expected_keys
                    unique_match = actual_unique == expected_unique
                    partial_match = actual_partial_filter == expected_partial_filter

                    if not (keys_match and unique_match and partial_match):
                        # Hay conflicto - el índice existe con diferente definición
                        print("   - ⚠️  Detectado índice quiz con mismo nombre pero diferente definición:")
                        print(f"     • Nombre: idx_unique_quiz_per_topic")
                        print(f"     • Keys: {index_keys} (esperado: {expected_keys}) - {'✅' if keys_match else '❌'}")
                        print(f"     • Unique: {actual_unique} (esperado: {expected_unique}) - {'✅' if unique_match else '❌'}")
                        print(f"     • Partial Filter: {actual_partial_filter} (esperado: {expected_partial_filter}) - {'✅' if partial_match else '❌'}")

                        if drop_existing:
                            print("   - 🗑️  Eliminando índice quiz conflictivo (--drop-existing)")
                            try:
                                collection.drop_index("idx_unique_quiz_per_topic")
                                print("   - ✅ Índice quiz conflictivo eliminado exitosamente")
                                conflicting_quiz_index_found = True
                            except OperationFailure as e:
                                print(f"   - ❌ Error eliminando índice quiz conflictivo: {str(e)}")
                                raise
                        else:
                            print("   - ❌ Conflicto detectado en índice quiz. Use --drop-existing para recrear el índice con la definición correcta")
                            raise OperationFailure("Index already exists with different options", 85)  # MongoDB code 85 for IndexOptionsConflict

                    else:
                        print("   - ✅ Índice idx_unique_quiz_per_topic ya existe con definición correcta")
                        indexes_created += 1  # Contar como ya existente
                        conflicting_quiz_index_found = True

                    break

        except OperationFailure as e:
            if "already exists with different options" in str(e):
                print(f"❌ Error de conflicto de índice quiz: {str(e)}")
                print("   - Solución: Use --drop-existing para eliminar y recrear el índice quiz")
                sys.exit(1)
            else:
                raise

        # Si no hay conflicto o el índice no existe, crearlo
        if not conflicting_quiz_index_found or drop_existing:
            if drop_existing:
                try:
                    collection.drop_index("idx_unique_quiz_per_topic")
                    print("   - Eliminado índice existente 'idx_unique_quiz_per_topic'")
                except OperationFailure:
                    # Index doesn't exist, which is fine
                    pass

            collection.create_index(
                [("topic_id", ASCENDING)],
                name="idx_unique_quiz_per_topic",
                unique=True,
                partialFilterExpression={"content_type": "quiz"},
                background=True
            )
        print("✅ Índice único parcial creado: idx_unique_quiz_per_topic")
        print("   - Keys: (topic_id)")
        print("   - Unique: True")
        print("   - Partial: content_type='quiz'")
        print("   - Background: True")
        indexes_created += 1
        
    except Exception as e:
        error_msg = str(e)
        if "11000" in error_msg or "duplicate key" in error_msg.lower():
            print("❌ Error: Índice único parcial no se puede crear debido a quizzes duplicados")
            print("   - Limpie duplicados primero o use --force si ya los limpió")
        else:
            print(f"❌ Error creando índice único parcial de quizzes: {error_msg}")
    
    return indexes_created

def verify_unique_indexes() -> bool:
    """
    Verifica que los índices únicos se crearon correctamente.
    
    Returns:
        bool: True si ambos índices existen y son correctos
    """
    db = get_db()
    collection = db.topic_contents
    
    print("\n🔍 Verificando índices creados...")
    print("=" * 60)
    
    try:
        indexes = list(collection.list_indexes())
        print(f"📋 topic_contents: {len(indexes)} índices totales")
        
        idx_slides_found = False
        idx_quiz_found = False
        idx_general_found = False

        for index in indexes:
            name = index.get("name", "")
            is_new = name in ["idx_unique_slide_topic_order", "idx_unique_quiz_per_topic"]
            marker = "✅ NUEVO" if is_new else ""

            print(f"   - {name} {marker}")

            if name == "idx_unique_slide_topic_order":
                # Verificar propiedades
                if (index.get("unique") and
                    dict(index.get("key")) == {"topic_id": 1, "order": 1} and
                    index.get("partialFilterExpression") == {"content_type": "slide"}):
                    print("     ✓ Propiedades correctas (único parcial, keys correctas)")
                    idx_slides_found = True
                else:
                    print("     ⚠️  Propiedades incorrectas")

            elif name == "idx_unique_quiz_per_topic":
                # Verificar propiedades
                if (index.get("unique") and
                    dict(index.get("key")) == {"topic_id": 1} and
                    index.get("partialFilterExpression") == {"content_type": "quiz"}):
                    print("     ✓ Propiedades correctas (único parcial, keys correctas)")
                    idx_quiz_found = True
                else:
                    print("     ⚠️  Propiedades incorrectas")

            elif name == "idx_topic_content_type_order":
                # Verificar propiedades del índice general (preservado para performance)
                if (not index.get("unique", False) and
                    dict(index.get("key")) == {"topic_id": 1, "content_type": 1, "order": 1} and
                    not index.get("partialFilterExpression")):
                    print("     ✓ Propiedades correctas (general no-único, preservado para performance)")
                    idx_general_found = True
                else:
                    print("     ⚠️  Propiedades incorrectas en índice general")

        # Éxito si los dos índices únicos están correctos (el general es opcional)
        unique_indexes_success = idx_slides_found and idx_quiz_found

        if unique_indexes_success:
            print("\n✅ Verificación exitosa: Índices únicos correctamente configurados")
            print("   - Índice único parcial para slides: idx_unique_slide_topic_order")
            print("   - Índice único parcial para quizzes: idx_unique_quiz_per_topic")

            # Verificar índice general como advertencia (opcional)
            if idx_general_found:
                print("   - Índice general para performance: idx_topic_content_type_order ✅")
            else:
                print("   - ⚠️  ADVERTENCIA: Índice general para performance (idx_topic_content_type_order) no encontrado")
                print("     • Este índice optimiza consultas no-slide pero es opcional para la funcionalidad")
                print("     • Para crearlo manualmente: use setup_database_indexes() o el script de índices generales")
        else:
            print("\n❌ Verificación fallida: Índices únicos no están correctamente configurados")
            missing = []
            if not idx_slides_found:
                missing.append("índice único para slides")
            if not idx_quiz_found:
                missing.append("índice único para quizzes")
            print(f"   Faltante(s): {', '.join(missing)}")

        return unique_indexes_success
        
    except Exception as e:
        print(f"❌ Error verificando índices: {str(e)}")
        return False

def test_index_constraints() -> Tuple[bool, List[str]]:
    """
    Prueba que los índices únicos realmente previenen duplicados.
    
    Returns:
        Tuple[bool, List[str]]: (todos_pasaron, mensajes_de_prueba)
    """
    db = get_db()
    collection = db.topic_contents
    
    print("\n🧪 Probando constraints de índices únicos...")
    print("=" * 60)
    
    mensajes = []
    todos_pasaron = True
    
    # Generar IDs de prueba que no existan
    test_topic_id = ObjectId()
    test_slide_id = ObjectId()
    test_quiz_id = ObjectId()
    
    # Test 1: Slides duplicados
    try:
        # Insertar slide de prueba
        slide_doc = {
            "_id": test_slide_id,
            "topic_id": test_topic_id,
            "content_type": "slide",
            "order": 1,
            "title": "Test Slide",
            "content": {"text": "Test content"},
            "status": "active",
            "created_at": "2024-01-01T00:00:00Z",
            "updated_at": "2024-01-01T00:00:00Z"
        }
        
        collection.insert_one(slide_doc)
        
        # Intentar insertar duplicado
        duplicate_slide = slide_doc.copy()
        duplicate_slide["_id"] = ObjectId()
        
        try:
            collection.insert_one(duplicate_slide)
            print("❌ Test 1 FALLÓ: Se permitió insertar slide duplicado")
            mensajes.append("Test 1: FALLÓ - Slide duplicado permitido")
            todos_pasaron = False
        except Exception as e:
            if "11000" in str(e) or "duplicate key" in str(e).lower():
                print("✅ Test 1: Índice previene slides duplicados correctamente")
                mensajes.append("Test 1: PASÓ - Slide duplicado rechazado")
            else:
                print(f"❌ Test 1 FALLÓ: Error inesperado: {str(e)}")
                mensajes.append(f"Test 1: FALLÓ - Error inesperado: {str(e)}")
                todos_pasaron = False
        
        # Limpiar
        collection.delete_one({"_id": test_slide_id})
        
    except Exception as e:
        print(f"❌ Error en test de slides: {str(e)}")
        mensajes.append(f"Test 1: ERROR - {str(e)}")
        todos_pasaron = False
    
    # Test 2: Quizzes duplicados
    try:
        # Insertar quiz de prueba
        quiz_doc = {
            "_id": test_quiz_id,
            "topic_id": test_topic_id,
            "content_type": "quiz",
            "order": 1,
            "title": "Test Quiz",
            "content": {"questions": []},
            "status": "active",
            "created_at": "2024-01-01T00:00:00Z",
            "updated_at": "2024-01-01T00:00:00Z"
        }
        
        collection.insert_one(quiz_doc)
        
        # Intentar insertar segundo quiz para mismo topic
        duplicate_quiz = quiz_doc.copy()
        duplicate_quiz["_id"] = ObjectId()
        
        try:
            collection.insert_one(duplicate_quiz)
            print("❌ Test 2 FALLÓ: Se permitió insertar segundo quiz para mismo topic")
            mensajes.append("Test 2: FALLÓ - Segundo quiz permitido")
            todos_pasaron = False
        except Exception as e:
            if "11000" in str(e) or "duplicate key" in str(e).lower():
                print("✅ Test 2: Índice previene múltiples quizzes por topic correctamente")
                mensajes.append("Test 2: PASÓ - Segundo quiz rechazado")
            else:
                print(f"❌ Test 2 FALLÓ: Error inesperado: {str(e)}")
                mensajes.append(f"Test 2: FALLÓ - Error inesperado: {str(e)}")
                todos_pasaron = False
        
        # Limpiar
        collection.delete_one({"_id": test_quiz_id})
        
    except Exception as e:
        print(f"❌ Error en test de quizzes: {str(e)}")
        mensajes.append(f"Test 2: ERROR - {str(e)}")
        todos_pasaron = False

    # Test 3: Upsert idempotencia
    try:
        # Insertar slide inicial con upsert
        result = collection.update_one(
            {"topic_id": test_topic_id, "content_type": "slide", "order": 1},
            {"$set": {
                "title": "Test Slide Original",
                "content": {"text": "Test content original"},
                "status": "active",
                "created_at": "2024-01-01T00:00:00Z",
                "updated_at": "2024-01-01T00:00:00Z"
            }},
            upsert=True
        )

        # Verificar que se insertó un documento
        count_after_first = collection.count_documents({"topic_id": test_topic_id, "content_type": "slide", "order": 1})

        if count_after_first != 1:
            print(f"❌ Test 3 FALLÓ: Se esperaba 1 documento después del primer upsert, se encontraron {count_after_first}")
            mensajes.append(f"Test 3: FALLÓ - Conteo incorrecto después del primer upsert: {count_after_first}")
            todos_pasaron = False
        else:
            # Ejecutar segundo upsert con mismo filtro pero diferente contenido
            result = collection.update_one(
                {"topic_id": test_topic_id, "content_type": "slide", "order": 1},
                {"$set": {
                    "title": "Test Slide Actualizado",
                    "content": {"text": "Test content actualizado"},
                    "status": "active",
                    "updated_at": "2024-01-02T00:00:00Z"
                }},
                upsert=True
            )

            # Verificar idempotencia: aún debe haber solo 1 documento
            count_after_second = collection.count_documents({"topic_id": test_topic_id, "content_type": "slide", "order": 1})

            if count_after_second != 1:
                print(f"❌ Test 3 FALLÓ: Se esperaba 1 documento después del segundo upsert, se encontraron {count_after_second}")
                mensajes.append(f"Test 3: FALLÓ - Idempotencia fallida, conteo: {count_after_second}")
                todos_pasaron = False
            else:
                # Verificar que el documento se actualizó
                doc_actualizado = collection.find_one({"topic_id": test_topic_id, "content_type": "slide", "order": 1})
                if doc_actualizado and doc_actualizado.get("title") == "Test Slide Actualizado":
                    print("✅ Test 3: Upsert idempotente funciona correctamente")
                    mensajes.append("Test 3: PASÓ - Upsert idempotente verificado")
                else:
                    print("❌ Test 3 FALLÓ: El documento no se actualizó correctamente")
                    mensajes.append("Test 3: FALLÓ - El documento no se actualizó")
                    todos_pasaron = False

        # Limpiar documentos creados
        collection.delete_many({"topic_id": test_topic_id})

    except Exception as e:
        print(f"❌ Error en test de upsert idempotencia: {str(e)}")
        mensajes.append(f"Test 3: ERROR - {str(e)}")
        todos_pasaron = False

    return todos_pasaron, mensajes

def validate_index_usage_with_explain() -> bool:
    """
    Valida que el query planner utilice el índice optimizado para queries típicos.

    Returns:
        bool: True si el planner usa el índice correcto
    """
    db = get_db()
    collection = db.topic_contents

    print("\n🔍 Validando uso de índices con explain()...")
    print("=" * 60)

    try:
        # Crear documento de prueba para ensure explain tiene datos sobre los que trabajar
        test_topic_id = ObjectId()
        test_slide = {
            "_id": ObjectId(),
            "topic_id": test_topic_id,
            "content_type": "slide",
            "order": 1,
            "title": "Test Slide para explain",
            "content": {"text": "Test content"},
            "status": "active",
            "created_at": "2024-01-01T00:00:00Z",
            "updated_at": "2024-01-01T00:00:00Z"
        }

        collection.insert_one(test_slide)

        # Query típico utilizado por la aplicación
        typical_query = {
            "topic_id": test_topic_id,
            "content_type": "slide",
            "order": 1
        }

        # Ejecutar explain
        explain_result = collection.find(typical_query).explain("executionStats")

        # Extraer información del winningPlan
        winning_plan = explain_result.get("queryPlanner", {}).get("winningPlan", {})
        input_stage = winning_plan

        # Navegar por los stages hasta encontrar el índice usado
        index_used = None
        while input_stage:
            if "indexName" in input_stage:
                index_used = input_stage["indexName"]
                break
            input_stage = input_stage.get("inputStage")

        # Limpiar documento de prueba
        collection.delete_one({"_id": test_slide["_id"]})

        if index_used == "idx_unique_slide_topic_order":
            print("✅ Query planner está usando el índice optimizado idx_unique_slide_topic_order")
            print("   - El índice parcial se utiliza eficientemente para queries con content_type='slide'")
            return True
        elif index_used:
            print(f"⚠️  Query planner está usando un índice diferente: {index_used}")
            print("   - El índice optimizado podría no estar siendo utilizado")
            return False
        else:
            print("⚠️  Query planner no está usando ningún índice (COLLSCAN)")
            print("   - Considerar revisar la configuración del índice")
            return False

    except Exception as e:
        print(f"❌ Error validando uso de índices: {str(e)}")
        return False

def main():
    """
    Función principal para ejecutar la configuración de índices únicos.
    """
    parser = argparse.ArgumentParser(description="Configurar índices únicos para topic_contents")
    parser.add_argument("--dry-run", action="store_true", help="Solo verificar duplicados, no crear índices")
    parser.add_argument("--skip-tests", action="store_true", help="No ejecutar pruebas de constraints")
    parser.add_argument("--force", action="store_true", help="Continuar incluso si hay duplicados")
    parser.add_argument("--drop-existing", action="store_true", help="Eliminar índices existentes antes de crear")
    
    args = parser.parse_args()
    
    print("🎯 Configurando Índices Únicos para Topic Contents")
    print("   Garantiza integridad de slides y quiz en el sistema de contenido de temas")
    print("=" * 70)
    
    try:
        # Paso 1: Verificar duplicados
        puede_continuar, reporte = check_for_duplicates()
        
        if not puede_continuar and not args.force and not args.dry_run:
            print("\n❌ Abortando debido a duplicados existentes. Use --force para continuar.")
            sys.exit(1)
        
        if args.dry_run:
            print("\n🔍 Modo dry-run: Solo verificación completada.")
            return
        
        # Paso 2: Crear índices
        indexes_created = create_topic_content_unique_indexes(args.drop_existing)
        
        # Paso 3: Verificar índices
        verificacion_ok = verify_unique_indexes()
        
        # Paso 4: Probar constraints (opcional)
        if not args.skip_tests:
            tests_ok, mensajes_tests = test_index_constraints()
        else:
            tests_ok = None
            mensajes_tests = []

        # Paso 5: Validar uso de índices con explain()
        explain_ok = validate_index_usage_with_explain()

        # Resumen final
        print("\n" + "=" * 70)
        print("✨ Configuración completada!")
        print("📊 Resumen:")
        print(f"   - Índices únicos creados: {indexes_created}")
        print(f"   - Verificación: {'✅ Exitosa' if verificacion_ok else '❌ Fallida'}")
        if tests_ok is not None:
            print(f"   - Pruebas: {'✅ ' + str(len([m for m in mensajes_tests if 'PASÓ' in m])) + '/' + str(len(mensajes_tests)) + ' pasadas' if tests_ok else '❌ Fallidas'}")
        print(f"   - Uso de índices (explain): {'✅ Optimizado' if explain_ok else '❌ Subóptimo'}")
        
        print("\n💡 Recomendaciones:")
        print("   - Los índices garantizan que operaciones de upsert en slides sean idempotentes")
        print("   - Solo puede existir un quiz por topic a nivel de base de datos")
        print("   - El índice de slides usa (topic_id, order) como índice único parcial con filtro content_type='slide'")
        print("   - Monitorear logs de aplicación para errores de violación de índice único")
        
        if not verificacion_ok:
            sys.exit(1)
            
    except KeyboardInterrupt:
        print("\n\n⚠️  Interrumpido por usuario")
        sys.exit(1)
    except Exception as e:
        logger.error(f"Error durante la configuración: {str(e)}")
        print(f"\n❌ Error: {str(e)}")
        sys.exit(1)

if __name__ == "__main__":
    main()