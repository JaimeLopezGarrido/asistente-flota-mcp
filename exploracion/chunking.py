"""Laboratorio de ingesta (L09): extraer un PDF con pypdf, cortarlo de 4 formas y ver qué se pierde.

No toca el producto (rag/ingesta.py sigue igual). Lee el folleto A6 del manual, saca el ruido de
maquetación (encabezados y pies de página), arma un solo texto que recuerda en qué página y en qué
sección está cada carácter, y compara cuatro estrategias de chunking con sus metadatos.

Uso:
    python -m exploracion.chunking                     # compara las 4 estrategias
    python -m exploracion.chunking --ver secciones     # cada fragmento con sus metadatos
    python -m exploracion.chunking --pdf datos/manual/manual_rentadora.pdf   # el PDF de E2
"""

import argparse
import re
import textwrap
from bisect import bisect_right
from collections import Counter
from collections.abc import Callable
from dataclasses import dataclass
from itertools import pairwise
from pathlib import Path

from pypdf import PdfReader

from scripts.generar_folleto import ANEXO, FUENTE, SALIDA, a_latin1

TAMANIO = 420  # caracteres por fragmento, igual que rag/ingesta.py
SOLAPAMIENTO = 80  # caracteres que se repiten entre un fragmento y el siguiente
MAXIMO_SECCION = 700  # una sección más larga que esto se subdivide por oraciones
# Fin de oración: . ! o ? seguido de espacio o del final. "5. Cruce" no corta (el punto sigue a un número)
FIN_DE_ORACION = re.compile(r"(?<!\d)[.!?](?=\s|$)")

# Datos que tienen que quedar enteros en al menos un fragmento para poder responder bien
HECHOS = [
    ("permiso notarial", "72 horas"),
    ("Pinchadura", "auxilio"),
    ("¿Puedo llevar mascotas?", "jaula"),
    ("Lavado especial", "25.000"),
]

Span = tuple[int, int]  # un corte [inicio, fin) dentro del texto completo


def leer_paginas(ruta: Path) -> list[tuple[int, list[str]]]:
    """Texto crudo de cada página, renglón por renglón, como lo devuelve pypdf (desde la página 1)."""
    lector = PdfReader(ruta)
    return [
        (numero, (pagina.extract_text() or "").splitlines())
        for numero, pagina in enumerate(lector.pages, start=1)
    ]


def metadatos_pdf(ruta: Path) -> dict:
    """Lo que el propio PDF dice de sí mismo: cantidad de páginas, título y autor."""
    lector = PdfReader(ruta)
    info = lector.metadata
    return {
        "fuente": ruta.name,
        "paginas": len(lector.pages),
        "titulo": info.title if info else None,
        "autor": info.author if info else None,
    }


def _forma(linea: str) -> str:
    """La línea sin espacios de más y con los números tapados: 'Página 3 de 11' -> 'Página # de #'."""
    return re.sub(r"\d+", "#", " ".join(linea.split()))


def lineas_de_ruido(paginas: list[tuple[int, list[str]]], minimo: float = 0.5) -> set[str]:
    """Formas de línea que se repiten en al menos la mitad de las páginas: encabezados y pies."""
    cuenta: Counter[str] = Counter()
    for _, lineas in paginas:
        cuenta.update({_forma(linea) for linea in lineas if linea.strip()})
    umbral = max(2, minimo * len(paginas))
    return {forma for forma, veces in cuenta.items() if veces >= umbral}


def limpiar_paginas(paginas: list[tuple[int, list[str]]]) -> list[tuple[int, str]]:
    """Saca el ruido y une los renglones de cada página en un solo texto: [(página, texto), ...]."""
    ruido = lineas_de_ruido(paginas)
    limpias = []
    for numero, lineas in paginas:
        utiles = [linea for linea in lineas if linea.strip() and _forma(linea) not in ruido]
        limpias.append((numero, " ".join(" ".join(utiles).split())))
    return limpias


def titulos_del_manual(fuente: Path = FUENTE) -> list[str]:
    """Los títulos '## ...' del manual (tal como quedan en el PDF) y el del anexo."""
    lineas = [linea.strip() for linea in fuente.read_text(encoding="utf-8").splitlines()]
    titulos = [a_latin1(linea[3:].strip()) for linea in lineas if linea.startswith("## ")]
    return [*titulos, ANEXO]


@dataclass
class Documento:
    """Todo el texto útil del PDF en un solo string, con mapas de posición a página y a sección."""

    texto: str
    fuente: str
    inicios_pagina: list[int]
    numeros_pagina: list[int]
    inicios_seccion: list[int]
    secciones: list[str]

    def pagina_en(self, posicion: int) -> int:
        i = bisect_right(self.inicios_pagina, posicion) - 1
        return self.numeros_pagina[max(i, 0)]

    def paginas_entre(self, inicio: int, fin: int) -> list[int]:
        primera = max(bisect_right(self.inicios_pagina, inicio) - 1, 0)
        ultima = max(bisect_right(self.inicios_pagina, fin - 1) - 1, 0)
        return self.numeros_pagina[primera : ultima + 1]

    def seccion_en(self, posicion: int) -> str:
        i = bisect_right(self.inicios_seccion, posicion) - 1
        return self.secciones[i] if i >= 0 else ""

    def secciones_entre(self, inicio: int, fin: int) -> list[str]:
        """La sección donde arranca el corte más las que empiezan adentro de él."""
        pares = zip(self.secciones, self.inicios_seccion, strict=True)
        nuevas = [seccion for seccion, comienzo in pares if inicio < comienzo < fin]
        return [self.seccion_en(inicio), *nuevas]

    def rangos_de_pagina(self) -> list[Span]:
        fines = [*(comienzo - 1 for comienzo in self.inicios_pagina[1:]), len(self.texto)]
        return list(zip(self.inicios_pagina, fines, strict=True))

    def rangos_de_seccion(self) -> list[Span]:
        cortes = [0, *self.inicios_seccion, len(self.texto)]
        return [(a, b) for a, b in pairwise(cortes) if b > a]


def construir_documento(paginas: list[tuple[int, str]], titulos: list[str], fuente: str) -> Documento:
    """Une las páginas con un espacio, anota dónde empieza cada una y busca los títulos en orden."""
    partes: list[str] = []
    inicios: list[int] = []
    numeros: list[int] = []
    posicion = 0
    for numero, texto in paginas:
        if not texto:
            continue
        if partes:
            posicion += 1  # el espacio que separa una página de la anterior
        inicios.append(posicion)
        numeros.append(numero)
        partes.append(texto)
        posicion += len(texto)
    if not partes:
        raise ValueError("el PDF no tiene texto extraíble: si es un escaneo, primero hace falta OCR")
    completo = " ".join(partes)
    inicios_seccion: list[int] = []
    secciones: list[str] = []
    desde = 0
    for titulo in titulos:
        encontrado = completo.find(titulo, desde)
        if encontrado >= 0:
            inicios_seccion.append(encontrado)
            secciones.append(titulo)
            desde = encontrado + len(titulo)
    return Documento(completo, fuente, inicios, numeros, inicios_seccion, secciones)


def por_caracteres(texto: str, tamanio: int, solapamiento: int = 0) -> list[Span]:
    """Un corte cada `tamanio` caracteres, sin mirar el contenido. El solapamiento repite el final."""
    if not 0 <= solapamiento < tamanio:
        raise ValueError("el solapamiento tiene que ser menor que el tamaño")
    paso = tamanio - solapamiento
    cortes: list[Span] = []
    inicio = 0
    while inicio < len(texto):
        fin = min(inicio + tamanio, len(texto))
        cortes.append((inicio, fin))
        if fin == len(texto):
            break
        inicio += paso
    return cortes


def oraciones(texto: str, inicio: int = 0, fin: int | None = None) -> list[Span]:
    """Las oraciones de texto[inicio:fin], como posiciones dentro del texto completo."""
    fin = len(texto) if fin is None else fin
    partes: list[Span] = []
    desde = inicio
    for marca in FIN_DE_ORACION.finditer(texto, inicio, fin):
        partes.append((desde, marca.end()))
        desde = marca.end()
    if desde < fin:
        partes.append((desde, fin))
    return [(a, b) for a, b in partes if texto[a:b].strip()]


def agrupar(partes: list[Span], tamanio: int, solapamiento: int = 0) -> list[Span]:
    """Junta oraciones seguidas mientras entren en `tamanio`. Con solapamiento=1 repite la última."""
    grupos: list[Span] = []
    i = 0
    while i < len(partes):
        j = i
        while j + 1 < len(partes) and partes[j + 1][1] - partes[i][0] <= tamanio:
            j += 1
        grupos.append((partes[i][0], partes[j][1]))
        if j + 1 >= len(partes):
            break
        i = max(j + 1 - solapamiento, i + 1)
    return grupos


def estrategia_fijo(doc: Documento) -> list[Span]:
    return por_caracteres(doc.texto, TAMANIO)


def estrategia_fijo_solapado(doc: Documento) -> list[Span]:
    return por_caracteres(doc.texto, TAMANIO, SOLAPAMIENTO)


def estrategia_oraciones_por_pagina(doc: Documento) -> list[Span]:
    """Como rag/ingesta.py: oraciones completas, una de solapamiento y nunca dos páginas juntas."""
    cortes: list[Span] = []
    for inicio, fin in doc.rangos_de_pagina():
        cortes.extend(agrupar(oraciones(doc.texto, inicio, fin), TAMANIO, solapamiento=1))
    return cortes


def estrategia_secciones(doc: Documento) -> list[Span]:
    """Una sección por fragmento; si es muy larga, se subdivide por oraciones sin salir de ella."""
    cortes: list[Span] = []
    for inicio, fin in doc.rangos_de_seccion():
        if fin - inicio <= MAXIMO_SECCION:
            cortes.append((inicio, fin))
        else:
            cortes.extend(agrupar(oraciones(doc.texto, inicio, fin), TAMANIO))
    return cortes


ESTRATEGIAS: dict[str, Callable[[Documento], list[Span]]] = {
    "fijo": estrategia_fijo,
    "fijo_solapado": estrategia_fijo_solapado,
    "oraciones_por_pagina": estrategia_oraciones_por_pagina,
    "secciones": estrategia_secciones,
}


def fragmentar(doc: Documento, cortes: list[Span], estrategia: str) -> list[dict]:
    """Convierte los cortes en fragmentos con metadatos: fuente, páginas, sección y posición."""
    fragmentos: list[dict] = []
    for inicio, fin in cortes:
        texto = doc.texto[inicio:fin].strip()
        if not texto:
            continue
        fragmentos.append(
            {
                "id": f"{estrategia}-{len(fragmentos) + 1:02d}",
                "fuente": doc.fuente,
                "paginas": doc.paginas_entre(inicio, fin),
                "seccion": doc.seccion_en(inicio),
                "secciones": doc.secciones_entre(inicio, fin),
                "inicio": inicio,
                "caracteres": len(texto),
                "corta_oracion": not texto.endswith((".", "!", "?")),
                "texto": texto,
            }
        )
    return fragmentos


def hecho_entero(fragmentos: list[dict], hecho: tuple[str, ...]) -> bool:
    """True si algún fragmento contiene todas las partes del dato (sin distinguir mayúsculas)."""
    return any(all(parte.casefold() in f["texto"].casefold() for parte in hecho) for f in fragmentos)


def preparar(ruta: Path) -> Documento:
    """Extraer, limpiar y armar el documento: los pasos 1 a 3 de la ingesta."""
    return construir_documento(limpiar_paginas(leer_paginas(ruta)), titulos_del_manual(), ruta.name)


def mostrar_comparacion(ruta: Path, doc: Documento) -> None:
    meta = metadatos_pdf(ruta)
    print(f"PDF: {meta['fuente']} | {meta['paginas']} páginas | título: {meta['titulo']}")
    print(f"Texto útil: {len(doc.texto)} caracteres | secciones encontradas: {len(doc.secciones)}")
    print()
    resultados = {nombre: fragmentar(doc, cortar(doc), nombre) for nombre, cortar in ESTRATEGIAS.items()}
    columnas = ("frag.", "prom.", "cruzan pág.", "mezclan secc.", "cortan oración")
    anchos = (6, 7, 13, 15, 16)
    print(f"{'estrategia':<22}" + "".join(f"{c:>{a}}" for c, a in zip(columnas, anchos, strict=True)))
    for nombre, fragmentos in resultados.items():
        promedio = sum(f["caracteres"] for f in fragmentos) / max(len(fragmentos), 1)
        cruzan = sum(len(f["paginas"]) > 1 for f in fragmentos)
        mezclan = sum(len(f["secciones"]) > 1 for f in fragmentos)
        cortan = sum(f["corta_oracion"] for f in fragmentos)
        print(f"{nombre:<22}{len(fragmentos):>6}{promedio:>7.0f}{cruzan:>13}{mezclan:>15}{cortan:>16}")
    print()
    print("¿Cada dato quedó entero en algún fragmento?")
    for hecho in HECHOS:
        estados = "  ".join(
            f"{nombre}={'OK' if hecho_entero(fragmentos, hecho) else 'PARTIDO'}"
            for nombre, fragmentos in resultados.items()
        )
        print(f"  {' + '.join(hecho)}")
        print(f"      {estados}")


def mostrar_fragmentos(doc: Documento, estrategia: str) -> None:
    for f in fragmentar(doc, ESTRATEGIAS[estrategia](doc), estrategia):
        paginas = ", ".join(str(p) for p in f["paginas"])
        seccion = f["seccion"] or "(sin sección)"
        aviso = "  (!) termina a mitad de oración" if f["corta_oracion"] else ""
        print()
        print(f"[{f['id']}] pág. {paginas} | {seccion} | {f['caracteres']} car.{aviso}")
        print(textwrap.indent(textwrap.fill(f["texto"], 96), "    "))


def main() -> None:
    parser = argparse.ArgumentParser(description="Extraer un PDF, cortarlo de 4 formas y ver qué se pierde")
    parser.add_argument("--pdf", type=Path, default=SALIDA, help="PDF a leer (por defecto, el folleto)")
    parser.add_argument("--ver", choices=list(ESTRATEGIAS), help="mostrar los fragmentos de una estrategia")
    args = parser.parse_args()
    if not args.pdf.exists():
        print(f"No encontré {args.pdf}. Generalo con: python -m scripts.generar_folleto")
        return
    try:
        doc = preparar(args.pdf)
    except ValueError as error:
        print(error)
        return
    if args.ver:
        mostrar_fragmentos(doc, args.ver)
    else:
        mostrar_comparacion(args.pdf, doc)


if __name__ == "__main__":
    main()
