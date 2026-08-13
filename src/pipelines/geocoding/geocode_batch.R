# Geocodifica um lote de enderecos contra o CNEFE (geocodebr) e grava o
# resultado num CSV. Chamado como subprocesso pelo pipeline Python
# (src/pipelines/geocoding/etapa1_geocodebr.py) - nunca roda no caminho de
# uma requisicao HTTP ao vivo, so em batch.
#
# Uso: Rscript geocode_batch.R <entrada.csv> <saida.csv>
#
# entrada.csv precisa ter as colunas: entidade_id, logradouro, numero, cep,
# localidade, municipio, estado.
#
# resultado_completo=TRUE quebra nesta versao do geocodebr (0.6.4) com um
# erro de binder do duckdb ("Table output_db does not have a column named
# empate") - reproduzido no Piloto 2 independente de resolver_empates.
# Usamos resultado_completo=FALSE, resolver_empates=FALSE de proposito
# (mesma configuracao validada no piloto).

args <- commandArgs(trailingOnly = TRUE)
if (length(args) != 2) {
  stop("uso: Rscript geocode_batch.R <entrada.csv> <saida.csv>")
}
arquivo_entrada <- args[1]
arquivo_saida <- args[2]

lib_paths <- Sys.getenv("MERCATOR_R_LIBS", unset = "")
if (nzchar(lib_paths)) {
  .libPaths(c(lib_paths, .libPaths()))
}
library(geocodebr)

input_df <- read.csv(arquivo_entrada, colClasses = "character", fileEncoding = "UTF-8", encoding = "UTF-8")

campos <- geocodebr::definir_campos(
  logradouro = "logradouro",
  numero = "numero",
  cep = "cep",
  localidade = "localidade",
  municipio = "municipio",
  estado = "estado"
)

resultado <- geocodebr::geocode(
  enderecos = input_df,
  campos_endereco = campos,
  resultado_completo = FALSE,
  resolver_empates = FALSE,
  resultado_sf = FALSE,
  verboso = FALSE
)

write.csv(
  resultado[, c("entidade_id", "lat", "lon", "precisao", "tipo_resultado")],
  arquivo_saida,
  row.names = FALSE,
  na = "",
  fileEncoding = "UTF-8"
)
