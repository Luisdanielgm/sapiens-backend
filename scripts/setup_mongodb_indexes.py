#!/usr/bin/env python3
"""
Script para configurar índices de MongoDB para optimizar el sistema de virtualización.
Ejecutar una vez después del deployment inicial para mejorar el performance.
"""

import sys
import os
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from src.shared.database import get_db
import logging

def create_virtualization_indexes():
    """
    Crea índices específicos para optimizar el sistema de virtualización.
    """
    db = get_db()
    indexes_created = 0
    
    print("🚀 Configurando índices de MongoDB para virtualización...")
    print("=" * 60)
    
    # Índices para virtual_generation_tasks (cola de tareas)
    try:
        # Índice compuesto para consultas de cola
        db.virtual_generation_tasks.create_index([
            ("status", 1),
            ("priority", 1), 
            ("created_at", 1)
        ], name="queue_processing_idx")
        print("✅ Índice creado: virtual_generation_tasks.queue_processing_idx")
        indexes_created += 1
        
        # Índice para consultas por estudiante
        db.virtual_generation_tasks.create_index([
            ("student_id", 1),
            ("status", 1)
        ], name="student_queue_status_idx")
        print("✅ Índice creado: virtual_generation_tasks.student_queue_status_idx")
        indexes_created += 1
        
        # Índice para limpieza de tareas antiguas
        db.virtual_generation_tasks.create_index([
            ("status", 1),
            ("completed_at", 1)
        ], name="cleanup_idx")
        print("✅ Índice creado: virtual_generation_tasks.cleanup_idx")
        indexes_created += 1
        
    except Exception as e:
        print(f"⚠️  Error creando índices para virtual_generation_tasks: {str(e)}")
    
    # Índices para virtual_modules
    try:
        # Índice para consultas por estudiante y módulo
        db.virtual_modules.create_index([
            ("student_id", 1),
            ("module_id", 1)
        ], name="student_module_idx", unique=True)
        print("✅ Índice creado: virtual_modules.student_module_idx (único)")
        indexes_created += 1
        
        # Índice para consultas por módulo original
        db.virtual_modules.create_index([
            ("module_id", 1),
            ("status", 1)
        ], name="module_status_idx")
        print("✅ Índice creado: virtual_modules.module_status_idx")
        indexes_created += 1
        
        # Índice para estado de generación
        db.virtual_modules.create_index([
            ("generation_status", 1),
            ("student_id", 1)
        ], name="generation_status_idx")
        print("✅ Índice creado: virtual_modules.generation_status_idx")
        indexes_created += 1
        
    except Exception as e:
        print(f"⚠️  Error creando índices para virtual_modules: {str(e)}")
    
    # Índices para modules (optimizar virtualization readiness)
    try:
        # Índice para módulos habilitados para virtualización
        db.modules.create_index([
            ("study_plan_id", 1),
            ("ready_for_virtualization", 1)
        ], name="virtualization_ready_idx")
        print("✅ Índice creado: modules.virtualization_ready_idx")
        indexes_created += 1
        
        # Índice para detección de cambios
        db.modules.create_index([
            ("last_content_update", 1)
        ], name="content_update_idx")
        print("✅ Índice creado: modules.content_update_idx")
        indexes_created += 1
        
    except Exception as e:
        print(f"⚠️  Error creando índices para modules: {str(e)}")
    
    return indexes_created

def create_general_performance_indexes():
    """
    Crea índices adicionales para mejorar el performance general.
    """
    db = get_db()
    indexes_created = 0
    
    print("\n📈 Configurando índices de performance general...")
    print("=" * 60)
    
    try:
        # Índices para topics (optimizar consultas de contenido)
        db.topics.create_index([
            ("module_id", 1),
            ("status", 1)
        ], name="module_topics_idx", background=True)
        print("✅ Índice creado: topics.module_topics_idx")
        indexes_created += 1
        
        # Índices para evaluations
        db.evaluations.create_index([
            ("module_id", 1),
            ("status", 1)
        ], name="module_evaluations_idx", background=True)
        print("✅ Índice creado: evaluations.module_evaluations_idx")
        indexes_created += 1
        
        # Índices para users (consultas de perfil cognitivo)
        db.users.create_index([
            ("role", 1),
            ("status", 1)
        ], name="user_role_status_idx", background=True)
        print("✅ Índice creado: users.user_role_status_idx")
        indexes_created += 1
        
    except Exception as e:
        print(f"⚠️  Error creando índices de performance: {str(e)}")
    
    return indexes_created

def verify_indexes():
    """
    Verifica que los índices se crearon correctamente.
    """
    db = get_db()
    
    print("\n🔍 Verificando índices creados...")
    print("=" * 60)
    
    collections_to_check = [
        "virtual_generation_tasks",
        "virtual_modules", 
        "modules",
        "virtual_topics",
        "content_templates",
        "topics",
        "evaluations",
        "users"
    ]
    
    total_indexes = 0
    for collection_name in collections_to_check:
        try:
            collection = db[collection_name]
            indexes = list(collection.list_indexes())
            print(f"📋 {collection_name}: {len(indexes)} índices")
            
            for index in indexes:
                if index.get("name") != "_id_":
                    print(f"   - {index.get('name', 'unnamed')}")
            
            total_indexes += len(indexes)
            
        except Exception as e:
            print(f"⚠️  Error verificando índices para {collection_name}: {str(e)}")
    
    print(f"\n📊 Total de índices en el sistema: {total_indexes}")
    return total_indexes

def main():
    """
    Función principal para ejecutar la configuración de índices.
    """
    print("🎯 Configurando índices de MongoDB para Sistema de Virtualización")
    print("=" * 70)
    
    try:
        virtualization_indexes = create_virtualization_indexes()
        
        # Crear índices de performance general
        performance_indexes = create_general_performance_indexes()
        
        # Verificar índices
        total_indexes = verify_indexes()
        
        print("\n" + "=" * 70)
        print("✨ Configuración de índices completada exitosamente!")
        print(f"📊 Resumen:")
        print(f"   - Índices de virtualización: {virtualization_indexes}")
        print(f"   - Índices de performance: {performance_indexes}")
        print(f"   - Total creados: {virtualization_indexes + performance_indexes}")
        print(f"   - Total en sistema: {total_indexes}")
        
        print("\n💡 Recomendaciones:")
        print("   - Monitorear el performance de consultas en producción")
        print("   - Revisar el uso de índices con db.collection.getIndexes()")
        print("   - Considerar índices parciales para colecciones muy grandes")
        
    except Exception as e:
        print(f"❌ Error durante la configuración de índices: {str(e)}")
        sys.exit(1)

if __name__ == "__main__":
    main() 