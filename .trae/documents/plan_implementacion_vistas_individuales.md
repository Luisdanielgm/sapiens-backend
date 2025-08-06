# Plan de Implementación: Vistas Individuales para Estudiantes y Profesores

## 1. Resumen Ejecutivo

Este documento detalla el plan de implementación para completar las vistas individuales de estudiantes (`INDIVIDUAL_STUDENT`) y profesores (`INDIVIDUAL_TEACHER`) en el sistema de workspaces de SapiensAI. El plan se enfoca en las modificaciones necesarias del backend para soportar el aislamiento de datos y la personalización de funcionalidades según el tipo de workspace.

### Objetivos Principales

* Implementar filtrado automático por `workspace_type` en todos los endpoints relevantes

* Modificar el sistema de autorización para considerar roles específicos del workspace

* Crear nuevos endpoints para funcionalidades específicas de workspaces individuales

* Asegurar el aislamiento completo de datos entre workspaces

## 2. Análisis del Estado Actual del Backend

### 2.1 Funcionalidades Ya Implementadas ✅

#### Sistema de Workspaces Base

* **WorkspaceService**: Servicio completo para gestión de workspaces

* **Endpoints básicos**: `/api/workspaces/`, `/api/workspaces/<workspace_id>`, `/api/workspaces/personal`

* **Sistema de membresías**: Gestión de pertenencia a workspaces a través de `institute_members`

* **JWT con claims**: Tokens incluyen `workspace_type`, `workspace_id`, `role`

* **Decoradores de autorización**: `@workspace_access_required`, `@workspace_owner_required`

#### Tipos de Workspace Soportados

* `INSTITUTE`: Workspaces institucionales tradicionales

* `INDIVIDUAL_STUDENT`: Workspaces personales para estudiantes

* `INDIVIDUAL_TEACHER`: Workspaces personales para profesores

#### Instituto Genérico

* **Academia Sapiens**: Instituto genérico para workspaces individuales

* **Creación automática**: Se crea automáticamente si no existe

* **Aislamiento**: Permite separar workspaces individuales de institucionales

### 2.2 Funcionalidades Parcialmente Implementadas ⚠️

#### Filtrado por Workspace Type

* **Estado**: Estructura básica existe pero no implementada en todos los endpoints

* **Faltante**: Aplicación sistemática en dashboards, clases, perfiles, miembros

* **Impacto**: Datos no están completamente aislados entre workspaces

#### Sistema de Autorización Contextual

* **Estado**: Decoradores básicos implementados

* **Faltante**: Consideración de `workspace_role` vs `user.role`

* **Impacto**: Permisos incorrectos en workspaces individuales

### 2.3 Funcionalidades No Implementadas ❌

#### Endpoints Específicos para Workspaces Individuales

* **Faltante**: `POST /api/workspaces/{workspace_id}/study-plan`

* **Faltante**: `GET /api/workspaces/{workspace_id}/progress`

* **Impacto**: Funcionalidades avanzadas no disponibles

#### Filtrado Automático en Endpoints Existentes

* **Faltante**: Modificaciones en `/api/dashboards/`, `/api/classes/`, `/api/profiles/`, `/api/members/`

* **Impacto**: Vistas no personalizadas según workspace type

## 3. Plan Detallado de Implementación

### 3.1 Modificaciones en Endpoints Existentes (Prioridad Alta)

#### 3.1.1 Endpoints de Dashboard

**Archivos afectados**: `src/dashboards/routes.py`, `src/dashboards/services.py`

**Modificaciones requeridas**:

```python
# En src/dashboards/routes.py
@dashboards_bp.route('/student/<student_id>', methods=['GET'])
@APIRoute.standard(auth_required_flag=True)
@workspace_type_required(['INDIVIDUAL_STUDENT', 'INSTITUTE'])
def get_student_dashboard(student_id):
    """Dashboard de estudiante con filtrado por workspace"""
    jwt_claims = get_jwt()
    workspace_type = jwt_claims.get('workspace_type')
    workspace_id = jwt_claims.get('workspace_id')
    
    # Aplicar filtros según workspace type
    dashboard_data = DashboardService.get_student_dashboard(
        student_id=student_id,
        workspace_type=workspace_type,
        workspace_id=workspace_id
    )
    
    return APIRoute.success(data=dashboard_data)

@dashboards_bp.route('/teacher/<teacher_id>', methods=['GET'])
@APIRoute.standard(auth_required_flag=True)
@workspace_type_required(['INDIVIDUAL_TEACHER', 'INSTITUTE'])
def get_teacher_dashboard(teacher_id):
    """Dashboard de profesor con filtrado por workspace"""
    jwt_claims = get_jwt()
    workspace_type = jwt_claims.get('workspace_type')
    workspace_id = jwt_claims.get('workspace_id')
    
    dashboard_data = DashboardService.get_teacher_dashboard(
        teacher_id=teacher_id,
        workspace_type=workspace_type,
        workspace_id=workspace_id
    )
    
    return APIRoute.success(data=dashboard_data)
```

**Modificaciones en servicio**:

```python
# En src/dashboards/services.py
class DashboardService:
    @staticmethod
    def get_student_dashboard(student_id: str, workspace_type: str, workspace_id: str) -> Dict:
        """Obtener dashboard de estudiante filtrado por workspace"""
        if workspace_type == 'INDIVIDUAL_STUDENT':
            # Solo mostrar datos del workspace personal
            return DashboardService._get_individual_student_dashboard(student_id, workspace_id)
        else:
            # Dashboard institucional tradicional
            return DashboardService._get_institute_student_dashboard(student_id, workspace_id)
    
    @staticmethod
    def get_teacher_dashboard(teacher_id: str, workspace_type: str, workspace_id: str) -> Dict:
        """Obtener dashboard de profesor filtrado por workspace"""
        if workspace_type == 'INDIVIDUAL_TEACHER':
            # Solo mostrar clases propias
            return DashboardService._get_individual_teacher_dashboard(teacher_id, workspace_id)
        else:
            # Dashboard institucional tradicional
            return DashboardService._get_institute_teacher_dashboard(teacher_id, workspace_id)
```

#### 3.1.2 Endpoints de Clases

**Archivos afectados**: `src/classes/routes.py`, `src/classes/services.py`

**Modificaciones requeridas**:

```python
# En src/classes/routes.py
@classes_bp.route('/teacher/<teacher_id>', methods=['GET'])
@APIRoute.standard(auth_required_flag=True)
@workspace_type_required(['INDIVIDUAL_TEACHER', 'INSTITUTE'])
def get_teacher_classes(teacher_id):
    """Obtener clases de profesor filtradas por workspace"""
    jwt_claims = get_jwt()
    workspace_type = jwt_claims.get('workspace_type')
    workspace_id = jwt_claims.get('workspace_id')
    class_id = jwt_claims.get('class_id')  # Para INDIVIDUAL_TEACHER
    
    classes = ClassService.get_teacher_classes(
        teacher_id=teacher_id,
        workspace_type=workspace_type,
        workspace_id=workspace_id,
        class_id=class_id
    )
    
    return APIRoute.success(data={'classes': classes})

@classes_bp.route('/student/<student_id>', methods=['GET'])
@APIRoute.standard(auth_required_flag=True)
@workspace_type_required(['INDIVIDUAL_STUDENT', 'INSTITUTE'])
def get_student_classes(student_id):
    """Obtener clases de estudiante filtradas por workspace"""
    jwt_claims = get_jwt()
    workspace_type = jwt_claims.get('workspace_type')
    workspace_id = jwt_claims.get('workspace_id')
    
    classes = ClassService.get_student_classes(
        student_id=student_id,
        workspace_type=workspace_type,
        workspace_id=workspace_id
    )
    
    return APIRoute.success(data={'classes': classes})
```

**Modificaciones en servicio**:

```python
# En src/classes/services.py
class ClassService:
    @staticmethod
    def get_teacher_classes(teacher_id: str, workspace_type: str, workspace_id: str, class_id: str = None) -> List[Dict]:
        """Obtener clases de profesor con filtrado por workspace"""
        db = get_db()
        
        if workspace_type == 'INDIVIDUAL_TEACHER':
            # Solo mostrar clases donde created_by = teacher_id o class_id específico
            query = {
                "$or": [
                    {"created_by": ObjectId(teacher_id)},
                    {"_id": ObjectId(class_id)} if class_id else {}
                ]
            }
        else:
            # Filtrar por instituto del workspace
            membership = db.institute_members.find_one({"_id": ObjectId(workspace_id)})
            query = {
                "institute_id": ObjectId(membership["institute_id"]),
                "$or": [
                    {"created_by": ObjectId(teacher_id)},
                    {"teachers": ObjectId(teacher_id)}
                ]
            }
        
        classes = list(db.classes.find(query))
        return [ClassService._format_class_response(cls) for cls in classes]
    
    @staticmethod
    def get_student_classes(student_id: str, workspace_type: str, workspace_id: str) -> List[Dict]:
        """Obtener clases de estudiante con filtrado por workspace"""
        db = get_db()
        
        if workspace_type == 'INDIVIDUAL_STUDENT':
            # Solo mostrar clases asociadas a planes de estudio personales
            study_plans = db.study_plans.find({"user_id": ObjectId(student_id)})
            class_ids = []
            for plan in study_plans:
                if plan.get('class_id'):
                    class_ids.append(plan['class_id'])
            
            query = {"_id": {"$in": class_ids}} if class_ids else {"_id": {"$in": []}}
        else:
            # Filtrar por instituto y membresía del estudiante
            membership = db.institute_members.find_one({"_id": ObjectId(workspace_id)})
            query = {
                "institute_id": ObjectId(membership["institute_id"]),
                "students": ObjectId(student_id)
            }
        
        classes = list(db.classes.find(query))
        return [ClassService._format_class_response(cls) for cls in classes]
```

#### 3.1.3 Endpoints de Perfiles

**Archivos afectados**: `src/profiles/routes.py`, `src/profiles/services.py`

**Modificaciones requeridas**:

```python
# En src/profiles/routes.py
@profiles_bp.route('/student/<user_id>', methods=['GET'])
@APIRoute.standard(auth_required_flag=True)
def get_student_profile(user_id):
    """Obtener perfil de estudiante considerando workspace type"""
    jwt_claims = get_jwt()
    workspace_type = jwt_claims.get('workspace_type')
    
    # Un profesor en workspace INDIVIDUAL_STUDENT debe ver su perfil de estudiante
    profile_data = ProfileService.get_student_profile(
        user_id=user_id,
        workspace_type=workspace_type
    )
    
    return APIRoute.success(data=profile_data)

@profiles_bp.route('/teacher/<user_id>', methods=['GET'])
@APIRoute.standard(auth_required_flag=True)
def get_teacher_profile(user_id):
    """Obtener perfil de profesor considerando workspace type"""
    jwt_claims = get_jwt()
    workspace_type = jwt_claims.get('workspace_type')
    
    profile_data = ProfileService.get_teacher_profile(
        user_id=user_id,
        workspace_type=workspace_type
    )
    
    return APIRoute.success(data=profile_data)
```

#### 3.1.4 Endpoints de Miembros

**Archivos afectados**: `src/members/routes.py`, `src/members/services.py`

**Modificaciones requeridas**:

```python
# En src/members/routes.py
@members_bp.route('/classes/<class_id>/students', methods=['GET'])
@APIRoute.standard(auth_required_flag=True)
@workspace_access_required
def get_class_students(class_id):
    """Obtener estudiantes de clase filtrados por workspace"""
    jwt_claims = get_jwt()
    workspace_type = jwt_claims.get('workspace_type')
    workspace_id = jwt_claims.get('workspace_id')
    
    students = MembershipService.get_class_students(
        class_id=class_id,
        workspace_type=workspace_type,
        workspace_id=workspace_id
    )
    
    return APIRoute.success(data={'students': students})
```

### 3.2 Nuevos Endpoints Requeridos (Prioridad Media)

#### 3.2.1 Plan de Estudio Personal

**Archivo**: `src/workspaces/routes.py`

```python
@workspaces_bp.route('/<workspace_id>/study-plan', methods=['POST'])
@APIRoute.standard(auth_required_flag=True)
@workspace_access_required
@workspace_type_required(['INDIVIDUAL_STUDENT'])
def create_study_plan(workspace_id):
    """Generar plan de estudio personalizado para INDIVIDUAL_STUDENT"""
    try:
        user_id = get_jwt_identity()
        data = request.get_json()
        
        # Validar datos requeridos
        if not data or not data.get('description'):
            return APIRoute.error(ErrorCodes.BAD_REQUEST, "La descripción es requerida")
        
        # Procesar archivo PDF si se proporciona
        pdf_file = request.files.get('pdf_file') if request.files else None
        
        # Crear plan de estudio
        success, message, study_plan_data = WorkspaceService.create_personal_study_plan(
            workspace_id=workspace_id,
            user_id=user_id,
            description=data['description'],
            objectives=data.get('objectives', []),
            pdf_file=pdf_file
        )
        
        if not success:
            return APIRoute.error(ErrorCodes.SERVER_ERROR, message)
        
        return APIRoute.success(
            data=study_plan_data,
            message="Plan de estudio creado exitosamente"
        )
        
    except Exception as e:
        log_error(f"Error creating study plan: {str(e)}", e, "workspaces.routes")
        return APIRoute.error(ErrorCodes.SERVER_ERROR, "No se pudo crear el plan de estudio")
```

#### 3.2.2 Progreso Personal

**Archivo**: `src/workspaces/routes.py`

```python
@workspaces_bp.route('/<workspace_id>/progress', methods=['GET'])
@APIRoute.standard(auth_required_flag=True)
@workspace_access_required
def get_workspace_progress(workspace_id):
    """Obtener progreso específico del workspace individual"""
    try:
        user_id = get_jwt_identity()
        jwt_claims = get_jwt()
        workspace_type = jwt_claims.get('workspace_type')
        
        # Obtener progreso filtrado por workspace
        progress_data = WorkspaceService.get_workspace_progress(
            workspace_id=workspace_id,
            user_id=user_id,
            workspace_type=workspace_type
        )
        
        return APIRoute.success(data=progress_data)
        
    except Exception as e:
        log_error(f"Error getting workspace progress: {str(e)}", e, "workspaces.routes")
        return APIRoute.error(ErrorCodes.SERVER_ERROR, "No se pudo obtener el progreso")
```

### 3.3 Modificaciones en Sistema de Autorización (Prioridad Alta)

#### 3.3.1 Nuevo Decorador @workspace\_type\_required

**Archivo**: `src/shared/decorators.py`

```python
def workspace_type_required(allowed_types: List[str]):
    """Decorador para validar que el workspace type esté en la lista permitida"""
    def decorator(f):
        @wraps(f)
        def decorated_function(*args, **kwargs):
            try:
                jwt_claims = get_jwt()
                workspace_type = jwt_claims.get('workspace_type')
                
                if not workspace_type:
                    return APIRoute.error(ErrorCodes.UNAUTHORIZED, "Workspace type no especificado")
                
                if workspace_type not in allowed_types:
                    return APIRoute.error(
                        ErrorCodes.FORBIDDEN, 
                        f"Workspace type '{workspace_type}' no permitido para esta operación"
                    )
                
                return f(*args, **kwargs)
                
            except Exception as e:
                log_error(f"Workspace type validation error: {str(e)}", e, "decorators")
                return APIRoute.error(ErrorCodes.SERVER_ERROR, "Error de validación de workspace")
        
        return decorated_function
    return decorator
```

#### 3.3.2 Modificación del Decorador @role\_required

**Archivo**: `src/shared/decorators.py`

```python
def role_required(required_roles):
    """Decorador mejorado que considera workspace_role del JWT"""
    if isinstance(required_roles, str):
        required_roles = [required_roles]
    
    def decorator(f):
        @wraps(f)
        def decorated_function(*args, **kwargs):
            try:
                jwt_claims = get_jwt()
                user_id = get_jwt_identity()
                
                # Obtener rol del workspace del JWT (prioritario)
                workspace_role = jwt_claims.get('role')
                workspace_type = jwt_claims.get('workspace_type')
                
                # Si no hay workspace_role, usar rol del usuario
                if not workspace_role:
                    user = get_db().users.find_one({"_id": ObjectId(user_id)})
                    workspace_role = user.get('role') if user else None
                
                if not workspace_role:
                    return APIRoute.error(ErrorCodes.UNAUTHORIZED, "Rol no especificado")
                
                # Normalizar rol
                normalized_role = normalize_role(workspace_role)
                
                # Validar rol
                if normalized_role not in required_roles:
                    return APIRoute.error(
                        ErrorCodes.FORBIDDEN, 
                        f"Rol '{normalized_role}' no tiene permisos para esta operación"
                    )
                
                # Logging para debugging
                log_info(f"Role validation: user={user_id}, workspace_type={workspace_type}, role={normalized_role}")
                
                return f(*args, **kwargs)
                
            except Exception as e:
                log_error(f"Role validation error: {str(e)}", e, "decorators")
                return APIRoute.error(ErrorCodes.SERVER_ERROR, "Error de validación de rol")
        
        return decorated_function
    return decorator
```

#### 3.3.3 Middleware de Filtrado Automático

**Archivo**: `src/shared/middleware.py` (nuevo)

```python
from flask import request, g
from flask_jwt_extended import get_jwt, get_jwt_identity
from bson import ObjectId

class WorkspaceFilterMiddleware:
    """Middleware para aplicar filtros automáticos por workspace"""
    
    @staticmethod
    def apply_workspace_context():
        """Aplicar contexto de workspace a la request actual"""
        try:
            jwt_claims = get_jwt()
            user_id = get_jwt_identity()
            
            # Establecer contexto global de workspace
            g.workspace_context = {
                'user_id': user_id,
                'workspace_id': jwt_claims.get('workspace_id'),
                'workspace_type': jwt_claims.get('workspace_type'),
                'institute_id': jwt_claims.get('institute_id'),
                'class_id': jwt_claims.get('class_id'),
                'role': jwt_claims.get('role')
            }
            
        except Exception:
            # Si no hay JWT válido, establecer contexto vacío
            g.workspace_context = {}
    
    @staticmethod
    def get_workspace_filter() -> Dict[str, Any]:
        """Obtener filtro base para consultas según workspace actual"""
        context = getattr(g, 'workspace_context', {})
        workspace_type = context.get('workspace_type')
        workspace_id = context.get('workspace_id')
        user_id = context.get('user_id')
        
        if not workspace_type or not workspace_id:
            return {}
        
        if workspace_type == 'INDIVIDUAL_STUDENT':
            return {
                'user_id': ObjectId(user_id)
            }
        elif workspace_type == 'INDIVIDUAL_TEACHER':
            return {
                '$or': [
                    {'created_by': ObjectId(user_id)},
                    {'teachers': ObjectId(user_id)}
                ]
            }
        elif workspace_type == 'INSTITUTE':
            return {
                'institute_id': ObjectId(context.get('institute_id'))
            }
        
        return {}
```

### 3.4 Extensiones en WorkspaceService

**Archivo**: `src/workspaces/services.py`

```python
# Agregar al WorkspaceService existente

def create_personal_study_plan(self, workspace_id: str, user_id: str, description: str, 
                              objectives: List[str] = None, pdf_file = None) -> Tuple[bool, str, Dict[str, Any]]:
    """Crear plan de estudio personalizado para workspace individual"""
    try:
        # Validar que es un workspace INDIVIDUAL_STUDENT
        workspace = self.get_workspace_by_id(workspace_id, user_id)
        if workspace['workspace_type'] != 'INDIVIDUAL_STUDENT':
            raise AppException("Solo disponible para workspaces de estudiante individual", AppException.BAD_REQUEST)
        
        # Procesar archivo PDF si se proporciona
        pdf_content = None
        if pdf_file:
            # Aquí iría la lógica de procesamiento de PDF
            pdf_content = self._process_pdf_file(pdf_file)
        
        # Crear plan de estudio
        study_plan_data = {
            "user_id": ObjectId(user_id),
            "workspace_id": ObjectId(workspace_id),
            "description": description,
            "objectives": objectives or [],
            "pdf_content": pdf_content,
            "status": "generating",
            "created_at": datetime.utcnow()
        }
        
        result = self.db.study_plans.insert_one(study_plan_data)
        study_plan_id = str(result.inserted_id)
        
        # Iniciar generación asíncrona (integrar con sistema existente)
        self._trigger_study_plan_generation(study_plan_id, description, objectives)
        
        response_data = {
            "study_plan_id": study_plan_id,
            "status": "generating",
            "message": "Plan de estudio en generación"
        }
        
        return True, "Plan de estudio creado exitosamente", response_data
        
    except Exception as e:
        if isinstance(e, AppException):
            raise
        raise AppException(f"Error al crear plan de estudio: {str(e)}", AppException.INTERNAL_ERROR)

def get_workspace_progress(self, workspace_id: str, user_id: str, workspace_type: str) -> Dict[str, Any]:
    """Obtener progreso específico del workspace"""
    try:
        # Aplicar filtros según tipo de workspace
        if workspace_type == 'INDIVIDUAL_STUDENT':
            return self._get_individual_student_progress(workspace_id, user_id)
        elif workspace_type == 'INDIVIDUAL_TEACHER':
            return self._get_individual_teacher_progress(workspace_id, user_id)
        else:
            return self._get_institute_progress(workspace_id, user_id)
            
    except Exception as e:
        raise AppException(f"Error al obtener progreso: {str(e)}", AppException.INTERNAL_ERROR)

def _get_individual_student_progress(self, workspace_id: str, user_id: str) -> Dict[str, Any]:
    """Obtener progreso de estudiante individual"""
    # Obtener planes de estudio del workspace
    study_plans = list(self.db.study_plans.find({
        "user_id": ObjectId(user_id),
        "workspace_id": ObjectId(workspace_id)
    }))
    
    # Calcular métricas de progreso
    total_topics = 0
    completed_topics = 0
    
    for plan in study_plans:
        # Integrar con sistema de virtual topics existente
        topics = list(self.db.virtual_topics.find({"study_plan_id": plan["_id"]}))
        total_topics += len(topics)
        completed_topics += len([t for t in topics if t.get('status') == 'completed'])
    
    progress_percentage = (completed_topics / total_topics * 100) if total_topics > 0 else 0
    
    return {
        "workspace_id": workspace_id,
        "workspace_type": "INDIVIDUAL_STUDENT",
        "total_study_plans": len(study_plans),
        "total_topics": total_topics,
        "completed_topics": completed_topics,
        "progress_percentage": round(progress_percentage, 2),
        "last_activity": self._get_last_activity_date(user_id)
    }

def _get_individual_teacher_progress(self, workspace_id: str, user_id: str) -> Dict[str, Any]:
    """Obtener progreso de profesor individual"""
    # Obtener clases creadas por el profesor
    classes = list(self.db.classes.find({
        "created_by": ObjectId(user_id),
        "is_personal": True
    }))
    
    # Calcular métricas
    total_students = 0
    active_students = 0
    
    for cls in classes:
        students = cls.get('students', [])
        total_students += len(students)
        # Aquí se podría calcular estudiantes activos basado en última actividad
    
    return {
        "workspace_id": workspace_id,
        "workspace_type": "INDIVIDUAL_TEACHER",
        "total_classes": len(classes),
        "total_students": total_students,
        "active_students": active_students,
        "last_activity": self._get_last_activity_date(user_id)
    }
```

## 4. Cronograma de Desarrollo Estimado

### Semana 1-2: Modificaciones en Endpoints Existentes (Prioridad Alta)

* **Días 1-3**: Modificar endpoints de Dashboard

  * Implementar filtrado por `workspace_type` en `DashboardService`

  * Agregar decorador `@workspace_type_required`

  * Testing de dashboards individuales vs institucionales

* **Días 4-7**: Modificar endpoints de Clases

  * Implementar filtrado en `ClassService.get_teacher_classes()`

  * Implementar filtrado en `ClassService.get_student_classes()`

  * Validar aislamiento de datos entre workspaces

* **Días 8-10**: Modificar endpoints de Perfiles y Miembros

  * Adaptar perfiles según `workspace_type`

  * Filtrar miembros de clases para profesores individuales

  * Testing de coherencia de roles

### Semana 3: Modificaciones en Sistema de Autorización (Prioridad Alta)

* **Días 1-3**: Implementar decoradores mejorados

  * Crear `@workspace_type_required`

  * Modificar `@role_required` para considerar `workspace_role`

  * Testing de permisos por workspace

* **Días 4-5**: Implementar middleware de filtrado

  * Crear `WorkspaceFilterMiddleware`

  * Integrar con endpoints existentes

  * Validar aislamiento automático de datos

### Semana 4: Nuevos Endpoints (Prioridad Media)

* **Días 1-3**: Implementar endpoint de plan de estudio personal

  * `POST /api/workspaces/{workspace_id}/study-plan`

  * Integrar con sistema de generación existente

  * Manejo de archivos PDF

* **Días 4-5**: Implementar endpoint de progreso personal

  * `GET /api/workspaces/{workspace_id}/progress`

  * Métricas específicas por tipo de workspace

  * Integración con sistema de analytics existente

### Semana 5: Testing y Validación

* **Días 1-2**: Testing de integración

  * Validar flujos completos de estudiante individual

  * Validar flujos completos de profesor individual

  * Testing de aislamiento de datos

* **Días 3-4**: Testing de seguridad

  * Validar que no hay filtración de datos entre workspaces

  * Testing de permisos y autorización

  * Validar decoradores y middleware

* **Día 5**: Documentación y deployment

  * Actualizar documentación de API

  * Preparar scripts de migración si es necesario

  * Deployment a ambiente de staging

## 5. Consideraciones Técnicas

### 5.1 Compatibilidad con Sistema Existente

* **Workspaces institucionales**: Mantener funcionalidad existente sin cambios

* **Tokens JWT**: Aprovechar claims existentes (`workspace_type`, `workspace_id`, `role`)

* **Base de datos**: No requiere cambios de esquema, solo nuevos filtros

* **APIs existentes**: Mantener retrocompatibilidad

### 5.2 Rendimiento

* **Índices de base de datos**: Asegurar índices en `workspace_type`, `user_id`, `created_by`

* **Caché**: Implementar caché para consultas frecuentes de workspace

* **Consultas optimizadas**: Usar agregaciones MongoDB para métricas complejas

### 5.3 Seguridad

* **Aislamiento de datos**: Filtrado automático en todas las consultas

* **Validación de permisos**: Decoradores en todos los endpoints sensibles

* **Logging**: Registrar accesos y cambios de workspace para auditoría

### 5.4 Escalabilidad

* **Middleware reutilizable**: Aplicar filtros automáticamente sin modificar cada endpoint

* **Servicios modulares**: Separar lógica de filtrado en servicios especializados

* **Configuración flexible**: Permitir agregar nuevos tipos de workspace fácilmente

## 6. Criterios de Aceptación

### 6.1 Funcionalidad

* ✅ Estudiantes individuales solo ven sus propios datos

* ✅ Profesores individuales solo ven sus clases creadas

* ✅ Dashboards muestran métricas específicas del workspace

* ✅ Perfiles se adaptan según el rol en el workspace actual

* ✅ Planes de estudio personales se pueden crear y gestionar

### 6.2 Seguridad

* ✅ No hay filtración de datos entre workspaces

* ✅ Permisos se aplican correctamente según `workspace_role`

* ✅ Decoradores validan acceso a recursos

* ✅ Middleware aplica filtros automáticamente

### 6.3 Rendimiento

* ✅ Consultas optimizadas con índices apropiados

* ✅ Tiempo de respuesta < 500ms para endpoints principales

* ✅ Caché implementado para consultas frecuentes

### 6.4 Compatibilidad

* ✅ Workspaces institucionales funcionan sin cambios

* ✅ APIs mantienen retrocompatibilidad

* ✅ Frontend puede consumir nuevos endpoints sin problemas

## 7. Riesgos y Mitigaciones

### 7.1 Riesgo: Filtración de Datos

**Mitigación**:

* Implementar middleware de filtrado automático

* Testing exhaustivo de aislamiento

* Code review obligatorio para endpoints que manejan datos sensibles

### 7.2 Riesgo: Degradación de Rendimiento

**Mitigación**:

* Crear índices específicos para filtros de workspace

* Implementar caché para consultas frecuentes

* Monitoreo de performance en producción

### 7.3 Riesgo: Complejidad de Autorización

**Mitigación**:

* Documentar claramente la lógica de permisos

* Crear tests unitarios para todos los decoradores

* Implementar logging detallado para debugging

### 7.4 Riesgo: Incompatibilidad con Frontend

**Mitigación**:

* Coordinar cambios con equipo de frontend

* Mantener versionado de API

* Documentar cambios en formato OpenAPI/Swagger

## 8. Conclusiones

Este plan de implementación proporciona una ruta clara para completar las vistas individuales de estudiantes y profesores en el sistema de workspaces. La estrategia se basa en:

1. **Reutilización máxima** del código y arquitectura existente
2. **Implementación incremental** con prioridades claras
3. **Seguridad por diseño** con aislamiento automático de datos
4. **Compatibilidad garantizada** con funcionalidades existentes

La estimación total de **4-5 semanas** es realista considerando la complejidad de las modificaciones y la necesidad de testing exhaustivo. El enfoque modular permite entregar funcionalidades de forma incremental, reduciendo riesgos y permitiendo feedback temprano.

**Próximos pasos**:

1. Revisar y aprobar este plan con el equipo
2. Crear tickets específicos para cada tarea
3. Configurar ambiente de desarrollo y testing
4. Iniciar implementación siguiendo el cronograma propuesto

