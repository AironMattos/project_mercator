"""Quadrante cruzado (checkpoint 12g, seção 3.2 do prompt de referência):
classifica um bairro pela direção das duas séries (comércio, oferta de
anúncio) no período, contra a própria baseline de cada uma - rótulos
descritivos, nunca avaliativos ("o produto não diz que um quadrante é
bom e outro é ruim", seção 3.2)."""
from __future__ import annotations

MOVIMENTO_NOS_DOIS_LADOS = "movimento_nos_dois_lados"
COMERCIO_CRESCE_OFERTA_ESCASSA = "comercio_cresce_oferta_escassa"
OFERTA_CRESCE_COMERCIO_PARADO = "oferta_cresce_comercio_parado"
MOVIMENTO_BAIXO_NOS_DOIS_LADOS = "movimento_baixo_nos_dois_lados"


def classificar_quadrante_cruzado(
    variacao_comercio_pct: float | None, variacao_anuncios_pct: float | None
) -> str | None:
    """Eixo comércio: `variacao_comercio_pct` acima de zero = "abrindo
    acima da média" (contra a própria baseline do bairro, mesma máquina
    de analytics.features.indicadores). Eixo anúncio:
    `variacao_anuncios_pct` acima de zero = "oferta imobiliária
    crescendo". `None` quando falta qualquer um dos dois eixos - nunca
    um palpite com metade da informação (mesmo padrão de
    classificar_quadrante_aquecimento)."""
    if variacao_comercio_pct is None or variacao_anuncios_pct is None:
        return None
    comercio_acima_da_media = variacao_comercio_pct > 0
    oferta_crescendo = variacao_anuncios_pct > 0
    if comercio_acima_da_media and oferta_crescendo:
        return MOVIMENTO_NOS_DOIS_LADOS
    if comercio_acima_da_media and not oferta_crescendo:
        return COMERCIO_CRESCE_OFERTA_ESCASSA
    if not comercio_acima_da_media and oferta_crescendo:
        return OFERTA_CRESCE_COMERCIO_PARADO
    return MOVIMENTO_BAIXO_NOS_DOIS_LADOS
