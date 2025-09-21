Qué hay que cambiar (y dónde) para que el flujo cumpla EXACTO tu especificación
Flujo deseado (resumen tajante)

Secuencial (1 worker activo por fase):
a) Generar contenido teórico (una sola llamada).
b) Dividir contenido teórico en fragmentos (pura programación).
c) Generar plan maestro + estilos (template de referencia).

Primer guardado en BD (secuencial):
Crear una diapositiva por fragmento con: full_text, template_snapshot (estilos de referencia), status="skeleton", order, parent_content_id/topic_id. Sin HTML aún.

Paralelo (5 workers, a full):
Para cada diapositiva: generar HTML creativo con prompt que incluye full_text + template_snapshot. Guardar en el doc de la diapositiva: content_html + render_engine="raw_html" + status="html_ready".

Paralelo (5 workers):
Para cada diapositiva: generar narrative_text con prompt que incluye content_html + full_text. Guardar narrative_text + status="narrative_ready".

Final
Cuando la última narrativa termina, encolar el quiz (último en la cola).

Frontend – Cambios concretos
1) Orquestación en src/hooks/useUnifiedContentGenerator.ts

Desactivar el flujo heredado generateSlides/generateIndividualSlide (guarda JSON plano) y crear generateSlidesV2 con las 3 fases arriba:

Fase A (secuencial): contenido teórico → división → plan+template (referencia).

Fase B (secuencial): POST skeleton de todas las diapositivas (una por fragmento).

Fase C (paralelo 5): HTML por diapositiva → PUT de content_html.

Fase D (paralelo 5): narrativa por diapositiva → PUT de narrative_text.

Fase E (secuencial): quiz.

Puntos clave del código:

Mantén slidePlanPrompt / slideTemplatePrompt para obtener sólo estilo/estructura de referencia (no HTML definitivo).

Para el HTML por diapositiva, crea un prompt específico que combine:

full_text del fragmento

template_snapshot (colores, grid, tamaños, tipografías, constraints de área) como guía

Instrucciones de creatividad (keywords, micro-diagramas, columnas, jerarquía visual, CTA educativos)

Prohibir reusar el HTML del template; usarlo como guía de estilo y layout.

Resultado: llamas al text-caller y escribes content_html en la diapositiva individual.

2) Paralelismo real (5 workers)

En tu servicio de workers del front, fija concurrencia=5 para Fase C y Fase D (generación de HTML y narrativa), y concurrencia=1 para teoría, división y plan.

Asegura que el quiz no se encola hasta que status de todas las diapositivas sea al menos narrative_ready.

3) TOASTs/Progreso (“TOAS”)

Emite progreso por fase y por diapositiva.

Cierra/splicea los indicadores cuando el evento onPhaseCompleted / onAllSlidesReady / onNarrativesReady se dispare.

Quita los “cargando” fantasmas: si no hay tareas en cola, finaliza el estado global de generación.

4) Viewer

SlideContentViewer: renderiza content_html si existe; si no, muestra fallback.

Si render_engine="raw_html", usa dangerouslySetInnerHTML (sanitiza si corresponde).

Backend – Cambios mínimos y seguros
1) Modelo/documento por diapositiva

Para cada diapositiva (documento en topic_contents):

content_type: "slide"

full_text: string (el fragmento teórico completo)

template_snapshot: { palette, grid, fontFamilies, spacing, breakpoints, … } (sólo referencia)

content_html?: string (se llena en Fase C)

narrative_text?: string (se llena en Fase D)

render_engine: "raw_html" una vez haya HTML

order: number, parent_content_id o topic_id

status: "skeleton" | "html_ready" | "narrative_ready"

Nota: No guardes el HTML del template. El template es snapshot de estilo, no HTML final.

2) Endpoints

POST /api/content/bulk (skeleton): crea todas las diapositivas con full_text + template_snapshot + status="skeleton".

PUT /api/content/{id}/html (Fase C): guarda content_html, render_engine="raw_html", status="html_ready".

PUT /api/content/{id}/narrative (Fase D): guarda narrative_text, status="narrative_ready".

POST /api/content/quiz (Final): encola/crea el quiz sólo si todas las slides de ese parent_content_id/topic_id están narrative_ready.

3) Reglas de orquestación (quiz al final)

Política del dispatcher: no asignar quiz mientras exista cualquier slide con status!="narrative_ready" (en ejecución o en cola).

Si usas prioridades, añade además dependencia explícita: quiz.dependsOn = all(slides.narrative_ready).

Prompts (base)

HTML de diapositiva (por slide, paralelo 5):

Contexto: full_text (sin cortar), template_snapshot (guía), topic_name, learning_objectives.

Instrucciones:

“Genera HTML completo para una diapositiva creativa (mismo tamaño estándar), respetando paleta/tipografías/espaciados del template como guía, pero NO reutilices el HTML del template.

Usa jerarquía visual, palabras clave, listas, micro-diagramas ASCII o cajas div estilizadas, sin frameworks.

Estructura semántica (<section>, <h1…>, <p>, <ul>, <aside>).

Prohibido: iframes, scripts, CSS externos.

Entrega solo HTML (sin JSON).”

Narrativa (por slide, paralelo 5):

Inputs: content_html + full_text.

Instrucciones:

“Redacta narración fluida (90–150s) para presentar esta diapositiva a estudiantes de [nivel], enlazando el HTML mostrado con el conocimiento base. Tono didáctico, claro, con transiciones. Devuelve solo texto.”

Qué está mal hoy (confirmación)

El front sigue usando generateIndividualSlide y guarda JSON (título, contenido y narrativa), sin HTML. Eso es el objeto que mostraste.

El template actual se guarda como estilos planos y se usa directamente para render legacy; no se usa solo como referencia de prompts.

La narrativa se resume en lugar de generarse con IA a partir del HTML + full_text.

El quiz puede colarse antes de terminar todas las narrativas si no hay dependencia estricta.

Check-list de implementación (en orden)

Frontend

Deshabilitar generateSlides/generateIndividualSlide.

Implementar generateSlidesV2 con las fases A–E.

Añadir jobs paralelos (5) para HTML y narrativa.

Actualizar TOASTs y progreso por fase.

SlideContentViewer renderiza content_html.

Backend

POST /content/bulk (skeleton por fragmento con full_text + template_snapshot).

PUT /content/{id}/html y PUT /content/{id}/narrative.

Dispatcher: bloquear quiz hasta narrative_ready global.

Validaciones: si llega content_html → render_engine="raw_html".

¿Qué hace actualmente el frontend?

Hook useUnifiedContentGenerator:

Usa el método antiguo generateSlides, que divide el contenido teórico en sub‑temas y guarda cada diapositiva como un JSON con title, content y una narrativa resumida
GitHub
. No invoca el generador unificado ni genera HTML.

Cada sub‑tema se procesa secuencialmente (no hay paralelismo) y se guarda en la base de datos mediante createTopicContent con un slide_template fijo
GitHub
. Por tanto, no se aprovechan los 5 workers para generar HTML ni narrativa.

Generador unificado (generateSlideContent) en src/services/AI/unifiedContentGenerator.ts:

Sí implementa el flujo ideal: genera un plan de diapositivas con slidePlanPrompt, luego una plantilla maestra con slideTemplatePrompt y finalmente crea el HTML de cada diapositiva usando slideContentPrompt
GitHub
. El resultado es un objeto con slide_template y un array slides con content_html
GitHub
.

Sin embargo, este método no se usa en el hook actual para generar diapositivas.

Servicios de fases (SkeletonSlidesPhaseService y NarrativeTextPhaseService):

El servicio de esqueleto genera diapositivas sin HTML y sólo guarda títulos, puntos clave y tipos
GitHub
.

El servicio de narrativa genera texto a partir del contenido de esas diapositivas, no del HTML
GitHub
. Es decir, la narrativa se basa en un resumen del texto, no en la diapositiva final.

En resumen, la UI actual continúa usando la lógica antigua (diapositivas JSON con narrativa resumida), mientras que el generador unificado capaz de producir HTML y plan de estilos aún no está integrado.

¿Qué soporta el backend?

El modelo TopicContent permite almacenar slide_template y también soporta render_engine
GitHub
, pero por defecto usa "legacy".

Existe una función create_bulk_content para insertar múltiples contenidos a la vez, pero no se utiliza en el pipeline de diapositivas.

El backend no tiene endpoints específicos para actualizar sólo el content_html o la narrative_text de una diapositiva. Para modificar esos campos habría que usar el método genérico update_content, que actualiza el documento completo
GitHub
.

Conclusión: Las tareas recomendadas son necesarias

Comparando tu flujo deseado con el código actual:

Fases secuenciales con workers: No existen. La generación de contenido teórico se hace aparte, pero la división en fragmentos, el plan y la plantilla no se encadenan de forma secuencial con workers. El generador unificado lo hace todo a la vez, y el hook antiguo ni siquiera lo usa.

Almacenar cada diapositiva como documento individual (skeleton): No se implementa. El generador unificado guarda todas las diapositivas en un solo documento TopicContent con un array slides
GitHub
, y el hook antiguo guarda cada diapositiva como JSON plano, sin HTML, sin narrativa, sólo con un template fijo.

Generación paralela de HTML (5 workers) y narrativa: No existe. El generador unificado genera el HTML secuencialmente, y la narrativa se genera a partir del contenido (no del HTML) y también de forma secuencial en el hook antiguo.

Quiz encolado al final: Tampoco se controla. En el pipeline paralelo de slides, el quiz se puede encolar antes de que terminen todas las diapositivas, tal como señalaste.

Por estas razones, las tareas que propuse (crear generateSlidesV2, usar workers de 5 concurrentes para HTML y narrativa, guardar skeletons con full_text y template_snapshot, actualizar la UI, añadir endpoints para PUT /content/{id}/html y PUT /content/{id}/narrative, etc.) sí son necesarias para alcanzar tu flujo exacto. El código actual no respeta la secuencia, no usa los estilos como referencia en los prompts de HTML, no genera HTML creativo por cada diapositiva en paralelo y no espera a que todas las narrativas estén listas antes de arrancar el quiz.

En pocas palabras: el sistema dispone de algunas piezas (generador unificado, servicios de workers, modelo flexible), pero no están integradas conforme a tu especificación. Implementar las fases y endpoints propuestos permitirá cumplir con el flujo ideal que describiste.