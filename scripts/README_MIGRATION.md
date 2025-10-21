# Migración de Campos de Contenido - SapiensAI

## 1. Descripción general

**Propósito del script:** migrar campos de contenido de slides y quizzes desde el nivel raíz al objeto `content`

**Contexto:** parte de la refactorización para cumplir con las políticas de almacenamiento de datos específicos del contenido

**Campos afectados:** `full_text`, `content_html`, `narrative_text`, `slide_plan`, `template_snapshot`, `slide_template`

## 2. Requisitos previos

- MongoDB 3.6+ (4.0+ si se usan transacciones)
- Python 3.8+
- Dependencias: pymongo, python-dotenv
- Variables de entorno configuradas: `MONGO_DB_URI`, `DB_NAME`
- Backup de la base de datos recomendado antes de ejecutar

## 3. Uso básico

- Modo dry-run (recomendado primero): `python scripts/migrate_topic_content_fields.py --dry-run`
- Ejecución real: `python scripts/migrate_topic_content_fields.py`
- Con transacciones: `python scripts/migrate_topic_content_fields.py --use-transactions`
- Solo validación: `python scripts/migrate_topic_content_fields.py --validate-only`

## 4. Opciones avanzadas

- `--batch-size N`: tamaño de lotes para procesamiento (default: 500)
- `--commit-every N`: checkpoint cada N documentos (default: 1000)
- `--verbose`: logging detallado por documento
- `--skip-validation`: omitir validación post-migración

## 5. Proceso de migración

- Paso 1: Ejecutar en modo dry-run para ver qué se migrará
- Paso 2: Revisar el output y verificar que los cambios son correctos
- Paso 3: Hacer backup de la base de datos
- Paso 4: Ejecutar la migración real
- Paso 5: Revisar el resumen y validar que no hay errores
- Paso 6: Ejecutar `--validate-only` para confirmar que no quedan campos al nivel raíz

## 6. Interpretación de resultados

- "Documentos migrados exitosamente": documentos que fueron actualizados
- "Documentos ya correctos": documentos que no necesitaban cambios
- "Documentos con errores": documentos que fallaron (revisar logs)
- Estadísticas por campo: muestra cuántos de cada campo fueron migrados

## 7. Troubleshooting

- Si hay errores de conexión: verificar `MONGO_DB_URI` y conectividad
- Si hay errores de transacciones: usar sin `--use-transactions` o actualizar MongoDB
- Si hay documentos con errores: revisar logs detallados y ejecutar con `--verbose`
- Si la validación falla: ejecutar nuevamente el script (es idempotente)

## 8. Consideraciones de rendimiento

- Para bases de datos grandes (>10,000 documentos), considerar ejecutar fuera de horas pico
- Ajustar `--batch-size` según recursos disponibles (más grande = más rápido pero más memoria)
- Las transacciones pueden ser más lentas pero garantizan atomicidad

## 9. Rollback

- Si se usaron transacciones y hubo error, el rollback es automático por lote
- Sin transacciones, restaurar desde backup si es necesario
- El script es idempotente: puede ejecutarse múltiples veces sin duplicar cambios

## 10. Verificación post-migración

- Ejecutar `--validate-only` para confirmar que no quedan campos al nivel raíz
- Verificar en MongoDB Compass o shell que los campos están dentro de `content`
- Probar la aplicación para asegurar que todo funciona correctamente
- Revisar logs de la aplicación para detectar posibles problemas