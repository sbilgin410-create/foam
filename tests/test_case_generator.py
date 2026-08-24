import shutil
from pathlib import Path

import pytest

from app.cfd.case_generator import generate_case
from app.cfd.geometry import (
    AisleSpec,
    CabinetSpec,
    RoomSpec,
    build_engineering_summary,
    build_geometry,
)

OUT_DIR = Path(__file__).resolve().parent / "_tmp_case"


def _sample_data():
    room = RoomSpec(
        length_x=8.0,
        width_y=6.0,
        height_z=3.0,
        raised_floor_height=0.6,
        tile_size=0.6,
        supply_air_temp_c=22.0,
        supply_air_flow_m3s=3.0,
    )
    cabinets = [
        CabinetSpec(tag="A-01", x=1.0, y=1.0, width=0.6, depth=1.0, height=2.0, power_kw=6.0),
        CabinetSpec(tag="A-02", x=1.6, y=1.0, width=0.6, depth=1.0, height=2.0, power_kw=6.0),
        CabinetSpec(tag="B-01", x=1.0, y=3.5, width=0.6, depth=1.0, height=2.0, power_kw=5.0),
    ]
    aisles = [
        AisleSpec(name="Soguk-1", aisle_type="soguk", x=1.0, y=2.2, width_x=1.2, width_y=1.0, containment="soguk_kapali"),
        AisleSpec(name="Sicak-1", aisle_type="sicak", x=1.0, y=4.6, width_x=1.2, width_y=1.0),
    ]
    return room, cabinets, aisles


def test_build_geometry_grid_covers_room():
    room, cabinets, aisles = _sample_data()
    geo = build_geometry(room, cabinets, aisles)
    assert geo.nx == round(room.length_x / room.tile_size)
    assert geo.ny == round(room.width_y / room.tile_size)
    assert len(geo.columns) == geo.nx * geo.ny
    assert len(geo.racks) == len(cabinets)
    cold_cols = [c for c in geo.columns if c.floor_patch == "soguk_giris"]
    assert cold_cols, "soğuk koridor altında en az bir sütun inlet olmalı"


def test_engineering_summary_flags_missing_hot_aisle():
    room, cabinets, aisles = _sample_data()
    only_cold = [a for a in aisles if a.aisle_type == "soguk"]
    summary = build_engineering_summary(room, cabinets, only_cold)
    assert summary.total_it_load_kw == pytest.approx(17.0)
    assert any("sıcak koridor" in w for w in summary.warnings)


def test_generate_case_writes_expected_files():
    room, cabinets, aisles = _sample_data()
    if OUT_DIR.exists():
        shutil.rmtree(OUT_DIR)
    result = generate_case(room, cabinets, aisles, OUT_DIR)
    try:
        case = result.case_dir
        for rel in [
            "system/blockMeshDict",
            "system/topoSetDict",
            "system/controlDict",
            "system/fvSchemes",
            "system/fvSolution",
            "constant/g",
            "constant/turbulenceProperties",
            "constant/thermophysicalProperties",
            "constant/fvOptions",
            "0/U",
            "0/T",
            "0/p",
            "0/p_rgh",
            "0/k",
            "0/epsilon",
            "0/nut",
            "0/alphat",
        ]:
            assert (case / rel).exists(), f"eksik dosya: {rel}"

        block_mesh = (case / "system" / "blockMeshDict").read_text()
        assert "soguk_giris" in block_mesh
        assert "tavan_donus" in block_mesh
        assert block_mesh.count("hex (") == result.geometry.total_blocks

        fv_options = (case / "constant" / "fvOptions").read_text()
        for c in cabinets:
            assert f"rackHeat_{c.tag.replace('-', '_')}" in fv_options
    finally:
        shutil.rmtree(OUT_DIR, ignore_errors=True)


def test_too_small_tile_size_raises():
    room, cabinets, aisles = _sample_data()
    room.tile_size = 0.01
    with pytest.raises(ValueError):
        build_geometry(room, cabinets, aisles)
