# Laboratorio Grid: planificación en una Grid heterogénea

Sistemas Distribuidos · Universidad Tecnológica de Pereira

Segunda parte del laboratorio de clústeres y Grid. Un broker (planificador) reparte tareas entre sitios que difieren en velocidad, latencia de red y disponibilidad, y se comparan tres estrategias de planificación. El objetivo es mostrar por qué balancear la carga en una Grid es mucho más difícil que en un clúster.

El laboratorio se maneja desde una interfaz web local: se eligen los parámetros, se ve cómo trabaja cada estrategia sitio por sitio y al final se obtienen tablas y gráficas.

## Qué simula

Es una **simulación de eventos discretos** (el mismo enfoque de simuladores de Grid como GridSim o SimGrid). El tiempo es simulado, no medido, así que el resultado no depende del computador donde se ejecuta y es reproducible con la misma semilla. **No es una Grid real.**

### Modelo

- **Tareas:** cada una cuesta entre 5 y 15 unidades de trabajo.
- **Sitios:** cada sitio tiene una velocidad (unidades de trabajo por segundo), una latencia media de transferencia con variación aleatoria y periodos de caída (tiempo en línea y duración de la caída, ambos aleatorios).
- **Ejecución:** una tarea ocupa el sitio durante la transferencia (latencia) más el cómputo (costo / velocidad).
- **Fallas:** si un sitio se cae a mitad de una tarea, se pierde el avance y la tarea se repite desde cero.

### Estrategias de planificación

| Estrategia | Cómo reparte |
|---|---|
| Round-robin (estático) | Reparte las tareas de forma cíclica al inicio, sin mirar las características de los sitios. |
| Por capacidad (estático) | Asigna cada tarea al sitio con menor tiempo estimado de fin según su velocidad nominal. Ignora la latencia y las caídas. |
| Cola dinámica (work stealing) | Reparto inicial cíclico. Cuando un sitio se queda sin tareas, toma la mitad de la cola del sitio con más pendientes. Las colas viven en el broker, por lo que robar es reasignar; así también se rescata el trabajo de sitios caídos. |

Las estrategias estáticas no migran tareas: lo que quedó asignado a un sitio caído espera a que se recupere.

### Métricas

- **Tiempo total:** instante en que termina la última tarea.
- **Mínimo ideal:** trabajo total / capacidad total, sin latencia ni caídas.
- **Eficiencia:** mínimo ideal / tiempo total.
- **Utilización:** fracción del tiempo que un sitio estuvo ocupado en tareas que sí se completaron.
- **Tareas repetidas:** tareas que hubo que reiniciar por una caída.
- **Tareas reasignadas:** tareas movidas entre sitios por work stealing.

## Reproducibilidad

Todo lo aleatorio (costo de las tareas, latencias y caídas) sale de una **semilla**. La misma semilla produce siempre los mismos resultados. Con varias repeticiones se usan la semilla indicada, la siguiente, y así sucesivamente, y las tres estrategias enfrentan exactamente las mismas tareas, latencias y caídas en cada repetición, por lo que la comparación es justa.

## Instalación y ejecución

Requiere Python 3.10 o superior y un navegador.

```
python -m venv .venv
.venv\Scripts\activate
pip install -r requirements.txt
python app.py
```

En Linux o macOS, la activación es `source .venv/bin/activate`. Después abre <http://127.0.0.1:5001> en el navegador.

## Cómo usar la interfaz

1. **Parámetros:** perfil de sitios (Grid heterogénea, clúster homogéneo o personalizado), cantidad de tareas, repeticiones y semilla (fija o aleatoria). La tabla de sitios se puede editar; si el tiempo en línea de un sitio queda vacío, ese sitio nunca se cae.
2. **Ejecución:** una línea de tiempo por estrategia con una fila por sitio, que muestra las tareas completadas, el trabajo perdido por caídas y los periodos en que el sitio estuvo caído. Se puede pausar, reiniciar, cambiar la velocidad y moverse en el tiempo.
3. **Resultados:** tabla comparativa, gráfica de tiempos con cada repetición y el reparto de tareas por sitio.
4. **¿Y si fuera un clúster?:** compara contra un clúster homogéneo con la misma cantidad de sitios y la misma capacidad total.

## Resultados de referencia

Perfil por defecto, 200 tareas, 10 repeticiones, semilla 1. Tiempo total en segundos simulados (media ± desviación entre repeticiones). El mínimo ideal es de unos 303 s.

| Estrategia | Clúster homogéneo | Grid heterogénea | Eficiencia en la Grid |
|---|---|---|---|
| Round-robin | 331,4 ± 11,0 | 2.007,6 ± 369,8 | 15,8 % |
| Por capacidad | 313,2 ± 6,9 | 850,5 ± 230,1 | 38,4 % |
| Work stealing | 313,3 ± 7,0 | 392,6 ± 18,0 | 78,3 % |

En el clúster las tres estrategias quedan cerca entre sí. En la Grid, el reparto estático no puede adaptarse a sitios de distinta velocidad ni a las caídas, y la diferencia con la cola dinámica es de varias veces.

Los parámetros de los sitios son de ejemplo, elegidos para el laboratorio, no mediciones de una Grid real.

## Estructura del proyecto

```
app.py              Servidor web (Flask) y API de simulación
nucleo.py           Simulación: sitios, tareas, planificadores y métricas
static/index.html   Interfaz web (HTML, CSS y JavaScript en un solo archivo)
prueba.py           Comparación por consola, sin interfaz
requirements.txt    Dependencias de Python
```

## Limitaciones

- Es un modelo simplificado: no simula congestión de red, costos de transferencia que dependan del tamaño de los datos, ni un broker que se caiga.
- Las colas de cada sitio son lógicas y el broker conoce su estado, lo que favorece al work stealing frente a una implementación completamente distribuida.