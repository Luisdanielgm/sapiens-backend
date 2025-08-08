#!/usr/bin/env python3
"""
Script de diagnóstico para investigar el error 404 en el endpoint /api/virtual/progressive-generation
Este script busca el plan de estudios con ID específico en ambas colecciones y proporciona
información detallada para resolver inconsistencias.

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

# ID del plan problemático del error
PROBLEMATIC_PLAN_ID = "681e3343367dbe6ee9c7ceab"
STUDENT_ID = "67d8634d841411d3638cf9f1"
CLASS_ID = "680956112463a1016fb02290"
WORKSPACE_ID = "681e3670367dbe6ee9c7ceac"

def print_separator(title: str):
    """Imprime un separador visual con título"""
    print("\n" + "="*80)
    print(f" {title}")
    print("="*80)

def print_subsection(title: str):
    """Imprime un subseparador"""
    print(f"\n--- {title} ---")

def format_document(doc: Dict, collection_name: str) -> str:
    """Formatea un documento para mostrar información relevante"""
    if not doc:
        return "No encontrado"
    
    result = f"\n📄 Documento encontrado en '{collection_name}':\n"
    result += f"   ID: {doc.get('_id')}\n"
    result += f"   Nombre/Título: {doc.get('name', doc.get('title', 'N/A'))}\n"
    result += f"   Descripción: {doc.get('description', 'N/A')[:100]}...\n"
    result += f"   Autor ID: {doc.get('author_id', doc.get('user_id', 'N/A'))}\n"
    result += f"   Estado: {doc.get('status', 'N/A')}\n"
    result += f"   Creado: {doc.get('created_at', 'N/A')}\n"
    
    # Campos específicos por tipo de colección
    if 'subject_id' in doc:
        result += f"   Subject ID: {doc.get('subject_id')}\n"
    if 'workspace_id' in doc:
        result += f"   Workspace ID: {doc.get('workspace_id')}\n"
    if 'is_personal' in doc:
        result += f"   Es Personal: {doc.get('is_personal')}\n"
    if 'plan_type' in doc:
        result += f"   Tipo de Plan: {doc.get('plan_type')}\n"
    
    return result

def search_plan_in_collection(db, collection_name: str, plan_id: str) -> Optional[Dict]:
    """Busca un plan en una colección específica"""
    try:
        collection = db[collection_name]
        plan = collection.find_one({"_id": ObjectId(plan_id)})
        return plan
    except Exception as e:
        print(f"❌ Error buscando en {collection_name}: {str(e)}")
        return None

def get_related_modules(db, plan_id: str) -> List[Dict]:
    """Obtiene módulos relacionados con el plan"""
    try:
        modules = list(db.modules.find({"study_plan_id": ObjectId(plan_id)}))
        return modules
    except Exception as e:
        print(f"❌ Error obteniendo módulos: {str(e)}")
        return []

def get_virtual_modules(db, student_id: str, plan_id: str) -> List[Dict]:
    """Obtiene módulos virtuales del estudiante para este plan"""
    try:
        # Primero obtener módulos del plan
        modules = get_related_modules(db, plan_id)
        module_ids = [m["_id"] for m in modules]
        
        if not module_ids:
            return []
        
        virtual_modules = list(db.virtual_modules.find({
            "student_id": ObjectId(student_id),
            "module_id": {"$in": module_ids}
        }))
        return virtual_modules
    except Exception as e:
        print(f"❌ Error obteniendo módulos virtuales: {str(e)}")
        return []

def check_published_topics(db, plan_id: str) -> Dict:
    """Verifica temas publicados en los módulos del plan"""
    try:
        modules = get_related_modules(db, plan_id)
        result = {
            "total_modules": len(modules),
            "modules_with_published_topics": 0,
            "total_published_topics": 0,
            "module_details": []
        }
        
        for module in modules:
            published_count = db.topics.count_documents({
                "module_id": module["_id"],
                "published": True
            })
            
            module_info = {
                "module_id": str(module["_id"]),
                "module_name": module.get("name", "Sin nombre"),
                "published_topics": published_count
            }
            
            result["module_details"].append(module_info)
            result["total_published_topics"] += published_count
            
            if published_count > 0:
                result["modules_with_published_topics"] += 1
        
        return result
    except Exception as e:
        print(f"❌ Error verificando temas publicados: {str(e)}")
        return {}

def check_workspace_access(db, workspace_id: str, student_id: str) -> Dict:
    """Verifica el acceso del estudiante al workspace"""
    try:
        # Buscar membresía en institute_members
        membership = db.institute_members.find_one({
            "user_id": ObjectId(student_id),
            "workspace_id": ObjectId(workspace_id)
        })
        
        workspace = db.workspaces.find_one({"_id": ObjectId(workspace_id)})
        
        return {
            "has_membership": membership is not None,
            "membership_details": membership,
            "workspace_exists": workspace is not None,
            "workspace_details": workspace
        }
    except Exception as e:
        print(f"❌ Error verificando acceso al workspace: {str(e)}")
        return {}

def diagnose_study_plan_error():
    """Función principal de diagnóstico"""
    logger = get_logger("diagnose_study_plan_error")
    
    print_separator("🔍 DIAGNÓSTICO DE ERROR EN PLAN DE ESTUDIOS")
    print(f"Plan ID problemático: {PROBLEMATIC_PLAN_ID}")
    print(f"Student ID: {STUDENT_ID}")
    print(f"Workspace ID: {WORKSPACE_ID}")
    print(f"Class ID: {CLASS_ID}")
    print(f"Fecha de diagnóstico: {datetime.now()}")
    
    try:
        db = get_db()
        logger.info("Conexión a base de datos establecida")
        
        # 1. Buscar el plan en ambas colecciones
        print_separator("1. BÚSQUEDA EN COLECCIONES DE PLANES")
        
        plan_in_study_plans = search_plan_in_collection(db, "study_plans", PROBLEMATIC_PLAN_ID)
        plan_in_study_plans_per_subject = search_plan_in_collection(db, "study_plans_per_subject", PROBLEMATIC_PLAN_ID)
        
        print_subsection("Resultados de búsqueda:")
        print(format_document(plan_in_study_plans, "study_plans"))
        print(format_document(plan_in_study_plans_per_subject, "study_plans_per_subject"))
        
        # Determinar en qué colección está el plan
        plan_found = plan_in_study_plans or plan_in_study_plans_per_subject
        plan_collection = "study_plans" if plan_in_study_plans else "study_plans_per_subject" if plan_in_study_plans_per_subject else None
        
        if not plan_found:
            print("\n❌ PROBLEMA CRÍTICO: El plan no existe en ninguna colección")
            print("\n🔧 RECOMENDACIONES:")
            print("   1. Verificar que el ID del plan sea correcto")
            print("   2. Revisar si el plan fue eliminado accidentalmente")
            print("   3. Verificar logs de migración de datos")
            return
        
        print(f"\n✅ Plan encontrado en: {plan_collection}")
        
        # 2. Verificar módulos y temas publicados
        print_separator("2. ANÁLISIS DE MÓDULOS Y TEMAS")
        
        modules_info = check_published_topics(db, PROBLEMATIC_PLAN_ID)
        print(f"📊 Estadísticas de módulos:")
        print(f"   Total de módulos: {modules_info.get('total_modules', 0)}")
        print(f"   Módulos con temas publicados: {modules_info.get('modules_with_published_topics', 0)}")
        print(f"   Total de temas publicados: {modules_info.get('total_published_topics', 0)}")
        
        if modules_info.get('module_details'):
            print("\n📋 Detalle por módulo:")
            for module in modules_info['module_details']:
                status = "✅" if module['published_topics'] > 0 else "❌"
                print(f"   {status} {module['module_name']}: {module['published_topics']} temas publicados")
        
        # 3. Verificar módulos virtuales existentes
        print_separator("3. MÓDULOS VIRTUALES EXISTENTES")
        
        virtual_modules = get_virtual_modules(db, STUDENT_ID, PROBLEMATIC_PLAN_ID)
        print(f"📱 Módulos virtuales encontrados: {len(virtual_modules)}")
        
        if virtual_modules:
            for vm in virtual_modules:
                print(f"   - Módulo Virtual ID: {vm.get('_id')}")
                print(f"     Módulo Original ID: {vm.get('module_id')}")
                print(f"     Estado: {vm.get('generation_status', 'N/A')}")
                print(f"     Progreso: {vm.get('progress', 0)}%")
        
        # 4. Verificar acceso al workspace
        print_separator("4. VERIFICACIÓN DE ACCESO AL WORKSPACE")
        
        workspace_access = check_workspace_access(db, WORKSPACE_ID, STUDENT_ID)
        print(f"🏢 Acceso al workspace:")
        print(f"   Tiene membresía: {'✅' if workspace_access.get('has_membership') else '❌'}")
        print(f"   Workspace existe: {'✅' if workspace_access.get('workspace_exists') else '❌'}")
        
        if workspace_access.get('membership_details'):
            membership = workspace_access['membership_details']
            print(f"   Rol en workspace: {membership.get('role', 'N/A')}")
            print(f"   Estado de membresía: {membership.get('status', 'N/A')}")
        
        # 5. Análisis del problema y recomendaciones
        print_separator("5. DIAGNÓSTICO Y RECOMENDACIONES")
        
        print("🔍 ANÁLISIS DEL PROBLEMA:")
        
        if plan_collection == "study_plans" and not plan_in_study_plans_per_subject:
            print("\n❌ PROBLEMA IDENTIFICADO: Inconsistencia de colecciones")
            print("   El plan existe en 'study_plans' pero el endpoint virtual busca en 'study_plans_per_subject'")
            print("\n🔧 SOLUCIONES RECOMENDADAS:")
            print("   1. INMEDIATA: Migrar el plan a 'study_plans_per_subject'")
            print("   2. TEMPORAL: Modificar el endpoint para buscar en ambas colecciones")
            print("   3. PERMANENTE: Ejecutar migración completa de unificación de planes")
            
            print("\n📝 COMANDO DE MIGRACIÓN INMEDIATA:")
            print(f"   db.study_plans_per_subject.insertOne({{")
            print(f"     ...db.study_plans.findOne({{_id: ObjectId('{PROBLEMATIC_PLAN_ID}')}})")
            print(f"   }})")
        
        elif modules_info.get('modules_with_published_topics', 0) == 0:
            print("\n❌ PROBLEMA IDENTIFICADO: Sin módulos con temas publicados")
            print("   El plan existe pero no tiene módulos con temas publicados")
            print("\n🔧 SOLUCIONES RECOMENDADAS:")
            print("   1. Publicar al menos un tema en algún módulo del plan")
            print("   2. Verificar el estado de los temas existentes")
            print("   3. Revisar el proceso de publicación de contenido")
        
        elif not workspace_access.get('has_membership'):
            print("\n❌ PROBLEMA IDENTIFICADO: Sin acceso al workspace")
            print("   El estudiante no tiene membresía en el workspace")
            print("\n🔧 SOLUCIONES RECOMENDADAS:")
            print("   1. Agregar al estudiante como miembro del workspace")
            print("   2. Verificar permisos de acceso")
            print("   3. Revisar configuración del workspace")
        
        else:
            print("\n✅ CONFIGURACIÓN APARENTEMENTE CORRECTA")
            print("   El plan existe, tiene módulos con temas publicados y el estudiante tiene acceso")
            print("\n🔧 VERIFICACIONES ADICIONALES:")
            print("   1. Revisar logs detallados del endpoint virtual")
            print("   2. Verificar filtros de workspace en el endpoint")
            print("   3. Comprobar validaciones adicionales en el código")
        
        print("\n📋 PRÓXIMOS PASOS:")
        print("   1. Aplicar la solución recomendada")
        print("   2. Probar nuevamente el endpoint /api/virtual/progressive-generation")
        print("   3. Monitorear logs para confirmar la resolución")
        print("   4. Documentar la solución aplicada")
        
    except Exception as e:
        logger.error(f"Error durante el diagnóstico: {str(e)}")
        print(f"\n❌ ERROR CRÍTICO: {str(e)}")
        print("\n🔧 ACCIONES DE EMERGENCIA:")
        print("   1. Verificar conexión a la base de datos")
        print("   2. Revisar configuración de MongoDB")
        print("   3. Contactar al administrador del sistema")

if __name__ == "__main__":
    diagnose_study_plan_error()