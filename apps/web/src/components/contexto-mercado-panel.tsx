import { MethodologyTooltip } from "@/components/methodology-tooltip";
import type { ContextoImoveis } from "@/lib/api";
import { formatarValorCompacto } from "@/lib/indicadores";
import { formatarMesAno } from "@/lib/periodo";

function formatarNumero(valor: number, casas = 0): string {
  return new Intl.NumberFormat("pt-BR", {
    minimumFractionDigits: casas,
    maximumFractionDigits: casas,
  }).format(valor);
}

function formatarVariacao(valor: number | null): string {
  if (valor === null) return "—";
  const pct = Math.round(valor * 1000) / 10;
  return pct > 0 ? `+${pct}%` : `${pct}%`;
}

const NOMES_CATEGORIA_BCB: Record<string, string> = {
  valor: "valores (R$)",
  area: "área financiada (m²)",
  contagem: "contagem de operações",
};

// Nomes legíveis das 14 séries reais do BCB (checkpoint 11d) - os ids
// (ex.: "imoveis_dormitorio_1") vêm da Metodologia.pdf oficial do BCB, não
// são autoexplicativos pra quem não trabalha com o dado bruto.
const NOMES_INDICADOR_BCB: Record<string, string> = {
  imoveis_area_privativa: "área privativa (mediana)",
  imoveis_area_total: "área total (mediana)",
  imoveis_dormitorio_1: "1 dormitório",
  imoveis_dormitorio_2: "2 dormitórios",
  imoveis_dormitorio_3: "3 dormitórios",
  imoveis_dormitorio_4_mais: "4+ dormitórios",
  imoveis_garantia_alienacao_fiduciaria: "garantia: alienação fiduciária",
  imoveis_garantia_hipoteca: "garantia: hipoteca",
  imoveis_implantacao_condominio: "implantação: condomínio",
  imoveis_implantacao_isolado: "implantação: isolado",
  imoveis_tipo_apartamento: "tipo: apartamento",
  imoveis_tipo_casa: "tipo: casa",
  imoveis_valor_avaliacao: "valor de avaliação (mediana)",
  imoveis_valor_compra: "valor de compra (mediana)",
};

function formatarLeituraBcb(valor: number, unidade: string, casas: number): string {
  const numero = formatarNumero(valor, casas);
  return unidade === "R$" ? `R$ ${numero}` : `${numero} ${unidade}`;
}

const NOMES_SEGMENTO_QUINTOANDAR: Record<string, string> = {
  cidade_toda: "cidade toda",
  "1_dormitorio": "1 dormitório",
  "2_dormitorios": "2 dormitórios",
  "3_dormitorios": "3 dormitórios",
};

type ContextoMercadoPanelProps = {
  contexto: ContextoImoveis;
  nomesPorTerritorio: Map<string, string>;
};

// Painel do design system pedido pelo prompt de referência do Radar
// Imobiliário - cada fonte de contexto (BCB, QuintoAndar, Censo) com sua
// própria granularidade explícita no cabeçalho da seção (checkpoint 11d/
// 11e: "granularidade declarada em cada seção da própria resposta" - nunca
// um número de UF ou cidade apresentado como se fosse por bairro).
export function ContextoMercadoPanel({ contexto, nomesPorTerritorio }: ContextoMercadoPanelProps) {
  const bcbPorCategoria = new Map<string, typeof contexto.bcb.indicadores>();
  for (const indicador of contexto.bcb.indicadores) {
    const lista = bcbPorCategoria.get(indicador.categoria) ?? [];
    lista.push(indicador);
    bcbPorCategoria.set(indicador.categoria, lista);
  }

  const censoOrdenado = [...contexto.censo.bairros].sort(
    (a, b) => (b.densidadeDomiciliosKm2 ?? 0) - (a.densidadeDomiciliosKm2 ?? 0),
  );

  return (
    <div className="flex flex-col gap-8">
      <section>
        <div className="flex items-center gap-1.5">
          <h2 className="font-heading text-lg font-medium">Crédito imobiliário — Banco Central</h2>
          <MethodologyTooltip
            titulo="contexto BCB"
            formula="Séries do Sistema de Financiamento Imobiliário (SFI/SCR), granularidade estadual — nunca específico de Curitiba."
            ancora="imoveis-contexto"
          />
        </div>
        <p className="mt-1 text-xs text-muted-foreground">
          Granularidade: <strong>estado do Paraná</strong> ({contexto.bcb.uf}) — não é dado
          específico de Curitiba.
          {contexto.bcb.periodoReferencia && ` Período de referência: ${formatarMesAno(contexto.bcb.periodoReferencia)}.`}
        </p>
        <div className="mt-3 space-y-4">
          {[...bcbPorCategoria.entries()].map(([categoria, indicadores]) => (
            <div key={categoria}>
              <p className="mb-1 text-xs font-medium text-muted-foreground">
                {NOMES_CATEGORIA_BCB[categoria] ?? categoria}
              </p>
              <div className="overflow-x-auto rounded-md border">
                <table className="w-full text-sm">
                  <tbody className="divide-y">
                    {indicadores.map((i) => (
                      <tr key={i.indicador}>
                        <td className="px-3 py-1.5 text-xs text-muted-foreground">
                          {NOMES_INDICADOR_BCB[i.indicador] ?? i.indicador}
                        </td>
                        <td
                          className="px-3 py-1.5 text-right text-sm font-medium"
                          style={{ fontVariantNumeric: "tabular-nums" }}
                        >
                          {formatarLeituraBcb(i.leitura, i.unidade, categoria === "contagem" ? 0 : 2)}
                        </td>
                        <td className="px-3 py-1.5 text-right text-xs text-muted-foreground">
                          {i.tipoValor ?? "—"}
                        </td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>
            </div>
          ))}
        </div>
      </section>

      <section>
        <div className="flex items-center gap-1.5">
          <h2 className="font-heading text-lg font-medium">Aluguel — índice QuintoAndar</h2>
          <MethodologyTooltip
            titulo="contexto QuintoAndar"
            formula="Índice mensal de preço de aluguel por segmento, misturando anúncios e contratos fechados — não é uma grandeza de compra (nunca rotulado com tipo_valor)."
            ancora="imoveis-contexto"
          />
        </div>
        <p className="mt-1 text-xs text-muted-foreground">
          Granularidade: <strong>cidade</strong> ({contexto.quintoandar.cidade}).
          {contexto.quintoandar.periodoReferencia &&
            ` Período de referência: ${formatarMesAno(contexto.quintoandar.periodoReferencia)}.`}
        </p>
        <div className="mt-3 overflow-x-auto rounded-md border">
          <table className="w-full text-sm">
            <thead>
              <tr className="border-b bg-muted/30 text-xs text-muted-foreground">
                <th className="px-3 py-2 text-left font-medium">segmento</th>
                <th className="px-3 py-2 text-right font-medium">R$/m²/mês</th>
                <th className="px-3 py-2 text-right font-medium">var. mensal</th>
                <th className="px-3 py-2 text-right font-medium">var. 12m</th>
              </tr>
            </thead>
            <tbody className="divide-y">
              {contexto.quintoandar.segmentos.map((s) => (
                <tr key={s.segmento}>
                  <td className="px-3 py-1.5 text-xs">
                    {NOMES_SEGMENTO_QUINTOANDAR[s.segmento] ?? s.segmento}
                  </td>
                  <td
                    className="px-3 py-1.5 text-right text-sm font-medium"
                    style={{ fontVariantNumeric: "tabular-nums" }}
                  >
                    R$ {formatarNumero(s.aluguelM2, 2)}
                  </td>
                  <td className="px-3 py-1.5 text-right text-xs text-muted-foreground">
                    {formatarVariacao(s.variacaoMensal)}
                  </td>
                  <td className="px-3 py-1.5 text-right text-xs text-muted-foreground">
                    {formatarVariacao(s.variacao12m)}
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      </section>

      <section>
        <div className="flex items-center gap-1.5">
          <h2 className="font-heading text-lg font-medium">Demografia — Censo 2022</h2>
          <MethodologyTooltip
            titulo="contexto Censo"
            formula="Setores censitários do Censo 2022 somados por bairro — não é um levantamento independente por bairro."
            ancora="imoveis-contexto"
          />
        </div>
        <p className="mt-1 text-xs text-muted-foreground">
          Granularidade: <strong>setor censitário agregado por bairro</strong> — ano de
          referência {contexto.censo.anoReferencia}.
        </p>
        <div className="mt-3 max-h-96 overflow-y-auto rounded-md border">
          <table className="w-full text-sm">
            <thead className="sticky top-0 bg-background">
              <tr className="border-b bg-muted/30 text-xs text-muted-foreground">
                <th className="px-3 py-2 text-left font-medium">bairro</th>
                <th className="px-3 py-2 text-right font-medium">população</th>
                <th className="px-3 py-2 text-right font-medium">domicílios</th>
                <th className="px-3 py-2 text-right font-medium">densidade dom./km²</th>
                <th className="px-3 py-2 text-right font-medium">setores</th>
              </tr>
            </thead>
            <tbody className="divide-y">
              {censoOrdenado.map((b) => (
                <tr key={b.territorioId}>
                  <td className="px-3 py-1.5 text-xs">
                    {nomesPorTerritorio.get(b.territorioId) ?? b.territorioId}
                  </td>
                  <td className="px-3 py-1.5 text-right text-xs" style={{ fontVariantNumeric: "tabular-nums" }}>
                    {formatarValorCompacto(b.populacaoTotal)}
                  </td>
                  <td className="px-3 py-1.5 text-right text-xs" style={{ fontVariantNumeric: "tabular-nums" }}>
                    {formatarValorCompacto(b.domiciliosTotal)}
                  </td>
                  <td className="px-3 py-1.5 text-right text-xs font-medium" style={{ fontVariantNumeric: "tabular-nums" }}>
                    {b.densidadeDomiciliosKm2 !== null ? formatarNumero(b.densidadeDomiciliosKm2, 0) : "—"}
                  </td>
                  <td className="px-3 py-1.5 text-right text-xs text-muted-foreground" style={{ fontVariantNumeric: "tabular-nums" }}>
                    {b.setoresAgregados}
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      </section>
    </div>
  );
}
