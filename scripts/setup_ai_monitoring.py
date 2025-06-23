#!/usr/bin/env python3
"""
Script de inicialización para el sistema de monitoreo de IA.

Este script:
1. Inicializa la configuración por defecto del monitoreo
2. Configura los índices específicos para las colecciones de IA
3. Ejecuta pruebas básicas del sistema

Uso:
    python scripts/setup_ai_monitoring.py

Variables de entorno requeridas:
    - MONGO_DB_URI: URI de conexión a MongoDB
    - DB_NAME: Nombre de la base de datos
"""

import sys
import os
import logging
from datetime import datetime

# Agregar el directorio raíz al path
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

# Configurar logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

def main():
    """
    Función principal del script de inicialización.
    """
    try:
        logger.info("🚀 Iniciando configuración del sistema de monitoreo de IA...")
        
        # Importar después de configurar el path
        from src.shared.database import get_db
        from src.ai_monitoring.services import AIMonitoringService
        from src.ai_monitoring.models import AIMonitoringConfig
        
        # Verificar conexión a la base de datos
        logger.info("📊 Verificando conexión a MongoDB...")
        db = get_db()
        logger.info("✅ Conexión a MongoDB establecida")
        
        # Inicializar servicio de monitoreo
        logger.info("⚙️ Inicializando servicio de monitoreo de IA...")
        ai_monitoring_service = AIMonitoringService()
        
        # Configurar configuración por defecto
        logger.info("🔧 Configurando configuración por defecto...")
        success = ai_monitoring_service.initialize_config()
        if success:
            logger.info("✅ Configuración por defecto creada exitosamente")
        else:
            logger.warning("⚠️ No se pudo crear la configuración por defecto")
        
        # Verificar configuración
        config = ai_monitoring_service.get_monitoring_config()
        if config:
            logger.info("📋 Configuración actual:")
            logger.info(f"   - Límite diario: ${config.get('daily_budget', 0)}")
            logger.info(f"   - Límite semanal: ${config.get('weekly_budget', 0)}")
            logger.info(f"   - Límite mensual: ${config.get('monthly_budget', 0)}")
            logger.info(f"   - Límite por usuario/día: ${config.get('user_daily_limit', 0)}")
            logger.info(f"   - Umbrales de alerta: {config.get('alert_thresholds', [])}")
        else:
            logger.error("❌ No se pudo obtener la configuración")
            return False
        
        # Verificar índices específicos del monitoreo
        logger.info("🗂️ Verificando índices de colecciones...")
        collections_to_check = [
            'ai_api_calls',
            'ai_monitoring_config', 
            'ai_monitoring_alerts'
        ]
        
        for collection_name in collections_to_check:
            collection = db[collection_name]
            indexes = list(collection.list_indexes())
            logger.info(f"   - {collection_name}: {len(indexes)} índices configurados")
        
        # Ejecutar una prueba básica
        logger.info("🧪 Ejecutando prueba básica del sistema...")
        
        # Simular registro de una llamada de prueba
        test_call_data = {
            "call_id": f"test_call_{int(datetime.now().timestamp())}",
            "provider": "gemini",
            "model_name": "gemini-1.5-flash-002",
            "prompt_tokens": 100,
            "user_id": "test_user",
            "session_id": "test_session",
            "feature": "system_test",
            "user_type": "admin",
            "endpoint": "test/endpoint"
        }
        
        success, result = ai_monitoring_service.register_call(test_call_data)
        if success:
            logger.info(f"✅ Prueba de registro de llamada exitosa: {result}")
            
            # Actualizar la llamada de prueba
            update_data = {
                "completion_tokens": 50,
                "response_time": 1200,
                "success": True,
                "input_cost": 0.0000075,
                "output_cost": 0.000015,
                "total_cost": 0.0000225,
                "total_tokens": 150
            }
            
            success, result = ai_monitoring_service.update_call(test_call_data["call_id"], update_data)
            if success:
                logger.info("✅ Prueba de actualización de llamada exitosa")
            else:
                logger.warning(f"⚠️ Error en prueba de actualización: {result}")
        else:
            logger.warning(f"⚠️ Error en prueba de registro: {result}")
        
        # Obtener estadísticas de prueba
        logger.info("📊 Obteniendo estadísticas...")
        stats = ai_monitoring_service.get_statistics()
        if stats:
            logger.info(f"   - Total de llamadas: {stats.get('total_calls', 0)}")
            logger.info(f"   - Costo total: ${stats.get('total_cost', 0)}")
            logger.info(f"   - Tasa de éxito: {stats.get('success_rate', 0)*100:.1f}%")
        
        logger.info("🎉 ¡Configuración del sistema de monitoreo de IA completada exitosamente!")
        logger.info("")
        logger.info("📖 Endpoints disponibles:")
        logger.info("   POST   /api/ai-monitoring/calls          - Registrar llamada")
        logger.info("   PUT    /api/ai-monitoring/calls/<id>     - Actualizar llamada")
        logger.info("   GET    /api/ai-monitoring/stats          - Obtener estadísticas")
        logger.info("   GET    /api/ai-monitoring/alerts         - Obtener alertas")
        logger.info("   GET    /api/ai-monitoring/config         - Obtener configuración")
        logger.info("   PUT    /api/ai-monitoring/config         - Actualizar configuración")
        logger.info("   GET    /api/ai-monitoring/calls          - Listar llamadas")
        logger.info("   POST   /api/ai-monitoring/cleanup        - Limpiar datos antiguos")
        logger.info("   GET    /api/ai-monitoring/export         - Exportar datos")
        logger.info("")
        logger.info("🔐 Nota: Todos los endpoints requieren autenticación con rol ADMIN")
        
        return True
        
    except Exception as e:
        logger.error(f"❌ Error durante la configuración: {str(e)}")
        import traceback
        logger.error(traceback.format_exc())
        return False

if __name__ == "__main__":
    success = main()
    sys.exit(0 if success else 1) 