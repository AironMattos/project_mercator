import {
  corDelta,
  formatarDeltaPct,
  formatarValorCompacto,
  motivoIndisponivelLegivel,
  rotuloTendencia,
  type Tendencia,
} from "@/lib/indicadores";

type StatTileProps = {
  /** minúsculo, sem dois-pontos no final (seção 3.4 do prompt de referência) */
  rotulo: string;
  valorAtual: number;
  baseline: number | null;
  variacaoPct: number | null;
  tendencia: Tendencia;
  motivoIndisponivel: string | null;
  /** true = acima do baseline é bom (aberturas/saldo); false inverteria (um
   * tile isolado de fechamento, se algum dia existir - ver corDelta). */
  cimaEBom: boolean;
  /** Texto explícito pro estado "em construção" (histórico insuficiente) -
   * em vez de omitir o tile ou mostrar zero, seção 3.3 do prompt. Se
   * omitido, cai no motivo genérico (motivoIndisponivelLegivel). */
  mensagemConstrucao?: string;
};

export function StatTile({
  rotulo,
  valorAtual,
  baseline,
  variacaoPct,
  tendencia,
  motivoIndisponivel,
  cimaEBom,
  mensagemConstrucao,
}: StatTileProps) {
  const semBaseline = baseline === null;

  return (
    <div className="flex-1 rounded-md border p-3">
      <p className="text-xs text-muted-foreground">{rotulo}</p>
      <p
        className="mt-1 text-2xl font-semibold"
        style={{ fontVariantNumeric: "proportional-nums" }}
      >
        {formatarValorCompacto(valorAtual)}
      </p>
      {semBaseline ? (
        <p className="mt-1 text-xs text-muted-foreground">
          {mensagemConstrucao ?? motivoIndisponivelLegivel(motivoIndisponivel)}
        </p>
      ) : (
        <div className="mt-1 flex flex-wrap items-center gap-x-2 gap-y-0.5 text-xs text-muted-foreground">
          {variacaoPct !== null ? (
            <span className="font-medium" style={{ color: corDelta(variacaoPct, cimaEBom) }}>
              {formatarDeltaPct(variacaoPct)}
            </span>
          ) : (
            <span>{motivoIndisponivelLegivel(motivoIndisponivel)}</span>
          )}
          <span>vs. baseline {formatarValorCompacto(baseline)}</span>
          {tendencia && <span>· {rotuloTendencia(tendencia)}</span>}
        </div>
      )}
    </div>
  );
}
