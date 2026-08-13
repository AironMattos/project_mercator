"use client";

import { Info } from "lucide-react";
import Link from "next/link";

import { Popover, PopoverContent, PopoverTrigger } from "@/components/ui/popover";

type MethodologyTooltipProps = {
  titulo: string;
  formula: string;
  /** id da seção correspondente em /metodologia (ex.: "baseline") */
  ancora?: string;
};

// Componente do design system pedido pelo prompt de referência
// (MethodologyTooltip) - todo indicador em tela deve poder responder "como
// vocês chegaram nesse número?" sem sair da tela. Mostra a fórmula direto
// (não obriga navegar até /metodologia pra ver o essencial), com um link
// pra lá quando a explicação completa vale a pena.
export function MethodologyTooltip({ titulo, formula, ancora }: MethodologyTooltipProps) {
  return (
    <Popover>
      <PopoverTrigger
        aria-label={`Como "${titulo}" é calculado`}
        className="inline-flex h-3.5 w-3.5 shrink-0 items-center justify-center rounded-full text-muted-foreground/70 outline-none hover:text-foreground focus-visible:text-foreground"
      >
        <Info className="h-3.5 w-3.5" />
      </PopoverTrigger>
      <PopoverContent className="w-64 text-xs">
        <p className="font-medium text-foreground">{titulo}</p>
        <p className="mt-1 text-muted-foreground">{formula}</p>
        {ancora && (
          <Link
            href={`/metodologia#${ancora}`}
            className="mt-2 inline-block text-primary underline underline-offset-2"
          >
            Ver metodologia completa
          </Link>
        )}
      </PopoverContent>
    </Popover>
  );
}
