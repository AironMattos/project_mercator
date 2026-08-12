from __future__ import annotations

import re

# A Base de Alvarás (SMF/Curitiba) não documenta o formato de
# CNAE_ATIVIDADE_PRINCIPAL - nem o prompt original, nem o "dicionário de
# dados" publicado pela própria fonte mencionam esse campo. Investigando o
# dado real (~511 mil observações de 2026-08), dois formatos aparecem:
#
# 1. "S.96.0.2-5/01-00" (~97% dos códigos distintos) - decompõe como
#    <seção letra>.<divisão 2d>.<grupo 1d>.<classe 1d>-<dv 1d>/<subclasse
#    2d>-<sufixo 2d, sempre "00", sem significado aparente>. Concatenando
#    divisão+grupo+classe+dv+subclasse dá exatamente o "id" de 7 dígitos
#    que a API pública do IBGE usa para a subclasse - confirmado
#    comparando contra descrições conhecidas: "S.96.0.2-5/01-00" vira
#    "9602501" = "CABELEIREIROS, MANICURE E PEDICURE" (bate);
#    "G.47.2.1-1/02-00" vira "4721102" = "PADARIA E CONFEITARIA COM
#    PREDOMINÂNCIA DE REVENDA" (bate); "C.10.9.1-1/02-00" vira "1091102"
#    = "FABRICAÇÃO DE PRODUTOS DE PADARIA..." (bate).
# 2. Um segundo formato tipo "5-70.20.00" (~3%) e um placeholder óbvio
#    "X.88.8.8-8/88-88" (seção "X" não existe na CNAE oficial, que vai de
#    A a U) usado para "autônomo genérico"/atividade não classificada.
#    Nenhum dos dois corresponde a um código CNAE real - não tentamos
#    normalizar esses; ficam como não resolvidos (retornam None), mesmo
#    tratamento dado a divergências de bairro no checkpoint 2.
#
# A seção é restrita a A-U (as 21 seções reais da CNAE) de propósito: sem
# isso, o placeholder "X.88.8.8-8/88-88" passa pelo formato dominante e
# normaliza silenciosamente para "8888888", um código que não existe.
_PADRAO_FORMATO_FONTE = re.compile(
    r"^[A-U]\.(\d{2})\.(\d)\.(\d)-(\d)/(\d{2})-\d{2}$"
)


def normalizar_codigo_cnae(bruto: str | None) -> str | None:
    """Converte o CNAE como a Base de Alvarás relata para o código de
    7 dígitos usado pela tabela oficial do IBGE (`canonical.dim_cnae`).

    Retorna None quando o valor não é reconhecível como um código CNAE
    real (formato não documentado, placeholder, ausente) - não é um erro,
    é um problema esperado da fonte.
    """
    if not bruto:
        return None
    m = _PADRAO_FORMATO_FONTE.match(bruto.strip())
    if not m:
        return None
    return "".join(m.groups())
