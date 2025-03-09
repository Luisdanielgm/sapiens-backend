# Módulo compartido (shared)

Este directorio contiene componentes compartidos que son utilizados en toda la aplicación.

## Componentes principales

### 1. Decoradores (`decorators.py`)

Contiene decoradores para:
- **handle_errors**: Maneja excepciones de forma consistente
- **auth_required**: Verifica autenticación del usuario
- **role_required**: Verifica permisos según roles
- **validate_json**: Valida datos JSON de entrada

Ejemplo:
```python
@handle_errors
@auth_required
@role_required('admin')
@validate_json(['name', 'email'])
def create_resource():
    # Implementación
```

### 2. Excepciones personalizadas (`exceptions.py`)

La clase `AppException` permite lanzar errores con código HTTP y detalles personalizados.

Ejemplo:
```python
# Lanzar excepción con código predefinido
if not user:
    raise AppException("Usuario no encontrado", AppException.NOT_FOUND)

# Incluir detalles adicionales
raise AppException("Validación fallida", 400, {"campo": "El valor es inválido"})
```

### 3. Validadores (`validators.py`)

Funciones de validación:
- **is_valid_object_id**: Valida si un string es un ObjectId válido
- **validate_object_id**: Valida un ObjectId y lanza AppException si es inválido
- **validate_schema**: Valida datos contra un esquema estructurado
- **validate_email**: Valida formato de email

Ejemplo:
```python
# Validar ID de MongoDB
validate_object_id(user_id)  # Lanza AppException si no es válido

# Validar datos contra esquema
schema = {
    'name': {'type': 'string', 'required': True, 'minLength': 3},
    'age': {'type': 'integer', 'minimum': 18}
}
is_valid, errors = validate_schema(data, schema)
```

### 4. Constantes (`constants.py`)

Define constantes utilizadas en toda la aplicación.

### 5. Utilidades (`utils.py`)

Contiene funciones de utilidad generales. Los decoradores no deben importarse desde aquí, sino desde `decorators.py`.

### 6. Base de datos (`database.py`)

Proporciona conexión a la base de datos MongoDB y funciones relacionadas.

### 7. Estandarización (`standardization.py`)

**NUEVO:** Este módulo unifica la estandarización de rutas, servicios y códigos de error en un único archivo:

1. **APIBlueprint**: Una extensión de Flask Blueprint para definir las rutas
2. **APIRoute**: Clase de utilidad con métodos para:
   - Crear decoradores estándar (`@APIRoute.standard()`)
   - Generar respuestas exitosas (`APIRoute.success()`)
   - Generar respuestas de error (`APIRoute.error()`)
3. **BaseService**: Clase base para servicios CRUD
4. **ErrorCodes**: Códigos de error estandarizados

## Estandarización de API

### Principios de diseño

1. **Coherencia**: Todas las rutas deben seguir el mismo patrón de diseño
2. **Simplicidad**: Reducir código duplicado y simplificar la implementación
3. **Mantenibilidad**: Facilitar la adición de nuevas funcionalidades
4. **Seguridad**: Centralizar el manejo de autenticación y autorización
5. **Respuesta estandarizada**: Formato uniforme para todas las respuestas

### Estructura de respuesta estándar

#### Respuestas exitosas

```json
{
  "success": true,
  "data": {}, // Opcional: Datos de respuesta 
  "message": "Mensaje descriptivo" // Opcional: Mensaje informativo
}
```

#### Respuestas de error

```json
{
  "success": false,
  "error": "CODIGO_ERROR",
  "message": "Descripción del error",
  "details": {} // Opcional: Detalles adicionales sobre el error
}
```

### Ejemplos de uso

#### Definición de rutas estandarizadas

```python
from src.shared.standardization import APIBlueprint, APIRoute, ErrorCodes

# Crear un blueprint para tu dominio
mi_bp = APIBlueprint('nombre_dominio', __name__)

# Definir una ruta básica
@mi_bp.route('/ruta', methods=['GET'])
@APIRoute.standard()
def mi_funcion():
    try:
        # Lógica de negocio
        resultado = mi_servicio.obtener_datos()
        return APIRoute.success(data=resultado)
    except Exception as e:
        return APIRoute.error(ErrorCodes.SERVER_ERROR, str(e))
```

#### Rutas con autenticación y roles

```python
@mi_bp.route('/admin/recursos', methods=['GET'])
@APIRoute.standard(
    auth_required_flag=True,
    roles=[ROLES["ADMIN"]]
)
def admin_funcion():
    # Lógica para administradores
    return APIRoute.success(data=datos)
```

#### Implementación de servicios estandarizados

```python
from src.shared.standardization import BaseService

class MiServicio(BaseService):
    def __init__(self):
        super().__init__(collection_name="mi_coleccion")
        
    # Métodos personalizados adicionales
    def logica_especifica(self, datos):
        # Implementación...
        pass
```

## Proceso de migración

Para migrar un módulo existente a la nueva estructura estandarizada:

1. **Crear una nueva versión del archivo de rutas** usando APIBlueprint y APIRoute
2. **Refactorizar los servicios** para heredar de BaseService
3. **Probar exhaustivamente** cada endpoint
4. **Reemplazar gradualmente** los archivos originales con las versiones estandarizadas

### Ejemplo de migración

**Antes**:
```python
from flask import Blueprint, request, jsonify
from .services import MiServicio
from src.shared.decorators import handle_errors, auth_required

mi_bp = Blueprint('nombre', __name__)
mi_servicio = MiServicio()

@mi_bp.route('/ruta', methods=['GET'])
@handle_errors
@auth_required
def mi_funcion():
    try:
        resultado = mi_servicio.obtener_datos()
        return jsonify({
            "success": True,
            "data": resultado
        }), 200
    except Exception as e:
        return jsonify({
            "success": False,
            "error": "ERROR_CODIGO",
            "message": str(e)
        }), 500
```

**Después**:
```python
from flask import request
from .services import MiServicio
from src.shared.standardization import APIBlueprint, APIRoute, ErrorCodes

mi_bp = APIBlueprint('nombre', __name__)
mi_servicio = MiServicio()

@mi_bp.route('/ruta', methods=['GET'])
@APIRoute.standard(auth_required_flag=True)
def mi_funcion():
    try:
        resultado = mi_servicio.obtener_datos()
        return APIRoute.success(data=resultado)
    except Exception as e:
        return APIRoute.error(ErrorCodes.SERVER_ERROR, str(e), status_code=500)
```

## Configuración de la aplicación

La aplicación usa un sistema de configuración basado en variables de entorno:

1. Variables de entorno definidas en el archivo `.env`
2. Clases de configuración en `config.py` que cargan estas variables
3. Diferentes configuraciones para desarrollo, pruebas y producción

### CORS y seguridad

- **Entornos de desarrollo**: Se usa Flask-CORS con orígenes específicos definidos en `CORS_ORIGINS`.
- **En Vercel**: Se configura en `vercel.json` con encabezados CORS, y la configuración de Flask-CORS se minimiza.

La seguridad de la API se mantiene gracias a:
- Autenticación JWT mediante `flask_jwt_extended` (`@auth_required`)
- Verificación de roles (`@role_required`)
- Validación de entrada (`@validate_json`)

## Buenas prácticas

1. **Autenticación**:
   - Usar `flask_jwt_extended` para toda la gestión de JWT
   - Evitar usar las funciones deprecadas en `utils.py` (`generate_token`, `verify_token`)
   
2. **Manejo de errores**:
   - Usar `AppException` para errores específicos de la aplicación
   - Implementar `handle_errors` en todas las rutas o usar `APIRoute.standard()`
   
3. **Validación**:
   - Usar `validate_json` en rutas que reciben datos o `APIRoute.standard(required_fields=[...])`
   - Usar `validate_object_id` para validar IDs de MongoDB
   
4. **Importaciones**:
   - Evitar importaciones circulares
   - Para decoradores, importar directamente desde `decorators.py`
   - Para estandarización, importar desde `standardization.py`

5. **Respuestas**:
   - Usar `APIRoute.success()` y `APIRoute.error()` para respuestas consistentes
   - Usar códigos de error estandarizados de `ErrorCodes` 

## Métodos de Verificación Estandarizados

La aplicación ahora implementa un patrón estándar para métodos de verificación en los servicios. Estos métodos:

1. **Propósito**: Verifican la existencia de entidades en la base de datos antes de realizar operaciones
2. **Nomenclatura**: Siguen el patrón `check_X_exists` donde X es la entidad a verificar
3. **Retorno**: Devuelven un valor booleano (True/False)
4. **Manejo de errores**: Incluyen manejo de excepciones

### Características principales

- **Prefijo estándar**: Todos comienzan con `check_`
- **Manejo interno de excepciones**: Evita que las excepciones de base de datos se propaguen
- **Documentación completa**: Incluyen docstrings explicativos
- **Simplicidad**: Realizan una única verificación específica

### Implementación típica

```python
def check_entity_exists(self, entity_id: str) -> bool:
    """
    Verifica si una entidad existe.
    
    Args:
        entity_id: ID de la entidad a verificar
        
    Returns:
        bool: True si la entidad existe, False en caso contrario
    """
    try:
        entity = self.db.entities.find_one({"_id": ObjectId(entity_id)})
        return entity is not None
    except Exception:
        return False
```

### Ejemplos de uso

En la lógica de negocio, estos métodos se utilizan para validar condiciones previas:

```python
def create_something(self, data: dict) -> Tuple[bool, str]:
    # Verificar entidades relacionadas
    if not self.check_entity_exists(data['entity_id']):
        return False, "Entidad no encontrada"
        
    # Continuar con la creación si la verificación pasa
    # ...
```

### Beneficios

1. **Código más limpio**: Los métodos principales se centran en su funcionalidad específica
2. **Reducción de duplicación**: La lógica de verificación se centraliza
3. **Manejo consistente de errores**: Todas las verificaciones siguen el mismo patrón
4. **Mayor robustez**: Cada operación verifica primero las condiciones necesarias
5. **Mantenibilidad mejorada**: Si cambia la lógica de verificación, solo hay que modificarla en un lugar

### Implementación en nuevos servicios

Al crear un nuevo servicio, se recomienda:

1. Extender la clase `VerificationBaseService` en lugar de `BaseService`
2. Utilizar los métodos de verificación predefinidos
3. Implementar métodos de verificación adicionales específicos del dominio si es necesario

### Clase VerificationBaseService

Para simplificar la implementación de estos métodos, se ha creado la clase `VerificationBaseService` en `standardization.py`, que extiende `BaseService` y proporciona métodos de verificación comunes:

```python
from src.shared.standardization import VerificationBaseService

class MiServicio(VerificationBaseService):
    def __init__(self):
        super().__init__(collection_name="mi_coleccion")
        
    def create_algo(self, data: dict) -> Tuple[bool, str]:
        # Usar métodos heredados de verificación
        if not self.check_user_exists(data['user_id']):
            return False, "Usuario no encontrado"
            
        if not self.check_class_exists(data['class_id']):
            return False, "Clase no encontrada"
            
        # ... lógica de creación ...
```

Los métodos de verificación predefinidos incluyen:
- `check_user_exists`
- `check_institute_exists`
- `check_class_exists`
- `check_student_exists`
- `check_teacher_exists`
- `check_study_plan_exists`
- `check_academic_period_exists`
- `check_subject_exists`

Para entidades específicas de dominio, se deben implementar métodos adicionales siguiendo el mismo patrón.

### Ejemplo de migración de un servicio existente

**Antes (usando BaseService):**
```python
from src.shared.standardization import BaseService

class VirtualModuleService(BaseService):
    def __init__(self):
        super().__init__(collection_name="virtual_modules")
        
    def check_study_plan_exists(self, plan_id: str) -> bool:
        try:
            plan = self.db.study_plans_per_subject.find_one({"_id": ObjectId(plan_id)})
            return plan is not None
        except Exception:
            return False
            
    def create_module(self, module_data: dict) -> Tuple[bool, str]:
        try:
            # Verificar que el plan de estudio existe
            if not self.check_study_plan_exists(module_data['study_plan_id']):
                return False, "Plan de estudios no encontrado"

            module = VirtualModule(**module_data)
            result = self.collection.insert_one(module.to_dict())
            return True, str(result.inserted_id)
        except Exception as e:
            return False, str(e)
```

**Después (usando VerificationBaseService):**
```python
from src.shared.standardization import VerificationBaseService

class VirtualModuleService(VerificationBaseService):
    def __init__(self):
        super().__init__(collection_name="virtual_modules")
            
    def create_module(self, module_data: dict) -> Tuple[bool, str]:
        try:
            # Verificar que el plan de estudio existe
            if not self.check_study_plan_exists(module_data['study_plan_id']):
                return False, "Plan de estudios no encontrado"

            module = VirtualModule(**module_data)
            result = self.collection.insert_one(module.to_dict())
            return True, str(result.inserted_id)
        except Exception as e:
            return False, str(e)
```

La migración elimina la necesidad de implementar el método `check_study_plan_exists`, ya que ahora se hereda de `VerificationBaseService`. 