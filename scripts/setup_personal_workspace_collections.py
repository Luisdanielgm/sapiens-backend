#!/usr/bin/env python3
"""
Script para configurar las colecciones necesarias para recursos personales del workspace
"""

import sys
import os
from datetime import datetime

# Agregar el directorio raíz al path para importar módulos
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from src.shared.database import get_db
from src.shared.logging import get_logger

def setup_personal_workspace_collections():
    """
    Configurar colecciones para recursos personales del workspace
    """
    logger = get_logger("setup_personal_workspace_collections")
    db = get_db()
    
    try:
        logger.info("Configurando colecciones para recursos personales del workspace...")
        
        # 1. Configurar colección study_goals
        logger.info("Configurando colección study_goals...")
        
        # Crear índices para study_goals
        db.study_goals.create_index([
            ("user_id", 1),
            ("workspace_id", 1)
        ])
        
        db.study_goals.create_index([
            ("user_id", 1),
            ("workspace_id", 1),
            ("status", 1)
        ])
        
        db.study_goals.create_index([
            ("user_id", 1),
            ("priority", 1)
        ])
        
        db.study_goals.create_index([
            ("target_date", 1)
        ])
        
        db.study_goals.create_index([
            ("created_at", -1)
        ])
        
        # 2. Configurar colección personal_resources
        logger.info("Configurando colección personal_resources...")
        
        # Crear índices para personal_resources
        db.personal_resources.create_index([
            ("user_id", 1),
            ("workspace_id", 1)
        ])
        
        db.personal_resources.create_index([
            ("user_id", 1),
            ("workspace_id", 1),
            ("resource_type", 1)
        ])
        
        db.personal_resources.create_index([
            ("user_id", 1),
            ("workspace_id", 1),
            ("status", 1)
        ])
        
        db.personal_resources.create_index([
            ("created_at", -1)
        ])
        
        # 3. Verificar que la colección study_plans tenga los índices necesarios
        logger.info("Verificando índices de study_plans...")
        
        # Crear índices adicionales para study_plans si no existen
        existing_indexes = [index['name'] for index in db.study_plans.list_indexes()]
        
        if "user_id_1_workspace_id_1" not in existing_indexes:
            db.study_plans.create_index([
                ("user_id", 1),
                ("workspace_id", 1)
            ])
            logger.info("Índice user_id_1_workspace_id_1 creado para study_plans")
        
        if "user_id_1_workspace_id_1_status_1" not in existing_indexes:
            db.study_plans.create_index([
                ("user_id", 1),
                ("workspace_id", 1),
                ("status", 1)
            ])
            logger.info("Índice user_id_1_workspace_id_1_status_1 creado para study_plans")
        
        if "created_at_-1" not in existing_indexes:
            db.study_plans.create_index([
                ("created_at", -1)
            ])
            logger.info("Índice created_at_-1 creado para study_plans")
        
        # 4. Crear documentos de ejemplo para testing (opcional)
        if os.getenv('CREATE_SAMPLE_DATA', '0') == '1':
            logger.info("Creando datos de ejemplo...")
            create_sample_data(db)
        
        logger.info("✅ Configuración de colecciones completada exitosamente")
        return True
        
    except Exception as e:
        logger.error(f"❌ Error configurando colecciones: {str(e)}")
        return False

def create_sample_data(db):
    """
    Crear datos de ejemplo para testing
    """
    from bson import ObjectId
    
    # Crear un workspace de ejemplo
    sample_workspace_id = ObjectId()
    sample_user_id = ObjectId()
    
    # Crear objetivos de ejemplo
    sample_goals = [
        {
            "title": "Completar curso de Python básico",
            "description": "Aprender los fundamentos de Python en 4 semanas",
            "user_id": sample_user_id,
            "workspace_id": sample_workspace_id,
            "priority": "high",
            "status": "active",
            "target_date": "2024-12-31",
            "created_at": datetime.utcnow(),
            "updated_at": datetime.utcnow()
        },
        {
            "title": "Practicar algoritmos de ordenamiento",
            "description": "Implementar y entender 5 algoritmos de ordenamiento",
            "user_id": sample_user_id,
            "workspace_id": sample_workspace_id,
            "priority": "medium",
            "status": "active",
            "target_date": "2024-11-30",
            "created_at": datetime.utcnow(),
            "updated_at": datetime.utcnow()
        }
    ]
    
    # Crear recursos de ejemplo
    sample_resources = [
        {
            "title": "Apuntes de Python",
            "description": "Notas personales sobre conceptos de Python",
            "resource_type": "document",
            "user_id": sample_user_id,
            "workspace_id": sample_workspace_id,
            "status": "active",
            "created_at": datetime.utcnow(),
            "updated_at": datetime.utcnow()
        },
        {
            "title": "Video tutorial de algoritmos",
            "description": "Enlace a video explicativo de algoritmos",
            "resource_type": "video",
            "url": "https://example.com/video-algoritmos",
            "user_id": sample_user_id,
            "workspace_id": sample_workspace_id,
            "status": "active",
            "created_at": datetime.utcnow(),
            "updated_at": datetime.utcnow()
        }
    ]
    
    # Insertar datos de ejemplo
    if sample_goals:
        db.study_goals.insert_many(sample_goals)
        print(f"✅ {len(sample_goals)} objetivos de ejemplo creados")
    
    if sample_resources:
        db.personal_resources.insert_many(sample_resources)
        print(f"✅ {len(sample_resources)} recursos de ejemplo creados")

if __name__ == "__main__":
    success = setup_personal_workspace_collections()
    if success:
        print("✅ Configuración completada exitosamente")
        sys.exit(0)
    else:
        print("❌ Error en la configuración")
        sys.exit(1)
