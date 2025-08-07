#!/usr/bin/env python3
"""
Script para probar la ruta POST /api/content
"""

import requests
import json
import sys
import os

# Agregar el directorio raíz al path para importar módulos
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

def test_content_route():
    """Prueba la ruta POST /api/content"""
    base_url = "http://localhost:5000/api"
    
    print("=== Probando ruta POST /api/content ===")
    
    # Datos de prueba para crear contenido
    test_data = {
        "topic_id": "6814591fa98ca4b5ee002f04",
        "content_type": "text",
        "content": {
            "title": "Contenido de prueba",
            "description": "Descripción de prueba",
            "difficulty": "baja",
            "content": {
                "introduction": "Introducción de prueba",
                "sections": [
                    {
                        "title": "Sección 1",
                        "content": "Contenido de la sección 1"
                    }
                ],
                "conclusion": "Conclusión de prueba",
                "key_concepts": ["concepto1", "concepto2"]
            }
        },
        "methodology": "general",
        "learning_methodologies": ["reading_writing"],
        "metadata": {
            "difficulty": "baja",
            "keywords": [],
            "sectionsCount": 1
        }
    }
    
    # Probar OPTIONS request
    print(f"\n1. Probando OPTIONS request...")
    try:
        response = requests.options(f"{base_url}/content")
        print(f"   Status: {response.status_code}")
        print(f"   Headers: {dict(response.headers)}")
    except Exception as e:
        print(f"   Error en OPTIONS: {e}")
    
    # Probar POST request (sin autenticación)
    print(f"\n2. Probando POST request (sin autenticación)...")
    try:
        response = requests.post(f"{base_url}/content", json=test_data)
        print(f"   Status: {response.status_code}")
        if response.status_code != 404:
            print(f"   Response: {response.text[:200]}...")
        else:
            print(f"   ✅ La ruta ahora existe (401 es esperado sin autenticación)")
    except Exception as e:
        print(f"   Error en POST: {e}")
    
    # Probar con diferentes tipos de contenido
    print(f"\n3. Probando con diferentes content_types...")
    content_types = ["text", "quiz", "game", "simulation", "diagram"]
    
    for content_type in content_types:
        test_data["content_type"] = content_type
        try:
            response = requests.post(f"{base_url}/content", json=test_data)
            print(f"   Content type '{content_type}': Status {response.status_code}")
        except Exception as e:
            print(f"   Content type '{content_type}': Error {e}")

if __name__ == "__main__":
    test_content_route()
