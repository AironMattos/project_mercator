import type { QualidadeDadosImoveis } from "@/lib/api";
import { formatarPercentual1, formatarValorCompacto } from "@/lib/indicadores";
import { formatarDataDMY } from "@/lib/periodo";

const NOMES_FONTE: Record<string, string> = {
  smu_alvara_construcao: "alvarás de construção (SMU)",
  smu_cvco: "CVCOs (SMU)",
  ippuc_pgv: "Planta Genérica de Valores (IPPUC)",
  geocuritiba_lote_cadastral: "lote cadastral (GeoCuritiba)",
  geocuritiba_zoneamento: "zoneamento (GeoCuritiba)",
  bcb_mercado_imobiliario: "mercado imobiliário (BCB)",
  quintoandar_indice_aluguel: "índice de aluguel (QuintoAndar)",
  ibge_censo_setor: "Censo por setor (IBGE)",
};

function formatarData(iso: string | null): string {
  if (!iso) return "nenhuma execução registrada";
  return new Date(iso).toLocaleDateString("pt-BR", { day: "2-digit", month: "2-digit", year: "numeric" });
}

// Mesmo princípio de DataQuality (comércio): fatos crus de
// GET /imoveis/qualidade-dados, sem nota nem score composto (checkpoint
// 11e, trava metodológica "Qualidade de dado como indicador objetivo").
export function DataQualityImoveis({ dados }: { dados: QualidadeDadosImoveis }) {
  return (
    <div className="space-y-4">
      <dl className="grid grid-cols-2 gap-x-6 gap-y-3 text-xs sm:grid-cols-4">
        <div>
          <dt className="text-muted-foreground">alvarás com bairro resolvido</dt>
          <dd className="mt-0.5 text-sm font-medium" style={{ fontVariantNumeric: "tabular-nums" }}>
            {formatarPercentual1(dados.alvaras.pctTerritorioResolvido)}{" "}
            <span className="font-normal text-muted-foreground">
              ({formatarValorCompacto(dados.alvaras.total)} no total)
            </span>
          </dd>
        </div>
        <div>
          <dt className="text-muted-foreground">CVCOs com bairro resolvido</dt>
          <dd className="mt-0.5 text-sm font-medium" style={{ fontVariantNumeric: "tabular-nums" }}>
            {formatarPercentual1(dados.cvcos.pctTerritorioResolvido)}{" "}
            <span className="font-normal text-muted-foreground">
              ({formatarValorCompacto(dados.cvcos.total)} no total)
            </span>
          </dd>
        </div>
        <div>
          <dt className="text-muted-foreground">lotes cadastrais sem geometria/território</dt>
          <dd className="mt-0.5 text-sm font-medium" style={{ fontVariantNumeric: "tabular-nums" }}>
            {formatarValorCompacto(dados.loteCadastral.semGeometria)} /{" "}
            {formatarValorCompacto(dados.loteCadastral.semTerritorio)}{" "}
            <span className="font-normal text-muted-foreground">
              (de {formatarValorCompacto(dados.loteCadastral.total)})
            </span>
          </dd>
        </div>
        <div>
          <dt className="text-muted-foreground">PGV — bairros cobertos</dt>
          <dd className="mt-0.5 text-sm font-medium" style={{ fontVariantNumeric: "tabular-nums" }}>
            {dados.pgvBairrosCobertos}{" "}
            <span className="font-normal text-muted-foreground">
              ({formatarValorCompacto(dados.pgvTotalRegistros)} registros, vigente desde{" "}
              {dados.pgvVigenciaInicio ? formatarDataDMY(dados.pgvVigenciaInicio) : "—"})
            </span>
          </dd>
        </div>
      </dl>

      <div>
        <p className="mb-1.5 text-xs text-muted-foreground">última atualização por fonte</p>
        <div className="overflow-x-auto rounded-md border">
          <table className="w-full text-sm">
            <tbody className="divide-y">
              {Object.entries(dados.ultimaAtualizacaoPorFonte).map(([fonte, data]) => (
                <tr key={fonte}>
                  <td className="px-3 py-1.5 text-xs text-muted-foreground">
                    {NOMES_FONTE[fonte] ?? fonte}
                  </td>
                  <td className="px-3 py-1.5 text-right text-xs">{formatarData(data)}</td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      </div>
    </div>
  );
}
