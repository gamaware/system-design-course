# Iconos oficiales de las cuatro nubes

El ejercicio usa los iconos oficiales de cada proveedor. **Ni los paquetes ni los iconos se guardan en el
repositorio**: `scripts/fetch-icons.sh` descarga cada paquete en el build, verifica su sha256 contra
`icons/packages.tsv` y extrae a `dist/icons/` solo los iconos que usan los puzzles. Lo que sí se guarda es
`icons/registry.json`, que relaciona cada id de servicio con el archivo dentro del paquete (son nombres, no
imágenes).

## Paquetes

Revisados el 2026-10-16 en la página oficial de cada proveedor.

| Nube | Página oficial | Paquete | Tamaño | sha256 |
| --- | --- | --- | --- | --- |
| AWS | <https://aws.amazon.com/architecture/icons/> | `Icon-package_07312026.zip` (versión del tercer trimestre de 2026) | 13,988,918 bytes | `d2d166c453526471749d520e0db022c459abef759d2946cf2dd1d1c992dc6526` |
| Azure | <https://learn.microsoft.com/en-us/azure/architecture/icons/> | `Azure_Public_Service_Icons_V24.zip` (Last-Modified 2026-07-08) | 1,033,184 bytes | `921594ccd1bf3d9c0a1bd7b6d924e050551a59342f2b353bb74bdcf761c35141` |
| Google Cloud | <https://cloud.google.com/icons> | `core-products-icons.zip` | 318,678 bytes | `6531a10f58bc599c24d9a455d81dd757c1a03c3c43da9cddf639b859c1c1eece` |
| Google Cloud | <https://cloud.google.com/icons> | `category-icons.zip` | 795,968 bytes | `e5bc3abd3527dc2500e9bff7f15870783e2c764129c49b7cd4c1b4e105345002` |
| Google Cloud (logotipo) | <https://www.googlecloudpresscorner.com/digital-assets> | `Google_Cloud_Logos.zip` (archivos de agosto de 2026) | 2,135,311 bytes | `0a73eb09d64be3de2a979153e83d24653e483009a1c5a6d57781472a6ce184c1` |
| Oracle Cloud | <https://docs.oracle.com/en-us/iaas/Content/General/Reference/graphicsfordiagrams.htm> | `OCI-Style-Guide-for-Drawio.zip` (Last-Modified 2024-04-29, librería v24.2) | 6,997,183 bytes | `8e20646de88b6197f7b2ce941219fdb61e88b2b6276e3e7b5e0ce046445174e8` |

URL de descarga de cada paquete (las mismas de `icons/packages.tsv`):

- AWS: <https://d1.awsstatic.com/onedam/marketing-channels/website/public/shared/architecture-icon-release/Icon-package_07312026.5846e92413caa21490223536cc97f1269e44fa92.zip>
- Azure: <https://arch-center.azureedge.net/icons/Azure_Public_Service_Icons_V24.zip>
- Google Cloud: <https://services.google.com/fh/files/misc/core-products-icons.zip> y
  <https://services.google.com/fh/files/misc/category-icons.zip>; logotipo:
  <https://www.googlecloudpresscorner.com/download/Google_Cloud_Logos.zip>
- Oracle Cloud: <https://docs.oracle.com/iaas/Content/Resources/Assets/OCI-Style-Guide-for-Drawio.zip>

Notas por proveedor:

- **AWS** publica versiones trimestrales (enero, abril y julio) y cambia el nombre del archivo en cada una.
- **Google Cloud** cambió su sistema de iconos en 2025: unos 20 productos centrales tienen icono propio y el
  resto usa el icono de su categoría, según la guía `google-cloud-product-icons.pdf` de la misma página
  (versión de mayo de 2026). Por eso el grupo de instancias administrado, los balanceadores, Certificate
  Manager, Cloud KMS y Cloud Monitoring muestran el icono de su categoría. Recommender no aparece en esa guía;
  se usa la categoría Management Tools.
- **Oracle** no publica archivos SVG: ofrece la librería de draw.io, un PowerPoint y plantillas de Visio. El
  build lee las figuras de `OCI Library.xml` (geometría vectorial de draw.io) y las escribe como SVG con los
  mismos trazos, colores y proporciones; se comparó contra la exportación de draw.io y coinciden. La librería
  es de abril de 2024.
- El selector de nube de la portada y los enlaces a la misma arquitectura en otra nube muestran un icono por
  nube (`clouds` en `registry.json`): el logotipo de AWS Cloud del paquete de grupos de AWS y el icono Azure A
  de Azure, y el logotipo de Google Cloud (`GC_Logo_FullColor_rgb.svg`) del paquete de logotipos que publica
  la sala de prensa de Google Cloud; como ese logotipo ya es el nombre escrito, el texto queda solo para
  lectores de pantalla. La librería de Oracle no trae el logotipo de la marca (su figura "Logical - Grouping -
  Oracle Cloud" es un rectángulo con el texto), así que se usa su figura genérica de nube (`logo_note`). En
  las demás nubes el nombre aparece junto al icono.
- Cuando un servicio no tiene icono propio en el paquete, `registry.json` usa el más cercano de la misma
  familia y lo explica en `icon_note` (por ejemplo, el launch template de AWS usa el recurso AMI).

## Términos de uso

**AWS** (página de iconos): "We allow customers and partners to use these toolkits and assets to create
architecture diagrams." y "You can also put icons in materials like whitepapers, presentations, data sheets, and
posters." Aplican también los [AWS Trademark Guidelines](https://aws.amazon.com/trademark-guidelines/): no
alterar las imágenes ni sugerir patrocinio; la sección 15 dice "AWS does not object to limited fair use of such
materials for educational or non-profit purposes."

**Microsoft Azure** (página de iconos y `Microsoft_Terms_of_Use.pdf` dentro del zip): "Microsoft permits the use
of these icons in architectural diagrams, training materials, or documentation. You may copy, distribute, and
display the icons only for the permitted use unless granted explicit permission by Microsoft." Las reglas del
mismo PDF: "Don't crop, flip or rotate icons", "Don't distort or change icon shape in any way" y "Don't use
Microsoft product icons to represent your product or service". El `Azure_Icons_FAQ.pdf` pide que "the full name
of the service should always appear near the icon"; por eso las fichas de Azure muestran el nombre completo.

**Google Cloud**: la [página de iconos](https://cloud.google.com/icons) no trae términos propios; los describe
como "the Google Cloud product icons you need for your diagrams, technical documentation, and more". Aplican las
[guías de marca de Google](https://about.google/brand-resource-center/rules/), que piden no imitar el "trade
dress" de Google, incluidos sus "product icons", ni sugerir afiliación. El logotipo de Google Cloud sale de la
[sala de prensa](https://www.googlecloudpresscorner.com/digital-assets) ("Download Google Cloud product logos,
suitable for print or web"), y la [guía de uso de la marca](https://about.google/brand-resource-center/guidance/)
lo permite sin solicitud en materiales de enseñanza: "You can use unaltered static screenshots or video captures
of our products, the Google logo, or specific product icons for educational purposes in textbooks or other
standard teaching materials." Las reglas piden además "Use only Google-approved artwork when using Google's
logos"; por eso se usa el archivo del paquete sin cambios.

**Oracle Cloud** (página de la librería): "Use these assets to draw custom architecture diagrams for your OCI
implementation." Aplican los [Oracle Trademarks](https://www.oracle.com/legal/trademarks/): "You may not use
Oracle trademarks in a manner which could cause confusion as to Oracle sponsorship, affiliation or endorsement."

Evaluación propia, sin ser opinión legal: el uso cabe en lo permitido, porque el sitio solo dibuja diagramas de
arquitectura con fines educativos. Para quedarse dentro de los términos:

- Los iconos no se modifican, no se recolorean ni se recortan. El estado de una ficha o un slot se marca con
  contornos, insignias y la opacidad de la ficha, nunca tiñendo el icono. Al incrustarlos como `<symbol>` el
  build solo quita el prólogo XML, los comentarios y `<title>`, y prefija los id y las clases de CSS para que no
  choquen entre iconos.
- No se usa ningún logotipo de proveedor como marca del sitio. El pie de página nombra el paquete de origen y
  dice que el ejercicio no está afiliado ni respaldado por AWS, Microsoft, Google ni Oracle.
- Las personas, internet y el equipo de guardia usan iconos neutros propios (`gen-*`), no los de un proveedor.

## Actualizar un paquete

1. Copia la URL vigente desde la página oficial (el nombre cambia en cada versión).
2. Descárgala, calcula su sha256 y actualiza la línea en `icons/packages.tsv` y la tabla de este archivo.
3. Si cambian rutas dentro del zip, ajusta `icons/registry.json`; `scripts/fetch-icons.sh` falla y dice qué
   archivo falta.
4. Corre `./build.sh` y revisa el resultado en el navegador.

Si el sha256 de una descarga no coincide, el script se detiene sin extraer nada: el proveedor cambió el paquete
y hay que revisarlo antes de confiar en él.
