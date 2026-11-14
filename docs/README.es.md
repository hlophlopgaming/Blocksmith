# Blocksmith

[English](../README.md) · **Español** · [Français](README.fr.md) · [Deutsch](README.de.md) · [Русский](README.ru.md)

Dibuja prototipos de niveles editables en **Blender 5+** y expórtalos a **Godot**. Versión **0.8.7**, con licencia **GPL-3.0-or-later**.

Blocksmith es una implementación independiente inspirada en los flujos de trabajo de BlockD descritos públicamente. No incluye todas las funciones de BlockD. La interfaz admite inglés, español, francés, alemán y ruso. Elige el idioma en **Edit → Preferences → Interface → Translation** y activa **Interface** y **Tooltips**. Blocksmith sigue el idioma de Blender; conserva los nombres de los objetos existentes.

## Funciones

- Dibuja paredes, suelos, habitaciones, escaleras y rampas en la vista 3D; elige entre 32 preajustes con vista previa.
- Modifica dimensiones desde el panel lateral o los controles de la vista. Incluye puertas, ventanas, arcos, tejados, barandillas y paredes curvas.
- Ajusta a la cuadrícula y a vértices y aristas visibles, incluidos los resultados de Boolean y Array. Une paredes rectas a inglete, a tope o en T.
- Dibuja huecos no destructivos en mallas sólidas y repite objetos o huecos con la herramienta de filas.
- Conecta dos alturas con escaleras rectas o una rampa. Consulta referencias del jugador y avisos sobre escalones, pasos, coberturas y pendientes.
- Aplica las texturas de prototipado de Kenney, asigna etiquetas de juego y exporta GLB o FBX.
- Marca mallas para permitir su **colocación libre**, sin las restricciones geométricas de Blocksmith.
- Genera niveles a partir de JSON validado mediante una CLI de Python, sin instalar el complemento en tu sesión personal de Blender.


Desactiva **Activar Blocksmith en este archivo** en la parte superior del panel para modelar o esculpir libremente. El ajuste se guarda en el `.blend` y afecta a todas sus escenas. Las herramientas, atajos, indicaciones, actualizaciones automáticas y reversiones de geometría se pausan; el complemento sigue activado en Blender. Activa el mismo ajuste para continuar sin restaurar la geometría antigua. Los ajustes de ajuste nativos de Blender permanecen intactos.

## Instalación

1. Descarga `blocksmith-0.8.7.zip` desde [Releases](https://github.com/hlophlopgaming/Blocksmith/releases), o genera el archivo desde la raíz del repositorio:

   ```sh
   python3 tools/package.py
   ```

2. En Blender, abre **Edit → Preferences → Get Extensions → menú superior derecho → Install from Disk**. Selecciona el ZIP descargado o `dist/blocksmith-0.8.7.zip` y activa la extensión.
3. En la vista 3D, pulsa **N** y abre la pestaña **Blocksmith**.

La generación del ZIP requiere Python 3.10+, sin dependencias externas. Los archivos automáticos **Source code** de GitHub contienen el código fuente; no son ZIP de instalación de la extensión.

## Primeros pasos

1. Pulsa **Dibujar estructuras** o **Shift+Alt+D**.
2. Elige una forma en la fila superior o en **Siguiente estructura**. **Catálogo de preajustes** abre el catálogo de preajustes.
3. Arrastra con el botón izquierdo y suéltalo para crear la estructura. Selecciónala para cambiar sus dimensiones o utilizar los controles naranjas.
4. Activa **Repetir** para seguir dibujando. **Esc / botón derecho** cancela el gesto actual o vuelve a la selección.

Durante el dibujo normal, **Ctrl** desactiva temporalmente el ajuste, **Shift** limita la dirección a intervalos de 45° o crea una base cuadrada, **H** ajusta la altura y **F** invierte escaleras o rampas. Entre gestos puedes navegar y utilizar el panel.

Para una escalera recta o una rampa, arrastra desde el suelo inferior hasta el borde de la plataforma superior; también funciona al revés. Para puertas, ventanas y arcos, dibuja un rectángulo sobre una malla sólida: cada hueco añade un corte Boolean no destructivo. Las paredes curvas se crean mediante puntos, un trazo libre o un arco de tres puntos. Consulta el [manual detallado en ruso](manual.ru.md) para los controles de las herramientas avanzadas.

## Colocación libre

Selecciona una malla y activa **N → Blocksmith → Ignorar reglas de Blocksmith**. Es una propiedad persistente del objeto, disponible en los modos Objeto y Edición. Para varias mallas seleccionadas, usa **Aplicar a seleccionados** después de activar la opción en la malla activa.

Las mallas marcadas pueden solaparse con otros objetos, moverse, girar, escalarse, tener escala negativa y recibir modificaciones manuales o normales invertidas sin que Blocksmith revierta los cambios. Otros módulos también pueden solaparse con ellas. La marca no cambia geometría, materiales ni etiquetas de juego; se conserva al duplicar, convertir a malla y guardar o cargar un `.blend`. La malla sigue disponible para ajuste y exportación, salvo que su función ya la excluya, como ocurre con cortadores o figuras de referencia.

Desactivar la opción restaura la protección habitual del módulo. Si su estado actual incumple las restricciones, la protección permanece desactivada: se conservan la malla y sus cambios manuales. Corrige primero los solapamientos, la escala o las normales. Las mallas normales de Blender no tienen estas restricciones aunque no estén marcadas. La operación permite deshacer y rehacer.

Para scripts, selecciona las mallas y ejecuta:

```python
obj.bs.free_placement = True
bpy.ops.blocksmith.free_placement(enabled=True)
bpy.ops.blocksmith.free_placement(enabled=False)
```

La marca omite la validación: la geometría marcada puede exportarse con solapamientos o defectos. El ajuste de Blender y las indicaciones de dimensiones son opciones independientes. Una transformación del objeto padre aún puede rechazarse si afecta a un hijo protegido.

## Protección de la geometría

Los módulos de Blocksmith sin marca rechazan intersecciones, escala negativa o nula, mallas abiertas y normales invertidas. Se permite el contacto entre caras. Se comprueba la geometría evaluada, no solo las cajas delimitadoras. Las mallas normales o importadas, las referencias, el agua y los cortadores Boolean activos quedan fuera de estas comprobaciones de sólidos.

La protección cubre operaciones del complemento, transformaciones nativas, cambios al salir del modo de edición y deshacer/rehacer. La exportación vuelve a validar los módulos protegidos. Las escenas existentes se aceptan como punto de partida sin borrar objetos, pero los conflictos de módulos protegidos deben corregirse antes de exportar. Las comprobaciones son numéricas, pueden ser lentas en escenas complejas y no constituyen una garantía matemática.

## Exportación a Godot

Abre **Exportar a Godot**, elige **GLB** o **FBX**, los objetos que deseas exportar, la carpeta y el nombre de archivo. Guarda el `.blend` antes de usar una ruta relativa.

GLB es el formato principal probado. Con colisiones activadas, las mallas sólidas reciben el sufijo `-col` de Godot. El agua se exporta visible y sin colisión. Se excluyen las referencias, los cortadores utilizados, los archivos ocultos de las mallas originales y los objetos temporales de protección. Las paredes curvas se convierten en mallas. No se sobrescriben archivos existentes: elige otro nombre o carpeta.

## CLI JSON

Desde la raíz del repositorio, con Python 3.10+ y Blender 5+ en `PATH`:

```sh
python3 tools/levelgen.py shapes
python3 tools/levelgen.py presets
python3 tools/levelgen.py schema
python3 tools/levelgen.py validate examples/courtyard.json
python3 tools/levelgen.py generate examples/courtyard.json --out-dir generated/courtyard
```

Se generan `level.blend`, `level.glb`, `level.spec.json`, `report.json` y `blender.log`. Usa `--blender /ruta/a/blender` para indicar otro ejecutable y `--overwrite` para reemplazar resultados anteriores. Blender se ejecuta en un proceso separado en segundo plano; un fallo de validación conserva las exportaciones anteriores. La salida es JSON y los errores usan stderr y un código de salida distinto de cero.

La especificación utiliza **metros**, coordenadas de Blender con **Z hacia arriba** y ángulos de Euler en **grados**. GLB convierte las coordenadas al eje Y vertical de Godot. Consulta el [esquema](../examples/level.schema.json), los [ejemplos](../examples/) y el comando `schema`. Se rechazan claves desconocidas, nombres duplicados, números inválidos y complejidad excesiva; JSON nunca ejecuta Python. La marca de colocación libre es una opción de la malla en Blender, no un campo del esquema CLI actual.

## Desarrollo y comprobaciones

```sh
python3 -m unittest discover -s tests -p 'test_*.py' -v
blender -b -noaudio --factory-startup --python-exit-code 1 --python tests/free_placement_check.py
blender -b -noaudio --factory-startup --python-exit-code 1 --python tests/guard_check.py
python3 tools/package.py
```

Consulta [CONTRIBUTING](../CONTRIBUTING.md), [CHANGELOG](../CHANGELOG.md) y el [informe de validación de 0.8.3](validation-0.8.3.md), actualmente en ruso. GitHub Actions está configurado para ejecutar pruebas de Python, comprobar la sintaxis y generar el ZIP. Las pruebas de la vista 3D necesitan un entorno gráfico. Las copias de seguridad, compilaciones y escenas generadas se excluyen de Git.

## Límites actuales

Blender 5.0 es el mínimo declarado, pero no se ha probado por separado. Las comprobaciones anteriores abarcaron Blender 5.2.3, 5.3.0 y Godot 4.7.2. FBX tiene menos cobertura que GLB. Las cadenas de paredes no se cierran automáticamente ni desplazan las paredes vecinas al editar una. Usa **Shift+D** para copias editables independientes; **Alt+D** comparte la malla, pero no sus parámetros. Apply Scale admite escala positiva uniforme en mallas paramétricas sin editar y con un único usuario. Las indicaciones no simulan un controlador de juego. Las colisiones exportadas son mallas de triángulos estáticas. La geometría de prototipado puede necesitar optimización para producción.

## Licencia

Código de Blocksmith: **GPL-3.0-or-later**, véase [LICENSE](../LICENSE). El ZIP de instalación incluye una copia.

[Kenney Prototype Textures](https://kenney.nl/assets/prototype-textures): **CC0**. Se conservan su [licencia](../blocksmith/assets/kenney/License.txt) e [información de origen](../blocksmith/assets/kenney/SOURCE.txt).
