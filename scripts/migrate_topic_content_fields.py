#!/usr/bin/env python3
"""
Script para migrar campos de contenido de slides y quizzes de nivel raíz a dentro del objeto 'content'.
Este script mueve los campos full_text, content_html, narrative_text, slide_plan y template_snapshot
de nivel raíz a content.* para documentos con content_type 'slide' o 'quiz'.

Preservación de datos (legacy_raw):
Si el campo 'content' original es un string (no dict), se preserva el valor original
en content['legacy_raw'] antes de convertirlo a dict. Esto asegura que no se pierda
información durante la migración.

Plan de limpieza:
El campo legacy_raw debe ser eliminado después de verificar que los datos han sido migrados correctamente.
Se recomienda implementar un script de limpieza separado que ejecute después de un período de prueba.
"""

import os
import sys
import logging
import argparse
from pymongo import MongoClient
from pymongo.operations import UpdateOne
from bson import ObjectId

# Agregar el directorio src al path para importar módulos
sys.path.append(os.path.join(os.path.dirname(__file__), '..', 'src'))

from shared.database import get_db

# Configurar logging
logging.basicConfig(level=logging.INFO, format='%(levelname)s:%(name)s:%(message)s')

def migrate_topic_content_fields(dry_run=False, batch_size=500, commit_every=1000):
    """Migra los campos de contenido de slides y quizzes de nivel raíz a content.*"""
    print("\n" + "="*60)
    print("MIGRACIÓN DE CAMPOS DE CONTENIDO - SapiensAI")
    print("="*60)
    print(f"Configuración: batch_size={batch_size}, commit_every={commit_every}")

    if dry_run:
        print("DRY-RUN: Simulando migracion sin modificar datos")

    try:
        # Conectar a la base de datos
        db = get_db()
        topic_contents_collection = db['topic_contents']

        # Query para encontrar documentos que necesitan migración
        query = {
            "content_type": {"$in": ["slide", "quiz"]},
            "$or": [
                {"full_text": {"$exists": True}},
                {"content_html": {"$exists": True}},
                {"narrative_text": {"$exists": True}},
                {"slide_plan": {"$exists": True}},
                {"template_snapshot": {"$exists": True}}
            ]
        }

        # Usar cursor con batch_size para paginación
        documents_cursor = topic_contents_collection.find(query, batch_size=batch_size)
        total_count = topic_contents_collection.count_documents(query)

        if total_count == 0:
            print("No se encontraron documentos que necesiten migracion.")
            return

        print(f"Encontrados {total_count} documentos para migrar.")

        migrated_count = 0
        already_correct_count = 0
        error_count = 0
        processed_count = 0
        batch_count = 0

        fields_to_migrate = ['full_text', 'content_html', 'narrative_text', 'slide_plan', 'template_snapshot']

        # Procesar en lotes
        current_batch = []
        batch_operations = []

        for doc in documents_cursor:
            processed_count += 1
            doc_id = str(doc['_id'])
            content_type = doc.get('content_type', 'unknown')

            # Mostrar progreso cada commit_every documentos para checkpoints
            if processed_count % commit_every == 0:
                print(f"Checkpoint de progreso: {processed_count}/{total_count} documentos procesados...")

            # Mostrar progreso cada 100 documentos para seguimiento detallado
            if processed_count % 100 == 0:
                print(f"Procesados {processed_count}/{total_count} documentos...")

            print(f"\nProcesando documento {doc_id} (tipo: {content_type})")

            try:
                # Obtener content actual
                original_content = doc.get('content', {})

                # Inicializar content basado en el tipo de original_content
                if not isinstance(original_content, dict):
                    # Preservar valor original como legacy_raw antes de convertir a dict
                    content = {
                        'legacy_raw': original_content
                    }
                    print(f"   Convirtiendo content a dict y preservando valor original en legacy_raw")
                else:
                    content = original_content.copy()

                # Campos a mover y unset
                fields_to_set = {}
                fields_to_unset = {}

                # Mover campos de raíz a content si no existen ya en content
                for field in fields_to_migrate:
                    if field in doc and field not in content:
                        content[field] = doc[field]
                        fields_to_unset[field] = ""
                        print(f"   Moviendo {field} de raiz a content.{field}")
                    elif field in doc and field in content:
                        print(f"   Campo {field} ya existe en content, eliminando duplicado de raíz")
                        fields_to_unset[field] = ""

                # Preparar operaciones de actualización
                update_ops = {}
                if content != original_content:
                    update_ops["$set"] = {"content": content}
                if fields_to_unset:
                    update_ops["$unset"] = fields_to_unset

                if update_ops:
                    # Agregar operaciones al lote actual
                    current_batch.append({
                        'filter': {"_id": doc['_id']},
                        'update': update_ops,
                        'doc_id': doc_id,
                        'content_type': content_type
                    })

                    if dry_run:
                        print(f"   DRY-RUN: Se actualizaría documento con: {update_ops}")
                else:
                    print(f"   No hay cambios necesarios para este documento")
                    already_correct_count += 1

                # Procesar lote cuando alcanza el tamaño deseado
                if len(current_batch) >= batch_size:
                    batch_count += 1
                    print(f"\n--- Procesando lote {batch_count} ({len(current_batch)} documentos) ---")

                    if not dry_run and current_batch:
                        # Preparar operaciones bulk_write
                        bulk_operations = []
                        for batch_item in current_batch:
                            # Construir operación de actualización
                            update_operation = {
                                'filter': batch_item['filter'],
                                'update': {'$set': batch_item['update']['$set']} if '$set' in batch_item['update'] else {},
                                'upsert': False
                            }

                            # Agregar unset si existe
                            if '$unset' in batch_item['update']:
                                update_operation['update']['$unset'] = batch_item['update']['$unset']

                            bulk_operations.append(
                                UpdateOne(
                                    update_operation['filter'],
                                    update_operation['update'],
                                    upsert=update_operation['upsert']
                                )
                            )

                        # Ejecutar bulk_write
                        try:
                            result = topic_contents_collection.bulk_write(bulk_operations)
                            batch_migrated = result.modified_count
                            migrated_count += batch_migrated
                            print(f"   Lote {batch_count}: {batch_migrated} documentos actualizados exitosamente")
                        except Exception as bulk_error:
                            print(f"   Error en lote {batch_count}: {str(bulk_error)}")
                            # Si falla el batch, intentar individualmente
                            for batch_item in current_batch:
                                try:
                                    individual_result = topic_contents_collection.update_one(
                                        batch_item['filter'],
                                        batch_item['update']
                                    )
                                    if individual_result.modified_count > 0:
                                        migrated_count += 1
                                        print(f"   Documento {batch_item['doc_id']} actualizado individualmente")
                                except Exception as individual_error:
                                    print(f"   Error en documento {batch_item['doc_id']}: {str(individual_error)}")
                                    error_count += 1

                    # Limpiar lote actual
                    current_batch = []

            except Exception as e:
                print(f"   Error procesando documento {doc_id}: {str(e)}")
                logging.error(f"Error en documento {doc_id}: {str(e)}")
                error_count += 1

        # Procesar cualquier lote restante
        if current_batch and not dry_run:
            batch_count += 1
            print(f"\n--- Procesando lote final {batch_count} ({len(current_batch)} documentos) ---")

            # Preparar operaciones bulk_write para el lote final
            bulk_operations = []
            for batch_item in current_batch:
                update_operation = {
                    'filter': batch_item['filter'],
                    'update': {'$set': batch_item['update']['$set']} if '$set' in batch_item['update'] else {},
                    'upsert': False
                }

                if '$unset' in batch_item['update']:
                    update_operation['update']['$unset'] = batch_item['update']['$unset']

                bulk_operations.append(
                    UpdateOne(
                        update_operation['filter'],
                        update_operation['update'],
                        upsert=update_operation['upsert']
                    )
                )

            try:
                result = topic_contents_collection.bulk_write(bulk_operations)
                batch_migrated = result.modified_count
                migrated_count += batch_migrated
                print(f"   Lote final: {batch_migrated} documentos actualizados exitosamente")
            except Exception as bulk_error:
                print(f"   Error en lote final: {str(bulk_error)}")
                # Intentar individualmente si falla el batch
                for batch_item in current_batch:
                    try:
                        individual_result = topic_contents_collection.update_one(
                            batch_item['filter'],
                            batch_item['update']
                        )
                        if individual_result.modified_count > 0:
                            migrated_count += 1
                            print(f"   Documento {batch_item['doc_id']} actualizado individualmente")
                    except Exception as individual_error:
                        print(f"   Error en documento {batch_item['doc_id']}: {str(individual_error)}")
                        error_count += 1

        print(f"\n" + "="*60)
        print("RESUMEN DE MIGRACIÓN")
        print("="*60)
        print(f"Documentos migrados exitosamente: {migrated_count}")
        print(f"Documentos ya correctos: {already_correct_count}")
        print(f"Documentos con errores: {error_count}")
        print(f"Total procesados: {processed_count}")
        print(f"Lotes procesados: {batch_count}")

        if dry_run:
            print("\nMODO DRY-RUN: No se modificaron datos reales.")
            print("Ejecuta sin --dry-run para aplicar los cambios.")
        elif migrated_count > 0:
            print("\nMigracion completada! Los campos de contenido han sido movidos a content.*")
        else:
            print("\nNo se pudo migrar ningun documento.")

    except Exception as e:
        print(f"Error durante la migracion: {str(e)}")
        logging.error(f"Error en migracion: {str(e)}")

if __name__ == "__main__":
    print("Iniciando migracion de campos de contenido...")

    # Parsear argumentos de línea de comandos
    parser = argparse.ArgumentParser(description='Migrar campos de contenido de slides y quizzes')
    parser.add_argument('--dry-run', action='store_true', help='Simular migración sin modificar datos')
    parser.add_argument('--batch-size', type=int, default=500, help='Tamaño de lotes para procesamiento (default: 500)')
    parser.add_argument('--commit-every', type=int, default=1000, help='Confirmar cada N documentos (default: 1000)')
    args = parser.parse_args()

    try:
        migrate_topic_content_fields(
            dry_run=args.dry_run,
            batch_size=args.batch_size,
            commit_every=args.commit_every
        )
    except KeyboardInterrupt:
        print("\nMigracion cancelada por el usuario")
    except Exception as e:
        print(f"Error inesperado: {str(e)}")
        logging.error(f"Error inesperado en migracion: {str(e)}")