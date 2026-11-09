import random
from dataclasses import asdict
from pathlib import Path

from flask import Flask, jsonify, request, send_from_directory

import nucleo

app = Flask(__name__)
RAIZ = Path(__file__).parent

LIM = {
    "tareas": (20, 2000),
    "repeticiones": (1, 30),
    "semilla": (0, 999_999),
    "sitios": (2, 12),
}


def redondear(obj, nd=3):
    if isinstance(obj, float):
        return round(obj, nd)
    if isinstance(obj, (list, tuple)):
        return [redondear(x, nd) for x in obj]
    if isinstance(obj, dict):
        return {k: redondear(v, nd) for k, v in obj.items()}
    return obj


def entero(datos, clave, defecto):
    bruto = datos.get(clave)
    if bruto in (None, ""):
        return defecto
    try:
        return int(bruto)
    except (TypeError, ValueError):
        raise ValueError(f"«{clave}» debe ser un número entero")


def leer_sitios(lista):
    lo, hi = LIM["sitios"]
    if not isinstance(lista, list) or not (lo <= len(lista) <= hi):
        raise ValueError(f"Debe haber entre {lo} y {hi} sitios")
    sitios = []
    for i, d in enumerate(lista, 1):
        try:
            up = d.get("uptime")
            s = nucleo.Sitio(
                nombre=str(d.get("nombre") or f"Sitio {i}")[:20],
                velocidad=float(d["velocidad"]),
                latencia=float(d["latencia"]),
                jitter=float(d["jitter"]),
                uptime=None if up in (None, "", 0) else float(up),
                downtime=float(d.get("downtime") or 0),
            )
        except (KeyError, TypeError, ValueError, AttributeError):
            raise ValueError(f"Sitio {i}: faltan datos o no son números")
        if not 0.1 <= s.velocidad <= 10:
            raise ValueError(f"Sitio {i}: la velocidad debe estar entre 0,1 y 10")
        if not 0 <= s.latencia <= 30:
            raise ValueError(f"Sitio {i}: la latencia debe estar entre 0 y 30 s")
        if not 0 <= s.jitter <= 1:
            raise ValueError(f"Sitio {i}: el jitter debe estar entre 0 y 1")
        if s.uptime is not None:
            if not 10 <= s.uptime <= 10_000:
                raise ValueError(f"Sitio {i}: el tiempo en línea debe estar entre 10 y 10000 s")
            if not 1 <= s.downtime <= 1000:
                raise ValueError(f"Sitio {i}: la duración de la caída debe estar entre 1 y 1000 s")
        sitios.append(s)
    return sitios


def perfil_por_nombre(nombre):
    if nombre == "cluster":
        return nucleo.perfil_cluster()
    if nombre == "grid":
        return nucleo.perfil_grid()
    raise ValueError("perfil debe ser «grid», «cluster» o «personalizado»")


@app.get("/")
def inicio():
    destino = RAIZ / "static" / "index.html"
    if destino.exists():
        return send_from_directory(RAIZ / "static", "index.html")
    return "Servidor activo. Falta static/index.html (etapa 4)."


@app.get("/api/perfiles")
def perfiles():
    return jsonify({
        "grid": [asdict(s) for s in nucleo.perfil_grid()],
        "cluster": [asdict(s) for s in nucleo.perfil_cluster()],
        "estrategias": [{"clave": c, "nombre": n} for c, n in nucleo.ESTRATEGIAS],
        "limites": LIM,
    })


@app.route("/api/simular", methods=["GET", "POST"])
def simular():
    datos = (request.get_json(silent=True) or {}) if request.method == "POST" else request.args
    try:
        perfil = str(datos.get("perfil") or "grid")
        if perfil == "personalizado":
            sitios = leer_sitios(datos.get("sitios"))
        else:
            sitios = perfil_por_nombre(perfil)
        tareas = entero(datos, "tareas", 200)
        reps = entero(datos, "repeticiones", 10)
        semilla = entero(datos, "semilla", None)
        for nombre, valor in (("tareas", tareas), ("repeticiones", reps)):
            lo, hi = LIM[nombre]
            if not lo <= valor <= hi:
                raise ValueError(f"«{nombre}» debe estar entre {lo} y {hi}")
        if semilla is None:
            semilla = random.randrange(1, LIM["semilla"][1])
        if not LIM["semilla"][0] <= semilla <= LIM["semilla"][1]:
            raise ValueError("«semilla» debe estar entre 0 y 999999")
    except ValueError as e:
        return jsonify(error=str(e)), 400

    con_detalle = str(datos.get("detalle", "1")).lower() not in ("0", "false")
    resumen = nucleo.comparar(sitios, n_tareas=tareas, repeticiones=reps, semilla=semilla)
    estrategias = []
    for clave, r in resumen.items():
        item = {"clave": clave, **{k: v for k, v in r.items() if k != "detalle"}}
        if con_detalle:
            item["detalle"] = r["detalle"]
        estrategias.append(item)
    return jsonify(redondear({
        "config": {"perfil": perfil, "tareas": tareas, "repeticiones": reps, "semilla": semilla},
        "sitios": [asdict(s) for s in sitios],
        "estrategias": estrategias,
    }))


if __name__ == "__main__":
    app.run(host="127.0.0.1", port=5001, debug=False)