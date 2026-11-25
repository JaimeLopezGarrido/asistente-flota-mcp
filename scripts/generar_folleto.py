"""Genera el folleto de bolsillo (A6) del manual de la rentadora, armado como muchos PDFs reales (L09).

Mismo contenido ficticio que datos/manual/manual_rentadora.md, pero con texto corrido (las secciones
siguen de una página a la otra), encabezado y pie de página, y un anexo con una tabla de cargos.
Sirve para ver qué se pierde al extraer y cortar un PDF que no fue pensado para RAG.

Uso:
    python -m scripts.generar_folleto
"""

from pathlib import Path

from fpdf import FPDF

RAIZ = Path(__file__).resolve().parent.parent
FUENTE = RAIZ / "datos" / "manual" / "manual_rentadora.md"
SALIDA = RAIZ / "datos" / "manual" / "folleto_rentadora.pdf"

ENCABEZADO = "Rentadora Bariloche (ficticia) - Manual del cliente"
AVISO = (
    "Documento ficticio para practicar RAG: no es el manual de ninguna empresa real. "
    "Versión folleto de bolsillo (A6), con el texto corrido como en muchos PDFs reales."
)
ANEXO = "Anexo: cargos adicionales"
CARGOS = [
    ("Cargo", "Monto (ficticio)", "Cuándo se cobra"),
    ("Lavado especial", "$ 25.000", "Barro, arena o pelos de mascota"),
    ("Combustible faltante", "$ 4.000 por litro", "Si el tanque no vuelve lleno"),
    ("Devolución tardía", "1 día extra", "Más de 2 horas de demora"),
    ("Conductor adicional", "$ 9.000 por día", "Por cada conductor extra"),
    ("Silla para bebé", "$ 6.000 por día", "A pedido, en la reserva"),
]

# Las fuentes básicas de los PDF solo tienen caracteres latinos (latin-1): reemplazamos los que no entran
REEMPLAZOS = {
    "\u2014": "-",  # raya
    "\u2013": "-",  # guion medio
    "\u201c": '"',  # comillas tipográficas
    "\u201d": '"',
    "\u2018": "'",
    "\u2019": "'",
    "\u2026": "...",  # puntos suspensivos en un solo carácter
    "\u2192": "->",
    "\u2022": "-",  # viñeta
}


def a_latin1(texto: str) -> str:
    """Deja el texto listo para las fuentes básicas del PDF; lo que igual no entra se vuelve '?'."""
    for viejo, nuevo in REEMPLAZOS.items():
        texto = texto.replace(viejo, nuevo)
    return texto.encode("latin-1", "replace").decode("latin-1")


def leer_manual(ruta: Path = FUENTE) -> tuple[str, list[tuple[str, list[str]]]]:
    """Título del manual y sus secciones: [(título de sección, [párrafos]), ...]."""
    titulo = ""
    secciones: list[tuple[str, list[str]]] = []
    for linea in ruta.read_text(encoding="utf-8").splitlines():
        limpia = linea.strip()
        if limpia.startswith("## "):
            secciones.append((limpia[3:].strip(), []))
        elif limpia.startswith("# "):
            titulo = limpia[2:].strip()
        elif limpia and secciones:
            secciones[-1][1].append(limpia.lstrip("-*> ").replace("**", ""))
    return titulo, secciones


class Folleto(FPDF):
    """Página A6 con encabezado y pie de página en todas las hojas, menos en la portada."""

    def header(self) -> None:
        if self.page_no() == 1:
            return
        self.set_font("Helvetica", size=7)
        self.cell(0, 5, a_latin1(ENCABEZADO), new_x="LMARGIN", new_y="NEXT")
        self.ln(2)

    def footer(self) -> None:
        if self.page_no() == 1:
            return
        self.set_y(-12)
        self.set_font("Helvetica", size=7)
        # {nb} lo reemplaza fpdf2 por el total de páginas al guardar
        self.cell(0, 5, a_latin1(f"Página {self.page_no()} de {{nb}}"), align="C")


def generar(salida: Path = SALIDA, fuente: Path = FUENTE) -> int:
    """Escribe el folleto en `salida` y devuelve cuántas páginas tiene."""
    titulo, secciones = leer_manual(fuente)
    pdf = Folleto(format=(105, 148))  # A6 en milímetros: fpdf2 2.9 no reconoce el nombre "A6"
    pdf.set_margins(12, 12, 12)
    pdf.set_auto_page_break(auto=True, margin=16)
    pdf.set_title(titulo)
    pdf.set_author("Rentadora ficticia (datos de práctica)")

    pdf.add_page()  # portada
    pdf.set_font("Helvetica", style="B", size=14)
    pdf.multi_cell(0, 7, a_latin1(titulo), new_x="LMARGIN", new_y="NEXT")
    pdf.ln(4)
    pdf.set_font("Helvetica", size=9)
    pdf.multi_cell(0, 5, a_latin1(AVISO), new_x="LMARGIN", new_y="NEXT")

    pdf.add_page()  # desde acá, texto corrido: una sección puede seguir en la página siguiente
    for titulo_seccion, parrafos in secciones:
        pdf.ln(3)
        pdf.set_font("Helvetica", style="B", size=10)
        pdf.multi_cell(0, 6, a_latin1(titulo_seccion), new_x="LMARGIN", new_y="NEXT")
        pdf.set_font("Helvetica", size=10)
        for parrafo in parrafos:
            pdf.multi_cell(0, 5, a_latin1(parrafo), new_x="LMARGIN", new_y="NEXT")
            pdf.ln(1.5)

    pdf.ln(3)
    pdf.set_font("Helvetica", style="B", size=10)
    pdf.multi_cell(0, 6, a_latin1(ANEXO), new_x="LMARGIN", new_y="NEXT")
    pdf.set_font("Helvetica", size=7)
    with pdf.table(col_widths=(28, 22, 31), text_align="LEFT", line_height=4) as tabla:
        for fila in CARGOS:
            celdas = tabla.row()
            for celda in fila:
                celdas.cell(a_latin1(celda))

    salida.parent.mkdir(parents=True, exist_ok=True)
    pdf.output(str(salida))
    return pdf.page_no()


def main() -> None:
    paginas = generar()
    print(f"Folleto generado: {SALIDA.relative_to(RAIZ)} ({paginas} páginas)")


if __name__ == "__main__":
    main()
