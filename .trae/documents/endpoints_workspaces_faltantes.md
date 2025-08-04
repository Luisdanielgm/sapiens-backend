# Endpoints Faltantes para Workspaces - Documento Técnico

## 1. Resumen Ejecutivo

Basado en el análisis de las inconsistencias identificadas en el frontend, se han detectado varios endpoints críticos que faltan en el backend para completar la funcionalidad de workspaces. El frontend está intentando consumir endpoints que no existen, causando errores en la funcionalidad de gestión de workspaces.

## 2. Endpoints Faltantes Identificados

### 2.1 GET /api/workspaces/{workspaceId}

**Propósito**: Obtener información detallada de un workspace específico

**Parámetros**:
- `workspaceId` (path): ID del workspace a consultar

**Respuesta esperada**:
```json
{
  "success": true,
  "data": {
    "workspace_id": "string",
    "workspace_type": "INSTITUTE|INDIVIDUAL_STUDENT|INDIVIDUAL_TEACHER",
    "workspace_name": "string",
    "role_in_workspace": "student|teacher|institute_admin|admin",
    "institute_id": "string",
    "class_id": "string|null",
    "status": "active|inactive",
    "joined_at": "datetime",
    "metadata": {
      "institute_name": "string",
      "institute_description": "string",
      "permissions": ["string"]
    }
  }
}
```

**Validaciones**:
- Verificar que el workspace existe
- Verificar que el usuario autenticado es miembro del workspace
- Retornar 404 si el workspace no existe
- Retornar 403 si el usuario no tiene acceso

### 2.2 POST /api/workspaces/personal

**Propósito**: Crear un nuevo workspace personal (individual) para el usuario

**Payload**:
```json
{
  "workspace_type": "INDIVIDUAL_STUDENT|INDIVIDUAL_TEACHER",
  "workspace_name": "string",
  "description": "string (opcional)"
}
```

**Respuesta esperada**:
```json
{
  "success": true,
  "data": {
    "workspace_id": "string",
    "workspace_type": "string",
    "workspace_name": "string",
    "role_in_workspace": "string",
    "institute_id": "string",
    "class_id": "string|null",
    "message": "Workspace personal creado exitosamente"
  }
}
```

**Lógica de implementación**:
1. Obtener entidades genéricas del instituto "Academia Sapiens"
2. Crear nueva membresía en `institute_members` con:
   - `institute_id`: ID del instituto genérico
   - `user_id`: ID del usuario autenticado
   - `workspace_type`: Tipo especificado en el payload
   - `workspace_name`: Nombre especificado en el payload
   - `role`: "student" para INDIVIDUAL_STUDENT, "teacher" para INDIVIDUAL_TEACHER
   - `status`: "active"
   - `joined_at`: Fecha actual
3. Si es INDIVIDUAL_TEACHER, crear clase personal asociada
4. Retornar información del workspace creado

**Validaciones**:
- Verificar que el usuario no tenga ya un workspace del mismo tipo
- Validar que el workspace_type sea válido
- Validar que el workspace_name no esté vacío

### 2.3 PATCH /api/workspaces/{workspaceId}

**Propósito**: Actualizar información de un workspace existente

**Parámetros**:
- `workspaceId` (path): ID del workspace a actualizar

**Payload**:
```json
{
  "workspace_name": "string (opcional)",
  "description": "string (opcional)",
  "status": "active|inactive (opcional)"
}
```

**Respuesta esperada**:
```json
{
  "success": true,
  "data": {
    "workspace_id": "string",
    "workspace_name": "string",
    "updated_fields": ["string"],
    "message": "Workspace actualizado exitosamente"
  }
}
```

**Lógica de implementación**:
1. Verificar que el workspace existe y pertenece al usuario
2. Validar permisos de edición (solo el propietario puede editar workspaces individuales)
3. Actualizar campos especificados en `institute_members`
4. Si se actualiza el nombre y hay clase asociada, actualizar también el nombre de la clase
5. Retornar información actualizada

**Validaciones**:
- Verificar que el usuario tiene permisos para editar el workspace
- Validar que los campos a actualizar sean válidos
- No permitir cambio de `workspace_type`
- Para workspaces institucionales, solo permitir ciertos campos

### 2.4 POST /api/workspaces/{workspaceId}/study-plan

**Propósito**: Crear un plan de estudio personalizado para un workspace individual de estudiante

**Parámetros**:
- `workspaceId` (path): ID del workspace individual de estudiante

**Payload**:
```json
{
  "title": "string",
  "description": "string",
  "objectives": ["string"],
  "document_url": "string (opcional)",
  "content_type": "pdf|text|url",
  "difficulty_level": "beginner|intermediate|advanced",
  "estimated_duration_weeks": "number"
}
```

**Respuesta esperada**:
```json
{
  "success": true,
  "data": {
    "study_plan_id": "string",
    "title": "string",
    "status": "generating|ready|error",
    "generation_task_id": "string",
    "estimated_completion": "datetime",
    "message": "Plan de estudio iniciado. La generación comenzará en breve."
  }
}
```

**Lógica de implementación**:
1. Verificar que el workspace es de tipo INDIVIDUAL_STUDENT
2. Verificar que el usuario es propietario del workspace
3. Crear un nuevo StudyPlan asociado al workspace
4. Iniciar proceso de generación automática de contenido
5. Encolar tarea de generación progresiva
6. Retornar información del plan creado

**Validaciones**:
- Solo permitir en workspaces INDIVIDUAL_STUDENT
- Verificar que el usuario no tenga ya un plan activo en ese workspace
- Validar formato de documento si se proporciona
- Validar que los objetivos no estén vacíos

## 3. Filtros de Permisos para Workspaces Individuales

### 3.1 Filtros por Workspace Type

Para evitar que usuarios en workspaces individuales vean datos de otros usuarios en el instituto genérico, se deben implementar los siguientes filtros:

#### 3.1.1 INDIVIDUAL_TEACHER
- **Clases**: Solo mostrar clases donde `created_by` sea el user_id o `_id` coincida con `class_id` de su membership
- **Contenidos**: Solo contenidos de sus propias clases
- **Estudiantes**: Solo estudiantes inscritos en sus clases personales
- **Evaluaciones**: Solo evaluaciones de sus propias clases

#### 3.1.2 INDIVIDUAL_STUDENT
- **Planes de estudio**: Solo sus propios planes de estudio personales
- **Módulos virtuales**: Solo módulos asociados a sus planes
- **Contenidos**: Solo contenidos de sus módulos virtuales
- **Resultados**: Solo sus propios resultados de evaluaciones

### 3.2 Implementación de Filtros

**En servicios de consulta**, agregar lógica condicional:

```python
def apply_workspace_filters(query, workspace_type, user_id, class_id=None):
    if workspace_type == "INDIVIDUAL_TEACHER":
        query["$or"] = [
            {"created_by": ObjectId(user_id)},
            {"_id": ObjectId(class_id)} if class_id else {}
        ]
    elif workspace_type == "INDIVIDUAL_STUDENT":
        # Filtrar por planes de estudio del usuario
        user_study_plans = get_user_study_plans(user_id)
        plan_ids = [plan["_id"] for plan in user_study_plans]
        query["study_plan_id"] = {"$in": plan_ids}
    
    return query
```

**En decoradores de autorización**, verificar workspace_type del token JWT:

```python
@role_required('teacher')
def get_classes():
    workspace_type = get_jwt_claims().get('workspace_type')
    user_id = get_jwt_identity()
    class_id = get_jwt_claims().get('class_id')
    
    query = {"institute_id": get_institute_id()}
    
    if workspace_type in ["INDIVIDUAL_TEACHER", "INDIVIDUAL_STUDENT"]:
        query = apply_workspace_filters(query, workspace_type, user_id, class_id)
    
    return get_filtered_classes(query)
```

## 4. Modificaciones Requeridas en Código Existente

### 4.1 Archivo: src/workspaces/routes.py

**Agregar nuevos endpoints**:
- Implementar `get_workspace_details(workspace_id)`
- Implementar `create_personal_workspace()`
- Implementar `update_workspace(workspace_id)`
- Implementar `create_study_plan(workspace_id)`

### 4.2 Archivo: src/members/services.py

**Agregar nuevos métodos**:
- `create_personal_workspace(user_id, workspace_data)`
- `update_workspace_info(workspace_id, update_data)`
- `get_workspace_by_id(workspace_id, user_id)`

### 4.3 Archivo: src/shared/decorators.py

**Modificar decoradores existentes**:
- Actualizar `@role_required` para considerar `workspace_type`
- Agregar `@workspace_required` para validar acceso a workspace específico
- Implementar filtros automáticos por workspace en consultas

## 5. Casos de Uso y Flujos

### 5.1 Creación de Workspace Personal
1. Usuario hace clic en "Crear Workspace Personal"
2. Frontend llama a `POST /api/workspaces/personal`
3. Backend crea membresía en instituto genérico
4. Si es profesor, se crea clase personal automáticamente
5. Frontend actualiza lista de workspaces
6. Usuario puede cambiar al nuevo workspace

### 5.2 Generación de Plan de Estudio Individual
1. Estudiante en workspace individual accede a "Mi Plan de Estudio"
2. Frontend llama a `POST /api/workspaces/{id}/study-plan`
3. Backend crea StudyPlan y encola generación
4. Sistema genera módulos virtuales personalizados
5. Estudiante recibe notificación cuando está listo

### 5.3 Filtrado de Datos por Workspace
1. Usuario cambia a workspace individual
2. Token JWT incluye `workspace_type` y `class_id`
3. Todas las consultas posteriores se filtran automáticamente
4. Usuario solo ve sus propios datos
5. No hay exposición de datos de otros usuarios

## 6. Consideraciones de Seguridad

### 6.1 Validación de Permisos
- Verificar siempre que el usuario pertenece al workspace antes de cualquier operación
- Validar que el workspace_type en el token coincide con el tipo real en BD
- Implementar rate limiting en endpoints de creación

### 6.2 Aislamiento de Datos
- Garantizar que workspaces individuales no expongan datos de otros usuarios
- Implementar filtros a nivel de base de datos, no solo en aplicación
- Auditar todas las consultas que involucren el instituto genérico

### 6.3 Integridad de Datos
- Validar que no se creen workspaces duplicados del mismo tipo
- Mantener consistencia entre membresías y clases asociadas
- Implementar transacciones para operaciones que afecten múltiples colecciones

## 7. Plan de Implementación

### Fase 1: Endpoints Básicos (Prioridad Alta)
1. Implementar `GET /api/workspaces/{workspaceId}`
2. Implementar `POST /api/workspaces/personal`
3. Implementar `PATCH /api/workspaces/{workspaceId}`
4. Agregar filtros básicos de permisos

### Fase 2: Funcionalidad Avanzada (Prioridad Media)
1. Implementar `POST /api/workspaces/{id}/study-plan`
2. Integrar con sistema de generación automática
3. Implementar filtros avanzados por workspace_type

### Fase 3: Optimización y Seguridad (Prioridad Baja)
1. Optimizar consultas con filtros
2. Implementar auditoría de accesos
3. Agregar métricas y monitoreo

## 8. Testing y Validación

### 8.1 Tests Unitarios
- Probar cada endpoint con diferentes tipos de workspace
- Validar filtros de permisos
- Probar casos de error y validaciones

### 8.2 Tests de Integración
- Probar flujo completo de creación de workspace
- Validar cambio entre workspaces
- Probar generación de planes de estudio

### 8.3 Tests End-to-End
- Probar desde frontend la funcionalidad completa
- Validar que no se exponen datos entre usuarios
- Probar rendimiento con múltiples workspaces

Este documento técnico proporciona la especificación completa para implementar los endpoints faltantes y resolver las inconsistencias identificadas en el frontend.