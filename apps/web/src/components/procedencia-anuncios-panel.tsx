import type { ProcedenciaFonte } from "@/lib/api";
import { formatarPercentual1, formatarValorCompacto } from "@/lib/indicadores";

const NOMES_FONTE: Record<string, string> = {
  apolar_anuncios: "Apolar",
  chavesnamao_anuncios: "Chaves na Mão",
};

function formatarData(iso: string | null): string {
  if (!iso) return "nenhuma coleta registrada";
  return new Date(iso).toLocaleDateString("pt-BR", { day: "2-digit", month: "2-digit", year: "numeric" });
}

// Painel de procedência ampliado do Radar de Anúncios (checkpoint 12i,
// seção 10 do prompt de referência) - Apolar e Chaves na Mão sempre
// separados, nunca uma média silenciosa entre as duas (seção 1.2). Mesmo
// princípio de DataQualityImoveis: fatos crus, sem nota nem score.
export function ProcedenciaAnunciosPanel({ fontes }: { fontes: ProcedenciaFonte[] }) {
  return (
    <div className="space-y-3">
      <p className="text-xs text-muted-foreground">
        Todo dado de anúncio nesta tela vem de uma destas duas fontes, ou das duas juntas — nunca
        combinadas sem indicação (seção 1.2 do prompt de referência).
      </p>
      <div className="overflow-x-auto rounded-md border">
        <table className="w-full text-sm">
          <thead className="border-b bg-muted/40 text-xs text-muted-foreground">
            <tr>
              <th className="px-3 py-2 text-left font-medium">fonte</th>
              <th className="px-3 py-2 text-right font-medium">última coleta</th>
              <th className="px-3 py-2 text-right font-medium">cadência</th>
              <th className="px-3 py-2 text-right font-medium">observados (30 dias)</th>
              <th className="px-3 py-2 text-right font-medium">tipologia classificada</th>
              <th className="px-3 py-2 text-right font-medium">bairro resolvido</th>
            </tr>
          </thead>
          <tbody className="divide-y">
            {fontes.map((fonte) => (
              <tr key={fonte.fonteId}>
                <td className="px-3 py-2 font-medium">{NOMES_FONTE[fonte.fonteId] ?? fonte.fonteId}</td>
                <td className="px-3 py-2 text-right text-xs text-muted-foreground">
                  {formatarData(fonte.ultimaAtualizacao)}
                </td>
                <td className="px-3 py-2 text-right text-xs text-muted-foreground">{fonte.cadencia}</td>
                <td className="px-3 py-2 text-right" style={{ fontVariantNumeric: "tabular-nums" }}>
                  {formatarValorCompacto(fonte.totalObservadoNoPeriodo)}
                </td>
                <td className="px-3 py-2 text-right" style={{ fontVariantNumeric: "tabular-nums" }}>
                  {fonte.taxaClassificacaoTipologia !== null
                    ? formatarPercentual1(fonte.taxaClassificacaoTipologia * 100)
                    : "—"}
                </td>
                <td className="px-3 py-2 text-right" style={{ fontVariantNumeric: "tabular-nums" }}>
                  {fonte.taxaResolucaoBairro !== null
                    ? formatarPercentual1(fonte.taxaResolucaoBairro * 100)
                    : "—"}
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
    </div>
  );
}
