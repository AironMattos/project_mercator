.libPaths(c("C:/Users/Airon/Documents/R/win-library/4.6", .libPaths()))
library(geocodebr)

t0 <- Sys.time()
path <- geocodebr::download_cnefe(tabela = "todas", verboso = TRUE)
t1 <- Sys.time()

cat("\nCACHE PATH:", path, "\n")
cat("DOWNLOAD_SECONDS:", as.numeric(difftime(t1, t0, units = "secs")), "\n")

listar_dados_cache <- geocodebr::listar_dados_cache
arquivos <- listar_dados_cache()
print(arquivos)
