# Análisis de Eliminaciones en Cascada

## Resumen Ejecutivo

Este documento detalla el estado actual de las eliminaciones en cascada en el sistema SapiensAI, identificando dónde están implementadas, dónde faltan, y cómo funcionan.

---

## 1. Sistema Centralizado de Eliminación en Cascada

### 1.1 CascadeDeletionService

**Ubicación:** `src/shared/cascade_deletion_service.py`

Este es el servicio centralizado que maneja eliminaciones en cascada para múltiples entidades relacionadas. Previene datos huérfanos y mantiene la integridad referencial.

#### Funcionamiento:

1. **Definición de Dependencias:** El servicio mantiene un diccionario `dependencies` que mapea cada entidad padre con sus entidades hijas dependientes.

2. **Método Principal:** `delete_with_cascade(collection_name, entity_id, dry_run=False)`
   - Construye un plan de eliminación recursivo
   - Ordena las eliminaciones por nivel de dependencia (hojas primero)
   - Ejecuta las eliminaciones en orden inverso
   - Soporta modo `dry_run` para simular sin ejecutar

3. **Proceso de Eliminación:**
   ```
   - Construye plan recursivo (_build_deletion_plan)
   - Encuentra dependencias (_find_dependent_entities)
   - Ordena colecciones (_get_deletion_order)
   - Elimina entidades en orden (_delete_entities)
   ```

#### Entidades Coberturas por CascadeDeletionService:

| Entidad Padre | Entidades Hijas Eliminadas |
|--------------|----------------------------|
| `study_plans` | modules, study_plan_assignments, virtual_modules |
| `modules` | topics, virtual_modules, virtual_generation_tasks |
| `topics` | topic_contents, virtual_topics, evaluations, content_results |
| `virtual_modules` | virtual_topics, virtual_generation_tasks |
| `virtual_topics` | virtual_topic_contents, parallel_content_generation_tasks |
| `topic_contents` | virtual_topic_contents, content_results |
| `evaluations` | evaluation_submissions, evaluation_resources, content_results |
| `students` | virtual_modules, virtual_topics, virtual_topic_contents, content_results, evaluation_submissions, student_performance |
| `classes` | study_plan_assignments, student_performance, class_statistics, evaluation_analytics |

### 1.2 Rutas API

**Ubicación:** `src/shared/cascade_routes.py`

Endpoints disponibles:
- `DELETE /api/cascade/delete/<collection>/<entity_id>?dry_run=true`
- `POST /api/cascade/cleanup/<collection>?dry_run=true`
- `GET /api/cascade/report/<collection>/<entity_id>`
- `POST /api/cascade/cleanup-all?dry_run=true`

---

## 2. Eliminaciones en Cascada Implementadas Manualmente

### 2.1 StudyPlanService.delete_study_plan()

**Ubicación:** `src/study_plans/services.py:296`

**Implementación:** Eliminación manual en cascada
- ✅ Elimina módulos asociados
- ✅ Elimina temas de los módulos
- ✅ Elimina evaluaciones asociadas a los temas
- ❌ NO elimina: topic_contents, virtual_modules, virtual_topics
- ⚠️ **Problema:** Duplica lógica del CascadeDeletionService pero es incompleto

**Código:**
```python
# Elimina módulos → temas → evaluaciones
# Pero NO elimina topic_contents ni entidades virtuales
```

### 2.2 ModuleService.delete_module()

**Ubicación:** `src/study_plans/services.py:819`

**Implementación:** Eliminación manual parcial
- ✅ Elimina topics asociados
- ✅ Elimina topic_contents de los topics
- ❌ NO elimina: virtual_modules, virtual_generation_tasks, evaluations relacionadas
- ⚠️ **Problema:** Solo elimina una capa de dependencias

### 2.3 TopicService.delete_topic()

**Ubicación:** `src/study_plans/services.py:1302`

**Implementación:** Eliminación manual con lógica especial
- ✅ Elimina topic_contents
- ✅ Gestiona evaluations: elimina si solo vinculadas a este tema, actualiza si vinculadas a múltiples
- ✅ Elimina evaluation_results de evaluaciones eliminadas
- ❌ NO elimina: virtual_topics, virtual_topic_contents, content_results indirectos
- ⚠️ **Problema:** Implementación parcial, falta cobertura completa

### 2.4 ContentService.delete_content()

**Ubicación:** `src/content/services.py:2281`

**Implementación:** Soft delete en cascada
- ✅ Elimina contenidos hijos (soft delete: status="deleted")
- ✅ Elimina contenido principal (soft delete)
- ⚠️ **Nota:** Usa soft delete, no eliminación física

### 2.5 ResourceFolderService.delete_folder()

**Ubicación:** `src/resources/services.py:815`

**Implementación:** Eliminación recursiva completa
- ✅ Elimina recursos asociados recursivamente
- ✅ Elimina subcarpetas recursivamente
- ✅ Elimina carpeta principal
- ✅ **Bien implementado:** Eliminación recursiva completa

### 2.6 EvaluationService.delete_evaluation() (study_plans)

**Ubicación:** `src/study_plans/services.py:1971`

**Implementación:** Eliminación parcial
- ✅ Elimina evaluation_results
- ❌ NO elimina: evaluation_submissions, evaluation_resources, content_results
- ⚠️ **Problema:** Incompleto comparado con CascadeDeletionService

### 2.7 EvaluationService.delete_evaluation() (evaluations)

**Ubicación:** `src/evaluations/services.py:133`

**Implementación:** Eliminación más completa
- ✅ Elimina evaluation_submissions
- ✅ Elimina evaluation_resources
- ✅ Elimina rubrics relacionadas
- ✅ Elimina evaluación principal
- ✅ **Bien implementado:** Cubre las dependencias principales

---

## 3. Eliminaciones SIN Cascada (Solo Validación)

### 3.1 ClassService.delete_class()

**Ubicación:** `src/classes/services.py:337`

**Comportamiento:** Validación previa, NO elimina en cascada
- ❌ Verifica si hay miembros asociados → Bloquea eliminación
- ❌ Verifica si hay subperiodos asociados → Bloquea eliminación
- ✅ Solo elimina si NO hay dependencias
- ⚠️ **Problema:** No elimina dependencias, solo previene eliminación
- 💡 **Recomendación:** Debería usar CascadeDeletionService o eliminar dependencias

### 3.2 PeriodService.delete_period()

**Ubicación:** `src/academic/services.py:164`

**Comportamiento:** Validación previa, NO elimina en cascada
- ❌ Verifica si hay clases asociadas → Bloquea eliminación
- ✅ Solo elimina si NO hay dependencias
- ⚠️ **Problema:** Similar a delete_class, no maneja cascada

### 3.3 Otros Servicios

Los siguientes servicios probablemente tienen comportamiento similar:
- `SectionService.delete_section()`
- `SubjectService.delete_subject()`
- `LevelService.delete_level()`
- `ProgramService.delete_program()`

---

## 4. Problemas Identificados

### 4.1 Inconsistencias

1. **Doble Implementación:**
   - `StudyPlanService.delete_study_plan()` tiene su propia lógica de cascada
   - `CascadeDeletionService` también maneja study_plans
   - **Riesgo:** Comportamiento inconsistente según qué método se use

2. **Cobertura Incompleta:**
   - Muchos métodos `delete_*` manuales no cubren todas las dependencias
   - `CascadeDeletionService` tiene definiciones más completas pero no se usa consistentemente

3. **Falta de Uso del Servicio Centralizado:**
   - Los servicios individuales no están usando `CascadeDeletionService`
   - Cada uno implementa su propia lógica

### 4.2 Entidades Sin Cascada

Las siguientes entidades podrían necesitar eliminación en cascada pero no la tienen:
- `institute` → Debería eliminar: programs, levels, sections, classes, members
- `program` → Debería eliminar: levels, sections, classes
- `level` → Debería eliminar: sections, classes
- `section` → Debería eliminar: classes
- `subperiod` → Debería eliminar: period assignments
- `period` → Debería eliminar: classes (pero actualmente bloquea)

### 4.3 Dependencias No Definidas en CascadeDeletionService

Algunas dependencias no están definidas en el servicio centralizado:
- `topic_contents` → `evaluations` (evaluaciones pueden referenciar contenidos)
- `classes` → `subperiods` (no está en el diccionario)
- `institute` → múltiples entidades académicas

---

## 5. Recomendaciones

### 5.1 Corto Plazo

1. **Unificar Eliminaciones:**
   - Modificar todos los métodos `delete_*` para usar `CascadeDeletionService`
   - Eliminar lógica manual duplicada

2. **Completar CascadeDeletionService:**
   - Agregar dependencias faltantes (institute, program, level, section, subperiod)
   - Agregar dependencias indirectas (topic_contents → evaluations)

3. **Documentar Dependencias:**
   - Crear diagrama de dependencias
   - Documentar qué entidades se eliminan con cada padre

### 5.2 Mediano Plazo

1. **Política de Eliminación:**
   - Decidir cuándo usar cascada vs. validación preventiva
   - Establecer reglas de negocio claras

2. **Testing:**
   - Crear tests para verificar eliminaciones en cascada
   - Verificar que no queden datos huérfanos

3. **Monitoreo:**
   - Implementar auditoría de eliminaciones
   - Alertar sobre datos huérfanos

### 5.3 Largo Plazo

1. **Soft Delete Universal:**
   - Considerar soft delete para todas las entidades críticas
   - Mantener historial de eliminaciones

2. **Transacciones:**
   - Implementar transacciones MongoDB para garantizar atomicidad
   - Rollback en caso de error

---

## 6. Diagrama de Dependencias Actual

```
study_plans
  ├── modules
  │     ├── topics
  │     │     ├── topic_contents
  │     │     │     ├── virtual_topic_contents
  │     │     │     └── content_results
  │     │     ├── virtual_topics
  │     │     ├── evaluations
  │     │     └── content_results (indirecto)
  │     ├── virtual_modules
  │     └── virtual_generation_tasks
  ├── study_plan_assignments
  └── virtual_modules

evaluations
  ├── evaluation_submissions
  ├── evaluation_resources
  └── content_results

students
  ├── virtual_modules
  ├── virtual_topics
  ├── virtual_topic_contents
  ├── content_results
  ├── evaluation_submissions
  └── student_performance

classes
  ├── study_plan_assignments
  ├── student_performance
  ├── class_statistics
  └── evaluation_analytics

resources (carpetas)
  └── resources (recursivo)
```

---

## 7. Casos de Uso de CascadeDeletionService

### Ejemplo 1: Eliminar Study Plan con Cascada

```python
from src.shared.cascade_deletion_service import CascadeDeletionService

service = CascadeDeletionService()

# Simular primero (dry_run)
result = service.delete_with_cascade('study_plans', plan_id, dry_run=True)
print(f"Se eliminarían {result['total_entities']} entidades")

# Ejecutar eliminación real
result = service.delete_with_cascade('study_plans', plan_id, dry_run=False)
print(f"Eliminadas {result['total_deleted']} entidades")
```

### Ejemplo 2: Obtener Reporte de Dependencias

```python
service = CascadeDeletionService()
report = service.get_dependency_report('study_plans', plan_id)

for collection, data in report['dependencies'].items():
    print(f"{collection}: {data['count']} entidades")
```

### Ejemplo 3: Limpiar Datos Huérfanos

```python
service = CascadeDeletionService()

# Limpiar una colección específica
result = service.cleanup_orphaned_data('topic_contents', dry_run=False)

# Limpiar todas las colecciones
# (usar endpoint /api/cascade/cleanup-all)
```

---

## 8. Conclusión

El sistema tiene **dos enfoques paralelos** para eliminaciones en cascada:

1. **CascadeDeletionService** (Centralizado, completo): Bien diseñado pero subutilizado
2. **Métodos delete_* individuales** (Manual, incompleto): Implementaciones parciales y duplicadas

**Estado Actual:**
- ✅ CascadeDeletionService existe y funciona bien
- ⚠️ No se usa consistentemente
- ❌ Muchas eliminaciones manuales son incompletas
- ❌ Algunas entidades solo validan sin eliminar

**Prioridad:**
1. Unificar uso de CascadeDeletionService
2. Completar dependencias faltantes
3. Reemplazar lógica manual



