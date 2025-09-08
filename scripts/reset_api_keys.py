#!/usr/bin/env python3
"""
Script para limpiar las API keys corruptas y permitir que los usuarios las vuelvan a ingresar.
Este script eliminará todas las API keys existentes que no se pueden desencriptar.
"""

import os
import sys
import logging
from pymongo import MongoClient
from bson import ObjectId

# Agregar el directorio src al path para importar módulos
sys.path.append(os.path.join(os.path.dirname(__file__), '..', 'src'))

from shared.database import get_db

# Configurar logging
logging.basicConfig(level=logging.INFO, format='%(levelname)s:%(name)s:%(message)s')

def reset_corrupted_api_keys():
    """Limpia las API keys corruptas de todos los usuarios."""
    print("\n" + "="*60)
    print("LIMPIEZA DE API KEYS CORRUPTAS - SapiensAI")
    print("="*60)
    
    try:
        # Conectar a la base de datos
        db = get_db()
        users_collection = db['users']
        
        # Buscar usuarios con API keys
        users_with_keys = list(users_collection.find({
            "api_keys": {"$exists": True, "$ne": {}}
        }))
        
        if not users_with_keys:
            print("❌ No se encontraron usuarios con API keys.")
            return
            
        print(f"🔍 Encontrados {len(users_with_keys)} usuarios con API keys.")
        print("\n⚠️  ADVERTENCIA: Este script eliminará todas las API keys existentes.")
        print("   Los usuarios deberán volver a ingresarlas desde la interfaz.")
        
        # Solicitar confirmación
        response = input("\n¿Deseas continuar? (escriba 'SI' para confirmar): ")
        if response.upper() != 'SI':
            print("❌ Operación cancelada por el usuario.")
            return
        
        print("\n🧹 Iniciando limpieza de API keys...")
        
        reset_count = 0
        failed_count = 0
        
        for user in users_with_keys:
            user_id = str(user['_id'])
            email = user.get('email', 'Sin email')
            api_keys = user.get('api_keys', {})
            
            print(f"\n👤 Procesando usuario: {email}")
            print(f"   🔑 Proveedores a limpiar: {list(api_keys.keys())}")
            
            try:
                # Limpiar las API keys del usuario
                result = users_collection.update_one(
                    {"_id": ObjectId(user_id)},
                    {"$set": {"api_keys": {}}}
                )
                
                if result.modified_count > 0:
                    print(f"   ✅ API keys limpiadas exitosamente")
                    reset_count += 1
                else:
                    print(f"   ⚠️  No se realizaron cambios")
                    
            except Exception as e:
                print(f"   ❌ Error limpiando usuario: {str(e)}")
                failed_count += 1
        
        print(f"\n" + "="*60)
        print("RESUMEN DE LIMPIEZA")
        print("="*60)
        print(f"✅ Usuarios limpiados exitosamente: {reset_count}")
        print(f"❌ Usuarios con errores: {failed_count}")
        print(f"📊 Total procesados: {len(users_with_keys)}")
        
        if reset_count > 0:
            print("\n🎉 ¡Limpieza completada exitosamente!")
            print("\n📋 PRÓXIMOS PASOS:")
            print("   1. Reinicia el servidor backend si está ejecutándose")
            print("   2. Los usuarios pueden ahora ingresar sus API keys desde:")
            print("      - Configuración de usuario")
            print("      - Sección de API Keys")
            print("   3. Las nuevas API keys se encriptarán correctamente")
            print("\n✅ El endpoint /api/users/me/api-keys debería funcionar ahora.")
        else:
            print("\n⚠️  No se pudo limpiar ninguna API key.")
            
    except Exception as e:
        print(f"❌ Error durante la limpieza: {str(e)}")
        logging.error(f"Error en limpieza: {str(e)}")

def verify_cleanup():
    """Verifica que la limpieza se haya realizado correctamente."""
    print("\n" + "="*60)
    print("VERIFICACIÓN POST-LIMPIEZA")
    print("="*60)
    
    try:
        db = get_db()
        users_collection = db['users']
        
        # Contar usuarios con API keys vacías
        users_with_empty_keys = users_collection.count_documents({
            "api_keys": {}
        })
        
        # Contar usuarios con API keys no vacías
        users_with_keys = users_collection.count_documents({
            "api_keys": {"$exists": True, "$ne": {}}
        })
        
        print(f"📊 Usuarios con API keys vacías: {users_with_empty_keys}")
        print(f"📊 Usuarios con API keys existentes: {users_with_keys}")
        
        if users_with_keys == 0:
            print("✅ Limpieza verificada: No quedan API keys corruptas")
        else:
            print(f"⚠️  Aún quedan {users_with_keys} usuarios con API keys")
            
    except Exception as e:
        print(f"❌ Error en verificación: {str(e)}")

if __name__ == "__main__":
    print("Iniciando limpieza de API keys corruptas...")
    
    try:
        reset_corrupted_api_keys()
        verify_cleanup()
        
        print("\n" + "="*60)
        print("INFORMACIÓN ADICIONAL")
        print("="*60)
        print("🔧 Para probar el endpoint después de la limpieza:")
        print("   GET /api/users/me/api-keys")
        print("   Debería devolver: {'data': {'api_keys': {}}, 'success': True}")
        print("")
        print("🔑 Para agregar nuevas API keys:")
        print("   PUT /api/users/me/api-keys")
        print("   Body: {'api_keys': {'openrouter': 'tu_api_key_aqui'}}")
        
    except KeyboardInterrupt:
        print("\n⚠️  Limpieza cancelada por el usuario")
    except Exception as e:
        print(f"❌ Error inesperado: {str(e)}")
        logging.error(f"Error inesperado en limpieza: {str(e)}")