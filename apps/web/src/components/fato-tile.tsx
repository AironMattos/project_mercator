import { MethodologyTooltip } from "@/components/methodology-tooltip";

type FatoTileProps = {
  rotulo: string;
  valor: string;
  metodologia?: { formula: string; ancora?: string };
};

// Extraído de radius-search-panel.tsx (checkpoint 9e) para ser reaproveitado
// pelo Radar Imobiliário (checkpoint 11f) - mais simples que StatTile porque
// esses números não têm baseline/tendência (fato pontual, não uma
// comparação com histórico).
export function FatoTile({ rotulo, valor, metodologia }: FatoTileProps) {
  return (
    <div className="flex-1 rounded-md border p-3">
      <span className="flex items-center gap-1 text-xs text-muted-foreground">
        {rotulo}
        {metodologia && (
          <MethodologyTooltip titulo={rotulo} formula={metodologia.formula} ancora={metodologia.ancora} />
        )}
      </span>
      <p className="mt-1 text-2xl font-semibold" style={{ fontVariantNumeric: "proportional-nums" }}>
        {valor}
      </p>
    </div>
  );
}
