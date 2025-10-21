#!/usr/bin/env python3
"""
Script para migrar campos de contenido de slides y quizzes de nivel raíz a dentro del objeto 'content'.
Este script mueve los campos full_text, content_html, narrative_text, slide_plan, template_snapshot y slide_template
de nivel raíz a content.* para documentos con content_type 'slide' o 'quiz'.

Campos migrados:
- full_text: Contenido de texto completo del slide/quiz
- content_html: Contenido HTML del slide/quiz
- narrative_text: Texto narrativo del contenido
- slide_plan: Planificación del slide
- template_snapshot: Instantánea de la plantilla
- slide_template: Plantilla del slide (agregado en esta versión)

Preservación de datos (legacy_raw):
Si el campo 'content' original es un string (no dict), se preserva el valor original
en content['legacy_raw'] antes de convertirlo a dict. Esto asegura que no se pierda
información durante la migración.

Características:
- Modo dry-run para simular migración sin modificar datos
- Procesamiento por lotes para manejar grandes volúmenes de datos
- Estadísticas detalladas por campo migrado
- Validación post-migración para verificar completitud
- Soporte opcional para transacciones MongoDB (requiere MongoDB 4.0+ con replica set)
- Logging mejorado con indicadores de progreso visual
- Manejo robusto de errores con contexto detallado

Uso básico:
  python scripts/migrate_topic_content_fields.py --dry-run                    # Simular migración
  python scripts/migrate_topic_content_fields.py                             # Ejecutar migración
  python scripts/migrate_topic_content_fields.py --use-transactions         # Con transacciones
  python scripts/migrate_topic_content_fields.py --validate-only            # Solo validar

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

def migrate_topic_content_fields(dry_run=False, batch_size=500, commit_every=1000, use_transactions=False):
    """Migra los campos de contenido de slides y quizzes de nivel raíz a content.*"""
    print("\n" + "="*60)
    print("MIGRACIÓN DE CAMPOS DE CONTENIDO - SapiensAI")
    print("="*60)
    print(f"Configuración: batch_size={batch_size}, commit_every={commit_every}, use_transactions={use_transactions}")

    if dry_run:
        print("DRY-RUN: Simulando migracion sin modificar datos")

    try:
        # Conectar a la base de datos
        db = get_db()
        topic_contents_collection = db['topic_contents']

        # Verificar soporte para transacciones
        transactions_supported = False
        if use_transactions:
            try:
                # Intentar iniciar una sesión para verificar soporte
                with db.client.start_session() as session:
                    transactions_supported = True
                print("✅ Transacciones MongoDB disponibles")
            except Exception as e:
                print(f"⚠️  Transacciones no disponibles: {str(e)}")
                print("   Continuando sin transacciones...")
                transactions_supported = False

        # Query para encontrar documentos que necesitan migración
        query = {
            "content_type": {"$in": ["slide", "quiz"]},
            "$or": [
                {"full_text": {"$exists": True}},
                {"content_html": {"$exists": True}},
                {"narrative_text": {"$exists": True}},
                {"slide_plan": {"$exists": True}},
                {"template_snapshot": {"$exists": True}},
                {"slide_template": {"$exists": True}}
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

        fields_to_migrate = ['full_text', 'content_html', 'narrative_text', 'slide_plan', 'template_snapshot', 'slide_template']

        # Estadísticas por campo
        field_migration_stats = {field: 0 for field in fields_to_migrate}
        field_exists_stats = {field: 0 for field in fields_to_migrate}

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

            # Mostrar progreso visual cada 100 documentos
            if processed_count % 100 == 0:
                progress = (processed_count / total_count) * 100
                bar_length = 40
                filled_length = int(bar_length * processed_count // total_count)
                bar = '█' * filled_length + '-' * (bar_length - filled_length)
                print(f"\r[{bar}] {progress:.1f}% ({processed_count}/{total_count})", end='', flush=True)

            # Logging detallado solo en dry-run o cuando hay problemas
            if dry_run or processed_count % commit_every == 0:
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
                    # print(f"   Convirtiendo content a dict y preservando valor original en legacy_raw")
                else:
                    content = original_content.copy()

                # Campos a mover y unset
                fields_to_set = {}
                fields_to_unset = {}

                # Mover campos de raíz a content si no existen ya en content
                for field in fields_to_migrate:
                    if field in doc:
                        field_exists_stats[field] += 1
                        if field not in content:
                            content[field] = doc[field]
                            fields_to_unset[field] = ""
                            field_migration_stats[field] += 1
                            # print(f"   Moviendo {field} de raiz a content.{field}")
                        elif field in content:
                            # print(f"   Campo {field} ya existe en content, eliminando duplicado de raíz")
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
                        # print(f"   DRY-RUN: Se actualizaría documento con: {update_ops}")
                        pass
                else:
                    print(f"   No hay cambios necesarios para este documento")
                    already_correct_count += 1

                # Procesar lote cuando alcanza el tamaño deseado
                    if len(current_batch) >= batch_size:
                        batch_count += 1
                        print(f"\n--- Procesando lote {batch_count} ({len(current_batch)} documentos) ---")
    
                        if not dry_run and current_batch:
                            # Ejecutar operaciones con o sin transacciones
                            if transactions_supported and use_transactions:
                                # Usar transacciones
                                try:
                                    with db.client.start_session() as session:
                                        with session.start_transaction():
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
    
                                            # Ejecutar bulk_write dentro de la transacción
                                            result = topic_contents_collection.bulk_write(bulk_operations, session=session)
                                            batch_migrated = result.modified_count
                                            migrated_count += batch_migrated
                                            print(f"   Lote {batch_count} (con transacción): {batch_migrated} documentos actualizados exitosamente")
                                except Exception as transaction_error:
                                    print(f"   Error en transacción lote {batch_count}: {str(transaction_error)}")
                                    print("   Intentando sin transacciones...")
                                    # Fallback: intentar individualmente sin transacciones
                                    for batch_item in current_batch:
                                        try:
                                            individual_result = topic_contents_collection.update_one(
                                                batch_item['filter'],
                                                batch_item['update']
                                            )
                                            if individual_result.modified_count > 0:
                                                migrated_count += 1
                                                print(f"   Documento {batch_item['doc_id']} actualizado individualmente (fallback)")
                                        except Exception as individual_error:
                                            print(f"   Error en documento {batch_item['doc_id']}: {str(individual_error)}")
                                            error_count += 1
                            else:
                                # Sin transacciones (comportamiento original)
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
                error_type = type(e).__name__
                error_details = {
                    'document_id': doc_id,
                    'content_type': content_type,
                    'error_type': error_type,
                    'error_message': str(e),
                    'fields_in_doc': [f for f in fields_to_migrate if f in doc]
                }
                print(f"   Error procesando documento {doc_id} ({error_type}): {str(e)}")
                print(f"     Campos presentes: {error_details['fields_in_doc']}")
                logging.error(f"Error detallado en documento {doc_id}: {error_details}")
                error_count += 1

        # Procesar cualquier lote restante
        if current_batch and not dry_run:
            batch_count += 1
            print(f"\n--- Procesando lote final {batch_count} ({len(current_batch)} documentos) ---")

            if transactions_supported and use_transactions:
                # Usar transacciones para el lote final
                try:
                    with db.client.start_session() as session:
                        with session.start_transaction():
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

                            result = topic_contents_collection.bulk_write(bulk_operations, session=session)
                            batch_migrated = result.modified_count
                            migrated_count += batch_migrated
                            print(f"   Lote final (con transacción): {batch_migrated} documentos actualizados exitosamente")
                except Exception as transaction_error:
                    print(f"   Error en transacción lote final: {str(transaction_error)}")
                    print("   Intentando sin transacciones...")
                    # Fallback: intentar individualmente sin transacciones
                    for batch_item in current_batch:
                        try:
                            individual_result = topic_contents_collection.update_one(
                                batch_item['filter'],
                                batch_item['update']
                            )
                            if individual_result.modified_count > 0:
                                migrated_count += 1
                                print(f"   Documento {batch_item['doc_id']} actualizado individualmente (fallback)")
                        except Exception as individual_error:
                            print(f"   Error en documento {batch_item['doc_id']}: {str(individual_error)}")
                            error_count += 1
            else:
                # Sin transacciones para el lote final (comportamiento original)
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

        print(f"\nEstadísticas por campo:")
        for field in fields_to_migrate:
            print(f"  {field}: {field_migration_stats[field]} migrados de {field_exists_stats[field]} existentes")

        if dry_run:
            print("\nMODO DRY-RUN: No se modificaron datos reales.")
            print("Ejecuta sin --dry-run para aplicar los cambios.")
        elif migrated_count > 0:
            print("\nMigracion completada! Los campos de contenido han sido movidos a content.*")
        else:
            print("\nNo se pudo migrar ningun documento.")

        # Validación post-migración
        print(f"\n" + "="*60)
        print("VALIDACIÓN POST-MIGRACIÓN")
        print("="*60)

        try:
            validation_query = {
                "content_type": {"$in": ["slide", "quiz"]},
                "$or": [{field: {"$exists": True}} for field in fields_to_migrate]
            }

            problematic_docs = list(topic_contents_collection.find(validation_query, {"_id": 1, "content_type": 1}))
            problematic_count = len(problematic_docs)

            if problematic_count == 0:
                print("Validacion exitosa: No se encontraron documentos con campos al nivel raiz.")
            else:
                print(f"Validacion fallida: {problematic_count} documentos aun tienen campos al nivel raiz.")
                print("Documentos problemáticos:")
                for doc in problematic_docs[:10]:  # Mostrar máximo 10
                    try:
                        print(f"  - ID: {doc['_id']}, Tipo: {doc.get('content_type', 'unknown')}")
                    except UnicodeEncodeError:
                        print(f"  - ID: {str(doc['_id'])}, Tipo: {doc.get('content_type', 'unknown')}")
                if problematic_count > 10:
                    print(f"  ... y {problematic_count - 10} más")
        except Exception as e:
            print(f"Error durante validacion: {str(e)}")
            print("La validacion no se pudo completar.")

    except UnicodeEncodeError as e:
        print(f"Error de codificación durante la migración: {str(e)}")
        print("La migración se completó pero hay problemas de codificación en la salida.")
        logging.error(f"Error de codificación en migracion: {str(e)}")
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
    parser.add_argument('--use-transactions', action='store_true', help='Usar transacciones MongoDB si están disponibles (requiere MongoDB 4.0+ con replica set)')
    parser.add_argument('--validate-only', action='store_true', help='Solo ejecutar validación post-migración sin migrar')
    parser.add_argument('--verbose', action='store_true', help='Logging detallado por documento')
    parser.add_argument('--skip-validation', action='store_true', help='Omitir validación post-migración')
    args = parser.parse_args()

    # Validar argumentos mutuamente excluyentes
    if args.dry_run and args.validate_only:
        print("Error: --dry-run y --validate-only no pueden usarse juntos")
        sys.exit(1)

    if args.validate_only:
        # Solo ejecutar validación
        print("Ejecutando solo validación post-migración...")
        try:
            db = get_db()
            topic_contents_collection = db['topic_contents']
            fields_to_migrate = ['full_text', 'content_html', 'narrative_text', 'slide_plan', 'template_snapshot', 'slide_template']

            validation_query = {
                "content_type": {"$in": ["slide", "quiz"]},
                "$or": [{field: {"$exists": True}} for field in fields_to_migrate]
            }

            problematic_docs = list(topic_contents_collection.find(validation_query, {"_id": 1, "content_type": 1}))
            problematic_count = len(problematic_docs)

            print(f"\n" + "="*60)
            print("VALIDACIÓN POST-MIGRACIÓN")
            print("="*60)

            if problematic_count == 0:
                print("Validacion exitosa: No se encontraron documentos con campos al nivel raiz.")
            else:
                print(f"Validacion fallida: {problematic_count} documentos aun tienen campos al nivel raiz.")
                print("Documentos problemáticos:")
                for doc in problematic_docs[:10]:  # Mostrar máximo 10
                    print(f"  - ID: {doc['_id']}, Tipo: {doc.get('content_type', 'unknown')}")
                if problematic_count > 10:
                    print(f"  ... y {problematic_count - 10} más")

        except Exception as e:
            print(f"Error durante la validación: {str(e)}")
            sys.exit(1)
    else:
        # Ejecutar migración completa
        try:
            migrate_topic_content_fields(
                dry_run=args.dry_run,
                batch_size=args.batch_size,
                commit_every=args.commit_every,
                use_transactions=args.use_transactions
            )
        except Exception as e:
            print(f"Error inesperado: {str(e)}")
            logging.error(f"Error inesperado en migracion: {str(e)}")
            sys.exit(1)

try:
    pass  # Placeholder for any additional code if needed
except KeyboardInterrupt:
    print("\nMigracion cancelada por el usuario")
    sys.exit(1)
except Exception as e:
    print(f"Error inesperado: {str(e)}")
    logging.error(f"Error inesperado en migracion: {str(e)}")
    sys.exit(1)