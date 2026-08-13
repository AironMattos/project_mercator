.libPaths(c("C:/Users/Airon/Documents/R/win-library/4.6", .libPaths()))
library(geocodebr)

input_df <- read.csv(
  "C:/engenharia/project_mercator/experimental/geocodificacao_piloto/enderecos_lindoia.csv",
  colClasses = "character",
  fileEncoding = "UTF-8",
  encoding = "UTF-8"
)
cat("linhas de entrada:", nrow(input_df), "\n")

campos <- geocodebr::definir_campos(
  logradouro = "logradouro",
  numero = "numero",
  cep = "cep",
  localidade = "localidade",
  municipio = "municipio",
  estado = "estado"
)

t0 <- Sys.time()
resultado <- geocodebr::geocode(
  enderecos = input_df,
  campos_endereco = campos,
  resultado_completo = FALSE,
  resolver_empates = FALSE,
  resultado_sf = FALSE,
  verboso = TRUE
)
t1 <- Sys.time()

cat("GEOCODE_SECONDS:", as.numeric(difftime(t1, t0, units = "secs")), "\n")
cat("linhas de saida:", nrow(resultado), "\n")

write.csv(
  resultado,
  "C:/engenharia/project_mercator/experimental/geocodificacao_piloto/resultado_geocodebr_todos.csv",
  row.names = FALSE,
  na = "",
  fileEncoding = "UTF-8"
)
