from __future__ import annotations

import uuid
from dataclasses import dataclass, field
from datetime import date

from domain.valuation import TIPOS_VALOR_VALIDOS

# Operação, não confundir com "venda concretizada" - um anúncio "à venda"
# é oferta, nunca um fato de transação (ver seção 1 do prompt de
# referência do Radar de Anúncios: "anúncio encerrado" nunca vira "venda").
OPERACOES_VALIDAS = frozenset({"venda", "aluguel"})

# Catálogo fechado e pequeno de propósito (seção 8 do prompt de
# referência) - "nao_classificado" é o destino de tudo que não casar,
# nunca um "outros" que esconde a taxa de classificação real da fonte
# (mesmo espírito de "sem categoria" no Radar de Comércio).
TIPOLOGIAS_VALIDAS = frozenset(
    {
        "apartamento",
        "casa",
        "sobrado",
        "kitnet_studio",
        "cobertura",
        "terreno",
        "sala_comercial",
        "galpao",
        "chacara_sitio",
        "nao_classificado",
    }
)

# tipo_valor é sempre 'anuncio' aqui - reaproveita a mesma validação das
# quatro grandezas monetárias do Radar Imobiliário (domain.valuation),
# nunca um valor solto sem classificação.
_TIPO_VALOR_ANUNCIO = "anuncio"


@dataclass(frozen=True)
class ObservacaoAnuncio:
    """O que sabíamos sobre um anúncio, e quando - mesma disciplina de
    imutabilidade de ObservacaoEntidade, mas como tabela própria
    (canonical.observacao_anuncio) em vez do padrão genérico
    entidade/atributos JSONB, porque o dado tem estrutura real que vale
    indexar (preço, bairro, tipologia) - mesmo raciocínio que já levou
    geolocalizacao_entidade e valor_referencia_territorial a serem
    tabelas dedicadas.

    Nunca contém nome, telefone, e-mail ou CRECI do anunciante - esses
    campos são descartados antes de este objeto existir (ver
    docs/lia-anuncios.md, seção 1). `ofertante_hash` é a única pegada do
    anunciante que sobrevive, e é irreversível.
    """

    entidade_id: uuid.UUID
    observado_em: date
    operacao: str
    tipologia: str
    preco: float | None
    condominio: float | None
    iptu: float | None
    area_util_m2: float | None
    quartos: int | None
    banheiros: int | None
    vagas: int | None
    andar: int | None
    impressao_digital: str
    fonte_id: str
    snapshot_ref: str
    territorio_id: str | None = None
    ofertante_hash: str | None = None
    tipo_valor: str = _TIPO_VALOR_ANUNCIO
    observacao_id: uuid.UUID = field(default_factory=uuid.uuid4)

    def __post_init__(self) -> None:
        if self.operacao not in OPERACOES_VALIDAS:
            raise ValueError(
                f"operacao inválida: {self.operacao!r}. "
                f"Deve ser uma de {sorted(OPERACOES_VALIDAS)}"
            )
        if self.tipologia not in TIPOLOGIAS_VALIDAS:
            raise ValueError(
                f"tipologia inválida: {self.tipologia!r}. "
                f"Deve ser uma de {sorted(TIPOLOGIAS_VALIDAS)}"
            )
        if self.tipo_valor not in TIPOS_VALOR_VALIDOS:
            raise ValueError(f"tipo_valor inválido: {self.tipo_valor!r}")
        if self.tipo_valor != _TIPO_VALOR_ANUNCIO:
            raise ValueError(
                f"ObservacaoAnuncio.tipo_valor é sempre {_TIPO_VALOR_ANUNCIO!r} - "
                "nenhuma outra grandeza monetária do Radar Imobiliário se aplica "
                "aqui (essas vêm de outras fontes, ver domain.valuation)"
            )
        if self.preco is not None and self.preco < 0:
            raise ValueError("preco não pode ser negativo")
        if not self.impressao_digital:
            raise ValueError(
                "impressao_digital não pode ser vazia - é a chave de "
                "resolução entre fontes (seção 8.1)"
            )
        if not self.fonte_id:
            raise ValueError("fonte_id não pode ser vazio")
        if not self.snapshot_ref:
            raise ValueError("snapshot_ref não pode ser vazio")


@dataclass(frozen=True)
class ClusterImovel:
    """Resultado da resolução entre fontes (seção 8.1) - um imóvel físico
    único, possivelmente anunciado por mais de uma fonte ao mesmo tempo.
    `entidade_ids`/`fontes` sempre têm o mesmo tamanho e mesma ordem -
    é o que alimenta o rótulo "anunciado em: Apolar e Chaves na Mão" na
    interface (seção 1.2 do prompt de referência)."""

    entidade_ids: tuple[uuid.UUID, ...]
    fontes: tuple[str, ...]
    impressao_digital: str
    cluster_id: uuid.UUID = field(default_factory=uuid.uuid4)

    def __post_init__(self) -> None:
        if not self.entidade_ids:
            raise ValueError("entidade_ids não pode ser vazio")
        if len(self.entidade_ids) != len(self.fontes):
            raise ValueError("entidade_ids e fontes devem ter o mesmo tamanho")
        if not self.impressao_digital:
            raise ValueError("impressao_digital não pode ser vazia")

    @property
    def multiplas_fontes(self) -> bool:
        """True quando o mesmo imóvel físico foi resolvido a partir de
        anúncios de mais de uma fonte distinta - o caso que a seção 8.1
        existe para não contar duas vezes em volume."""
        return len(set(self.fontes)) > 1
