# Documentacion Tecnica - Editor WhatsApp Pro

## 1. Objetivo

Editor WhatsApp Pro es una aplicacion GUI de escritorio para preparar mensajes con sintaxis compatible con WhatsApp, trabajar sobre archivos de texto y copiar el contenido final al portapapeles sin perder emojis visuales ni formato textual.

El objetivo del proyecto no es construir un editor WYSIWYG general, sino un editor pragmatico para flujos de redaccion cortos y medianos en Windows.

## 2. Stack tecnico

- Python
- `tkinter`
- `ttk.Notebook`
- `customtkinter`
- `Pillow`
- `pyperclip`

Dependencias runtime actuales en `requirements.txt`:

- `customtkinter`
- `pyperclip`
- `pillow`

## 3. Estructura del repositorio

```text
EditorWhatsapp/
  main.py
  README.md
  DOCUMENTACION_TECNICA.md
  requirements.txt
  generate_icon.py
  icon2.ico
  Editor WhatsApp Pro.spec
  Editor WhatsApp Pro.exe
  build/
  dist/
```

Archivos relevantes:

- `main.py`: toda la aplicacion, incluyendo UI, serializacion, emojis, sesion y archivos.
- `README.md`: guia corta de uso e instalacion.
- `DOCUMENTACION_TECNICA.md`: esta documentacion.
- `generate_icon.py`: utilitario de generacion del icono.
- `Editor WhatsApp Pro.spec`: configuracion de PyInstaller.

## 4. Arquitectura general

La aplicacion usa una arquitectura monolitica orientada a eventos.

Componentes principales:

- `WhatsAppEditor(ctk.CTk)`: ventana principal y coordinador de toda la app.
- `DocumentState`: dataclass por pestana con referencia al `Text`, estado de modificacion, caches y metadatos.
- `tk.Text`: motor real de edicion.
- `ttk.Notebook`: contenedor de multiples documentos.

No hay separacion por capas o modulos. La ventaja es simplicidad; la desventaja es acoplamiento alto y dificultad para testear partes aisladas.

## 5. Modelo de datos interno

`DocumentState` mantiene el estado de cada documento abierto:

- `frame`: contenedor visual de la pestana.
- `text`: widget `tk.Text`.
- `file_path`: ruta del archivo asociado o `None`.
- `is_modified`: bandera de cambios sin guardar.
- `suspend_change_events`: evita recalculos durante inserciones programaticas.
- `syntax_after_id`: id del `after` usado para debounce de resaltado.
- `last_highlight_source`: ultimo texto plano procesado por el resaltado.
- `emoji_map`: relacion `nombre_imagen -> emoji Unicode real`.
- `emoji_counter`: contador para generar nombres unicos de imagen.
- `interactive_ranges`: rangos detectados para links, correos, telefonos y fechas.
- `stats_after_id`: id del `after` usado para debounce de contadores.
- `message_cache`: ultimo mensaje reconstruido completo.
- `message_cache_dirty`: invalida o reutiliza el cache de serializacion.

## 6. Construccion de la interfaz

### 6.1 Toolbar superior

Incluye:

- Menu Archivo
- Menu Editar
- Menu Vista
- Botones rapidos de formato
- Boton principal "Copiar para WhatsApp"

### 6.2 Sidebar de emojis

- Agrupa emojis por categoria.
- Renderiza cada emoji con Pillow y lo muestra como `CTkButton`.
- Inserta el emoji al editor como imagen embebida cuando es posible.

### 6.3 Area central

- Usa `ttk.Notebook` para multiples documentos.
- Cada pestana aloja un `tk.Text` configurado con tags para sintaxis y deteccion inteligente.

### 6.4 Barra de estado

- Muestra caracteres, palabras y nombre del documento.
- Advierte cuando el contenido se acerca o supera el limite practico configurado para "Leer mas".

## 7. Flujo funcional

### 7.1 Creacion de documento

`create_document_tab()`:

1. Crea `Frame` y `Text`.
2. Configura tags visuales.
3. Registra bindings del editor.
4. Crea `DocumentState`.
5. Inserta contenido inicial, si existe.

### 7.2 Edicion

`on_content_changed()`:

1. Marca el documento como modificado.
2. Invalida el cache de serializacion.
3. Actualiza el titulo de la pestana.
4. Agenda actualizacion de contadores.
5. Agenda resaltado sintactico.

### 7.3 Resaltado sintactico

`apply_syntax_highlighting()`:

- Obtiene texto plano via `Text.get("1.0", tk.END)`.
- Compara con `last_highlight_source`.
- Limpia tags previos.
- Recorre regex de formato:
  - negrita
  - cursiva
  - tachado
  - inline code
  - bloque de codigo
- Recorre regex de estructura:
  - citas
  - listas
  - listas numeradas
- Recorre regex interactivas:
  - enlaces
  - correos
  - telefonos
  - expresiones de fecha/hora

### 7.4 Insercion visual de emojis

`_insert_text_with_visual_emojis()`:

1. Recorre el string pegado o cargado.
2. Detecta secuencias emoji simples, compuestas y keycap.
3. Inserta texto normal en bloque.
4. Inserta emojis como imagen embebida o como fallback textual.

`get_emoji_image_tk()`:

- Renderiza el emoji sobre un canvas RGBA.
- Recorta con margen.
- Reescala manteniendo relacion de aspecto.
- Convierte a `ImageTk.PhotoImage`.
- Cachea por `(emoji, size)`.

### 7.5 Reconstruccion del mensaje real

`_reconstruct_range_from_editor()` usa `Text.dump(..., text=True, image=True)` para serializar:

- nodos de texto
- objetos imagen

Si encuentra una imagen, busca el Unicode real en `emoji_map`.

Casos de uso:

- exportar a WhatsApp
- guardar archivo
- persistir sesion
- copiar/cortar seleccion
- actualizar contadores

### 7.6 Copiar, cortar y borrar seleccion

La app no depende solo del comportamiento por defecto de Tk para estos casos.

Metodos relevantes:

- `copy_selection()`
- `cut_selection()`
- `delete_selection()`

Esto evita inconsistencias entre:

- lo visible en el `Text`
- lo realmente serializado
- los emojis embebidos

### 7.7 Persistencia de sesion

`save_session()` y `load_session()` almacenan la lista de documentos en:

`%APPDATA%/.whatsapp_editor_session.json`

Se guarda:

- titulo derivado
- contenido reconstruido
- ruta del archivo
- bandera de modificacion

## 8. Eventos y bindings

Bindings actuales por documento:

- `Ctrl+C`: copiar seleccion serializada
- `Ctrl+X`: cortar seleccion serializada
- `Ctrl+V`: pegado inteligente
- `Ctrl+Z`: undo
- `Ctrl+Y`: redo
- `Ctrl+F`: buscar y reemplazar
- `Ctrl+Click`: accion interactiva sobre links, correos o telefonos
- `BackSpace`: elimina seleccion de forma explicita
- `Delete`: elimina seleccion de forma explicita
- `Return`: autocompleta listas y listas numeradas
- `Ctrl + rueda del mouse`: zoom

Binding global relevante:

- `Ctrl+F` sobre la ventana principal

## 9. Optimizaciones implementadas

### 9.1 Cache del mensaje reconstruido

Problema anterior:

- `update_counters()` reconstruia todo el documento en cada cambio.
- Eso implicaba recorrer el `Text.dump()` completo con frecuencia alta.

Solucion aplicada:

- `DocumentState.message_cache`
- `DocumentState.message_cache_dirty`

Resultado:

- Guardado, exportacion y contadores pueden reutilizar el ultimo mensaje cuando no hubo cambios nuevos.

### 9.2 Debounce de contadores

Problema anterior:

- Cada `KeyRelease` disparaba calculo inmediato de caracteres y palabras.

Solucion aplicada:

- `schedule_counters_update()`
- delay configurable con `STATS_REFRESH_DELAY_MS`

Resultado:

- Menor trabajo repetido durante escritura rapida.

### 9.3 Limpieza de `emoji_map`

Problema anterior:

- Al borrar emojis embebidos, sus entradas podian seguir en `emoji_map`.
- Esto no siempre generaba error funcional, pero si retencion innecesaria de referencias.

Solucion aplicada:

- Durante la reconstruccion completa se podan claves que ya no existen en el documento.

Resultado:

- Menor acumulacion de basura logica por documento.

### 9.4 Copiado y corte deterministas

Problema anterior:

- El comportamiento por defecto de `tk.Text` no siempre era consistente con contenido embebido y serializacion custom.

Solucion aplicada:

- `Ctrl+C` y `Ctrl+X` reconstruyen explicitamente el rango seleccionado.

Resultado:

- Coherencia entre seleccion visible, texto copiado y exportacion final.

## 10. Build y distribucion

`Editor WhatsApp Pro.spec`:

- incluye `icon2.ico` como data
- excluye paquetes pesados no usados:
  - `matplotlib`
  - `numpy`
  - `pandas`
  - `scipy`
  - `IPython`
  - `jedi`
  - `pytest`
  - `PyQt5`
  - `qtpy`
- usa `optimize=2`
- `console=False`
- `upx=False`

Compilacion:

```bash
pyinstaller "Editor WhatsApp Pro.spec"
```

Salida esperada:

- `dist/Editor WhatsApp Pro.exe`

## 11. Limitaciones actuales

### 11.1 Monolito

Toda la logica esta en `main.py`. Eso dificulta:

- pruebas unitarias
- reuso
- mantenimiento
- separacion entre UI y logica de dominio

### 11.2 Resaltado completo por documento

Aunque el resaltado esta amortiguado con `after`, sigue recorriendo el documento entero y aplicando regex globales.

Impacto:

- escalado peor en textos largos
- mas trabajo de tags en el widget

### 11.3 Dependencia fuerte de Windows

- fuente `seguiemj.ttf`
- manejo de icono
- build orientado a `.exe`

### 11.4 Cobertura de tests

No existe suite automatizada para:

- reconstruccion de mensajes
- parser de emojis
- busqueda y reemplazo
- persistencia de sesion
- regresiones de copiado/corte/borrado

### 11.5 Atajos incompletos

El README historico listaba algunos atajos no implementados como `Ctrl+N`, `Ctrl+O` o `Ctrl+S`.
Actualmente esas acciones existen por menu, no por binding de teclado.

## 12. Recomendaciones de optimizacion futuras

### 12.1 Modularizacion

Separar al menos en:

- `ui/`
- `editor/`
- `emoji/`
- `persistence/`
- `services/clipboard.py`

### 12.2 Parser y serializer aislados

Extraer:

- deteccion de emojis
- reconstruccion desde `Text.dump`
- logica de seleccion

Esto permitiria pruebas unitarias puras sin GUI.

### 12.3 Cache de texto plano para resaltado

Hoy el cache cubre la reconstruccion completa del mensaje, pero no el texto plano del resaltado.
Se puede añadir un cache incremental o al menos un snapshot de texto por documento para reducir llamadas repetidas a `Text.get`.

### 12.4 Persistencia incremental

La sesion solo se guarda al cerrar. Se podria:

- guardar cada N segundos
- guardar tras cambios relevantes
- mantener backup de recuperacion

### 12.5 Telemetria local y logging

Agregar logging opcional para:

- errores de apertura y guardado
- fallos de render emoji
- tiempos de reconstruccion y resaltado

## 13. Escenarios de prueba recomendados

1. Escribir texto largo y verificar que los contadores sigan responsivos.
2. Insertar emojis desde el panel y copiar una seleccion parcial.
3. Borrar texto con emojis y verificar exportacion sin residuos.
4. Abrir archivo UTF-8 y CP1252.
5. Guardar, cerrar y recuperar sesion.
6. Probar links, correos y telefonos con `Ctrl+Click`.
7. Probar listas automaticas con `Return`.

## 14. Resumen ejecutivo

El proyecto es funcional y tiene una base razonable para un editor especializado de escritorio. Los principales riesgos tecnicos no son bugs estructurales graves, sino concentracion de logica en un solo archivo, ausencia de pruebas automatizadas y costo de operaciones globales sobre el documento.

Las optimizaciones aplicadas en esta revision reducen trabajo repetido en el ciclo de escritura y mejoran la coherencia del contenido serializado frente a operaciones de copiado, corte y borrado.
