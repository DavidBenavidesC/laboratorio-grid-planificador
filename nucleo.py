"""Núcleo del laboratorio Grid: simulación de eventos discretos de una Grid heterogénea.

Un broker (planificador) reparte tareas entre sitios que difieren en velocidad,
latencia de red y disponibilidad. Se comparan tres estrategias de planificación.
El tiempo es simulado: el resultado no depende de la máquina donde se ejecuta
y es reproducible con la misma semilla.
"""
import heapq
import random
import statistics
from collections import deque
from dataclasses import dataclass


@dataclass
class Sitio:
    nombre: str
    velocidad: float        # unidades de trabajo por segundo simulado
    latencia: float         # latencia media de transferencia por tarea (s)
    jitter: float           # variación relativa de la latencia (0 a 1)
    uptime: float | None    # tiempo medio en línea entre caídas (s); None = siempre disponible
    downtime: float         # duración media de cada caída (s)


ESTRATEGIAS = [
    ("rr", "Round-robin (estático)"),
    ("capacidad", "Por capacidad (estático)"),
    ("robo", "Cola dinámica (work stealing)"),
]


def perfil_grid():
    datos = [
        ("Sitio A", 2.0, 0.2, 0.10, None, 0),
        ("Sitio B", 1.5, 0.5, 0.20, 400, 20),
        ("Sitio C", 1.0, 1.0, 0.30, 250, 30),
        ("Sitio D", 1.0, 2.0, 0.40, 200, 40),
        ("Sitio E", 0.6, 3.0, 0.50, 120, 50),
        ("Sitio F", 0.4, 5.0, 0.60, 80, 60),
    ]
    return [Sitio(*d) for d in datos]


def perfil_cluster(referencia=None):
    """Clúster homogéneo con la misma capacidad total que la Grid de referencia."""
    ref = referencia or perfil_grid()
    v = sum(s.velocidad for s in ref) / len(ref)
    return [Sitio(f"Nodo {i + 1}", v, 0.05, 0.05, None, 0) for i in range(len(ref))]


def generar_tareas(n, semilla):
    rng = random.Random(semilla)
    return [rng.uniform(5, 15) for _ in range(n)]


def _caidas(sitio, indice, semilla, horizonte):
    if not sitio.uptime or sitio.uptime <= 0 or sitio.downtime <= 0:
        return []
    rng = random.Random(semilla * 7919 + indice * 104729 + 17)
    t, res = 0.0, []
    while True:
        t += rng.expovariate(1 / sitio.uptime)
        if t >= horizonte:
            break
        d = rng.expovariate(1 / sitio.downtime)
        res.append((t, t + d))
        t += d
    return res


def _latencia(sitio, semilla, tarea, intento, indice):
    # Números aleatorios comunes: cada estrategia ve la misma latencia para la misma tarea
    rng = random.Random(semilla * 1_000_003 + tarea * 10_007 + intento * 101 + indice)
    return max(0.0, sitio.latencia * (1 + sitio.jitter * (rng.random() * 2 - 1)))


def simular(sitios, costos, estrategia, semilla=1):
    n, m = len(sitios), len(costos)
    vel = [s.velocidad for s in sitios]
    horizonte = 100 * sum(costos) / sum(vel) + 1000
    caidas = [_caidas(s, i, semilla, horizonte) for i, s in enumerate(sitios)]

    # Reparto inicial (el broker conoce las colas; las colas son lógicas)
    colas = [deque() for _ in range(n)]
    if estrategia == "capacidad":
        carga = [0.0] * n
        for t, c in enumerate(costos):
            i = min(range(n), key=lambda k: (carga[k] + c) / vel[k])
            carga[i] += c
            colas[i].append(t)
    else:
        for t in range(m):
            colas[t % n].append(t)

    en_linea = [True] * n
    actual = [None] * n
    inicio = [0.0] * n
    token = [0] * n
    intentos = [0] * m
    segmentos = [[] for _ in range(n)]
    tareas_ok = [0] * n
    ocupado_ok = [0.0] * n
    perdidas = [0] * n
    trabajo_perdido = [0.0] * n
    fin_sitio = [0.0] * n
    reasignaciones = 0
    heap, seq = [], 0

    def push(t, tipo, i, tk=0):
        nonlocal seq
        heapq.heappush(heap, (t, seq, tipo, i, tk))
        seq += 1

    for i, lista in enumerate(caidas):
        for a, b in lista:
            push(a, "caida", i)
            push(b, "recup", i)

    def intentar(i, t):
        nonlocal reasignaciones
        if not en_linea[i] or actual[i] is not None:
            return
        if not colas[i] and estrategia == "robo":
            victima = max(range(n), key=lambda k: (len(colas[k]), not en_linea[k]))
            if victima != i and colas[victima]:
                cuantas = (len(colas[victima]) + 1) // 2
                for _ in range(cuantas):
                    colas[i].append(colas[victima].pop())
                reasignaciones += cuantas
        if not colas[i]:
            return
        tarea = colas[i].popleft()
        lat = _latencia(sitios[i], semilla, tarea, intentos[tarea], i)
        intentos[tarea] += 1
        actual[i], inicio[i] = tarea, t
        token[i] += 1
        push(t + lat + costos[tarea] / vel[i], "fin", i, token[i])

    pendientes, t = m, 0.0
    for i in range(n):
        intentar(i, 0.0)
    while pendientes:
        if not heap:
            raise RuntimeError("La simulación se quedó sin eventos")
        t, _, tipo, i, tk = heapq.heappop(heap)
        if tipo == "fin":
            if tk != token[i] or actual[i] is None:
                continue
            segmentos[i].append((inicio[i], t, actual[i], "ok"))
            ocupado_ok[i] += t - inicio[i]
            tareas_ok[i] += 1
            fin_sitio[i] = t
            actual[i] = None
            pendientes -= 1
            intentar(i, t)
        elif tipo == "caida":
            en_linea[i] = False
            if actual[i] is not None:
                segmentos[i].append((inicio[i], t, actual[i], "perdida"))
                perdidas[i] += 1
                trabajo_perdido[i] += t - inicio[i]
                colas[i].appendleft(actual[i])
                actual[i] = None
                token[i] += 1
                if estrategia == "robo":
                    for k in range(n):
                        intentar(k, t)
        else:
            en_linea[i] = True
            intentar(i, t)

    makespan = t
    assert sum(tareas_ok) == m, "Cada tarea debe completarse exactamente una vez"
    tiempo_caido, caidas_vis = [], []
    for i in range(n):
        tot, vis = 0.0, []
        for a, b in caidas[i]:
            if a >= makespan:
                break
            fin = min(b, makespan)
            tot += fin - a
            vis.append((a, fin))
        tiempo_caido.append(tot)
        caidas_vis.append(vis)
    limite = sum(costos) / sum(vel)
    util = [o / makespan for o in ocupado_ok]
    return {
        "estrategia": estrategia,
        "makespan": makespan,
        "limite_inferior": limite,
        "eficiencia": limite / makespan,
        "tareas_por_sitio": tareas_ok,
        "utilizacion": util,
        "utilizacion_media": sum(util) / n,
        "tiempo_caido": tiempo_caido,
        "perdidas": sum(perdidas),
        "trabajo_perdido": sum(trabajo_perdido),
        "reasignaciones": reasignaciones,
        "fin_por_sitio": fin_sitio,
        "segmentos": segmentos,
        "caidas": caidas_vis,
    }


def comparar(sitios, n_tareas=200, repeticiones=5, semilla=1):
    resumen = {}
    for clave, nombre in ESTRATEGIAS:
        corridas = []
        for r in range(repeticiones):
            s = semilla + r
            corridas.append(simular(sitios, generar_tareas(n_tareas, s), clave, s))
        ms = [c["makespan"] for c in corridas]
        resumen[clave] = {
            "nombre": nombre,
            "makespan_medio": statistics.mean(ms),
            "makespan_sd": statistics.stdev(ms) if len(ms) > 1 else 0.0,
            "makespans": ms,
            "eficiencia_media": statistics.mean(c["eficiencia"] for c in corridas),
            "utilizacion_media": statistics.mean(c["utilizacion_media"] for c in corridas),
            "perdidas_medias": statistics.mean(c["perdidas"] for c in corridas),
            "reasignaciones_medias": statistics.mean(c["reasignaciones"] for c in corridas),
            "detalle": corridas[0],
        }
    return resumen