#!/usr/bin/env python3
"""
Script de diagnóstico específico para identificar problemas en los modelos
"""

import sys
import os
import logging

# Configurar logging
logging.basicConfig(level=logging.DEBUG, format='%(asctime)s - %(levelname)s - %(message)s')

def test_basic_imports():
    """Probar importaciones básicas"""
    try:
        print("1. Probando importaciones básicas...")
        from datetime import datetime
        from typing import Dict, List, Optional
        from bson import ObjectId
        print("✓ Importaciones básicas exitosas")
        return True
    except Exception as e:
        print(f"✗ Error en importaciones básicas: {e}")
        return False

def test_bson_objectid():
    """Probar específicamente ObjectId"""
    try:
        print("2. Probando ObjectId...")
        from bson import ObjectId
        test_id = ObjectId()
        print(f"✓ ObjectId creado: {test_id}")
        return True
    except Exception as e:
        print(f"✗ Error con ObjectId: {e}")
        return False

def test_teacher_profile_class():
    """Probar la clase TeacherProfile específicamente"""
    try:
        print("3. Probando clase TeacherProfile...")
        
        # Importar solo las dependencias necesarias
        from datetime import datetime
        from typing import Dict, List, Optional
        from bson import ObjectId
        
        # Definir la clase aquí para probar
        class TeacherProfile:
            def __init__(self, user_id: str, specialties: List[str] = None):
                self.user_id = ObjectId(user_id) if isinstance(user_id, str) else user_id
                self.specialties = specialties or []
                self.created_at = datetime.now()
        
        # Crear una instancia
        profile = TeacherProfile("507f1f77bcf86cd799439011")
        print(f"✓ TeacherProfile creado: {profile.user_id}")
        return True
    except Exception as e:
        print(f"✗ Error con TeacherProfile: {e}")
        return False

def test_models_import():
    """Probar importar el archivo de modelos completo"""
    try:
        print("4. Probando importación del archivo models.py...")
        import sys
        sys.path.append(os.path.dirname(os.path.abspath(__file__)))
        
        # Intentar importar paso a paso
        print("4.1 Importando módulo profiles.models...")
        from src.profiles import models
        print("✓ Módulo profiles.models importado")
        
        print("4.2 Importando TeacherProfile...")
        from src.profiles.models import TeacherProfile
        print("✓ TeacherProfile importado")
        
        return True
    except Exception as e:
        print(f"✗ Error importando models.py: {e}")
        import traceback
        traceback.print_exc()
        return False

def main():
    """Función principal de diagnóstico"""
    print("=== DIAGNÓSTICO DE MODELOS ===")
    
    tests = [
        test_basic_imports,
        test_bson_objectid,
        test_teacher_profile_class,
        test_models_import
    ]
    
    results = []
    for test in tests:
        try:
            result = test()
            results.append(result)
            print()
        except Exception as e:
            print(f"✗ Error ejecutando {test.__name__}: {e}")
            results.append(False)
            print()
    
    print("=== RESUMEN ===")
    for i, (test, result) in enumerate(zip(tests, results)):
        status = "✓" if result else "✗"
        print(f"{status} {test.__name__}: {'ÉXITO' if result else 'FALLO'}")
    
    if all(results):
        print("\n🎉 Todos los tests pasaron!")
    else:
        print(f"\n❌ {len([r for r in results if not r])} tests fallaron")

if __name__ == "__main__":
    main()