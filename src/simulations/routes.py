from flask import request

from src.shared.standardization import APIBlueprint, APIRoute, ErrorCodes
from src.shared.constants import ROLES
from .services import SimulationService, VirtualSimulationService, SimulationResultService

# Crear blueprint
simulations_bp = APIBlueprint('simulations', __name__, url_prefix='/api/simulations')

# Inicializar servicios
simulation_service = SimulationService()
virtual_simulation_service = VirtualSimulationService()
simulation_result_service = SimulationResultService()

# Rutas para Simulaciones
@simulations_bp.route('', methods=['POST'])
@APIRoute.standard(
    auth_required_flag=True,
    roles=[ROLES["TEACHER"]], 
    required_fields=['topic_id', 'title', 'description', 'simulation_type', 'code', 'parameters']
)
def create_simulation():
    """Crea una nueva simulación educativa"""
    try:
        data = request.get_json()
        data['creator_id'] = request.user_id  # Añadir ID del creador
        
        success, result = simulation_service.create_simulation(data)
        
        if success:
            return APIRoute.success(
                data={"simulation_id": result},
                message="Simulación creada exitosamente",
                status_code=201
            )
        return APIRoute.error(
            ErrorCodes.CREATION_ERROR,
            result,
            status_code=400
        )
    except Exception as e:
        return APIRoute.error(
            ErrorCodes.SERVER_ERROR,
            str(e),
            status_code=500
        )

@simulations_bp.route('/<simulation_id>', methods=['GET'])
@APIRoute.standard(auth_required_flag=True)
def get_simulation(simulation_id):
    """Obtiene una simulación por su ID"""
    try:
        simulation = simulation_service.get_simulation(simulation_id)
        if simulation:
            return APIRoute.success(data={"simulation": simulation})
        return APIRoute.error(
            ErrorCodes.NOT_FOUND,
            "Simulación no encontrada",
            status_code=404
        )
    except Exception as e:
        return APIRoute.error(
            ErrorCodes.SERVER_ERROR,
            str(e),
            status_code=500
        )

@simulations_bp.route('/<simulation_id>', methods=['PUT'])
@APIRoute.standard(
    auth_required_flag=True,
    roles=[ROLES["TEACHER"]]
)
def update_simulation(simulation_id):
    """Actualiza una simulación existente"""
    try:
        data = request.get_json()
        success, message = simulation_service.update_simulation(simulation_id, data)
        
        if success:
            return APIRoute.success(message=message)
        return APIRoute.error(
            ErrorCodes.UPDATE_ERROR,
            message,
            status_code=400
        )
    except Exception as e:
        return APIRoute.error(
            ErrorCodes.SERVER_ERROR,
            str(e),
            status_code=500
        )

@simulations_bp.route('/<simulation_id>', methods=['DELETE'])
@APIRoute.standard(
    auth_required_flag=True,
    roles=[ROLES["TEACHER"], ROLES["ADMIN"]]
)
def delete_simulation(simulation_id):
    """Elimina una simulación existente"""
    try:
        success, message = simulation_service.delete_simulation(simulation_id)
        
        if success:
            return APIRoute.success(message=message)
        return APIRoute.error(
            ErrorCodes.DELETE_ERROR,
            message,
            status_code=400
        )
    except Exception as e:
        return APIRoute.error(
            ErrorCodes.SERVER_ERROR,
            str(e),
            status_code=500
        )

@simulations_bp.route('/topic/<topic_id>', methods=['GET'])
@APIRoute.standard(auth_required_flag=True)
def get_simulations_by_topic(topic_id):
    """Obtiene todas las simulaciones asociadas a un tema"""
    try:
        simulations = simulation_service.get_simulations_by_topic(topic_id)
        return APIRoute.success(data={"simulations": simulations})
    except Exception as e:
        return APIRoute.error(
            ErrorCodes.SERVER_ERROR,
            str(e),
            status_code=500
        )

@simulations_bp.route('/<simulation_id>/toggle-evaluation', methods=['PUT'])
@APIRoute.standard(
    auth_required_flag=True,
    roles=[ROLES["TEACHER"]]
)
def toggle_evaluation_mode(simulation_id):
    """Activa o desactiva el modo evaluación de una simulación"""
    try:
        success, message = simulation_service.toggle_evaluation_mode(simulation_id)
        
        if success:
            return APIRoute.success(message=message)
        return APIRoute.error(
            ErrorCodes.UPDATE_ERROR,
            message,
            status_code=400
        )
    except Exception as e:
        return APIRoute.error(
            ErrorCodes.SERVER_ERROR,
            str(e),
            status_code=500
        )

# Rutas para Simulaciones Virtuales
@simulations_bp.route('/virtual', methods=['POST'])
@APIRoute.standard(
    auth_required_flag=True,
    required_fields=['simulation_id', 'virtual_topic_id', 'student_id', 'adaptations']
)
def create_virtual_simulation():
    """Crea una nueva instancia virtual de simulación para un estudiante"""
    try:
        data = request.get_json()
        success, result = virtual_simulation_service.create_virtual_simulation(data)
        
        if success:
            return APIRoute.success(
                data={"virtual_simulation_id": result},
                message="Simulación virtual creada exitosamente",
                status_code=201
            )
        return APIRoute.error(
            ErrorCodes.CREATION_ERROR,
            result,
            status_code=400
        )
    except Exception as e:
        return APIRoute.error(
            ErrorCodes.SERVER_ERROR,
            str(e),
            status_code=500
        )

@simulations_bp.route('/virtual/<virtual_simulation_id>', methods=['GET'])
@APIRoute.standard(auth_required_flag=True)
def get_virtual_simulation(virtual_simulation_id):
    """Obtiene una simulación virtual por su ID"""
    try:
        virtual_simulation = virtual_simulation_service.get_virtual_simulation(virtual_simulation_id)
        if virtual_simulation:
            return APIRoute.success(data={"virtual_simulation": virtual_simulation})
        return APIRoute.error(
            ErrorCodes.NOT_FOUND,
            "Simulación virtual no encontrada",
            status_code=404
        )
    except Exception as e:
        return APIRoute.error(
            ErrorCodes.SERVER_ERROR,
            str(e),
            status_code=500
        )

@simulations_bp.route('/virtual/student/<student_id>', methods=['GET'])
@APIRoute.standard(auth_required_flag=True)
def get_student_simulations(student_id):
    """Obtiene todas las simulaciones virtuales de un estudiante"""
    try:
        simulations = virtual_simulation_service.get_student_simulations(student_id)
        return APIRoute.success(data={"simulations": simulations})
    except Exception as e:
        return APIRoute.error(
            ErrorCodes.SERVER_ERROR,
            str(e),
            status_code=500
        )

@simulations_bp.route('/virtual/<virtual_simulation_id>/progress', methods=['PUT'])
@APIRoute.standard(
    auth_required_flag=True,
    required_fields=['completion_status', 'time_spent', 'interactions']
)
def update_simulation_progress(virtual_simulation_id):
    """Actualiza el progreso de una simulación virtual"""
    try:
        data = request.get_json()
        
        success, message = virtual_simulation_service.update_simulation_progress(
            virtual_simulation_id,
            data['completion_status'],
            data['time_spent'],
            data['interactions']
        )
        
        if success:
            return APIRoute.success(message=message)
        return APIRoute.error(
            ErrorCodes.UPDATE_ERROR,
            message,
            status_code=400
        )
    except Exception as e:
        return APIRoute.error(
            ErrorCodes.SERVER_ERROR,
            str(e),
            status_code=500
        )

# Rutas para Resultados de Simulaciones
@simulations_bp.route('/results', methods=['POST'])
@APIRoute.standard(
    auth_required_flag=True,
    required_fields=['virtual_simulation_id', 'student_id', 'completion_percentage']
)
def save_simulation_result():
    """Guarda el resultado de una simulación completada"""
    try:
        data = request.get_json()
        success, result = simulation_result_service.save_result(data)
        
        if success:
            return APIRoute.success(
                data={"result_id": result},
                message="Resultado guardado exitosamente",
                status_code=201
            )
        return APIRoute.error(
            ErrorCodes.CREATION_ERROR,
            result,
            status_code=400
        )
    except Exception as e:
        return APIRoute.error(
            ErrorCodes.SERVER_ERROR,
            str(e),
            status_code=500
        )

@simulations_bp.route('/results/student/<student_id>', methods=['GET'])
@APIRoute.standard(auth_required_flag=True)
def get_student_results(student_id):
    """Obtiene todos los resultados de simulaciones de un estudiante"""
    try:
        results = simulation_result_service.get_student_results(student_id)
        return APIRoute.success(data={"results": results})
    except Exception as e:
        return APIRoute.error(
            ErrorCodes.SERVER_ERROR,
            str(e),
            status_code=500
        )

@simulations_bp.route('/results/<result_id>', methods=['GET'])
@APIRoute.standard(auth_required_flag=True)
def get_simulation_result(result_id):
    """Obtiene un resultado específico de simulación"""
    try:
        result = simulation_result_service.get_result(result_id)
        if result:
            return APIRoute.success(data={"result": result})
        return APIRoute.error(
            ErrorCodes.NOT_FOUND,
            "Resultado no encontrado",
            status_code=404
        )
    except Exception as e:
        return APIRoute.error(
            ErrorCodes.SERVER_ERROR,
            str(e),
            status_code=500
        ) 