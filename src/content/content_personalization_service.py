from typing import Dict, List, Union, Optional
import json
import re
import logging

logger = logging.getLogger(__name__)

class ContentPersonalizationService:
    """Servicio para personalizar contenido basado en preferencias y estilos de aprendizaje del estudiante"""
    
    # Patrones para identificar marcadores de personalización en el contenido
    VISUAL_MARKERS = [
        r'\b(?:imagen|gráfico|diagrama|visual|esquema|mapa|tabla|chart|graph|figure)\b',
        r'\b(?:ver|observar|mostrar|visualizar|display)\b',
        r'\b(?:color|forma|diseño|layout|interfaz)\b'
    ]
    
    AUDITORY_MARKERS = [
        r'\b(?:escuchar|audio|sonido|música|pronunciar|hablar)\b',
        r'\b(?:discutir|explicar|narrar|contar|relatar)\b',
        r'\b(?:ritmo|tono|volumen|melodía)\b'
    ]
    
    KINESTHETIC_MARKERS = [
        r'\b(?:práctica|ejercicio|actividad|hacer|construir|crear)\b',
        r'\b(?:mover|tocar|manipular|experimentar|probar)\b',
        r'\b(?:hands-on|interactivo|simulación|laboratorio)\b'
    ]
    
    READING_WRITING_MARKERS = [
        r'\b(?:leer|escribir|texto|documento|nota|apunte)\b',
        r'\b(?:lista|resumen|definición|concepto|teoría)\b',
        r'\b(?:análisis|reflexión|ensayo|reporte)\b'
    ]
    
    def __init__(self):
        self.personalization_strategies = {
            'visual': self._adaptar_para_visual,
            'auditory': self._adaptar_para_auditivo,
            'kinesthetic': self._adaptar_para_kinestesico,
            'reading_writing': self._adaptar_para_lectura_escritura
        }
    
    @staticmethod
    def extract_markers(content: Union[str, Dict]) -> Dict[str, List[str]]:
        """
        Extrae marcadores de personalización del contenido para identificar estilos de aprendizaje
        
        Args:
            content: Contenido a analizar (string o dict)
            
        Returns:
            Dict con marcadores encontrados por estilo de aprendizaje
        """
        try:
            # Convertir contenido a string si es necesario
            if isinstance(content, dict):
                content_str = json.dumps(content, ensure_ascii=False)
            else:
                content_str = str(content) if content else ""
            
            # Convertir a minúsculas para análisis
            content_lower = content_str.lower()
            
            markers = {
                'visual': [],
                'auditory': [],
                'kinesthetic': [],
                'reading_writing': []
            }
            
            # Buscar marcadores visuales
            for pattern in ContentPersonalizationService.VISUAL_MARKERS:
                matches = re.findall(pattern, content_lower, re.IGNORECASE)
                markers['visual'].extend(matches)
            
            # Buscar marcadores auditivos
            for pattern in ContentPersonalizationService.AUDITORY_MARKERS:
                matches = re.findall(pattern, content_lower, re.IGNORECASE)
                markers['auditory'].extend(matches)
            
            # Buscar marcadores kinestésicos
            for pattern in ContentPersonalizationService.KINESTHETIC_MARKERS:
                matches = re.findall(pattern, content_lower, re.IGNORECASE)
                markers['kinesthetic'].extend(matches)
            
            # Buscar marcadores de lectura/escritura
            for pattern in ContentPersonalizationService.READING_WRITING_MARKERS:
                matches = re.findall(pattern, content_lower, re.IGNORECASE)
                markers['reading_writing'].extend(matches)
            
            # Remover duplicados
            for style in markers:
                markers[style] = list(set(markers[style]))
            
            logger.debug(f"Marcadores extraídos: {markers}")
            return markers
            
        except Exception as e:
            logger.error(f"Error extrayendo marcadores de personalización: {str(e)}")
            return {
                'visual': [],
                'auditory': [],
                'kinesthetic': [],
                'reading_writing': []
            }
    
    def personalizar_contenido(self, contenido: str, estilo_aprendizaje: str, dificultad: str = None) -> str:
        """
        Personalizar contenido basado en estilo de aprendizaje y dificultad
        
        Args:
            contenido: Contenido original a personalizar
            estilo_aprendizaje: Estilo de aprendizaje preferido del estudiante
            dificultad: Nivel de dificultad del contenido
            
        Returns:
            Contenido personalizado como string
        """
        if estilo_aprendizaje not in self.personalization_strategies:
            logger.warning(f"Estilo de aprendizaje no reconocido: {estilo_aprendizaje}")
            return contenido
            
        estrategia = self.personalization_strategies[estilo_aprendizaje]
        personalizado = estrategia(contenido, dificultad)
        
        return personalizado
    
    def _adaptar_para_visual(self, contenido: str, dificultad: str = None) -> str:
        """Adaptar contenido para aprendices visuales"""
        adaptaciones = [
            "💡 Considera agregar diagramas o gráficos para ilustrar los conceptos",
            "🎨 Utiliza colores y elementos visuales para destacar información importante",
            "📊 Incluye tablas, mapas conceptuales o infografías cuando sea posible"
        ]
        
        if dificultad == "avanzado":
            adaptaciones.append("🔬 Agrega esquemas detallados y visualizaciones complejas")
        elif dificultad == "básico":
            adaptaciones.append("🎯 Usa imágenes simples y claras para explicar conceptos")
            
        return f"{contenido}\n\n[Adaptación Visual]\n" + "\n".join(adaptaciones)
    
    def _adaptar_para_auditivo(self, contenido: str, dificultad: str = None) -> str:
        """Adaptar contenido para aprendices auditivos"""
        adaptaciones = [
            "🎧 Considera grabar explicaciones en audio para este contenido",
            "💬 Incluye puntos de discusión y preguntas para debate",
            "🗣️ Agrega ejercicios de explicación verbal y presentaciones orales"
        ]
        
        if dificultad == "avanzado":
            adaptaciones.append("🎙️ Incluye debates complejos y análisis críticos verbales")
        elif dificultad == "básico":
            adaptaciones.append("📢 Usa repetición y ritmo para reforzar conceptos clave")
            
        return f"{contenido}\n\n[Adaptación Auditiva]\n" + "\n".join(adaptaciones)
    
    def _adaptar_para_kinestesico(self, contenido: str, dificultad: str = None) -> str:
        """Adaptar contenido para aprendices kinestésicos"""
        adaptaciones = [
            "🔧 Incluye actividades prácticas y ejercicios hands-on",
            "🎯 Agrega simulaciones y experimentos interactivos",
            "🏃‍♂️ Considera actividades que involucren movimiento físico"
        ]
        
        if dificultad == "avanzado":
            adaptaciones.append("⚗️ Diseña proyectos complejos y laboratorios avanzados")
        elif dificultad == "básico":
            adaptaciones.append("🎮 Usa juegos simples y manipulativos básicos")
            
        return f"{contenido}\n\n[Adaptación Kinestésica]\n" + "\n".join(adaptaciones)
    
    def _adaptar_para_lectura_escritura(self, contenido: str, dificultad: str = None) -> str:
        """Adaptar contenido para aprendices de lectura/escritura"""
        adaptaciones = [
            "📝 Incluye ejercicios de escritura y toma de notas estructurada",
            "📚 Agrega lecturas complementarias y referencias bibliográficas",
            "📋 Proporciona listas, resúmenes y definiciones claras"
        ]
        
        if dificultad == "avanzado":
            adaptaciones.append("📖 Incluye ensayos analíticos y reportes de investigación")
        elif dificultad == "básico":
            adaptaciones.append("✏️ Usa ejercicios de completar espacios y vocabulario")
            
        return f"{contenido}\n\n[Adaptación Lectura/Escritura]\n" + "\n".join(adaptaciones)