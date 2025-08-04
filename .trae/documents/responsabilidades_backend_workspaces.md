# Responsabilidades del Backend para Resolver Inconsistencias de Workspaces

## 1. Resumen de Responsabilidades

Basado en el análisis de las inconsistencias identificadas en el frontend, el backend tiene las siguientes responsabilidades críticas para completar la implementación de workspaces:

## 2. Endpoints Faltantes - Responsabilidad Inmediata

### 2.1 Implementar GET /api/workspaces/{workspaceId}

**Responsabilidad**: Crear endpoint para obtener detalles específicos de un workspace

**Ubicación**: `src/workspaces/routes.py`

**Implementación requerida**:
```python
@workspaces_bp.route('/<workspace_id>', methods=['GET'])
@APIRoute.standard(auth_required_flag=True)
def get_workspace_details(workspace_id):
    # Validar que el workspace existe y pertenece al usuario
    # Retornar información detallada del workspace
    pass
```

**Estado actual**: ❌ No implementado
**Impacto**: El frontend no puede obtener detalles específicos de workspaces

### 2.2 Implementar POST /api/workspaces/personal

**Responsabilidad**: Crear endpoint para generar nuevos workspaces personales

**Ubicación**: `src/workspaces/routes.py`

**Implementación requerida**:
```python
@workspaces_bp.route('/personal', methods=['POST'])
@APIRoute.standard(auth_required_flag=True)
def create_personal_workspace():
    # Crear workspace individual para el usuario
    # Manejar creación de clase personal si es INDIVIDUAL_TEACHER
    pass
```

**Estado actual**: ❌ No implementado
**Impacto**: Los usuarios no pueden crear workspaces personales desde la interfaz

### 2.3 Implementar PATCH /api/workspaces/{workspaceId}

**Responsabilidad**: Crear endpoint para actualizar información de workspaces

**Ubicación**: `src/workspaces/routes.py`

**Implementación requerida**:
```python
@workspaces_bp.route('/<workspace_id>', methods=['PATCH'])
@APIRoute.standard(auth_required_flag=True)
def update_workspace(workspace_id):
    # Actualizar información del workspace
    # Validar permisos de edición
    pass
```

**Estado actual**: ❌ No implementado
**Impacto**: Los usuarios no pueden editar nombres o configuraciones de sus workspaces

### 2.4 Implementar POST /api/workspaces/{workspaceId}/study-plan

**Responsabilidad**: Crear endpoint para generar planes de estudio individuales

**Ubicación**: `src/workspaces/routes.py`

**Implementación requerida**:
```python
@workspaces_bp.route('/<workspace_id>/study-plan', methods=['POST'])
@APIRoute.standard(auth_required_flag=True)
def create_study_plan(workspace_id):
    # Crear plan de estudio personalizado
    # Integrar con sistema de generación automática
    pass
```

**Estado actual**: ❌ No implementado
**Impacto**: Estudiantes individuales no pueden generar planes de estudio personalizados

## 3. Servicios de Soporte - Responsabilidad de Extensión

### 3.1 Extender MembershipService

**Responsabilidad**: Agregar métodos para gestión completa de workspaces

**Ubicación**: `src/members/services.py`

**Métodos requeridos**:
```python
class MembershipService:
    def create_personal_workspace(self, user_id: str, workspace_data: dict) -> Tuple[bool, str]:
        """Crear workspace personal para usuario"""
        pass
    
    def get_workspace_by_id(self, workspace_id: str, user_id: str) -> Dict:
        """Obtener workspace específico validando pertenencia"""
        pass
    
    def update_workspace_info(self, workspace_id: str, update_data: dict) -> Tuple[bool, str]:
        """Actualizar información de workspace"""
        pass
    
    def validate_workspace_ownership(self, workspace_id: str, user_id: str) -> bool:
        """Validar que el usuario es propietario del workspace"""
        pass
```

**Estado actual**: ⚠️ Parcialmente implementado (solo `get_user_workspaces`)
**Impacto**: Funcionalidad limitada para gestión de workspaces

### 3.2 Crear WorkspaceService

**Responsabilidad**: Crear servicio dedicado para lógica de negocio de workspaces

**Ubicación**: `src/workspaces/services.py` (nuevo archivo)

**Funcionalidades requeridas**:
- Validación de tipos de workspace
- Creación de clases personales para profesores
- Gestión de permisos por workspace
- Integración con sistema de generación de contenido

**Estado actual**: ❌ No existe
**Impacto**: Lógica de negocio dispersa y sin centralizar

## 4. Filtros de Permisos - Responsabilidad de Seguridad

### 4.1 Implementar Filtros por Workspace Type

**Responsabilidad**: Asegurar aislamiento de datos entre workspaces individuales

**Ubicación**: Múltiples servicios (`src/classes/`, `src/content/`, `src/study_plan/`)

**Implementación requerida**:
```python
def apply_workspace_filters(query: dict, workspace_type: str, user_id: str, class_id: str = None) -> dict:
    """Aplicar filtros según tipo de workspace para aislar datos"""
    if workspace_type == "INDIVIDUAL_TEACHER":
        # Solo clases propias
        query["$or"] = [
            {"created_by": ObjectId(user_id)},
            {"_id": ObjectId(class_id)} if class_id else {}
        ]
    elif workspace_type == "INDIVIDUAL_STUDENT":
        # Solo contenido propio
        user_plans = get_user_study_plans(user_id)
        query["study_plan_id"] = {"$in": [p["_id"] for p in user_plans]}
    
    return query
```

**Estado actual**: ❌ No implementado
**Impacto**: Riesgo de exposición de datos entre usuarios en instituto genérico

### 4.2 Actualizar Decoradores de Autorización

**Responsabilidad**: Modificar sistema de autorización para considerar workspace_type

**Ubicación**: `src/shared/decorators.py`

**Modificaciones requeridas**:
```python
@role_required('teacher')
def protected_endpoint():
    # Obtener workspace_type del token JWT
    workspace_type = get_jwt_claims().get('workspace_type')
    
    # Aplicar filtros según tipo de workspace
    if workspace_type in ["INDIVIDUAL_TEACHER", "INDIVIDUAL_STUDENT"]:
        # Aplicar filtros restrictivos
        pass
```

**Estado actual**: ⚠️ Parcialmente implementado (decoradores existen pero no consideran workspace_type)
**Impacto**: Permisos incorrectos en workspaces individuales

## 5. Migración y Datos - Responsabilidad de Consistencia

### 5.1 Corregir Script de Migración

**Responsabilidad**: Asegurar que la migración use el instituto genérico existente

**Ubicación**: `scripts/migrate_workspace_refactoring.py`

**Problema identificado**: El script actual puede crear institute_id únicos en lugar de usar el instituto genérico

**Corrección requerida**:
```python
def _get_or_create_generic_entities(self):
    # Buscar instituto genérico existente ANTES de crear uno nuevo
    existing_generic = self.db.institutes.find_one({"name": "Academia Sapiens"})
    if existing_generic:
        return {
            "institute_id": str(existing_generic["_id"]),
            # ... otras entidades
        }
    # Solo crear si no existe
```

**Estado actual**: ⚠️ Requiere revisión
**Impacto**: Datos inconsistentes en migración

### 5.2 Validar Nombres de Workspace

**Responsabilidad**: Asegurar nombres consistentes según esquema acordado

**Ubicación**: Scripts de migración y servicios de creación

**Esquema requerido**:
- INDIVIDUAL_STUDENT: "Aprendizaje de {Nombre}"
- INDIVIDUAL_TEACHER: "Clases de {Nombre}"
- INSTITUTE: Nombre del instituto

**Estado actual**: ⚠️ Inconsistente entre scripts
**Impacto**: Nombres de workspace inconsistentes en la interfaz

## 6. Integración con Sistema Existente - Responsabilidad de Compatibilidad

### 6.1 Actualizar Sistema de Generación de Contenido

**Responsabilidad**: Integrar workspaces individuales con generación automática

**Ubicación**: `src/virtual/` y `src/study_plan/`

**Modificaciones requeridas**:
- Permitir generación de planes para workspaces individuales
- Asociar módulos virtuales con workspaces específicos
- Filtrar contenido generado por workspace

**Estado actual**: ⚠️ Sistema existe pero no integrado con workspaces individuales
**Impacto**: Estudiantes individuales no pueden generar contenido personalizado

### 6.2 Actualizar Sistema de Clases Personales

**Responsabilidad**: Asegurar creación automática de clases para profesores individuales

**Ubicación**: `src/classes/services.py` y `src/users/services.py`

**Validaciones requeridas**:
- Verificar que se crea clase personal al crear workspace INDIVIDUAL_TEACHER
- Asegurar que class_id se almacena en membership
- Validar que solo el profesor puede acceder a su clase personal

**Estado actual**: ✅ Implementado en registro, ⚠️ falta en creación manual de workspaces
**Impacto**: Profesores que crean workspaces manualmente no tendrán clase asociada

## 7. Priorización de Responsabilidades

### Prioridad 1 - Crítica (Bloquea funcionalidad básica)
1. ❌ Implementar `GET /api/workspaces/{workspaceId}`
2. ❌ Implementar `POST /api/workspaces/personal`
3. ❌ Implementar `PATCH /api/workspaces/{workspaceId}`
4. ❌ Implementar filtros básicos de permisos

### Prioridad 2 - Alta (Funcionalidad avanzada)
1. ❌ Implementar `POST /api/workspaces/{id}/study-plan`
2. ⚠️ Corregir script de migración
3. ⚠️ Extender MembershipService
4. ❌ Crear WorkspaceService

### Prioridad 3 - Media (Optimización y seguridad)
1. ❌ Implementar filtros avanzados por workspace_type
2. ⚠️ Actualizar decoradores de autorización
3. ⚠️ Integrar con sistema de generación de contenido
4. ⚠️ Validar nombres de workspace consistentes

## 8. Estimación de Esfuerzo

### Endpoints básicos: 2-3 días
- Implementación de 4 endpoints principales
- Validaciones básicas
- Tests unitarios

### Servicios de soporte: 2-3 días
- Extensión de MembershipService
- Creación de WorkspaceService
- Integración con servicios existentes

### Filtros de permisos: 3-4 días
- Implementación de filtros por workspace_type
- Actualización de decoradores
- Pruebas de seguridad

### Migración y datos: 1-2 días
- Corrección de scripts
- Validación de datos existentes
- Tests de migración

**Total estimado: 8-12 días de desarrollo**

## 9. Criterios de Aceptación

### Funcionalidad
- ✅ Todos los endpoints faltantes implementados y funcionales
- ✅ Frontend puede crear, editar y obtener workspaces sin errores
- ✅ Usuarios pueden generar planes de estudio individuales
- ✅ Filtros de permisos impiden acceso a datos ajenos

### Seguridad
- ✅ Workspaces individuales completamente aislados
- ✅ Validación de pertenencia en todos los endpoints
- ✅ No exposición de datos entre usuarios del instituto genérico

### Consistencia
- ✅ Nombres de workspace según esquema acordado
- ✅ Migración usa instituto genérico existente
- ✅ Clases personales creadas automáticamente

### Performance
- ✅ Consultas optimizadas con filtros
- ✅ No degradación en endpoints existentes
- ✅ Tiempo de respuesta < 500ms para operaciones básicas

Este documento define claramente las responsabilidades del backend para resolver todas las inconsistencias identificadas en el frontend y completar la implementación de workspaces.