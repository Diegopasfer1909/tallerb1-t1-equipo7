# Diagramas de arquitectura

[`ARQUITECTURA.md`](../ARQUITECTURA.md) reúne cuatro vistas de B1–T1 con su explicación: arquitectura (01), dominio (02), dependencias (05) y flujo de la consola (06). Cubren lo que pide el apartado 4.6 del enunciado: jerarquía de clases, dependencias y flujo.

Cada vista tiene dos archivos:

| Formato | Uso |
| --- | --- |
| `.mmd` | Fuente en Mermaid, editable como texto. Es el original: se cambia a mano cuando cambia el código. No fija colores, para que se lea con el tema claro u oscuro del visor. |
| `.png` | Exportación del `.mmd`, para `ARQUITECTURA.md`, diapositivas y documentos. |

## Ver los diagramas en VS Code

VS Code no dibuja Mermaid por sí solo. Instala una de estas extensiones desde la vista de extensiones (`Ctrl+Shift+X`):

| Extensión | Para qué sirve |
| --- | --- |
| Mermaid Chart (`MermaidChart.vscode-mermaid-chart`) | Abre los `.mmd` de esta carpeta con vista previa. |
| Markdown Preview Mermaid Support (`bierner.markdown-mermaid`) | Dibuja los bloques Mermaid que se escriban dentro de un `.md` en la vista previa de Markdown (`Ctrl+Shift+V`, o `Ctrl+K V` para verla al lado). |

`ARQUITECTURA.md` no necesita ninguna: muestra los PNG, que la vista previa normal ya dibuja. GitHub dibuja Mermaid directamente, y <https://mermaid.live> permite editar un `.mmd` en el navegador.

## Volver a exportar un PNG

Después de cambiar un `.mmd`, exporta su PNG con [mermaid-cli](https://github.com/mermaid-js/mermaid-cli) (necesita Node.js). Desde la raíz del repositorio:

```bash
npx -p @mermaid-js/mermaid-cli mmdc -i diagramas/02-modelos-dominio.mmd -o diagramas/02-modelos-dominio.png -b white -s 2
```

`-b white` pone fondo blanco y `-s 2` duplica la resolución. Revisa la imagen antes de hacer commit, sobre todo los cruces de flechas y las etiquetas. Si no quieres instalar nada, <https://mermaid.live> también exporta a PNG.
