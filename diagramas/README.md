# Diagramas de arquitectura

La [galería principal](../ARQUITECTURA.md) reúne siete vistas de B1–T1: arquitectura, dominio, proveedores, simulación, dependencias, actividad CLI y secuencia Alpha Vantage. [`vista-general.png`](vista-general.png) las muestra juntas.

| Formato | Uso |
| --- | --- |
| `.svg` | Lectura y ampliación vectorial. |
| `.png` | Inserción en diapositivas y documentos. |
| `.excalidraw` | Edición visual de cajas, textos y conexiones en Excalidraw. |
| `.mmd` | Modelo semántico editable como texto Mermaid; disposición automática independiente. |

Desde la raíz del repositorio, con el entorno del proyecto activado:

```powershell
python -m pip install pillow
python -B diagramas\generar_diagramas.py
```

El generador usa la biblioteca estándar de Python y **Pillow como única dependencia gráfica**; no forma parte de las dependencias del paquete. Usa Arial (`C:/Windows/Fonts/arial.ttf`); en otro sistema, indica otra fuente con la variable `DIAGRAM_FONT`. Mantiene las fuentes Excalidraw y sus exportaciones SVG/PNG. Para cambios persistentes de composición, edita `generar_diagramas.py`: una regeneración puede reemplazar los cambios manuales hechos en los archivos generados. Actualiza los `.mmd` manualmente para conservar la equivalencia semántica.

`verificacion.json` identifica fuentes y artefactos con hashes e indica si el código de `src` coincidía con el commit al generar. Comprueba ese manifiesto y revisa las imágenes después de regenerar, especialmente cruces, etiquetas, multiplicidades y cambios del código.
