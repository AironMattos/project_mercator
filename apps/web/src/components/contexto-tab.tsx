import { ContextoMercadoPanel } from "@/components/contexto-mercado-panel";
import { Headline } from "@/components/headline";
import type { ContextoImoveis } from "@/lib/api";

type ContextoTabProps = {
  contexto: ContextoImoveis;
  nomesPorTerritorio: Map<string, string>;
};

// Aba "Contexto de mercado" - BCB (UF)/QuintoAndar (cidade)/Censo (setor
// agregado por bairro), cada um com sua granularidade própria e explícita
// (checkpoint 11d/11e) - não é dado por bairro/comparável entre si.
export function ContextoTab({ contexto, nomesPorTerritorio }: ContextoTabProps) {
  return (
    <div className="flex flex-1 flex-col gap-4">
      <Headline>
        Contexto de mercado e demografia — crédito imobiliário (Paraná), aluguel (Curitiba) e
        densidade domiciliar (por bairro).
      </Headline>
      <ContextoMercadoPanel contexto={contexto} nomesPorTerritorio={nomesPorTerritorio} />
    </div>
  );
}
