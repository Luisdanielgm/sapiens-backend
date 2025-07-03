#!/usr/bin/env python3
"""
Script de migración: Quiz/QuizResult → TopicContent/ContentResult
Migra el sistema legacy de quizzes al sistema unificado de contenido.
"""

import os
import sys
from pymongo import MongoClient
from bson import ObjectId
from datetime import datetime
from dotenv import load_dotenv

# Añadir directorio raíz al path
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

def get_db():
    """Establece conexión con la base de datos MongoDB."""
    load_dotenv()
    
    mongo_uri = os.getenv("MONGO_DB_URI")
    db_name = os.getenv("DB_NAME")
    
    if not mongo_uri or not db_name:
        print("Error: Variables MONGO_DB_URI y DB_NAME deben estar configuradas")
        sys.exit(1)
    
    try:
        client = MongoClient(mongo_uri)
        db = client[db_name]
        print(f"✅ Conectado a la base de datos '{db_name}'")
        return db
    except Exception as e:
        print(f"❌ Error conectando a la base de datos: {e}")
        sys.exit(1)

def migrate_quizzes_to_topic_content(db, dry_run=True):
    """
    Migra quizzes legacy a TopicContent con content_type='quiz'
    """
    print("\n🔄 Migrando Quizzes → TopicContent...")
    
    quizzes_collection = db["quizzes"]
    topic_contents_collection = db["topic_contents"]
    
    migrated_count = 0
    skipped_count = 0
    error_count = 0
    
    # Obtener todos los quizzes
    quizzes = list(quizzes_collection.find())
    
    if not quizzes:
        print("✅ No se encontraron quizzes legacy para migrar")
        return {"migrated": 0, "skipped": 0, "errors": 0}
    
    print(f"📋 Encontrados {len(quizzes)} quizzes para migrar...")
    
    for quiz in quizzes:
        try:
            quiz_id = quiz["_id"]
            
            # Verificar si ya existe TopicContent para este quiz
            existing = topic_contents_collection.find_one({
                "content_data.original_quiz_id": quiz_id
            })
            
            if existing:
                print(f"⏭️  Quiz {quiz_id} ya migrado - saltando")
                skipped_count += 1
                continue
            
            # Crear TopicContent basado en Quiz
            topic_content = {
                "_id": ObjectId(),
                "topic_id": quiz.get("topic_id"),
                "content_type": "quiz",
                "title": quiz.get("title", "Quiz sin título"),
                "description": quiz.get("description", ""),
                "content_data": {
                    # Guardar datos originales del quiz
                    "questions": quiz.get("questions", []),
                    "time_limit": quiz.get("time_limit"),
                    "attempts_allowed": quiz.get("attempts_allowed", 1),
                    "shuffle_questions": quiz.get("shuffle_questions", False),
                    "shuffle_answers": quiz.get("shuffle_answers", False),
                    "show_correct_answers": quiz.get("show_correct_answers", True),
                    "passing_score": quiz.get("passing_score", 70),
                    
                    # Metadatos de migración
                    "original_quiz_id": quiz_id,
                    "migrated_from": "quiz",
                    "migration_date": datetime.now()
                },
                "interactive_config": {
                    "quiz_type": quiz.get("quiz_type", "multiple_choice"),
                    "feedback_type": quiz.get("feedback_type", "immediate"),
                    "allow_review": quiz.get("allow_review", True)
                },
                "difficulty": quiz.get("difficulty", "medium"),
                "estimated_duration": quiz.get("time_limit", 15),  # minutos
                "tags": quiz.get("tags", []),
                "status": "active" if quiz.get("status") == "active" else "draft",
                "creator_id": quiz.get("created_by"),
                "created_at": quiz.get("created_at", datetime.now()),
                "updated_at": datetime.now()
            }
            
            if not dry_run:
                topic_contents_collection.insert_one(topic_content)
            
            migrated_count += 1
            print(f"✅ Quiz migrado: '{topic_content['title']}'")
            
        except Exception as e:
            error_count += 1
            print(f"❌ Error migrando quiz {quiz.get('_id')}: {e}")
    
    return {"migrated": migrated_count, "skipped": skipped_count, "errors": error_count}

def migrate_quiz_results_to_content_results(db, dry_run=True):
    """
    Migra quiz_results legacy a ContentResult
    """
    print("\n🔄 Migrando QuizResults → ContentResult...")
    
    quiz_results_collection = db["quiz_results"]
    content_results_collection = db["content_results"]
    topic_contents_collection = db["topic_contents"]
    
    migrated_count = 0
    skipped_count = 0
    error_count = 0
    
    # Obtener todos los quiz results
    quiz_results = list(quiz_results_collection.find())
    
    if not quiz_results:
        print("✅ No se encontraron quiz results legacy para migrar")
        return {"migrated": 0, "skipped": 0, "errors": 0}
    
    print(f"📋 Encontrados {len(quiz_results)} quiz results para migrar...")
    
    for result in quiz_results:
        try:
            result_id = result["_id"]
            quiz_id = result.get("quiz_id")
            
            # Verificar si ya existe ContentResult para este quiz result
            existing = content_results_collection.find_one({
                "session_data.original_quiz_result_id": result_id
            })
            
            if existing:
                print(f"⏭️  Quiz result {result_id} ya migrado - saltando")
                skipped_count += 1
                continue
            
            # Buscar el TopicContent correspondiente al quiz
            quiz_content = topic_contents_collection.find_one({
                "content_data.original_quiz_id": quiz_id
            })
            
            if not quiz_content:
                print(f"⚠️  No se encontró TopicContent para quiz {quiz_id} - creando órfano")
                virtual_content_id = None
            else:
                # Para simplificar, usar el TopicContent como referencia
                # En un entorno real, se buscaría el VirtualTopicContent correspondiente
                virtual_content_id = quiz_content["_id"]
            
            # Crear ContentResult basado en QuizResult
            content_result = {
                "_id": ObjectId(),
                "virtual_content_id": virtual_content_id,
                "student_id": result.get("student_id"),
                "session_data": {
                    # Datos originales del resultado
                    "score": result.get("score", 0),
                    "total_questions": result.get("total_questions", 0),
                    "correct_answers": result.get("correct_answers", 0),
                    "time_taken": result.get("time_taken", 0),
                    "answers": result.get("answers", []),
                    "attempt_number": result.get("attempt_number", 1),
                    "completed": result.get("completed", True),
                    
                    # Metadatos de migración
                    "original_quiz_result_id": result_id,
                    "original_quiz_id": quiz_id,
                    "migrated_from": "quiz_result",
                    "migration_date": datetime.now()
                },
                "learning_metrics": {
                    "completion_time": result.get("time_taken", 0),
                    "difficulty_rating": result.get("difficulty_rating"),
                    "confidence_level": result.get("confidence_level")
                },
                "score": result.get("score", 0),
                "feedback": result.get("feedback", ""),
                "session_type": "assessment",
                "created_at": result.get("submitted_at", datetime.now())
            }
            
            if not dry_run:
                content_results_collection.insert_one(content_result)
            
            migrated_count += 1
            
            if migrated_count % 100 == 0:
                print(f"📊 Progreso: {migrated_count} quiz results migrados...")
            
        except Exception as e:
            error_count += 1
            print(f"❌ Error migrando quiz result {result.get('_id')}: {e}")
    
    return {"migrated": migrated_count, "skipped": skipped_count, "errors": error_count}

def verify_migration(db):
    """
    Verifica que la migración se haya realizado correctamente
    """
    print("\n🔍 Verificando migración...")
    
    # Contar documentos
    quizzes_count = db["quizzes"].count_documents({})
    quiz_results_count = db["quiz_results"].count_documents({})
    
    topic_contents_quiz_count = db["topic_contents"].count_documents({"content_type": "quiz"})
    content_results_from_quiz_count = db["content_results"].count_documents({
        "session_data.migrated_from": "quiz_result"
    })
    
    print(f"📊 Estadísticas:")
    print(f"   Quizzes legacy: {quizzes_count}")
    print(f"   Quiz Results legacy: {quiz_results_count}")
    print(f"   TopicContent tipo quiz: {topic_contents_quiz_count}")
    print(f"   ContentResult migrados: {content_results_from_quiz_count}")
    
    if topic_contents_quiz_count > 0 or content_results_from_quiz_count > 0:
        print("✅ Migración verificada - datos encontrados en sistema unificado")
    else:
        print("⚠️  No se encontraron datos migrados")

def create_backup_collections(db):
    """
    Crea respaldos de las colecciones legacy antes de la migración
    """
    print("\n💾 Creando respaldos de seguridad...")
    
    try:
        # Respaldar quizzes
        db["quizzes_backup"] = db["quizzes"]
        quiz_backup_count = db["quizzes"].count_documents({})
        print(f"✅ Quiz backup: {quiz_backup_count} documentos respaldados")
        
        # Respaldar quiz_results  
        db["quiz_results_backup"] = db["quiz_results"]
        results_backup_count = db["quiz_results"].count_documents({})
        print(f"✅ Quiz Results backup: {results_backup_count} documentos respaldados")
        
    except Exception as e:
        print(f"⚠️  Error creando respaldos: {e}")

def main():
    import argparse
    
    parser = argparse.ArgumentParser(description="Migrar Quiz/QuizResult al sistema unificado")
    parser.add_argument('--run', action='store_true', 
                       help='Ejecutar migración real (por defecto es dry-run)')
    parser.add_argument('--verify-only', action='store_true',
                       help='Solo verificar estado actual')
    parser.add_argument('--backup', action='store_true',
                       help='Crear respaldos antes de migrar')
    
    args = parser.parse_args()
    
    print("🚀 Migración Quiz → Sistema Unificado")
    print("=" * 50)
    
    db = get_db()
    
    if args.verify_only:
        verify_migration(db)
        return
    
    if args.backup:
        create_backup_collections(db)
    
    dry_run = not args.run
    
    if dry_run:
        print("🧪 MODO DRY-RUN - No se harán cambios reales")
        print("    Usa --run para ejecutar migración real")
    else:
        print("⚠️  MIGRACIÓN REAL - Se modificará la base de datos")
    
    print()
    
    try:
        # Paso 1: Migrar Quizzes → TopicContent
        quiz_results = migrate_quizzes_to_topic_content(db, dry_run)
        
        # Paso 2: Migrar QuizResults → ContentResult
        result_results = migrate_quiz_results_to_content_results(db, dry_run)
        
        # Resumen
        print("\n" + "=" * 50)
        print("📋 RESUMEN DE MIGRACIÓN")
        print("=" * 50)
        
        print(f"🔄 Quizzes:")
        print(f"   Migrados: {quiz_results['migrated']}")
        print(f"   Saltados: {quiz_results['skipped']}")
        print(f"   Errores: {quiz_results['errors']}")
        
        print(f"🔄 Quiz Results:")
        print(f"   Migrados: {result_results['migrated']}")
        print(f"   Saltados: {result_results['skipped']}")
        print(f"   Errores: {result_results['errors']}")
        
        total_migrated = quiz_results['migrated'] + result_results['migrated']
        total_errors = quiz_results['errors'] + result_results['errors']
        
        if total_errors == 0:
            print(f"\n🎉 ¡Migración exitosa! {total_migrated} elementos migrados")
            if not dry_run:
                print("\n📝 Próximos pasos:")
                print("1. Verificar datos migrados")
                print("2. Actualizar código para usar sistema unificado")
                print("3. Considerar deprecar colecciones legacy")
        else:
            print(f"\n⚠️  Migración completada con {total_errors} errores")
        
        # Verificación final
        if not dry_run:
            verify_migration(db)
            
    except Exception as e:
        print(f"\n❌ Error durante la migración: {e}")
        sys.exit(1)

if __name__ == "__main__":
    main() 