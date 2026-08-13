import { AZUL_DESTAQUE, VERMELHO_DESTAQUE } from "@/lib/palette";

export type Tendencia = "acelerando" | "desacelerando" | "estavel" | null;

// "234", não "234,0" - inteiro, sem casas decimais (seção 3.1 do prompt de
// referência: "formato compacto: 234, não 234.0").
export function formatarValorCompacto(valor: number): string {
  return new Intl.NumberFormat("pt-BR", { maximumFractionDigits: 0 }).format(Math.round(valor));
}

// "92,4%" - uma casa decimal, para os fatos de qualidade de dado (seção
// "QUALIDADE DOS DADOS" do prompt de referência usa exemplos com uma casa:
// "92,4% possuem localização geográfica válida").
export function formatarPercentual1(valor: number): string {
  return `${new Intl.NumberFormat("pt-BR", { minimumFractionDigits: 1, maximumFractionDigits: 1 }).format(valor)}%`;
}

// "1%" - taxa simples (ex.: turnover), sem o sinal +/- de formatarDeltaPct.
// Diferente de uma variação percentual, uma taxa não é "acima/abaixo de um
// baseline" - o "+" de formatarDeltaPct aqui sugeriria uma comparação que
// não existe (checkpoint 11d: turnover é (aberturas+fechamentos)/estoque,
// não uma variação de nada).
export function formatarTaxaPct(valor: number): string {
  return `${Math.round(valor * 100)}%`;
}

// "+89%" / "-12%" / "0%" - sinal sempre explícito pra positivo, nunca só o
// número nu (seção 3.1: "sinal explícito").
export function formatarDeltaPct(variacaoPct: number | null): string {
  if (variacaoPct === null) return "—";
  const pct = Math.round(variacaoPct * 100);
  return pct > 0 ? `+${pct}%` : `${pct}%`;
}

/**
 * Regra de cor do delta - a seção 3.2 do prompt de referência é explícita
 * que isso NÃO é "pra cima é sempre azul": depende de qual indicador está
 * sendo mostrado. `cimaEBom=true` pra aberturas/saldo/crescimento (acima do
 * baseline é bom -> azul). Se algum dia um tile isolado de
 * fechamento/desaparecimento for exibido, cimaEBom=false inverte (mais
 * fechamento acima do baseline é ruim -> vermelho pra cima, azul pra
 * baixo) - a mesma função cobre os dois casos, não uma regra hardcoded de
 * "positivo = azul" espalhada pelos componentes.
 */
export function corDelta(variacaoPct: number | null, cimaEBom: boolean): string {
  if (variacaoPct === null || variacaoPct === 0) return "var(--muted-foreground)";
  const acima = variacaoPct > 0;
  const bom = acima === cimaEBom;
  return bom ? AZUL_DESTAQUE : VERMELHO_DESTAQUE;
}

export function rotuloTendencia(tendencia: Tendencia): string {
  switch (tendencia) {
    case "acelerando":
      return "acelerando";
    case "desacelerando":
      return "desacelerando";
    case "estavel":
      return "estável";
    default:
      return "—";
  }
}

const MOTIVOS_LEGIVEIS: Record<string, string> = {
  historico_insuficiente: "dado em construção",
  baseline_zero: "sem histórico de comparação",
  mes_incompleto: "mês ainda sem cobertura completa",
  nao_aplicavel_sem_territorio_id: "não aplicável",
};

export function motivoIndisponivelLegivel(motivo: string | null): string {
  if (motivo === null) return "";
  return MOTIVOS_LEGIVEIS[motivo] ?? "indisponível";
}
