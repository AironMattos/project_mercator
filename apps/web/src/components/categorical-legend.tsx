type CategoricalLegendProps = {
  itens: Array<{ rotulo: string; cor: string }>;
};

// Swatches simples (checkpoint 11f, mapa de zoneamento) - lista sempre
// visível junto do mapa, mesmo princípio de "legenda sempre presente" já
// usado em SaldoLegend/SequentialLegend.
export function CategoricalLegend({ itens }: CategoricalLegendProps) {
  return (
    <div className="flex flex-wrap items-center gap-x-4 gap-y-1 text-xs text-muted-foreground">
      {itens.map((item) => (
        <span key={item.rotulo} className="flex items-center gap-1.5">
          <span
            className="h-2.5 w-2.5 shrink-0 rounded-sm border"
            style={{ backgroundColor: item.cor }}
            aria-hidden
          />
          {item.rotulo}
        </span>
      ))}
    </div>
  );
}
