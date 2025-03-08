from flask import request, jsonify
from bson.objectid import ObjectId
from datetime import datetime

from .services import (
    StudentAnalyticsService, 
    ClassAnalyticsService, 
    EvaluationAnalyticsService, 
    InstituteAnalyticsService, 
    StudentSubjectsAnalyticsService, 
    InstituteDashboardService
)
from src.shared.standardization import APIBlueprint, APIRoute, ErrorCodes
from src.shared.decorators import auth_required, role_required, validate_json
from src.shared.constants import ROLES
from src.shared.utils import ensure_json_serializable

analytics_bp = APIBlueprint('analytics', __name__)

student_analytics_service = StudentAnalyticsService()
class_analytics_service = ClassAnalyticsService()
evaluation_analytics_service = EvaluationAnalyticsService()
institute_analytics_service = InstituteAnalyticsService()
student_subjects_analytics_service = StudentSubjectsAnalyticsService()
institute_dashboard_service = InstituteDashboardService()

# Rutas para Análisis de Estudiantes
@analytics_bp.route('/student/<student_id>/performance', methods=['GET'])
@APIRoute.standard(
    auth_required_flag=True,
    roles=[ROLES["TEACHER"], ROLES["INSTITUTE_ADMIN"]]
)
def get_student_performance(student_id):
    """Obtiene el rendimiento de un estudiante en una clase específica"""
    class_id = request.args.get('class_id')
    period_id = request.args.get('period_id')
    
    if not all([class_id, period_id]):
        return APIRoute.error(
            ErrorCodes.VALIDATION_ERROR,
            "Se requieren class_id y period_id como parámetros",
            status_code=400
        )

    performance = student_analytics_service.calculate_student_performance(
        student_id, class_id, period_id
    )
    
    if performance:
        return APIRoute.success(data={"performance": performance})
    return APIRoute.error(
        ErrorCodes.NOT_FOUND, 
        "No se pudo obtener el rendimiento",
        status_code=404
    )

# Rutas para Análisis de Clases
@analytics_bp.route('/class/<class_id>/statistics', methods=['GET'])
@APIRoute.standard(
    auth_required_flag=True,
    roles=[ROLES["TEACHER"], ROLES["INSTITUTE_ADMIN"]]
)
def get_class_statistics(class_id):
    """Obtiene estadísticas generales de una clase"""
    period_id = request.args.get('period_id')
    if not period_id:
        return APIRoute.error(
            ErrorCodes.VALIDATION_ERROR,
            "Se requiere period_id como parámetro",
            status_code=400
        )
    
    statistics = class_analytics_service.get_class_analytics(class_id)
    
    if statistics:
        return APIRoute.success(data={"statistics": statistics})
    return APIRoute.error(
        ErrorCodes.NOT_FOUND,
        "No se encontraron estadísticas para esta clase",
        status_code=404
    )

@analytics_bp.route('/evaluation/<evaluation_id>/analytics', methods=['GET'])
@APIRoute.standard(
    auth_required_flag=True,
    roles=[ROLES["TEACHER"]]
)
def get_evaluation_analytics(evaluation_id):
    """Obtiene análisis detallado de una evaluación específica"""
    analytics = evaluation_analytics_service.analyze_evaluation(evaluation_id)
    
    if analytics:
        return APIRoute.success(data={"analytics": analytics})
    return APIRoute.error(
        ErrorCodes.NOT_FOUND,
        "No se encontraron datos de análisis para esta evaluación",
        status_code=404
    )

@analytics_bp.route('/institute/<institute_id>/statistics', methods=['GET'])
@APIRoute.standard(
    auth_required_flag=True,
    roles=[ROLES["ADMIN"], ROLES["INSTITUTE_ADMIN"]]
)
def get_institute_statistics(institute_id):
    """Obtiene estadísticas generales de un instituto"""
    statistics = institute_analytics_service.get_institute_statistics(institute_id)
    
    if statistics:
        return APIRoute.success(data={"statistics": statistics})
    return APIRoute.error(
        ErrorCodes.NOT_FOUND,
        "No se encontraron estadísticas para este instituto",
        status_code=404
    )

@analytics_bp.route('/institute/<institute_id>/statistics/history', methods=['GET'])
@APIRoute.standard(
    auth_required_flag=True,
    roles=[ROLES["ADMIN"], ROLES["INSTITUTE_ADMIN"]]
)
def get_institute_statistics_history(institute_id):
    """Obtiene histórico de estadísticas de un instituto"""
    days = int(request.args.get('days', 30))
    statistics = institute_analytics_service.get_institute_statistics_history(institute_id, days)
    
    return APIRoute.success(data={"history": statistics})

@analytics_bp.route('/institute/statistics/compare', methods=['GET'])
@APIRoute.standard(
    auth_required_flag=True,
    roles=[ROLES["ADMIN"]]
)
def compare_institute_statistics():
    """Compara estadísticas entre múltiples institutos"""
    institute_ids = request.args.getlist('institute_ids')
    
    if not institute_ids:
        return APIRoute.error(
            ErrorCodes.VALIDATION_ERROR,
            "Se requiere al menos un institute_id para comparar",
            status_code=400
        )
    
    statistics = institute_analytics_service.get_comparative_statistics(institute_ids)
    
    return APIRoute.success(data={"comparison": statistics})

@analytics_bp.route('/class/<class_id>/comprehensive', methods=['GET'])
@APIRoute.standard(
    auth_required_flag=True,
    roles=[ROLES["TEACHER"], ROLES["INSTITUTE_ADMIN"]]
)
def get_comprehensive_report(class_id):
    """Obtiene un reporte completo y detallado de una clase"""
    # Obtener estadísticas básicas de la clase
    class_statistics = class_analytics_service.get_class_analytics(class_id)
    if not class_statistics:
        return APIRoute.error(
            ErrorCodes.NOT_FOUND,
            "No se encontraron estadísticas para esta clase",
            status_code=404
        )
    
    # Aquí podrías agregar lógica para obtener más información detallada
    # desde diferentes servicios y combinarla en un informe comprensivo
    
    report = {
        "class_statistics": class_statistics,
        "report_date": datetime.now().isoformat(),
        # Otros componentes del reporte comprensivo
    }
    
    return APIRoute.success(data={"report": report})

@analytics_bp.route('/institute/<institute_id>/dashboard', methods=['GET'])
@APIRoute.standard(
    auth_required_flag=True,
    roles=[ROLES["INSTITUTE_ADMIN"]]
)
def get_institute_dashboard(institute_id):
    """Obtiene el dashboard completo para un instituto educativo"""
    dashboard = institute_dashboard_service.generate_institute_dashboard(institute_id)
    
    if dashboard:
        return APIRoute.success(data={"dashboard": dashboard})
    return APIRoute.error(
        ErrorCodes.NOT_FOUND,
        "No se encontraron datos para generar el dashboard",
        status_code=404
    )

@analytics_bp.route('/teacher/dashboard', methods=['GET'])
@APIRoute.standard(auth_required_flag=True, roles=[ROLES["TEACHER"]])
def get_teacher_dashboard():
    """Obtiene el dashboard para un profesor con métricas relevantes"""
    try:
        # En una implementación real, este id se obtendría del token JWT
        teacher_id = request.args.get('teacher_id')
        if not teacher_id:
            return APIRoute.error(
                ErrorCodes.VALIDATION_ERROR,
                "Se requiere el ID del profesor",
                status_code=400
            )
            
        # Obtener clases del profesor
        classes = list(ClassAnalyticsService().db.classes.find({
            "teacher_id": ObjectId(teacher_id)
        }))
        
        if not classes:
            return APIRoute.success(
                data={"dashboard": {"classes": [], "overall_metrics": {}}},
                message="No hay clases asignadas a este profesor"
            )
            
        # Métricas por clase
        class_metrics = []
        for cls in classes:
            stats = class_analytics_service.get_class_analytics(str(cls["_id"]))
            if stats:
                class_metrics.append({
                    "class_id": str(cls["_id"]),
                    "class_name": cls.get("name", "Sin nombre"),
                    "metrics": stats
                })
                
        # Métricas generales
        overall_metrics = {
            "total_classes": len(classes),
            "total_students": sum(cls.get("student_count", 0) for cls in class_metrics),
            "average_attendance": sum(m.get("attendance_rate", 0) for m in class_metrics) / len(class_metrics) if class_metrics else 0,
            "average_evaluation_score": sum(m.get("avg_score", 0) for m in class_metrics) / len(class_metrics) if class_metrics else 0
        }
            
        dashboard = {
            "teacher_id": teacher_id,
            "classes": class_metrics,
            "overall_metrics": overall_metrics
        }
            
        return APIRoute.success(data={"dashboard": dashboard})
    except Exception as e:
        return APIRoute.error(
            ErrorCodes.SERVER_ERROR,
            str(e),
            status_code=500
        )

@analytics_bp.route('/student/<student_id>/dashboard', methods=['GET'])
@APIRoute.standard(auth_required_flag=True)
def get_student_dashboard(student_id):
    """Obtiene el dashboard para un estudiante con su progreso académico"""
    try:
        # Obtener clases del estudiante
        memberships = list(ClassAnalyticsService().db.classroom_members.find({
            "user_id": ObjectId(student_id),
            "role": "student"
        }))
        
        if not memberships:
            return APIRoute.success(
                data={"dashboard": {"classes": [], "overall_metrics": {}}},
                message="No hay clases asignadas a este estudiante"
            )
            
        class_ids = [str(m["class_id"]) for m in memberships]
        
        # Obtener rendimiento por clase
        class_performances = []
        period_id = request.args.get('period_id')  # Opcional
        
        for class_id in class_ids:
            cls_info = ClassAnalyticsService().db.classes.find_one({"_id": ObjectId(class_id)})
            if cls_info and period_id:
                performance = student_analytics_service.calculate_student_performance(
                    student_id, class_id, period_id
                )
                if performance:
                    class_performances.append({
                        "class_id": class_id,
                        "class_name": cls_info.get("name", "Sin nombre"),
                        "performance": performance
                    })
            
        # Obtener análisis por materias
        subjects_analytics = student_subjects_analytics_service.get_student_subjects_analytics(
            student_id, period_id
        )
            
        dashboard = {
            "student_id": student_id,
            "classes": class_performances,
            "subjects": subjects_analytics
        }
            
        return APIRoute.success(data={"dashboard": dashboard})
    except Exception as e:
        return APIRoute.error(
            ErrorCodes.SERVER_ERROR,
            str(e),
            status_code=500
        )

@analytics_bp.route('/class/<class_id>/dashboard', methods=['GET'])
@APIRoute.standard(
    auth_required_flag=True,
    roles=[ROLES["TEACHER"], ROLES["INSTITUTE_ADMIN"]]
)
def get_class_dashboard(class_id):
    """Obtiene un dashboard completo para una clase específica"""
    try:
        # Obtener estadísticas generales de la clase
        statistics = class_analytics_service.get_class_analytics(class_id)
        if not statistics:
            return APIRoute.error(
                ErrorCodes.NOT_FOUND,
                "No se encontraron estadísticas para esta clase",
                status_code=404
            )
            
        # Obtener información adicional para el dashboard
        cls_info = ClassAnalyticsService().db.classes.find_one({"_id": ObjectId(class_id)})
        
        if not cls_info:
            return APIRoute.error(
                ErrorCodes.NOT_FOUND,
                "Clase no encontrada",
                status_code=404
            )
        
        dashboard = {
            "class_id": class_id,
            "class_name": cls_info.get("name", "Sin nombre"),
            "subject": cls_info.get("subject", "Sin asignatura"),
            "statistics": statistics,
            "last_updated": datetime.now().isoformat()
        }
        
        return APIRoute.success(data={"dashboard": dashboard})
    except Exception as e:
        return APIRoute.error(
            ErrorCodes.SERVER_ERROR,
            str(e),
            status_code=500
        )

@analytics_bp.route('/student/<student_id>/subjects', methods=['GET'])
@APIRoute.standard(auth_required_flag=True)
def get_student_subjects_dashboard(student_id):
    """Obtiene análisis de rendimiento del estudiante por materias/asignaturas"""
    try:
        period_id = request.args.get('period_id')
        
        subjects_analytics = student_subjects_analytics_service.get_student_subjects_analytics(
            student_id, period_id
        )
        
        if not subjects_analytics:
            return APIRoute.success(
                data={"subjects": []},
                message="No hay datos de materias para este estudiante"
            )
            
        # Añadir métricas generales al dashboard
        avg_score = 0
        num_subjects = len(subjects_analytics)
        
        if num_subjects > 0:
            avg_score = sum(subject.get("overall_grade", 0) for subject in subjects_analytics) / num_subjects
            
        dashboard = {
            "student_id": student_id,
            "subjects": subjects_analytics,
            "overall_metrics": {
                "num_subjects": num_subjects,
                "average_score": round(avg_score, 2),
                "passing_subjects": sum(1 for s in subjects_analytics if s.get("overall_grade", 0) >= 60)
            }
        }
        
        return APIRoute.success(data={"dashboard": dashboard})
    except Exception as e:
        return APIRoute.error(
            ErrorCodes.SERVER_ERROR,
            str(e),
            status_code=500
        )

@analytics_bp.route('/institute/<institute_id>/complete-dashboard', methods=['GET'])
@APIRoute.standard(
    auth_required_flag=True,
    roles=[ROLES["INSTITUTE_ADMIN"]]
)
def get_institute_complete_dashboard(institute_id):
    """Obtiene un dashboard completo y detallado del instituto"""
    try:
        # Obtener dashboard general
        dashboard = institute_dashboard_service.generate_institute_dashboard(institute_id)
        if not dashboard:
            return APIRoute.error(
                ErrorCodes.NOT_FOUND,
                "No se encontraron datos para generar el dashboard",
                status_code=404
            )
            
        # Obtener estadísticas detalladas
        statistics = institute_analytics_service.get_institute_statistics(institute_id)
        
        # Obtener historial (últimos 30 días)
        history = institute_analytics_service.get_institute_statistics_history(institute_id, 30)
        
        complete_dashboard = {
            "dashboard": dashboard,
            "statistics": statistics,
            "history": history,
            "generated_at": datetime.now().isoformat()
        }
        
        return APIRoute.success(data={"complete_dashboard": complete_dashboard})
    except Exception as e:
        return APIRoute.error(
            ErrorCodes.SERVER_ERROR,
            str(e),
            status_code=500
        ) 