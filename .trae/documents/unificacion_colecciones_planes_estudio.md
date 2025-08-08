# Unificación de Colecciones de Planes de Estudio

## 1. Problema Actual

Actualmente el sistema maneja dos colecciones separadas para planes de estudio:

* **`study_plans_per_subject`**: Utilizada por el sistema principal de planes de estudio institucionales

* **`study_plans`**: Utilizada por workspaces personales para estudiantes individuales

Esta separación causa problemas de compatibilidad, especialmente cuando el endpoint `/api/virtual/progressive-generation` busca planes en `study_plans_per_subject` pero los workspaces almacenan planes en `study_plans`.

## 2. Análisis Estructural

### 2.1 Estructura de `study_plans_per_subject`

Basada en el modelo `StudyPlanPerSubject`:

```javascript
{
  "_id": ObjectId,
  "version": String,
  "author_id": ObjectId,
  "name": String,
  "description": String,
  "status": String, // "draft", "approved", etc.
  "subject_id": ObjectId,
  "approval_date": Date,
  "created_at": Date
}
```

### 2.2 Estructura de `study_plans` (Workspaces)

Basada en las funciones de workspaces:

```javascript
{
  "_id": ObjectId,
  "user_id": ObjectId,
  "workspace_id": ObjectId,
  "title": String, // equivalente a "name"
  "description": String,
  "objectives": Array[String],
  "status": String, // "generating", "completed", etc.
  "pdf_content": String,
  "document_url": String,
  "progress": Number,
  "created_at": Date
}
```

### 2.3 Diferencias Clave

| Campo          | study\_plans\_per\_subject | study\_plans (workspaces)     |
| -------------- | -------------------------- | ----------------------------- |
| Identificación | `name`                     | `title`                       |
| Contexto       | `subject_id`, `author_id`  | `user_id`, `workspace_id`     |
| Aprobación     | `approval_date`, `version` | No aplica                     |
| Objetivos      | No explícito               | `objectives` array            |
| Contenido PDF  | No aplica                  | `pdf_content`, `document_url` |
| Progreso       | No explícito               | `progress`                    |

## 3. Propuesta de Unificación

### 3.1 Estructura Unificada

Crear una sola colección `study_plans` que soporte ambos casos de uso:

```javascript
{
  "_id": ObjectId,
  "name": String, // título del plan
  "description": String,
  "status": String,
  "created_at": Date,
  
  // Campos institucionales (opcionales)
  "version": String,
  "author_id": ObjectId,
  "subject_id": ObjectId,
  "approval_date": Date,
  
  // Campos de workspace (opcionales)
  "user_id": ObjectId,
  "workspace_id": ObjectId,
  "objectives": Array[String],
  "pdf_content": String,
  "document_url": String,
  "progress": Number,
  
  // Campo discriminador
  "plan_type": String // "institutional" | "personal"
}
```

### 3.2 Ventajas de la Unificación

1. **Compatibilidad**: Los endpoints virtuales funcionarán con ambos tipos de planes
2. **Simplicidad**: Una sola colección reduce complejidad
3. **Flexibilidad**: Permite evolución futura sin duplicación
4. **Consistencia**: Misma lógica de validación para todos los planes

## 4. Estrategia de Migración

### 4.1 Fase 1: Preparación

1. **Crear nueva colección unificada** con la estructura propuesta
2. **Migrar datos existentes**:

   * Copiar `study_plans_per_subject` con `plan_type: "institutional"`

   * Copiar `study_plans` con `plan_type: "personal"`
3. **Crear índices necesarios**:

   ```javascript
   db.study_plans.createIndex({ "plan_type": 1 })
   db.study_plans.createIndex({ "user_id": 1, "workspace_id": 1 })
   db.study_plans.createIndex({ "subject_id": 1, "status": 1 })
   ```

### 4.2 Fase 2: Actualización de Código

#### 4.2.1 Modificar `StudyPlanService`

```python
# src/study_plans/services.py
class StudyPlanService(VerificationBaseService):
    def __init__(self):
        super().__init__(collection_name="study_plans")  # Cambiar colección
    
    def check_study_plan_exists(self, plan_id: str) -> bool:
        """Verificar existencia en colección unificada"""
        return self.collection.find_one({"_id": ObjectId(plan_id)}) is not None
    
    def create_institutional_plan(self, plan_data: dict) -> str:
        """Crear plan institucional"""
        plan_data["plan_type"] = "institutional"
        return self.create_study_plan(plan_data)
```

#### 4.2.2 Actualizar `WorkspaceService`

```python
# src/workspaces/services.py
def create_personal_study_plan(self, workspace_id: str, user_id: str, ...):
    study_plan_data = {
        "name": title,  # Usar "name" en lugar de "title"
        "description": description,
        "user_id": ObjectId(user_id),
        "workspace_id": ObjectId(workspace_id),
        "plan_type": "personal",  # Agregar discriminador
        "objectives": objectives or [],
        "status": "generating",
        "created_at": datetime.utcnow()
    }
    
    # Usar colección unificada
    result = self.db.study_plans.insert_one(study_plan_data)
```

#### 4.2.3 Actualizar Endpoints Virtuales

```python
# src/virtual/routes.py
# No requiere cambios, ya que usa check_study_plan_exists()
# que ahora buscará en la colección unificada
```

### 4.3 Fase 3: Validación y Limpieza

1. **Verificar funcionalidad** de todos los endpoints
2. **Ejecutar tests** para ambos tipos de planes
3. **Eliminar colecciones antiguas** una vez confirmada la migración
4. **Actualizar documentación** y modelos

## 5. Cambios Específicos Requeridos

### 5.1 Archivos a Modificar

1. **`src/study_plans/services.py`**:

   * Cambiar `collection_name` a "study\_plans"

   * Agregar métodos específicos para planes institucionales y personales

   * Actualizar queries para incluir filtros por `plan_type`

2. **`src/workspaces/services.py`**:

   * Cambiar referencias de `self.db.study_plans` por la nueva estructura

   * Usar campo `name` en lugar de `title`

   * Agregar `plan_type: "personal"`

3. **`src/study_plans/models.py`**:

   * Crear nuevo modelo `UnifiedStudyPlan`

   * Mantener compatibilidad con modelos existentes

4. **`src/shared/standardization.py`**:

   * Actualizar `check_study_plan_exists` para usar colección unificada

### 5.2 Script de Migración

```python
# scripts/migrate_study_plans.py
def migrate_study_plans():
    db = get_db()
    
    # Migrar planes institucionales
    institutional_plans = db.study_plans_per_subject.find({})
    for plan in institutional_plans:
        plan["plan_type"] = "institutional"
        plan["name"] = plan.get("name", "Plan sin título")
        db.study_plans.insert_one(plan)
    
    # Migrar planes personales
    personal_plans = db.study_plans.find({})
    for plan in personal_plans:
        plan["plan_type"] = "personal"
        if "title" in plan:
            plan["name"] = plan.pop("title")
        db.study_plans_unified.insert_one(plan)
    
    # Renombrar colección
    db.study_plans.rename("study_plans_backup")
    db.study_plans_unified.rename("study_plans")
```

## 6. Beneficios Esperados

1. **Resolución del error 404**: Los workspaces podrán usar el endpoint virtual
2. **Arquitectura simplificada**: Una sola fuente de verdad para planes
3. **Mantenimiento reducido**: Menos duplicación de lógica
4. **Escalabilidad mejorada**: Estructura preparada para nuevos tipos de planes
5. **Consistencia de datos**: Mismas validaciones y estructura para todos los planes

## 7. Consideraciones de Implementación

* **Backward compatibility**: Mantener APIs existentes durante transición

* **Testing exhaustivo**: Verificar ambos flujos (institucional y personal)

* **Rollback plan**: Mantener backups de colecciones originales

* **Monitoreo**: Supervisar rendimiento post-migración

* **Documentación**: Actualizar documentación de API y modelos

