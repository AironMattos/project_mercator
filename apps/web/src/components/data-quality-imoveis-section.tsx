"use client";

import { useEffect, useState } from "react";

import { Alert, AlertDescription, AlertTitle } from "@/components/ui/alert";
import { DataQualityImoveis } from "@/components/data-quality-imoveis";
import { Skeleton } from "@/components/ui/skeleton";
import { getQualidadeDadosImoveis, type QualidadeDadosImoveis } from "@/lib/api";

type Estado =
  | { status: "carregando" }
  | { status: "erro"; mensagem: string }
  | { status: "pronto"; dados: QualidadeDadosImoveis };

// Mesmo padrão de DataQualitySection (comércio) - busca sob demanda pra
// /metodologia continuar sendo, no resto, uma página estática.
export function DataQualityImoveisSection() {
  const [estado, setEstado] = useState<Estado>({ status: "carregando" });

  useEffect(() => {
    let cancelado = false;
    getQualidadeDadosImoveis()
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
    return <Skeleton className="h-24 w-full" />;
  }

  if (estado.status === "erro") {
    return (
      <Alert variant="destructive">
        <AlertTitle>Não foi possível carregar os indicadores de qualidade</AlertTitle>
        <AlertDescription>{estado.mensagem}</AlertDescription>
      </Alert>
    );
  }

  return <DataQualityImoveis dados={estado.dados} />;
}
