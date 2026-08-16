import pytest

from infrastructure.connectors.fipezap.parsing import (
    encontrar_pagina_cidade,
    encontrar_pagina_destaques,
    extrair_bairros,
    extrair_kpis_cidade,
    resolver_territorio_bairro,
)

# Excertos reais (resumidos) do informe FipeZAP de venda residencial de
# julho/2026 - baixado de verdade no checkpoint 12b para confirmar o
# formato antes de escrever o parser.
TEXTO_DESTAQUES_VENDA = """DESTAQUES DO MÊS
■Análisedoúltimomês:combaseeminformaçõessobrepreçosdevendadeimóveisresidenciaisem56cidades,oÍndiceFipeZAPregistrouaumentomédiode
0,46%emjulhode2026.Individualmente,aaltaabrangeu49das56cidadesmonitoradas,incluindo18das22capitaisquecompõemacestadoÍndiceFipeZAP:
Vitória(+1,56%);Recife(+1,19%);Cuiabá(+0,11%);Curitiba(+0,08%);eBelém(+0,03%).Emcontraste,houvequedanospreçosdevendaemquatrocapitais.
■Balançoparcialde2026:oÍndiceFipeZAPdeVendaResidencialacumuloualtade2,89%entrejaneiroejulhode2026.RiodeJaneiro(+2,76%);SãoPaulo(+1,70%);
Curitiba(+0,32%);eBeloHorizonte(+0,09%).JáemPortoAlegre,houvequedade0,43%nobalançoparcialdoano.
■Análisedosúltimos12meses:levando-seemcontaosresultadosdejulhode2026,oÍndiceFipeZAPpassouaregistraraltade5,46%najanelamóvelde12meses.
BeloHorizonte(+3,85%);Curitiba(+3,85%);SãoPaulo(+3,70%);ePortoAlegre(+1,43%).
■Preçomédiodevendaresidencial:combaseeminformaçõesdaamostradeanúnciosdeimóveisresidenciaisparavendaemjulhode2026,opreçomédio
apuradonoâmbitodoÍndiceFipeZAPfoideR$9.900/m².ConsiderandoascapitaisqueintegramocálculodoÍndiceFipeZAP,SãoPaulo(R$12.099/m²);
Curitiba(R$11.761/m²);RiodeJaneiro(R$11.131/m²);BeloHorizonte(R$10.676/m²)."""

TEXTO_DESTAQUES_LOCACAO = """DESTAQUES DO MÊS
■Análisedoúltimomês:combaseeminformaçõesrelacionadasa36cidadesbrasileiras,oÍndiceFipeZAPregistrouavançode0,70%nospreçosdelocação
residencialemjulhode2026.Natal(+4,76%);Vitória(+2,66%);Curitiba(+0,57%);SãoPaulo(+0,31%).
■Balançoparcialde2026:nosprimeirossetemesesdoano,oÍndiceFipeZAPdeLocaçãoResidencialapresentoualtaacumuladade5,97%.Curitiba(+5,14%);
Cuiabá(+4,88%);PortoAlegre(+4,62%).
■Análisedosúltimos12meses:ospreçosdelocaçãoresidencialacumularamaltamédiade9,28%nosúltimos12meses.BeloHorizonte(+7,77%);
Curitiba(+9,17%);Recife(+7,57%).
■Preçomédiodelocaçãoresidencial:combasenaamostrade anúnciosdeapartamentosprontosparalocaçãonas36cidadesmonitoradas,opreçomédio
foideR$54,17/m²emjulhode2026.SãoPaulo(R$65,18/m²);BeloHorizonte(R$50,14/m²);Curitiba(R$48,91/m²);Cuiabá(R$48,86/m²).
■Rentabilidadedoaluguel:combaseemdadosdejulhode2026,oretornomédiofoiestimadoem6,14%aoano.Recife(8,47%a.a.);Curitiba(4,86%a.a.);
eVitória(4,16%a.a.)."""

TEXTO_PAGINA_CURITIBA_VENDA = """CURITIBA (PR)
ÍNDICE FIPEZAP | VENDA RESIDENCIAL INFORME DE JULHO/2026
(bloco de texto embaralhado do painel socioeconômico, ignorado de propósito)
■Zonas, distritos ou bairros mais representativos no cálculo do Índice FipeZAP*
Nível e variação média dos preços de venda de imóveis residenciais
variação em
preço médio em julho/2026 12 meses
BATEL R$ 17.525 /m² -0,8%
BIGORRILHO R$ 14.058 /m² +2,6%
Preço médio AGUA VERDE R$ 12.475 /m² +2,2%
mais alto (R$/m²)
CENTRO R$ 11.159 /m² +6,1%
Preço médio CAMPO COMPRIDO R$ 10.295 /m² +6,4%
mais baixo (R$/m²)
Sem informação CIDADE INDUSTRIAL DE CURITIBA R$ 9.078 /m² +9,0%
Fonte: Índice FipeZAP e IBGE. Nota (*): a Fipe não divulga informações detalhadas ou tabelas de preço médio por zona, distrito ou bairro."""

TEXTO_PAGINA_CURITIBA_LOCACAO = """CURITIBA (PR)
BATEL R$ 54,2 /m² +24,7%
CENTRO R$ 52,8 /m² +9,9%
CIDADE INDUSTRIAL DE… R$ 50,8 /m² +21,0%
AGUA VERDE R$ 48,8 /m² +9,0%
BACACHERI R$ 42,9 /m² +4,7%
ÍNDICE FIPEZAP | LOCAÇÃO RESIDENCIAL INFORME DE JULHO/2026
(bloco de texto embaralhado do painel socioeconômico, ignorado de propósito)"""

TEXTO_PAGINA_OUTRA_CIDADE_MENCIONANDO_CURITIBA = """VARIAÇÃO DO ÍNDICE FIPEZAP NAS CAPITAIS
Curitiba (PR) +0,08% alta real
Fonte: Índice FipeZAP e IBGE."""


def test_extrai_kpis_cidade_venda():
    kpis = extrair_kpis_cidade(TEXTO_DESTAQUES_VENDA, cidade="Curitiba")
    assert kpis.variacao_mensal == pytest.approx(0.0008)
    assert kpis.variacao_acumulada_ano == pytest.approx(0.0032)
    assert kpis.variacao_12m == pytest.approx(0.0385)
    assert kpis.preco_medio_m2 == 11761.0


def test_extrai_kpis_cidade_locacao_ignora_rentabilidade_sem_sinal():
    kpis = extrair_kpis_cidade(TEXTO_DESTAQUES_LOCACAO, cidade="Curitiba")
    assert kpis.variacao_mensal == pytest.approx(0.0057)
    assert kpis.variacao_acumulada_ano == pytest.approx(0.0514)
    assert kpis.variacao_12m == pytest.approx(0.0917)
    assert kpis.preco_medio_m2 == 48.91


def test_extrai_kpis_cidade_ausente_retorna_none():
    kpis = extrair_kpis_cidade(TEXTO_DESTAQUES_VENDA, cidade="Fortaleza")
    assert kpis.variacao_mensal is None
    assert kpis.variacao_acumulada_ano is None
    assert kpis.variacao_12m is None
    assert kpis.preco_medio_m2 is None


def test_encontrar_pagina_cidade_acha_cabecalho_exato():
    paginas = [
        TEXTO_PAGINA_OUTRA_CIDADE_MENCIONANDO_CURITIBA,
        TEXTO_PAGINA_CURITIBA_VENDA,
    ]
    achada = encontrar_pagina_cidade(paginas, "Curitiba")
    assert achada == TEXTO_PAGINA_CURITIBA_VENDA


def test_encontrar_pagina_cidade_nao_confunde_mencao_em_grafico():
    # a página de gráfico comparativo menciona "Curitiba (PR)" mas não é
    # o cabeçalho da página - não pode ser confundida com a página certa
    paginas = [TEXTO_PAGINA_OUTRA_CIDADE_MENCIONANDO_CURITIBA]
    assert encontrar_pagina_cidade(paginas, "Curitiba") is None


def test_extrai_bairros_venda_dez_representativos():
    linhas = extrair_bairros(TEXTO_PAGINA_CURITIBA_VENDA, operacao="venda")
    nomes = [linha.bairro_nome for linha in linhas]
    assert "BATEL" in nomes
    assert "CIDADE INDUSTRIAL DE CURITIBA" in nomes
    batel = next(linha for linha in linhas if linha.bairro_nome == "BATEL")
    assert batel.preco_medio_m2 == 17525.0
    assert batel.variacao_12m == pytest.approx(-0.008)


def test_extrai_bairros_locacao_com_nome_truncado():
    linhas = extrair_bairros(TEXTO_PAGINA_CURITIBA_LOCACAO, operacao="locacao")
    nomes = [linha.bairro_nome for linha in linhas]
    assert "CIDADE INDUSTRIAL DE…" in nomes
    truncado = next(linha for linha in linhas if linha.bairro_nome == "CIDADE INDUSTRIAL DE…")
    assert truncado.preco_medio_m2 == 50.8
    assert truncado.variacao_12m == pytest.approx(0.21)


def test_extrai_bairros_ignora_linhas_de_rotulo_do_grafico():
    linhas = extrair_bairros(TEXTO_PAGINA_CURITIBA_VENDA, operacao="venda")
    nomes = [linha.bairro_nome for linha in linhas]
    assert "Preço médio" not in nomes
    assert "Sem informação" not in " ".join(nomes)


def test_resolver_territorio_nome_exato():
    lookup = {"batel": "curitiba-bairro-batel", "centro": "curitiba-bairro-centro"}
    assert resolver_territorio_bairro("BATEL", lookup) == "curitiba-bairro-batel"


def test_resolver_territorio_nome_truncado_prefixo_unico():
    lookup = {
        "cidade-industrial-de-curitiba": "curitiba-bairro-cic",
        "centro": "curitiba-bairro-centro",
    }
    resolvido = resolver_territorio_bairro("CIDADE INDUSTRIAL DE…", lookup)
    assert resolvido == "curitiba-bairro-cic"


def test_resolver_territorio_nome_truncado_prefixo_ambiguo_fica_none():
    lookup = {
        "santa-candida": "curitiba-bairro-santa-candida",
        "santa-felicidade": "curitiba-bairro-santa-felicidade",
    }
    assert resolver_territorio_bairro("SANTA…", lookup) is None


def test_resolver_territorio_nao_resolvido_fica_none():
    lookup = {"batel": "curitiba-bairro-batel"}
    assert resolver_territorio_bairro("BAIRRO INEXISTENTE", lookup) is None


def test_encontrar_pagina_destaques_por_cabecalho():
    paginas = ["SUMÁRIO\nalgo\n", TEXTO_DESTAQUES_VENDA, TEXTO_PAGINA_CURITIBA_VENDA]
    assert encontrar_pagina_destaques(paginas) == TEXTO_DESTAQUES_VENDA


def test_encontrar_pagina_destaques_ausente_retorna_none():
    assert encontrar_pagina_destaques(["SUMÁRIO\nalgo\n"]) is None
