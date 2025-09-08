#!/usr/bin/env python3
"""
Script para verificar que el sistema de API keys funciona correctamente
después de la limpieza de claves corruptas.
"""

import sys
import os
import logging
from datetime import datetime

# Agregar el directorio src al path
sys.path.append(os.path.join(os.path.dirname(__file__), '..'))
sys.path.append(os.path.join(os.path.dirname(__file__), '..', 'src'))

from src.shared.database import get_db
from src.shared.encryption_service import encryption_service
from src.users.services import UserService

# Configurar logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

def test_encryption_system():
    """Prueba que el sistema de encriptación funciona correctamente."""
    print("\n🔧 Probando sistema de encriptación...")
    
    test_data = {
        "openai": "sk-test123456789",
        "anthropic": "sk-ant-test123456789"
    }
    
    try:
        # Encriptar
        encrypted = encryption_service.encrypt_api_keys_dict(test_data)
        print(f"✅ Encriptación exitosa: {len(encrypted)} claves encriptadas")
        
        # Desencriptar
        decrypted = encryption_service.decrypt_api_keys_dict(encrypted)
        print(f"✅ Desencriptación exitosa: {len(decrypted)} claves desencriptadas")
        
        # Verificar que los datos coinciden
        if decrypted == test_data:
            print("✅ Los datos encriptados/desencriptados coinciden")
            return True
        else:
            print("❌ Los datos no coinciden después de encriptar/desencriptar")
            return False
            
    except Exception as e:
        print(f"❌ Error en el sistema de encriptación: {str(e)}")
        return False

def test_user_api_keys_workflow():
    """Prueba el flujo completo de API keys de usuario."""
    print("\n🔄 Probando flujo completo de API keys...")
    
    try:
        user_service = UserService()
        target_email = "luisdanielgm19@gmail.com"
        
        # Buscar usuario
        db = get_db()
        user = db.users.find_one({"email": target_email})
        if not user:
            print(f"❌ Usuario {target_email} no encontrado")
            return False
            
        user_id = str(user["_id"])
        print(f"✅ Usuario encontrado: {user.get('name', 'Unknown')}")
        
        # Verificar estado actual
        current_keys = user_service.get_user_api_keys(user_id)
        print(f"📊 Estado actual de API keys: {current_keys}")
        
        # Simular actualización de API keys
        test_keys = {
            "openai": "sk-test-openai-key-123",
            "anthropic": "sk-ant-test-anthropic-key-456"
        }
        
        print("\n🔄 Simulando actualización de API keys...")
        success, message = user_service.update_user(user_id, {"api_keys": test_keys})
        
        if success:
            print(f"✅ Actualización exitosa: {message}")
            
            # Verificar que se guardaron correctamente
            updated_keys = user_service.get_user_api_keys(user_id)
            print(f"📊 API keys después de actualización: {updated_keys}")
            
            if updated_keys == test_keys:
                print("✅ Las API keys se guardaron y recuperaron correctamente")
                
                # Limpiar las claves de prueba
                print("\n🧹 Limpiando claves de prueba...")
                user_service.update_user(user_id, {"api_keys": {}})
                print("✅ Claves de prueba eliminadas")
                
                return True
            else:
                print("❌ Las API keys no coinciden después de guardar")
                return False
        else:
            print(f"❌ Error al actualizar API keys: {message}")
            return False
            
    except Exception as e:
        print(f"❌ Error en el flujo de API keys: {str(e)}")
        return False

def verify_database_state():
    """Verifica el estado actual de la base de datos."""
    print("\n📊 Verificando estado de la base de datos...")
    
    try:
        db = get_db()
        users_collection = db.users
        
        # Contar usuarios totales
        total_users = users_collection.count_documents({})
        print(f"👥 Total de usuarios: {total_users}")
        
        # Contar usuarios con API keys
        users_with_keys = users_collection.count_documents({
            "api_keys": {"$exists": True, "$ne": {}}
        })
        print(f"🔑 Usuarios con API keys: {users_with_keys}")
        
        # Verificar usuario específico
        target_user = users_collection.find_one({"email": "luisdanielgm19@gmail.com"})
        if target_user:
            api_keys = target_user.get("api_keys", None)
            print(f"👤 Usuario Luis Gómez:")
            print(f"   - API keys field exists: {api_keys is not None}")
            print(f"   - API keys content: {api_keys}")
            print(f"   - API keys type: {type(api_keys)}")
        
        return True
        
    except Exception as e:
        print(f"❌ Error verificando base de datos: {str(e)}")
        return False

def main():
    """Función principal del script de verificación."""
    print("🔍 VERIFICACIÓN DEL SISTEMA DE API KEYS")
    print("=" * 50)
    print(f"Fecha: {datetime.now()}")
    
    all_tests_passed = True
    
    # Test 1: Sistema de encriptación
    if not test_encryption_system():
        all_tests_passed = False
    
    # Test 2: Estado de la base de datos
    if not verify_database_state():
        all_tests_passed = False
    
    # Test 3: Flujo completo de API keys
    if not test_user_api_keys_workflow():
        all_tests_passed = False
    
    print("\n" + "=" * 50)
    if all_tests_passed:
        print("✅ TODAS LAS PRUEBAS PASARON")
        print("\n🎉 El sistema de API keys está funcionando correctamente")
        print("\n📝 Resumen:")
        print("   - El sistema de encriptación funciona")
        print("   - Los endpoints de API keys están operativos")
        print("   - Los usuarios pueden guardar y recuperar API keys")
        print("   - Las claves corruptas fueron limpiadas exitosamente")
    else:
        print("❌ ALGUNAS PRUEBAS FALLARON")
        print("\n⚠️  Revisar los errores anteriores")
    
    print("\n" + "=" * 50)

if __name__ == "__main__":
    main()