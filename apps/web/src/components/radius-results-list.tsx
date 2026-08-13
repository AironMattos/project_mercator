"use client";

import { useState } from "react";

import { Button } from "@/components/ui/button";
import type { Categoria, EstabelecimentoRaio } from "@/lib/api";
import { cn } from "@/lib/utils";

type RadiusResultsListProps = {
  estabelecimentos: EstabelecimentoRaio[];
  categorias: Categoria[];
  hoveredId: string | null;
  onHover: (id: string | null) => void;
  onSelect: (id: string) => void;
};

const TAMANHO_PAGINA = 50;

function formatarDistancia(m: number): string {
  return `${Math.round(m)}m`;
}

// Alternativa em texto ao mapa (checkpoint 9g) - o coroplético e o ranking
// já tinham isso (polígono com tooltip, lista ordenada), a busca por raio
// ainda não.
export function RadiusResultsList({
  estabelecimentos,
  categorias,
  hoveredId,
  onHover,
  onSelect,
}: RadiusResultsListProps) {
  const [visiveis, setVisiveis] = useState(TAMANHO_PAGINA);
  // Reseta a paginação quando chega um resultado novo de busca - ajuste de
  // estado durante a renderização (não em useEffect), padrão recomendado
  // pelo React pra "resetar estado quando uma prop muda".
  const [ultimosEstabelecimentos, setUltimosEstabelecimentos] = useState(estabelecimentos);
  if (estabelecimentos !== ultimosEstabelecimentos) {
    setUltimosEstabelecimentos(estabelecimentos);
    setVisiveis(TAMANHO_PAGINA);
  }

  const nomePorCategoria = new Map(categorias.map((c) => [c.categoria_id, c.nome]));
  const pagina = estabelecimentos.slice(0, visiveis);
  const restantes = estabelecimentos.length - pagina.length;

  return (
    <div className="flex h-full flex-col overflow-hidden rounded-md border">
      <ul className="flex-1 divide-y overflow-y-auto" role="list">
        {pagina.map((e) => (
          <li key={e.entidadeId}>
            <button
              type="button"
              className={cn(
                "flex w-full flex-col gap-0.5 px-3 py-2 text-left transition-colors",
                hoveredId === e.entidadeId ? "bg-muted" : "hover:bg-muted/50",
              )}
              onMouseEnter={() => onHover(e.entidadeId)}
              onMouseLeave={() => onHover(null)}
              onClick={() => {
                onHover(e.entidadeId);
                onSelect(e.entidadeId);
              }}
            >
              <div className="flex items-baseline justify-between gap-2">
                <span className="truncate text-sm font-medium">{e.nome ?? "(sem nome)"}</span>
                <span
                  className="shrink-0 text-xs text-muted-foreground"
                  style={{ fontVariantNumeric: "proportional-nums" }}
                >
                  {formatarDistancia(e.distanciaM)}
                </span>
              </div>
              <span className="truncate text-xs text-muted-foreground">
                {nomePorCategoria.get(e.categoriaId ?? "") ?? "Sem categoria"}
                {e.endereco ? ` · ${e.endereco}` : ""}
              </span>
            </button>
          </li>
        ))}
      </ul>
      {restantes > 0 && (
        <div className="border-t p-2">
          <Button
            variant="outline"
            size="sm"
            className="w-full"
            onClick={() => setVisiveis((v) => v + TAMANHO_PAGINA)}
          >
            Carregar mais ({restantes} restantes)
          </Button>
        </div>
      )}
    </div>
  );
}
