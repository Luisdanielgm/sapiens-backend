#!/usr/bin/env python3
"""
Script simple para limpiar duplicados en topic_contents sin emojis que causan problemas en Windows.
"""

import sys
import os
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from src.shared.database import get_db
from pymongo import ASCENDING
from bson import ObjectId

def find_and_fix_duplicates():
    """
    Encuentra y elimina duplicados en topic_contents.
    """
    db = get_db()
    collection = db.topic_contents

    print("Buscando duplicados en topic_contents...")

    # Encontrar slides duplicados
    pipeline_slides = [
        {"$match": {"content_type": "slide"}},
        {"$sort": {"_id": -1}},
        {"$group": {
            "_id": {"topic_id": "$topic_id", "order": "$order"},
            "count": {"$sum": 1},
            "ids": {"$push": "$_id"}
        }},
        {"$match": {"count": {"$gt": 1}}}
    ]

    slides_duplicados = list(collection.aggregate(pipeline_slides))

    if slides_duplicados:
        print(f"Encontrados {len(slides_duplicados)} grupos de slides duplicados:")

        for dup in slides_duplicados:
            topic_id = dup["_id"]["topic_id"]
            order = dup["_id"]["order"]
            ids = dup["ids"]

            print(f"Topic: {topic_id}, Order: {order}, Count: {dup['count']}")

            # Mantener el más reciente (basado en _id o created_at si existe)
            # y eliminar los demás
            ids_a_eliminar = ids[1:]  # Eliminar todos excepto el primero

            for id_to_delete in ids_a_eliminar:
                result = collection.delete_one({"_id": id_to_delete})
                print(f"  - Eliminado documento duplicado: {id_to_delete} (deleted: {result.deleted_count})")

        print("Limpiando slides duplicados completado.")
    else:
        print("No se encontraron slides duplicados.")

    # Encontrar quizzes duplicados
    pipeline_quizzes = [
        {"$match": {"content_type": "quiz"}},
        {"$sort": {"_id": -1}},
        {"$group": {
            "_id": "$topic_id",
            "count": {"$sum": 1},
            "ids": {"$push": "$_id"}
        }},
        {"$match": {"count": {"$gt": 1}}}
    ]

    quizzes_duplicados = list(collection.aggregate(pipeline_quizzes))

    if quizzes_duplicados:
        print(f"Encontrados {len(quizzes_duplicados)} topics con multiples quizzes:")

        for dup in quizzes_duplicados:
            topic_id = dup["_id"]
            ids = dup["ids"]

            print(f"Topic: {topic_id}, Count: {dup['count']}")

            # Mantener solo el primer quiz
            ids_a_eliminar = ids[1:]

            for id_to_delete in ids_a_eliminar:
                result = collection.delete_one({"_id": id_to_delete})
                print(f"  - Eliminado quiz duplicado: {id_to_delete} (deleted: {result.deleted_count})")

        print("Limpiando quizzes duplicados completado.")
    else:
        print("No se encontraron quizzes duplicados.")

def create_indexes():
    """
    Crea los índices únicos necesarios.
    """
    db = get_db()
    collection = db.topic_contents

    print("\nCreando indices unicos...")

    try:
        # Intentar crear índice único para slides
        collection.create_index(
            [("topic_id", ASCENDING), ("order", ASCENDING)],
            name="idx_unique_slide_topic_order",
            unique=True,
            partialFilterExpression={"content_type": "slide"}
        )
        print("Indice unico para slides creado exitosamente: idx_unique_slide_topic_order")
    except Exception as e:
        print(f"Error creando indice para slides: {e}")

    try:
        # Intentar crear índice único para quizzes
        collection.create_index(
            [("topic_id", ASCENDING)],
            name="idx_unique_quiz_per_topic",
            unique=True,
            partialFilterExpression={"content_type": "quiz"}
        )
        print("Indice unico para quizzes creado exitosamente: idx_unique_quiz_per_topic")
    except Exception as e:
        print(f"Error creando indice para quizzes: {e}")

if __name__ == "__main__":
    try:
        find_and_fix_duplicates()
        create_indexes()
        print("\nProceso completado exitosamente.")
    except Exception as e:
        print(f"Error: {e}")
        sys.exit(1)