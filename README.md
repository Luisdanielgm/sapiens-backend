# SapiensAI Backend

Backend para la plataforma educativa SapiensAI, desarrollada con Flask y MongoDB para gestionar institutos educativos, clases, estudiantes y contenido personalizado.

## Mejoras Recientes

Se han realizado las siguientes mejoras para optimizar el funcionamiento y mantenibilidad del backend:

1. **Sistema de Logging Centralizado**:
   - Se ha implementado un sistema de logging centralizado en `src/shared/logging.py`
   - Reemplazados múltiples `print()` por funciones de logging apropiadas
   - Mejor seguimiento de errores con contexto y niveles adecuados

2. **Manejo de Excepciones**:
   - Mejorado el manejo de excepciones para evitar fallos silenciosos
   - Todas las excepciones son ahora registradas en logs
   - Respuestas de error más descriptivas para APIs

3. **Validación de ObjectId**:
   - Validación mejorada para IDs de MongoDB
   - Verificación de existencia antes de acceder a propiedades
   - Mensajes de error más descriptivos

4. **Validación de Variables de Entorno**:
   - Sistema centralizado para validar variables de entorno críticas
   - Advertencias claras cuando faltan variables importantes
   - Opción para detener la aplicación en caso de configuración incorrecta

5. **Rendimiento de Base de Datos**:
   - Implementación de índices para colecciones MongoDB frecuentemente consultadas
   - Optimización de consultas para reducir la carga del servidor
   - Configuración de límites para evitar sobrecarga

6. **Refactorización de APIs**:
   - Eliminación de endpoints duplicados
   - Estandarización de respuestas
   - Mejor documentación de parámetros

## Variables de Entorno Requeridas

El proyecto usa las siguientes variables de entorno que deben configurarse en un archivo `.env`:

```
# Base de datos
MONGO_DB_URI=mongodb://localhost:27017
DB_NAME=sapiensai
INDIGENOUS_DB_NAME=indigenous_languages

# JWT
JWT_SECRET=<clave_secreta_para_tokens>
JWT_EXPIRATION_HOURS=24

# Servidor
FLASK_ENV=development
FLASK_DEBUG=1
PORT=5000

# CORS
CORS_ORIGINS=http://localhost:3000

# Opciones Adicionales
API_LOGGING=basic            # 'none', 'basic' o 'detailed'
ENFORCE_ENV_VALIDATION=0     # Establecer a 1 en producción para validación estricta
SETUP_INDEXES=1              # Configurar índices MongoDB al iniciar
```

## Ejecución

Para ejecutar el proyecto en modo desarrollo:

```bash
python main.py
```

Para despliegue en producción con Vercel, la configuración ya está preparada en `vercel.json`.

## Estructura del Proyecto

El proyecto está organizado de forma modular:

- `main.py`: Punto de entrada principal y configuración de la aplicación
- `config.py`: Configuración de la aplicación según el entorno
- `src/`: Código fuente organizado por módulos funcionales
  - `shared/`: Componentes compartidos (base de datos, excepciones, utilidades)
  - `users/`: Gestión de usuarios y autenticación
  - `institute/`: Gestión de institutos educativos
  - `classes/`: Gestión de clases y secciones
  - `study_plans/`: Planes de estudio y contenido educativo
  - Otros módulos para funcionalidades específicas 

## Características principales

- Procesamiento de documentos PDF
- Extracción de texto e imágenes
- Búsqueda web mediante SearXNG (ver [documentación](docs/SEARXNG.md))
- Generación de diagramas
- Almacenamiento de recursos 

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
Marca la vinculación como "deleted" sin eliminar el recurso.

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