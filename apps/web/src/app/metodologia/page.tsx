import Link from "next/link";

import { DataQualityImoveisSection } from "@/components/data-quality-imoveis-section";
import { DataQualitySection } from "@/components/data-quality-section";

type Secao = {
  id: string;
  titulo: string;
  corpo: React.ReactNode;
};

const SECOES: Secao[] = [
  {
    id: "fonte",
    titulo: "Fonte dos dados",
    corpo: (
      <p>
        Alvarás de funcionamento da Prefeitura de Curitiba (Secretaria Municipal de Finanças),
        publicados mensalmente como base aberta. Cada arquivo mensal é um snapshot do estado
        consolidado até o fim do mês anterior ao rótulo do arquivo — o processado em
        &ldquo;2026-08-01&rdquo;, por exemplo, reflete o que era conhecido até 31 de julho.
      </p>
    ),
  },
  {
    id: "cobertura",
    titulo: "Cobertura temporal",
    corpo: (
      <p>
        Um evento (abertura, fechamento, mudança de categoria) só existe quando dois snapshots
        mensais consecutivos já foram processados e comparados — a data exata de cobertura
        aparece em toda tela que usa essa comparação, nunca é implícita.
      </p>
    ),
  },
  {
    id: "aberturas",
    titulo: "Definição de abertura",
    corpo: (
      <>
        <p>
          Duas fontes distintas, usadas em telas diferentes por propósitos diferentes — os dois
          números podem divergir para o mesmo bairro/mês, isso é esperado:
        </p>
        <ul className="mt-2 list-disc space-y-1 pl-5">
          <li>
            <strong>Por evento de detecção</strong> (mapa, saldo): um estabelecimento aparece num
            snapshot sem estar no anterior. Confiança <em>alta</em> quando a data de início de
            atividade confirma que a abertura caiu dentro do período; <em>baixa</em> quando o
            estabelecimento só é visto pela primeira vez, sem essa confirmação.
          </li>
          <li>
            <strong>Por data de início de atividade</strong> (baseline, tendência, ranking): usa o
            campo de início de atividade declarado no próprio alvará, que tem profundidade real de
            anos — não depende de dois snapshots já terem sido comparados.
          </li>
        </ul>
      </>
    ),
  },
  {
    id: "fechamentos",
    titulo: "Definição de fechamento",
    corpo: (
      <p>
        Um estabelecimento presente num snapshot e ausente no seguinte. Só existe a partir do
        segundo par de snapshots processado — com histórico curto, o produto mostra
        explicitamente &ldquo;dado em construção&rdquo; em vez de um zero que pareceria real.
      </p>
    ),
  },
  {
    id: "saldo",
    titulo: "Saldo líquido",
    corpo: <p className="font-mono text-sm">saldo = aberturas − fechamentos</p>,
  },
  {
    id: "baseline",
    titulo: "Baseline e crescimento",
    corpo: (
      <>
        <p>
          <strong>Baseline</strong>: média móvel dos 24 meses anteriores ao mês de referência (o
          mês corrente nunca entra na própria média). Exige pelo menos 3 meses distintos de
          histórico dentro da janela — abaixo disso, o indicador aparece como
          &ldquo;dado em construção&rdquo;, nunca um número calculado sobre 1–2 pontos.
        </p>
        <p className="mt-2 font-mono text-sm">variação % = (valor atual − baseline) / baseline</p>
        <p className="mt-2">
          Exemplo: 582 aberturas no mês atual contra uma média de 308 nos 24 meses anteriores →
          (582 − 308) / 308 = +89%.
        </p>
      </>
    ),
  },
  {
    id: "tendencia",
    titulo: "Tendência",
    corpo: (
      <p>
        Compara a média dos últimos 3 meses fechados com a média dos 3 meses imediatamente
        anteriores a esses — mede momentum recente, não o mesmo que o baseline de 24 meses (que
        mede nível normal). Diferença acima de +10% → <em>acelerando</em>; abaixo de −10% →
        <em> desacelerando</em>; entre os dois → <em>estável</em>.
      </p>
    ),
  },
  {
    id: "participacao",
    titulo: "Participação por categoria",
    corpo: (
      <>
        <p className="font-mono text-sm">participação = (estabelecimentos da categoria / total) × 100</p>
        <p className="mt-2">
          Exemplo: 120 estabelecimentos de alimentação em 500 estabelecimentos totais → 24%.
        </p>
      </>
    ),
  },
  {
    id: "densidade",
    titulo: "Densidade comercial",
    corpo: (
      <p className="font-mono text-sm">densidade = estabelecimentos ativos / área (km²)</p>
    ),
  },
  {
    id: "turnover",
    titulo: "Turnover",
    corpo: (
      <>
        <p className="font-mono text-sm">turnover = (aberturas + fechamentos) / estoque</p>
        <p className="mt-2">
          &ldquo;Estoque&rdquo; é definido como o número de estabelecimentos com alvará
          identificado no snapshot mais recente processado — não um censo populacional
          independente, é o mesmo dado de origem usado em todo o resto do produto.
        </p>
      </>
    ),
  },
  {
    id: "geocodificacao",
    titulo: "Metodologia de geocodificação",
    corpo: (
      <>
        <p>
          Cada estabelecimento é localizado em duas etapas: primeiro por número de endereço exato
          (geocodebr/CNEFE-IBGE, base oficial do IBGE) — quando o endereço resolve com essa
          precisão, a localização recebe confiança <strong>alta</strong> direto. O restante entra
          numa segunda passagem contra um serviço de geocodificação por nome de rua (Nominatim); se
          as duas fontes concordam (até 150m de distância entre si), a confiança sobe para
          <strong> alta</strong>; entre 150m e 1km, <strong>média</strong>; acima de 1km, ou quando
          só uma fonte resolveu, <strong>baixa</strong>.
        </p>
        <p className="mt-2">
          Localizações de confiança <em>baixa</em> não entram em nenhuma contagem territorial ou
          busca por raio — aparecem separadamente, nunca escondidas silenciosamente.
        </p>
      </>
    ),
  },
  {
    id: "limitacoes",
    titulo: "Limitações conhecidas",
    corpo: (
      <ul className="list-disc space-y-1.5 pl-5">
        <li>
          A base cobre apenas os snapshots mensais já processados — eventos comparativos
          (abertura/fechamento por detecção, saldo) têm profundidade real curta mesmo quando o
          início de atividade declarado no alvará cobre anos.
        </li>
        <li>
          Cerca de 6% das observações não têm bairro resolvido (variação de grafia na fonte
          bruta, ex. &ldquo;CIC&rdquo; vs. &ldquo;Cidade Industrial de Curitiba&rdquo;).
        </li>
        <li>
          Cerca de 34% dos códigos de atividade econômica (CNAE) não são normalizáveis para uma
          categoria do catálogo — ficam marcados como &ldquo;sem categoria&rdquo;, não descartados.
        </li>
        <li>
          Concentração por rua/corredor dentro de um bairro não é mostrada: o endereço bruto da
          fonte não é normalizado (variações de grafia da mesma rua apareceriam como corredores
          diferentes), então essa quebra foi deliberadamente deixada de fora até esse dado ser
          tratado.
        </li>
      </ul>
    ),
  },
];

// Seções do Radar Imobiliário (checkpoint 11f) - âncoras prefixadas
// "imoveis-" pra não colidir com as seções do Radar de Comércio acima
// (ex.: "valor-referencia" evitaria confusão, mas duas seções na mesma
// página com o mesmo id quebrariam a navegação por âncora).
const SECOES_IMOVEIS: Secao[] = [
  {
    id: "imoveis-alvara-cvco",
    titulo: "Alvará de construção x CVCO",
    corpo: (
      <>
        <p>
          Duas fontes com significados diferentes, sempre em campos separados — nunca somadas
          numa única &ldquo;atividade construtiva&rdquo;:
        </p>
        <ul className="mt-2 list-disc space-y-1 pl-5">
          <li>
            <strong>Alvará aprovado</strong>: o empreendimento foi licenciado — &ldquo;vai
            mudar&rdquo;. Área licenciada é a metragem construída autorizada.
          </li>
          <li>
            <strong>CVCO concluído</strong>: a obra foi vistoriada e concluída — &ldquo;já
            mudou&rdquo;. Área concluída é a metragem efetivamente entregue.
          </li>
        </ul>
      </>
    ),
  },
  {
    id: "imoveis-defasagem",
    titulo: "Defasagem alvará → CVCO",
    corpo: (
      <>
        <p className="font-mono text-sm">
          defasagem = mediana, em dias, entre a aprovação do alvará e a conclusão do CVCO do
          mesmo empreendimento
        </p>
        <p className="mt-2">
          Calculada cruzando os dois eventos pela mesma entidade (mesmo Número Alvará) — exige
          ao menos 3 pares observados no bairro; abaixo disso, aparece como &ldquo;dado em
          construção&rdquo;, nunca uma mediana sobre 1–2 pontos.
        </p>
      </>
    ),
  },
  {
    id: "imoveis-valor-referencia",
    titulo: "Valor de referência (PGV)",
    corpo: (
      <>
        <p>
          Mediana do valor unitário de terreno (VUKT, R$/m²) das microrregiões da Planta
          Genérica de Valores (IPPUC) dentro de cada bairro.
        </p>
        <p className="mt-2">
          É a referência oficial de tributação, <strong>não</strong> um preço de mercado nem de
          anúncio — e não é série temporal: a PGV é revisada esporadicamente, não mês a mês, por
          isso não tem baseline nem variação %, só nível e data de vigência.
        </p>
      </>
    ),
  },
  {
    id: "imoveis-zoneamento",
    titulo: "Zoneamento",
    corpo: (
      <p>
        Camada estática de parâmetros construtivos por polígono (Lei 15.511/2019, GeoCuritiba) —
        reflete a versão mais recente publicada, sem histórico de revisões anteriores. O mapa
        mostra cor própria só para os 3 grupos de zona mais frequentes (limite de contraste
        confiável entre cores para leitores com daltonismo); os demais entram em
        &ldquo;outros&rdquo;, visível na legenda — o nome completo de cada zona aparece ao passar
        o mouse.
      </p>
    ),
  },
  {
    id: "imoveis-contexto",
    titulo: "Contexto de mercado e demografia",
    corpo: (
      <ul className="list-disc space-y-1.5 pl-5">
        <li>
          <strong>Crédito imobiliário (Banco Central)</strong>: granularidade de estado (Paraná),
          nunca específico de Curitiba — inclui valores de compra/avaliação (financiamento via
          SCR), área financiada e contagem de operações, sempre em campos separados.
        </li>
        <li>
          <strong>Índice de aluguel (QuintoAndar)</strong>: granularidade de cidade, mistura
          anúncios e contratos fechados — não é uma das quatro grandezas de compra, por isso
          nunca rotulado com um &ldquo;tipo de valor&rdquo;.
        </li>
        <li>
          <strong>Censo 2022 (IBGE)</strong>: setores censitários somados por bairro — não é um
          levantamento independente por bairro, é a mesma malha de setores agregada.
        </li>
      </ul>
    ),
  },
];

export default function MetodologiaPage() {
  return (
    <main className="mx-auto w-full max-w-3xl flex-1 px-6 py-10">
      <div className="mb-8 flex items-center justify-between gap-4">
        <div>
          <p className="text-xs font-semibold tracking-wider text-primary uppercase">Mercator</p>
          <h1 className="font-heading text-3xl leading-tight font-semibold">Metodologia</h1>
        </div>
        <div className="flex items-center gap-4">
          <Link href="/radar" className="text-sm text-muted-foreground underline underline-offset-2">
            Radar de Comércio
          </Link>
          <Link href="/imoveis" className="text-sm text-muted-foreground underline underline-offset-2">
            Radar Imobiliário
          </Link>
        </div>
      </div>

      <p className="text-balance text-muted-foreground">
        Toda métrica exibida no Mercator é calculada a partir de dado observável, com fórmula
        simples e reproduzível — nenhum índice ou score composto. Esta página documenta, seção a
        seção, como cada número em tela foi calculado.
      </p>

      <section className="mt-8 rounded-md border p-4">
        <h2 className="font-heading text-lg font-medium">Qualidade dos dados — Radar de Comércio</h2>
        <p className="mt-1 text-xs text-muted-foreground">
          Fatos objetivos sobre a base — não uma nota de confiança.
        </p>
        <div className="mt-3">
          <DataQualitySection />
        </div>
      </section>

      <div className="mt-10 space-y-8">
        <h2 className="font-heading text-xl font-semibold">Radar de Comércio</h2>
        {SECOES.map((secao) => (
          <section key={secao.id} id={secao.id} className="scroll-mt-6 border-t pt-6">
            <h3 className="font-heading text-lg font-medium">{secao.titulo}</h3>
            <div className="mt-2 text-sm text-muted-foreground [&_strong]:text-foreground [&_em]:text-foreground [&_em]:not-italic [&_em]:font-medium">
              {secao.corpo}
            </div>
          </section>
        ))}
      </div>

      <section className="mt-10 rounded-md border p-4">
        <h2 className="font-heading text-lg font-medium">Qualidade dos dados — Radar Imobiliário</h2>
        <p className="mt-1 text-xs text-muted-foreground">
          Fatos objetivos sobre a base — não uma nota de confiança.
        </p>
        <div className="mt-3">
          <DataQualityImoveisSection />
        </div>
      </section>

      <div className="mt-10 space-y-8">
        <h2 className="font-heading text-xl font-semibold">Radar Imobiliário</h2>
        {SECOES_IMOVEIS.map((secao) => (
          <section key={secao.id} id={secao.id} className="scroll-mt-6 border-t pt-6">
            <h3 className="font-heading text-lg font-medium">{secao.titulo}</h3>
            <div className="mt-2 text-sm text-muted-foreground [&_strong]:text-foreground [&_em]:text-foreground [&_em]:not-italic [&_em]:font-medium">
              {secao.corpo}
            </div>
          </section>
        ))}
      </div>
    </main>
  );
}
