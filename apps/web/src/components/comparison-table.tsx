import type { BairroResumo, Indicador } from "@/lib/api";
import { formatarDeltaPct, formatarValorCompacto, motivoIndisponivelLegivel } from "@/lib/indicadores";
import { MethodologyTooltip } from "@/components/methodology-tooltip";

type Props = { itens: BairroResumo[] };

function CelulaIndicador({ indicador }: { indicador: Indicador }) {
  if (indicador.baseline === null) {
    return (
      <span className="text-muted-foreground">
        {motivoIndisponivelLegivel(indicador.motivoIndisponivel)}
      </span>
    );
  }
  return (
    <span style={{ fontVariantNumeric: "tabular-nums" }}>
      <span className="font-medium">{formatarValorCompacto(indicador.valorAtual)}</span>{" "}
      <span className="text-xs text-muted-foreground">
        ({formatarDeltaPct(indicador.variacaoPct)} vs. baseline)
      </span>
    </span>
  );
}

// ComparisonTable do design system pedido pelo prompt - linhas = métrica,
// colunas = bairro selecionado, lado a lado. Nenhuma nota agregada
// decidindo "qual é melhor" (seção "COMPARAÇÃO": "a comparação deve
// apresentar os dados lado a lado e permitir que o usuário forme sua
// própria conclusão").
export function ComparisonTable({ itens }: Props) {
  return (
    <div className="overflow-x-auto rounded-md border">
      <table className="w-full text-sm">
        <thead>
          <tr className="border-b bg-muted/30">
            <th className="px-3 py-2 text-left text-xs font-medium text-muted-foreground">
              métrica
            </th>
            {itens.map((item) => (
              <th key={item.territorioId} className="px-3 py-2 text-left text-sm font-semibold">
                {item.nome}
              </th>
            ))}
          </tr>
        </thead>
        <tbody className="divide-y">
          <tr>
            <td className="px-3 py-2 text-xs text-muted-foreground">
              <span className="flex items-center gap-1">
                aberturas (mês de referência)
                <MethodologyTooltip
                  titulo="aberturas"
                  formula="Novos estabelecimentos identificados no mês, comparados à média móvel dos 24 meses anteriores."
                  ancora="baseline"
                />
              </span>
            </td>
            {itens.map((item) => (
              <td key={item.territorioId} className="px-3 py-2">
                <CelulaIndicador indicador={item.aberturas} />
              </td>
            ))}
          </tr>
          <tr>
            <td className="px-3 py-2 text-xs text-muted-foreground">
              <span className="flex items-center gap-1">
                saldo líquido
                <MethodologyTooltip
                  titulo="saldo"
                  formula="Aberturas menos fechamentos (desaparecimentos) no período."
                  ancora="saldo"
                />
              </span>
            </td>
            {itens.map((item) => (
              <td key={item.territorioId} className="px-3 py-2">
                <CelulaIndicador indicador={item.saldo} />
              </td>
            ))}
          </tr>
          <tr>
            <td className="px-3 py-2 text-xs text-muted-foreground">
              <span className="flex items-center gap-1">
                posição no ranking de crescimento
                <MethodologyTooltip
                  titulo="ranking de crescimento"
                  formula="Bairros ordenados por variação % de aberturas frente ao baseline dos últimos 24 meses - crescimento relativo, não volume absoluto."
                  ancora="baseline"
                />
              </span>
            </td>
            {itens.map((item) => (
              <td key={item.territorioId} className="px-3 py-2" style={{ fontVariantNumeric: "tabular-nums" }}>
                {item.posicaoRanking !== null && item.totalRanking !== null ? (
                  <span className="font-medium">
                    #{item.posicaoRanking} de {item.totalRanking}
                  </span>
                ) : (
                  <span className="text-muted-foreground">fora do ranking principal</span>
                )}
              </td>
            ))}
          </tr>
          <tr>
            <td className="px-3 py-2 text-xs text-muted-foreground">categoria principal em aberturas</td>
            {itens.map((item) => {
              const principal = item.quebraCategoria[0];
              return (
                <td key={item.territorioId} className="px-3 py-2">
                  {principal ? (
                    <span>
                      {principal.nome}{" "}
                      <span className="text-xs text-muted-foreground">
                        ({formatarValorCompacto(principal.contagem)})
                      </span>
                    </span>
                  ) : (
                    <span className="text-muted-foreground">sem categoria resolvida</span>
                  )}
                </td>
              );
            })}
          </tr>
        </tbody>
      </table>
    </div>
  );
}
