from pydantic import BaseModel, Field
from bson import ObjectId
from typing import Optional, List, Dict
from datetime import datetime

class CorrectionTask(BaseModel):
    """
    Modelo para gestionar una tarea de corrección automática de exámenes.
    Orquesta el proceso desde la solicitud hasta la obtención del resultado.
    """
    id: ObjectId = Field(default_factory=ObjectId, alias="_id")
    
    # --- IDs de Referencia ---
    evaluation_id: ObjectId
    submission_resource_id: ObjectId # El archivo subido por el estudiante
    rubric_resource_id: Optional[ObjectId] = None # La rúbrica o guía del profesor
    teacher_id: ObjectId # El profesor que inicia la corrección
    
    # --- Estado de la Tarea ---
    status: str = "pending" # pending, ocr_processing, llm_processing, completed, failed
    created_at: datetime = Field(default_factory=datetime.now)
    updated_at: datetime = Field(default_factory=datetime.now)
    
    # --- Proceso y Resultados ---
    ocr_extracted_text: Optional[str] = None # Texto extraído del examen
    llm_prompt: Optional[str] = None # El prompt final enviado al LLM
    
    suggested_grade: Optional[float] = None # Nota sugerida por la IA (0-100)
    feedback: Optional[str] = None # Feedback detallado generado por la IA
    cost: Optional[float] = None # Costo de la operación de IA
    
    # --- Manejo de Errores ---
    error_message: Optional[str] = None
    attempts: int = 0

    class Config:
        arbitrary_types_allowed = True
        json_encoders = {ObjectId: str}

    def to_db(self) -> Dict:
        """Convierte el modelo a un diccionario para MongoDB."""
        data = self.model_dump(by_alias=True)
        # Asegurarse de que los campos opcionales no se guarden si son None
        return {k: v for k, v in data.items() if v is not None}
