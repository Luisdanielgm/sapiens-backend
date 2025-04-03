"""
Modelos para el módulo de investigación profunda (deep research)
"""
from datetime import datetime
from typing import List, Dict, Optional, Any
from bson import ObjectId

class DeepResearchSession:
    """
    Representa una sesión de investigación profunda.
    Almacena el estado de la investigación incluyendo el plan, consultas, resultados, etc.
    """
    def __init__(self,
                user_id: str,
                topic: str,
                format_requirements: Optional[str] = None,
                research_plan: Optional[str] = None,
                structured_queries: Optional[List[str]] = None,
                final_report: Optional[str] = None,
                status: str = "iniciado",
                topic_id: Optional[str] = None):
        
        self.user_id = ObjectId(user_id)
        self.topic = topic
        self.format_requirements = format_requirements
        self.research_plan = research_plan
        self.structured_queries = structured_queries or []
        self.final_report = final_report
        self.status = status  # iniciado, en_progreso, completado, fallido
        self.topic_id = ObjectId(topic_id) if topic_id else None
        self.created_at = datetime.now()
        self.updated_at = datetime.now()
        
    def to_dict(self) -> Dict[str, Any]:
        """Convierte el objeto a un diccionario para almacenamiento en MongoDB"""
        return {
            "user_id": self.user_id,
            "topic": self.topic,
            "format_requirements": self.format_requirements,
            "research_plan": self.research_plan,
            "structured_queries": self.structured_queries,
            "final_report": self.final_report,
            "status": self.status,
            "topic_id": self.topic_id,
            "created_at": self.created_at,
            "updated_at": self.updated_at
        } 