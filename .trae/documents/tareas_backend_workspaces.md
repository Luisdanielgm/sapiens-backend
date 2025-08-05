# Tareas Específicas del Backend - Workspaces

## 1. Tareas de Verificación Inmediata

### 1.1 Verificar Conectividad de Endpoints

**Objetivo**: Confirmar que todos los endpoints están accesibles desde el frontend.

**Comandos de verificación**:

```bash
# Verificar que el servidor está corriendo
curl -X GET http://localhost:5000/api/workspaces/ -H "Authorization: Bearer <token>"

# Probar endpoint específico de workspace
curl -X GET http://localhost:5000/api/workspaces/<workspace_id> -H "Authorization: Bearer <token>"

# Probar creación de workspace personal
curl -X POST http://localhost:5000/api/workspaces/personal \
  -H "Authorization: Bearer <token>" \
  -H "Content-Type: application/json" \
  -d '{"workspace_name": "Mi Workspace Personal"}'
```

**Archivos a revisar**:

* `src/main.py` - Verificar registro del blueprint

* `src/workspaces/routes.py` - Confirmar definición de rutas

* `src/config.py` - Verificar configuración de CORS

### 1.2 Validar Formato de Parámetros

**Problema identificado**: Posible incompatibilidad entre `{workspaceId}` (frontend) y `<workspace_id>` (backend).

**Verificaciones necesarias**:

```python
# En routes.py, verificar que acepta ObjectId válidos
from bson import ObjectId
from bson.errors import InvalidId

@workspaces_bp.route('/<workspace_id>', methods=['GET'])
@auth_required
@workspace_access_required
def get_workspace_details(workspace_id):
    try:
        # Verificar que workspace_id es un ObjectId válido
        ObjectId(workspace_id)
    except InvalidId:
        return jsonify({'error': 'Invalid workspace ID format'}), 400
    # ... resto del código
```

### 1.3 Revisar Configuración de CORS

**Archivo**: `src/main.py` o `src/config.py`

**Verificar que incluye**:

```python
from flask_cors import CORS

# Configuración CORS para desarrollo
CORS(app, origins=['http://localhost:3000'], supports_credentials=True)

# O configuración más específica
CORS(app, resources={
    r"/api/*": {
        "origins": ["http://localhost:3000"],
        "methods": ["GET", "POST", "PATCH", "DELETE"],
        "allow_headers": ["Content-Type", "Authorization"]
    }
})
```

## 2. Tareas de Corrección de Código

### 2.1 Mejorar Manejo de Errores en Endpoints

**Archivo**: `src/workspaces/routes.py`

**Mejoras necesarias**:

```python
@workspaces_bp.route('/personal', methods=['POST'])
@auth_required
def create_personal_workspace():
    try:
        data = request.get_json()
        if not data or 'workspace_name' not in data:
            return jsonify({
                'error': 'Missing required field: workspace_name',
                'code': 'MISSING_WORKSPACE_NAME'
            }), 400
        
        user_id = get_current_user_id()
        workspace = WorkspaceService.create_personal_workspace(
            user_id=user_id,
            workspace_name=data['workspace_name'],
            workspace_type=data.get('workspace_type', 'INDIVIDUAL_STUDENT')
        )
        
        return jsonify({
            'success': True,
            'workspace': workspace,
            'message': 'Personal workspace created successfully'
        }), 201
        
    except ValueError as e:
        return jsonify({
            'error': str(e),
            'code': 'VALIDATION_ERROR'
        }), 400
    except Exception as e:
        logger.error(f"Error creating personal workspace: {str(e)}")
        return jsonify({
            'error': 'Internal server error',
            'code': 'INTERNAL_ERROR'
        }), 500
```

### 2.2 Agregar Logging para Debugging

**Archivo**: `src/workspaces/routes.py`

**Agregar al inicio del archivo**:

```python
import logging
logger = logging.getLogger(__name__)

# En cada endpoint, agregar logging
@workspaces_bp.route('/<workspace_id>', methods=['GET'])
@auth_required
@workspace_access_required
def get_workspace_details(workspace_id):
    logger.info(f"Getting workspace details for ID: {workspace_id}")
    try:
        # ... código existente
        logger.info(f"Successfully retrieved workspace: {workspace_id}")
        return jsonify(workspace_data)
    except Exception as e:
        logger.error(f"Error getting workspace {workspace_id}: {str(e)}")
        raise
```

### 2.3 Validar Decoradores de Workspace

**Archivo**: `src/workspaces/decorators.py`

**Verificar implementación**:

```python
def workspace_access_required(f):
    @wraps(f)
    def decorated_function(*args, **kwargs):
        try:
            workspace_id = kwargs.get('workspace_id')
            if not workspace_id:
                return jsonify({'error': 'Workspace ID required'}), 400
            
            user_id = get_current_user_id()
            if not MembershipService.get_workspace_membership(user_id, workspace_id):
                return jsonify({'error': 'Access denied to workspace'}), 403
            
            return f(*args, **kwargs)
        except Exception as e:
            logger.error(f"Workspace access validation error: {str(e)}")
            return jsonify({'error': 'Access validation failed'}), 500
    return decorated_function
```

## 3. Tareas de Optimización

### 3.1 Mejorar Consultas de Workspace

**Archivo**: `src/workspaces/services.py`

**Optimización en** **`apply_workspace_filters`**:

```python
def apply_workspace_filters(query, workspace_type, workspace_id, user_id):
    """Aplica filtros de workspace para aislar datos por workspace"""
    
    if workspace_type == 'INDIVIDUAL_STUDENT':
        # Solo mostrar study plans del usuario
        query = query.filter(StudyPlan.user_id == user_id)
    
    elif workspace_type == 'INDIVIDUAL_TEACHER':
        # Solo mostrar clases creadas por el profesor
        query = query.filter(Class.created_by == user_id)
    
    elif workspace_type == 'INSTITUTE':
        # Filtrar por instituto del workspace
        workspace = WorkspaceService.get_workspace_by_id(workspace_id)
        if workspace:
            query = query.filter(Class.institute_id == workspace['institute_id'])
    
    return query
```

### 3.2 Validar Migración de Datos

**Crear script de validación**: `scripts/validate_workspace_migration.py`

```python
from src.database import db
from src.institutes.models import Institute
from src.members.models import InstituteMember

def validate_migration():
    """Valida que la migración de workspaces se ejecutó correctamente"""
    
    # Verificar instituto genérico
    generic_institute = Institute.query.filter_by(name="Academia Sapiens").first()
    if not generic_institute:
        print("❌ Instituto genérico no encontrado")
        return False
    
    # Verificar workspaces individuales
    individual_members = InstituteMember.query.filter(
        InstituteMember.workspace_type.in_(['INDIVIDUAL_STUDENT', 'INDIVIDUAL_TEACHER'])
    ).all()
    
    print(f"✅ Encontrados {len(individual_members)} workspaces individuales")
    
    # Verificar nombres de workspace
    for member in individual_members[:5]:  # Revisar primeros 5
        if not member.workspace_name:
            print(f"❌ Workspace sin nombre: {member.id}")
        else:
            print(f"✅ Workspace: {member.workspace_name}")
    
    return True

if __name__ == "__main__":
    validate_migration()
```

## 4. Tareas de Testing

### 4.1 Completar Tests Unitarios

**Archivo**: `tests/test_workspaces_endpoints.py`

**Agregar tests faltantes**:

```python
import pytest
from src.main import create_app
from src.database import db

class TestWorkspaceEndpoints:
    
    def test_get_workspace_details_success(self, client, auth_headers, sample_workspace):
        """Test successful workspace details retrieval"""
        response = client.get(
            f'/api/workspaces/{sample_workspace.id}',
            headers=auth_headers
        )
        assert response.status_code == 200
        data = response.get_json()
        assert data['workspace_id'] == str(sample_workspace.id)
    
    def test_create_personal_workspace_success(self, client, auth_headers):
        """Test successful personal workspace creation"""
        response = client.post(
            '/api/workspaces/personal',
            json={'workspace_name': 'Mi Workspace Test'},
            headers=auth_headers
        )
        assert response.status_code == 201
        data = response.get_json()
        assert data['success'] is True
        assert 'workspace' in data
    
    def test_update_workspace_success(self, client, auth_headers, sample_workspace):
        """Test successful workspace update"""
        response = client.patch(
            f'/api/workspaces/{sample_workspace.id}',
            json={'workspace_name': 'Nuevo Nombre'},
            headers=auth_headers
        )
        assert response.status_code == 200
        data = response.get_json()
        assert data['success'] is True
```

### 4.2 Tests de Integración

**Crear**: `tests/test_workspace_integration.py`

```python
def test_complete_workspace_flow(client, auth_headers):
    """Test complete workspace creation and usage flow"""
    
    # 1. Crear workspace personal
    create_response = client.post(
        '/api/workspaces/personal',
        json={'workspace_name': 'Test Integration Workspace'},
        headers=auth_headers
    )
    assert create_response.status_code == 201
    workspace_id = create_response.get_json()['workspace']['workspace_id']
    
    # 2. Cambiar a ese workspace
    switch_response = client.post(
        f'/api/workspaces/switch/{workspace_id}',
        headers=auth_headers
    )
    assert switch_response.status_code == 200
    new_token = switch_response.get_json()['token']
    
    # 3. Verificar que el workspace está activo
    new_headers = {'Authorization': f'Bearer {new_token}'}
    details_response = client.get(
        f'/api/workspaces/{workspace_id}',
        headers=new_headers
    )
    assert details_response.status_code == 200
```

## 5. Checklist de Verificación

### 5.1 Endpoints Funcionales

* [ ] `GET /api/workspaces/` - Lista workspaces

* [ ] `GET /api/workspaces/<workspace_id>` - Detalles de workspace

* [ ] `POST /api/workspaces/personal` - Crear workspace personal

* [ ] `PATCH /api/workspaces/<workspace_id>` - Actualizar workspace

* [ ] `POST /api/workspaces/switch/<workspace_id>` - Cambiar workspace

* [ ] `POST /api/workspaces/<workspace_id>/study-plan` - Crear study plan

### 5.2 Validaciones

* [ ] Autenticación JWT funciona

* [ ] Decoradores de workspace validan correctamente

* [ ] Filtros de datos por workspace funcionan

* [ ] Manejo de errores es robusto

* [ ] Logging está implementado

### 5.3 Integración

* [ ] Frontend puede consumir todos los endpoints

* [ ] CORS configurado correctamente

* [ ] Formato de respuestas es consistente

* [ ] Tests pasan exitosamente

## 6. Comandos de Ejecución

```bash
# Ejecutar tests
python -m pytest tests/test_workspaces_endpoints.py -v

# Validar migración
python scripts/validate_workspace_migration.py

# Ejecutar servidor en modo debug
FLASK_ENV=development python src/main.py

# Verificar endpoints con curl
bash scripts/test_workspace_endpoints.
```

