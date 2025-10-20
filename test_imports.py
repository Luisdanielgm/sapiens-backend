#!/usr/bin/env python3
"""
Script para probar la importación de blueprints
"""

import sys
import traceback

def test_import(module_name, blueprint_name):
    try:
        module = __import__(module_name, fromlist=[blueprint_name])
        blueprint = getattr(module, blueprint_name)
        print(f"✓ {module_name}.{blueprint_name} - OK")
        return True
    except Exception as e:
        print(f"✗ {module_name}.{blueprint_name} - ERROR: {e}")
        traceback.print_exc()
        return False

def main():
    print("Probando importación de blueprints...")
    
    blueprints_to_test = [
        ('src.users.routes', 'users_bp'),
        ('src.institute.routes', 'institute_bp'),
        ('src.academic.routes', 'academic_bp'),
        ('src.classes.routes', 'classes_bp'),
        ('src.study_plans.routes', 'study_plan_bp'),
    ]
    
    success_count = 0
    total_count = len(blueprints_to_test)
    
    for module_name, blueprint_name in blueprints_to_test:
        if test_import(module_name, blueprint_name):
            success_count += 1
    
    print(f"\nResultado: {success_count}/{total_count} blueprints importados exitosamente")
    
    if success_count == total_count:
        print("✓ Todas las importaciones exitosas")
        return 0
    else:
        print("✗ Hay problemas con algunas importaciones")
        return 1

if __name__ == '__main__':
    sys.exit(main