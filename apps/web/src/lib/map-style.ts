// URL do estilo-base do MapLibre, compartilhada por TODOS os mapas do
// produto (coroplético em choropleth-map.tsx e busca por raio em
// radius-map.tsx) - trocar de provedor é mudar só esta constante, nunca
// duplicada nos componentes.
//
// OpenFreeMap (checkpoint 9f): sem chave de API, sem conta, gratuito para
// uso contínuo em produção - ao contrário dos tiles brutos do OSM
// (tile.openstreetmap.org), que restringem uso pesado/produção do mesmo
// jeito que o Nominatim público (ver checkpoint 9, pilotos de
// geocodificação). Estilo "positron": claro/neutro, POIs removidos por
// design - de propósito, para o coroplético e os marcadores continuarem
// sendo o elemento mais chamativo da tela, não o mapa-base.
//
// MapTiler foi a recomendação original do prompt de referência (faixa
// gratuita generosa, estilo "streets" pronto) - não usado aqui porque
// criar a conta/API key não é algo que a Claude possa fazer sozinha.
// Para trocar pra MapTiler:
//   1. Crie uma conta em https://www.maptiler.com/ e gere uma API key
//   2. Defina NEXT_PUBLIC_MAPTILER_KEY no .env.local
//   3. Troque MAP_STYLE_URL abaixo por, por exemplo,
//      `https://api.maptiler.com/maps/streets-v2-light/style.json?key=${process.env.NEXT_PUBLIC_MAPTILER_KEY}`
export const MAP_STYLE_URL = "https://tiles.openfreemap.org/styles/positron";

// "Anel" de 2px na cor de superfície do produto (--background, #ffffff em
// globals.css) ao redor de todo marcador/borda de polígono - o que separa
// visualmente o dado (coroplético, marcadores) de um mapa-base agora com
// ruas e rótulos reais, sem desenhar uma borda escura própria.
export const COR_SUPERFICIE = "#ffffff";
export const LARGURA_ANEL_SUPERFICIE = 2;
