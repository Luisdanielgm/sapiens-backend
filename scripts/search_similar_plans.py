#!/usr/bin/env python3
"""
Script para buscar planes de estudio similares y verificar posibles problemas
con IDs o migraciones incorrectas.

Autor: Sistema de Diagnóstico SapiensAI
Fecha: 2025-01-08
"""

import sys
import os
from datetime import datetime
from bson import ObjectId
from typing import Dict, Optional, List

# Agregar el directorio raíz al path para importar módulos
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from src.shared.database import get_db
from src.shared.logging import get_logger

# Datos del error
PROBLEMATIC_PLAN_ID = "681e3343367dbe6ee9c7ceab"
STUDENT_ID = "67d8634d841411d3638cf9f1"
WORKSPACE_ID = "681e3670367dbe6ee9c7ceac"
CLASS_ID = "680956112463a1016fb02290"

def print_separator(title: str):
    """Imprime un separador visual con título"""
    print("\n" + "="*80)
    print(f" {title}")
    print("="*80)

def print_subsection(title: str):
    """Imprime un subseparador"""
    print(f"\n--- {title} ---")

def search_plans_by_workspace(db, workspace_id: str) -> List[Dict]:
    """Busca planes asociados al workspace"""
    try:
        # Buscar en study_plans
        plans_1 = list(db.study_plans.find({"workspace_id": ObjectId(workspace_id)}))
        
        # Buscar en study_plans_per_subject
        plans_2 = list(db.study_plans_per_subject.find({"workspace_id": ObjectId(workspace_id)}))
        
        return {
            "study_plans": plans_1,
            "study_plans_per_subject": plans_2
        }
    except Exception as e:
        print(f"❌ Error buscando planes por workspace: {str(e)}")
        return {"study_plans": [], "study_plans_per_subject": []}

def search_plans_by_student(db, student_id: str) -> List[Dict]:
    """Busca planes asociados al estudiante"""
    try:
        # Buscar en study_plans por user_id
        plans_1 = list(db.study_plans.find({"user_id": ObjectId(student_id)}))
        
        # Buscar en study_plans_per_subject por author_id
        plans_2 = list(db.study_plans_per_subject.find({"author_id": ObjectId(student_id)}))
        
        return {
            "study_plans": plans_1,
            "study_plans_per_subject": plans_2
        }
    except Exception as e:
        print(f"❌ Error buscando planes por estudiante: {str(e)}")
        return {"study_plans": [], "study_plans_per_subject": []}

def search_plans_by_class(db, class_id: str) -> List[Dict]:
    """Busca planes asignados a la clase"""
    try:
        # Buscar asignaciones de planes a la clase
        assignments = list(db.study_plan_assignments.find({"class_id": ObjectId(class_id)}))
        
        result = []
        for assignment in assignments:
            plan_id = assignment.get("study_plan_id")
            if plan_id:
                # Buscar el plan en ambas colecciones
                plan_1 = db.study_plans.find_one({"_id": ObjectId(plan_id)})
                plan_2 = db.study_plans_per_subject.find_one({"_id": ObjectId(plan_id)})
                
                if plan_1:
                    result.append({"plan": plan_1, "collection": "study_plans", "assignment": assignment})
                if plan_2:
                    result.append({"plan": plan_2, "collection": "study_plans_per_subject", "assignment": assignment})
        
        return result
    except Exception as e:
        print(f"❌ Error buscando planes por clase: {str(e)}")
        return []

def search_similar_ids(db, target_id: str) -> List[Dict]:
    """Busca IDs similares en caso de errores de tipeo"""
    try:
        # Extraer partes del ID para buscar similares
        target_prefix = target_id[:10]  # Primeros 10 caracteres
        target_suffix = target_id[-10:]  # Últimos 10 caracteres
        
        results = []
        
        # Buscar en study_plans
        for collection_name in ["study_plans", "study_plans_per_subject"]:
            collection = db[collection_name]
            
            # Buscar todos los documentos y comparar IDs
            all_docs = list(collection.find({}, {"_id": 1, "name": 1, "title": 1}))
            
            for doc in all_docs:
                doc_id = str(doc["_id"])
                
                # Verificar similitud
                if (doc_id.startswith(target_prefix) or 
                    doc_id.endswith(target_suffix) or 
                    target_id in doc_id or 
                    doc_id in target_id):
                    
                    results.append({
                        "collection": collection_name,
                        "id": doc_id,
                        "name": doc.get("name", doc.get("title", "Sin nombre")),
                        "similarity": "prefix" if doc_id.startswith(target_prefix) else "suffix" if doc_id.endswith(target_suffix) else "partial"
                    })
        
        return results
    except Exception as e:
        print(f"❌ Error buscando IDs similares: {str(e)}")
        return []

def check_virtual_modules_orphaned(db, student_id: str) -> List[Dict]:
    """Busca módulos virtuales huérfanos (sin plan padre)"""
    try:
        # Obtener todos los módulos virtuales del estudiante
        virtual_modules = list(db.virtual_modules.find({"student_id": ObjectId(student_id)}))
        
        orphaned = []
        
        for vm in virtual_modules:
            module_id = vm.get("module_id")
            if module_id:
                # Buscar el módulo original
                original_module = db.modules.find_one({"_id": module_id})
                
                if original_module:
                    study_plan_id = original_module.get("study_plan_id")
                    
                    # Verificar si el plan existe
                    plan_exists = (
                        db.study_plans.find_one({"_id": study_plan_id}) is not None or
                        db.study_plans_per_subject.find_one({"_id": study_plan_id}) is not None
                    )
                    
                    if not plan_exists:
                        orphaned.append({
                            "virtual_module_id": str(vm["_id"]),
                            "module_id": str(module_id),
                            "missing_plan_id": str(study_plan_id),
                            "module_name": original_module.get("name", "Sin nombre")
                        })
        
        return orphaned
    except Exception as e:
        print(f"❌ Error buscando módulos virtuales huérfanos: {str(e)}")
        return []

def get_collection_stats(db) -> Dict:
    """Obtiene estadísticas de las colecciones"""
    try:
        stats = {}
        
        collections = ["study_plans", "study_plans_per_subject", "modules", "virtual_modules", "study_plan_assignments"]
        
        for collection_name in collections:
            if collection_name in db.list_collection_names():
                count = db[collection_name].count_documents({})
                stats[collection_name] = count
            else:
                stats[collection_name] = "No existe"
        
        return stats
    except Exception as e:
        print(f"❌ Error obteniendo estadísticas: {str(e)}")
        return {}

def search_similar_plans():
    """Función principal de búsqueda"""
    logger = get_logger("search_similar_plans")
    
    print_separator("🔍 BÚSQUEDA EXHAUSTIVA DE PLANES DE ESTUDIO")
    print(f"Plan ID problemático: {PROBLEMATIC_PLAN_ID}")
    print(f"Student ID: {STUDENT_ID}")
    print(f"Workspace ID: {WORKSPACE_ID}")
    print(f"Class ID: {CLASS_ID}")
    print(f"Fecha de búsqueda: {datetime.now()}")
    
    try:
        db = get_db()
        logger.info("Conexión a base de datos establecida")
        
        # 1. Estadísticas generales
        print_separator("1. ESTADÍSTICAS DE COLECCIONES")
        stats = get_collection_stats(db)
        for collection, count in stats.items():
            print(f"   📊 {collection}: {count} documentos")
        
        # 2. Buscar planes por workspace
        print_separator("2. PLANES ASOCIADOS AL WORKSPACE")
        workspace_plans = search_plans_by_workspace(db, WORKSPACE_ID)
        
        print(f"📁 Planes en study_plans: {len(workspace_plans['study_plans'])}")
        for plan in workspace_plans['study_plans']:
            print(f"   - ID: {plan['_id']}, Título: {plan.get('title', 'Sin título')}")
        
        print(f"📁 Planes en study_plans_per_subject: {len(workspace_plans['study_plans_per_subject'])}")
        for plan in workspace_plans['study_plans_per_subject']:
            print(f"   - ID: {plan['_id']}, Nombre: {plan.get('name', 'Sin nombre')}")
        
        # 3. Buscar planes por estudiante
        print_separator("3. PLANES ASOCIADOS AL ESTUDIANTE")
        student_plans = search_plans_by_student(db, STUDENT_ID)
        
        print(f"👤 Planes del estudiante en study_plans: {len(student_plans['study_plans'])}")
        for plan in student_plans['study_plans']:
            print(f"   - ID: {plan['_id']}, Título: {plan.get('title', 'Sin título')}")
        
        print(f"👤 Planes del estudiante en study_plans_per_subject: {len(student_plans['study_plans_per_subject'])}")
        for plan in student_plans['study_plans_per_subject']:
            print(f"   - ID: {plan['_id']}, Nombre: {plan.get('name', 'Sin nombre')}")
        
        # 4. Buscar planes asignados a la clase
        print_separator("4. PLANES ASIGNADOS A LA CLASE")
        class_plans = search_plans_by_class(db, CLASS_ID)
        
        print(f"🏫 Planes asignados a la clase: {len(class_plans)}")
        for item in class_plans:
            plan = item['plan']
            collection = item['collection']
            assignment = item['assignment']
            print(f"   - ID: {plan['_id']} (en {collection})")
            print(f"     Nombre: {plan.get('name', plan.get('title', 'Sin nombre'))}")
            print(f"     Asignado: {assignment.get('created_at', 'Fecha desconocida')}")
        
        # 5. Buscar IDs similares
        print_separator("5. BÚSQUEDA DE IDS SIMILARES")
        similar_ids = search_similar_ids(db, PROBLEMATIC_PLAN_ID)
        
        print(f"🔍 IDs similares encontrados: {len(similar_ids)}")
        for item in similar_ids:
            print(f"   - {item['collection']}: {item['id']} ({item['similarity']})")
            print(f"     Nombre: {item['name']}")
        
        # 6. Buscar módulos virtuales huérfanos
        print_separator("6. MÓDULOS VIRTUALES HUÉRFANOS")
        orphaned = check_virtual_modules_orphaned(db, STUDENT_ID)
        
        print(f"🚫 Módulos virtuales huérfanos: {len(orphaned)}")
        for item in orphaned:
            print(f"   - Módulo Virtual: {item['virtual_module_id']}")
            print(f"     Módulo Original: {item['module_id']} ({item['module_name']})")
            print(f"     Plan Faltante: {item['missing_plan_id']}")
        
        # 7. Recomendaciones finales
        print_separator("7. ANÁLISIS Y RECOMENDACIONES")
        
        total_plans_found = (
            len(workspace_plans['study_plans']) + 
            len(workspace_plans['study_plans_per_subject']) +
            len(student_plans['study_plans']) + 
            len(student_plans['study_plans_per_subject']) +
            len(class_plans)
        )
        
        if total_plans_found == 0:
            print("❌ PROBLEMA CRÍTICO: No se encontraron planes relacionados")
            print("\n🔧 POSIBLES CAUSAS:")
            print("   1. El plan fue eliminado de la base de datos")
            print("   2. Error en la migración de datos")
            print("   3. ID incorrecto en la solicitud del frontend")
            print("   4. Problema de sincronización entre colecciones")
            
            if similar_ids:
                print("\n💡 SUGERENCIA: Se encontraron IDs similares")
                print("   Verificar si alguno de estos es el plan correcto:")
                for item in similar_ids[:3]:  # Mostrar solo los primeros 3
                    print(f"   - {item['id']} ({item['name']})")
        
        elif len(class_plans) > 0:
            print("✅ Se encontraron planes asignados a la clase")
            print("\n🔧 RECOMENDACIÓN:")
            print("   Verificar si el frontend está enviando el ID correcto")
            print("   El plan correcto podría ser uno de los asignados a la clase")
        
        elif len(workspace_plans['study_plans']) > 0 or len(workspace_plans['study_plans_per_subject']) > 0:
            print("✅ Se encontraron planes en el workspace")
            print("\n🔧 RECOMENDACIÓN:")
            print("   El plan problemático podría haber sido reemplazado")
            print("   Verificar la lógica de selección de planes en el frontend")
        
        if orphaned:
            print("\n⚠️ ADVERTENCIA: Módulos virtuales huérfanos detectados")
            print("   Esto indica problemas en la integridad de datos")
            print("   Considerar ejecutar un script de limpieza")
        
        print("\n📋 PRÓXIMOS PASOS RECOMENDADOS:")
        print("   1. Verificar logs del frontend para confirmar el ID enviado")
        print("   2. Revisar la lógica de asignación de planes en la aplicación")
        print("   3. Considerar implementar validación de existencia antes del envío")
        print("   4. Ejecutar migración de datos si es necesario")
        
    except Exception as e:
        logger.error(f"Error durante la búsqueda: {str(e)}")
        print(f"\n❌ ERROR CRÍTICO: {str(e)}")

if __name__ == "__main__":
    search_similar_plans()