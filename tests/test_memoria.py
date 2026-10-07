import numpy as np
import pytest

from memoria import fusionar, margen, votar


def memoria_de_prueba():
    vectores = np.eye(4, dtype=np.float32)
    vectores = np.vstack([vectores, vectores, vectores])
    tipos = np.array([0, 1, 2, 3] * 3)
    numeros = np.arange(1, 13)
    return {"vectores": vectores, "tipos": tipos, "numeros": numeros}


def test_votar_sin_suficientes_vecinos_pasados():
    assert votar(memoria_de_prueba(), np.array([1, 0, 0, 0], dtype=np.float32), 3) is None


def test_votar_favorece_a_los_parecidos():
    voto = votar(memoria_de_prueba(), np.array([0, 0, 1, 0], dtype=np.float32), 100)
    assert max(voto, key=voto.get) == "question"
    assert sum(voto.values()) == pytest.approx(1.0)


def test_fusionar_no_toca_si_el_modelo_esta_seguro():
    respuesta = {"choice": "bug", "answer_confidence": 0.9, "probabilities": {"bug": 0.9, "feature": 0.05, "question": 0.03, "docs": 0.02}}
    voto = {"bug": 0.0, "feature": 0.0, "question": 1.0, "docs": 0.0}
    resultado, usada = fusionar(respuesta, voto)
    assert not usada
    assert resultado["choice"] == "bug"


def test_fusionar_cambia_la_decision_si_el_modelo_duda():
    respuesta = {"choice": "bug", "answer_confidence": 0.5, "probabilities": {"bug": 0.5, "feature": 0.05, "question": 0.4, "docs": 0.05}}
    voto = {"bug": 0.1, "feature": 0.0, "question": 0.9, "docs": 0.0}
    resultado, usada = fusionar(respuesta, voto)
    assert usada
    assert resultado["choice"] == "question"
    assert sum(resultado["probabilities"].values()) == pytest.approx(1.0)


def test_margen():
    assert margen({"bug": 0.5, "question": 0.4, "feature": 0.1}) == pytest.approx(0.1)