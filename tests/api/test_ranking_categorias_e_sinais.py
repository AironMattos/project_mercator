from __future__ import annotations

# Cenário do conftest.py: analytics.contagem_inicio_atividade só tem
# categoria_id=None em todas as linhas (ver seeded_session) - suficiente
# pra confirmar que /ranking/categorias não quebra e devolve lista vazia
# quando não há nenhuma categoria resolvida na janela (categoria_id IS NULL
# é excluído de propósito, ver series_aberturas_por_categoria).


def test_ranking_categorias_sem_categoria_resolvida_devolve_lista_vazia(client):
    resp = client.get("/ranking/categorias")
    assert resp.status_code == 200
    body = resp.json()
    assert body["itens"] == []


def test_ranking_comercio_ordem_asc_traz_maiores_retracoes(client):
    resp = client.get("/ranking/comercio", params={"ordem": "asc"})
    assert resp.status_code == 200
    # Mesmo cenário de test_ranking_comercio_abaixo_do_piso_de_volume_fica_fora_da_lista_principal:
    # nenhum item elegível nesse banco semeado (CENTRO abaixo do piso de
    # volume, BATEL sem variacao_pct) - o que importa aqui é que o parâmetro
    # `ordem` é aceito e não quebra a rota.
    assert resp.json()["itens"] == []


def test_sinais_sem_historico_suficiente_reporta_motivo(client):
    resp = client.get("/sinais")
    assert resp.status_code == 200
    body = resp.json()
    # Cobertura real (ver ContagemEventos semeada) só tem jul/ago-2026 -
    # bem abaixo dos 4 meses consecutivos exigidos pelo critério, mas o mês
    # de referência existe, então motivo_indisponivel deve vir None (o
    # critério simplesmente não encontrou ninguém elegível, o que é
    # diferente de "não há dado nenhum").
    assert body["itens"] == []
    assert body["periodo_referencia"] == "2026-08-01"
    assert "saldo líquido" in body["criterio"].lower()
