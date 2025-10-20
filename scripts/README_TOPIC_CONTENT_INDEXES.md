# Índices Únicos para Topic Contents

Estos índices garantizan la integridad de datos en el sistema de generación de contenido de temas, asegurando que no se produzcan duplicados en slides ni en quizzes, y soportando operaciones idempotentes de upsert.

## Índices Implementados

### Índice 1: `idx_unique_slide_topic_order`
- **Tipo**: Índice único parcial
- **Keys**: `(topic_id, order)`
- **Filtro parcial**: `content_type = 'slide'`
- **Propósito**: Garantizar que no existan slides duplicados con el mismo topic_id y order
- **Casos de uso**:
  - Soporta operaciones de upsert idempotente en `create_bulk_slides_skeleton`
  - Previene duplicación accidental en regeneraciones
  - Permite actualizar slides existentes por (topic_id, order) sin crear duplicados
- **Comportamiento**: Solo aplica a documentos con `content_type='slide'`, permitiendo que otros content_types usen las mismas combinaciones de (topic_id, order)

### Índice 2: `idx_unique_quiz_per_topic`
- **Tipo**: Índice único parcial
- **Keys**: `(topic_id)`
- **Filtro parcial**: `content_type = 'quiz'`
- **Propósito**: Garantizar que solo exista un quiz por topic
- **Casos de uso**:
  - Complementa la lógica de eliminación de quiz previo en `create_content`
  - Actúa como última línea de defensa contra múltiples quizzes
  - Permite que otros content_types tengan múltiples documentos por topic
- **Comportamiento**: Solo aplica a documentos con `content_type='quiz'`, rechaza segundo quiz para mismo topic

## Justificación: Índice Parcial vs Índice Compuesto

### ¿Por qué un índice parcial para slides en lugar de un índice compuesto?

El diseño original solicitaba un índice compuesto `(topic_id, content_type, order)`, pero la implementación utiliza un índice parcial `(topic_id, order)` con filtro `content_type='slide'` por las siguientes razones técnicas:

#### Ventajas del índice parcial:
1. **Menor cardinalidad y tamaño**: El índice solo contiene documentos de tipo `slide`, reduciendo el tamaño del índice aproximadamente en un 60-80% dependiendo de la proporción de slides vs otros content_types
2. **Mejor rendimiento de escritura**: Menos documentos indexados = inserciones más rápidas para otros content_types
3. **Misma unicidad garantizada**: Para slides, el efecto es idéntico: no pueden existir dos slides con el mismo `(topic_id, order)`
4. **Queries más eficientes**: Las queries que filtran por `content_type='slide'` se benefician del `partialFilterExpression` y utilizan el índice de manera más óptima
5. **Flexibilidad futura**: Permite que otros content_types usen libremente las combinaciones `(topic_id, order)` sin restricciones

#### Compatibilidad con la intención original:
- **Idempotencia preservada**: Las operaciones de upsert para slides siguen siendo idempotentes
- **Misma garantía de unicidad**: No pueden existir slides duplicados con el mismo topic_id y order
- **Queries optimizadas**: Las queries típicas `(topic_id, content_type, order)` siguen utilizando el índice eficientemente

#### Nota sobre detección de duplicados:
El script de verificación agrupa por `{topic_id, order}` filtrando por `content_type='slide'` para detectar duplicados relevantes al índice parcial, lo que proporciona una detección precisa y eficiente de conflictos reales.

## Instalación y Uso

### Ejecución del script
```bash
python scripts/setup_topic_content_unique_indexes.py
```

### Opciones disponibles
- `--dry-run`: Verificar estado sin crear índices
- `--skip-tests`: Omitir pruebas de constraints
- `--force`: Continuar incluso si hay duplicados
- `--drop-existing`: Recrear índices existentes

### Cuándo ejecutar
- Después de implementar Fase 3 (upsert idempotente)
- Antes de desplegar a producción
- Si se detectan duplicados en la base de datos

## Manejo de Duplicados Existentes

### Detección
- El script detecta automáticamente duplicados antes de crear índices
- Reporta IDs específicos de documentos duplicados

### Limpieza de slides duplicados
- Query para encontrar duplicados:
  ```javascript
  db.topic_contents.aggregate([
    {$match: {content_type: "slide"}},
    {$group: {
      _id: {topic_id: "$topic_id", order: "$order"},
      count: {$sum: 1},
      ids: {$push: "$_id"}
    }},
    {$match: {count: {$gt: 1}}}
  ])
  ```
- Estrategia de limpieza:
  - Mantener el documento más reciente (mayor `updated_at`)
  - Eliminar duplicados más antiguos
  - Verificar que no se pierda información importante

### Limpieza de quizzes duplicados
- Query similar agrupando por `topic_id` donde `content_type='quiz'`
- Estrategia: mantener quiz más reciente, eliminar anteriores

## Integración con Código de Aplicación

### Servicios afectados
- `create_bulk_slides_skeleton` en `src/content/services.py`:
  - Ahora puede confiar en que upsert por (topic_id, order) está protegido
  - Errores de índice único indican problema en lógica de upsert
- `create_content` para quiz:
  - Índice parcial garantiza unicidad incluso si lógica de eliminación falla
  - Debe manejar error de índice único como caso excepcional

### Manejo de errores
- Error de MongoDB: `E11000 duplicate key error`
- Código debe capturar y loggear estos errores
- Sugerencia: agregar try-catch específico para errores de índice único

## Verificación y Monitoreo

### Verificar índices existentes
```javascript
db.topic_contents.getIndexes()
```

### Verificar que índices se usan en queries
```javascript
db.topic_contents.find({
  topic_id: ObjectId("..."),
  content_type: "slide",
  order: 1
}).explain("executionStats")
```
- Debe mostrar `idx_unique_slide_topic_order` en `winningPlan`
- El índice parcial se usará eficientemente ya que `content_type: "slide"` coincide con el `partialFilterExpression`

### Monitorear violaciones de índice único
- Revisar logs de aplicación para errores E11000
- Investigar causas: ¿lógica de upsert incorrecta? ¿condiciones de carrera?

## Troubleshooting

### Problema: Script falla al crear índices
- Causa probable: Duplicados existentes
- Solución: Ejecutar con `--dry-run`, limpiar duplicados, reintentar

### Problema: Aplicación recibe errores de índice único
- Causa: Lógica de upsert no funciona correctamente
- Solución: Revisar implementación de `create_bulk_slides_skeleton`

### Problema: Necesito recrear índices
- Solución: Ejecutar script con `--drop-existing`
- Advertencia: Puede causar downtime breve

## Referencias

- Documentación de implementación: `implementacion_contenido_temas.md`
- Flujo de contenido: `flujo_contenido_tema.md`
- Contexto completo: `full_context_implementacion_contenido_temas.md`
- Fase 3: Implementación de upsert idempotente
- MongoDB Unique Indexes: https://docs.mongodb.com/manual/core/index-unique/
- MongoDB Partial Indexes: https://docs.mongodb.com/manual/core/index-partial/