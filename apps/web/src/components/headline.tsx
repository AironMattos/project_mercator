import { cn } from "@/lib/utils";

type HeadlineProps = {
  children: React.ReactNode;
  className?: string;
  /** "lg" para telas cheias (mapa/ranking/busca), "md" pro painel lateral
   * de detalhe, mais estreito. */
  size?: "md" | "lg";
};

// A frase-manchete (checkpoint 10b) - elemento mais proeminente de cada
// tela principal, sempre antes do mapa/gráfico que a sustenta (seção 1 do
// checkpoint 10: "a frase vem antes do gráfico, sempre").
export function Headline({ children, className, size = "lg" }: HeadlineProps) {
  return (
    <p
      className={cn(
        "text-balance font-heading leading-snug font-medium text-foreground",
        size === "lg" ? "text-2xl sm:text-3xl" : "text-xl sm:text-2xl",
        className,
      )}
    >
      {children}
    </p>
  );
}
