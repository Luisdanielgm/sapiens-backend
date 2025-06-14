from flask import Blueprint, request, jsonify, g
from flask_jwt_extended import jwt_required, get_jwt_identity
from bson import ObjectId
import logging

from src.shared.decorators import handle_errors, auth_required, validate_json, role_required
from src.shared.database import get_db
from .services import ContentService, ContentTypeService, VirtualContentService, ContentResultService

content_bp = Blueprint('content', __name__, url_prefix='/api/content')

# Servicios
content_service = ContentService()
content_type_service = ContentTypeService()
virtual_content_service = VirtualContentService()
content_result_service = ContentResultService()

# ============================================
# ENDPOINTS DE TIPOS DE CONTENIDO
# ============================================

@content_bp.route('/types', methods=['GET'])
@jwt_required()
def get_content_types():
    """
    Obtiene todos los tipos de contenido disponibles.
    Query params: category, subcategory
    """
    try:
        category = request.args.get('category')  # static, interactive, immersive
        subcategory = request.args.get('subcategory')  # game, simulation, quiz, diagram, etc.
        
        content_types = content_type_service.get_content_types(category, subcategory)
        
        return jsonify({
            "success": True,
            "content_types": content_types
        }), 200
        
    except Exception as e:
        logging.error(f"Error obteniendo tipos de contenido: {str(e)}")
        return jsonify({
            "success": False,
            "message": "Error interno del servidor"
        }), 500

@content_bp.route('/types', methods=['POST'])
@jwt_required()
@role_required(['admin'])
def create_content_type():
    """
    Crea un nuevo tipo de contenido.
    """
    try:
        data = request.json
        
        success, result = content_type_service.create_content_type(data)
        
        if success:
            return jsonify({
                "success": True,
                "message": "Tipo de contenido creado exitosamente",
                "content_type_id": result
            }), 201
        else:
            return jsonify({
                "success": False,
                "message": result
            }), 400
            
    except Exception as e:
        logging.error(f"Error creando tipo de contenido: {str(e)}")
        return jsonify({
            "success": False,
            "message": "Error interno del servidor"
        }), 500

# ============================================
# ENDPOINTS DE CONTENIDO UNIFICADO
# ============================================

@content_bp.route('/', methods=['POST'])
@jwt_required()
@role_required(['professor', 'admin'])
def create_content():
    """
    Crea contenido de cualquier tipo (game, simulation, quiz, diagram, etc.)
    
    Body:
    {
        "topic_id": "ObjectId",
        "content_type": "game|simulation|quiz|diagram|text|video|...",
        "title": "Título del contenido",
        "description": "Descripción",
        "content_data": {...},  // Contenido específico según tipo
        "interactive_config": {...},  // Para tipos interactivos
        "template_id": "ObjectId",  // Opcional
        "difficulty": "easy|medium|hard",
        "estimated_duration": 15,
        "learning_objectives": [...],
        "tags": [...],
        "resources": [...],
        "generation_prompt": "..."  // Para contenido generado por IA
    }
    """
    try:
        data = request.json
        data['creator_id'] = get_jwt_identity()
        
        success, result = content_service.create_content(data)
        
        if success:
            return jsonify({
                "success": True,
                "message": "Contenido creado exitosamente",
                "content_id": result
            }), 201
        else:
            return jsonify({
                "success": False,
                "message": result
            }), 400
            
    except Exception as e:
        logging.error(f"Error creando contenido: {str(e)}")
        return jsonify({
            "success": False,
            "message": "Error interno del servidor"
        }), 500

@content_bp.route('/topic/<topic_id>', methods=['GET'])
@jwt_required()
def get_topic_content(topic_id):
    """
    Obtiene todo el contenido de un tema.
    Query params: content_type (para filtrar por tipo específico)
    """
    try:
        content_type = request.args.get('content_type')
        
        contents = content_service.get_topic_content(topic_id, content_type)
        
        return jsonify({
            "success": True,
            "contents": contents
        }), 200
        
    except Exception as e:
        logging.error(f"Error obteniendo contenido del tema: {str(e)}")
        return jsonify({
            "success": False,
            "message": "Error interno del servidor"
        }), 500

@content_bp.route('/topic/<topic_id>/interactive', methods=['GET'])
@jwt_required()
def get_interactive_content(topic_id):
    """
    Obtiene solo contenido interactivo de un tema (games, simulations, quizzes).
    """
    try:
        contents = content_service.get_interactive_content(topic_id)
        
        return jsonify({
            "success": True,
            "interactive_contents": contents
        }), 200
        
    except Exception as e:
        logging.error(f"Error obteniendo contenido interactivo: {str(e)}")
        return jsonify({
            "success": False,
            "message": "Error interno del servidor"
        }), 500

@content_bp.route('/<content_id>', methods=['PUT'])
@jwt_required()
@role_required(['professor', 'admin'])
def update_content(content_id):
    """
    Actualiza contenido existente.
    """
    try:
        data = request.json
        
        success, result = content_service.update_content(content_id, data)
        
        if success:
            return jsonify({
                "success": True,
                "message": result
            }), 200
        else:
            return jsonify({
                "success": False,
                "message": result
            }), 400
            
    except Exception as e:
        logging.error(f"Error actualizando contenido: {str(e)}")
        return jsonify({
            "success": False,
            "message": "Error interno del servidor"
        }), 500

@content_bp.route('/<content_id>', methods=['DELETE'])
@jwt_required()
@role_required(['professor', 'admin'])
def delete_content(content_id):
    """
    Elimina contenido (soft delete).
    """
    try:
        success, result = content_service.delete_content(content_id)
        
        if success:
            return jsonify({
                "success": True,
                "message": result
            }), 200
        else:
            return jsonify({
                "success": False,
                "message": result
            }), 404
            
    except Exception as e:
        logging.error(f"Error eliminando contenido: {str(e)}")
        return jsonify({
            "success": False,
            "message": "Error interno del servidor"
        }), 500

# ============================================
# ENDPOINTS DE CONTENIDO PERSONALIZADO
# ============================================

@content_bp.route('/personalize', methods=['POST'])
@jwt_required()
def personalize_content():
    """
    Personaliza contenido para un estudiante específico.
    
    Body:
    {
        "virtual_topic_id": "ObjectId",
        "content_id": "ObjectId",
        "student_id": "ObjectId",  // Opcional, por defecto usuario actual
        "cognitive_profile": {...}  // Opcional, se obtiene de BD si no se proporciona
    }
    """
    try:
        data = request.json
        student_id = data.get('student_id', get_jwt_identity())
        
        # Obtener perfil cognitivo si no se proporciona
        cognitive_profile = data.get('cognitive_profile')
        if not cognitive_profile:
            profile = get_db().cognitive_profiles.find_one({"user_id": ObjectId(student_id)})
            if profile:
                cognitive_profile = profile
            else:
                return jsonify({
                    "success": False,
                    "message": "No se encontró perfil cognitivo para el estudiante"
                }), 404
        
        success, result = virtual_content_service.personalize_content(
            data['virtual_topic_id'],
            data['content_id'],
            student_id,
            cognitive_profile
        )
        
        if success:
            return jsonify({
                "success": True,
                "message": "Contenido personalizado exitosamente",
                "virtual_content_id": result
            }), 201
        else:
            return jsonify({
                "success": False,
                "message": result
            }), 400
            
    except Exception as e:
        logging.error(f"Error personalizando contenido: {str(e)}")
        return jsonify({
            "success": False,
            "message": "Error interno del servidor"
        }), 500

@content_bp.route('/interaction', methods=['POST'])
@jwt_required()
def track_interaction():
    """
    Registra interacción con contenido personalizado.
    
    Body:
    {
        "virtual_content_id": "ObjectId",
        "interaction_data": {
            "time_spent": 120,  // segundos
            "completion_percentage": 75.5,
            "completion_status": "in_progress|completed",
            "score": 85.0,  // Para contenido evaluable
            "interactions": [...]  // Detalles específicos de interacción
        }
    }
    """
    try:
        data = request.json
        
        success = virtual_content_service.track_interaction(
            data['virtual_content_id'],
            data['interaction_data']
        )
        
        if success:
            return jsonify({
                "success": True,
                "message": "Interacción registrada exitosamente"
            }), 200
        else:
            return jsonify({
                "success": False,
                "message": "Error registrando interacción"
            }), 400
            
    except Exception as e:
        logging.error(f"Error registrando interacción: {str(e)}")
        return jsonify({
            "success": False,
            "message": "Error interno del servidor"
        }), 500

# ============================================
# ENDPOINTS DE RESULTADOS UNIFICADOS
# ============================================

@content_bp.route('/results', methods=['POST'])
@jwt_required()
def record_result():
    """
    Registra resultado de interacción con contenido (game, simulation, quiz, etc.)
    
    Body:
    {
        "virtual_content_id": "ObjectId",
        "student_id": "ObjectId",  // Opcional, por defecto usuario actual
        "session_data": {
            "score": 88.5,
            "completion_percentage": 95.0,
            "time_spent": 420,
            "content_specific_data": {...}  // Datos específicos según tipo de contenido
        },
        "learning_metrics": {
            "effectiveness": 0.87,
            "engagement": 0.92,
            "mastery_improvement": 0.15
        },
        "feedback": "Excelente trabajo...",
        "session_type": "completion|practice|assessment"
    }
    """
    try:
        data = request.json
        data['student_id'] = data.get('student_id', get_jwt_identity())
        
        success, result = content_result_service.record_result(data)
        
        if success:
            return jsonify({
                "success": True,
                "message": "Resultado registrado exitosamente",
                "result_id": result
            }), 201
        else:
            return jsonify({
                "success": False,
                "message": result
            }), 400
            
    except Exception as e:
        logging.error(f"Error registrando resultado: {str(e)}")
        return jsonify({
            "success": False,
            "message": "Error interno del servidor"
        }), 500

@content_bp.route('/results/student/<student_id>', methods=['GET'])
@jwt_required()
def get_student_results(student_id):
    """
    Obtiene resultados de un estudiante.
    Query params: content_type (para filtrar por tipo específico)
    """
    try:
        # Verificar permisos: solo el mismo estudiante o profesores/admin
        current_user = get_jwt_identity()
        if current_user != student_id and not g.user.get('role') in ['professor', 'admin']:
            return jsonify({
                "success": False,
                "message": "No autorizado para ver estos resultados"
            }), 403
        
        content_type = request.args.get('content_type')
        
        results = content_result_service.get_student_results(student_id, content_type)
        
        return jsonify({
            "success": True,
            "results": results
        }), 200
        
    except Exception as e:
        logging.error(f"Error obteniendo resultados del estudiante: {str(e)}")
        return jsonify({
            "success": False,
            "message": "Error interno del servidor"
        }), 500

@content_bp.route('/results/my', methods=['GET'])
@jwt_required()
def get_my_results():
    """
    Obtiene resultados del usuario actual.
    Query params: content_type
    """
    try:
        student_id = get_jwt_identity()
        content_type = request.args.get('content_type')
        
        results = content_result_service.get_student_results(student_id, content_type)
        
        return jsonify({
            "success": True,
            "results": results
        }), 200
        
    except Exception as e:
        logging.error(f"Error obteniendo mis resultados: {str(e)}")
        return jsonify({
            "success": False,
            "message": "Error interno del servidor"
        }), 500

# ============================================
# ENDPOINTS DE COMPATIBILIDAD (LEGACY)
# ============================================

@content_bp.route('/games', methods=['POST'])
@jwt_required()
@role_required(['professor', 'admin'])
def create_game_legacy():
    """
    Endpoint de compatibilidad para crear juegos.
    Redirige al endpoint unificado con content_type="game"
    """
    try:
        data = request.json
        data['content_type'] = 'game'
        data['creator_id'] = get_jwt_identity()
        
        success, result = content_service.create_content(data)
        
        if success:
            return jsonify({
                "success": True,
                "message": "Juego creado exitosamente",
                "game_id": result  # Mantener nombre legacy
            }), 201
        else:
            return jsonify({
                "success": False,
                "message": result
            }), 400
            
    except Exception as e:
        logging.error(f"Error creando juego (legacy): {str(e)}")
        return jsonify({
            "success": False,
            "message": "Error interno del servidor"
        }), 500

@content_bp.route('/simulations', methods=['POST'])
@jwt_required()
@role_required(['professor', 'admin'])
def create_simulation_legacy():
    """
    Endpoint de compatibilidad para crear simulaciones.
    """
    try:
        data = request.json
        data['content_type'] = 'simulation'
        data['creator_id'] = get_jwt_identity()
        
        success, result = content_service.create_content(data)
        
        if success:
            return jsonify({
                "success": True,
                "message": "Simulación creada exitosamente",
                "simulation_id": result
            }), 201
        else:
            return jsonify({
                "success": False,
                "message": result
            }), 400
            
    except Exception as e:
        logging.error(f"Error creando simulación (legacy): {str(e)}")
        return jsonify({
            "success": False,
            "message": "Error interno del servidor"
        }), 500

@content_bp.route('/quizzes', methods=['POST'])
@jwt_required()
@role_required(['professor', 'admin'])
def create_quiz_legacy():
    """
    Endpoint de compatibilidad para crear quizzes.
    """
    try:
        data = request.json
        data['content_type'] = 'quiz'
        data['creator_id'] = get_jwt_identity()
        
        success, result = content_service.create_content(data)
        
        if success:
            return jsonify({
                "success": True,
                "message": "Quiz creado exitosamente",
                "quiz_id": result
            }), 201
        else:
            return jsonify({
                "success": False,
                "message": result
            }), 400
            
    except Exception as e:
        logging.error(f"Error creando quiz (legacy): {str(e)}")
        return jsonify({
            "success": False,
            "message": "Error interno del servidor"
        }), 500 