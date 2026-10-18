# Cómo escribir un escenario de "completa el diagrama"

Guía corta para agregar los escenarios de `../ARCHITECTURES.md` al motor. El piloto es el Escenario 2
(`puzzles/e02-aws.json`, `e02-azure.json`, `e02-gcp.json`, `e02-oci.json`): cópialo y cambia lo necesario.

## Archivos

| Qué | Dónde |
| --- | --- |
| Un puzzle por (escenario, nube), texto en español | `puzzles/eNN-<nube>.json`, nube = `aws`, `azure`, `gcp` u `oci` |
| Traducción al inglés (opcional, mismos ids) | `puzzles/en/eNN-<nube>.json` |
| Esquema (draft 2020-12) | `schema/puzzle.schema.json` |
| Ids de servicio y su icono oficial | `icons/registry.json` (agrega ahí los que falten; nunca inventes un id en un puzzle) |
| Paquetes de iconos, URL y sha256 | `icons/packages.tsv`, explicados en `ICONS.md` |

## Comandos

```bash
python3 -I tools/build.py validate puzzles/e05-gcp.json   # hasta que diga "ok"; lee cada línea E-* y W-*
python3 -I tools/build.py validate puzzles                # todos
./build.sh                                                # valida, baja y verifica iconos, escribe dist/
node --test tests/ && python3 -m unittest discover -s tests
```

`./build.sh` deja el sitio en `dist/` (no se commitea). Abre `dist/index.html` directo desde el disco y juega el
escenario completo: correcto, incorrecto, pista y reintento. Para no descargar otra vez un paquete que ya tienes,
pasa su carpeta en `ARCH_ICON_LOCAL` (varias separadas por `:`); se usa solo si su sha256 coincide.

## Reglas del puzzle

- `id` = `<escenario>-<nube>` (por ejemplo `e05-oci`), igual al nombre del archivo. Es estable: el progreso del
  alumno se guarda con ese id.
- Las cuatro nubes de un escenario comparten la topología: mismos slots, nodos, flechas y celdas. Cambian los
  servicios, los tipos y etiquetas de grupo, las explicaciones y las fuentes.
- De 2 a 9 slots. Cada slot acepta un solo servicio (`accept` de largo 1) y cita sus fuentes en `refs`; cada
  URL de `refs` debe estar también en `source_refs` con su título.
- Un requisito por slot, con exactamente un hueco `{{sN}}` y `slot: "sN"`; su `n` es el número del slot. Los
  requisitos de contexto llevan `slot: null`, sin hueco, y el nodo que describen lleva ese número.
- `hint_cue` es un fragmento exacto del requisito (la pista 1 lo resalta). Sin Markdown dentro del fragmento.
- `explanation`: de 20 a 300 caracteres, por qué la respuesta cumple esas palabras del requisito.
- Paleta: cada respuesta una vez (`uses` = número de slots que la aceptan). El resto lleva `role`
  (`near-miss`, `distractor` o `filler`) y `why_not` por slot. Toma el distractor de la tabla de
  `ARCHITECTURES.md`; `near_miss` del slot apunta a él. Mínimo de distractores: 75 % del número de slots.
- Un distractor debe estar mal en todos los slots donde se pueda soltar. Si cabe en otro slot, es una segunda
  respuesta: cambia el requisito o quita la ficha.
- Todos los servicios del puzzle son de su nube (E-CLOUD); los genéricos `gen-users`, `gen-internet` y
  `gen-team` sirven en todas y necesitan `label`.
- Nada de rayas largas en ningún texto.

## Reglas del leak check (E-LEAK y E-ARTICLE)

El validador revisa el título, el resumen, los requisitos, las etiquetas de nodos, flechas, grupos y slots, en
español y en la traducción al inglés. Ninguno puede nombrar la respuesta de un slot. Cuenta como nombre:

- `label`, `short` y `aliases` del servicio en `icons/registry.json`;
- el nombre sin "Amazon", "AWS", "Azure", "Microsoft", "Google", "Google Cloud", "Oracle" ni "OCI";
- la forma entre paréntesis de la etiqueta.

La comparación es por palabra completa. Una palabra sola con mayúscula inicial ("Monitoring", "Compute") solo
cuenta si aparece con mayúscula; las demás no distinguen mayúsculas. Agrega a `aliases` las traducciones que
delatarían la respuesta ("máquina virtual", "grupo de Auto Scaling"). `mode` ("alarmas", "certificados") se
muestra en la ficha pero no entra al leak check.

Un artículo justo antes del hueco delata el género o el sonido de la respuesta: `el`, `la`, `los`, `las`, `un`,
`una`, `unos`, `unas`, `del`, `al` y `lo` en español; `a`, `an` y `the` en inglés. Pon el hueco al inicio
("{{s2}} mantiene...") o usa "El servicio que...".

Si de verdad hace falta nombrar una respuesta (rara vez), decláralo en `allow_mention` con la razón.

## Geometría

- Celda = 120 x 112 unidades; viewBox = `cols*120` x `rows*112`. Usa `cols` de 9 o menos para que el texto se
  lea. Coordenadas en celdas, con dos decimales como máximo.
- Un nodo o slot ocupa una caja de 108 x 104 a partir de su celda; no se pueden encimar.
- Un grupo hijo cabe en su padre con márgenes de 0.06 a los lados y abajo, y 0.22 arriba para la etiqueta.
  Los hermanos no se enciman, salvo los tipos que cruzan: zonas (`az`, `azure-zone`, `gcp-zone`,
  `oci-fault-domain`, `oci-ad`), `auto-scaling-group` y `security-group`.
- Las zonas se dibujan como columnas que cruzan las subredes, porque en Azure y GCP la subred es regional. En
  OCI de México la columna es un dominio de falla.
- Pon el primer renglón de iconos 0.25 debajo de la parte de arriba de su grupo, para no tapar la etiqueta
  (W-LABEL avisa).
- Flechas: `route` `auto`, `h-first`, `v-first` o `points`. Los pasos van de 1 a k sin huecos. `node --test
  tests/` revisa que ninguna flecha cruce un icono u otra flecha.

## Tipos de grupo por nube

| Nube | Tipos |
| --- | --- |
| AWS | `aws-cloud`, `aws-account`, `region`, `vpc`, `az`, `public-subnet`, `private-subnet`, `security-group`, `auto-scaling-group` |
| Azure | `azure-subscription`, `azure-resource-group`, `azure-region`, `azure-vnet`, `azure-subnet`, `azure-zone` |
| Google Cloud | `gcp-cloud`, `gcp-project`, `gcp-region`, `gcp-vpc`, `gcp-subnet`, `gcp-zone` |
| Oracle Cloud | `oci-tenancy`, `oci-compartment`, `oci-region`, `oci-ad`, `oci-fault-domain`, `oci-vcn`, `oci-subnet` |
| Cualquiera | `generic`, `corporate-dc` |

## Revisión antes de entregar

1. El validador dice "ok" sin avisos en las cuatro nubes.
2. Juega cada puzzle sin mirar las respuestas: cada slot tiene una sola ficha correcta leyendo solo el
   requisito.
3. Cada explicación y cada `why_not` se apoya en las URLs de la tabla; si un dato no está ahí, no lo escribas.
4. Deja `status: "draft"` hasta que otra persona lo juegue a ciegas.
