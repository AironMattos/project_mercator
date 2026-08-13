"use client";

import { useState } from "react";

import { Alert, AlertDescription, AlertTitle } from "@/components/ui/alert";
import { Button } from "@/components/ui/button";
import { Headline } from "@/components/headline";
import { Input } from "@/components/ui/input";
import { RadiusMap } from "@/components/radius-map";
import { RadiusResultsList } from "@/components/radius-results-list";
import { Skeleton } from "@/components/ui/skeleton";
import { BuscaRaioError, getBuscaRaio, type BuscaRaio, type Categoria } from "@/lib/api";
import { formatarRaioM, mancheteBuscaRaio } from "@/lib/manchete";
import { cn } from "@/lib/utils";

type RadiusSearchPanelProps = {
  categoriaId?: string;
  nomeCategoria?: string;
  categorias: Categoria[];
};

const PRESETS_RAIO = [
  { label: "250m", valor: 250 },
  { label: "500m", valor: 500 },
  { label: "1km", valor: 1000 },
  { label: "2km", valor: 2000 },
] as const;

type Estado =
  | { status: "ocioso" }
  | { status: "carregando" }
  | { status: "erro"; mensagem: string }
  | { status: "pronto"; resultado: BuscaRaio };

export function RadiusSearchPanel({ categoriaId, nomeCategoria, categorias }: RadiusSearchPanelProps) {
  const [endereco, setEndereco] = useState("");
  const [raioM, setRaioM] = useState<number>(500);
  const [estado, setEstado] = useState<Estado>({ status: "ocioso" });
  const [hoveredId, setHoveredId] = useState<string | null>(null);
  const [selectedId, setSelectedId] = useState<string | null>(null);
  const [selectedNonce, setSelectedNonce] = useState(0);

  function buscar() {
    const texto = endereco.trim();
    if (!texto) return;

    setEstado({ status: "carregando" });
    setHoveredId(null);
    setSelectedId(null);
    getBuscaRaio(texto, raioM, categoriaId)
      .then((resultado) => setEstado({ status: "pronto", resultado }))
      .catch((erro: unknown) => {
        const mensagem =
          erro instanceof BuscaRaioError
            ? erro.message
            : erro instanceof Error
              ? erro.message
              : "Erro desconhecido";
        setEstado({ status: "erro", mensagem });
      });
  }

  return (
    <div className="flex flex-1 flex-col gap-3">
      <form
        className="flex flex-wrap items-center gap-2"
        onSubmit={(e) => {
          e.preventDefault();
          buscar();
        }}
      >
        <Input
          value={endereco}
          onChange={(e) => setEndereco(e.target.value)}
          placeholder="Endereço (ex.: R. XV de Novembro, 500)"
          className="w-80"
        />
        <div className="flex items-center gap-1">
          {PRESETS_RAIO.map((preset) => (
            <button
              key={preset.valor}
              type="button"
              onClick={() => setRaioM(preset.valor)}
              className={cn(
                "rounded-full border px-3 py-1 text-xs font-medium transition-colors",
                raioM === preset.valor
                  ? "border-primary bg-primary text-primary-foreground"
                  : "border-border bg-background text-muted-foreground hover:bg-muted",
              )}
            >
              {preset.label}
            </button>
          ))}
        </div>
        <Button type="submit" disabled={!endereco.trim() || estado.status === "carregando"}>
          Buscar
        </Button>
      </form>

      {estado.status === "ocioso" && (
        <Alert>
          <AlertTitle>Busque um endereço</AlertTitle>
          <AlertDescription>
            Digite um endereço em Curitiba e escolha um raio para ver os estabelecimentos
            {nomeCategoria ? ` de ${nomeCategoria}` : ""} próximos.
          </AlertDescription>
        </Alert>
      )}

      {estado.status === "carregando" && (
        <div className="space-y-3" role="status" aria-label="Buscando">
          <Skeleton className="h-8 w-64" />
          <Skeleton className="h-96 w-full" />
        </div>
      )}

      {estado.status === "erro" && (
        <Alert variant="destructive">
          <AlertTitle>Não foi possível buscar</AlertTitle>
          <AlertDescription>{estado.mensagem}</AlertDescription>
        </Alert>
      )}

      {estado.status === "pronto" && (
        <div className="flex flex-1 flex-col gap-3">
          {estado.resultado.total > 0 && (
            <Headline>{mancheteBuscaRaio(estado.resultado, categorias, nomeCategoria)}</Headline>
          )}

          <div className="flex flex-wrap items-end gap-3">
            <div className="rounded-md border p-3">
              <p className="text-xs text-muted-foreground">
                Estabelecimentos{nomeCategoria ? ` de ${nomeCategoria}` : ""} num raio de{" "}
                {formatarRaioM(estado.resultado.raioM)}
              </p>
              <p
                className="mt-1 text-2xl font-semibold"
                style={{ fontVariantNumeric: "proportional-nums" }}
              >
                {estado.resultado.total}
              </p>
            </div>
            {estado.resultado.excluidosBaixaConfianca > 0 && (
              <p className="text-xs text-muted-foreground">
                + {estado.resultado.excluidosBaixaConfianca} endereço
                {estado.resultado.excluidosBaixaConfianca > 1 ? "s" : ""} próximo
                {estado.resultado.excluidosBaixaConfianca > 1 ? "s" : ""} com localização pouco
                confiável, não contado{estado.resultado.excluidosBaixaConfianca > 1 ? "s" : ""}
              </p>
            )}
          </div>

          {estado.resultado.total === 0 && (
            <Alert>
              <AlertTitle>Nenhum estabelecimento encontrado</AlertTitle>
              <AlertDescription>
                Não há estabelecimentos{nomeCategoria ? ` de ${nomeCategoria}` : ""} num raio de{" "}
                {formatarRaioM(estado.resultado.raioM)} de &ldquo;{estado.resultado.enderecoBuscado}
                &rdquo;.
                {estado.resultado.excluidosBaixaConfianca > 0 &&
                  " Há endereços próximos com localização pouco confiável, não contados acima."}
              </AlertDescription>
            </Alert>
          )}
          {estado.resultado.total > 0 && (
            <div className="flex min-h-[480px] flex-1 flex-col gap-3 lg:flex-row">
              <div className="flex-[2] overflow-hidden rounded-md border">
                <RadiusMap
                  resultado={estado.resultado}
                  hoveredId={hoveredId}
                  onHoverMarker={setHoveredId}
                  selectedId={selectedId}
                  selectedNonce={selectedNonce}
                />
              </div>
              <div className="flex-1 lg:max-w-sm">
                <RadiusResultsList
                  estabelecimentos={estado.resultado.estabelecimentos}
                  categorias={categorias}
                  hoveredId={hoveredId}
                  onHover={setHoveredId}
                  onSelect={(id) => {
                    setSelectedId(id);
                    setSelectedNonce((n) => n + 1);
                  }}
                />
              </div>
            </div>
          )}
        </div>
      )}
    </div>
  );
}
