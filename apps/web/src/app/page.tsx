import Link from "next/link";

import { buttonVariants } from "@/components/ui/button";

// Tela de entrada (checkpoint 10c) - quem abre o produto direto não caía
// mais num mapa sem contexto nenhum. Não é elaborada de propósito (a spec
// só pede que exista): nome, uma frase de posicionamento e um CTA.
export default function Home() {
  return (
    <main className="flex flex-1 flex-col items-center justify-center gap-8 px-6 py-16 text-center">
      <div className="max-w-xl space-y-4">
        <p className="text-xs font-semibold tracking-wider text-primary uppercase">Mercator</p>
        <h1 className="font-heading text-4xl leading-tight font-semibold sm:text-5xl">
          Radar de Comércio
        </h1>
        <p className="text-balance text-lg text-muted-foreground">
          Mapeamento mês a mês de abertura e fechamento de comércio em Curitiba, bairro a
          bairro — pra quem precisa decidir com dado real: corretores, incorporadoras, fundos
          e gestão pública.
        </p>
      </div>
      <Link
        href="/radar"
        className={buttonVariants({ size: "lg", className: "px-8 text-base" })}
      >
        Ver o mapa de Curitiba
      </Link>
    </main>
  );
}
