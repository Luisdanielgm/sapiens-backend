Backend — Resumen ejecutivo para “Topic Generation”
Contexto (rol del backend)

El backend no llama modelos ni orquesta IA. Su papel es:

Persistencia canónica de Topics y TopicContents.

Contratos de API para crear/actualizar teoría, slides y quiz.

Validación y gobernanza del esquema (formatos, casing, campos permitidos).

Idempotencia en re-generaciones (no duplicar, sobreescribir donde corresponda).

Seguridad y consistencia (sanitización HTML, límites, transacciones).

Requerimientos y restricciones (enfocados al backend)

Entidades

Topics

Solo interviene theory_content (string). No tocar otros campos.

TopicContents

content_type ∈ {'slide','quiz'}.

Todo dato específico del contenido va dentro de content (lowercase):

Slides: content.full_text (trozo literal), content.slide_plan (string/Markdown, no JSON), content.content_html (HTML), content.narrative_text (string).

Quiz: estructura completa del quiz dentro de content según esquema vigente.

Flujo (visto desde API)

Teoría: endpoint que solo hace set Topics.theory_content.

Slides: endpoint(es) para crear esqueletos (N docs) y actualizar content.content_html y content.narrative_text.

Quiz: endpoint para crear/actualizar un único TopicContents de tipo quiz.

Regeneración: sobreescribir teoría; re-poblar slides (mismos order); un solo quiz.

Políticas

Sin parámetros de proveedor/modelo en payloads (rechazar/ignorar).

slide_plan es string (texto/MD), prohibido JSON.

full_text debe ser un substring literal de Topics.theory_content.

No duplicar campos fuera de content (nada de content_html, narrative_text, full_text al nivel raíz).

Checklist de verificación (solo backend)

Topics

 PUT /topics/{id}/theory: persiste únicamente theory_content.

 No se agregan otros campos ni side-effects.

TopicContents — Slides

 Creación de N slides (content_type='slide') con:

 content.full_text = trozo literal (validable como substring).

 content.slide_plan = string/MD, no JSON.

 content.content_html inicial vacío.

 content.narrative_text inicial vacío.

 order secuencial; status ∈ {'skeleton','html_ready','narrative_ready'}.

 No existen full_text/content_html/narrative_text fuera de content.

 PUT /content/{id}/html solo hace $set content.content_html (+status).

 PUT /content/{id}/narrative solo hace $set content.narrative_text (+status).

 Sanitización de HTML (lista blanca) y límites de tamaño.

TopicContents — Quiz

 Existe un doc content_type='quiz' por topic.

 Quiz completo dentro de content según esquema vigente.

 Re-generación reemplaza (no duplica) el quiz.

Políticas de API

 Si llegan provider/model en payload → 400/ignorar.

 slide_plan validado como string (rechazar objetos/arrays).

 Idempotencia: re-click no duplica slides (reusa order) ni quiz.

Datos/Índices

 Índice único (topic_id, content_type, order) para slides.

 Índice único parcial (topic_id) WHERE content_type='quiz'.

Tareas a resolver y verificar (backend)
A. Esquema y almacenamiento

Eliminar duplicados fuera de content

Ajustar create_content/to_dict para no insertar full_text/content_html/narrative_text al tope.

Migración: mover valores existentes al anidado y limpiar raíz.

Actualizaciones anidadas

Garantizar PUT /content/{id}/html|narrative solo toque content.* y status/updated_at.

B. Bulk slides e idempotencia

Creación de esqueletos idempotente

POST /content/bulk/slides que acepte lote con order; upsert por (topic_id, order).

Si sobran slides previos (más que N), eliminarlos.

Auto-generar template_snapshot por defecto si falta (o aceptar mínimo válido), sin bloquear el flujo (el spec no lo exige).

Validación slide_plan

Tipo string; rechazar payloads object/array.

Límite de longitud razonable.

C. Quiz único por topic

Unicidad de quiz

Antes de crear, borrar/reemplazar existente.

O aplicar índice único parcial y convertir segunda inserción en update.

D. Políticas y seguridad

Filtrado de payloads

Rechazar/ignorar provider/model.

Sanitizar HTML (bleach/OWASP) y limitar tamaño (p. ej. 100–200 KB por slide).

Rate-limit y logs de auditoría.

E. Consistencia transaccional

Transacciones por corrida (opcional)

Al re-generar: upsert slides por order, limpiar sobrantes y quiz anterior en una transacción (si el driver/DB lo permite).

F. Observabilidad y pruebas

Métricas y logs

Contadores: slides creados/actualizados, quiz reemplazado, fallos de validación.

Tests automatizados

Unit: validadores (slide_plan, HTML, nesting).

Integración:

Generación inicial: N slides + 1 quiz, nesting correcto.

Re-generación: no duplica, reemplaza quiz, mantiene order.

Rechazo de provider/model y slide_plan no-string.

G. Documentación

Actualizar doc backend

Esquema efectivo (content.*), contratos de endpoints, reglas de idempotencia y unicidad de quiz.

Notas de implementación rápida (en 1 día, bajo impacto)

Hotfix de nesting: interceptar to_dict()/insert y forzar que full_text/content_html/narrative_text vivan solo en content.

Upsert por (topic_id, order) en creación de slides (bulk) y delete sobrantes.

Reemplazo de quiz: deleteMany(topic_id, 'quiz') previo a crear.

Validadores: rechazar slide_plan no-string; sanitizar content_html.

Índices: crear únicos para slides/quiz.