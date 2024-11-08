from typing import Dict, List, Optional
import google.generativeai as genai
import os
from dotenv import load_dotenv
from datetime import datetime

# Cargar variables de entorno
load_dotenv()

# Configurar Gemini
genai.configure(api_key=os.getenv('GEMINI_API_KEY'))
model = genai.GenerativeModel('gemini-pro')

def generate_personalized_content(
    base_content: Dict,
    cognitive_profile: Dict,
    learning_objectives: Optional[List[str]] = None,
    difficulty_level: Optional[str] = None,
    preferred_learning_style: Optional[str] = None
) -> Dict:
    """
    Genera contenido personalizado basado en el perfil cognitivo del estudiante usando Gemini.
    
    Args:
        base_content: Contenido base del módulo virtual
        cognitive_profile: Perfil cognitivo del estudiante
        learning_objectives: Objetivos de aprendizaje específicos
        difficulty_level: Nivel de dificultad deseado
        preferred_learning_style: Estilo de aprendizaje preferido
    
    Returns:
        Dict: Contenido personalizado adaptado al estudiante
    """
    try:
        # Preparar el prompt para Gemini
        prompt = _prepare_personalization_prompt(
            base_content,
            cognitive_profile,
            learning_objectives,
            difficulty_level,
            preferred_learning_style
        )
        
        # Generar contenido personalizado usando Gemini
        response = model.generate_content(
            [
                "Eres un experto en educación adaptativa.",
                prompt
            ],
            generation_config=genai.types.GenerationConfig(
                temperature=0.7,
                max_output_tokens=2000,
                top_p=0.8,
                top_k=40
            )
        )
        
        # Procesar y estructurar la respuesta
        personalized_content = _process_ai_response(response.text)
        
        # Validar el contenido generado
        _validate_content(personalized_content)
        
        return personalized_content
        
    except Exception as e:
        raise Exception(f"Error al generar contenido personalizado: {str(e)}") 

def _prepare_personalization_prompt(
    base_content: Dict,
    cognitive_profile: Dict,
    learning_objectives: Optional[List[str]],
    difficulty_level: Optional[str],
    preferred_learning_style: Optional[str]
) -> str:
    """
    Prepara el prompt para Gemini combinando todos los parámetros de entrada.
    """
    prompt = f"""
    Contenido base: {base_content}
    Perfil cognitivo: {cognitive_profile}
    Objetivos de aprendizaje: {learning_objectives if learning_objectives else 'No especificados'}
    Nivel de dificultad: {difficulty_level if difficulty_level else 'No especificado'}
    Estilo de aprendizaje: {preferred_learning_style if preferred_learning_style else 'No especificado'}
    
    Por favor, adapta el contenido base considerando el perfil cognitivo del estudiante y los parámetros proporcionados.
    """
    return prompt

def _process_ai_response(response_text: str) -> Dict:
    """
    Procesa y estructura la respuesta del modelo AI.
    """
    # Aquí puedes agregar lógica más compleja según tus necesidades
    return {
        'content': response_text,
        'metadata': {
            'generated_timestamp': datetime.now().isoformat(),
            'model': 'gemini-pro'
        }
    }

def _validate_content(content: Dict) -> None:
    """
    Valida que el contenido generado cumpla con los requisitos mínimos.
    """
    if not content or 'content' not in content:
        raise ValueError("El contenido generado no tiene el formato esperado")
    
    if not isinstance(content['content'], str) or len(content['content']) < 10:
        raise ValueError("El contenido generado es demasiado corto o inválido")