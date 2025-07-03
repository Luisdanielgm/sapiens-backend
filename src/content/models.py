from datetime import datetime
from bson import ObjectId
from typing import Dict, List, Optional, Any, Union

class ContentType:
    """
    Definición unificada de tipos de contenido (estáticos e interactivos).
    Reemplaza las definiciones separadas de games, simulations, quizzes.
    """
    def __init__(self,
                 code: str,
                 name: str,
                 category: str,  # "static", "interactive", "immersive"
                 subcategory: str = None,  # "game", "simulation", "quiz", "diagram", etc.
                 description: str = "",
                 template_schema: Dict = None,
                 cognitive_compatibility: Dict = None,
                 accessibility_features: List[str] = None,
                 generation_prompts: Dict = None,
                 rendering_config: Dict = None,
                 interaction_config: Dict = None,
                 status: str = "active"):
        
        self.code = code
        self.name = name
        self.category = category
        self.subcategory = subcategory or "default"
        self.description = description
        self.template_schema = template_schema or {}
        self.cognitive_compatibility = cognitive_compatibility or {}
        self.accessibility_features = accessibility_features or []
        self.generation_prompts = generation_prompts or {}
        self.rendering_config = rendering_config or {}
        self.interaction_config = interaction_config or {}
        self.status = status
        self.created_at = datetime.now()
        self.updated_at = datetime.now()

    def to_dict(self) -> Dict:
        return {
            "code": self.code,
            "name": self.name,
            "category": self.category,
            "subcategory": self.subcategory,
            "description": self.description,
            "template_schema": self.template_schema,
            "cognitive_compatibility": self.cognitive_compatibility,
            "accessibility_features": self.accessibility_features,
            "generation_prompts": self.generation_prompts,
            "rendering_config": self.rendering_config,
            "interaction_config": self.interaction_config,
            "status": self.status,
            "created_at": self.created_at,
            "updated_at": self.updated_at
        }

class TopicContent:
    """
    Contenido unificado que puede ser estático (diagram, text) o interactivo (game, simulation, quiz).
    Reemplaza las colecciones separadas de games, simulations, quizzes.
    """
    def __init__(self,
                 topic_id: str,
                 content_type: str,  # Código del tipo de contenido
                 title: str,
                 description: str = "",
                 content_data: Dict = None,  # Contenido principal (HTML, JSON, etc.)
                 interactive_config: Dict = None,  # Config para tipos interactivos
                 template_id: str = None,  # Referencia a plantilla si usa una
                 learning_objectives: List[str] = None,
                 difficulty: str = "medium",
                 estimated_duration: int = 15,  # minutos
                 tags: List[str] = None,
                 resources: List[str] = None,
                 web_resources: List[Dict] = None,
                 generation_prompt: str = None,
                 ai_credits: bool = True,
                 creator_id: str = None,
                 status: str = "draft"):
        
        self.topic_id = ObjectId(topic_id)
        self.content_type = content_type
        self.title = title
        self.description = description
        self.content_data = content_data or {}
        self.interactive_config = interactive_config or {}
        self.template_id = ObjectId(template_id) if template_id else None
        self.learning_objectives = learning_objectives or []
        self.difficulty = difficulty
        self.estimated_duration = estimated_duration
        self.tags = tags or []
        self.resources = resources or []
        self.web_resources = web_resources or []
        self.generation_prompt = generation_prompt
        self.ai_credits = ai_credits
        self.creator_id = ObjectId(creator_id) if creator_id else None
        self.status = status
        self.created_at = datetime.now()
        self.updated_at = datetime.now()
        
        # Métricas de efectividad
        self.effectiveness_score = 0.0
        self.usage_count = 0
        self.avg_completion_rate = 0.0
        self.avg_satisfaction = 0.0

    def to_dict(self) -> Dict:
        result = {
            "topic_id": self.topic_id,
            "content_type": self.content_type,
            "title": self.title,
            "description": self.description,
            "content_data": self.content_data,
            "interactive_config": self.interactive_config,
            "learning_objectives": self.learning_objectives,
            "difficulty": self.difficulty,
            "estimated_duration": self.estimated_duration,
            "tags": self.tags,
            "resources": self.resources,
            "web_resources": self.web_resources,
            "generation_prompt": self.generation_prompt,
            "ai_credits": self.ai_credits,
            "status": self.status,
            "effectiveness_score": self.effectiveness_score,
            "usage_count": self.usage_count,
            "avg_completion_rate": self.avg_completion_rate,
            "avg_satisfaction": self.avg_satisfaction,
            "created_at": self.created_at,
            "updated_at": self.updated_at
        }
        
        if self.template_id:
            result["template_id"] = self.template_id
        if self.creator_id:
            result["creator_id"] = self.creator_id
            
        return result

class VirtualTopicContent:
    """
    Contenido personalizado para un estudiante específico.
    Unifica virtual_games, virtual_simulations, y contenido personalizado.
    """
    def __init__(self,
                 virtual_topic_id: str,
                 content_id: str,
                 student_id: str,
                 personalization_data: Dict = None,
                 adapted_content: Dict = None,  # Contenido modificado específicamente
                 interaction_tracking: Dict = None,
                 access_permissions: Dict = None,
                 status: str = "active"):
        
        self.virtual_topic_id = ObjectId(virtual_topic_id)
        self.content_id = ObjectId(content_id)
        self.student_id = ObjectId(student_id)
        self.personalization_data = personalization_data or {}
        self.adapted_content = adapted_content  # None = usar contenido original
        self.interaction_tracking = interaction_tracking or {
            "access_count": 0,
            "total_time_spent": 0,
            "last_accessed": None,
            "completion_status": "not_started",  # "not_started", "in_progress", "completed"
            "completion_percentage": 0.0,
            "sessions": 0,
            "best_score": None,
            "avg_score": None,
            "interactions": []
        }
        self.access_permissions = access_permissions or {}
        self.status = status
        self.created_at = datetime.now()
        self.updated_at = datetime.now()

    def to_dict(self) -> Dict:
        return {
            "virtual_topic_id": self.virtual_topic_id,
            "content_id": self.content_id,
            "student_id": self.student_id,
            "personalization_data": self.personalization_data,
            "adapted_content": self.adapted_content,
            "interaction_tracking": self.interaction_tracking,
            "access_permissions": self.access_permissions,
            "status": self.status,
            "created_at": self.created_at,
            "updated_at": self.updated_at
        }

class ContentResult:
    """
    Resultados unificados de interacción y evaluación.
    Reemplaza game_results, simulation_results, quiz_results, evaluation_results.
    """
    def __init__(self,
                 student_id: str,
                 virtual_content_id: Optional[str] = None,  # Para resultados de contenido
                 evaluation_id: Optional[str] = None,       # Para resultados de evaluación formal
                 session_data: Optional[Dict] = None,
                 learning_metrics: Optional[Dict] = None,
                 score: Optional[float] = None,
                 feedback: Optional[str] = None,
                 graded_by: Optional[str] = None,           # ID del profesor/evaluador
                 session_type: str = "completion"):  # "practice", "assessment", "exploration"
        
        if not virtual_content_id and not evaluation_id:
            raise ValueError("Se debe proporcionar virtual_content_id o evaluation_id")

        self.virtual_content_id = ObjectId(virtual_content_id) if virtual_content_id else None
        self.evaluation_id = ObjectId(evaluation_id) if evaluation_id else None
        self.student_id = ObjectId(student_id)
        self.session_data = session_data or {}
        self.learning_metrics = learning_metrics or {}
        self.score = score
        self.feedback = feedback
        self.graded_by = ObjectId(graded_by) if graded_by else None
        self.session_type = session_type
        self.created_at = datetime.now()

    def to_dict(self) -> Dict:
        return {
            "virtual_content_id": self.virtual_content_id,
            "evaluation_id": self.evaluation_id,
            "student_id": self.student_id,
            "session_data": self.session_data,
            "learning_metrics": self.learning_metrics,
            "score": self.score,
            "feedback": self.feedback,
            "graded_by": self.graded_by,
            "session_type": self.session_type,
            "created_at": self.created_at
        }

class ContentTemplate:
    """
    Plantillas parametrizables para contenido interactivo.
    Reemplaza game_templates y permite templates para cualquier tipo.
    """
    def __init__(self,
                 name: str,
                 content_type: str,
                 description: str,
                 template_code: str,  # HTML/JS/CSS template
                 parameter_schema: Dict,  # Definición de parámetros configurables
                 adaptation_rules: Dict = None,  # Reglas de adaptación por perfil cognitivo
                 default_config: Dict = None,
                 compatibility_matrix: Dict = None,
                 version: str = "1.0",
                 creator_id: str = None,
                 status: str = "active"):
        
        self.name = name
        self.content_type = content_type
        self.description = description
        self.template_code = template_code
        self.parameter_schema = parameter_schema
        self.adaptation_rules = adaptation_rules or {}
        self.default_config = default_config or {}
        self.compatibility_matrix = compatibility_matrix or {}
        self.version = version
        self.creator_id = ObjectId(creator_id) if creator_id else None
        self.status = status
        self.created_at = datetime.now()
        self.updated_at = datetime.now()
        
        # Métricas de uso
        self.usage_count = 0
        self.avg_effectiveness = 0.0

    def to_dict(self) -> Dict:
        result = {
            "name": self.name,
            "content_type": self.content_type,
            "description": self.description,
            "template_code": self.template_code,
            "parameter_schema": self.parameter_schema,
            "adaptation_rules": self.adaptation_rules,
            "default_config": self.default_config,
            "compatibility_matrix": self.compatibility_matrix,
            "version": self.version,
            "status": self.status,
            "usage_count": self.usage_count,
            "avg_effectiveness": self.avg_effectiveness,
            "created_at": self.created_at,
            "updated_at": self.updated_at
        }
        
        if self.creator_id:
            result["creator_id"] = self.creator_id
            
        return result 