import { NEUTRO_SALDO_ZERO, RAMPA_AZUL, RAMPA_VERMELHA } from "@/lib/palette";

type SaldoLegendProps = {
  minSaldo: number;
  maxSaldo: number;
};

export function SaldoLegend({ minSaldo, maxSaldo }: SaldoLegendProps) {
  const degraus = [...[...RAMPA_VERMELHA].reverse(), NEUTRO_SALDO_ZERO, ...RAMPA_AZUL];
  const gradiente = `linear-gradient(to right, ${degraus.join(", ")})`;

  return (
    <div className="flex items-center gap-2 text-xs text-muted-foreground">
      <span>{minSaldo <= 0 ? minSaldo : 0}</span>
      <div
        className="h-2 w-40 rounded-full border"
        style={{ background: gradiente }}
        aria-hidden
      />
      <span>+{maxSaldo >= 0 ? maxSaldo : 0}</span>
      <span className="ml-1">saldo líquido (aberturas − fechamentos)</span>
    </div>
  );
}
