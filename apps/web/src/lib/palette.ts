import type { ExpressionSpecification } from "@maplibre/maplibre-gl-style-spec";

/**
 * Codificação divergente do mapa coroplético (saldo líquido = aberturas -
 * desaparecimentos). Valores exatos da spec do produto; o braço vermelho
 * (ausente da spec, que só fixa o degrau intermediário) foi construído e
 * validado com o skill dataviz: mesma contagem de degraus do azul,
 * luminosidade monotônica em cada braço (checado com
 * validate_palette.js --ordinal), hue único, sem estouro de gamute.
 */

// Claro -> escuro. Saldo positivo (mais aberturas).
export const RAMPA_AZUL = [
  "#cde2fb",
  "#86b6ef",
  "#3987e5",
  "#2a78d6",
  "#256abf",
  "#1c5cab",
  "#184f95",
  "#104281",
  "#0d366b",
] as const;

// Claro -> escuro. Saldo negativo (mais desaparecimentos). Degrau 5 (índice
// 4) é o vermelho categórico do resto do produto (#e34948) - fixado pela
// spec como o degrau intermediário.
export const RAMPA_VERMELHA = [
  "#f6e2e0",
  "#f2bab4",
  "#f17c75",
  "#ee615c",
  "#e34948",
  "#ce3e3f",
  "#b5393a",
  "#9b3637",
  "#823234",
] as const;

export const NEUTRO_SALDO_ZERO = "#f0efec";

/**
 * Expressão de estilo MapLibre para colorir por saldo líquido: interpola
 * cada braço a partir do zero (cinza neutro) até o extremo dos dados no
 * período filtrado. minSaldo/maxSaldo vêm dos dados reais - nunca de um
 * domínio fixo, porque o volume de eventos varia mês a mês.
 */
export function expressaoCorPorSaldo(
  minSaldo: number,
  maxSaldo: number,
): ExpressionSpecification {
  const extremoNegativo = Math.min(minSaldo, -1);
  const extremoPositivo = Math.max(maxSaldo, 1);
  const n = RAMPA_AZUL.length; // 9 - mesma contagem nos dois braços

  // Vermelho, do mais escuro (extremo) até o mais claro (perto do zero) -
  // ordem ascendente de valor, já que extremoNegativo é negativo.
  const stopsNegativos = [...RAMPA_VERMELHA]
    .reverse()
    .map((cor, i) => {
      const indiceOriginal = n - 1 - i; // 8..0
      const fracao = (indiceOriginal + 1) / n; // 1 (escuro) -> 1/9 (claro)
      return [extremoNegativo * fracao, cor] as const;
    });

  // Azul, do mais claro (perto do zero) até o mais escuro (extremo).
  const stopsPositivos = RAMPA_AZUL.map((cor, indice) => {
    const fracao = (indice + 1) / n; // 1/9 (claro) -> 1 (escuro)
    return [extremoPositivo * fracao, cor] as const;
  });

  const stops: Array<readonly [number, string]> = [
    ...stopsNegativos,
    [0, NEUTRO_SALDO_ZERO],
    ...stopsPositivos,
  ];

  const expressao: unknown[] = ["interpolate", ["linear"], ["get", "saldo"]];
  for (const [valor, cor] of stops) {
    expressao.push(valor, cor);
  }
  return expressao as unknown as ExpressionSpecification;
}
