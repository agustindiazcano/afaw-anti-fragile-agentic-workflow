# Instrucciones generales para agentes de código

Reglas reutilizables en cualquier proyecto, unificadas a partir de dos `AGENTS.md`/`CLAUDE.md` reales más reglas propias. Copiar a la raíz del repo como `CLAUDE.md` y `AGENTS.md` (mantener ambos idénticos).

## 0. IDIOMA — SIEMPRE HABLAR EN INGLÉS
> **ALWAYS RESPOND IN ENGLISH.** Every reply, explanation, commit message, PR title/description and code comment is written in English, regardless of the language the user writes in.

## 1. Inicio de sesión y contexto
1. **En el primer mensaje, consultar siempre `ROL:` al humano** (qué rol cumple este agente en el proyecto).
2. Además de leer los archivos de contexto (`PENDING.md`), buscar el `LASTCONTEXT` de ese rol: si existe, leerlo; si no existe, leer el `LASTCONTEXT` global.
3. Actualizar el contexto al final de cada sesión relevante.
4. **Al terminar una tarea:** actualizar la documentación afectada y los documentos de estado (el archivo de contexto propio de la tarea y su estado en `state/tasks/`, nunca el `LASTCONTEXT` global), y hacer un commit de documentación de la tarea (`docs(scope): ...`), aparte del commit de código, con un mensaje que diga qué se hizo. Ese commit es solo de documentos, así que no lanza tests (sección 11).
5. Mantener sincronizados los archivos de instrucciones duplicados (`AGENTS.md` y `CLAUDE.md` idénticos): se editan ambos en el mismo cambio.
6. Documentar el estado de cada fase (hecho, en curso, roadmap) junto con las decisiones tomadas y su fecha.
7. **Los archivos generados no se editan a mano:** `state/pending.json`, `context/global/lastcontext.json` y `context/roles/*/lastcontext.json` los regenera el CI (`scripts/merge_state.py`) y abre un PR que aprueba el humano. El agente solo escribe su delta (`context/tasks/task_NNN_context.json`) y su archivo de tarea (`state/tasks/task_NNN.json`). El CI rechaza un PR que cambie código sin un delta válido que liste esos archivos en `files_touched` (`scripts/check_task_delta.py`); qué carpetas cuentan como código se define por proyecto en `state/config.json`.

## 2. Rol y método de trabajo
1. Actuar como ingeniero senior y especialista en QA: SOLID, Clean Architecture, código pequeño, modular, tipado, testeable y listo para producción.
2. **Nunca afirmar un resultado que no se midió.**
3. **TDD estricto (Red → Green → Refactor):** escribir primero el test y confirmar que falla; luego el mínimo código para que pase; refactorizar con el test en verde.
4. Nunca presentar una función o endpoint como terminado sin su test.
5. Ante un bug, escribir primero un test que lo reproduzca (debe fallar) y recién después arreglar.
6. Los tests de detectores o estimadores usan secuencias sintéticas con ruido y punto de cambio conocidos.
7. **Parsimonia:** implementar el modelo o detector más simple que resuelva el problema; usar uno más pesado solo con evidencia de que el simple falla.
8. No agregar componentes opacos (p. ej. un clasificador entrenado) que después haya que monitorear.
9. Consultar la documentación vigente de una librería antes de implementar con ella, no hacerlo de memoria.

## 3. Reporte de estado del proyecto
Cuando se pida el estado del proyecto, responder **siempre** con una tabla de tareas pendientes con semáforo, dificultad y prioridad:

| Tarea | Estado | Dificultad (1-5) | Prioridad (1-5) |
|---|---|---|---|
| Ejemplo: migrar el worker a async | 🟡 | 3 | 1 |

1. **Semáforo:** 🟢 terminada o en camino sin riesgo · 🟡 en curso o en riesgo · 🔴 bloqueada, fallando o vencida.
2. **Dificultad:** 1 = trivial, 5 = muy difícil o incierta.
3. **Prioridad:** 1 = la más urgente, 5 = la menos urgente. Ordenar la tabla por prioridad ascendente.
4. Un solo renglón por tarea; sin párrafos dentro de la tabla. Si una tarea está en 🔴, dar en una línea aparte el bloqueo y qué se necesita para destrabarla.
5. Solo tareas reales del proyecto (`PENDING.md`); no inventar tareas para completar la tabla.
6. **Para leer el estado, leer solo `state/pending.json` desde `origin/main`** (`git fetch` y `git show origin/main:state/pending.json`), porque la copia de la propia rama puede estar desactualizada. No leer los archivos de `state/tasks/` uno por uno.

## 4. Estándares de código
1. Type hints en toda función pública, con docstring corto (qué mide/hace y qué archivo escribe).
2. `mypy --strict`; sin `Any` salvo justificación en un comentario en línea.
3. Toda función con I/O es `async`, y nunca hay I/O bloqueante dentro de `async` (usar `asyncio.sleep`, `httpx.AsyncClient`, drivers async).
4. Toda llamada bloqueante a subprocess lleva timeout; los procesos de larga duración se terminan o se esperan; los directorios de trabajo temporales se borran.
5. Configuración desde variables de entorno con `pydantic-settings`; nunca hardcodear secretos ni cadenas de conexión.
6. Logging estructurado (`structlog`); nunca `print()`.
7. PEP 8 con línea máxima de 100 caracteres.
8. Sin `from module import *`.
9. No usar `except Exception` genérico sin loguear o re-lanzar el error específico.
10. Sin comentarios `TODO`: implementarlo o preguntar.
11. No agregar dependencias nuevas sin justificarlas; preferir la biblioteca estándar.
12. Funciones de un solo propósito; un archivo, una responsabilidad; dividir un archivo antes de que pase de ~600 líneas.
13. Cada módulo tiene su archivo de test (`pytest` + `pytest-asyncio`).
14. Los tests corren contra una base propia cuyo nombre termina en `_test`; la suite se niega a arrancar si no es así.
15. Todo el código vive en `src/` con imports absolutos, para que funcione igual en local, en tests y en Docker.
16. Los datos de ejemplo o demo se cargan con scripts o jobs aparte, nunca dentro de una migración.

## 5. Arquitectura
1. **La IA decide, el motor mide:** todo número (cobertura, métricas, riesgo) sale de una función determinista, nunca de una estimación, redondeo o extrapolación.
2. **Determinismo:** misma entrada, mismos números. Dos corridas idénticas que difieren son un bug.
3. **Separación de capas:** nunca mezclar lógica de base de datos, ruteo e IA en el mismo archivo. El núcleo no tiene código de web/CLI/protocolo; los adaptadores (CLI, servidor, MCP) son finos y delegan.
4. Los repositorios solo acceden a la base de datos; las llamadas HTTP externas van en services o agentes.
5. **La capa de IA nunca importa modelos, repositorios ni conexiones de la base:** todo acceso a datos pasa por herramientas (MCP).
6. **Idempotencia obligatoria:** cada request lleva un `request_id` único; se consulta antes de invocar al LLM y, si existe, se devuelve el resultado cacheado.
7. **Reintentos con backoff exponencial** y límite configurable en toda llamada externa; al agotarlos, NACK para reencolar o mandar a dead-letter.
8. **Factory de proveedores LLM:** cambiar de proveedor con una variable de entorno, sin tocar la lógica de negocio. Un proveedor `mock` para todos los roles evita gasto en pruebas y cargas.
9. Los módulos de scoring/reglas son funciones puras de sus entradas, sin acceso a base ni herramientas, para que cada disparo sea reproducible y auditable.
10. Registrar cada disparo de regla (id, entradas, grado de creencia, veredicto final): es lo que vuelve auditable la capa, y no se omite para ahorrar escrituras.
11. La observabilidad y la detección de drift nunca bloquean ni participan del camino crítico: consumen logs ya persistidos y su falla no afecta las transacciones.
12. Definir explícitamente cada componente como fail-open o fail-closed: guardas y jueces fallan cerrado; recuperación de contexto y tracing fallan abierto. Un valor de configuración faltante en un chequeo de seguridad falla cerrado.
13. **Salidas como contrato:** las funciones devuelven un dict y escriben JSON en una carpeta de salida; los subagentes se comunican por archivos, no por memoria compartida.
14. **Respuestas compactas:** resúmenes por defecto, datos completos solo bajo pedido (todo queda en el contexto del agente y se reenvía en cada turno).
15. No imprimir a stdout en servidores stdio: es el canal del protocolo; usar stderr o valores de retorno.
16. Un frontend interno de solo lectura consume solo endpoints GET y nunca se conecta directo a la base ni a servicios internos.
17. Elegir el transporte de forma deliberada y documentada; un cambio global de transporte se conversa, y una alternativa se agrega como opción adicional.
18. **El código fuente es la referencia:** al escribir tests solo se edita `tests/`. Si un test nuevo falla contra el código original, el test está mal salvo evidencia de un bug real; en ese caso `xfail(reason="possible bug: ...")`, jamás arreglar el código fuente para que pase.
19. Operar sobre copias temporales, nunca in situ, cuando el repo objetivo es la base de las métricas documentadas.

## 6. Agentes y LLMs
1. **El LLM nunca ejecuta herramientas con efectos secundarios:** solo código determinista, y toda herramienta de escritura es idempotente por `request_id`.
2. **Nunca confiar en la salida del LLM:** revalidarla en el servidor con esquemas Pydantic estrictos (`extra="forbid"`) y límites de negocio.
3. El agente de cara al usuario tiene mínimo privilegio: sin acceso a la base, a la tabla de conocimiento ni al servidor de herramientas. Solo propone una intención estructurada y, si no puede mapear el mensaje, pregunta en vez de adivinar un campo.
4. Filtro previo de prompt injection/jailbreak antes de que el mensaje llegue al agente, que falla rápido.
5. El feedback al usuario expone un veredicto objetivo y auditable, nunca la justificación cruda de un juez, que podría filtrar razonamiento o reglas de negocio internas. El agente lo redacta pero nunca lo reinterpreta ni lo anula.
6. Capturar cualquier excepción en el dispatch de herramientas de un agente y devolverla al modelo como resultado de error: una llamada mala no debe tirar todo el proceso.

## 7. Seguridad
1. Autenticar cada llamada a herramientas con token bearer: el servidor guarda solo su hash SHA-256, lo compara en tiempo constante y deriva `client_id` del token, nunca de un header del cliente.
2. Autorización por herramienta con allowlist del lado del servidor; nada en el prompt ni en documentos recuperados puede ampliar el acceso.
3. Rate limiting por cliente y herramienta, calculado desde la tabla de auditoría para que valga entre réplicas sin Redis.
4. Audit log de toda invocación, incluso las denegadas, con PII enmascarada; si la escritura de auditoría falla, la herramienta no se ejecuta.
5. Enmascarar PII en el export de trazas (pseudonimizar user ids, redactar emails y números largos); todo campo PII nuevo se agrega con su test antes de trazarlo.
6. Una cuenta de servicio por servicio, con acceso por secreto y nunca a nivel de proyecto.
7. Los valores que Terraform no genera se cargan a mano, no por variables de Terraform, para que no queden en el state.
8. Normalizar secretos (`.strip()`) en ambos lados de una comparación; cuidado con saltos de línea en secretos.
9. Documentar los análisis de exposición (p. ej. abuso de una API pública) y no implementar una defensa sin el visto bueno del usuario.
10. Persistencia opt-in y nunca pública en rutas que aceptan entradas arbitrarias; no guardar números redondeados.

## 8. Concurrencia y mensajería
1. Bloqueo pesimista (`SELECT ... FOR UPDATE`) más `UniqueConstraint` sobre el id para evitar doble procesamiento.
2. Un barredor de recuperación (`FOR UPDATE SKIP LOCKED`) reencola lo que un worker caído dejó a medias.
3. Publicar mensajes como persistentes en colas durables: un mensaje transiente se pierde al reiniciar el broker.
4. Ack/nack seguros (loguear y seguir si el canal se cerró) y reconexión con reintento, en vez de morir.
5. Los consumidores de larga vida usan `restart: unless-stopped` y esperan al broker ellos mismos; los servicios normales, un reinicio acotado como defensa.
6. Cerrar la transacción de base antes de llamadas externas largas (MCP, LLM).
7. Usar `clock_timestamp()` y no `now()` para timestamps de auditoría: `now()` refleja el inicio de una transacción larga y distorsiona las latencias.
8. En clientes con timeout, abrir una sesión nueva por intento y no reutilizarla entre reintentos.
9. **Estado en memoria + múltiples instancias = bug:** locks y rate limiters deben ser durables (base de datos) si el servicio escala horizontalmente.

## 9. Observabilidad y trazas
1. Una traza por transacción, con id derivado del `request_id`, y observaciones tipadas y anidadas.
2. Los nombres de observaciones son una API: estables, verbo primero, baja cardinalidad; ids y modelos van en metadata. Renombrar es un cambio incompatible.
3. El tracing es fail-safe: se apaga sin claves y sus fallas se loguean sin cambiar el resultado ni el ACK/NACK.
4. Los tests nunca envían trazas: se desactiva el tracing en la suite y se usa un exporter en memoria cuando hay que aseverar sobre spans. Si el test depende de callbacks, usar modelos falsos reales y no `AsyncMock`.
5. Verificar contra una traza real después de cambiar la instrumentación.

## 10. Evaluación de modelos y jueces
1. Evaluar el código de producción, nunca una copia pegada del prompt.
2. Las etiquetas de los casos las decide el usuario: los casos nuevos quedan pendientes hasta que él los revise.
3. Reportar primero los falsos aprobados: son el error peligroso y la accuracy sola lo esconde.
4. Mantener fija la recuperación de contexto en las evaluaciones.
5. Las corridas reales cuestan dinero y tiempo: usar el proveedor mock para probar el flujo y pasar precios actualizados con fecha.
6. Jueces asimétricos de familias de modelos distintas; el desempate usa un modelo distinto al del primer juez para dar una opinión independiente.
7. Los veredictos de los LLM varían entre corridas: no repetir la votación para "corregir", y cubrir ese hueco con chequeos deterministas.

## 11. Tests de código
1. **Los tests siempre se lanzan en la nube** (GitHub Actions o el CI que use el proyecto), nunca en la máquina local: correrlos localmente es perder tiempo. Lo mismo vale para linters, type-check, mutation testing y builds: **todo se lanza en el CI**.
2. **Se paralelizan siempre que sea posible**; no se lanzan en cola.
3. Cambios en el back lanzan solo los tests del back; cambios en el front, solo los del front.
4. **Las modificaciones de documentos no lanzan tests:** solo lo que tenga código.
5. Usar filtros por rutas (`paths`/`paths-ignore`) en los workflows para que cada job corra solo cuando cambian sus archivos.
6. Las cargas y pruebas de caos (Locust, matar workers, reiniciar el broker) también se lanzan en la nube (workflow manual o programado), nunca en local, y no corren en cada PR por su costo y duración.

## 12. Fragilidad de código y cobertura (mutation testing con AST)
1. Para medir la fragilidad se usa **AST**: se altera el código intencionalmente (mutantes) y se vuelven a lanzar los tests. Si los tests siguen pasando, esa línea no estaba realmente cubierta.
2. Los mutantes que sobreviven se arreglan escribiendo o mejorando tests, y se lanza AST de nuevo, en ciclo, hasta cumplir el coverage real necesario.
3. **AST solo se lanza sobre archivos nuevos o modificados**, nunca sobre archivos que no cambiaron.
4. Este set de tests se lanza **paralelizado en la nube, en GitHub**.
5. Validar la línea base antes de mutar: la suite debe pasar sin modificar el código, o todo mutante se contaría como "muerto" y saldría un falso 100%.
6. Mutantes equivalentes (p. ej. `round(x, 2)` → `round(x, 3)`): reportarlos, no escribir tests artificiales.
7. **Obligatorio en los módulos críticos** (dinero, seguridad, concurrencia, contratos públicos). En el resto es opcional y lo decide cada proyecto. Un archivo obligatorio por debajo del puntaje mínimo bloquea el PR.
8. Las carpetas críticas y el puntaje mínimo no viven en este archivo, porque cambian de un proyecto a otro: se definen en `state/config.json` (`mutation_critical_paths` y `mutation_min_score`). `python -m scripts.mutation_targets --base origin/main` lista, entre los archivos modificados, cuáles son obligatorios y cuáles opcionales, y el puntaje mínimo. El motor de mutación y su job de CI son propios de cada proyecto y llaman a ese script.

## 13. Verificación
1. Verificar tras cualquier cambio de motor contra valores base documentados, en el CI.
2. **Un script que dice PASS no prueba que midió lo correcto:** combinar consistencia interna (dos corridas coinciden) con un valor externo conocido.
3. **Fallar en voz alta, no fabricar:** si una comprobación no pudo ejecutarse (dependencia faltante, credenciales), devolver un error real y nunca un resultado vacío que parezca un pass.
4. **Fallar rápido:** validar credenciales y configuración antes de gastar minutos de cómputo.
5. Nunca dejar fixtures o archivos de referencia de verificación dentro del proyecto después de usarlos.
6. Validar con reclamos reales de punta a punta en el entorno desplegado, no solo con tests.

## 14. Depuración, carga y caos
1. Ante un fallo entre contenedores, aislar el transporte de la aplicación: escribir el script mínimo que ejercite solo esa conexión y correrlo con `docker exec` dentro del contenedor que falla.
2. Si el script pasa, el bug está en el flujo de control o el manejo de excepciones de la app, no en Docker, DNS ni la red.
3. **Una dependencia faltante ≠ una config faltante:** ambas se ven como `500` opaco; revisar el traceback del servidor antes de suponer.
4. Documentar los postmortems.
5. Validar con carga real (Locust) y con caos: matar workers, reiniciar el broker y verificar invariantes en SQL (cero duplicados, cero perdidos, nada colgado).
6. Medir el escalado pausando los workers (`docker pause`), no con `stop`/`start`.
7. Cuidar los healthchecks pesados: pueden mantener un broker inactivo con CPU alta.

## 15. Entorno y dependencias
1. **Nunca llamar `subprocess.run(["pytest", ...])` con un nombre de comando "desnudo":** usar `[sys.executable, "-m", ...]` para fijar el intérprete y no depender del PATH ambiental.
2. Checkouts/worktrees paralelos: un script instalado en modo editable puede apuntar a otro checkout; verificar con `pip show` antes de confiar en una corrida.
3. Pinnear versiones exactas de paquetes acoplados (p. ej. fastapi/starlette) y reinstalar limpio si se desincronizan.
4. Documentar las variables de entorno en una tabla con descripción y valor por defecto.

## 16. Infraestructura y despliegue
1. Una imagen Docker por servicio, con solo dependencias de producción y usuario no root.
2. Etiquetar las imágenes con el commit, nunca con `latest`.
3. Toda la infraestructura como código (Terraform) con state versionado.
4. Scripts para apagar y prender el entorno de demo y así controlar costos.
5. Actualizar la documentación de infraestructura en el mismo PR que cualquier cambio de infra.
6. No cambiar de broker ni de proveedor sin confirmar, y documentar cada decisión con su fecha.

## 17. Cuándo pausar y confirmar
1. Confirmar con el usuario antes de tocar:
   - DELETE o UPDATE sin WHERE.
   - Migraciones que borren columnas o tablas.
   - La lógica ACK/NACK.
   - Herramientas públicas (renombrar o quitar) o guardas de escritura.
   - Umbrales de una guarda de seguridad (bajarlos) o los operadores/umbrales de medición sin re-medir y actualizar docs en el mismo cambio.
   - Fixtures que afectan todos los números documentados.
   - `.env` y secretos.
   - Archivos de modelos, routers o registro de herramientas (listar el impacto antes de borrar o mover).
   - Números publicados sin una medición real detrás.
2. Antes de una migración, verificar la revisión actual (`alembic current`) y confirmar el destino con el usuario; aplica igual a la base de la nube.
3. Proteger con un hook de denegación dura el archivo de roadmap personal (`PENDING.md`): se puede editar su contenido, nunca borrarlo ni vaciarlo.
4. Al rechazar una acción, decir siempre la alternativa correcta en la misma respuesta.

## 18. Linters, ramas, commits y PRs
### Linters
1. Los linters y el type-check (`ruff`, `mypy`, y los del front) corren en el CI, no en local.
2. Se lanzan solo sobre lo modificado (el diff), y solo el linter del lado que cambió (back o front).
3. No corren en cambios que sean solo documentos.

### Ramas y commits
4. GitHub Flow: un `main` siempre desplegable y ramas cortas. **Paso 0, siempre:** antes de modificar cualquier archivo, revisar la rama y el working tree (`git status` y `git branch`), porque hay múltiples agentes trabajando en el proyecto. Nunca empezar a trabajar en la rama actual por defecto: crear antes una rama nueva y aislada para la tarea.
5. **El nombre de la rama representa la tarea** (`feat/`, `fix/`, `chore/` + descripción clara, p. ej. `feat/fuzzy-scoring-layer`).
6. **Sistema de tasks atómico:** una feature = un commit con nombre representativo.
7. Conventional Commits: `tipo(scope): descripción`.

### Pull requests
8. **Nunca hacer commit ni push a `main`.**
9. **Nunca mergear sin una directiva humana explícita.**
10. **El humano siempre aprueba el PR de forma manual.**
11. **El agente pregunta si crear el PR, salvo que el humano ya lo haya pedido en la instrucción.**
12. Al crear un PR, entregar en la respuesta el título y un comentario con la descripción, y escribirlos también en el PR si el entorno lo permite.
13. Los checks (linters, tests, AST) corren en el CI; pegar en el PR el enlace a la corrida y no una salida local.
14. Si un PR cambia un número medido, actualizar README/docs en el mismo PR.
15. Tras el merge que decida el humano, borrar la rama.

## 19. Presupuesto de tokens
1. Respuestas breves: tablas y listas, sin repetir la salida de herramientas.
2. No leer JSON de salida, imágenes ni fixtures salvo que la tarea lo requiera; leer solo la parte necesaria de un archivo y no releer lo recién escrito.
3. Máximo 3 subagentes por ronda, pasando a cada uno solo su archivo y sus datos, no el historial de la conversación.
