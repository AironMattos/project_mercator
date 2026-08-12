type SparklineProps = {
  pontos: Array<{ valor: number }>;
  corDestaque: string;
  className?: string;
};

const LARGURA = 100;
const ALTURA = 28;
const PADDING = 5;

/**
 * Sparkline de N pontos (o produto usa 12 - ver
 * servico_indicadores.MESES_SPARKLINE no backend). Especificação de forma
 * (seção 3.4 do prompt de referência), sem exceção:
 * - linha 2px, extremidade arredondada;
 * - pontos históricos em tom neutro/de-ênfase, nunca na cor de destaque;
 * - marcador do ponto atual >=8px de diâmetro (r=4), cor de destaque;
 * - sem borda ao redor de marca nenhuma - separação por espaçamento (o
 *   anel de 2px na cor de superfície atrás do marcador atual), não contorno;
 * - nunca mais de um número por marca - o sparkline em si não rotula
 *   nenhum ponto (o valor atual já aparece no stat tile ao lado).
 */
export function Sparkline({ pontos, corDestaque, className }: SparklineProps) {
  if (pontos.length === 0) return null;

  const valores = pontos.map((p) => p.valor);
  const min = Math.min(...valores, 0);
  const max = Math.max(...valores, 0);
  const amplitude = max - min || 1;

  const coords = pontos.map((p, i) => {
    const x =
      pontos.length === 1
        ? LARGURA / 2
        : PADDING + (i / (pontos.length - 1)) * (LARGURA - 2 * PADDING);
    const y = ALTURA - PADDING - ((p.valor - min) / amplitude) * (ALTURA - 2 * PADDING);
    return { x, y };
  });

  const caminho = coords
    .map((c, i) => `${i === 0 ? "M" : "L"}${c.x.toFixed(1)},${c.y.toFixed(1)}`)
    .join(" ");
  const atual = coords[coords.length - 1];

  return (
    <svg
      viewBox={`0 0 ${LARGURA} ${ALTURA}`}
      className={className}
      role="img"
      aria-label="tendência dos últimos meses"
    >
      <path
        d={caminho}
        fill="none"
        stroke="var(--muted-foreground)"
        strokeWidth={2}
        strokeLinecap="round"
        strokeLinejoin="round"
        opacity={0.55}
      />
      {coords.slice(0, -1).map((c, i) => (
        <circle key={i} cx={c.x} cy={c.y} r={1.5} fill="var(--muted-foreground)" opacity={0.55} />
      ))}
      {/* anel na cor de superfície - separa o marcador da linha por espaçamento, não contorno */}
      <circle cx={atual.x} cy={atual.y} r={6} fill="var(--background)" />
      <circle cx={atual.x} cy={atual.y} r={4} fill={corDestaque} />
    </svg>
  );
}
