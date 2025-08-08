#!/usr/bin/env python3
"""
Script para buscar un ID específico en todas las colecciones de MongoDB
para determinar si el frontend está enviando un ID incorrecto.

Este script busca el ID '681e3343367dbe6ee9c7ceab' en todas las colecciones
de la base de datos para identificar qué tipo de entidad es realmente.
"""

import sys
import os
from bson import ObjectId
from bson.errors import InvalidId
import re

# Agregar el directorio padre al path para importar módulos
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from src.shared.database import get_db

# ID problemático que está causando el error 404
PROBLEMATIC_ID = '681e3343367dbe6ee9c7ceab'
STUDENT_ID = '6814591fa98ca4b5ee002f02'
CLASS_ID = '6814591fa98ca4b5ee002f02'
WORKSPACE_ID = '6814591fa98ca4b5ee002f02'

def format_document(doc, collection_name):
    """Formatea un documento para mostrar información relevante"""
    if not doc:
        return "Documento no encontrado"
    
    formatted = f"\n=== DOCUMENTO ENCONTRADO EN '{collection_name}' ==="
    formatted += f"\nID: {doc.get('_id')}"
    
    # Campos comunes que pueden ayudar a identificar el tipo de documento
    common_fields = ['name', 'title', 'subject_id', 'workspace_id', 'student_id', 
                    'class_id', 'plan_id', 'module_id', 'topic_id', 'type', 
                    'is_personal', 'plan_type', 'created_at', 'updated_at']
    
    for field in common_fields:
        if field in doc:
            formatted += f"\n{field}: {doc[field]}"
    
    # Mostrar todos los campos del documento
    formatted += "\n\n--- TODOS LOS CAMPOS ---"
    for key, value in doc.items():
        if key not in ['_id'] + common_fields:
            # Truncar valores muy largos
            str_value = str(value)
            if len(str_value) > 100:
                str_value = str_value[:100] + "..."
            formatted += f"\n{key}: {str_value}"
    
    return formatted

def search_in_collection(db, collection_name, target_id):
    """Busca un ID específico en una colección"""
    try:
        collection = db[collection_name]
        
        # Buscar por _id como ObjectId
        try:
            obj_id = ObjectId(target_id)
            doc = collection.find_one({'_id': obj_id})
            if doc:
                return doc, 'by_id'
        except InvalidId:
            pass
        
        # Buscar por _id como string
        doc = collection.find_one({'_id': target_id})
        if doc:
            return doc, 'by_string_id'
        
        # Buscar en otros campos que podrían contener el ID
        search_fields = ['plan_id', 'student_id', 'class_id', 'workspace_id', 
                        'module_id', 'topic_id', 'parent_id', 'subject_id']
        
        for field in search_fields:
            # Buscar como ObjectId
            try:
                obj_id = ObjectId(target_id)
                doc = collection.find_one({field: obj_id})
                if doc:
                    return doc, f'by_{field}_objectid'
            except InvalidId:
                pass
            
            # Buscar como string
            doc = collection.find_one({field: target_id})
            if doc:
                return doc, f'by_{field}_string'
        
        return None, None
        
    except Exception as e:
        print(f"Error buscando en colección {collection_name}: {e}")
        return None, None

def search_similar_ids(db, collection_name, target_id):
    """Busca IDs similares en una colección"""
    try:
        collection = db[collection_name]
        
        # Crear patrón regex para IDs similares (mismos primeros/últimos caracteres)
        prefix = target_id[:8]  # Primeros 8 caracteres
        suffix = target_id[-8:]  # Últimos 8 caracteres
        
        # Buscar IDs que empiecen igual
        similar_docs = list(collection.find({
            '_id': {'$regex': f'^{prefix}', '$options': 'i'}
        }).limit(5))
        
        if similar_docs:
            return similar_docs, 'prefix_match'
        
        # Buscar IDs que terminen igual
        similar_docs = list(collection.find({
            '_id': {'$regex': f'{suffix}$', '$options': 'i'}
        }).limit(5))
        
        if similar_docs:
            return similar_docs, 'suffix_match'
        
        return [], None
        
    except Exception as e:
        print(f"Error buscando IDs similares en {collection_name}: {e}")
        return [], None

def get_collection_stats(db, collection_name):
    """Obtiene estadísticas básicas de una colección"""
    try:
        collection = db[collection_name]
        count = collection.count_documents({})
        
        # Obtener un documento de muestra para ver la estructura
        sample = collection.find_one()
        
        return {
            'count': count,
            'sample_fields': list(sample.keys()) if sample else []
        }
    except Exception as e:
        print(f"Error obteniendo estadísticas de {collection_name}: {e}")
        return {'count': 0, 'sample_fields': []}

def main():
    """Función principal del diagnóstico"""
    print("=" * 80)
    print("BÚSQUEDA COMPLETA EN TODAS LAS COLECCIONES")
    print("=" * 80)
    print(f"Buscando ID: {PROBLEMATIC_ID}")
    print(f"Contexto - Student ID: {STUDENT_ID}")
    print(f"Contexto - Class ID: {CLASS_ID}")
    print(f"Contexto - Workspace ID: {WORKSPACE_ID}")
    print("=" * 80)
    
    try:
        # Conectar a la base de datos
        db = get_db()
        
        # Obtener todas las colecciones
        collection_names = db.list_collection_names()
        print(f"\nTotal de colecciones encontradas: {len(collection_names)}")
        print(f"Colecciones: {', '.join(collection_names)}")
        
        found_documents = []
        similar_documents = []
        
        # Buscar en cada colección
        for collection_name in collection_names:
            print(f"\n--- Buscando en '{collection_name}' ---")
            
            # Obtener estadísticas de la colección
            stats = get_collection_stats(db, collection_name)
            print(f"Documentos en colección: {stats['count']}")
            print(f"Campos de muestra: {', '.join(stats['sample_fields'][:10])}")
            
            # Buscar el ID exacto
            doc, match_type = search_in_collection(db, collection_name, PROBLEMATIC_ID)
            if doc:
                print(f"\n✅ ENCONTRADO en '{collection_name}' (método: {match_type})")
                print(format_document(doc, collection_name))
                found_documents.append({
                    'collection': collection_name,
                    'document': doc,
                    'match_type': match_type
                })
            else:
                print(f"❌ No encontrado en '{collection_name}'")
            
            # Buscar IDs similares
            similar_docs, similarity_type = search_similar_ids(db, collection_name, PROBLEMATIC_ID)
            if similar_docs:
                print(f"\n🔍 IDs similares encontrados en '{collection_name}' ({similarity_type}):")
                for i, similar_doc in enumerate(similar_docs[:3]):
                    print(f"  {i+1}. ID: {similar_doc.get('_id')} - Campos: {list(similar_doc.keys())[:5]}")
                similar_documents.extend([{
                    'collection': collection_name,
                    'document': doc,
                    'similarity_type': similarity_type
                } for doc in similar_docs])
        
        # Resumen de resultados
        print("\n" + "=" * 80)
        print("RESUMEN DE RESULTADOS")
        print("=" * 80)
        
        if found_documents:
            print(f"\n✅ ID ENCONTRADO EN {len(found_documents)} COLECCIÓN(ES):")
            for result in found_documents:
                print(f"  - {result['collection']} (método: {result['match_type']})")
                
                # Determinar el tipo de entidad
                doc = result['document']
                entity_type = "Desconocido"
                
                if result['collection'] in ['study_plans', 'study_plans_per_subject']:
                    entity_type = "Plan de Estudios"
                elif result['collection'] == 'modules':
                    entity_type = "Módulo"
                elif result['collection'] == 'topics':
                    entity_type = "Tema/Tópico"
                elif result['collection'] == 'virtual_modules':
                    entity_type = "Módulo Virtual"
                elif result['collection'] == 'students':
                    entity_type = "Estudiante"
                elif result['collection'] == 'classes':
                    entity_type = "Clase"
                elif result['collection'] == 'workspaces':
                    entity_type = "Workspace"
                elif 'name' in doc or 'title' in doc:
                    entity_type = f"Entidad con nombre: {doc.get('name', doc.get('title', 'Sin nombre'))}"
                
                print(f"    Tipo de entidad: {entity_type}")
        else:
            print("\n❌ ID NO ENCONTRADO EN NINGUNA COLECCIÓN")
        
        if similar_documents:
            print(f"\n🔍 IDs similares encontrados en {len(set(r['collection'] for r in similar_documents))} colección(es)")
        
        # Recomendaciones
        print("\n" + "=" * 80)
        print("RECOMENDACIONES")
        print("=" * 80)
        
        if found_documents:
            print("\n1. ✅ El ID SÍ existe en la base de datos")
            
            # Verificar si está en la colección correcta
            study_plan_collections = ['study_plans', 'study_plans_per_subject']
            found_in_study_plans = any(r['collection'] in study_plan_collections for r in found_documents)
            
            if found_in_study_plans:
                print("2. ✅ El ID corresponde a un plan de estudios")
                print("3. 🔍 El problema puede estar en:")
                print("   - Lógica de validación en el endpoint /api/virtual/progressive-generation")
                print("   - Permisos o filtros adicionales en la consulta")
                print("   - Validación de relaciones (student_id, class_id, workspace_id)")
            else:
                print("2. ⚠️  EL ID NO CORRESPONDE A UN PLAN DE ESTUDIOS")
                entity_types = []
                for result in found_documents:
                    doc = result['document']
                    if result['collection'] == 'modules':
                        entity_types.append("Módulo")
                    elif result['collection'] == 'topics':
                        entity_types.append("Tema/Tópico")
                    elif result['collection'] == 'virtual_modules':
                        entity_types.append("Módulo Virtual")
                    else:
                        entity_types.append(f"Entidad de tipo '{result['collection']}'")
                
                print(f"3. 🚨 El frontend está enviando un ID de: {', '.join(set(entity_types))}")
                print("4. 🔧 SOLUCIONES:")
                print("   - Verificar la lógica del frontend que obtiene el plan_id")
                print("   - Revisar si se debe enviar un campo diferente")
                print("   - Verificar la relación entre la entidad encontrada y los planes de estudio")
        else:
            print("\n1. ❌ El ID NO existe en ninguna colección")
            print("2. 🔧 SOLUCIONES:")
            print("   - Verificar que el ID no tenga errores tipográficos")
            print("   - Revisar logs de migración de datos")
            print("   - Verificar si el documento fue eliminado accidentalmente")
            print("   - Revisar la lógica del frontend que genera/obtiene este ID")
        
        if similar_documents:
            print("\n5. 🔍 Se encontraron IDs similares - revisar si hay errores tipográficos")
        
        print("\n6. 📋 PRÓXIMOS PASOS RECOMENDADOS:")
        print("   - Revisar logs del frontend para ver de dónde viene este ID")
        print("   - Verificar la lógica de asignación de planes en el frontend")
        print("   - Revisar el endpoint /api/virtual/progressive-generation")
        print("   - Considerar agregar validación de existencia antes de procesar")
        
    except Exception as e:
        print(f"\n❌ Error durante el diagnóstico: {e}")
        import traceback
        traceback.print_exc()

if __name__ == "__main__":
    main()