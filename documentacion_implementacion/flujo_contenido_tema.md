Especificación de Implementación — Vista “Topic Generation” (Profesor)
1) Alcance

Implementar el flujo “un solo clic” que genera, divide y materializa contenido de un Tema en contenido teórico, diapositivas (HTML + narrativa) y quiz, sin modificar el esquema existente más allá de los campos explícitamente mencionados en este documento.
Los demás campos de las colecciones pueden existir y deben preservarse; no se tocan salvo que el esquema vigente lo requiera en su propia lógica.

2) Entidades y campos que intervienen (explícitos)
Topics

theory_content: string (texto teórico completo).

Único campo de Topics involucrado en este proceso.

Nota: Pueden existir otros campos en Topics. No se eliminan, no se inventan, no se modifican.

TopicContents

content_type: identifica el tipo de contenido (por ejemplo, slide, quiz).

Content (contenedor de datos específicos del contenido).

Para content_type = 'slide', dentro de Content intervienen:

full_text: trozo de teoría correspondiente a la diapositiva (sin resumir ni alterar).

slide_plan: plan/estilos/estructura en string (texto/Markdown). No JSON.

content_html: HTML de la diapositiva.

narrative_text: texto narrativo asociado a la diapositiva.

Para content_type = 'quiz', el quiz se guarda dentro de Content conforme al esquema existente (sin definir subcampos aquí).

Nota de nomenclatura: use la casing exacta del esquema para el campo contenedor (Content/content). Este documento lo nombra Content a efectos de claridad, pero se debe respetar lo que exista en la base real.

Importante: Si actualmente algún dato propio del contenido (p. ej., narrative_text, slide_plan, content_html) se guarda fuera de Content, corregir para que viva dentro de Content.

3) Políticas y restricciones

Workers obligatorios (pool de 5):

Todas las generaciones (teoría, plan/estilos, HTML por diapositiva, narrativa por diapositiva, quiz) se encolan al pool.

Nunca se llama a un LLM/proveedor de forma directa.

No se pasan parámetros de proveedor/modelo al payload; el pool resuelve con la configuración del usuario.

Formato de slide_plan:

Debe ser string (texto o Markdown).

Prohibido JSON (ajustar prompts si fuera necesario).

División del texto:

Se hace tras persistir theory_content en Topics.

Es determinística y no modifica el texto (cada trozo = una diapositiva).

Un solo clic:

El botón Generar en el tab Contenido teórico activa el pipeline completo.

4) Flujo operativo (paso a paso)

0. Selección en UI
Profesor: Plan → Módulo → Tema → Tab Contenido teórico → Generar (un clic).

1. Secuencial (Worker) — Contenido teórico

Encolar tarea: generar teoría.

Resultado: texto teórico completo.

Persistir en Topics.theory_content.

A partir de aquí, no se vuelve a tocar Topics en esta corrida.

2. Secuencial (Worker) — Plan/estilos/estructura de diapositivas

Encolar tarea: generar slide_plan.

Resultado: string (texto/Markdown, sin JSON).

No se guarda en Topics. Se mantendrá para poblar los esqueletos.

3. Paralelo (lógica, sin LLM) — División

Dividir theory_content (ya guardado) en N trozos sin alterar el texto.

Cada trozo representa una futura diapositiva.

Este paso puede ejecutarse en paralelo al Paso 2.

4. Esqueletos en TopicContents (slides)

Crear/actualizar N documentos con:

content_type = 'slide'.

En Content:

full_text = trozo i.

slide_plan = el mismo string para todas las diapositivas.

content_html = (vacío inicialmente).

narrative_text = (vacío inicialmente).

5. Paralelo (Workers) — HTML por diapositiva

Encolar N tareas: generar HTML de diapositiva.

Payload mínimo: full_text + slide_plan.

Al completar, actualizar solo TopicContents.Content.content_html de la diapositiva correspondiente.

6. Paralelo (Workers) — Narrativa por diapositiva

Encolar N tareas: generar narrativa de diapositiva.

Payload mínimo: content_html + full_text.

Al completar, actualizar solo TopicContents.Content.narrative_text.

7. Quiz (Worker, encolado al final)

Encolar una tarea: generar quiz del tema (cuando ya se encolaron las narrativas).

Al completar, crear/actualizar un TopicContents con content_type = 'quiz' y guardar su información dentro de Content conforme al esquema existente (sin definir subcampos aquí).

8. Resultado tras el clic

Topics: contiene theory_content completo.

TopicContents:

Slides: Content.full_text, Content.slide_plan, Content.content_html, Content.narrative_text completos.

Quiz: contenido guardado dentro de Content (según esquema vigente).

5) Regeneración (mismo botón, mismas reglas)

Al presionar Generar nuevamente para el mismo tema:

Se re-genera la teoría y se re-escribe Topics.theory_content.

Se re-genera el slide_plan (string).

Se vuelve a dividir el texto y se actualizan los TopicContents de tipo slide (población de Content.full_text y Content.slide_plan) y luego su Content.content_html y Content.narrative_text mediante workers.

Se encola y actualiza el quiz en TopicContents (content_type='quiz'), guardando el resultado dentro de Content.

No se asumen ni se documentan otros campos fuera de los aquí listados.

6) Checklist de verificación (solo con campos conocidos)

Topics

 theory_content se guarda tras la generación de teoría.

 No se almacena ninguna otra cosa en Topics.

TopicContents — Slides

 Existe un documento por cada diapositiva con content_type = 'slide'.

 En Content:

 full_text = trozo íntegro de la teoría (sin modificar).

 slide_plan = string de plan/estilos (mismo para todas; no JSON).

 content_html = poblado por la tarea de HTML.

 narrative_text = poblado por la tarea de narrativa.

 Ningún campo propio del contenido está fuera de Content.

TopicContents — Quiz

 Existe un documento con content_type = 'quiz'.

 Su información se guarda dentro de Content conforme al esquema vigente.

Ejecución por Workers

 Todas las generaciones se encolaron al pool (teoría, plan, HTML por slide, narrativa por slide, quiz).

 No hubo llamadas directas a proveedores/LLM.

 No se pasaron parámetros de proveedor/modelo en payloads.

Formato

 slide_plan es string (texto/Markdown).

 No se utilizó JSON para slide_plan.

 Los full_text son copia literal de los trozos de theory_content.