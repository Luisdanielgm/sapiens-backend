"""
Módulo de Personalización Adaptativa

Este módulo implementa el sistema de recomendaciones inteligentes basado en:
- Modelo de Aprendizaje por Refuerzo (RL) externo
- Análisis estadístico V-A-K-R
- Perfiles cognitivos del estudiante
- Historial de interacciones

Endpoints principales:
- /api/personalization/adaptive - Recomendaciones adaptativas
- /api/personalization/analytics - Estadísticas V-A-K-R
"""

from .services import AdaptivePersonalizationService

__all__ = ['AdaptivePersonalizationService', 'personalization_bp']
