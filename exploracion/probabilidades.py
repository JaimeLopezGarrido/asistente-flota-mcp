"""Cómo la temperatura cambia la distribución del siguiente token (ejemplo numérico con numpy).

Uso: python -m exploracion.probabilidades
"""

import numpy as np

CONTEXTO = "Quiero alquilar un auto para ir a"
# Candidatos simplificados: en un modelo real, varios de estos serían más de un token.
CANDIDATOS = [" Chile", " Villa La Angostura", " El Bolsón", " Cerro Catedral", " la playa", " Marte"]
LOGITS = np.array([3.2, 2.9, 2.1, 1.8, 0.5, -2.0])
TEMPERATURAS = (0, 0.2, 0.7, 1.0, 1.5)


def softmax(logits, temperatura: float = 1.0) -> np.ndarray:
    """Convierte logits en probabilidades. Temperatura 0 = elegir siempre el mayor (greedy)."""
    z = np.asarray(logits, dtype=float)
    if temperatura < 0:
        raise ValueError("La temperatura no puede ser negativa")
    if temperatura == 0:
        probs = np.zeros_like(z)
        probs[np.argmax(z)] = 1.0
        return probs
    z = z / temperatura
    z = z - z.max()  # estabilidad numérica: no cambia el resultado y evita que exp desborde
    e = np.exp(z)
    return e / e.sum()


def entropia(probs) -> float:
    """Incertidumbre en bits: 0 si un candidato tiene el 100%, más alta cuanto más repartido."""
    p = np.asarray(probs, dtype=float)
    p = p[p > 0]
    return max(0.0, float(-(p * np.log2(p)).sum()))


def top_p(probs, umbral: float = 0.9) -> np.ndarray:
    """Índices de los candidatos más probables hasta acumular `umbral` (nucleus sampling)."""
    p = np.asarray(probs, dtype=float)
    orden = np.argsort(p)[::-1]
    acumulada = np.cumsum(p[orden])
    corte = min(int(np.searchsorted(acumulada, umbral)) + 1, len(p))
    return orden[:corte]


def muestrear(probs, n: int, semilla: int = 0) -> np.ndarray:
    """Elige n candidatos al azar según sus probabilidades (con semilla para poder repetirlo)."""
    rng = np.random.default_rng(semilla)
    return rng.choice(len(probs), size=n, p=probs)


def barra(p: float, ancho: int = 30) -> str:
    return "█" * round(p * ancho)


def mostrar(temperatura: float) -> None:
    probs = softmax(LOGITS, temperatura)
    print(f"\nTemperatura {temperatura}  (entropía {entropia(probs):.2f} bits)")
    for nombre, p in zip(CANDIDATOS, probs):
        print(f"  {nombre!r:<22} {p:6.1%} {barra(p)}")
    nucleo = [CANDIDATOS[i].strip() for i in top_p(probs, 0.9)]
    print(f"  top-p 0.9 se queda con: {', '.join(nucleo)}")
    elegidos = muestrear(probs, 20, semilla=42)
    print("  20 muestras:", " ".join(CANDIDATOS[i].split()[0] for i in elegidos))


def main() -> None:
    print(f"Texto: {CONTEXTO!r} -> ¿qué token sigue?")
    for t in TEMPERATURAS:
        mostrar(t)


if __name__ == "__main__":
    main()
