#!/usr/bin/env python3
"""
Test rápido para identificar el problema específico
"""
import sys
import os

print("=== TEST RÁPIDO DE INICIALIZACIÓN ===")

# 1. Verificar variables de entorno
print("\n1. VERIFICANDO VARIABLES DE ENTORNO:")
try:
    from dotenv import load_dotenv
    load_dotenv()
    
    mongo_uri = os.getenv('MONGO_DB_URI')
    db_name = os.getenv('DB_NAME')
    flask_env = os.getenv('FLASK_ENV')
    port = os.getenv('PORT')
    
    print(f"✓ MONGO_DB_URI: {mongo_uri[:50] if mongo_uri else 'None'}...")
    print(f"✓ DB_NAME: {db_name}")
    print(f"✓ FLASK_ENV: {flask_env}")
    print(f"✓ PORT: {port}")
    
except Exception as e:
    print(f"✗ Error cargando variables: {e}")
    sys.exit(1)

# 2. Probar importación de Flask
print("\n2. PROBANDO FLASK:")
try:
    from flask import Flask
    print("✓ Flask importado")
    
    from config import active_config
    print("✓ Config importado")
    
    app = Flask(__name__)
    app.config.from_object(active_config)
    print("✓ App Flask creada")
    
except Exception as e:
    print(f"✗ Error con Flask: {e}")
    sys.exit(1)

# 3. Probar conexión MongoDB (sin bloquear)
print("\n3. PROBANDO MONGODB:")
try:
    from pymongo import MongoClient
    from pymongo.errors import ServerSelectionTimeoutError
    
    # Crear cliente con timeout corto
    client = MongoClient(
        mongo_uri,
        serverSelectionTimeoutMS=3000,  # 3 segundos
        connectTimeoutMS=3000
    )
    
    # Probar conexión
    client.admin.command('ping')
    print("✓ MongoDB conectado exitosamente")
    
except ServerSelectionTimeoutError:
    print("⚠ MongoDB no disponible (timeout) - continuando sin BD")
except Exception as e:
    print(f"⚠ Error MongoDB: {e} - continuando sin BD")

# 4. Probar importación de un blueprint simple
print("\n4. PROBANDO BLUEPRINT SIMPLE:")
try:
    from src.users.routes import users_bp
    print("✓ Users blueprint importado")
except Exception as e:
    print(f"✗ Error importando users blueprint: {e}")

print("\n=== TEST COMPLETADO ===")
print("Revisando main.py para identificar el problema...")

# 5. Intentar ejecutar main.py paso a paso
print("\n5. PROBANDO MAIN.PY:")
try:
    # Importar main sin ejecutar
    import main
    print("✓ main.py importado sin errores")
except Exception as e:
    print(f"✗ Error en main.py: {e}")
    import traceback
    traceback.print_exc()