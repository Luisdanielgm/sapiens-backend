"""
TemplateValidator - Validador de artefactos HTML para templates interactivos.

Valida que los templates interactivos tengan la capacidad de reportar
resultados al sistema padre (postMessage o sapiensReportResult).

Protocolo de reporte requerido:
- contentId o virtualContentId (identificador del contenido)
- score (0-100, normalizado)
- timeSpent o duration (tiempo en milisegundos)
- completionPercentage (0-100)
- Opcionales: learningOutcomes, difficultyRating, satisfactionRating, comments, sessionData
"""

import re
import logging
from typing import Tuple, List, Optional, Dict, Any
from dataclasses import dataclass, field


@dataclass
class ValidationResult:
    """Resultado detallado de validación de un template."""
    is_valid: bool
    has_reporting: bool
    has_valid_structure: bool
    reporting_method: Optional[str] = None
    payload_fields: List[str] = field(default_factory=list)
    missing_required_fields: List[str] = field(default_factory=list)
    errors: List[str] = field(default_factory=list)
    warnings: List[str] = field(default_factory=list)
    suggestions: List[str] = field(default_factory=list)
    
    def to_dict(self) -> Dict[str, Any]:
        return {
            "is_valid": self.is_valid,
            "has_reporting": self.has_reporting,
            "has_valid_structure": self.has_valid_structure,
            "reporting_method": self.reporting_method,
            "payload_fields": self.payload_fields,
            "missing_required_fields": self.missing_required_fields,
            "errors": self.errors,
            "warnings": self.warnings,
            "suggestions": self.suggestions,
        }


class TemplateValidator:
    """
    Validador de HTML para templates interactivos.
    Verifica que el HTML tenga capacidad de reporte de resultados completo.
    """

    # Campos requeridos en el payload de reporte
    REQUIRED_PAYLOAD_FIELDS = [
        'contentId',           # Puede ser contentId, virtualContentId, variantContentId
        'score',               # Puntuación (0-100 o 0-1)
    ]
    
    # Campos opcionales pero recomendados
    RECOMMENDED_PAYLOAD_FIELDS = [
        'timeSpent',           # Tiempo en ms
        'completionPercentage', # Porcentaje completado
        'duration',            # Alternativa a timeSpent
    ]
    
    # Campos opcionales adicionales
    OPTIONAL_PAYLOAD_FIELDS = [
        'learningOutcomes',
        'difficultyRating',
        'satisfactionRating',
        'comments',
        'sessionData',
        'templateUsageId',
        'parentContentId',
        'variantContentId',
    ]

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
    
    # Patrones para detectar campos del payload
    PAYLOAD_FIELD_PATTERNS = {
        'contentId': [
            r'contentId\s*[=:]\s*',
            r'content_id\s*[=:]\s*',
            r'virtualContentId\s*[=:]\s*',
            r'virtual_content_id\s*[=:]\s*',
        ],
        'score': [
            r'score\s*[=:]\s*',
            r'puntuacion\s*[=:]\s*',
            r'resultado\s*[=:]\s*',
        ],
        'timeSpent': [
            r'timeSpent\s*[=:]\s*',
            r'time_spent\s*[=:]\s*',
            r'duration\s*[=:]\s*',
            r'tiempo\s*[=:]\s*',
        ],
        'completionPercentage': [
            r'completionPercentage\s*[=:]\s*',
            r'completion_percentage\s*[=:]\s*',
            r'porcentaje\s*[=:]\s*',
            r'progress\s*[=:]\s*',
        ],
        'learningOutcomes': [
            r'learningOutcomes\s*[=:]\s*',
            r'learning_outcomes\s*[=:]\s*',
        ],
        'difficultyRating': [
            r'difficultyRating\s*[=:]\s*',
            r'difficulty_rating\s*[=:]\s*',
            r'dificultad\s*[=:]\s*',
        ],
        'satisfactionRating': [
            r'satisfactionRating\s*[=:]\s*',
            r'satisfaction_rating\s*[=:]\s*',
            r'satisfaccion\s*[=:]\s*',
        ],
        'templateUsageId': [
            r'templateUsageId\s*[=:]\s*',
            r'template_usage_id\s*[=:]\s*',
        ],
        'variantContentId': [
            r'variantContentId\s*[=:]\s*',
            r'variant_content_id\s*[=:]\s*',
        ],
        'parentContentId': [
            r'parentContentId\s*[=:]\s*',
            r'parent_content_id\s*[=:]\s*',
        ],
        'sessionData': [
            r'sessionData\s*[=:]\s*',
            r'session_data\s*[=:]\s*',
        ],
    }

    def __init__(self):
        self.logger = logging.getLogger(__name__)

    def detect_payload_fields(self, html: str) -> Tuple[List[str], List[str]]:
        """
        Detecta qué campos del payload están presentes en el código HTML.
        
        Args:
            html: Contenido HTML del template
            
        Returns:
            Tuple[List[str], List[str]]: (campos_encontrados, campos_requeridos_faltantes)
        """
        found_fields: List[str] = []
        
        if not html:
            return found_fields, self.REQUIRED_PAYLOAD_FIELDS.copy()
        
        for field_name, patterns in self.PAYLOAD_FIELD_PATTERNS.items():
            for pattern in patterns:
                if re.search(pattern, html, re.IGNORECASE):
                    if field_name not in found_fields:
                        found_fields.append(field_name)
                    break
        
        # Verificar campos requeridos faltantes
        missing_required = []
        for required_field in self.REQUIRED_PAYLOAD_FIELDS:
            if required_field not in found_fields:
                # Verificar si hay alguna variante del campo
                field_variants = {
                    'contentId': ['contentId', 'virtualContentId', 'variantContentId'],
                    'score': ['score'],
                }
                variants = field_variants.get(required_field, [required_field])
                if not any(v in found_fields for v in variants):
                    missing_required.append(required_field)
        
        return found_fields, missing_required

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

    def validate_interactive_template(self, html: str, strict: bool = False) -> Dict[str, Any]:
        """
        Validación completa de un template interactivo.
        
        Args:
            html: Contenido HTML del template
            strict: Si es True, los campos recomendados también son obligatorios
            
        Returns:
            Dict con is_valid, errors, warnings, y has_reporting
        """
        # Validar estructura
        structure_valid, structure_errors = self.validate_structure(html)
        
        # Validar capacidad de reporte
        reporting_valid, reporting_errors = self.validate_reporting_capability(html)
        
        # Detectar campos del payload
        payload_fields, missing_required = self.detect_payload_fields(html)
        
        # Extraer método de reporte
        reporting_method = self.extract_reporting_method(html)
        
        # Verificar advertencias
        warnings = self.check_warnings(html)
        
        # Generar sugerencias
        suggestions = self._generate_suggestions(html, payload_fields, missing_required, reporting_valid)
        
        # Agregar errores de campos faltantes
        payload_errors = []
        if reporting_valid and missing_required:
            for field in missing_required:
                if strict or field in self.REQUIRED_PAYLOAD_FIELDS:
                    payload_errors.append(
                        f"Campo requerido '{field}' no encontrado en el payload de reporte"
                    )
        
        # En modo estricto, verificar campos recomendados
        if strict and reporting_valid:
            for rec_field in self.RECOMMENDED_PAYLOAD_FIELDS:
                if rec_field not in payload_fields:
                    warnings.append(
                        f"Campo recomendado '{rec_field}' no encontrado en el payload"
                    )
        
        # Combinar errores
        all_errors = structure_errors + reporting_errors + payload_errors
        
        result = ValidationResult(
            is_valid=len(all_errors) == 0,
            has_reporting=reporting_valid,
            has_valid_structure=structure_valid,
            reporting_method=reporting_method,
            payload_fields=payload_fields,
            missing_required_fields=missing_required,
            errors=all_errors,
            warnings=warnings,
            suggestions=suggestions,
        )
        
        if not result.is_valid:
            self.logger.warning(f"Template validation failed: {all_errors}")
        
        return result.to_dict()
    
    def _generate_suggestions(
        self, 
        html: str, 
        payload_fields: List[str], 
        missing_required: List[str],
        has_reporting: bool
    ) -> List[str]:
        """
        Genera sugerencias para mejorar el template.
        
        Args:
            html: Contenido HTML del template
            payload_fields: Campos encontrados en el payload
            missing_required: Campos requeridos que faltan
            has_reporting: Si tiene capacidad de reporte
            
        Returns:
            List[str]: Lista de sugerencias
        """
        suggestions = []
        
        if not has_reporting:
            suggestions.append(
                "Agrega una llamada a window.parent.sapiensReportResult({...}) o "
                "window.parent.postMessage({ type: 'sapiens:template_result', payload: {...} }, '*') "
                "para reportar resultados al sistema."
            )
            suggestions.append(
                "Ejemplo mínimo:\n"
                "window.parent.sapiensReportResult({\n"
                "  contentId: window.__sapiensTemplateContext?.virtualContentId,\n"
                "  score: 85,\n"
                "  timeSpent: Date.now() - startTime,\n"
                "  completionPercentage: 100\n"
                "});"
            )
        else:
            # Sugerencias de campos faltantes
            if 'contentId' in missing_required:
                suggestions.append(
                    "Incluye 'contentId' usando window.__sapiensTemplateContext?.virtualContentId "
                    "para identificar el contenido."
                )
            
            if 'score' in missing_required:
                suggestions.append(
                    "Incluye 'score' (0-100) para que el sistema pueda trackear el rendimiento del estudiante."
                )
            
            if 'timeSpent' not in payload_fields and 'duration' not in payload_fields:
                suggestions.append(
                    "Considera agregar 'timeSpent' (en milisegundos) para analytics de tiempo."
                )
            
            if 'completionPercentage' not in payload_fields:
                suggestions.append(
                    "Considera agregar 'completionPercentage' (0-100) para tracking de progreso."
                )
        
        # Verificar si usa el contexto del sistema
        if has_reporting and not re.search(r'__sapiensTemplateContext', html, re.IGNORECASE):
            suggestions.append(
                "Considera usar window.__sapiensTemplateContext para obtener IDs del contexto actual "
                "(virtualContentId, templateUsageId, contentId)."
            )
        
        # Verificar si captura tiempo de inicio
        if has_reporting and not re.search(r'startTime|tiempoInicio|Date\.now\(\)', html, re.IGNORECASE):
            suggestions.append(
                "Considera capturar el tiempo de inicio (const startTime = Date.now()) "
                "para calcular timeSpent al reportar."
            )
        
        return suggestions

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


def validate_template_html(html: str, strict: bool = False) -> Dict[str, Any]:
    """
    Función de conveniencia para validar HTML de templates.
    
    Args:
        html: Contenido HTML del template
        strict: Si es True, también verifica campos recomendados
        
    Returns:
        Dict con resultados de validación completos
    """
    return template_validator.validate_interactive_template(html, strict=strict)


def validate_template_reporting_compliance(html: str) -> Dict[str, Any]:
    """
    Validación específica para cumplimiento del sistema de reporte.
    Útil para verificar que un artefacto pueda comunicarse con el sistema padre.
    
    Args:
        html: Contenido HTML del template
        
    Returns:
        Dict con:
        - compliant: bool - Si cumple con el protocolo de reporte
        - reporting_method: str - Método de reporte detectado
        - payload_fields: List[str] - Campos encontrados en el payload
        - missing_fields: List[str] - Campos requeridos faltantes
        - compliance_score: float - Score de cumplimiento (0-1)
        - details: Dict - Detalles adicionales
    """
    result = template_validator.validate_interactive_template(html, strict=True)
    
    # Calcular score de cumplimiento
    total_fields = len(TemplateValidator.REQUIRED_PAYLOAD_FIELDS) + len(TemplateValidator.RECOMMENDED_PAYLOAD_FIELDS)
    found_fields = len(result.get('payload_fields', []))
    missing_required = len(result.get('missing_required_fields', []))
    
    # Score base: 50% por tener reporte, 50% por campos
    base_score = 0.5 if result.get('has_reporting', False) else 0
    field_score = (found_fields / total_fields) * 0.5 if total_fields > 0 else 0
    
    # Penalizar por campos requeridos faltantes
    penalty = (missing_required * 0.15)
    
    compliance_score = max(0, min(1, base_score + field_score - penalty))
    
    return {
        "compliant": result.get('has_reporting', False) and missing_required == 0,
        "reporting_method": result.get('reporting_method'),
        "payload_fields": result.get('payload_fields', []),
        "missing_fields": result.get('missing_required_fields', []),
        "compliance_score": round(compliance_score, 2),
        "details": {
            "has_valid_structure": result.get('has_valid_structure', False),
            "errors": result.get('errors', []),
            "warnings": result.get('warnings', []),
            "suggestions": result.get('suggestions', []),
        }
    }
