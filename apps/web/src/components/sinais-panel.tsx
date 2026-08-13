"use client";

import { useEffect, useState } from "react";

import { Alert, AlertDescription, AlertTitle } from "@/components/ui/alert";
import { Skeleton } from "@/components/ui/skeleton";
import { getSinais, type Sinal } from "@/lib/api";

type Estado =
  | { status: "carregando" }
  | { status: "erro"; mensagem: string }
  | { status: "pronto"; itens: Sinal[]; criterio: string; motivoIndisponivel: string | null };

// Sinais (checkpoint 11b, seção "SINAIS E DESTAQUES" do prompt) - critério
// simples e sempre visível junto do resultado (nunca um score escondido).
// Vive junto do ranking na aba Radar, não como aba própria - é um
// complemento ao ranking, não uma quarta forma de navegar o mesmo dado.
export function SinaisPanel() {
  const [estado, setEstado] = useState<Estado>({ status: "carregando" });

  useEffect(() => {
    let cancelado = false;
    getSinais()
      .then((sinais) => {
        if (!cancelado) {
          setEstado({
            status: "pronto",
            itens: sinais.itens,
            criterio: sinais.criterio,
            motivoIndisponivel: sinais.motivoIndisponivel,
          });
        }
      })
      .catch((erro: unknown) => {
        if (!cancelado) {
          setEstado({
            status: "erro",
            mensagem: erro instanceof Error ? erro.message : "Erro desconhecido",
          });
        }
      });
    return () => {
      cancelado = true;
    };
  }, []);

  if (estado.status === "carregando") {
    return <Skeleton className="h-16 w-full" />;
  }

  if (estado.status === "erro") {
    return (
      <Alert variant="destructive">
        <AlertTitle>Não foi possível carregar os sinais</AlertTitle>
        <AlertDescription>{estado.mensagem}</AlertDescription>
      </Alert>
    );
  }

  return (
    <div className="rounded-md border p-3">
      <p className="text-xs text-muted-foreground">
        Sinais — critério: {estado.criterio}
      </p>
      {estado.itens.length === 0 ? (
        <p className="mt-1.5 text-sm text-muted-foreground">
          {estado.motivoIndisponivel === "historico_insuficiente"
            ? "Nenhum evento processado ainda para avaliar esse critério."
            : "Nenhum bairro atende esse critério no momento."}
        </p>
      ) : (
        <ul className="mt-1.5 space-y-1">
          {estado.itens.map((sinal) => (
            <li key={sinal.territorioId} className="text-sm">
              {sinal.descricao}
            </li>
          ))}
        </ul>
      )}
    </div>
  );
}
