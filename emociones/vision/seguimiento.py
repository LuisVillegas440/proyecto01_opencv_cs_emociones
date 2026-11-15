"""Seguimiento simple de rostros entre frames y suavizado temporal.

El clasificador evalúa cada frame por separado, por lo que la etiqueta
"parpadea" entre emociones parecidas. Aquí se asocia cada rostro con el del
frame anterior (por solapamiento IoU) y se promedian sus probabilidades con
una media móvil exponencial (EMA). Así cada rostro mantiene un id estable.
"""
from dataclasses import dataclass, field

import numpy as np


def iou(a, b) -> float:
    """Intersección sobre unión de dos cajas [x, y, ancho, alto]."""
    ax1, ay1, ax2, ay2 = a[0], a[1], a[0] + a[2], a[1] + a[3]
    bx1, by1, bx2, by2 = b[0], b[1], b[0] + b[2], b[1] + b[3]
    iw = max(0, min(ax2, bx2) - max(ax1, bx1))
    ih = max(0, min(ay2, by2) - max(ay1, by1))
    inter = iw * ih
    union = a[2] * a[3] + b[2] * b[3] - inter
    return inter / union if union > 0 else 0.0


@dataclass
class Pista:
    """Un rostro seguido a lo largo del tiempo."""
    id: int
    caja: list
    probs: np.ndarray
    frames_perdido: int = 0
    frames_visto: int = 1


@dataclass
class SeguidorRostros:
    alfa: float = 0.4            # peso del frame nuevo en la EMA
    iou_minimo: float = 0.3      # solapamiento mínimo para considerar "el mismo rostro"
    max_frames_perdido: int = 5  # se descarta la pista tras N frames sin verlo
    pistas: list = field(default_factory=list)
    _siguiente_id: int = 1

    def actualizar(self, cajas: list, probs: np.ndarray) -> list[Pista]:
        """Asocia las detecciones del frame actual y devuelve sus pistas (mismo orden)."""
        # Pares (iou, índice pista, índice detección) ordenados de mayor a menor.
        candidatos = sorted(
            ((iou(p.caja, c), i, j) for i, p in enumerate(self.pistas) for j, c in enumerate(cajas)),
            reverse=True,
        )
        pista_de = {}
        usadas = set()
        for valor, i, j in candidatos:
            if valor < self.iou_minimo:
                break
            if i in usadas or j in pista_de:
                continue
            usadas.add(i)
            pista_de[j] = self.pistas[i]

        resultado = []
        for j, caja in enumerate(cajas):
            pista = pista_de.get(j)
            if pista is None:
                pista = Pista(self._siguiente_id, list(caja), probs[j].copy())
                self._siguiente_id += 1
                self.pistas.append(pista)
            else:
                pista.caja = list(caja)
                pista.probs = self.alfa * probs[j] + (1 - self.alfa) * pista.probs
                pista.frames_perdido = 0
                pista.frames_visto += 1
            resultado.append(pista)

        vistas = {id(p) for p in resultado}
        for p in self.pistas:
            if id(p) not in vistas:
                p.frames_perdido += 1
        self.pistas = [p for p in self.pistas if p.frames_perdido <= self.max_frames_perdido]
        return resultado
