import uuid

from infrastructure.geocoding import geocodebr_subprocess
from infrastructure.geocoding.geocodebr_subprocess import EnderecoParaGeocodificar, geocodificar_lote

ENTIDADE_1 = uuid.uuid4()
ENTIDADE_2 = uuid.uuid4()


def test_geocodificar_lote_vazio_nao_chama_subprocesso(monkeypatch):
    chamado = []
    monkeypatch.setattr(geocodebr_subprocess.subprocess, "run", lambda *a, **k: chamado.append(1))

    resultado = geocodificar_lote([])

    assert resultado == []
    assert chamado == []


def test_geocodificar_lote_le_csv_de_saida_escrito_pelo_r(monkeypatch):
    def fake_run(cmd, capture_output, text, **kwargs):
        # cmd = [rscript, script, entrada_csv, saida_csv]
        saida_csv = cmd[3]
        with open(saida_csv, "w", encoding="utf-8") as f:
            f.write("entidade_id,lat,lon,precisao,tipo_resultado\n")
            f.write(f"{ENTIDADE_1},-25.4799,-49.2788,numero,dn01\n")
            f.write(f"{ENTIDADE_2},,,,\n")

        class Resultado:
            returncode = 0
            stderr = ""

        return Resultado()

    monkeypatch.setattr(geocodebr_subprocess.subprocess, "run", fake_run)

    enderecos = [
        EnderecoParaGeocodificar(ENTIDADE_1, "R. X", "10", "80000-000", "CENTRO"),
        EnderecoParaGeocodificar(ENTIDADE_2, "R. Y", "20", "80000-000", "CENTRO"),
    ]
    resultado = geocodificar_lote(enderecos)

    assert len(resultado) == 2
    por_id = {r.entidade_id: r for r in resultado}
    assert por_id[ENTIDADE_1].lat == -25.4799
    assert por_id[ENTIDADE_1].precisao == "numero"
    assert por_id[ENTIDADE_2].lat is None
    assert por_id[ENTIDADE_2].precisao is None


def test_geocodificar_lote_levanta_erro_se_r_falhar(monkeypatch):
    def fake_run(cmd, capture_output, text, **kwargs):
        class Resultado:
            returncode = 1
            stderr = "erro simulado do R"

        return Resultado()

    monkeypatch.setattr(geocodebr_subprocess.subprocess, "run", fake_run)

    enderecos = [EnderecoParaGeocodificar(ENTIDADE_1, "R. X", "10", "80000-000", "CENTRO")]

    try:
        geocodificar_lote(enderecos)
        assert False, "deveria ter levantado RuntimeError"
    except RuntimeError as e:
        assert "erro simulado do R" in str(e)
