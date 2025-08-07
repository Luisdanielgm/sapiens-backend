#!/usr/bin/env python3
"""
Script para probar las rutas de recursos personales del workspace
"""

import sys
import os
import requests
import json

# Agregar el directorio raíz al path para importar módulos
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

def test_personal_workspace_routes():
    """
    Probar las rutas de recursos personales del workspace
    """
    base_url = "http://localhost:5000/api"
    
    # Datos de prueba
    test_workspace_id = "68901ff7910c7cc367596361"  # Usar el ID del error original
    
    print("🧪 Probando rutas de recursos personales del workspace...")
    print(f"📋 Workspace ID: {test_workspace_id}")
    print()
    
    # 1. Probar OPTIONS para personal-study-plans
    print("1️⃣ Probando OPTIONS /personal-study-plans...")
    try:
        response = requests.options(f"{base_url}/workspaces/{test_workspace_id}/personal-study-plans")
        print(f"   Status: {response.status_code}")
        print(f"   Response: {response.text}")
    except Exception as e:
        print(f"   ❌ Error: {str(e)}")
    print()
    
    # 2. Probar OPTIONS para study-goals
    print("2️⃣ Probando OPTIONS /study-goals...")
    try:
        response = requests.options(f"{base_url}/workspaces/{test_workspace_id}/study-goals")
        print(f"   Status: {response.status_code}")
        print(f"   Response: {response.text}")
    except Exception as e:
        print(f"   ❌ Error: {str(e)}")
    print()
    
    # 3. Probar OPTIONS para personal-resources
    print("3️⃣ Probando OPTIONS /personal-resources...")
    try:
        response = requests.options(f"{base_url}/workspaces/{test_workspace_id}/personal-resources")
        print(f"   Status: {response.status_code}")
        print(f"   Response: {response.text}")
    except Exception as e:
        print(f"   ❌ Error: {str(e)}")
    print()
    
    # 4. Probar GET para personal-study-plans (sin autenticación)
    print("4️⃣ Probando GET /personal-study-plans (sin auth)...")
    try:
        response = requests.get(f"{base_url}/workspaces/{test_workspace_id}/personal-study-plans")
        print(f"   Status: {response.status_code}")
        print(f"   Response: {response.text}")
    except Exception as e:
        print(f"   ❌ Error: {str(e)}")
    print()
    
    # 5. Probar GET para study-goals (sin autenticación)
    print("5️⃣ Probando GET /study-goals (sin auth)...")
    try:
        response = requests.get(f"{base_url}/workspaces/{test_workspace_id}/study-goals")
        print(f"   Status: {response.status_code}")
        print(f"   Response: {response.text}")
    except Exception as e:
        print(f"   ❌ Error: {str(e)}")
    print()
    
    # 6. Probar GET para personal-resources (sin autenticación)
    print("6️⃣ Probando GET /personal-resources (sin auth)...")
    try:
        response = requests.get(f"{base_url}/workspaces/{test_workspace_id}/personal-resources")
        print(f"   Status: {response.status_code}")
        print(f"   Response: {response.text}")
    except Exception as e:
        print(f"   ❌ Error: {str(e)}")
    print()
    
    print("✅ Pruebas completadas")

def test_with_authentication():
    """
    Probar con autenticación (requiere token válido)
    """
    print("\n🔐 Probando con autenticación...")
    print("⚠️  Esta prueba requiere un token válido")
    
    # Aquí podrías agregar lógica para obtener un token válido
    # y probar las rutas con autenticación
    
    print("📝 Para probar con autenticación, necesitas:")
    print("   1. Un usuario válido")
    print("   2. Un workspace válido")
    print("   3. Un token de autenticación")
    print("   4. Ejecutar las pruebas con el token en el header Authorization")

if __name__ == "__main__":
    test_personal_workspace_routes()
    test_with_authentication()
