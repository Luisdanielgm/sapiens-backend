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

@ai_monitoring_bp.route('/calls', methods=['POST'])
@APIRoute.standard(auth_required_flag=True, roles=[ROLES["ADMIN"]], required_fields=['call_id', 'provider', 'model_name', 'prompt_tokens'])
def register_call():
    """
    Registra una nueva llamada a API de IA.
    Solo administradores pueden registrar llamadas.
    
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
@APIRoute.standard(auth_required_flag=True, roles=[ROLES["ADMIN"]])
def update_call(call_id):
    """
    Actualiza una llamada existente con los resultados.
    Solo administradores pueden actualizar llamadas.
    
    Args:
        call_id: ID de la llamada
        
    Body:
        completion_tokens: Tokens de salida (opcional)
        response_time: Tiempo de respuesta en ms (opcional)
        success: Si la llamada fue exitosa (opcional)
        input_cost: Costo por tokens de entrada (opcional)
        output_cost: Costo por tokens de salida (opcional)
        total_cost: Costo total (opcional)
        total_tokens: Total de tokens (opcional)
        error_message: Mensaje de error si falló (opcional)
    """
    try:
        data = request.get_json() or {}
        
        success, result = ai_monitoring_service.update_call(call_id, data)
        
        if success:
            return APIRoute.success(message=result)
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
    Solo administradores pueden acceder a las estadísticas.
    
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
    Obtiene las alertas activas.
    Solo administradores pueden ver las alertas.
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
    Solo administradores pueden ver la configuración.
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
    Solo administradores pueden actualizar la configuración.
    
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
            return APIRoute.success(message=result)
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
    Solo administradores pueden ver las llamadas.
    
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
    Solo administradores pueden realizar limpieza.
    
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
    Solo administradores pueden exportar datos.
    
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
        
        # Por ahora, simplemente retornamos la información para generar el archivo
        # En una implementación completa, se podría generar el archivo y subirlo a un servicio de almacenamiento
        filename = f"ai-monitoring-export-{datetime.now().strftime('%Y%m%d')}.{format_type}"
        
        return APIRoute.success(
            data={
                "download_url": f"#",  # En implementación real, aquí iría la URL del archivo generado
                "format": format_type,
                "filename": filename,
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