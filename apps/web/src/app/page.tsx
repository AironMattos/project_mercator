import Link from "next/link";

import { buttonVariants } from "@/components/ui/button";

// Tela de entrada (checkpoint 10c) - quem abre o produto direto não caía
// mais num mapa sem contexto nenhum. Não é elaborada de propósito (a spec
// só pede que exista): nome, uma frase de posicionamento e um CTA por
// produto. Segundo CTA (checkpoint 11f) adicionado quando o Radar
// Imobiliário passou a ter frontend próprio, terceiro (checkpoint 12i)
// quando o Radar de Anúncios ganhou o dele - os três produtos leem o
// mesmo substrato de eventos, mas são experiências distintas.
export default function Home() {
  return (
    <main className="flex flex-1 flex-col items-center justify-center gap-8 px-6 py-16 text-center">
      <div className="max-w-xl space-y-4">
        <p className="text-xs font-semibold tracking-wider text-primary uppercase">Mercator</p>
        <h1 className="font-heading text-4xl leading-tight font-semibold sm:text-5xl">
          Radar territorial de Curitiba
        </h1>
        <p className="text-balance text-lg text-muted-foreground">
          Mapeamento mês a mês do que muda em Curitiba, bairro a bairro — pra quem precisa
          decidir com dado real: corretores, incorporadoras, fundos e gestão pública.
        </p>
      </div>
      <div className="flex flex-col gap-3 sm:flex-row">
        <Link
          href="/radar"
          className={buttonVariants({ size: "lg", className: "px-8 text-base" })}
        >
          Radar de Comércio
        </Link>
        <Link
          href="/imoveis"
          className={buttonVariants({ variant: "secondary", size: "lg", className: "px-8 text-base" })}
        >
          Radar Imobiliário
        </Link>
        <Link
          href="/anuncios"
          className={buttonVariants({ variant: "secondary", size: "lg", className: "px-8 text-base" })}
        >
          Radar de Anúncios
        </Link>
      </div>
    </main>
  );
}
