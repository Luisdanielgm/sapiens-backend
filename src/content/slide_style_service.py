import logging
import random
from typing import Dict, List, Optional
from datetime import datetime

class SlideStyleService:
    """
    Servicio para generar estilos de diapositivas con paletas de colores predefinidas.
    Genera slide_template base para contenidos de tipo 'slide'.
    """
    
    # Paletas de colores predefinidas
    COLOR_PALETTES = {
        "professional": {
            "background": "#2C3E50",
            "textColor": "#FFFFFF",
            "titleColor": "#3498DB",
            "accentColor": "#E74C3C",
            "secondaryColor": "#95A5A6"
        },
        "warm": {
            "background": "#FFA500",
            "textColor": "#000000",
            "titleColor": "#FFFFFF",
            "accentColor": "#FF6347",
            "secondaryColor": "#FFE4B5"
        },
        "cool": {
            "background": "#4A90E2",
            "textColor": "#FFFFFF",
            "titleColor": "#F5F5F5",
            "accentColor": "#7ED321",
            "secondaryColor": "#B8E6B8"
        },
        "elegant": {
            "background": "#1A1A1A",
            "textColor": "#F0F0F0",
            "titleColor": "#D4AF37",
            "accentColor": "#C0C0C0",
            "secondaryColor": "#696969"
        },
        "nature": {
            "background": "#228B22",
            "textColor": "#FFFFFF",
            "titleColor": "#ADFF2F",
            "accentColor": "#32CD32",
            "secondaryColor": "#98FB98"
        },
        "academic": {
            "background": "#FFFFFF",
            "textColor": "#333333",
            "titleColor": "#1E3A8A",
            "accentColor": "#DC2626",
            "secondaryColor": "#6B7280"
        }
    }
    
    # Familias de fuentes disponibles
    FONT_FAMILIES = [
        "Arial, sans-serif",
        "Helvetica, sans-serif",
        "Georgia, serif",
        "Times New Roman, serif",
        "Verdana, sans-serif",
        "Trebuchet MS, sans-serif",
        "Calibri, sans-serif"
    ]
    
    def __init__(self):
        self.logger = logging.getLogger(__name__)
    
    def generate_slide_template(self, 
                              palette_name: Optional[str] = None,
                              font_family: Optional[str] = None,
                              custom_colors: Optional[Dict] = None) -> str:
        """
        Genera un prompt para slide_template con especificaciones de diseño.
        
        Args:
            palette_name: Nombre de la paleta predefinida (opcional)
            font_family: Familia de fuente específica (opcional)
            custom_colors: Colores personalizados que sobrescriben la paleta (opcional)
            
        Returns:
            String con el prompt para generar la plantilla de diapositiva
        """
        try:
            # Seleccionar paleta
            if palette_name and palette_name in self.COLOR_PALETTES:
                colors = self.COLOR_PALETTES[palette_name].copy()
            else:
                # Seleccionar paleta aleatoria si no se especifica
                palette_name = random.choice(list(self.COLOR_PALETTES.keys()))
                colors = self.COLOR_PALETTES[palette_name].copy()
            
            # Aplicar colores personalizados si se proporcionan
            if custom_colors:
                colors.update(custom_colors)
            
            # Seleccionar fuente
            if not font_family:
                font_family = random.choice(self.FONT_FAMILIES)
            
            # Generar prompt para slide template
            slide_template_prompt = f"""Crea una diapositiva educativa con las siguientes especificaciones de diseño:

PALETA DE COLORES ({palette_name}):
- Fondo: {colors["background"]}
- Texto principal: {colors["textColor"]}
- Títulos: {colors["titleColor"]}
- Color de acento: {colors["accentColor"]}
- Color secundario: {colors["secondaryColor"]}

TIPOGRAFÍA:
- Familia de fuente: {font_family}
- Tamaño de título: 2.5rem (peso: bold)
- Tamaño de texto: 1.2rem (peso: normal)
- Altura de línea: 1.6

DISEÑO Y LAYOUT:
- Padding: 2rem
- Margen: 1rem
- Bordes redondeados: 8px
- Sombra: sutil (0 4px 6px rgba(0, 0, 0, 0.1))

ANIMACIONES:
- Transición de entrada: fade-in
- Transición entre slides: ease-in-out
- Duración: 0.3s

La diapositiva debe ser visualmente atractiva, educativa y seguir principios de diseño moderno. Asegúrate de que el contraste sea adecuado para la legibilidad."""
            
            self.logger.info(f"Slide template prompt generado con paleta '{palette_name}'")
            return slide_template_prompt
            
        except Exception as e:
            self.logger.error(f"Error generando slide template prompt: {str(e)}")
            # Retornar prompt básico en caso de error
            return self._get_default_template()
    
    def _get_default_template(self) -> str:
        """
        Retorna un prompt de template por defecto en caso de error.
        """
        return """Crea una diapositiva educativa con las siguientes especificaciones de diseño:

PALETA DE COLORES (académica):
- Fondo: #FFFFFF
- Texto principal: #333333
- Títulos: #1E3A8A
- Color de acento: #DC2626
- Color secundario: #6B7280

TIPOGRAFÍA:
- Familia de fuente: Arial, sans-serif
- Tamaño de título: 2.5rem (peso: bold)
- Tamaño de texto: 1.2rem (peso: normal)
- Altura de línea: 1.6

DISEÑO Y LAYOUT:
- Padding: 2rem
- Margen: 1rem
- Bordes redondeados: 8px
- Sombra: sutil (0 4px 6px rgba(0, 0, 0, 0.1))

ANIMACIONES:
- Transición de entrada: fade-in
- Transición entre slides: ease-in-out
- Duración: 0.3s

La diapositiva debe ser visualmente atractiva, educativa y seguir principios de diseño moderno. Asegúrate de que el contraste sea adecuado para la legibilidad."""
    
    def get_available_palettes(self) -> List[str]:
        """
        Retorna la lista de paletas disponibles.
        """
        return list(self.COLOR_PALETTES.keys())
    
    def get_palette_preview(self, palette_name: str) -> Optional[Dict]:
        """
        Retorna una vista previa de una paleta específica.
        
        Args:
            palette_name: Nombre de la paleta
            
        Returns:
            Dict con los colores de la paleta o None si no existe
        """
        return self.COLOR_PALETTES.get(palette_name)
    
    def validate_slide_template(self, slide_template: str) -> bool:
        """
        Valida que un slide_template sea un string válido para usar como prompt de IA.
        
        Args:
            slide_template: String con el prompt para generar la plantilla
            
        Returns:
            bool: True si es válido, False en caso contrario
        """
        try:
            # Validar que sea un string no vacío
            if not isinstance(slide_template, str):
                self.logger.warning("El slide_template debe ser un string")
                return False
            
            # Validar que no esté vacío (después de quitar espacios)
            if not slide_template.strip():
                self.logger.warning("El slide_template no puede estar vacío")
                return False
            
            # Validar longitud mínima y máxima razonable para un prompt
            if len(slide_template.strip()) < 10:
                self.logger.warning("El slide_template es demasiado corto (mínimo 10 caracteres)")
                return False
                
            if len(slide_template) > 5000:
                self.logger.warning("El slide_template es demasiado largo (máximo 5000 caracteres)")
                return False
            
            return True
            
        except Exception as e:
            self.logger.error(f"Error validando slide_template: {str(e)}")
            return False