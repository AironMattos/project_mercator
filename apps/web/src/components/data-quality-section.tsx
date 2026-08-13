"use client";

import { useEffect, useState } from "react";

import { Alert, AlertDescription, AlertTitle } from "@/components/ui/alert";
import { DataQuality } from "@/components/data-quality";
import { Skeleton } from "@/components/ui/skeleton";
import { getQualidadeDados, type QualidadeDados } from "@/lib/api";

type Estado =
  | { status: "carregando" }
  | { status: "erro"; mensagem: string }
  | { status: "pronto"; dados: QualidadeDados };

// Busca GET /qualidade-dados sob demanda - separado em client component pra
// /metodologia (checkpoint 11a) poder ser, no resto, uma página estática
// (server component, sem "use client" desnecessário no texto que não muda).
export function DataQualitySection() {
  const [estado, setEstado] = useState<Estado>({ status: "carregando" });

  useEffect(() => {
    let cancelado = false;
    getQualidadeDados()
      .then((dados) => {
        if (!cancelado) setEstado({ status: "pronto", dados });
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
        <AlertTitle>Não foi possível carregar os indicadores de qualidade</AlertTitle>
        <AlertDescription>{estado.mensagem}</AlertDescription>
      </Alert>
    );
  }

  return <DataQuality dados={estado.dados} />;
}
