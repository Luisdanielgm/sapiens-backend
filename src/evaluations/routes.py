from flask import Blueprint, request, jsonify
from datetime import datetime
from bson import ObjectId
from src.evaluations.services import EvaluationService
from src.evaluations.models import EvaluationResource
from src.evaluations.weighted_grading_service import weighted_grading_service
from src.shared.decorators import auth_required
from src.shared.validators import validate_object_id
import os
from werkzeug.utils import secure_filename

# Crear blueprint para las rutas de evaluaciones
evaluation_routes = Blueprint('evaluations', __name__, url_prefix='/api/evaluations')
evaluation_service = EvaluationService()

# ==================== CRUD Operations ====================

@evaluation_routes.route('/', methods=['GET'])
@auth_required
def list_evaluations(current_user):
    """
    Listar evaluaciones con filtros opcionales.
    """
    try:
        query = {}
        topic_id = request.args.get('topic_id')
        evaluation_type = request.args.get('evaluation_type')
        status = request.args.get('status')
        score_source = request.args.get('score_source')
        blocking_scope = request.args.get('blocking_scope')
        blocking_condition = request.args.get('blocking_condition')
        virtual_topic_id = request.args.get('virtual_topic_id')
        virtual_module_id = request.args.get('virtual_module_id')

        if topic_id and validate_object_id(topic_id):
            query['topic_ids'] = ObjectId(topic_id)
        if evaluation_type:
            query['evaluation_type'] = evaluation_type
        if status:
            query['status'] = status
        if score_source:
            query['score_source'] = score_source
        if blocking_scope:
            query['blocking_scope'] = blocking_scope
        if blocking_condition:
            query['blocking_condition'] = blocking_condition
        if virtual_topic_id and validate_object_id(virtual_topic_id):
            query['virtual_topic_id'] = ObjectId(virtual_topic_id)
        if virtual_module_id and validate_object_id(virtual_module_id):
            query['virtual_module_id'] = ObjectId(virtual_module_id)

        evaluations = list(evaluation_service.evaluations_collection.find(query).sort("created_at", -1))
        for ev in evaluations:
            ev["_id"] = str(ev["_id"])
            ev["topic_ids"] = [str(tid) for tid in ev.get("topic_ids", [])]
            if ev.get("virtual_topic_id"):
                ev["virtual_topic_id"] = str(ev["virtual_topic_id"])
            if ev.get("virtual_module_id"):
                ev["virtual_module_id"] = str(ev["virtual_module_id"])
            if ev.get("linked_quiz_id"):
                ev["linked_quiz_id"] = str(ev["linked_quiz_id"])
        return jsonify({"evaluations": evaluations}), 200
    except Exception as e:
        return jsonify({'error': f'Error interno: {str(e)}'}), 500

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
        
        data = request.get_json() or {}
        submission_type = data.get("submission_type", "text")
        if submission_type not in ["file", "text", "url", "quiz_response", "content_result"]:
            return jsonify({'error': 'submission_type invケlido'}), 400

        payload = {
            "evaluation_id": evaluation_id,
            "student_id": current_user['_id'],
            "submission_type": submission_type,
            "content": data.get("content"),
            "file_path": data.get("file_path"),
            "url": data.get("url"),
            "status": "submitted",
            "created_at": datetime.now(),
            "updated_at": datetime.now(),
            "attempts": data.get("attempts", 1),
            "submission_metadata": data.get("submission_metadata", {})
        }

        submission_id = evaluation_service.create_submission(payload)
        
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
            if submission.get('student_id'):
                submission['student_id'] = str(submission['student_id'])
            if submission.get('resource_id'):
                submission['resource_id'] = str(submission['resource_id'])
        
        return jsonify(submissions), 200
        
    except Exception as e:
        return jsonify({'error': f'Error interno: {str(e)}'}), 500

@evaluation_routes.route('/<evaluation_id>/submissions', methods=['GET'])
@auth_required
def list_submissions(current_user, evaluation_id):
    """
    Listar entregas de una evaluaciИn. Filtros: student_id.
    """
    try:
        if not validate_object_id(evaluation_id):
            return jsonify({'error': 'ID de evaluaciИn invケlido'}), 400
        student_id = request.args.get('student_id')
        query = {"evaluation_id": ObjectId(evaluation_id)}
        if student_id and validate_object_id(student_id):
            query["student_id"] = ObjectId(student_id)
        submissions = list(evaluation_service.submissions_collection.find(query).sort("created_at", -1))
        for submission in submissions:
            submission['_id'] = str(submission['_id'])
            submission['evaluation_id'] = str(submission['evaluation_id'])
            if submission.get('graded_by'):
                submission['graded_by'] = str(submission['graded_by'])
            if submission.get('student_id'):
                submission['student_id'] = str(submission['student_id'])
            if submission.get('resource_id'):
                submission['resource_id'] = str(submission['resource_id'])
        return jsonify({"submissions": submissions}), 200
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

# ==================== Resources Management ====================

@evaluation_routes.route('/<evaluation_id>/resources', methods=['POST'])
@auth_required
def link_resource(current_user, evaluation_id):
    """
    Vincular un recurso a una evaluaciИn. Campos: resource_id, role (template|supporting_material|submission)
    """
    try:
        if not validate_object_id(evaluation_id):
            return jsonify({'error': 'ID de evaluaciИn invケlido'}), 400
        data = request.get_json() or {}
        resource_id = data.get("resource_id")
        role = data.get("role")
        if not resource_id or not validate_object_id(resource_id):
            return jsonify({'error': 'resource_id invケlido'}), 400
        if role not in ["template", "supporting_material", "submission"]:
            return jsonify({'error': 'role invケlido'}), 400

        link = EvaluationResource(
            evaluation_id=evaluation_id,
            resource_id=resource_id,
            role=role,
            created_by=current_user["_id"],
        )
        evaluation_service.resources_collection.insert_one(link.to_dict())
        return jsonify({"message": "Recurso vinculado", "link_id": str(link._id)}), 201
    except Exception as e:
        return jsonify({'error': f'Error interno: {str(e)}'}), 500

@evaluation_routes.route('/<evaluation_id>/resources', methods=['GET'])
@auth_required
def list_resources(current_user, evaluation_id):
    """
    Listar recursos vinculados a una evaluaciИn. Filtro opcional: role.
    """
    try:
        if not validate_object_id(evaluation_id):
            return jsonify({'error': 'ID de evaluaciИn invケlido'}), 400
        role = request.args.get("role")
        query = {"evaluation_id": ObjectId(evaluation_id)}
        if role:
            query["role"] = role
        resources = list(evaluation_service.resources_collection.find(query).sort("created_at", -1))
        for r in resources:
            r["_id"] = str(r["_id"])
            r["evaluation_id"] = str(r["evaluation_id"])
            r["resource_id"] = str(r["resource_id"])
            r["created_by"] = str(r["created_by"])
        return jsonify({"resources": resources}), 200
    except Exception as e:
        return jsonify({'error': f'Error interno: {str(e)}'}), 500

@evaluation_routes.route('/<evaluation_id>/resources/<resource_id>', methods=['DELETE'])
@auth_required
def unlink_resource(current_user, evaluation_id, resource_id):
    """
    Eliminar un vínculo de recurso de evaluaciИn.
    """
    try:
        if not (validate_object_id(evaluation_id) and validate_object_id(resource_id)):
            return jsonify({'error': 'IDs invケlidos'}), 400
        result = evaluation_service.resources_collection.delete_one({
            "evaluation_id": ObjectId(evaluation_id),
            "resource_id": ObjectId(resource_id)
        })
        if result.deleted_count == 0:
            return jsonify({'error': 'VinculaciИn no encontrada'}), 404
        return jsonify({'message': 'VinculaciИn eliminada'}), 200
    except Exception as e:
        return jsonify({'error': f'Error interno: {str(e)}'}), 500

# ==================== Rubric Management ====================

@evaluation_routes.route('/<evaluation_id>/rubric', methods=['GET'])
@auth_required
def get_rubric(current_user, evaluation_id):
    """
    Obtener rカbrica de evaluaciИn.
    """
    try:
        if not validate_object_id(evaluation_id):
            return jsonify({'error': 'ID de evaluaciИn invケlido'}), 400
        rubric = evaluation_service.rubrics_collection.find_one({"evaluation_id": ObjectId(evaluation_id)})
        if not rubric:
            return jsonify({'error': 'Rカbrica no encontrada'}), 404
        rubric["_id"] = str(rubric["_id"])
        rubric["evaluation_id"] = str(rubric["evaluation_id"])
        if rubric.get("created_by"):
            rubric["created_by"] = str(rubric["created_by"])
        return jsonify(rubric), 200
    except Exception as e:
        return jsonify({'error': f'Error interno: {str(e)}'}), 500

@evaluation_routes.route('/<evaluation_id>/rubric', methods=['POST'])
@auth_required
def create_or_update_rubric(current_user, evaluation_id):
    """
    Crear/actualizar rカbrica.
    """
    try:
        if not validate_object_id(evaluation_id):
            return jsonify({'error': 'ID de evaluaciИn invケlido'}), 400
        data = request.get_json() or {}
        if "criteria" not in data or "total_points" not in data:
            return jsonify({'error': 'criteria y total_points requeridos'}), 400
        rubric = EvaluationRubric(
            evaluation_id=evaluation_id,
            title=data.get("title", "Rカbrica"),
            description=data.get("description", ""),
            criteria=data.get("criteria", []),
            total_points=data.get("total_points", 100.0),
            grading_scale=data.get("grading_scale"),
            created_by=current_user.get("_id"),
            rubric_type=data.get("rubric_type", "standard")
        )
        self_ref = evaluation_service.rubrics_collection
        self_ref.update_one(
            {"evaluation_id": rubric.evaluation_id},
            {"$set": rubric.to_dict()},
            upsert=True
        )
        return jsonify({"message": "Rカbrica guardada"}), 200
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

@evaluation_routes.route('/<evaluation_id>/results', methods=['GET'])
@auth_required
def list_evaluation_results(current_user, evaluation_id):
    """
    Obtener resultados consolidados de una evaluaciИn.
    """
    try:
        if not validate_object_id(evaluation_id):
            return jsonify({'error': 'ID de evaluaciИn invケlido'}), 400
        
        results = evaluation_service.get_results_by_evaluation(evaluation_id)
        return jsonify({"results": results}), 200
    except Exception as e:
        return jsonify({'error': f'Error interno: {str(e)}'}), 500

@evaluation_routes.route('/<evaluation_id>/progress-lock', methods=['GET'])
@auth_required
def evaluation_progress_lock(current_user, evaluation_id):
    """
    Consultar estado de bloqueo de una evaluaciИn para un estudiante.
    Requiere query param student_id.
    """
    try:
        student_id = request.args.get('student_id')
        if not student_id or not validate_object_id(student_id):
            return jsonify({'error': 'student_id requerido y válido'}), 400
        evaluation = evaluation_service.get_evaluation(evaluation_id)
        if not evaluation:
            return jsonify({'error': 'EvaluaciИn no encontrada'}), 404

        blocking_scope = evaluation.get("blocking_scope")
        blocking_condition = evaluation.get("blocking_condition")
        pass_score = evaluation.get("pass_score")

        # Si no hay bloqueo configurado
        if not blocking_scope or blocking_scope == "none":
            return jsonify({"blocked": False, "reason": None}), 200

        # Entregas
        submissions = evaluation_service.get_student_submissions(evaluation_id, student_id)
        latest = submissions[0] if submissions else None

        # Resultado consolidado
        result = evaluation_service.results_collection.find_one({
            "evaluation_id": ObjectId(evaluation_id),
            "student_id": ObjectId(student_id)
        })
        score = None
        if result:
            score = result.get("score")

        blocked = True
        reason = "CondiciИn de bloqueo no cumplida"

        if blocking_condition == "submission_received":
            blocked = latest is None
            reason = None if not blocked else "Falta entregar"
        elif blocking_condition == "graded":
            blocked = not latest or latest.get("status") != "graded"
            reason = None if not blocked else "Pendiente de calificar"
        elif blocking_condition == "auto_graded_ok":
            threshold = pass_score if pass_score is not None else 0
            score_to_check = score if score is not None else (latest.get("final_grade") if latest else None)
            blocked = score_to_check is None or score_to_check < threshold
            reason = None if not blocked else f"Requiere puntaje >= {threshold}"
        else:
            # fallback: no bloqueo
            blocked = False
            reason = None

        return jsonify({
            "blocked": blocked,
            "blocking_scope": blocking_scope,
            "blocking_condition": blocking_condition,
            "reason": reason,
            "latest_submission_id": str(latest["_id"]) if latest else None,
            "score": score
        }), 200
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

# ==================== Weighted Grading Service ====================

@evaluation_routes.route('/<evaluation_id>/students/<student_id>/calculate-weighted-grade', methods=['POST'])
@auth_required
def calculate_weighted_grade_for_student(current_user, evaluation_id, student_id):
    """
    Calcular calificación ponderada para un estudiante específico.
    """
    try:
        if not validate_object_id(evaluation_id):
            return jsonify({'error': 'ID de evaluación inválido'}), 400
        
        result = weighted_grading_service.calculate_weighted_grade_for_student(evaluation_id, student_id)
        
        if 'error' in result:
            return jsonify({'error': result['error']}), 400
        
        return jsonify(result), 200
        
    except Exception as e:
        return jsonify({'error': f'Error interno: {str(e)}'}), 500

@evaluation_routes.route('/<evaluation_id>/students/<student_id>/update-submission-grade', methods=['PUT'])
@auth_required
def update_submission_grade_weighted(current_user, evaluation_id, student_id):
    """
    Actualizar calificación de submission basada en cálculo ponderado.
    """
    try:
        if not validate_object_id(evaluation_id):
            return jsonify({'error': 'ID de evaluación inválido'}), 400
        
        success = weighted_grading_service.update_evaluation_submission_grade(evaluation_id, student_id)
        
        if not success:
            return jsonify({'error': 'No se pudo actualizar la calificación'}), 400
        
        return jsonify({'message': 'Calificación actualizada exitosamente'}), 200
        
    except Exception as e:
        return jsonify({'error': f'Error interno: {str(e)}'}), 500

@evaluation_routes.route('/<evaluation_id>/recalculate-all-grades', methods=['POST'])
@auth_required
def recalculate_all_grades(current_user, evaluation_id):
    """
    Recalcular calificaciones ponderadas para todos los estudiantes de una evaluación.
    """
    try:
        if not validate_object_id(evaluation_id):
            return jsonify({'error': 'ID de evaluación inválido'}), 400
        
        result = weighted_grading_service.recalculate_all_students_for_evaluation(evaluation_id)
        
        if 'error' in result:
            return jsonify({'error': result['error']}), 400
        
        return jsonify(result), 200
        
    except Exception as e:
        return jsonify({'error': f'Error interno: {str(e)}'}), 500

@evaluation_routes.route('/validate-topic-weights', methods=['POST'])
@auth_required
def validate_topic_weights(current_user):
    """
    Validar pesos de temas para evaluaciones multi-tema.
    """
    try:
        data = request.get_json()
        
        if 'topic_weights' not in data:
            return jsonify({'error': 'Campo requerido: topic_weights'}), 400
        
        is_valid, message = weighted_grading_service.validate_topic_weights(data['topic_weights'])
        
        return jsonify({
            'valid': is_valid,
            'message': message,
            'topic_weights': data['topic_weights']
        }), 200
        
    except Exception as e:
        return jsonify({'error': f'Error interno: {str(e)}'}), 500

@evaluation_routes.route('/topics/<topic_id>/performance-summary', methods=['GET'])
@auth_required
def get_topic_performance_summary(current_user, topic_id):
    """
    Obtener resumen de rendimiento para un tema específico.
    """
    try:
        if not validate_object_id(topic_id):
            return jsonify({'error': 'ID de tema inválido'}), 400
        
        # Obtener parámetro opcional de límite
        limit = request.args.get('limit', 50, type=int)
        if limit > 200:  # Limitar para evitar sobrecarga
            limit = 200
        
        result = weighted_grading_service.get_topic_performance_summary(topic_id, limit)
        
        if 'error' in result:
            return jsonify({'error': result['error']}), 400
        
        return jsonify(result), 200
        
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
