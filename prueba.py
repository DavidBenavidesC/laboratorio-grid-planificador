import nucleo

for titulo, perfil in (("Clúster homogéneo", nucleo.perfil_cluster()),
                       ("Grid heterogénea", nucleo.perfil_grid())):
    print(f"\n=== {titulo} (200 tareas, 10 repeticiones) ===")
    res = nucleo.comparar(perfil, n_tareas=200, repeticiones=10)
    limite = next(iter(res.values()))["detalle"]["limite_inferior"]
    print(f"Límite inferior (sin latencia ni caídas): {limite:.1f} s")
    print(f"{'Estrategia':32}{'Tiempo (s)':>16}{'Eficiencia':>12}{'Utiliz.':>9}{'Perdidas':>10}{'Reasig.':>9}")
    for r in res.values():
        print(f"{r['nombre']:32}{r['makespan_medio']:>10.1f} ±{r['makespan_sd']:>4.1f}"
              f"{r['eficiencia_media']*100:>11.1f}%{r['utilizacion_media']*100:>8.1f}%"
              f"{r['perdidas_medias']:>10.1f}{r['reasignaciones_medias']:>9.1f}")