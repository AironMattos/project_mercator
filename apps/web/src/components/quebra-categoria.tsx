import type { QuebraCategoria } from "@/lib/api";
import { formatarPercentual1, formatarValorCompacto } from "@/lib/indicadores";
import { AZUL_DESTAQUE } from "@/lib/palette";

// Barra horizontal fina (<=24px, cap arredondado) - especificação de forma
// da seção 3.4 do prompt de referência, mesma família de marca do resto
// do produto. Só as top N categorias já vêm do backend (quebra_categoria
// é limitada lá) - não é o catálogo inteiro, então a participação % abaixo
// é sobre a soma das categorias exibidas, não o total real do período
// (documentado em /metodologia#participacao).
export function QuebraCategoriaBars({ itens }: { itens: QuebraCategoria[] }) {
  if (itens.length === 0) {
    return <p className="text-xs text-muted-foreground">sem categoria resolvida no período</p>;
  }

  const max = Math.max(...itens.map((i) => i.contagem));
  const total = itens.reduce((soma, i) => soma + i.contagem, 0);

  return (
    <div className="space-y-1.5">
      {itens.map((item) => (
        <div key={item.categoriaId ?? "sem-categoria"} className="flex items-center gap-2">
          <span className="w-36 shrink-0 truncate text-xs text-muted-foreground">
            {item.nome}
          </span>
          <div className="h-4 flex-1 overflow-hidden rounded-sm bg-muted">
            <div
              className="h-full rounded-sm"
              style={{ width: `${Math.max(4, (item.contagem / max) * 100)}%`, backgroundColor: AZUL_DESTAQUE }}
            />
          </div>
          <span
            className="w-24 shrink-0 text-right text-xs font-medium"
            style={{ fontVariantNumeric: "tabular-nums" }}
          >
            {formatarValorCompacto(item.contagem)}{" "}
            <span className="font-normal text-muted-foreground">
              ({formatarPercentual1(total > 0 ? (item.contagem / total) * 100 : 0)})
            </span>
          </span>
        </div>
      ))}
    </div>
  );
}
