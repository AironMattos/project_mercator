from __future__ import annotations

import pytest

# Cenário do conftest.py (seeded_session): CENTRO tem 3 meses reais de
# INICIO_ATIVIDADE dentro da janela de baseline (2024-08, 2025-03,
# 2025-11) + 1 no mês "atual" (2026-07) -> baseline computável, não-zero.
# BATEL só tem o mês "atual" -> janela de baseline inteira zero-preenchida
# -> baseline=0.0 (não "historico_insuficiente" - zero é uma leitura real
# de "nenhuma abertura conhecida nesses meses", não falta de informação;
# ver a nota em indicador_repository._zero_fill). "historico_insuficiente"
# é reservado pra quando a própria janela não tem meses suficientes -
# nunca acontece aqui porque o repositório sempre zero-preenche 40 meses.


def test_metricas_comercio_com_territorio_inclui_baseline_de_aberturas(client):
    resp = client.get("/metricas/comercio", params={"territorio_id": "curitiba-bairro-centro"})
    assert resp.status_code == 200
    linhas = resp.json()
    por_mes = {linha["mes"]: linha for linha in linhas}

    linha_julho = por_mes["2026-07-01"]
    assert linha_julho["baseline"] == pytest.approx(0.125)
    assert linha_julho["variacao_pct"] == pytest.approx(7.0)
    assert linha_julho["tendencia"] == "acelerando"
    assert linha_julho["motivo_indisponivel"] is None

    # agosto é o mês do rótulo do snapshot mais recente - ainda sem
    # cobertura real de INICIO_ATIVIDADE (ver periodo_padrao_aberturas).
    linha_agosto = por_mes["2026-08-01"]
    assert linha_agosto["baseline"] is None
    assert linha_agosto["motivo_indisponivel"] == "mes_incompleto"


def test_metricas_comercio_agregado_por_bairro_baseline_nao_aplicavel(client):
    resp = client.get("/metricas/comercio")
    assert resp.status_code == 200
    linhas = resp.json()
    assert all(linha["baseline"] is None for linha in linhas)
    assert all(linha["motivo_indisponivel"] == "nao_aplicavel_sem_territorio_id" for linha in linhas)


def test_ranking_comercio_abaixo_do_piso_de_volume_fica_fora_da_lista_principal(client):
    resp = client.get("/ranking/comercio")
    assert resp.status_code == 200
    body = resp.json()

    # BATEL fica de fora por não ter variacao_pct (baseline zero). CENTRO
    # tem variacao_pct calculável (baseline 0.125, ver comentário no topo
    # do arquivo), mas 0.125 é bem abaixo do piso mínimo de volume do
    # ranking (checkpoint 10d, BASELINE_MINIMO_RANKING=10) - variação
    # percentual sobre uma fração de abertura por mês é ruído estatístico,
    # não crescimento real. Fica de fora de `itens`, mas contado em
    # `abaixo_do_piso_volume` - visível, não escondido. A mecânica de
    # ordenação/sparkline em si (com baseline realista, acima do piso) é
    # coberta em tests/analytics/features/test_indicadores.py, que não
    # depende de fixture de banco.
    assert body["itens"] == []
    assert body["abaixo_do_piso_volume"] == 1


def test_ranking_comercio_respeita_limite(client):
    resp = client.get("/ranking/comercio", params={"limite": 0})
    assert resp.status_code == 200
    assert resp.json()["itens"] == []


def test_bairro_resumo_inexistente_devolve_404(client):
    resp = client.get("/bairros/bairro-que-nao-existe/resumo")
    assert resp.status_code == 404


def test_bairro_resumo_centro_traz_aberturas_confiavel_e_saldo_em_construcao(client):
    resp = client.get("/bairros/curitiba-bairro-centro/resumo")
    assert resp.status_code == 200
    body = resp.json()

    assert body["territorio_id"] == "curitiba-bairro-centro"
    assert body["nome"] == "Centro"
    assert body["periodo"] == "2026-07-01"

    assert body["aberturas"]["baseline"] == pytest.approx(0.125)
    assert body["aberturas"]["motivo_indisponivel"] is None

    # saldo depende de fato_evento_territorial via ContagemEventos, que só
    # tem 2 meses reais no cenário semeado - insuficiente de propósito.
    assert body["saldo"]["baseline"] is None
    assert body["saldo"]["motivo_indisponivel"] == "historico_insuficiente"

    # Fora do ranking principal: baseline de aberturas (0.125) abaixo do
    # piso mínimo de volume (checkpoint 10d) - ver
    # test_ranking_comercio_abaixo_do_piso_de_volume_fica_fora_da_lista_principal.
    assert body["posicao_ranking"] is None
    assert body["total_ranking"] is None

    assert len(body["quebra_categoria"]) >= 1
    assert body["quebra_categoria"][0]["contagem"] >= 1

    assert len(body["serie_temporal"]) == 2
    meses_serie = {linha["mes"] for linha in body["serie_temporal"]}
    assert meses_serie == {"2026-07-01", "2026-08-01"}


def test_bairro_resumo_batel_aberturas_com_baseline_zero(client):
    resp = client.get("/bairros/curitiba-bairro-batel/resumo")
    assert resp.status_code == 200
    body = resp.json()

    assert body["aberturas"]["baseline"] == pytest.approx(0.0)
    assert body["aberturas"]["variacao_pct"] is None
    assert body["aberturas"]["motivo_indisponivel"] == "baseline_zero"

    # não elegível no ranking (sem variacao_pct) - e o total também vem
    # None porque o único outro bairro do cenário (Centro) está abaixo do
    # piso mínimo de volume (checkpoint 10d), então a lista de elegíveis
    # inteira fica vazia.
    assert body["posicao_ranking"] is None
    assert body["total_ranking"] is None
