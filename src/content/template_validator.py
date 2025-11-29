"""
TemplateValidator - Validador de artefactos HTML para templates interactivos.

Valida que los templates interactivos tengan la capacidad de reportar
resultados al sistema padre (postMessage o sapiensReportResult).
"""

import re
import logging
from typing import Tuple, List, Optional, Dict, Any


class TemplateValidator:
    """
    Validador de HTML para templates interactivos.
    Verifica que el HTML tenga capacidad de reporte de resultados.
    """

    # Patrones requeridos para capacidad de reporte
    REQUIRED_REPORT_PATTERNS = [
        r'sapiensReportResult',
        r'postMessage\s*\(\s*\{[^}]*type\s*:\s*[\'"]sapiens:template_result[\'"]',
        r'postMessage\s*\(\s*\{[^}]*[\'"]sapiens:template_result[\'"]',
        r'window\.parent\.postMessage',
        r'parent\.postMessage',
    ]

    # Patrones alternativos que también son válidos
    ALTERNATIVE_REPORT_PATTERNS = [
        r'Reporting\.sendReport',
        r'sendReport\s*\(',
        r'reportResult\s*\(',
        r'submitScore\s*\(',
    ]

    # Patrones de estructura básica requerida
    REQUIRED_STRUCTURE_PATTERNS = [
        (r'<!DOCTYPE\s+html', 'DOCTYPE declaration'),
        (r'<html', 'HTML tag'),
        (r'<script', 'Script tag'),
    ]

    # Patrones de riesgo que deberían generar advertencias
    WARNING_PATTERNS = [
        (r'eval\s*\(', 'Uso de eval() detectado'),
        (r'document\.write', 'Uso de document.write detectado'),
        (r'innerHTML\s*=\s*[^"\']*\+', 'Posible XSS con innerHTML'),
    ]

    def __init__(self):
        self.logger = logging.getLogger(__name__)

    def validate_reporting_capability(self, html: str) -> Tuple[bool, List[str]]:
        """
        Verifica que el HTML tenga capacidad de reporte de resultados.
        
        Args:
            html: Contenido HTML del template
            
        Returns:
            Tuple[bool, List[str]]: (es_valido, lista_de_errores)
        """
        errors: List[str] = []
        
        if not html or not html.strip():
            errors.append("El HTML del template está vacío")
            return False, errors

        # Verificar patrones principales de reporte
        has_report = False
        for pattern in self.REQUIRED_REPORT_PATTERNS:
            if re.search(pattern, html, re.IGNORECASE):
                has_report = True
                break

        # Si no hay patrón principal, verificar alternativos
        if not has_report:
            for pattern in self.ALTERNATIVE_REPORT_PATTERNS:
                if re.search(pattern, html, re.IGNORECASE):
                    has_report = True
                    break

        if not has_report:
            errors.append(
                "El template no implementa sistema de reporte de resultados. "
                "Debe incluir llamada a sapiensReportResult() o postMessage con type 'sapiens:template_result'"
            )

        return len(errors) == 0, errors

    def validate_structure(self, html: str) -> Tuple[bool, List[str]]:
        """
        Verifica que el HTML tenga la estructura básica requerida.
        
        Args:
            html: Contenido HTML del template
            
        Returns:
            Tuple[bool, List[str]]: (es_valido, lista_de_errores)
        """
        errors: List[str] = []
        
        if not html or not html.strip():
            errors.append("El HTML del template está vacío")
            return False, errors

        for pattern, name in self.REQUIRED_STRUCTURE_PATTERNS:
            if not re.search(pattern, html, re.IGNORECASE):
                errors.append(f"Falta elemento requerido: {name}")

        return len(errors) == 0, errors

    def check_warnings(self, html: str) -> List[str]:
        """
        Verifica patrones de riesgo en el HTML.
        
        Args:
            html: Contenido HTML del template
            
        Returns:
            List[str]: Lista de advertencias
        """
        warnings: List[str] = []
        
        if not html:
            return warnings

        for pattern, message in self.WARNING_PATTERNS:
            if re.search(pattern, html, re.IGNORECASE):
                warnings.append(message)

        return warnings

    def validate_interactive_template(self, html: str) -> Dict[str, Any]:
        """
        Validación completa de un template interactivo.
        
        Args:
            html: Contenido HTML del template
            
        Returns:
            Dict con is_valid, errors, warnings, y has_reporting
        """
        # Validar estructura
        structure_valid, structure_errors = self.validate_structure(html)
        
        # Validar capacidad de reporte
        reporting_valid, reporting_errors = self.validate_reporting_capability(html)
        
        # Verificar advertencias
        warnings = self.check_warnings(html)
        
        # Combinar errores
        all_errors = structure_errors + reporting_errors
        
        result = {
            "is_valid": len(all_errors) == 0,
            "has_reporting": reporting_valid,
            "has_valid_structure": structure_valid,
            "errors": all_errors,
            "warnings": warnings,
        }
        
        if not result["is_valid"]:
            self.logger.warning(f"Template validation failed: {all_errors}")
        
        return result

    def extract_reporting_method(self, html: str) -> Optional[str]:
        """
        Extrae el método de reporte utilizado en el template.
        
        Args:
            html: Contenido HTML del template
            
        Returns:
            str o None: Nombre del método de reporte encontrado
        """
        if not html:
            return None

        if re.search(r'sapiensReportResult', html, re.IGNORECASE):
            return 'sapiensReportResult'
        
        if re.search(r'Reporting\.sendReport', html, re.IGNORECASE):
            return 'Reporting.sendReport'
        
        if re.search(r'postMessage.*sapiens:template_result', html, re.IGNORECASE | re.DOTALL):
            return 'postMessage'
        
        if re.search(r'window\.parent\.postMessage', html, re.IGNORECASE):
            return 'postMessage (parent)'
        
        return None


# Instancia global del validador
template_validator = TemplateValidator()


def validate_template_html(html: str) -> Dict[str, Any]:
    """
    Función de conveniencia para validar HTML de templates.
    
    Args:
        html: Contenido HTML del template
        
    Returns:
        Dict con resultados de validación
    """
    return template_validator.validate_interactive_template(html)
