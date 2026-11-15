"""Normalización y tokenización simples para la búsqueda por palabras (sin dependencias)."""

import re
import unicodedata

VACIAS = {'a', 'al', 'algo', 'como', 'con', 'de', 'del', 'el', 'en', 'es', 'esta', 'este', 'hay', 'la', 'las', 'le', 'lo', 'los', 'me', 'mi', 'mis', 'no', 'o', 'para', 'pero', 'por', 'que', 'qué', 'se', 'si', 'sin', 'su', 'sus', 'te', 'tu', 'un', 'una', 'uno', 'unos', 'y', 'ya', 'yo', 'puedo', 'puede', 'tengo', 'tienen', 'tiene', 'hago', 'hacer', 'cual', 'cuál', 'cuanto', 'cuánto', 'sale', 'cuesta'}


def normalizar(texto: str) -> str:
    """Minúsculas y sin tildes, para comparar palabras sin falsos negativos."""
    descompuesto = unicodedata.normalize('NFKD', texto)
    return ''.join(c for c in descompuesto if not unicodedata.combining(c)).lower()


def palabras(texto: str) -> list[str]:
    """Palabras útiles (sin vacías) con un recorte básico de plurales."""
    salida = []
    for p in re.findall(r'[a-z0-9]+', normalizar(texto)):
        if p in VACIAS or len(p) < 3:
            continue
        salida.append(p[:-1] if len(p) > 4 and p.endswith('s') else p)
    return salida
