# Editor WhatsApp Pro

Aplicacion de escritorio en Python para redactar mensajes orientados a WhatsApp sobre un editor tipo documento, con soporte para archivos `.md` y `.txt`, vista previa visual de emojis y copiado limpio al portapapeles.

## Funcionalidades

- Editor multi-pestana basado en `tk.Text` y `ttk.Notebook`.
- Formato compatible con WhatsApp: `*negrita*`, `_cursiva_`, `~tachado~`, `` `inline code` `` y bloques ``` ``` .
- Panel lateral de emojis renderizados como imagen a color dentro del editor.
- Deteccion interactiva de enlaces, correos, telefonos y expresiones de fecha/hora.
- Pegado inteligente con conversion automatica de emojis Unicode a representacion visual.
- Exportacion a portapapeles mediante "Copiar para WhatsApp".
- Persistencia de sesion en el perfil del usuario.

## Requisitos

- Windows
- Python 3.10 o superior recomendado
- Fuente de emojis de Windows (`seguiemj.ttf`) para render visual completo

## Instalacion

```bash
pip install -r requirements.txt
```

## Ejecucion

```bash
python main.py
```

## Atajos disponibles

- `Ctrl+C`: copiar seleccion reconstruyendo texto real y emojis embebidos.
- `Ctrl+X`: cortar seleccion reconstruyendo texto real y emojis embebidos.
- `Ctrl+V`: pegado inteligente con procesamiento de emojis.
- `Ctrl+Z`: deshacer.
- `Ctrl+Y`: rehacer.
- `Ctrl+F`: abrir Buscar y Reemplazar.
- `Ctrl+Click`: abrir enlace o correo; en telefonos copia el numero al portapapeles.
- `Ctrl + rueda del mouse`: zoom.

Nota: acciones como nuevo, abrir y guardar estan disponibles por menu, pero actualmente no tienen atajo global definido en codigo.

## Estructura del proyecto

- `main.py`: aplicacion principal.
- `requirements.txt`: dependencias runtime.
- `DOCUMENTACION_TECNICA.md`: documentacion tecnica completa.
- `generate_icon.py`: generacion del icono.
- `Editor WhatsApp Pro.spec`: build de PyInstaller.
- `dist/`: ejecutables generados.
- `build/`: artefactos temporales de compilacion.

## Compilacion a ejecutable

```bash
pyinstaller "Editor WhatsApp Pro.spec"
```

El ejecutable se genera en `dist/Editor WhatsApp Pro.exe`.

## Optimizaciones aplicadas

- Cache del mensaje reconstruido por documento para evitar serializar todo el editor en cada pulsacion.
- Debounce de actualizacion de contadores para reducir trabajo repetido durante escritura rapida.
- Limpieza automatica de referencias de emojis eliminados para evitar crecimiento innecesario de memoria.
- Copiado y corte de seleccion implementados de forma explicita para mantener consistencia entre lo visible y lo exportado.

## Limitaciones actuales

- El proyecto sigue concentrado en un solo archivo principal.
- No hay suite automatizada de pruebas UI o regresion.
- El render visual de emojis depende del stack de Windows.
- El resaltado sintactico recorre el documento completo; aunque esta amortiguado con `after`, aun puede escalar peor en documentos muy grandes.

## Documentacion adicional

La descripcion de arquitectura, flujos, estado interno, build, limitaciones y roadmap se encuentra en `DOCUMENTACION_TECNICA.md`.
