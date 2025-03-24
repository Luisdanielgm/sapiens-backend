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