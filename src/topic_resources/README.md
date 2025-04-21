# Topic Resources API

Este módulo implementa un dominio dedicado para la gestión de vinculaciones entre recursos educativos y topics (temas). 

## Propósito

Separar la lógica de vinculación recurso-topic en su propio dominio para:

1. **Mejorar la organización del código**: Cada dominio tiene responsabilidades claras
2. **Mantener rutas consistentes**: Las URLs siguen la documentación `/api/topic-resources/`
3. **Evitar duplicación**: Un solo lugar para toda la lógica de vinculación
4. **Facilitar mantenimiento**: Los cambios en este dominio no afectan a otros módulos

## Estructura

```
src/topic_resources/
  ├── __init__.py      - Inicialización del blueprint
  ├── models.py        - Modelo TopicResource 
  ├── services.py      - Implementación de TopicResourceService
  └── routes.py        - Endpoints de la API
```

## Rutas API

### Vincular recurso a topic
```
POST /api/topic-resources/<topic_id>/<resource_id>
```
Crea o actualiza la vinculación entre un topic y un recurso.

**Payload:**
```json
{
  "relevance_score": 0.8,
  "recommended_for": ["visual", "adhd_adapted"],
  "usage_context": "supplementary",
  "content_types": ["text", "diagram"]
}
```

### Desvincular recurso de topic
```
DELETE /api/topic-resources/<topic_id>/<resource_id>
```
Elimina completamente la vinculación entre el recurso y el topic. Esta operación no afecta al recurso en sí, sólo elimina la relación.

### Obtener recursos de un topic
```
GET /api/topic-resources/<topic_id>
```
Obtiene todos los recursos vinculados a un topic específico.

**Parámetros de consulta:**
- `personalized=true` - Personaliza resultados según perfil cognitivo del usuario
- `content_type` - Filtra por tipo de contenido
- `usage_context` - Filtra por contexto de uso

### Obtener topics de un recurso
```
GET /api/topic-resources/by-resource/<resource_id>
```
Obtiene todos los topics vinculados a un recurso específico.

## Compatibilidad con código existente

Se mantienen las rutas antiguas en `/api/study-plan/topic-resources/` temporalmente, redirigiendo a esta nueva implementación para asegurar compatibilidad con el frontend existente.

## Uso en otros servicios

Este módulo es utilizado por:

1. `TopicService` - Para vincular recursos durante la creación de topics
2. `DELETE /topic` - Para gestionar la eliminación condicionada de recursos huérfanos 