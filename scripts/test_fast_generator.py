#!/usr/bin/env python3
"""
Script para verificar que FastVirtualModuleGenerator tiene el método generate_single_module
"""

import sys
import os
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from src.virtual.services import FastVirtualModuleGenerator

def test_fast_generator():
    print("🧪 Verificando FastVirtualModuleGenerator...")
    
    # Crear instancia
    generator = FastVirtualModuleGenerator()
    
    # Verificar que tiene el método generate_single_module
    if hasattr(generator, 'generate_single_module'):
        print("✅ Método 'generate_single_module' encontrado")
        print(f"✅ Tipo: {type(generator.generate_single_module)}")
    else:
        print("❌ Método 'generate_single_module' NO encontrado")
        print(f"❌ Métodos disponibles: {[m for m in dir(generator) if not m.startswith('_')]}")
        return False
    
    # Verificar herencia
    print(f"✅ Clase base: {generator.__class__.__bases__}")
    
    # Verificar otros métodos importantes
    important_methods = ['_generate_virtual_topics_fast', 'synchronize_module_content']
    for method in important_methods:
        if hasattr(generator, method):
            print(f"✅ Método '{method}' encontrado")
        else:
            print(f"⚠️ Método '{method}' no encontrado")
    
    print("\n🎉 FastVirtualModuleGenerator verificado correctamente!")
    return True

if __name__ == "__main__":
    test_fast_generator()