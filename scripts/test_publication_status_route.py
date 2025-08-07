#!/usr/bin/env python3
"""
Script para probar la ruta de publication-status de topics
"""

import requests
import json
import sys
import os

# Agregar el directorio raíz al path para importar módulos
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

def test_publication_status_route():
    """Prueba la ruta de publication-status de topics"""
    base_url = "http://localhost:5000/api"
    test_module_id = "6814591fa98ca4b5ee002f03"  # El mismo ID del error
    
    print("=== Probando ruta de publication-status ===")
    
    # Probar OPTIONS request
    print(f"\n1. Probando OPTIONS request...")
    try:
        response = requests.options(f"{base_url}/study-plan/module/{test_module_id}/topics/publication-status")
        print(f"   Status: {response.status_code}")
        print(f"   Headers: {dict(response.headers)}")
    except Exception as e:
        print(f"   Error en OPTIONS: {e}")
    
    # Probar GET request (sin autenticación)
    print(f"\n2. Probando GET request (sin autenticación)...")
    try:
        response = requests.get(f"{base_url}/study-plan/module/{test_module_id}/topics/publication-status")
        print(f"   Status: {response.status_code}")
        if response.status_code != 404:
            print(f"   Response: {response.text[:200]}...")
        else:
            print(f"   ✅ La ruta ahora existe (401 es esperado sin autenticación)")
    except Exception as e:
        print(f"   Error en GET: {e}")
    
    # Probar con un módulo ID válido (si existe)
    print(f"\n3. Probando con diferentes módulo IDs...")
    test_ids = [
        "6814591fa98ca4b5ee002f03",  # ID del error original
        "507f1f77bcf86cd799439011",  # ID de prueba válido
        "invalid_id"                 # ID inválido
    ]
    
    for test_id in test_ids:
        try:
            response = requests.get(f"{base_url}/study-plan/module/{test_id}/topics/publication-status")
            print(f"   Módulo ID '{test_id}': Status {response.status_code}")
        except Exception as e:
            print(f"   Módulo ID '{test_id}': Error {e}")

if __name__ == "__main__":
    test_publication_status_route()
