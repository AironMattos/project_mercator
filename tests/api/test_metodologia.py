from __future__ import annotations

import pytest

# Cenário do conftest.py: 4 entidades tipo_entidade='comercio' com linha em
# geolocalizacao_entidade (alta, media, baixa, alta) - nenhuma sem linha, então
# nao_geocodificados=0 nesse cenário; pct_localizacao_valida conta
# alta+media (3 de 4 = 75%), mesmo corte de CONFIANCAS_NA_CONTAGEM_PRINCIPAL
# em busca_raio.py.


def test_qualidade_dados_conta_por_confianca_sem_score_composto(client):
    resp = client.get("/qualidade-dados")
    assert resp.status_code == 200
    body = resp.json()

    assert body["total_estabelecimentos"] == 4
    assert body["geocodificados_alta"] == 2
    assert body["geocodificados_media"] == 1
    assert body["geocodificados_baixa"] == 1
    assert body["nao_geocodificados"] == 0
    assert body["pct_localizacao_valida"] == pytest.approx(75.0)


def test_qualidade_dados_inclui_cobertura_temporal_real(client):
    resp = client.get("/qualidade-dados")
    body = resp.json()
    # Cobertura real de fato_evento_territorial via ContagemEventos, mesmo
    # dado que GET /metricas/cobertura expõe.
    assert body["cobertura_temporal"]["mes_inicio"] == "2026-07-01"
    assert body["cobertura_temporal"]["mes_fim"] == "2026-08-01"
