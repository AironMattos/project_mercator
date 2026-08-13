import type { QualidadeDados } from "@/lib/api";
import { formatarPercentual1, formatarValorCompacto } from "@/lib/indicadores";

function formatarDataHora(iso: string | null): string {
  if (!iso) return "nenhuma execução registrada";
  const d = new Date(iso);
  return d.toLocaleDateString("pt-BR", { day: "2-digit", month: "2-digit", year: "numeric" });
}

// Componente do design system pedido pelo prompt (DataQuality) - fatos
// objetivos sobre a base, nunca um "índice de confiança" composto (a
// restrição é explícita na seção "QUALIDADE DOS DADOS"). Cada número aqui
// vem direto de GET /qualidade-dados, sem ponderação nem nota.
export function DataQuality({ dados }: { dados: QualidadeDados }) {
  return (
    <dl className="grid grid-cols-2 gap-x-6 gap-y-3 text-xs sm:grid-cols-4">
      <div>
        <dt className="text-muted-foreground">estabelecimentos analisados</dt>
        <dd className="mt-0.5 text-sm font-medium" style={{ fontVariantNumeric: "tabular-nums" }}>
          {formatarValorCompacto(dados.totalEstabelecimentos)}
        </dd>
      </div>
      <div>
        <dt className="text-muted-foreground">com localização geográfica válida</dt>
        <dd className="mt-0.5 text-sm font-medium" style={{ fontVariantNumeric: "tabular-nums" }}>
          {formatarPercentual1(dados.pctLocalizacaoValida)}
        </dd>
      </div>
      <div>
        <dt className="text-muted-foreground">com localização pouco confiável</dt>
        <dd className="mt-0.5 text-sm font-medium" style={{ fontVariantNumeric: "tabular-nums" }}>
          {formatarValorCompacto(dados.geocodificadosBaixa)}
        </dd>
      </div>
      <div>
        <dt className="text-muted-foreground">última atualização da base</dt>
        <dd className="mt-0.5 text-sm font-medium">{formatarDataHora(dados.ultimaAtualizacao)}</dd>
      </div>
    </dl>
  );
}
