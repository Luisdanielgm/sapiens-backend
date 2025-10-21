import logging
import random
from typing import Dict, List, Optional
from datetime import datetime

class SlideStyleService:
    """
    Servicio para generar estilos de diapositivas con paletas de colores predefinidas.
    Proporciona paletas de colores y configuraciones de estilo para diapositivas.
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