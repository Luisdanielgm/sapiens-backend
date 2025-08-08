# Plan Completo de Implementación: Unificación de Colecciones de Planes de Estudio

## 1. Contexto del Problema

### 1.1 Situación Actual
Actualmente el sistema SapiensAI maneja dos colecciones separadas para planes de estudio:

- **`study_plans_per_subject`**: Colección principal utilizada por `StudyPlanService` para planes de estudio institucionales
- **`study_plans`**: Colección secundaria utilizada por `WorkspaceService` para planes de estudio personales de workspaces

### 1.2 Problemas Identificados

#### Error 404 en Endpoint Virtual
- El endpoint `/api/workspaces/{workspace_id}/study-plans/{study_plan_id}` retorna error 404
- Causa: `StudyPlanService.get_study_plan()` busca en `study_plans_per_subject` pero los planes personales están en `study_plans`
- Impacto: Funcionalidad de workspaces personales completamente rota

#### Duplicación de Lógica
- Dos servicios manejan conceptos similares con lógicas diferentes
- `StudyPlanService`: Maneja planes institucionales con estructura compleja
- `WorkspaceService`: Maneja planes personales con estructura simplificada
- Resultado: Código duplicado, mantenimiento complejo, inconsistencias

#### Inconsistencias de Datos
- Diferentes esquemas de datos para el mismo concepto
- `study_plans_per_subject`: Usa `author_id`, `institute_id`
- `study_plans`: Usa `user_id`, `workspace_id`
- Dificultad para consultas unificadas y reportes

#### Escalabilidad Limitada
- Imposible implementar funcionalidades que requieran vista unificada
- Dificultad para migrar planes entre contextos (personal ↔ institucional)
- Complejidad creciente al agregar nuevos tipos de planes

## 2. Justificación Técnica para la Unificación

### 2.1 Beneficios Inmediatos
- **Resolución del Error 404**: Un solo punto de acceso para todos los planes
- **Simplificación del Código**: Eliminación de lógica duplicada
- **Consistencia de Datos**: Un solo esquema para todos los planes
- **Mantenimiento Reducido**: Menos puntos de falla y actualización

### 2.2 Beneficios a Largo Plazo
- **Escalabilidad**: Fácil adición de nuevos tipos de planes
- **Flexibilidad**: Migración fluida entre contextos
- **Reportes Unificados**: Consultas simples para analytics
- **Performance**: Menos consultas cruzadas entre colecciones

### 2.3 Riesgos de No Unificar
- Crecimiento exponencial de la complejidad
- Más errores similares al 404 actual
- Dificultad para implementar nuevas funcionalidades
- Deuda técnica acumulativa

## 3. Solución Propuesta: Extensión de study_plans_per_subject

### 3.1 Estrategia Seleccionada
**Extender `study_plans_per_subject`** agregando campos mínimos necesarios para soportar planes personales.

### 3.2 Campos a Agregar
```javascript
{
  // Campos existentes en study_plans_per_subject
  "_id": ObjectId,
  "title": String,
  "description": String,
  "author_id": String,
  "institute_id": String,
  "subject_id": String,
  "modules": Array,
  "created_at": Date,
  "updated_at": Date,
  
  // NUEVOS CAMPOS PARA UNIFICACIÓN
  "workspace_id": String,     // Opcional: ID del workspace (solo para planes personales)
  "is_personal": Boolean,     // Requerido: true para planes personales, false para institucionales
  "objectives": Array        // Opcional: objetivos específicos (migrado desde study_plans)
}
```

### 3.3 Lógica de Identificación
- **Planes Institucionales**: `is_personal: false`, `workspace_id: null`
- **Planes Personales**: `is_personal: true`, `workspace_id: "xxx"`
- **Compatibilidad**: `author_id` reemplaza a `user_id` en planes personales

## 4. Plan de Eliminación de Referencias a study_plans

### 4.1 Archivos a Modificar

#### src/workspaces/services.py
- **Eliminar funciones**:
  - `create_personal_study_plan()`
  - `create_personal_study_plan_with_title()`
  - `get_personal_study_plans()`
  - `get_student_study_plan()`
  - Todas las referencias a colección `study_plans`

- **Reemplazar con**:
  - Llamadas a `StudyPlanService` con filtros `is_personal: true`
  - Uso de `study_plans_per_subject` únicamente

#### src/workspaces/routes.py
- **Modificar endpoints**:
  - `/api/workspaces/{workspace_id}/study-plans/` → Usar `StudyPlanService`
  - `/api/workspaces/{workspace_id}/study-plans/{study_plan_id}` → Usar `StudyPlanService`
  - Mantener misma interfaz externa, cambiar implementación interna

#### src/study_plans/services.py
- **Agregar métodos**:
  - `create_personal_study_plan()`
  - `get_personal_study_plans_by_workspace()`
  - Filtros para `is_personal` en métodos existentes

#### src/study_plans/models.py
- **Actualizar modelo `StudyPlanPerSubject`**:
  - Agregar campos `workspace_id`, `is_personal`, `objectives`
  - Mantener retrocompatibilidad

### 4.2 Scripts y Migraciones
- **Eliminar scripts obsoletos**:
  - `setup_personal_workspace_collections.py`
  - Cualquier script que cree/modifique colección `study_plans`

### 4.3 Tests
- **Actualizar tests existentes**:
  - `test_workspaces_endpoints.py`
  - `test_integration_workspaces.py`
- **Eliminar tests específicos** de colección `study_plans`

## 5. Migración de Datos

### 5.1 Script de Migración
```python
# scripts/migrate_unify_study_plans.py

def migrate_study_plans_to_unified():
    """
    Migra todos los documentos de 'study_plans' a 'study_plans_per_subject'
    """
    
    # 1. Obtener todos los documentos de study_plans
    old_plans = db.study_plans.find({})
    
    # 2. Transformar y insertar en study_plans_per_subject
    for plan in old_plans:
        unified_plan = {
            "title": plan.get("title", "Plan Personal"),
            "description": plan.get("description", ""),
            "author_id": plan.get("user_id"),  # user_id → author_id
            "workspace_id": plan.get("workspace_id"),
            "is_personal": True,
            "objectives": plan.get("objectives", []),
            "institute_id": plan.get("institute_id"),
            "subject_id": None,  # Los planes personales no tienen subject_id
            "modules": [],  # Inicializar vacío, se puede poblar después
            "created_at": plan.get("created_at"),
            "updated_at": plan.get("updated_at", datetime.utcnow())
        }
        
        db.study_plans_per_subject.insert_one(unified_plan)
    
    # 3. Verificar migración
    old_count = db.study_plans.count_documents({})
    new_count = db.study_plans_per_subject.count_documents({"is_personal": True})
    
    if old_count == new_count:
        print(f"Migración exitosa: {old_count} planes migrados")
        return True
    else:
        print(f"Error en migración: {old_count} originales vs {new_count} migrados")
        return False

def rollback_migration():
    """
    Rollback: elimina planes personales de study_plans_per_subject
    """
    result = db.study_plans_per_subject.delete_many({"is_personal": True})
    print(f"Rollback completado: {result.deleted_count} documentos eliminados")
```

### 5.2 Validación Post-Migración
```python
def validate_migration():
    """
    Valida que la migración fue exitosa
    """
    
    # Verificar conteos
    old_count = db.study_plans.count_documents({})
    new_personal_count = db.study_plans_per_subject.count_documents({"is_personal": True})
    
    # Verificar campos requeridos
    invalid_docs = db.study_plans_per_subject.count_documents({
        "is_personal": True,
        "$or": [
            {"author_id": {"$exists": False}},
            {"workspace_id": {"$exists": False}}
        ]
    })
    
    return {
        "migration_complete": old_count == new_personal_count,
        "invalid_documents": invalid_docs,
        "total_migrated": new_personal_count
    }
```

## 6. Cambios en Código

### 6.1 Modificaciones en StudyPlanService

```python
# src/study_plans/services.py

class StudyPlanService:
    
    def create_personal_study_plan(self, user_id: str, workspace_id: str, 
                                 title: str, description: str, 
                                 objectives: List[str] = None):
        """
        Crea un plan de estudio personal para un workspace
        """
        study_plan = {
            "title": title,
            "description": description,
            "author_id": user_id,
            "workspace_id": workspace_id,
            "is_personal": True,
            "objectives": objectives or [],
            "institute_id": None,
            "subject_id": None,
            "modules": [],
            "created_at": datetime.utcnow(),
            "updated_at": datetime.utcnow()
        }
        
        result = db.study_plans_per_subject.insert_one(study_plan)
        return str(result.inserted_id)
    
    def get_personal_study_plans_by_workspace(self, workspace_id: str):
        """
        Obtiene todos los planes personales de un workspace
        """
        return list(db.study_plans_per_subject.find({
            "workspace_id": workspace_id,
            "is_personal": True
        }))
    
    def get_study_plan(self, study_plan_id: str):
        """
        Obtiene un plan de estudio (institucional o personal)
        """
        return db.study_plans_per_subject.find_one({
            "_id": ObjectId(study_plan_id)
        })
```

### 6.2 Modificaciones en WorkspaceService

```python
# src/workspaces/services.py

from src.study_plans.services import StudyPlanService

class WorkspaceService:
    def __init__(self):
        self.study_plan_service = StudyPlanService()
    
    def create_personal_study_plan_with_title(self, user_id: str, 
                                            workspace_id: str, 
                                            title: str, description: str):
        """
        Delega la creación a StudyPlanService
        """
        return self.study_plan_service.create_personal_study_plan(
            user_id=user_id,
            workspace_id=workspace_id,
            title=title,
            description=description
        )
    
    def get_personal_study_plans(self, workspace_id: str):
        """
        Delega la consulta a StudyPlanService
        """
        return self.study_plan_service.get_personal_study_plans_by_workspace(
            workspace_id
        )
```

### 6.3 Actualización de Rutas

```python
# src/workspaces/routes.py

@router.get("/api/workspaces/{workspace_id}/study-plans/{study_plan_id}")
def get_workspace_study_plan(workspace_id: str, study_plan_id: str):
    """
    Obtiene un plan de estudio específico del workspace
    """
    study_plan_service = StudyPlanService()
    
    # Obtener el plan
    plan = study_plan_service.get_study_plan(study_plan_id)
    
    if not plan:
        raise HTTPException(status_code=404, detail="Plan de estudio no encontrado")
    
    # Verificar que pertenece al workspace (solo para planes personales)
    if plan.get("is_personal") and plan.get("workspace_id") != workspace_id:
        raise HTTPException(status_code=403, detail="Plan no pertenece a este workspace")
    
    return plan
```

## 7. Testing y Validación

### 7.1 Tests Unitarios
```python
# tests/test_unified_study_plans.py

def test_create_personal_study_plan():
    """Test creación de plan personal"""
    service = StudyPlanService()
    
    plan_id = service.create_personal_study_plan(
        user_id="user123",
        workspace_id="workspace456",
        title="Mi Plan Personal",
        description="Descripción del plan"
    )
    
    # Verificar que se creó correctamente
    plan = service.get_study_plan(plan_id)
    assert plan["is_personal"] == True
    assert plan["workspace_id"] == "workspace456"
    assert plan["author_id"] == "user123"

def test_get_workspace_study_plan_endpoint():
    """Test endpoint que antes fallaba con 404"""
    # Crear plan personal
    plan_id = create_test_personal_plan()
    
    # Probar endpoint
    response = client.get(f"/api/workspaces/workspace456/study-plans/{plan_id}")
    
    assert response.status_code == 200
    assert response.json()["is_personal"] == True
```

### 7.2 Tests de Integración
```python
def test_migration_integration():
    """Test completo de migración"""
    
    # 1. Crear datos de prueba en study_plans
    create_test_data_in_old_collection()
    
    # 2. Ejecutar migración
    success = migrate_study_plans_to_unified()
    assert success == True
    
    # 3. Verificar que endpoints funcionan
    test_all_workspace_endpoints()
    
    # 4. Verificar integridad de datos
    validate_data_integrity()
```

### 7.3 Tests de Regresión
- Verificar que funcionalidad institucional no se afecte
- Confirmar que todos los endpoints de workspaces funcionan
- Validar que no hay pérdida de datos

## 8. Plan de Implementación

### 8.1 Fase 1: Preparación (30 minutos)
1. **Backup de datos**
   - Exportar colección `study_plans`
   - Exportar colección `study_plans_per_subject`

2. **Crear rama de desarrollo**
   ```bash
   git checkout -b feature/unify-study-plans
   ```

### 8.2 Fase 2: Modificación del Modelo (15 minutos)
1. **Actualizar `src/study_plans/models.py`**
   - Agregar campos `workspace_id`, `is_personal`, `objectives`
   - Mantener retrocompatibilidad

### 8.3 Fase 3: Migración de Datos (20 minutos)
1. **Crear script de migración**
   - `scripts/migrate_unify_study_plans.py`

2. **Ejecutar migración en desarrollo**
   ```bash
   python scripts/migrate_unify_study_plans.py
   ```

3. **Validar migración**
   - Verificar conteos
   - Validar integridad de datos

### 8.4 Fase 4: Modificación de Servicios (45 minutos)
1. **Actualizar `StudyPlanService`** (25 min)
   - Agregar métodos para planes personales
   - Modificar métodos existentes para soportar filtros

2. **Actualizar `WorkspaceService`** (20 min)
   - Eliminar métodos obsoletos
   - Delegar a `StudyPlanService`

### 8.5 Fase 5: Actualización de Rutas (15 minutos)
1. **Modificar `src/workspaces/routes.py`**
   - Actualizar endpoints para usar `StudyPlanService`
   - Mantener misma interfaz externa

### 8.6 Fase 6: Testing (30 minutos)
1. **Tests unitarios** (15 min)
2. **Tests de integración** (15 min)
3. **Validación manual de endpoints** (10 min)

### 8.7 Fase 7: Limpieza (15 minutos)
1. **Eliminar código obsoleto**
   - Funciones no utilizadas en `WorkspaceService`
   - Scripts obsoletos

2. **Actualizar documentación**

## 9. Estimación de Tiempo y Riesgos

### 9.1 Estimación de Tiempo
- **Tiempo total estimado**: 2.5 - 3 horas
- **Tiempo de desarrollo**: 2 horas
- **Tiempo de testing**: 30 minutos
- **Tiempo de validación**: 30 minutos

### 9.2 Riesgos y Mitigaciones

#### Riesgo Alto: Pérdida de Datos
- **Mitigación**: Backup completo antes de iniciar
- **Plan B**: Script de rollback preparado

#### Riesgo Medio: Endpoints Rotos
- **Mitigación**: Tests exhaustivos antes de deploy
- **Plan B**: Mantener código anterior en rama separada

#### Riesgo Bajo: Performance
- **Mitigación**: Índices apropiados en nuevos campos
- **Monitoreo**: Verificar tiempos de respuesta post-deploy

### 9.3 Criterios de Éxito
1. ✅ Error 404 resuelto
2. ✅ Todos los tests pasan
3. ✅ No pérdida de datos
4. ✅ Performance mantenida
5. ✅ Funcionalidad institucional intacta

## 10. Post-Implementación

### 10.1 Monitoreo
- Verificar logs de errores
- Monitorear performance de endpoints
- Validar que no hay consultas a colección obsoleta

### 10.2 Limpieza Final
- Después de 1 semana sin issues:
  - Eliminar colección `study_plans`
  - Remover backups temporales
  - Actualizar documentación de API

### 10.3 Beneficios Realizados
- ✅ Arquitectura simplificada
- ✅ Mantenimiento reducido
- ✅ Base sólida para futuras funcionalidades
- ✅ Consistencia de datos mejorada

Este plan proporciona una ruta clara y de bajo riesgo para resolver el problema actual y establecer una base sólida para el crecimiento futuro del sistema.