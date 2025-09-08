#!/usr/bin/env python3
"""
Script para migrar API keys que fueron encriptadas con una clave diferente.
Este script intentará re-encriptar las API keys con la clave actual.
"""

import os
import sys
import logging
from pymongo import MongoClient
from bson import ObjectId
from cryptography.fernet import Fernet
import base64

# Agregar el directorio src al path para importar módulos
sys.path.append(os.path.join(os.path.dirname(__file__), '..', 'src'))

from shared.encryption_service import encryption_service
from shared.database import get_db

# Configurar logging
logging.basicConfig(level=logging.INFO, format='%(levelname)s:%(name)s:%(message)s')

def generate_new_encryption_key():
    """Genera una nueva clave de encriptación."""
    return Fernet.generate_key().decode()

def try_decrypt_with_different_keys(encrypted_data, possible_keys):
    """Intenta desencriptar datos con diferentes claves posibles."""
    for i, key in enumerate(possible_keys):
        try:
            fernet = Fernet(key.encode())
            encrypted_bytes = base64.b64decode(encrypted_data.encode('utf-8'))
            decrypted_bytes = fernet.decrypt(encrypted_bytes)
            plain_text = decrypted_bytes.decode('utf-8')
            print(f"   ✅ Desencriptación exitosa con clave #{i+1}")
            return plain_text, key
        except Exception as e:
            print(f"   ❌ Clave #{i+1} falló: {type(e).__name__}")
            continue
    return None, None

def migrate_user_api_keys():
    """Migra las API keys de todos los usuarios."""
    print("\n" + "="*60)
    print("MIGRACIÓN DE API KEYS - SapiensAI")
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
        
        # Claves posibles para intentar desencriptar
        current_key = os.getenv('ENCRYPTION_KEY')
        possible_keys = []
        
        if current_key:
            possible_keys.append(current_key)
            print(f"📋 Clave actual desde .env: {current_key[:20]}...")
        
        # Agregar algunas claves comunes que podrían haber sido usadas
        # (esto es solo para demostración, en producción deberías tener un registro)
        fallback_keys = [
            # Aquí podrías agregar claves anteriores si las conoces
        ]
        possible_keys.extend(fallback_keys)
        
        migrated_count = 0
        failed_count = 0
        
        for user in users_with_keys:
            user_id = str(user['_id'])
            email = user.get('email', 'Sin email')
            api_keys = user.get('api_keys', {})
            
            print(f"\n👤 Procesando usuario: {email} (ID: {user_id})")
            print(f"   🔑 Proveedores: {list(api_keys.keys())}")
            
            migrated_keys = {}
            user_migration_success = True
            
            for provider, encrypted_key in api_keys.items():
                print(f"   🔄 Procesando {provider}...")
                
                # Intentar desencriptar con la clave actual primero
                try:
                    decrypted = encryption_service.decrypt_api_key(encrypted_key)
                    if decrypted:
                        print(f"   ✅ {provider}: Ya funciona con clave actual")
                        migrated_keys[provider] = encrypted_key  # Mantener como está
                        continue
                except Exception:
                    pass
                
                # Si falla, intentar con claves alternativas
                print(f"   🔍 Intentando desencriptar {provider} con claves alternativas...")
                decrypted_value, working_key = try_decrypt_with_different_keys(
                    encrypted_key, possible_keys
                )
                
                if decrypted_value:
                    # Re-encriptar con la clave actual
                    new_encrypted = encryption_service.encrypt_api_key(decrypted_value)
                    if new_encrypted:
                        migrated_keys[provider] = new_encrypted
                        print(f"   ✅ {provider}: Migrado exitosamente")
                    else:
                        print(f"   ❌ {provider}: Error re-encriptando")
                        user_migration_success = False
                else:
                    print(f"   ❌ {provider}: No se pudo desencriptar con ninguna clave")
                    user_migration_success = False
            
            # Actualizar usuario si la migración fue exitosa
            if user_migration_success and migrated_keys:
                try:
                    result = users_collection.update_one(
                        {"_id": ObjectId(user_id)},
                        {"$set": {"api_keys": migrated_keys}}
                    )
                    if result.modified_count > 0:
                        print(f"   ✅ Usuario actualizado en base de datos")
                        migrated_count += 1
                    else:
                        print(f"   ⚠️  No se realizaron cambios en base de datos")
                except Exception as e:
                    print(f"   ❌ Error actualizando usuario: {str(e)}")
                    failed_count += 1
            else:
                print(f"   ❌ Migración fallida para usuario {email}")
                failed_count += 1
        
        print(f"\n" + "="*60)
        print("RESUMEN DE MIGRACIÓN")
        print("="*60)
        print(f"✅ Usuarios migrados exitosamente: {migrated_count}")
        print(f"❌ Usuarios con errores: {failed_count}")
        print(f"📊 Total procesados: {len(users_with_keys)}")
        
        if migrated_count > 0:
            print("\n🎉 ¡Migración completada! Las API keys deberían funcionar ahora.")
        else:
            print("\n⚠️  No se pudo migrar ninguna API key. Considera:")
            print("   1. Verificar que la clave ENCRYPTION_KEY sea correcta")
            print("   2. Agregar claves anteriores al script si las conoces")
            print("   3. Solicitar a los usuarios que vuelvan a ingresar sus API keys")
            
    except Exception as e:
        print(f"❌ Error durante la migración: {str(e)}")
        logging.error(f"Error en migración: {str(e)}")

def suggest_manual_reset():
    """Sugiere cómo resetear manualmente las API keys."""
    print("\n" + "="*60)
    print("OPCIÓN ALTERNATIVA: RESET MANUAL")
    print("="*60)
    print("Si la migración automática falla, puedes:")
    print("")
    print("1. Limpiar todas las API keys existentes:")
    print("   db.users.updateMany({}, {$set: {api_keys: {}}})")
    print("")
    print("2. Solicitar a los usuarios que vuelvan a ingresar sus API keys")
    print("   desde la interfaz de usuario.")
    print("")
    print("3. Las nuevas API keys se encriptarán con la clave actual.")

if __name__ == "__main__":
    print("Iniciando migración de API keys...")
    
    # Verificar que existe la clave de encriptación
    if not os.getenv('ENCRYPTION_KEY'):
        print("❌ Error: No se encontró ENCRYPTION_KEY en variables de entorno")
        print("   Asegúrate de que el archivo .env contenga ENCRYPTION_KEY")
        sys.exit(1)
    
    try:
        migrate_user_api_keys()
        suggest_manual_reset()
    except KeyboardInterrupt:
        print("\n⚠️  Migración cancelada por el usuario")
    except Exception as e:
        print(f"❌ Error inesperado: {str(e)}")
        logging.error(f"Error inesperado en migración: {str(e)}")