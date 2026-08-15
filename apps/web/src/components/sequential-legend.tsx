import { RAMPA_AZUL } from "@/lib/palette";

type SequentialLegendProps = {
  max: number;
  /** ex.: "R$/m²" ou "alvarás aprovados" */
  rotulo: string;
  formatarMax?: (valor: number) => string;
};

// Mesmo padrão de SaldoLegend (checkpoint 7b), mas de um braço só - a
// magnitude do Radar Imobiliário (construção, valor de referência) não tem
// polo negativo, então não faz sentido reaproveitar a rampa divergente.
export function SequentialLegend({ max, rotulo, formatarMax }: SequentialLegendProps) {
  const gradiente = `linear-gradient(to right, ${RAMPA_AZUL.join(", ")})`;
  const rotuloMax = formatarMax ? formatarMax(max) : String(Math.round(max));

  return (
    <div className="flex items-center gap-2 text-xs text-muted-foreground">
      <span>0</span>
      <div className="h-2 w-40 rounded-full border" style={{ background: gradiente }} aria-hidden />
      <span>{rotuloMax}</span>
      <span className="ml-1">{rotulo}</span>
    </div>
  );
}
