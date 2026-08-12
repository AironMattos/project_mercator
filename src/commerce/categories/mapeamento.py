"""Categorias legíveis do Radar de Comércio e o mapeamento explícito de
CNAE (subclasse, código de 7 dígitos - ver commerce.cnae.normalizacao)
para essas categorias.

Lista pequena e explícita, de propósito (checkpoint 4): os ~80 códigos
mapeados aqui são os mais frequentes entre as observações reais de
alvaras_smf (2026-08), cobrindo ~65% das observações cujo CNAE dá pra
normalizar. Não cobre todos os ~1300 códigos da CNAE - um código sem
entrada aqui fica sem categoria (None), o que é esperado e aceitável
nesta fase; ampliar a cobertura é trabalho incremental, não um requisito
deste checkpoint.
"""
from __future__ import annotations

CATEGORIAS: dict[str, str] = {
    "alimentacao_varejo": "Comércio varejista de alimentos e bebidas",
    "bares_restaurantes": "Bares, restaurantes e lanchonetes",
    "vestuario_calcados": "Vestuário, calçados e confecção",
    "beleza_estetica": "Beleza e estética",
    "saude_clinicas": "Saúde e clínicas",
    "veterinaria_pet": "Veterinária e pet shop",
    "construcao_civil": "Construção civil e reformas",
    "veiculos_autopecas": "Comércio e manutenção de veículos",
    "transporte_logistica": "Transporte e logística",
    "imobiliario": "Imobiliário",
    "tecnologia_ti": "Tecnologia da informação",
    "juridico_contabil": "Serviços jurídicos e contábeis",
    "consultoria_empresarial": "Consultoria e serviços empresariais",
    "apoio_administrativo": "Apoio administrativo e escritório",
    "engenharia_arquitetura": "Engenharia e arquitetura",
    "publicidade_marketing": "Publicidade e marketing",
    "educacao_treinamento": "Educação e treinamento",
    "eventos_lazer_esporte": "Eventos, lazer e esporte",
    "seguros_financeiro": "Seguros e serviços financeiros",
    "comercio_eletronicos": "Comércio de eletrônicos e informática",
    "comercio_casa_decoracao": "Comércio de casa, móveis e decoração",
    "farmacia_cosmeticos": "Farmácia e cosméticos",
    "comercio_diversos": "Comércio varejista diversos",
    "associacoes_religiao": "Associações e organizações religiosas",
    "turismo": "Turismo e viagens",
    "servicos_gerais": "Outros serviços prestados a empresas",
}

# codigo_cnae (7 dígitos, formato canonical.dim_cnae) -> categoria_id
MAPEAMENTO_CNAE_CATEGORIA: dict[str, str] = {
    # apoio administrativo e escritório
    "8211300": "apoio_administrativo",  # Serviços combinados de escritório e apoio administrativo
    "8219999": "apoio_administrativo",  # Preparação de documentos e serv. especializados de apoio adm.
    "8291100": "apoio_administrativo",  # Atividades de cobranças e informações cadastrais
    # vestuário, calçados e confecção
    "4781400": "vestuario_calcados",  # Comércio varejista de artigos do vestuário e acessórios
    "1412601": "vestuario_calcados",  # Confecção de peças do vestuário
    # jurídico e contábil
    "6911701": "juridico_contabil",  # Serviços advocatícios
    "6920601": "juridico_contabil",  # Atividades de contabilidade
    # saúde e clínicas
    "8630503": "saude_clinicas",  # Atividade médica ambulatorial restrita a consultas
    "8650003": "saude_clinicas",  # Atividades de psicologia e psicanálise
    "8630504": "saude_clinicas",  # Atividade odontológica
    "8650004": "saude_clinicas",  # Atividades de fisioterapia
    # consultoria e serviços empresariais
    "7020400": "consultoria_empresarial",  # Consultoria em gestão empresarial
    "7490104": "consultoria_empresarial",  # Intermediação e agenciamento de serviços e negócios
    # bares, restaurantes e lanchonetes
    "5611201": "bares_restaurantes",  # Restaurantes e similares
    "5611203": "bares_restaurantes",  # Lanchonetes, casas de chá, de sucos e similares
    "5611204": "bares_restaurantes",  # Bares e outros estabelecimentos especializados em servir bebidas
    "5620104": "bares_restaurantes",  # Fornecimento de alimentos preparados para consumo domiciliar
    # seguros e serviços financeiros
    "6462000": "seguros_financeiro",  # Holdings de instituições não-financeiras
    "6622300": "seguros_financeiro",  # Corretores e agentes de seguros
    "6463800": "seguros_financeiro",  # Outras sociedades de participação, exceto holdings
    "6619399": "seguros_financeiro",  # Outras atividades auxiliares dos serviços financeiros
    # educação e treinamento
    "8599604": "educacao_treinamento",  # Treinamento em desenvolvimento profissional e gerencial
    "8599699": "educacao_treinamento",  # Outras atividades de ensino não especificadas anteriormente
    # publicidade e marketing
    "7319002": "publicidade_marketing",  # Posto de captação de anúncios e assinaturas de jornal
    "7319003": "publicidade_marketing",  # Marketing direto
    "7311400": "publicidade_marketing",  # Agências de publicidade
    # construção civil e reformas
    "4120400": "construcao_civil",  # Construção de edifícios
    "4399103": "construcao_civil",  # Obras de alvenaria
    "4321500": "construcao_civil",  # Instalação e manutenção elétrica
    "4330404": "construcao_civil",  # Serviços de pintura de edifícios em geral
    "4330499": "construcao_civil",  # Outras obras de acabamento da construção
    "4744099": "construcao_civil",  # Comércio varejista de materiais de construção em geral
    # beleza e estética
    "9602501": "beleza_estetica",  # Cabeleireiros, manicure e pedicure
    "9602502": "beleza_estetica",  # Atividades de estética e outros serviços de cuidados com a beleza
    # transporte e logística
    "4930202": "transporte_logistica",  # Transporte rodoviário de carga intermunicipal/interestadual/internac.
    "4930201": "transporte_logistica",  # Transporte rodoviário de carga municipal
    "5320202": "transporte_logistica",  # Serviços de entrega rápida
    "5223100": "transporte_logistica",  # Estacionamento de veículos da própria empresa
    # imobiliário
    "4110700": "imobiliario",  # Incorporação de empreendimentos imobiliários
    "6821801": "imobiliario",  # Corretagem na compra e venda e avaliação de imóveis
    "6810202": "imobiliario",  # Aluguel de imóveis próprios
    "6810201": "imobiliario",  # Compra e venda de imóveis próprios
    "6822600": "imobiliario",  # Gestão e administração da propriedade imobiliária
    # engenharia e arquitetura
    "7112000": "engenharia_arquitetura",  # Serviços de engenharia
    "7111100": "engenharia_arquitetura",  # Serviços de arquitetura
    # tecnologia da informação
    "6209100": "tecnologia_ti",  # Suporte técnico, manutenção e outros serviços em TI
    "6204000": "tecnologia_ti",  # Consultoria em tecnologia da informação
    "6201501": "tecnologia_ti",  # Desenvolvimento de programas de computador sob encomenda
    "6202300": "tecnologia_ti",  # Desenvolvimento e licenciamento de programas de computador customizáveis
    "6319400": "tecnologia_ti",  # Portais, provedores de conteúdo e outros serviços de informação na internet
    # comércio varejista diversos
    "4619200": "comercio_diversos",  # Representantes comerciais e agentes do comércio de mercadorias em geral
    "4789099": "comercio_diversos",  # Comércio varejista de outros produtos não especificados
    "4761003": "comercio_diversos",  # Comércio varejista de artigos de papelaria
    "4789001": "comercio_diversos",  # Comércio varejista de suvenires, bijuterias e artesanatos
    # comércio de alimentos e bebidas (varejo)
    "4712100": "alimentacao_varejo",  # Comércio varejista mercadorias em geral - predominância alimentícios
    "4729699": "alimentacao_varejo",  # Comércio varejista de produtos alimentícios em geral
    "4723700": "alimentacao_varejo",  # Comércio varejista de bebidas
    # eventos, lazer e esporte
    "8230001": "eventos_lazer_esporte",  # Serviços de organização de feiras, congressos, exposições e festas
    "9313100": "eventos_lazer_esporte",  # Academia de yoga, relaxamento, pilates e/ou aperfeiçoamento pessoal
    # comércio e manutenção de veículos
    "4530703": "veiculos_autopecas",  # Comércio a varejo de peças e acessórios novos para veículos automotores
    "4520001": "veiculos_autopecas",  # Serviços de manutenção e reparação mecânica de veículos automotores
    "4511102": "veiculos_autopecas",  # Comércio a varejo de automóveis, camionetas e utilitários usados
    # comércio de eletrônicos e informática
    "4751201": "comercio_eletronicos",  # Comércio varejista especializado de equip. e suprimentos de informática
    "4752100": "comercio_eletronicos",  # Comércio varejista especializado de equipamentos de telefonia
    "4753900": "comercio_eletronicos",  # Comércio varejista especializado de eletrodomésticos e áudio/vídeo
    "4757100": "comercio_eletronicos",  # Comércio varejista de peças para aparelhos eletroeletrônicos
    # associações e organizações religiosas
    "9430800": "associacoes_religiao",  # Atividades de associações de defesa de direitos sociais
    "9499500": "associacoes_religiao",  # Atividades associativas não especificadas anteriormente
    "9491000": "associacoes_religiao",  # Atividades de organizações religiosas e filosóficas
    # turismo
    "7911200": "turismo",  # Agências de viagens
    # comércio de casa, móveis e decoração
    "4754701": "comercio_casa_decoracao",  # Comércio varejista de móveis
    "4744001": "comercio_casa_decoracao",  # Comércio varejista de ferragens e ferramentas
    "4759899": "comercio_casa_decoracao",  # Comércio varejista de outros artigos de uso doméstico
    # farmácia e cosméticos
    "4772500": "farmacia_cosmeticos",  # Comércio varejista de cosméticos, produtos de perfumaria e higiene
    "4771701": "farmacia_cosmeticos",  # Comércio varejista de produtos farmacêuticos, sem manipulação
    # veterinária e pet shop
    "4789004": "veterinaria_pet",  # Comércio varejista de animais vivos e artigos para animais de estimação
    "7500100": "veterinaria_pet",  # Atividades veterinárias
    # outros serviços prestados a empresas
    "9511800": "servicos_gerais",  # Serviços de recuperação de fitas/cartuchos para impressoras
    "8299799": "servicos_gerais",  # Outras atividades de serviços prestados às empresas
}
