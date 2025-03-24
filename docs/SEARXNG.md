# Servicio de Búsqueda Web con SearXNG

Este módulo proporciona funcionalidad para realizar búsquedas web utilizando instancias SearXNG públicas verificadas, permitiendo obtener resultados de múltiples motores de búsqueda de manera anónima y descentralizada.

## Características

- Búsqueda web utilizando múltiples instancias de SearXNG
- Balanceo de carga entre instancias para evitar límites de tasa
- Agrupamiento y deduplicación de resultados
- Almacenamiento en caché para mejorar rendimiento
- Gestión de proveedores de búsqueda
- Soporte para diferentes tipos de búsqueda (general, imágenes, videos, noticias)

## Archivos principales

- `src/content_resources/models.py`: Define los modelos de datos para resultados de búsqueda y proveedores
- `src/content_resources/services.py`: Implementa los servicios para búsqueda web y gestión de proveedores
- `src/content_resources/routes.py`: Define las rutas API para los servicios
- `src/content_resources/verified_searxng_instances.json`: Lista de instancias SearXNG verificadas

## Endpoints API

### Búsqueda Web

- **POST** `/web-search`: Realiza una búsqueda web
  - Parámetros: `query` (obligatorio), `result_type`, `max_results`, `topic_id`
  - Respuesta: Lista de resultados de búsqueda

- **POST** `/web-search/result/<result_id>/save`: Marca un resultado como guardado
  - Parámetros: `result_id` en la URL
  - Respuesta: Mensaje de éxito o error

### Gestión de Proveedores

- **GET** `/search-providers`: Lista todos los proveedores de búsqueda
  - Parámetros (query): `active_only`
  - Respuesta: Lista de proveedores

- **POST** `/search-providers`: Crea un nuevo proveedor de búsqueda
  - Parámetros: `name` (obligatorio), `instances`, `config`
  - Respuesta: ID del proveedor creado

- **PUT** `/search-providers/<provider_id>`: Actualiza un proveedor existente
  - Parámetros: `name`, `instances`, `config`, `status`
  - Respuesta: Mensaje de éxito o error

- **DELETE** `/search-providers/<provider_id>`: Elimina un proveedor
  - Parámetros: `provider_id` en la URL
  - Respuesta: Mensaje de éxito o error

- **GET** `/search-providers/<provider_id>/test`: Prueba un proveedor
  - Parámetros: `provider_id` en la URL
  - Respuesta: Resultados de la prueba

- **POST** `/search-providers/setup-searxng`: Configura automáticamente un proveedor con instancias verificadas
  - Parámetros: Ninguno
  - Respuesta: ID del proveedor creado y número de instancias

## Configuración inicial

Para usar el servicio, primero debe existir al menos un proveedor SearXNG. El sistema intentará crear automáticamente un proveedor predeterminado utilizando las instancias verificadas si no existe ninguno.

Para configurar manualmente un proveedor:

1. **Usar el script de configuración**:
   ```
   python setup_searxng.py
   ```
   Este script proporciona una interfaz interactiva para:
   - Configurar un proveedor SearXNG con instancias verificadas
   - Listar los proveedores existentes
   - Realizar búsquedas de prueba

2. **O utilizar directamente el API**:
   ```
   POST /search-providers/setup-searxng
   ```

3. **O crear un proveedor con instancias personalizadas**:
   ```
   POST /search-providers
   {
     "name": "Mi proveedor SearXNG",
     "instances": [
       "https://search.example.org",
       "https://searx.example.com"
     ],
     "config": {
       "language": "es",
       "safesearch": 0
     }
   }
   ```

## Ejemplos de uso

### Realizar una búsqueda web

```
POST /web-search
{
  "query": "inteligencia artificial",
  "max_results": 10
}
```

### Búsqueda de imágenes

```
POST /web-search
{
  "query": "paisajes montaña",
  "result_type": "image",
  "max_results": 20
}
```

## Gestión de caché

Los resultados de búsqueda se almacenan en caché durante 24 horas para mejorar el rendimiento y reducir las solicitudes a las instancias de SearXNG. Para obtener resultados actualizados, se debe usar una consulta diferente.

## Instancias verificadas

El sistema utiliza un conjunto de instancias SearXNG verificadas que han sido probadas para asegurar:
1. Disponibilidad y fiabilidad
2. Ausencia de límites de tasa restrictivos
3. Soporte adecuado para consultas en español

Estas instancias se cargan desde el archivo `src/content_resources/verified_searxng_instances.json` y se actualizan periódicamente.

## Notas importantes

1. Las instancias SearXNG pueden tener límites de tasa. El sistema distribuye las consultas entre varias instancias para evitar estos límites.
2. Algunas instancias pueden estar temporalmente no disponibles. El sistema es tolerante a fallos y utilizará las instancias disponibles.
3. Actualmente solo se soporta el formato HTML para las consultas, ya que muchas instancias han desactivado las respuestas en formato JSON.

## Resolución de problemas

Si los resultados no se devuelven correctamente:

1. Verificar que exista al menos un proveedor activo
2. Comprobar la conectividad con las instancias SearXNG
3. Usar el endpoint de prueba para verificar el estado de las instancias
4. Revisar los logs del servidor en busca de errores específicos

## Dependencias

Este servicio requiere las siguientes dependencias principales:
- requests
- beautifulsoup4
- lxml
- flask
- pymongo

Todas las dependencias están incluidas en el archivo `requirements.txt`. 