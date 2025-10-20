#!/usr/bin/env python3
"""
Script de diagnóstico para identificar problemas de inicialización
"""
import sys
import os

print("=== DIAGNÓSTICO DE INICIALIZACIÓN ===")

# 1. Probar importaciones básicas
print("\n1. PROBANDO IMPORTACIONES BÁSICAS:")
try:
    import flask
    print("✓ Flask importado correctamente")
    
    from dotenv import load_dotenv
    load_dotenv()
    print("✓ dotenv cargado")
    
    mongo_uri = os.getenv('MONGO_DB_URI')
    print(f"✓ MONGO_DB_URI configurado: {bool(mongo_uri)}")
    
    from config import active_config
    print("✓ Config importado correctamente")
    
except Exception as e:
    print(f"✗ Error en importaciones básicas: {e}")
    sys.exit(1)

# 2. Probar conexión a MongoDB
print("\n2. PROBANDO CONEXIÓN A MONGODB:")
try:
    from src.shared.database import get_db
    print("✓ Database module importado")
    
    # Intentar conectar con timeout
    db = get_db()
    print("✓ Conexión a BD obtenida")
    
    # Probar ping
    result = db.command('ping')
    print(f"✓ Ping a MongoDB exitoso: {result}")
    
except Exception as e:
    print(f"⚠ Error en conexión a BD (no crítico): {e}")

# 3. Probar importación de blueprints críticos
print("\n3. PROBANDO IMPORTACIÓN DE BLUEPRINTS:")
blueprints = [
    ('users', 'src.users.routes', 'users_bp'),
    ('institute', 'src.institute.routes', 'institute_bp'),
    ('academic', 'src.academic.routes', 'academic_bp'),
]

for name, module_path, blueprint_name in blueprints:
    try:
        module = __import__(module_path, fromlist=[blueprint_name])
        blueprint = getattr(module, blueprint_name)
        print(f"✓ {name} blueprint importado correctamente")
    except Exception as e:
        print(f"✗ Error importando {name} blueprint: {e}")

# 4. Probar creación de aplicación Flask
print("\n4. PROBANDO CREACIÓN DE APLICACIÓN FLASK:")
try:
    app = flask.Flask(__name__)
    app.config.from_object(active_config)
    print("✓ Aplicación Flask creada y configurada")
    
    @app.route('/test')
    def test():
        return {"status": "ok"}
    
    print("✓ Endpoint de prueba creado")
    
except Exception as e:
    print(f"✗ Error creando aplicación Flask: {e}")
    sys.exit(1)

print("\n=== DIAGNÓSTICO COMPLETADO ===")
print("Si llegaste hasta aquí, la aplicación debería poder iniciarse.")