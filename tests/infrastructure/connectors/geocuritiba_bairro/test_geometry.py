from infrastructure.connectors.geocuritiba_bairro.geometry import (
    aneis_esri_para_multipolygon,
    anel_e_horario,
    reprojetar_anel,
)

# Envelope aproximado de Curitiba em graus (WGS84 / EPSG:4326).
CURITIBA_LON_MIN, CURITIBA_LON_MAX = -49.5, -49.0
CURITIBA_LAT_MIN, CURITIBA_LAT_MAX = -25.7, -25.2


def test_reprojetar_anel_31982_para_4326_cai_dentro_de_curitiba():
    # Coordenada real (coord_x/coord_y) de uma feature da camada Bairro do
    # GeoCuritiba, em EPSG:31982.
    ring = [[667792.18220869, 7183619.72139499]]
    (lon, lat) = reprojetar_anel(ring)[0]
    assert CURITIBA_LON_MIN < lon < CURITIBA_LON_MAX
    assert CURITIBA_LAT_MIN < lat < CURITIBA_LAT_MAX


def test_reprojetar_anel_preserva_numero_de_pontos():
    ring = [[670000, 7183000], [670010, 7183010], [670020, 7183000]]
    resultado = reprojetar_anel(ring)
    assert len(resultado) == len(ring)


def test_anel_horario_reconhecido():
    # Quadrado percorrido em sentido horário (convenção Esri: anel externo).
    horario = [(0, 0), (0, 10), (10, 10), (10, 0), (0, 0)]
    assert anel_e_horario(horario) is True


def test_anel_anti_horario_reconhecido():
    # Mesmo quadrado, sentido invertido (convenção Esri: buraco).
    anti_horario = [(0, 0), (10, 0), (10, 10), (0, 10), (0, 0)]
    assert anel_e_horario(anti_horario) is False


def _quadrado_com_offset(offset, tamanho, invertido=False):
    ox, oy = offset
    pontos = [
        (ox, oy),
        (ox, oy + tamanho),
        (ox + tamanho, oy + tamanho),
        (ox + tamanho, oy),
        (ox, oy),
    ]
    return list(reversed(pontos)) if invertido else pontos


def test_aneis_esri_para_multipolygon_com_buraco():
    # Coordenadas em EPSG:31982 dentro do envelope real de Curitiba, para
    # que a reprojeção produza um resultado geograficamente plausível.
    exterior = _quadrado_com_offset((670000, 7183000), 10)  # horário -> externo
    buraco = _quadrado_com_offset((670003, 7183003), 4, invertido=True)  # anti-horário -> buraco

    assert anel_e_horario(exterior) is True
    assert anel_e_horario(buraco) is False

    multipoligono = aneis_esri_para_multipolygon([exterior, buraco])

    assert multipoligono.is_valid
    assert len(multipoligono.geoms) == 1
    poligono = multipoligono.geoms[0]
    assert len(poligono.interiors) == 1


def test_aneis_esri_para_multipolygon_multiplas_partes_sem_buraco():
    parte_a = _quadrado_com_offset((670000, 7183000), 10)
    parte_b = _quadrado_com_offset((670100, 7183100), 10)

    multipoligono = aneis_esri_para_multipolygon([parte_a, parte_b])

    assert multipoligono.is_valid
    assert len(multipoligono.geoms) == 2
