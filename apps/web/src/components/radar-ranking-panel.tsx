"use client";

import { useState } from "react";

import { CategoryRankingList } from "@/components/category-ranking-list";
import { RankingList } from "@/components/ranking-list";
import { SinaisPanel } from "@/components/sinais-panel";
import { cn } from "@/lib/utils";

type Escopo = "bairros" | "categorias";
type Ordem = "desc" | "asc";

type Props = {
  categoriaId?: string;
  onSelecionarTerritorio: (territorioId: string, nome: string) => void;
  onSelecionarCategoria: (categoriaId: string) => void;
};

function Chip({
  ativo,
  onClick,
  children,
}: {
  ativo: boolean;
  onClick: () => void;
  children: React.ReactNode;
}) {
  return (
    <button
      type="button"
      onClick={onClick}
      className={cn(
        "rounded-full border px-3 py-1 text-xs font-medium transition-colors",
        ativo
          ? "border-primary bg-primary text-primary-foreground"
          : "border-border bg-background text-muted-foreground hover:bg-muted",
      )}
    >
      {children}
    </button>
  );
}

// Painel completo da aba "Ranking de crescimento" (checkpoint 11b) - duas
// dimensões independentes de filtro (escopo: bairros vs. categorias; ordem:
// crescimento vs. retração), nunca misturadas numa única lista - seção
// "RADAR" do prompt de referência é explícita sobre não combinar volume
// absoluto/crescimento percentual/retração numa métrica só.
export function RadarRankingPanel({ categoriaId, onSelecionarTerritorio, onSelecionarCategoria }: Props) {
  const [escopo, setEscopo] = useState<Escopo>("bairros");
  const [ordem, setOrdem] = useState<Ordem>("desc");

  return (
    <div className="flex flex-1 flex-col gap-3">
      <div className="flex flex-wrap items-center gap-4">
        <div className="flex items-center gap-1.5">
          <Chip ativo={escopo === "bairros"} onClick={() => setEscopo("bairros")}>
            Bairros
          </Chip>
          <Chip ativo={escopo === "categorias"} onClick={() => setEscopo("categorias")}>
            Categorias
          </Chip>
        </div>
        <div className="flex items-center gap-1.5">
          <Chip ativo={ordem === "desc"} onClick={() => setOrdem("desc")}>
            Maiores crescimentos
          </Chip>
          <Chip ativo={ordem === "asc"} onClick={() => setOrdem("asc")}>
            Maiores retrações
          </Chip>
        </div>
      </div>

      {escopo === "bairros" ? (
        <RankingList categoriaId={categoriaId} ordem={ordem} onSelecionarTerritorio={onSelecionarTerritorio} />
      ) : (
        <CategoryRankingList ordem={ordem} onSelecionarCategoria={onSelecionarCategoria} />
      )}

      <SinaisPanel />
    </div>
  );
}
