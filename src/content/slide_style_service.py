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
                              custom_colors: Optional[Dict] = None) -> Dict:
        """
        Genera un slide_template base con paleta de colores y estilos.
        
        Args:
            palette_name: Nombre de la paleta predefinida (opcional)
            font_family: Familia de fuente específica (opcional)
            custom_colors: Colores personalizados que sobrescriben la paleta (opcional)
            
        Returns:
            Dict con la estructura del slide_template
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
            
            # Generar template
            slide_template = {
                "background": colors["background"],
                "styles": {
                    "fontFamily": font_family,
                    "colors": {
                        "text": colors["textColor"],
                        "title": colors["titleColor"],
                        "accent": colors["accentColor"],
                        "secondary": colors["secondaryColor"]
                    },
                    "typography": {
                        "titleSize": "2.5rem",
                        "textSize": "1.2rem",
                        "lineHeight": "1.6",
                        "titleWeight": "bold",
                        "textWeight": "normal"
                    },
                    "layout": {
                        "padding": "2rem",
                        "margin": "1rem",
                        "borderRadius": "8px",
                        "boxShadow": "0 4px 6px rgba(0, 0, 0, 0.1)"
                    },
                    "animations": {
                        "fadeIn": True,
                        "slideTransition": "ease-in-out",
                        "duration": "0.3s"
                    }
                },
                "metadata": {
                    "paletteName": palette_name,
                    "generatedAt": datetime.now().isoformat(),
                    "version": "1.0"
                }
            }
            
            self.logger.info(f"Slide template generado con paleta '{palette_name}'")
            return slide_template
            
        except Exception as e:
            self.logger.error(f"Error generando slide template: {str(e)}")
            # Retornar template básico en caso de error
            return self._get_default_template()
    
    def _get_default_template(self) -> Dict:
        """
        Retorna un template por defecto en caso de error.
        """
        return {
            "background": "#FFFFFF",
            "styles": {
                "fontFamily": "Arial, sans-serif",
                "colors": {
                    "text": "#333333",
                    "title": "#1E3A8A",
                    "accent": "#DC2626",
                    "secondary": "#6B7280"
                },
                "typography": {
                    "titleSize": "2.5rem",
                    "textSize": "1.2rem",
                    "lineHeight": "1.6",
                    "titleWeight": "bold",
                    "textWeight": "normal"
                },
                "layout": {
                    "padding": "2rem",
                    "margin": "1rem",
                    "borderRadius": "8px",
                    "boxShadow": "0 4px 6px rgba(0, 0, 0, 0.1)"
                },
                "animations": {
                    "fadeIn": True,
                    "slideTransition": "ease-in-out",
                    "duration": "0.3s"
                }
            },
            "metadata": {
                "paletteName": "default",
                "generatedAt": datetime.now().isoformat(),
                "version": "1.0"
            }
        }
    
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
    
    def validate_slide_template(self, slide_template: Dict) -> bool:
        """
        Valida que un slide_template tenga la estructura requerida.
        
        Args:
            slide_template: Template a validar
            
        Returns:
            bool: True si es válido, False en caso contrario
        """
        try:
            # Campos obligatorios según la validación existente
            required_fields = ["background", "styles"]
            
            for field in required_fields:
                if field not in slide_template:
                    self.logger.warning(f"Campo requerido '{field}' faltante en slide_template")
                    return False
            
            # Validar estructura de styles si existe
            if "styles" in slide_template:
                styles = slide_template["styles"]
                if not isinstance(styles, dict):
                    self.logger.warning("El campo 'styles' debe ser un diccionario")
                    return False
            
            return True
            
        except Exception as e:
            self.logger.error(f"Error validando slide_template: {str(e)}")
            return False