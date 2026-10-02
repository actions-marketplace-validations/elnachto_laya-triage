from repo import MEZCLA_NATURAL, mapear_etiquetas, mezcla_desde_conteos, pesos_para_ruta
import pytest


def test_mezcla_con_pocos_etiquetados_devuelve_none():
    conteos = {"bug": 10, "feature": 5, "question": 2, "docs": 1}
    assert mezcla_desde_conteos(conteos) is None


def test_mapear_etiquetas_sinonimos():
    assert mapear_etiquetas(["type: bug"])["bug"] == "type: bug"


def test_pesos_para_ruta_sin_priores():
    mezcla = {"bug": 0.6, "feature": 0.2, "question": 0.1, "docs": 0.1}
    pesos = pesos_para_ruta(mezcla, None)
    for tipo, natural in MEZCLA_NATURAL.items():
        assert pesos[tipo] == pytest.approx(mezcla[tipo] / natural)


def test_mezcla_con_minimo_etiquetados_devuelve_distribucion():
    conteos = {"bug": 15, "feature": 10, "question": 3, "docs": 2}
    resultado = mezcla_desde_conteos(conteos)
    assert resultado is not None
    assert sum(resultado.values()) == pytest.approx(1.0)


def test_pesos_para_ruta_con_priores_devuelve_mezcla():
    mezcla = {"bug": 0.6, "feature": 0.2, "question": 0.1, "docs": 0.1}
    priores = {"bug": 0.5, "feature": 0.3, "question": 0.1, "docs": 0.1}
    assert pesos_para_ruta(mezcla, priores) == mezcla


def test_pesos_para_ruta_vacia_devuelve_priores():
    priores = {"bug": 0.5, "feature": 0.3, "question": 0.1, "docs": 0.1}
    assert pesos_para_ruta({}, priores) == priores
