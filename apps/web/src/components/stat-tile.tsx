import { MethodologyTooltip } from "@/components/methodology-tooltip";
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
  /** Fórmula/definição do indicador (checkpoint 11a) - todo tile numérico
   * deve poder responder "como vocês chegaram nesse número?" sem sair da
   * tela. Omitido só nos poucos casos sem contraparte em /metodologia. */
  metodologia?: { formula: string; ancora?: string };
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
  metodologia,
}: StatTileProps) {
  const semBaseline = baseline === null;

  const rotuloComTooltip = (
    <span className="flex items-center gap-1 text-xs text-muted-foreground">
      {rotulo}
      {metodologia && (
        <MethodologyTooltip titulo={rotulo} formula={metodologia.formula} ancora={metodologia.ancora} />
      )}
    </span>
  );

  // Checkpoint 10d: quando motivoIndisponivel está presente, o número em
  // destaque (text-2xl) ao lado do aviso "em construção" contradizia o
  // próprio aviso - o valor parcial passa a vir em peso visual claramente
  // secundário, e o texto de aviso é que fica proeminente.
  if (semBaseline) {
    return (
      <div className="flex-1 rounded-md border p-3">
        {rotuloComTooltip}
        <p className="mt-1 text-sm font-medium text-muted-foreground">
          {mensagemConstrucao ?? motivoIndisponivelLegivel(motivoIndisponivel)}
        </p>
        <p
          className="mt-1 text-xs text-muted-foreground"
          style={{ fontVariantNumeric: "proportional-nums" }}
        >
          valor parcial: {formatarValorCompacto(valorAtual)}
        </p>
      </div>
    );
  }

  return (
    <div className="flex-1 rounded-md border p-3">
      {rotuloComTooltip}
      <p
        className="mt-1 text-2xl font-semibold"
        style={{ fontVariantNumeric: "proportional-nums" }}
      >
        {formatarValorCompacto(valorAtual)}
      </p>
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
    </div>
  );
}
