#!/usr/bin/env python3
"""
Script de diagnóstico para investigar el problema con el endpoint /api/users/me/api-keys
que devuelve api_keys vacío a pesar de la autenticación exitosa.
"""

import sys
import os
import logging
from datetime import datetime
from bson import ObjectId

# Agregar el directorio raíz al path para importar módulos
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from src.shared.database import get_db
from src.shared.encryption_service import encryption_service
from src.users.services import UserService

# Configurar logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

def diagnose_user_api_keys(user_identifier=None):
    """
    Diagnostica el problema de API keys para un usuario específico.
    
    Args:
        user_identifier: Email o user_id del usuario. Si es None, busca usuarios con api_keys.
    """
    try:
        db = get_db()
        users_collection = db.users
        user_service = UserService()
        
        print("=" * 60)
        print("DIAGNÓSTICO DE API KEYS - SapiensAI")
        print("=" * 60)
        print(f"Fecha: {datetime.now()}")
        print()
        
        # Si no se proporciona un usuario específico, buscar usuarios con api_keys
        if user_identifier is None:
            print("🔍 Buscando usuarios con campo api_keys...")
            users_with_keys = list(users_collection.find(
                {"api_keys": {"$exists": True, "$ne": {}}},
                {"_id": 1, "email": 1, "name": 1, "api_keys": 1}
            ))
            
            if not users_with_keys:
                print("❌ No se encontraron usuarios con API keys almacenadas.")
                print("\n🔍 Verificando usuarios recientes...")
                recent_users = list(users_collection.find(
                    {},
                    {"_id": 1, "email": 1, "name": 1, "api_keys": 1, "created_at": 1}
                ).sort("created_at", -1).limit(5))
                
                print(f"\n📋 Últimos 5 usuarios registrados:")
                for i, user in enumerate(recent_users, 1):
                    api_keys_status = "✅ Tiene" if user.get("api_keys") else "❌ No tiene"
                    print(f"  {i}. {user.get('email', 'Sin email')} - {api_keys_status} api_keys")
                    
                return
            
            print(f"✅ Encontrados {len(users_with_keys)} usuarios con API keys.")
            print("\n📋 Lista de usuarios:")
            for i, user in enumerate(users_with_keys, 1):
                print(f"  {i}. {user.get('email', 'Sin email')} (ID: {user['_id']})")
            
            # Analizar el primer usuario encontrado
            user_to_analyze = users_with_keys[0]
            user_identifier = str(user_to_analyze['_id'])
            print(f"\n🎯 Analizando usuario: {user_to_analyze.get('email', 'Sin email')}")
        
        # Buscar el usuario específico
        if '@' in str(user_identifier):
            user = users_collection.find_one({"email": user_identifier})
            search_type = "email"
        else:
            try:
                user = users_collection.find_one({"_id": ObjectId(user_identifier)})
                search_type = "ID"
            except:
                print(f"❌ ID de usuario inválido: {user_identifier}")
                return
        
        if not user:
            print(f"❌ Usuario no encontrado ({search_type}: {user_identifier})")
            return
        
        user_id = str(user['_id'])
        user_email = user.get('email', 'Sin email')
        
        print(f"\n👤 INFORMACIÓN DEL USUARIO:")
        print(f"   ID: {user_id}")
        print(f"   Email: {user_email}")
        print(f"   Nombre: {user.get('name', 'Sin nombre')}")
        print(f"   Rol: {user.get('role', 'Sin rol')}")
        
        # Verificar campo api_keys en el documento
        print(f"\n🔑 ANÁLISIS DEL CAMPO API_KEYS:")
        api_keys_field = user.get('api_keys')
        
        if api_keys_field is None:
            print("   ❌ Campo 'api_keys' no existe en el documento")
        elif api_keys_field == {}:
            print("   ⚠️  Campo 'api_keys' existe pero está vacío")
        else:
            print(f"   ✅ Campo 'api_keys' existe con {len(api_keys_field)} entradas")
            print(f"   📝 Proveedores encontrados: {list(api_keys_field.keys())}")
            
            # Mostrar estructura de las claves (sin revelar contenido)
            for provider, encrypted_key in api_keys_field.items():
                if encrypted_key:
                    key_preview = encrypted_key[:20] + "..." if len(encrypted_key) > 20 else encrypted_key
                    print(f"      - {provider}: {key_preview} (longitud: {len(encrypted_key)})")
                else:
                    print(f"      - {provider}: [VACÍO]")
        
        # Probar el servicio de usuario
        print(f"\n🧪 PRUEBA DEL SERVICIO UserService.get_user_api_keys():")
        try:
            service_result = user_service.get_user_api_keys(user_id)
            
            if service_result is None:
                print("   ❌ El servicio devolvió None (usuario no encontrado)")
            elif service_result == {}:
                print("   ⚠️  El servicio devolvió diccionario vacío")
            else:
                print(f"   ✅ El servicio devolvió {len(service_result)} claves")
                print(f"   📝 Proveedores desencriptados: {list(service_result.keys())}")
                
                # Mostrar preview de las claves desencriptadas (sin revelar contenido completo)
                for provider, decrypted_key in service_result.items():
                    if decrypted_key:
                        key_preview = decrypted_key[:10] + "..." if len(decrypted_key) > 10 else decrypted_key
                        print(f"      - {provider}: {key_preview} (longitud: {len(decrypted_key)})")
                    else:
                        print(f"      - {provider}: [VACÍO DESPUÉS DE DESENCRIPTAR]")
                        
        except Exception as e:
            print(f"   ❌ Error en el servicio: {str(e)}")
            logger.error(f"Error en UserService.get_user_api_keys: {e}", exc_info=True)
        
        # Probar desencriptación manual si hay claves
        if api_keys_field and api_keys_field != {}:
            print(f"\n🔓 PRUEBA DE DESENCRIPTACIÓN MANUAL:")
            try:
                manual_decrypt = encryption_service.decrypt_api_keys_dict(api_keys_field)
                
                if manual_decrypt == {}:
                    print("   ⚠️  Desencriptación manual devolvió diccionario vacío")
                    print("   🔍 Probando desencriptación individual...")
                    
                    for provider, encrypted_key in api_keys_field.items():
                        try:
                            decrypted = encryption_service.decrypt_api_key(encrypted_key)
                            if decrypted:
                                print(f"      ✅ {provider}: Desencriptación exitosa")
                            else:
                                print(f"      ❌ {provider}: Desencriptación falló")
                        except Exception as decrypt_error:
                            print(f"      ❌ {provider}: Error - {str(decrypt_error)}")
                else:
                    print(f"   ✅ Desencriptación manual exitosa: {len(manual_decrypt)} claves")
                    
            except Exception as e:
                print(f"   ❌ Error en desencriptación manual: {str(e)}")
                logger.error(f"Error en desencriptación manual: {e}", exc_info=True)
        
        # Verificar configuración de encriptación
        print(f"\n⚙️  VERIFICACIÓN DE CONFIGURACIÓN:")
        try:
            # Probar encriptación/desencriptación con datos de prueba
            test_key = "test-api-key-12345"
            encrypted_test = encryption_service.encrypt_api_key(test_key)
            
            if encrypted_test:
                decrypted_test = encryption_service.decrypt_api_key(encrypted_test)
                if decrypted_test == test_key:
                    print("   ✅ Servicio de encriptación funciona correctamente")
                else:
                    print("   ❌ Error en el ciclo de encriptación/desencriptación")
            else:
                print("   ❌ Error en la encriptación de prueba")
                
        except Exception as e:
            print(f"   ❌ Error en verificación de encriptación: {str(e)}")
        
        print(f"\n" + "=" * 60)
        print("DIAGNÓSTICO COMPLETADO")
        print("=" * 60)
        
    except Exception as e:
        print(f"❌ Error general en el diagnóstico: {str(e)}")
        logger.error(f"Error en diagnose_user_api_keys: {e}", exc_info=True)

def main():
    try:
        # Connect to database
        db = get_db()
        users_collection = db.users
        
        print("🔍 Diagnosing API Keys Issue for specific user...")
        print("=" * 50)
        
        # Check specific user
        target_email = "luisdanielgm19@gmail.com"
        user = users_collection.find_one({"email": target_email})
        
        if not user:
            print(f"❌ User with email {target_email} not found")
            return
            
        print(f"\n👤 Found user: {user.get('name', 'Unknown')} ({target_email})")
        print(f"📧 User ID: {user['_id']}")
        print(f"📅 Created: {user.get('created_at', 'Unknown')}")
        print(f"📅 Updated: {user.get('updated_at', 'Unknown')}")
        
        # Check api_keys field
        api_keys = user.get('api_keys', None)
        print(f"\n🔑 API Keys field exists: {api_keys is not None}")
        print(f"🔑 API Keys content: {api_keys}")
        print(f"🔑 API Keys type: {type(api_keys)}")
        
        if api_keys:
            print(f"🔑 Number of providers: {len(api_keys)}")
            for provider, encrypted_key in api_keys.items():
                print(f"  - {provider}: {encrypted_key[:20]}..." if len(encrypted_key) > 20 else f"  - {provider}: {encrypted_key}")
        
        # Check users with api_keys
        users_with_keys = list(users_collection.find({"api_keys": {"$exists": True, "$ne": {}}}))
        print(f"\n📊 Total users with api_keys: {len(users_with_keys)}")
        
        # Permitir especificar un usuario como argumento
        user_identifier = None
        if len(sys.argv) > 1:
            user_identifier = sys.argv[1]
            print(f"Analizando usuario específico: {user_identifier}\n")
        
        diagnose_user_api_keys(user_identifier)
    except Exception as e:
        print(f"❌ Error in main: {str(e)}")
        logger.error(f"Error in main: {e}", exc_info=True)

if __name__ == "__main__":
    main()