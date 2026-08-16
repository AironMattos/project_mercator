from __future__ import annotations

import uuid
from dataclasses import dataclass, field
from datetime import date
from typing import Any

TIPOS_EVENTO_VALIDOS = frozenset(
    {
        "PRIMEIRA_OBSERVACAO",
        "ABERTURA_CONFIRMADA",
        "DESAPARECIMENTO",
        # reservado: depende de uma segunda fonte que ainda não existe no
        # projeto - nenhuma regra emite este tipo ainda.
        "FECHAMENTO_CONFIRMADO",
        "MUDANCA_CATEGORIA",
        # entity_type="obra" (Radar Imobiliário, checkpoint 11) - fonte
        # confirmada no checkpoint 11a (relatório mensal Alvará/CVCO da
        # SMU). ALVARA_APROVADO e OBRA_CONCLUIDA nunca são somados numa
        # métrica única de "atividade construtiva" - respondem perguntas
        # diferentes ("onde vai mudar" vs. "onde já mudou").
        "ALVARA_APROVADO",
        "OBRA_CONCLUIDA",
        "ALVARA_DEMOLICAO",
        # entity_type="territorio" - detecção de mudança de zoneamento por
        # diff de data_versao/data_atualizacao entre execuções do conector
        # geocuritiba_cadastro (campos confirmados no checkpoint 11a). A
        # regra de detecção em si é trabalho de pipeline, não deste
        # checkpoint - reservado como PRIMEIRA_OBSERVACAO/ABERTURA_CONFIRMADA
        # já foram antes de o conector correspondente existir.
        "ZONEAMENTO_ALTERADO",
        # reservado, propositalmente não implementado (ver seção 8 do
        # prompt de referência do Radar Imobiliário): LANCAMENTO depende de
        # dado comercial/setorial restrito; TRANSACAO depende de ITBI, que
        # Curitiba não publica. Nenhuma regra emite qualquer um dos dois -
        # populá-los com um proxy seria o atalho que o resto do sistema
        # recusa.
        "LANCAMENTO",
        "TRANSACAO",
        # entity_type="anuncio_imovel" (Radar de Anúncios, checkpoint 12) -
        # mede intenção/movimento de oferta, nunca transação consumada (ver
        # docs/fontes-anuncios.md e a seção 1 do prompt de referência: um
        # anúncio nunca é chamado de "venda"). ANUNCIO_ENCERRADO é sempre
        # confiança "baixa" por natureza - o anúncio pode ter saído da
        # oferta por venda, aluguel, retirada, expiração ou republicação
        # com outro identificador, indistinguíveis de fora (mesma
        # distinção que já separa DESAPARECIMENTO de FECHAMENTO_CONFIRMADO
        # no Radar de Comércio).
        "ANUNCIO_PUBLICADO",
        "ANUNCIO_ENCERRADO",
        "PRECO_ALTERADO",
        "REANUNCIO",
    }
)
CONFIANCAS_VALIDAS = frozenset({"alta", "media", "baixa"})


@dataclass(frozen=True)
class Evento:
    """O que foi inferido comparando duas observações. Sempre aponta de
    volta para as observações que o sustentam (origem_observacoes) - um
    evento nunca é gerado "do nada".
    """

    entity_type: str
    event_type: str
    entidade_id: uuid.UUID
    data_evento: date
    confianca: str
    origem_observacoes: tuple[uuid.UUID, ...]
    territorio_id: str | None = None
    payload: dict[str, Any] = field(default_factory=dict)
    evento_id: uuid.UUID = field(default_factory=uuid.uuid4)

    def __post_init__(self) -> None:
        if not self.entity_type:
            raise ValueError("entity_type não pode ser vazio")
        if self.event_type not in TIPOS_EVENTO_VALIDOS:
            raise ValueError(
                f"event_type inválido: {self.event_type!r}. "
                f"Deve ser um de {sorted(TIPOS_EVENTO_VALIDOS)}"
            )
        if self.confianca not in CONFIANCAS_VALIDAS:
            raise ValueError(
                f"confianca inválida: {self.confianca!r}. "
                f"Deve ser uma de {sorted(CONFIANCAS_VALIDAS)}"
            )
        if not self.origem_observacoes:
            raise ValueError(
                "origem_observacoes não pode ser vazio - todo evento aponta "
                "para as observações que o sustentam"
            )
