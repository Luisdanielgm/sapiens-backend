from flask import request, jsonify
from datetime import datetime
import logging
from typing import Dict, List

from .services import AIMonitoringService
from src.shared.standardization import APIBlueprint, APIRoute, ErrorCodes
from src.shared.utils import ensure_json_serializable
from src.shared.constants import ROLES
from src.shared.exceptions import AppException
from src.shared.logging import log_error, log_info

ai_monitoring_bp = APIBlueprint('ai_monitoring', __name__)
ai_monitoring_service = AIMonitoringService()

@ai_monitoring_bp.route('/health', methods=['GET'])
@APIRoute.standard(auth_required_flag=True, roles=[ROLES["ADMIN"]])
def health_check():
    """
    Endpoint de verificación del sistema de monitoreo de IA.
    Permite al frontend verificar que todo está funcionando correctamente.
    Solo administradores pueden acceder.
    """
    try:
        # Verificar conexión a la base de datos
        config = ai_monitoring_service.get_monitoring_config()
        database_connected = config is not None
        
        # Verificar configuración cargada
        config_loaded = bool(config and config.get('daily_budget'))
        
        # Contar endpoints disponibles
        endpoints_available = 10  # Total de endpoints implementados
        
        # Verificar estadísticas básicas
        stats = ai_monitoring_service.get_statistics()
        stats_working = isinstance(stats, dict)
        
        # Determinar estado general
        all_healthy = database_connected and config_loaded and stats_working
        
        return APIRoute.success(
            data={
                "status": "healthy" if all_healthy else "degraded",
                "database_connected": database_connected,
                "config_loaded": config_loaded,
                "stats_working": stats_working,
                "endpoints_available": endpoints_available,
                "current_config": {
                    "daily_budget": config.get('daily_budget') if config else None,
                    "weekly_budget": config.get('weekly_budget') if config else None,
                    "monthly_budget": config.get('monthly_budget') if config else None,
                    "alert_thresholds": config.get('alert_thresholds') if config else None
                } if config else None,
                "system_info": {
                    "total_calls": stats.get('total_calls', 0) if stats else 0,
                    "total_cost": stats.get('total_cost', 0) if stats else 0,
                    "success_rate": stats.get('success_rate', 0) if stats else 0
                }
            },
            message="Sistema de monitoreo de IA operativo" if all_healthy else "Sistema funcionando con limitaciones"
        )
        
    except Exception as e:
        log_error(f"Error en health check: {str(e)}", "ai_monitoring.routes")
        return APIRoute.error(
            ErrorCodes.SERVER_ERROR,
            "Error verificando estado del sistema",
            details={"error": str(e)},
            status_code=500
        )

@ai_monitoring_bp.route('/calls', methods=['POST'])
@APIRoute.standard(auth_required_flag=True, required_fields=['call_id', 'provider', 'model_name', 'prompt_tokens'])
def register_call():
    """
    Registra una nueva llamada a API de IA.
    Cualquier usuario autenticado puede registrar sus llamadas.
    
    Body:
        call_id: ID único de la llamada
        provider: Proveedor ('gemini', 'openai', 'claude', etc.)
        model_name: Nombre específico del modelo
        prompt_tokens: Tokens de entrada
        user_id: ID/email del usuario (opcional)
        session_id: ID de sesión (opcional)
        feature: Contexto de uso ('chat', 'content-generation', etc.) (opcional)
        user_type: Tipo de usuario ('student', 'teacher', 'admin') (opcional)
        endpoint: Endpoint usado (opcional)
    """
    try:
        data = request.get_json()
        
        success, result = ai_monitoring_service.register_call(data)
        
        if success:
            return APIRoute.success(
                data={"call_id": result},
                message="Llamada registrada exitosamente",
                status_code=201
            )
        else:
            # Verificar si es un error de límite de presupuesto
            if "excedido" in result.lower():
                return APIRoute.error(
                    "DAILY_BUDGET_EXCEEDED",
                    result,
                    status_code=429
                )
            else:
                return APIRoute.error(
                    ErrorCodes.BAD_REQUEST,
                    result,
                    status_code=400
                )
                
    except Exception as e:
        log_error(f"Error al registrar llamada: {str(e)}", "ai_monitoring.routes")
        return APIRoute.error(
            ErrorCodes.SERVER_ERROR,
            str(e),
            status_code=500
        )

@ai_monitoring_bp.route('/calls/<call_id>', methods=['PUT'])
@APIRoute.standard(auth_required_flag=True)
def update_call(call_id):
    """
    Actualiza una llamada existente con los resultados.
    Cualquier usuario autenticado puede actualizar sus llamadas.
    Los costos se calculan automáticamente en el servidor.
    
    IMPORTANTE: NO enviar campos de costo - se calculan automáticamente.
    
    Args:
        call_id: ID de la llamada
        
    Body:
        completion_tokens: Tokens de salida (opcional)
        response_time: Tiempo de respuesta en ms (opcional)
        success: Si la llamada fue exitosa (opcional)
        total_tokens: Total de tokens (opcional)
        error_message: Mensaje de error si falló (opcional)
        
    NOTA: Los campos input_cost, output_cost, total_cost se calculan automáticamente
    y NO deben ser enviados por el cliente.
    """
    try:
        data = request.get_json() or {}
        
        # Obtener información del usuario autenticado
        user_id = getattr(request, 'user_id', None)
        user_role = getattr(request, 'user_role', None)
        
        # Verificar si es administrador (mantenido para compatibilidad)
        is_admin = user_role == ROLES["ADMIN"]
        
        # Procesar actualización - los costos se calculan automáticamente
        success, result = ai_monitoring_service.update_call_secure(call_id, data, is_admin)
        
        if success:
            return APIRoute.success(
                message=result,
                data={
                    "call_id": call_id,
                    "costs_calculated_automatically": True
                }
            )
        else:
            return APIRoute.error(
                ErrorCodes.BAD_REQUEST,
                result,
                status_code=400
            )
            
    except Exception as e:
        log_error(f"Error al actualizar llamada: {str(e)}", "ai_monitoring.routes")
        return APIRoute.error(
            ErrorCodes.SERVER_ERROR,
            str(e),
            status_code=500
        )

@ai_monitoring_bp.route('/stats', methods=['GET'])
@APIRoute.standard(auth_required_flag=True, roles=[ROLES["ADMIN"]])
def get_statistics():
    """
    Obtiene estadísticas generales del monitoreo.
    Solo administradores pueden ver estadísticas globales del sistema.
    
    Query Parameters (opcionales):
        start_date: Fecha de inicio en formato ISO
        end_date: Fecha de fin en formato ISO
        provider: Proveedor específico
        user_id: Usuario específico
        user_type: Tipo de usuario
        feature: Característica específica
    """
    try:
        filters = {}
        
        # Procesar filtros de fecha
        start_date = request.args.get('start_date')
        if start_date:
            try:
                filters['start_date'] = datetime.fromisoformat(start_date.replace('Z', '+00:00'))
            except ValueError:
                return APIRoute.error(
                    ErrorCodes.INVALID_FORMAT,
                    "Formato de start_date inválido. Use formato ISO",
                    status_code=400
                )
        
        end_date = request.args.get('end_date')
        if end_date:
            try:
                filters['end_date'] = datetime.fromisoformat(end_date.replace('Z', '+00:00'))
            except ValueError:
                return APIRoute.error(
                    ErrorCodes.INVALID_FORMAT,
                    "Formato de end_date inválido. Use formato ISO",
                    status_code=400
                )
        
        # Otros filtros
        for param in ['provider', 'user_id', 'user_type', 'feature']:
            value = request.args.get(param)
            if value:
                filters[param] = value
        
        stats = ai_monitoring_service.get_statistics(filters)
        
        return APIRoute.success(
            data={"stats": stats},
            message="Estadísticas obtenidas exitosamente"
        )
        
    except Exception as e:
        log_error(f"Error al obtener estadísticas: {str(e)}", "ai_monitoring.routes")
        return APIRoute.error(
            ErrorCodes.SERVER_ERROR,
            str(e),
            status_code=500
        )

@ai_monitoring_bp.route('/alerts', methods=['GET'])
@APIRoute.standard(auth_required_flag=True, roles=[ROLES["ADMIN"]])
def get_alerts():
    """
    Obtiene las alertas activas del sistema.
    Solo administradores pueden ver alertas de presupuesto global.
    """
    try:
        alerts = ai_monitoring_service.get_active_alerts()
        
        return APIRoute.success(
            data={"alerts": alerts},
            message=f"Se encontraron {len(alerts)} alertas activas"
        )
        
    except Exception as e:
        log_error(f"Error al obtener alertas: {str(e)}", "ai_monitoring.routes")
        return APIRoute.error(
            ErrorCodes.SERVER_ERROR,
            str(e),
            status_code=500
        )

@ai_monitoring_bp.route('/config', methods=['GET'])
@APIRoute.standard(auth_required_flag=True, roles=[ROLES["ADMIN"]])
def get_config():
    """
    Obtiene la configuración actual del monitoreo.
    Solo administradores pueden ver configuración de límites y presupuestos.
    """
    try:
        config = ai_monitoring_service.get_monitoring_config()
        
        if config:
            return APIRoute.success(
                data={"config": config},
                message="Configuración obtenida exitosamente"
            )
        else:
            return APIRoute.error(
                ErrorCodes.RESOURCE_NOT_FOUND,
                "Configuración de monitoreo no encontrada",
                status_code=404
            )
        
    except Exception as e:
        log_error(f"Error al obtener configuración: {str(e)}", "ai_monitoring.routes")
        return APIRoute.error(
            ErrorCodes.SERVER_ERROR,
            str(e),
            status_code=500
        )

@ai_monitoring_bp.route('/config', methods=['PUT'])
@APIRoute.standard(auth_required_flag=True, roles=[ROLES["ADMIN"]])
def update_config():
    """
    Actualiza la configuración del monitoreo.
    Solo administradores pueden modificar límites de presupuesto del sistema.
    
    Body:
        daily_budget: Límite diario global (opcional)
        weekly_budget: Límite semanal global (opcional)
        monthly_budget: Límite mensual global (opcional)
        provider_limits: Límites por proveedor (opcional)
        user_daily_limit: Límite diario por usuario (opcional)
        user_weekly_limit: Límite semanal por usuario (opcional)
        user_monthly_limit: Límite mensual por usuario (opcional)
        alert_thresholds: Umbrales de alerta (opcional)
        log_level: Nivel de logging (opcional)
        enable_detailed_logging: Habilitar logging detallado (opcional)
    """
    try:
        data = request.get_json() or {}
        
        if not data:
            return APIRoute.error(
                ErrorCodes.MISSING_FIELDS,
                "Se requiere al menos un campo para actualizar",
                status_code=400
            )
        
        success, result = ai_monitoring_service.update_monitoring_config(data)
        
        if success:
            return APIRoute.success(data={"message": result}, message=result)
        else:
            return APIRoute.error(
                ErrorCodes.BAD_REQUEST,
                result,
                status_code=400
            )
            
    except Exception as e:
        log_error(f"Error al actualizar configuración: {str(e)}", "ai_monitoring.routes")
        return APIRoute.error(
            ErrorCodes.SERVER_ERROR,
            str(e),
            status_code=500
        )

@ai_monitoring_bp.route('/calls', methods=['GET'])
@APIRoute.standard(auth_required_flag=True, roles=[ROLES["ADMIN"]])
def get_calls():
    """
    Obtiene lista paginada de llamadas para auditoría.
    Solo administradores pueden ver todas las llamadas del sistema.
    
    Query Parameters:
        page: Número de página (default: 1)
        limit: Límite por página (default: 50, max: 100)
        start_date: Fecha de inicio en formato ISO (opcional)
        end_date: Fecha de fin en formato ISO (opcional)
        provider: Proveedor específico (opcional)
        success: Filtrar por éxito (true/false) (opcional)
    """
    try:
        # Parámetros de paginación
        page = int(request.args.get('page', 1))
        limit = int(request.args.get('limit', 50))
        
        if page < 1:
            return APIRoute.error(
                ErrorCodes.INVALID_DATA,
                "El número de página debe ser mayor a 0",
                status_code=400
            )
        
        # Filtros
        filters = {}
        
        start_date = request.args.get('start_date')
        if start_date:
            try:
                filters['start_date'] = datetime.fromisoformat(start_date.replace('Z', '+00:00'))
            except ValueError:
                return APIRoute.error(
                    ErrorCodes.INVALID_FORMAT,
                    "Formato de start_date inválido. Use formato ISO",
                    status_code=400
                )
        
        end_date = request.args.get('end_date')
        if end_date:
            try:
                filters['end_date'] = datetime.fromisoformat(end_date.replace('Z', '+00:00'))
            except ValueError:
                return APIRoute.error(
                    ErrorCodes.INVALID_FORMAT,
                    "Formato de end_date inválido. Use formato ISO",
                    status_code=400
                )
        
        provider = request.args.get('provider')
        if provider:
            filters['provider'] = provider
        
        success_param = request.args.get('success')
        if success_param is not None:
            filters['success'] = success_param.lower() == 'true'
        
        result = ai_monitoring_service.get_calls_paginated(page, limit, filters)
        
        return APIRoute.success(
            data=result,
            message=f"Se obtuvieron {len(result.get('calls', []))} llamadas"
        )
        
    except ValueError as e:
        return APIRoute.error(
            ErrorCodes.INVALID_DATA,
            "Parámetros de paginación inválidos",
            status_code=400
        )
    except Exception as e:
        log_error(f"Error al obtener llamadas: {str(e)}", "ai_monitoring.routes")
        return APIRoute.error(
            ErrorCodes.SERVER_ERROR,
            str(e),
            status_code=500
        )

@ai_monitoring_bp.route('/cleanup', methods=['POST'])
@APIRoute.standard(auth_required_flag=True, roles=[ROLES["ADMIN"]], required_fields=['days_to_keep'])
def cleanup_data():
    """
    Limpia datos antiguos del sistema.
    Solo administradores pueden ejecutar limpieza de datos históricos.
    
    Body:
        days_to_keep: Días a mantener
        provider: Proveedor específico (opcional)
    """
    try:
        data = request.get_json()
        
        days_to_keep = data.get('days_to_keep')
        provider = data.get('provider')
        
        if not isinstance(days_to_keep, int) or days_to_keep < 1:
            return APIRoute.error(
                ErrorCodes.INVALID_DATA,
                "days_to_keep debe ser un número entero mayor a 0",
                status_code=400
            )
        
        success, deleted_count = ai_monitoring_service.cleanup_old_data(days_to_keep, provider)
        
        if success:
            return APIRoute.success(
                data={"deleted_count": deleted_count},
                message="Limpieza completada exitosamente"
            )
        else:
            return APIRoute.error(
                ErrorCodes.OPERATION_FAILED,
                "Error durante la limpieza de datos",
                status_code=500
            )
            
    except Exception as e:
        log_error(f"Error en limpieza de datos: {str(e)}", "ai_monitoring.routes")
        return APIRoute.error(
            ErrorCodes.SERVER_ERROR,
            str(e),
            status_code=500
        )

@ai_monitoring_bp.route('/export', methods=['GET'])
@APIRoute.standard(auth_required_flag=True, roles=[ROLES["ADMIN"]])
def export_data():
    """
    Exporta datos del monitoreo.
    Solo administradores pueden exportar reportes del sistema.
    
    Query Parameters:
        start_date: Fecha de inicio en formato ISO (opcional)
        end_date: Fecha de fin en formato ISO (opcional)
        format: Formato de exportación ('json' o 'csv') (default: 'json')
    """
    try:
        # Obtener parámetros
        format_type = request.args.get('format', 'json').lower()
        
        if format_type not in ['json', 'csv']:
            return APIRoute.error(
                ErrorCodes.INVALID_DATA,
                "Formato debe ser 'json' o 'csv'",
                status_code=400
            )
        
        # Construir filtros para obtener datos
        filters = {}
        
        start_date = request.args.get('start_date')
        if start_date:
            try:
                filters['start_date'] = datetime.fromisoformat(start_date.replace('Z', '+00:00'))
            except ValueError:
                return APIRoute.error(
                    ErrorCodes.INVALID_FORMAT,
                    "Formato de start_date inválido. Use formato ISO",
                    status_code=400
                )
        
        end_date = request.args.get('end_date')
        if end_date:
            try:
                filters['end_date'] = datetime.fromisoformat(end_date.replace('Z', '+00:00'))
            except ValueError:
                return APIRoute.error(
                    ErrorCodes.INVALID_FORMAT,
                    "Formato de end_date inválido. Use formato ISO",
                    status_code=400
                )
        
        # Por ahora, retornar un placeholder de exportación
        return APIRoute.success(
            data={
                "download_url": "#",  # En el futuro, generar URL real
                "format": format_type,
                "filename": f"ai-monitoring-export-{datetime.now().strftime('%Y%m%d')}.{format_type}",
                "generated_at": datetime.now().isoformat()
            },
            message="Solicitud de exportación procesada. El archivo estará disponible en breve."
        )
        
    except Exception as e:
        log_error(f"Error en exportación: {str(e)}", "ai_monitoring.routes")
        return APIRoute.error(
            ErrorCodes.SERVER_ERROR,
            str(e),
            status_code=500
        )

@ai_monitoring_bp.route('/models', methods=['GET'])
@APIRoute.standard(auth_required_flag=True, roles=[ROLES["ADMIN"]])
def list_ai_models():
    """
    Lista los modelos de IA desde la base de datos. Si la colección está vacía, devuelve los modelos legacy como fallback.
    """
    try:
        active_only = request.args.get('active_only', 'false').lower() == 'true'
        models = ai_monitoring_service.model_service.get_all_models(active_only=active_only)

        if not models:
            legacy_prices = ai_monitoring_service._get_legacy_model_prices()
            for provider, provider_models in legacy_prices.items():
                for model_key, pricing in provider_models.items():
                    models.append({
                        "id": model_key,
                        "name": model_key,
                        "provider": provider,
                        "api_model_name": model_key,
                        "input_price": pricing.get("input", 0.0),
                        "output_price": pricing.get("output", 0.0),
                        "is_active": True,
                        "capabilities": ["chat"],
                        "source": "legacy"
                    })

        return APIRoute.success(
            data={"models": models},
            message=f"Se encontraron {len(models)} modelos"
        )
        
    except Exception as e:
        log_error(f"Error al obtener modelos: {str(e)}", "ai_monitoring.routes")
        return APIRoute.error(
            ErrorCodes.SERVER_ERROR,
            str(e),
            status_code=500
        )

@ai_monitoring_bp.route('/models', methods=['POST'])
@APIRoute.standard(auth_required_flag=True, roles=[ROLES["ADMIN"]], required_fields=['id', 'name', 'provider', 'api_model_name', 'input_price', 'output_price'])
def create_ai_model():
    """
    Crea un nuevo registro de modelo de IA en la colección ai_models.
    """
    try:
        data = request.get_json() or {}
        success, result = ai_monitoring_service.model_service.create_model(data)

        if success:
            return APIRoute.success(
                data={"model": result},
                message="Modelo creado exitosamente",
                status_code=201
            )
        return APIRoute.error(
            ErrorCodes.BAD_REQUEST,
            result,
            status_code=400
        )
            
    except Exception as e:
        log_error(f"Error al crear modelo: {str(e)}", "ai_monitoring.routes")
        return APIRoute.error(
            ErrorCodes.SERVER_ERROR,
            str(e),
            status_code=500
        )

@ai_monitoring_bp.route('/models/<model_id>', methods=['PUT'])
@APIRoute.standard(auth_required_flag=True, roles=[ROLES["ADMIN"]])
def update_ai_model(model_id):
    """
    Actualiza un modelo existente.
    """
    try:
        data = request.get_json() or {}

        if not data:
            return APIRoute.error(
                ErrorCodes.MISSING_FIELDS,
                "Se requiere al menos un campo para actualizar",
                status_code=400
            )

        success, result = ai_monitoring_service.model_service.update_model(model_id, data)

        if success:
            return APIRoute.success(
                data={"model": result},
                message="Modelo actualizado exitosamente"
            )
        return APIRoute.error(
            ErrorCodes.RESOURCE_NOT_FOUND if result == "Modelo no encontrado" else ErrorCodes.BAD_REQUEST,
            result,
            status_code=404 if result == "Modelo no encontrado" else 400
        )
    except Exception as e:
        log_error(f"Error al actualizar modelo: {str(e)}", "ai_monitoring.routes")
        return APIRoute.error(
            ErrorCodes.SERVER_ERROR,
            str(e),
            status_code=500
        )

@ai_monitoring_bp.route('/models/<model_id>', methods=['DELETE'])
@APIRoute.standard(auth_required_flag=True, roles=[ROLES["ADMIN"]])
def delete_ai_model(model_id):
    """
    Elimina o archiva un modelo. Usa borrado suave por defecto.
    """
    try:
        soft_delete = request.args.get('soft', 'true').lower() == 'true'

        if soft_delete:
            success, result = ai_monitoring_service.model_service.update_model(model_id, {"is_active": False})
            message = "Modelo archivado"
        else:
            success, result = ai_monitoring_service.model_service.delete_model(model_id)
            message = "Modelo eliminado"

        if success:
            return APIRoute.success(
                data={"model_id": model_id},
                message=message
            )
        return APIRoute.error(
            ErrorCodes.RESOURCE_NOT_FOUND if result == "Modelo no encontrado" else ErrorCodes.BAD_REQUEST,
            result,
            status_code=404 if result == "Modelo no encontrado" else 400
        )
    except Exception as e:
        log_error(f"Error al eliminar modelo: {str(e)}", "ai_monitoring.routes")
        return APIRoute.error(
            ErrorCodes.SERVER_ERROR,
            str(e),
            status_code=500
        )

@ai_monitoring_bp.route('/models/check', methods=['POST'])
@APIRoute.standard(auth_required_flag=True, required_fields=['provider', 'model_name'])
def check_model_support():
    """
    Verifica si un modelo específico está soportado.
    Cualquier usuario autenticado puede verificar soporte de modelos.
    
    Body:
        provider: Proveedor del modelo
        model_name: Nombre del modelo
    """
    try:
        data = request.get_json()
        
        provider = data.get('provider')
        model_name = data.get('model_name')

        db_pricing = ai_monitoring_service.model_service.get_model_pricing(provider, model_name)
        legacy_pricing = ai_monitoring_service._get_legacy_model_prices().get(provider, {}).get(model_name)

        pricing = db_pricing or legacy_pricing
        is_supported = pricing is not None
        
        response_data = {
            "provider": provider,
            "model_name": model_name,
            "is_supported": is_supported
        }
        
        if is_supported:
            response_data.update({
                "pricing": {
                    "input_price_per_1k": pricing.get("input"),
                    "output_price_per_1k": pricing.get("output")
                },
                "source": "db" if db_pricing else "legacy"
            })
            message = f"Modelo {provider}/{model_name} está soportado"
        else:
            response_data.update({
                "pricing": {
                    "input_price_per_1k": 0.001,
                    "output_price_per_1k": 0.002
                },
                "source": "default"
            })
            message = f"Modelo {provider}/{model_name} NO está soportado, se usarán precios por defecto"
        
        return APIRoute.success(
            data=response_data,
            message=message
        )
        
    except Exception as e:
        log_error(f"Error al verificar modelo: {str(e)}", "ai_monitoring.routes")
        return APIRoute.error(
            ErrorCodes.SERVER_ERROR,
            str(e),
            status_code=500
        ) 
