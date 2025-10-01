"""
Módulo de contenido unificado para SapiensAI.

Este módulo unifica la gestión de todos los tipos de contenido:
- Contenido estático: diagramas, textos, videos, etc.
- Contenido interactivo: juegos, simulaciones, quizzes, etc.
- Contenido inmersivo: realidad aumentada, laboratorios virtuales, etc.

Reemplaza los módulos separados de games, simulations, y quizzes,
proporcionando una API unificada y consistente.
"""

from .models import ContentType, TopicContent, VirtualTopicContent, ContentResult
from .services import ContentService, ContentTypeService
from .routes import content_bp

__all__ = [
    'ContentType',
    'TopicContent', 
    'VirtualTopicContent',
    'ContentResult',
    'ContentService',
    'ContentTypeService',
    'content_bp'
]