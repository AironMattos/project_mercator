import uuid
from datetime import date

import pytest

from domain.observation import ObservacaoEntidade


def _base_kwargs():
    return dict(
        entidade_id=uuid.uuid4(),
        observado_em=date(2026, 8, 1),
        atributos={"nome": "TESTE"},
        fonte_id="alvaras_smf",
        snapshot_ref="data/raw/alvaras_smf/2026-08-01.csv",
    )


def test_observacao_valida_e_aceita():
    o = ObservacaoEntidade(**_base_kwargs())
    assert o.observado_em == date(2026, 8, 1)
    assert o.observacao_id is not None


def test_observacao_id_gerado_automaticamente_e_unico():
    kwargs = _base_kwargs()
    o1 = ObservacaoEntidade(**kwargs)
    o2 = ObservacaoEntidade(**kwargs)
    assert o1.observacao_id != o2.observacao_id


def test_atributos_vazio_rejeitado():
    kwargs = _base_kwargs()
    kwargs["atributos"] = {}
    with pytest.raises(ValueError):
        ObservacaoEntidade(**kwargs)


def test_fonte_id_vazio_rejeitado():
    kwargs = _base_kwargs()
    kwargs["fonte_id"] = ""
    with pytest.raises(ValueError):
        ObservacaoEntidade(**kwargs)


def test_snapshot_ref_vazio_rejeitado():
    kwargs = _base_kwargs()
    kwargs["snapshot_ref"] = ""
    with pytest.raises(ValueError):
        ObservacaoEntidade(**kwargs)
