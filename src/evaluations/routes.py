from flask import Blueprint, request, jsonify
from datetime import datetime
from bson import ObjectId
from src.evaluations.services import EvaluationService
from src.shared.decorators import auth_required
from src.shared.validators import validate_object_id

# Crear blueprint para las rutas de evaluaciones
evaluation_routes = Blueprint('evaluations', __name__, url_prefix='/api/evaluations')
evaluation_service = EvaluationService()

# ==================== CRUD Operations ====================

@evaluation_routes.route('/', methods=['POST'])
@auth_required
def create_evaluation(current_user):
    """
    Crear una nueva evaluación.
    """
    try:
        data = request.get_json()
        
        # Validaciones básicas
        required_fields = ['topic_ids', 'title', 'description', 'weight']
        for field in required_fields:
            if field not in data:
                return jsonify({'error': f'Campo requerido: {field}'}), 400
        
        # Convertir topic_ids a ObjectId
        try:
            data['topic_ids'] = [ObjectId(tid) for tid in data['topic_ids']]
        except Exception:
            return jsonify({'error': 'topic_ids inválidos'}), 400
        
        # Agregar campos por defecto
        data['created_by'] = ObjectId(current_user['_id'])
        data['created_at'] = datetime.now()
        data['updated_at'] = datetime.now()
        data['status'] = data.get('status', 'active')
        
        evaluation_id = evaluation_service.create_evaluation(data)
        
        return jsonify({
            'message': 'Evaluación creada exitosamente',
            'evaluation_id': evaluation_id
        }), 201
        
    except ValueError as e:
        return jsonify({'error': str(e)}), 400
    except Exception as e:
        return jsonify({'error': f'Error interno: {str(e)}'}), 500

@evaluation_routes.route('/multi-topic', methods=['POST'])
@auth_required
def create_multi_topic_evaluation(current_user):
    """
    Crear una evaluación multi-tema con ponderaciones.
    """
    try:
        data = request.get_json()
        
        # Validaciones específicas para multi-tema
        required_fields = ['topic_ids', 'title', 'description', 'weights']
        for field in required_fields:
            if field not in data:
                return jsonify({'error': f'Campo requerido: {field}'}), 400
        
        # Validar formato de weights
        if not isinstance(data['weights'], dict):
            return jsonify({'error': 'weights debe ser un diccionario'}), 400
        
        evaluation_id = evaluation_service.create_multi_topic_evaluation(
            topic_ids=data['topic_ids'],
            title=data['title'],
            description=data['description'],
            weights=data['weights'],
            evaluation_type=data.get('evaluation_type', 'assignment'),
            due_date=datetime.fromisoformat(data['due_date']) if data.get('due_date') else None,
            criteria=data.get('criteria', [])
        )
        
        return jsonify({
            'message': 'Evaluación multi-tema creada exitosamente',
            'evaluation_id': evaluation_id
        }), 201
        
    except ValueError as e:
        return jsonify({'error': str(e)}), 400
    except Exception as e:
        return jsonify({'error': f'Error interno: {str(e)}'}), 500

@evaluation_routes.route('/<evaluation_id>', methods=['GET'])
@auth_required
def get_evaluation(current_user, evaluation_id):
    """
    Obtener una evaluación por ID.
    """
    try:
        if not validate_object_id(evaluation_id):
            return jsonify({'error': 'ID de evaluación inválido'}), 400
        
        evaluation = evaluation_service.get_evaluation(evaluation_id)
        
        if not evaluation:
            return jsonify({'error': 'Evaluación no encontrada'}), 404
        
        # Convertir ObjectId a string para JSON
        evaluation['_id'] = str(evaluation['_id'])
        evaluation['topic_ids'] = [str(tid) for tid in evaluation['topic_ids']]
        if evaluation.get('created_by'):
            evaluation['created_by'] = str(evaluation['created_by'])
        
        return jsonify(evaluation), 200
        
    except Exception as e:
        return jsonify({'error': f'Error interno: {str(e)}'}), 500

@evaluation_routes.route('/<evaluation_id>', methods=['PUT'])
@auth_required
def update_evaluation(current_user, evaluation_id):
    """
    Actualizar una evaluación.
    """
    try:
        if not validate_object_id(evaluation_id):
            return jsonify({'error': 'ID de evaluación inválido'}), 400
        
        data = request.get_json()
        
        # Campos que no se pueden actualizar directamente
        protected_fields = ['_id', 'created_at', 'created_by']
        for field in protected_fields:
            data.pop(field, None)
        
        # Convertir topic_ids si están presentes
        if 'topic_ids' in data:
            try:
                data['topic_ids'] = [ObjectId(tid) for tid in data['topic_ids']]
            except Exception:
                return jsonify({'error': 'topic_ids inválidos'}), 400
        
        success = evaluation_service.update_evaluation(evaluation_id, data)
        
        if not success:
            return jsonify({'error': 'Evaluación no encontrada o no se pudo actualizar'}), 404
        
        return jsonify({'message': 'Evaluación actualizada exitosamente'}), 200
        
    except Exception as e:
        return jsonify({'error': f'Error interno: {str(e)}'}), 500

@evaluation_routes.route('/<evaluation_id>', methods=['DELETE'])
@auth_required
def delete_evaluation(current_user, evaluation_id):
    """
    Eliminar una evaluación.
    """
    try:
        if not validate_object_id(evaluation_id):
            return jsonify({'error': 'ID de evaluación inválido'}), 400
        
        success = evaluation_service.delete_evaluation(evaluation_id)
        
        if not success:
            return jsonify({'error': 'Evaluación no encontrada'}), 404
        
        return jsonify({'message': 'Evaluación eliminada exitosamente'}), 200
        
    except Exception as e:
        return jsonify({'error': f'Error interno: {str(e)}'}), 500

# ==================== Submission Management ====================

@evaluation_routes.route('/<evaluation_id>/submissions', methods=['POST'])
@auth_required
def create_submission(current_user, evaluation_id):
    """
    Crear una nueva entrega para una evaluación.
    """
    try:
        if not validate_object_id(evaluation_id):
            return jsonify({'error': 'ID de evaluación inválido'}), 400
        
        data = request.get_json()
        
        # Agregar campos requeridos
        data['evaluation_id'] = evaluation_id
        data['student_id'] = current_user['_id']
        data['created_at'] = datetime.now()
        data['updated_at'] = datetime.now()
        data['status'] = 'submitted'
        
        submission_id = evaluation_service.create_submission(data)
        
        return jsonify({
            'message': 'Entrega creada exitosamente',
            'submission_id': submission_id
        }), 201
        
    except Exception as e:
        return jsonify({'error': f'Error interno: {str(e)}'}), 500

@evaluation_routes.route('/<evaluation_id>/submissions/<student_id>', methods=['GET'])
@auth_required
def get_student_submissions(current_user, evaluation_id, student_id):
    """
    Obtener entregas de un estudiante para una evaluación.
    """
    try:
        if not validate_object_id(evaluation_id):
            return jsonify({'error': 'ID de evaluación inválido'}), 400
        
        submissions = evaluation_service.get_student_submissions(evaluation_id, student_id)
        
        # Convertir ObjectIds a strings
        for submission in submissions:
            submission['_id'] = str(submission['_id'])
            submission['evaluation_id'] = str(submission['evaluation_id'])
            if submission.get('graded_by'):
                submission['graded_by'] = str(submission['graded_by'])
        
        return jsonify(submissions), 200
        
    except Exception as e:
        return jsonify({'error': f'Error interno: {str(e)}'}), 500

@evaluation_routes.route('/submissions/<submission_id>/grade', methods=['POST'])
@auth_required
def grade_submission(current_user, submission_id):
    """
    Calificar una entrega.
    """
    try:
        if not validate_object_id(submission_id):
            return jsonify({'error': 'ID de entrega inválido'}), 400
        
        data = request.get_json()
        
        # Validaciones
        if 'grade' not in data:
            return jsonify({'error': 'Campo requerido: grade'}), 400
        
        try:
            grade = float(data['grade'])
            if grade < 0 or grade > 100:
                return jsonify({'error': 'La calificación debe estar entre 0 y 100'}), 400
        except ValueError:
            return jsonify({'error': 'La calificación debe ser un número'}), 400
        
        success = evaluation_service.grade_submission(
            submission_id=submission_id,
            grade=grade,
            feedback=data.get('feedback', ''),
            graded_by=current_user['_id'],
            topic_scores=data.get('topic_scores')
        )
        
        if not success:
            return jsonify({'error': 'Entrega no encontrada'}), 404
        
        return jsonify({'message': 'Entrega calificada exitosamente'}), 200
        
    except Exception as e:
        return jsonify({'error': f'Error interno: {str(e)}'}), 500

# ==================== Weighted Grading ====================

@evaluation_routes.route('/<evaluation_id>/students/<student_id>/weighted-grade', methods=['GET'])
@auth_required
def calculate_weighted_grade(current_user, evaluation_id, student_id):
    """
    Calcular calificación ponderada para evaluaciones multi-tema.
    """
    try:
        if not validate_object_id(evaluation_id):
            return jsonify({'error': 'ID de evaluación inválido'}), 400
        
        result = evaluation_service.calculate_weighted_grade(evaluation_id, student_id)
        
        return jsonify(result), 200
        
    except Exception as e:
        return jsonify({'error': f'Error interno: {str(e)}'}), 500

@evaluation_routes.route('/<evaluation_id>/weights', methods=['PUT'])
@auth_required
def update_evaluation_weights(current_user, evaluation_id):
    """
    Actualizar ponderaciones de una evaluación multi-tema.
    """
    try:
        if not validate_object_id(evaluation_id):
            return jsonify({'error': 'ID de evaluación inválido'}), 400
        
        data = request.get_json()
        
        if 'weights' not in data:
            return jsonify({'error': 'Campo requerido: weights'}), 400
        
        success = evaluation_service.update_evaluation_weights(evaluation_id, data['weights'])
        
        if not success:
            return jsonify({'error': 'Evaluación no encontrada'}), 404
        
        return jsonify({'message': 'Ponderaciones actualizadas exitosamente'}), 200
        
    except ValueError as e:
        return jsonify({'error': str(e)}), 400
    except Exception as e:
        return jsonify({'error': f'Error interno: {str(e)}'}), 500

# ==================== Content Result Integration ====================

@evaluation_routes.route('/<evaluation_id>/students/<student_id>/process-content-results', methods=['POST'])
@auth_required
def process_content_result_grading(current_user, evaluation_id, student_id):
    """
    Procesar calificación automática basada en resultados de contenido.
    """
    try:
        if not validate_object_id(evaluation_id):
            return jsonify({'error': 'ID de evaluación inválido'}), 400
        
        result = evaluation_service.process_content_result_grading(evaluation_id, student_id)
        
        return jsonify(result), 200
        
    except Exception as e:
        return jsonify({'error': f'Error interno: {str(e)}'}), 500

# ==================== Rubric Management ====================

@evaluation_routes.route('/rubrics', methods=['POST'])
@auth_required
def create_rubric(current_user):
    """
    Crear una nueva rúbrica de evaluación.
    """
    try:
        data = request.get_json()
        
        # Validaciones básicas
        required_fields = ['evaluation_id', 'criteria', 'total_points']
        for field in required_fields:
            if field not in data:
                return jsonify({'error': f'Campo requerido: {field}'}), 400
        
        # Agregar campos por defecto
        data['created_by'] = ObjectId(current_user['_id'])
        data['created_at'] = datetime.now()
        
        rubric_id = evaluation_service.create_rubric(data)
        
        return jsonify({
            'message': 'Rúbrica creada exitosamente',
            'rubric_id': rubric_id
        }), 201
        
    except ValueError as e:
        return jsonify({'error': str(e)}), 400
    except Exception as e:
        return jsonify({'error': f'Error interno: {str(e)}'}), 500

@evaluation_routes.route('/submissions/<submission_id>/grade-with-rubric', methods=['POST'])
@auth_required
def grade_with_rubric(current_user, submission_id):
    """
    Calificar una entrega usando una rúbrica específica.
    """
    try:
        if not validate_object_id(submission_id):
            return jsonify({'error': 'ID de entrega inválido'}), 400
        
        data = request.get_json()
        
        # Validaciones
        required_fields = ['rubric_id', 'criteria_scores']
        for field in required_fields:
            if field not in data:
                return jsonify({'error': f'Campo requerido: {field}'}), 400
        
        if not validate_object_id(data['rubric_id']):
            return jsonify({'error': 'ID de rúbrica inválido'}), 400
        
        result = evaluation_service.grade_with_rubric(
            submission_id=submission_id,
            rubric_id=data['rubric_id'],
            criteria_scores=data['criteria_scores'],
            graded_by=current_user['_id']
        )
        
        return jsonify(result), 200
        
    except ValueError as e:
        return jsonify({'error': str(e)}), 400
    except Exception as e:
        return jsonify({'error': f'Error interno: {str(e)}'}), 500

# ==================== Query and Analytics ====================

@evaluation_routes.route('/by-topic/<topic_id>', methods=['GET'])
@auth_required
def get_evaluations_by_topic(current_user, topic_id):
    """
    Obtener evaluaciones que incluyen un tema específico.
    """
    try:
        if not validate_object_id(topic_id):
            return jsonify({'error': 'ID de tema inválido'}), 400
        
        evaluations = evaluation_service.get_evaluations_by_topic(topic_id)
        
        # Convertir ObjectIds a strings
        for evaluation in evaluations:
            evaluation['_id'] = str(evaluation['_id'])
            evaluation['topic_ids'] = [str(tid) for tid in evaluation['topic_ids']]
            if evaluation.get('created_by'):
                evaluation['created_by'] = str(evaluation['created_by'])
        
        return jsonify(evaluations), 200
        
    except Exception as e:
        return jsonify({'error': f'Error interno: {str(e)}'}), 500

@evaluation_routes.route('/students/<student_id>/summary', methods=['GET'])
@auth_required
def get_student_evaluation_summary(current_user, student_id):
    """
    Obtener resumen de evaluaciones para un estudiante.
    """
    try:
        # Obtener parámetros opcionales
        topic_ids = request.args.getlist('topic_ids')
        
        # Validar topic_ids si se proporcionan
        if topic_ids:
            for tid in topic_ids:
                if not validate_object_id(tid):
                    return jsonify({'error': f'ID de tema inválido: {tid}'}), 400
        
        summary = evaluation_service.get_student_evaluation_summary(
            student_id=student_id,
            topic_ids=topic_ids if topic_ids else None
        )
        
        return jsonify(summary), 200
        
    except Exception as e:
        return jsonify({'error': f'Error interno: {str(e)}'}), 500

# ==================== Bulk Operations ====================

@evaluation_routes.route('/bulk/create', methods=['POST'])
@auth_required
def bulk_create_evaluations(current_user):
    """
    Crear múltiples evaluaciones en lote.
    """
    try:
        data = request.get_json()
        
        if 'evaluations' not in data or not isinstance(data['evaluations'], list):
            return jsonify({'error': 'Campo requerido: evaluations (lista)'}), 400
        
        results = []
        errors = []
        
        for i, eval_data in enumerate(data['evaluations']):
            try:
                # Agregar campos comunes
                eval_data['created_by'] = ObjectId(current_user['_id'])
                eval_data['created_at'] = datetime.now()
                eval_data['updated_at'] = datetime.now()
                eval_data['status'] = eval_data.get('status', 'active')
                
                # Convertir topic_ids
                if 'topic_ids' in eval_data:
                    eval_data['topic_ids'] = [ObjectId(tid) for tid in eval_data['topic_ids']]
                
                evaluation_id = evaluation_service.create_evaluation(eval_data)
                results.append({
                    'index': i,
                    'evaluation_id': evaluation_id,
                    'success': True
                })
                
            except Exception as e:
                errors.append({
                    'index': i,
                    'error': str(e)
                })
        
        return jsonify({
            'message': f'Procesadas {len(results)} evaluaciones exitosamente',
            'results': results,
            'errors': errors,
            'total_processed': len(data['evaluations']),
            'successful': len(results),
            'failed': len(errors)
        }), 200
        
    except Exception as e:
        return jsonify({'error': f'Error interno: {str(e)}'}), 500

# ==================== Health Check ====================

@evaluation_routes.route('/health', methods=['GET'])
def health_check():
    """
    Verificar el estado del servicio de evaluaciones.
    """
    try:
        # Verificar conexión a la base de datos
        evaluation_service.evaluations_collection.find_one()
        
        return jsonify({
            'status': 'healthy',
            'service': 'evaluations',
            'timestamp': datetime.now().isoformat()
        }), 200
        
    except Exception as e:
        return jsonify({
            'status': 'unhealthy',
            'service': 'evaluations',
            'error': str(e),
            'timestamp': datetime.now().isoformat()
        }), 500