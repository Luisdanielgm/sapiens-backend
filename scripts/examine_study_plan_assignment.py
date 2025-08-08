#!/usr/bin/env python3
"""
Script para examinar específicamente el documento encontrado en 'study_plan_assignments'
y entender la relación con los planes de estudio.
"""

import sys
import os
from bson import ObjectId
from bson.errors import InvalidId
import json

# Agregar el directorio padre al path para importar módulos
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from src.shared.database import get_db

# ID problemático que está causando el error 404
PROBLEMATIC_ID = '681e3343367dbe6ee9c7ceab'
STUDENT_ID = '6814591fa98ca4b5ee002f02'
CLASS_ID = '6814591fa98ca4b5ee002f02'
WORKSPACE_ID = '6814591fa98ca4b5ee002f02'

def format_document_detailed(doc, title="DOCUMENTO"):
    """Formatea un documento de manera detallada y legible"""
    if not doc:
        return "Documento no encontrado"
    
    print(f"\n{'='*60}")
    print(f"{title}")
    print(f"{'='*60}")
    
    for key, value in doc.items():
        if isinstance(value, ObjectId):
            print(f"{key}: {str(value)} (ObjectId)")
        elif isinstance(value, dict):
            print(f"{key}: (Objeto)")
            for sub_key, sub_value in value.items():
                print(f"  {sub_key}: {sub_value}")
        elif isinstance(value, list):
            print(f"{key}: (Lista con {len(value)} elementos)")
            for i, item in enumerate(value[:3]):  # Mostrar solo los primeros 3
                if isinstance(item, dict):
                    print(f"  [{i}]: {list(item.keys())}")
                else:
                    print(f"  [{i}]: {item}")
            if len(value) > 3:
                print(f"  ... y {len(value) - 3} elementos más")
        else:
            print(f"{key}: {value}")

def find_related_study_plan(db, assignment_doc):
    """Busca el plan de estudios relacionado con la asignación"""
    print(f"\n{'='*60}")
    print("BUSCANDO PLAN DE ESTUDIOS RELACIONADO")
    print(f"{'='*60}")
    
    # Buscar en los campos que podrían contener el ID del plan
    plan_id_fields = ['plan_id', 'study_plan_id', 'subject_plan_id']
    
    for field in plan_id_fields:
        if field in assignment_doc:
            plan_id = assignment_doc[field]
            print(f"\nEncontrado campo '{field}': {plan_id}")
            
            # Buscar en study_plans
            try:
                if isinstance(plan_id, str):
                    plan_id = ObjectId(plan_id)
                
                study_plan = db.study_plans.find_one({'_id': plan_id})
                if study_plan:
                    format_document_detailed(study_plan, f"PLAN DE ESTUDIOS ENCONTRADO EN 'study_plans' (por {field})")
                    return study_plan, 'study_plans'
                
                # Buscar en study_plans_per_subject
                study_plan_per_subject = db.study_plans_per_subject.find_one({'_id': plan_id})
                if study_plan_per_subject:
                    format_document_detailed(study_plan_per_subject, f"PLAN DE ESTUDIOS ENCONTRADO EN 'study_plans_per_subject' (por {field})")
                    return study_plan_per_subject, 'study_plans_per_subject'
                
                print(f"❌ No se encontró plan de estudios con ID {plan_id} en ninguna colección")
                
            except Exception as e:
                print(f"Error buscando plan por {field}: {e}")
    
    return None, None

def analyze_assignment_structure(db):
    """Analiza la estructura de la colección study_plan_assignments"""
    print(f"\n{'='*60}")
    print("ANÁLISIS DE ESTRUCTURA DE 'study_plan_assignments'")
    print(f"{'='*60}")
    
    try:
        collection = db.study_plan_assignments
        
        # Obtener estadísticas
        total_docs = collection.count_documents({})
        print(f"Total de documentos: {total_docs}")
        
        # Obtener algunos documentos de muestra
        sample_docs = list(collection.find().limit(3))
        
        print(f"\nEstructura de documentos de muestra:")
        for i, doc in enumerate(sample_docs):
            print(f"\n--- Documento {i+1} ---")
            print(f"ID: {doc.get('_id')}")
            print(f"Campos: {list(doc.keys())}")
            
            # Mostrar campos que podrían ser relevantes
            relevant_fields = ['plan_id', 'study_plan_id', 'subject_plan_id', 'student_id', 'class_id', 'workspace_id']
            for field in relevant_fields:
                if field in doc:
                    print(f"  {field}: {doc[field]}")
        
        # Buscar documentos relacionados con nuestro contexto
        print(f"\n{'='*40}")
        print("DOCUMENTOS RELACIONADOS CON NUESTRO CONTEXTO")
        print(f"{'='*40}")
        
        context_queries = [
            {'student_id': ObjectId(STUDENT_ID)},
            {'class_id': ObjectId(CLASS_ID)},
            {'workspace_id': ObjectId(WORKSPACE_ID)}
        ]
        
        for query in context_queries:
            try:
                related_docs = list(collection.find(query).limit(5))
                if related_docs:
                    field_name = list(query.keys())[0]
                    print(f"\nDocumentos con {field_name} = {query[field_name]}:")
                    for doc in related_docs:
                        print(f"  ID: {doc.get('_id')} - Campos: {list(doc.keys())}")
            except Exception as e:
                print(f"Error en consulta {query}: {e}")
                
    except Exception as e:
        print(f"Error analizando estructura: {e}")

def main():
    """Función principal del análisis"""
    print("=" * 80)
    print("ANÁLISIS DETALLADO DE STUDY_PLAN_ASSIGNMENT")
    print("=" * 80)
    print(f"ID problemático: {PROBLEMATIC_ID}")
    print(f"Contexto - Student ID: {STUDENT_ID}")
    print(f"Contexto - Class ID: {CLASS_ID}")
    print(f"Contexto - Workspace ID: {WORKSPACE_ID}")
    
    try:
        # Conectar a la base de datos
        db = get_db()
        
        # Buscar el documento específico
        assignment_doc = db.study_plan_assignments.find_one({'_id': ObjectId(PROBLEMATIC_ID)})
        
        if assignment_doc:
            format_document_detailed(assignment_doc, "DOCUMENTO EN 'study_plan_assignments'")
            
            # Buscar el plan de estudios relacionado
            related_plan, collection_name = find_related_study_plan(db, assignment_doc)
            
            if related_plan:
                print(f"\n✅ PLAN DE ESTUDIOS RELACIONADO ENCONTRADO EN '{collection_name}'")
                
                # Verificar si el endpoint debería usar el plan_id del assignment
                if 'plan_id' in assignment_doc:
                    print(f"\n🔧 SOLUCIÓN SUGERIDA:")
                    print(f"El frontend debería enviar: {assignment_doc['plan_id']}")
                    print(f"En lugar de: {PROBLEMATIC_ID}")
                    print(f"\nEl endpoint /api/virtual/progressive-generation debería:")
                    print(f"1. Recibir el assignment_id: {PROBLEMATIC_ID}")
                    print(f"2. Buscar en study_plan_assignments")
                    print(f"3. Extraer el plan_id: {assignment_doc['plan_id']}")
                    print(f"4. Usar ese plan_id para buscar en study_plans/study_plans_per_subject")
            else:
                print(f"\n❌ NO SE ENCONTRÓ PLAN DE ESTUDIOS RELACIONADO")
                print(f"El documento de asignación no tiene referencias válidas a planes de estudio")
        else:
            print(f"\n❌ No se encontró el documento con ID {PROBLEMATIC_ID} en study_plan_assignments")
        
        # Analizar la estructura general
        analyze_assignment_structure(db)
        
        print(f"\n{'='*80}")
        print("CONCLUSIONES Y RECOMENDACIONES")
        print(f"{'='*80}")
        
        if assignment_doc:
            print("\n1. ✅ El ID corresponde a una ASIGNACIÓN de plan de estudios, no al plan mismo")
            print("2. 🔧 El frontend está enviando el ID incorrecto al endpoint")
            print("3. 💡 OPCIONES DE SOLUCIÓN:")
            print("   a) Modificar el frontend para enviar el plan_id correcto")
            print("   b) Modificar el endpoint para manejar assignment_ids")
            print("   c) Crear un endpoint específico para asignaciones")
            
            if 'plan_id' in assignment_doc:
                print(f"\n4. 🎯 PLAN_ID CORRECTO: {assignment_doc['plan_id']}")
                print("   El frontend debería usar este ID en lugar del assignment_id")
        
    except Exception as e:
        print(f"\n❌ Error durante el análisis: {e}")
        import traceback
        traceback.print_exc()

if __name__ == "__main__":
    main()