from scripts import comparar_costos as cc

PREFIJOS = {'agente': 1000, 'politicas': 800, 'router': 200}


def test_la_mezcla_suma_cien_y_cubre_todas_las_rutas():
    assert sum(cc.MEZCLA.values()) == 100
    assert set(cc.MEZCLA) == set(cc.VUELTAS_AGENTE)


def test_cada_vuelta_del_agente_reenvia_el_prefijo():
    assert cc.tokens_agente(1000, 1) == 1000 + cc.MENSAJE_TIPICO
    assert cc.tokens_agente(1000, 2) == 2 * (1000 + cc.MENSAJE_TIPICO) + cc.EXTRA_POR_VUELTA


def test_reclamo_con_router_no_paga_el_agente():
    fila = cc.estimar(PREFIJOS)['reclamo']
    assert fila['con_router'] == 200 + cc.MENSAJE_TIPICO
    assert fila['con_router'] < fila['solo_agente']


def test_cotizacion_con_router_cuesta_la_clasificacion_de_mas():
    fila = cc.estimar(PREFIJOS)['cotizacion']
    assert fila['con_router'] - fila['solo_agente'] == 200 + cc.MENSAJE_TIPICO
    assert fila['llamadas_router'] == fila['llamadas_solo'] + 1


def test_promedio_ponderado():
    filas = {'a': {'pct': 50, 'x': 100}, 'b': {'pct': 50, 'x': 300}}
    assert cc.promedio(filas, 'x') == 200
