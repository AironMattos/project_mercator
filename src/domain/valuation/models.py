from __future__ import annotations

import uuid
from dataclasses import dataclass, field
from datetime import date

from shapely.geometry.base import BaseGeometry

# As quatro grandezas monetárias do mercado imobiliário não são
# intercambiáveis - ver seção 1 do prompt de referência do Radar
# Imobiliário. Colapsá-las num campo genérico "valor"/"preco" é o erro
# estrutural que esta regra existe para impedir, do mesmo jeito que o
# catálogo de eventos já recusa colapsar PRIMEIRA_OBSERVACAO e
# ABERTURA_CONFIRMADA (ver domain/event/models.py).
TIPOS_VALOR_VALIDOS = frozenset({"venal", "avaliacao", "anuncio", "transacao"})
COMPONENTES_VALIDOS = frozenset({"terreno", "construcao", "total"})


@dataclass(frozen=True)
class ValorMonetario:
    """Uma grandeza monetária imobiliária, sempre com proveniência e
    classificação explícitas - nunca um número solto. Todo valor
    monetário do Radar Imobiliário passa por aqui antes de virar linha de
    banco, resposta de API ou número em tela."""

    valor_m2: float
    tipo_valor: str
    componente: str
    fonte_id: str

    def __post_init__(self) -> None:
        if self.tipo_valor not in TIPOS_VALOR_VALIDOS:
            raise ValueError(
                f"tipo_valor inválido: {self.tipo_valor!r}. "
                f"Deve ser um de {sorted(TIPOS_VALOR_VALIDOS)}"
            )
        if self.componente not in COMPONENTES_VALIDOS:
            raise ValueError(
                f"componente inválido: {self.componente!r}. "
                f"Deve ser um de {sorted(COMPONENTES_VALIDOS)}"
            )
        if not self.fonte_id:
            raise ValueError(
                "fonte_id não pode ser vazio - todo valor monetário "
                "precisa de proveniência"
            )
        if self.valor_m2 < 0:
            raise ValueError("valor_m2 não pode ser negativo")


@dataclass(frozen=True)
class ValorReferenciaTerritorial:
    """Um valor de referência territorial pronto para persistir em
    canonical.valor_referencia_territorial - a mesma validação de
    tipo_valor/componente/fonte_id de ValorMonetario, mais o que é
    necessário para localizar e versionar o registro.

    vigencia_inicio/vigencia_fim em vez de sobrescrita: quando um valor
    de referência for revisado, a versão anterior continua consultável -
    mesma disciplina de imutabilidade de observacao_entidade/evento.
    """

    geometria: BaseGeometry
    tipo_valor: str
    componente: str
    valor_m2: float
    moeda_data: date
    fonte_id: str
    vigencia_inicio: date
    snapshot_ref: str
    # Identidade do registro na fonte (ex.: objectid do ArcGIS) - é o que
    # torna a gravação idempotente (ver ORM), não territorio_id: uma
    # fonte comum tem várias geometrias (microrregiões, faces de quadra)
    # dentro do mesmo bairro, cada uma com seu próprio valor - usar
    # território como parte da chave de dedup colapsaria todas elas numa
    # só (bug real, encontrado rodando contra dado real do checkpoint
    # 11c: 1011 valores normalizados viraram 74 linhas gravadas).
    objectid_fonte: int | None = None
    territorio_id: str | None = None
    metodologia: str | None = None
    vigencia_fim: date | None = None
    valor_id: uuid.UUID = field(default_factory=uuid.uuid4)

    def __post_init__(self) -> None:
        if self.tipo_valor not in TIPOS_VALOR_VALIDOS:
            raise ValueError(
                f"tipo_valor inválido: {self.tipo_valor!r}. "
                f"Deve ser um de {sorted(TIPOS_VALOR_VALIDOS)}"
            )
        if self.componente not in COMPONENTES_VALIDOS:
            raise ValueError(
                f"componente inválido: {self.componente!r}. "
                f"Deve ser um de {sorted(COMPONENTES_VALIDOS)}"
            )
        if not self.fonte_id:
            raise ValueError(
                "fonte_id não pode ser vazio - todo valor monetário "
                "precisa de proveniência"
            )
        if self.valor_m2 < 0:
            raise ValueError("valor_m2 não pode ser negativo")
        if self.geometria is None or self.geometria.is_empty:
            raise ValueError("geometria não pode ser vazia")


CATEGORIAS_INDICADOR_BCB_VALIDAS = frozenset({"valor", "area", "contagem"})


@dataclass(frozen=True)
class IndicadorMercadoImobiliarioUf:
    """Uma leitura mensal de uma série do serviço MercadoImobiliario do
    BCB (checkpoint 11d), granularidade UF - nunca confundir com dado de
    Curitiba. A fonte publica 14 séries sob o mesmo formato genérico
    (Data/Info/Valor), cobrindo três naturezas de número diferentes -
    daqui a necessidade de categoria, para nunca somar uma contagem com
    um valor monetário:

    - categoria='valor': mediana em R$ de imóveis ADQUIRIDOS via
      financiamento reportado ao SCR (fonte ACNV1501, confirmado na
      Metodologia.pdf oficial do BCB) - 'imoveis_valor_avaliacao'
      (avaliação do banco) e 'imoveis_valor_compra'. 'valor_compra' é o
      preço efetivamente contratado na aquisição, não uma segunda
      avaliação - por isso mapeado para tipo_valor='transacao', não
      'avaliacao' (ver domain/valuation.TIPOS_VALOR_VALIDOS). Viés de
      amostra explícito: só cobre imóveis financiados via alienação
      fiduciária/hipoteca reportados ao SCR, não todas as transações do
      estado - nunca apresentar como preço de mercado do Paraná inteiro.
    - categoria='area': mediana em m² ('imoveis_area_privativa',
      'imoveis_area_total') - não monetário.
    - categoria='contagem': número de imóveis adquiridos no mês
      classificados por tipo/dormitórios/implantação/garantia - não
      monetário, não confundir com volume de mercado (é volume só da
      fatia financiada via SCR).

    tipo_valor só é preenchido quando categoria='valor' - reaproveita a
    mesma validação de TIPOS_VALOR_VALIDOS de ValorMonetario, para que a
    regra das quatro grandezas monetárias valha aqui também."""

    uf: str
    periodo_referencia: date
    indicador: str
    categoria: str
    unidade: str
    leitura: float
    fonte_id: str
    snapshot_ref: str
    tipo_valor: str | None = None

    def __post_init__(self) -> None:
        if not self.uf:
            raise ValueError("uf não pode ser vazia")
        if self.categoria not in CATEGORIAS_INDICADOR_BCB_VALIDAS:
            raise ValueError(
                f"categoria inválida: {self.categoria!r}. "
                f"Deve ser uma de {sorted(CATEGORIAS_INDICADOR_BCB_VALIDAS)}"
            )
        if self.categoria == "valor":
            if self.tipo_valor not in TIPOS_VALOR_VALIDOS:
                raise ValueError(
                    f"categoria='valor' exige tipo_valor válido, recebido "
                    f"{self.tipo_valor!r}"
                )
        elif self.tipo_valor is not None:
            raise ValueError(
                f"tipo_valor só se aplica a categoria='valor', não a "
                f"categoria={self.categoria!r}"
            )
        if not self.unidade:
            raise ValueError("unidade não pode ser vazia")
        if not self.fonte_id:
            raise ValueError("fonte_id não pode ser vazio")
