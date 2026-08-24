"""Oda / kabin / koridor verisinden çalışmaya hazır bir OpenFOAM case
(dizini) üretir. Hedef çözücü: buoyantSimpleFoam (kaldırma kuvveti etkili,
sıkıştırılabilir, kararlı hal ısı+akış çözücüsü) — veri merkezi soğuk/sıcak
koridor analizlerinde yaygın kullanılan bir OpenFOAM çözücüsüdür.

Bu üretici; ANSYS Fluent / Abaqus-CFD gibi ticari araçlardaki tipik
"geometri -> mesh -> sınır şartı -> çöz -> sonuç" iş akışını, tamamen açık
kaynak ve Ubuntu üzerinde lisanssız çalışan OpenFOAM ile karşılar.
"""

from __future__ import annotations

import shutil
from dataclasses import dataclass
from pathlib import Path

from .geometry import (
    AisleSpec,
    CabinetSpec,
    CaseGeometry,
    EngineeringSummary,
    RoomSpec,
    build_engineering_summary,
    build_geometry,
)

KELVIN_OFFSET = 273.15


def _foam_header(obj: str, cls: str, location: str) -> str:
    return f"""FoamFile
{{
    version     2.0;
    format      ascii;
    class       {cls};
    object      {obj};
}}
"""


def _dims(d: str) -> str:
    return f"dimensions      {d};\n"


# --------------------------------------------------------------------------
# system/blockMeshDict
# --------------------------------------------------------------------------

def _render_block_mesh_dict(geo: CaseGeometry) -> str:
    lines: list[str] = [_foam_header("blockMeshDict", "dictionary", "system")]
    lines.append("convertToMeters 1.0;\n")

    # vertices
    lines.append("vertices\n(")
    for k in (0, 1):
        z = 0.0 if k == 0 else geo.height_z
        for j in range(geo.ny + 1):
            y = j * geo.dy
            for i in range(geo.nx + 1):
                x = i * geo.dx
                lines.append(f"    ({x:.6f} {y:.6f} {z:.6f})")
    lines.append(");\n")

    # blocks
    lines.append("blocks\n(")
    for col in geo.columns:
        v0 = geo.vertex_index(col.ci, col.cj, 0)
        v1 = geo.vertex_index(col.ci + 1, col.cj, 0)
        v2 = geo.vertex_index(col.ci + 1, col.cj + 1, 0)
        v3 = geo.vertex_index(col.ci, col.cj + 1, 0)
        v4 = geo.vertex_index(col.ci, col.cj, 1)
        v5 = geo.vertex_index(col.ci + 1, col.cj, 1)
        v6 = geo.vertex_index(col.ci + 1, col.cj + 1, 1)
        v7 = geo.vertex_index(col.ci, col.cj + 1, 1)
        n = geo.cell_res_xy
        nz = geo.cell_res_z
        lines.append(
            f"    hex ({v0} {v1} {v2} {v3} {v4} {v5} {v6} {v7}) ({n} {n} {nz}) simpleGrading (1 1 1)"
        )
    lines.append(");\n")
    lines.append("edges\n(\n);\n")

    # boundary patches
    def col_faces(patch_pred):
        faces = []
        for col in geo.columns:
            if not patch_pred(col):
                continue
            v0 = geo.vertex_index(col.ci, col.cj, 0)
            v1 = geo.vertex_index(col.ci + 1, col.cj, 0)
            v2 = geo.vertex_index(col.ci + 1, col.cj + 1, 0)
            v3 = geo.vertex_index(col.ci, col.cj + 1, 0)
            faces.append(f"        ({v0} {v3} {v2} {v1})")
        return faces

    bottom_groups = {
        "soguk_giris": lambda c: c.floor_patch == "soguk_giris",
        "zemin_sicak_koridor": lambda c: c.floor_patch == "zemin_sicak_koridor",
        "zemin_diger": lambda c: c.floor_patch == "zemin_diger",
    }

    lines.append("boundary\n(")

    for name, pred in bottom_groups.items():
        faces = col_faces(pred)
        if not faces:
            continue
        ptype = "patch" if name == "soguk_giris" else "wall"
        lines.append(f"    {name}\n    {{")
        lines.append(f"        type {ptype};")
        lines.append("        faces\n        (")
        lines.extend(faces)
        lines.append("        );")
        lines.append("    }")

    # ceiling / return (top faces, all columns)
    top_faces = []
    for col in geo.columns:
        v4 = geo.vertex_index(col.ci, col.cj, 1)
        v5 = geo.vertex_index(col.ci + 1, col.cj, 1)
        v6 = geo.vertex_index(col.ci + 1, col.cj + 1, 1)
        v7 = geo.vertex_index(col.ci, col.cj + 1, 1)
        top_faces.append(f"        ({v4} {v5} {v6} {v7})")
    lines.append("    tavan_donus\n    {")
    lines.append("        type patch;")
    lines.append("        faces\n        (")
    lines.extend(top_faces)
    lines.append("        );")
    lines.append("    }")

    # outer side walls
    side_faces = []
    for col in geo.columns:
        v0 = geo.vertex_index(col.ci, col.cj, 0)
        v1 = geo.vertex_index(col.ci + 1, col.cj, 0)
        v2 = geo.vertex_index(col.ci + 1, col.cj + 1, 0)
        v3 = geo.vertex_index(col.ci, col.cj + 1, 0)
        v4 = geo.vertex_index(col.ci, col.cj, 1)
        v5 = geo.vertex_index(col.ci + 1, col.cj, 1)
        v6 = geo.vertex_index(col.ci + 1, col.cj + 1, 1)
        v7 = geo.vertex_index(col.ci, col.cj + 1, 1)
        if col.cj == 0:
            side_faces.append(f"        ({v0} {v1} {v5} {v4})")  # -y
        if col.cj == geo.ny - 1:
            side_faces.append(f"        ({v2} {v3} {v7} {v6})")  # +y
        if col.ci == 0:
            side_faces.append(f"        ({v0} {v4} {v7} {v3})")  # -x
        if col.ci == geo.nx - 1:
            side_faces.append(f"        ({v1} {v2} {v6} {v5})")  # +x
    lines.append("    duvarlar\n    {")
    lines.append("        type wall;")
    lines.append("        faces\n        (")
    lines.extend(side_faces)
    lines.append("        );")
    lines.append("    }")

    lines.append(");\n")
    lines.append("mergePatchPairs\n(\n);\n")
    return "\n".join(lines)


# --------------------------------------------------------------------------
# system/topoSetDict + constant/fvOptions (rack ısı kaynakları)
# --------------------------------------------------------------------------

def _safe_name(tag: str) -> str:
    return "".join(ch if ch.isalnum() else "_" for ch in tag)


def _render_topo_set_dict(geo: CaseGeometry) -> str:
    lines = [_foam_header("topoSetDict", "dictionary", "system"), "actions\n("]
    for r in geo.racks:
        name = f"rackSet_{_safe_name(r.tag)}"
        lines.append(f"    {{")
        lines.append(f"        name    {name};")
        lines.append("        type    cellSet;")
        lines.append("        action  new;")
        lines.append("        source  boxToCell;")
        lines.append(
            f"        box     ({r.x0:.6f} {r.y0:.6f} {r.z0:.6f}) ({r.x1:.6f} {r.y1:.6f} {r.z1:.6f});"
        )
        lines.append("    }")
    lines.append(");\n")
    return "\n".join(lines)


def _render_fv_options(geo: CaseGeometry) -> str:
    lines = [_foam_header("fvOptions", "dictionary", "constant")]
    for r in geo.racks:
        name = f"rackSet_{_safe_name(r.tag)}"
        lines.append(f"rackHeat_{_safe_name(r.tag)}")
        lines.append("{")
        lines.append("    type            scalarSemiImplicitSource;")
        lines.append("    selectionMode   cellSet;")
        lines.append(f"    cellSet         {name};")
        lines.append("    volumeMode      absolute;")
        lines.append("    injectionRateSuSp")
        lines.append("    {")
        lines.append(f"        h           ({r.power_w:.2f} 0);")
        lines.append("    }")
        lines.append("}")
        lines.append("")
    return "\n".join(lines)


# --------------------------------------------------------------------------
# 0/ alan dosyaları
# --------------------------------------------------------------------------

def _inlet_velocity(geo: CaseGeometry, supply_flow_m3s: float) -> float:
    inlet_area = sum(
        geo.dx * geo.dy for c in geo.columns if c.floor_patch == "soguk_giris"
    )
    if inlet_area <= 0:
        return 0.0
    return supply_flow_m3s / inlet_area


def _write_field(path: Path, obj: str, dims: str, internal: str, patches: dict[str, list[str]]) -> None:
    body = [_foam_header(obj, "volScalarField" if obj != "U" else "volVectorField", "0")]
    body.append(_dims(dims))
    body.append(f"internalField   {internal};\n")
    body.append("boundaryField\n{")
    for patch, opts in patches.items():
        body.append(f"    {patch}\n    {{")
        for line in opts:
            body.append(f"        {line}")
        body.append("    }")
    body.append("}\n")
    path.write_text("\n".join(body))


def _write_zero_fields(case_dir: Path, geo: CaseGeometry, supply_temp_c: float, supply_flow_m3s: float) -> None:
    zero = case_dir / "0"
    zero.mkdir(parents=True, exist_ok=True)

    supply_k = supply_temp_c + KELVIN_OFFSET
    ambient_k = supply_k + 8.0  # ilk tahmin: koridor ortalama sıcaklığı
    v_in = round(_inlet_velocity(geo, supply_flow_m3s), 4)

    walls = ["zemin_sicak_koridor", "zemin_diger", "duvarlar"]

    # --- U ---
    patches = {}
    patches["soguk_giris"] = [
        "type            fixedValue;",
        f"value           uniform (0 0 {v_in:.4f});",
    ]
    for w in walls:
        patches[w] = ["type            noSlip;"]
    patches["tavan_donus"] = [
        "type            pressureInletOutletVelocity;",
        "value           uniform (0 0 0);",
    ]
    _write_field(zero / "U", "U", "[0 1 -1 0 0 0 0]", "uniform (0 0 0)", patches)

    # --- T ---
    patches = {"soguk_giris": [
        "type            fixedValue;",
        f"value           uniform {supply_k:.2f};",
    ]}
    for w in walls:
        patches[w] = ["type            zeroGradient;"]
    patches["tavan_donus"] = [
        "type            inletOutlet;",
        f"inletValue      uniform {ambient_k:.2f};",
        f"value           uniform {ambient_k:.2f};",
    ]
    _write_field(zero / "T", "T", "[0 0 0 1 0 0 0]", f"uniform {ambient_k:.2f}", patches)

    # --- p_rgh ---
    patches = {}
    for w in ["soguk_giris"] + walls:
        patches[w] = [
            "type            fixedFluxPressure;",
            "value           uniform 100000;",
        ]
    patches["tavan_donus"] = [
        "type            prghPressure;",
        "p               uniform 100000;",
        "value           uniform 100000;",
    ]
    _write_field(zero / "p_rgh", "p_rgh", "[1 -1 -2 0 0 0 0]", "uniform 100000", patches)

    # --- p ---
    patches = {}
    for w in ["soguk_giris"] + walls + ["tavan_donus"]:
        patches[w] = ["type            calculated;", "value           uniform 100000;"]
    _write_field(zero / "p", "p", "[1 -1 -2 0 0 0 0]", "uniform 100000", patches)

    # --- k ---
    k_in = 0.01
    patches = {"soguk_giris": [
        "type            turbulentIntensityKineticEnergyInlet;",
        "intensity       0.05;",
        f"value           uniform {k_in};",
    ]}
    for w in walls:
        patches[w] = ["type            kqRWallFunction;", f"value           uniform {k_in};"]
    patches["tavan_donus"] = ["type            inletOutlet;", f"inletValue      uniform {k_in};", f"value           uniform {k_in};"]
    _write_field(zero / "k", "k", "[0 2 -2 0 0 0 0]", f"uniform {k_in}", patches)

    # --- epsilon ---
    eps_in = 0.01
    patches = {"soguk_giris": [
        "type            turbulentMixingLengthDissipationRateInlet;",
        "mixingLength    0.1;",
        f"value           uniform {eps_in};",
    ]}
    for w in walls:
        patches[w] = ["type            epsilonWallFunction;", f"value           uniform {eps_in};"]
    patches["tavan_donus"] = ["type            inletOutlet;", f"inletValue      uniform {eps_in};", f"value           uniform {eps_in};"]
    _write_field(zero / "epsilon", "epsilon", "[0 2 -3 0 0 0 0]", f"uniform {eps_in}", patches)

    # --- nut ---
    patches = {"soguk_giris": ["type            calculated;", "value           uniform 0;"]}
    for w in walls:
        patches[w] = ["type            nutkWallFunction;", "value           uniform 0;"]
    patches["tavan_donus"] = ["type            calculated;", "value           uniform 0;"]
    _write_field(zero / "nut", "nut", "[0 2 -1 0 0 0 0]", "uniform 0", patches)

    # --- alphat ---
    patches = {"soguk_giris": ["type            calculated;", "value           uniform 0;"]}
    for w in walls:
        patches[w] = [
            "type            compressible::alphatJayatillekeWallFunction;",
            "Prt             0.85;",
            "value           uniform 0;",
        ]
    patches["tavan_donus"] = ["type            calculated;", "value           uniform 0;"]
    _write_field(zero / "alphat", "alphat", "[1 -1 -1 0 0 0 0]", "uniform 0", patches)


# --------------------------------------------------------------------------
# constant/ statik dosyalar
# --------------------------------------------------------------------------

_G_DICT = """FoamFile
{
    version     2.0;
    format      ascii;
    class       uniformDimensionedVectorField;
    object      g;
}
dimensions      [0 1 -2 0 0 0 0];
value           (0 0 -9.81);
"""

_TURBULENCE_PROPERTIES = """FoamFile
{
    version     2.0;
    format      ascii;
    class       dictionary;
    object      turbulenceProperties;
}
simulationType  RAS;
RAS
{
    RASModel        kEpsilon;
    turbulence      on;
    printCoeffs     on;
}
"""

_THERMOPHYSICAL_PROPERTIES = """FoamFile
{
    version     2.0;
    format      ascii;
    class       dictionary;
    object      thermophysicalProperties;
}
thermoType
{
    type            heRhoThermo;
    mixture         pureMixture;
    transport       const;
    thermo          hConst;
    equationOfState perfectGas;
    specie          specie;
    energy          sensibleEnthalpy;
}
mixture
{
    specie
    {
        molWeight   28.96;
    }
    thermodynamics
    {
        Cp          1006;
        Hf          0;
    }
    transport
    {
        mu          1.8e-05;
        Pr          0.71;
    }
}
"""

_CONTROL_DICT = """FoamFile
{
    version     2.0;
    format      ascii;
    class       dictionary;
    object      controlDict;
}
application     buoyantSimpleFoam;
startFrom       startTime;
startTime       0;
stopAt          endTime;
endTime         1000;
deltaT          1;
writeControl    timeStep;
writeInterval   100;
purgeWrite      2;
writeFormat     ascii;
writePrecision  6;
writeCompression off;
timeFormat      general;
timePrecision   6;
runTimeModifiable true;
"""

_FV_SCHEMES = """FoamFile
{
    version     2.0;
    format      ascii;
    class       dictionary;
    object      fvSchemes;
}
ddtSchemes
{
    default         steadyState;
}
gradSchemes
{
    default         Gauss linear;
}
divSchemes
{
    default             none;
    div(phi,U)          bounded Gauss upwind;
    div(phi,h)          bounded Gauss upwind;
    div(phi,K)          bounded Gauss upwind;
    div(phi,k)          bounded Gauss upwind;
    div(phi,epsilon)    bounded Gauss upwind;
    div(phi,Ekp)        bounded Gauss upwind;
    div((phi|interpolate(rho)),p)  bounded Gauss upwind;
    div(((rho*nuEff)*dev2(T(grad(U)))))  Gauss linear;
}
laplacianSchemes
{
    default         Gauss linear corrected;
}
interpolationSchemes
{
    default         linear;
}
snGradSchemes
{
    default         corrected;
}
wallDist
{
    method          meshWave;
}
"""

_FV_SOLUTION = """FoamFile
{
    version     2.0;
    format      ascii;
    class       dictionary;
    object      fvSolution;
}
solvers
{
    "rho.*"
    {
        solver          diagonal;
    }
    p_rgh
    {
        solver          GAMG;
        tolerance       1e-8;
        relTol          0.01;
        smoother        GaussSeidel;
    }
    "(U|h|k|epsilon)"
    {
        solver          smoothSolver;
        smoother        GaussSeidel;
        tolerance       1e-8;
        relTol          0.1;
        nSweeps         1;
    }
}
SIMPLE
{
    momentumPredictor   yes;
    nNonOrthogonalCorrectors 1;
    pRefCell        0;
    pRefValue       100000;
    residualControl
    {
        p_rgh           1e-3;
        U               1e-4;
        h               1e-4;
        "(k|epsilon)"   1e-3;
    }
}
relaxationFactors
{
    fields
    {
        p_rgh           0.7;
        rho             0.05;
    }
    equations
    {
        U               0.3;
        h               0.3;
        "(k|epsilon)"   0.3;
    }
}
"""


def _write_static(case_dir: Path) -> None:
    (case_dir / "constant").mkdir(parents=True, exist_ok=True)
    (case_dir / "system").mkdir(parents=True, exist_ok=True)

    (case_dir / "constant" / "g").write_text(_G_DICT)
    (case_dir / "constant" / "turbulenceProperties").write_text(_TURBULENCE_PROPERTIES)
    (case_dir / "constant" / "thermophysicalProperties").write_text(_THERMOPHYSICAL_PROPERTIES)

    (case_dir / "system" / "controlDict").write_text(_CONTROL_DICT)
    (case_dir / "system" / "fvSchemes").write_text(_FV_SCHEMES)
    (case_dir / "system" / "fvSolution").write_text(_FV_SOLUTION)


# --------------------------------------------------------------------------
# genel üretim akışı
# --------------------------------------------------------------------------

@dataclass
class GeneratedCase:
    case_dir: Path
    geometry: CaseGeometry
    summary: EngineeringSummary


def generate_case(
    room: RoomSpec,
    cabinets: list[CabinetSpec],
    aisles: list[AisleSpec],
    out_dir: Path,
) -> GeneratedCase:
    if out_dir.exists():
        shutil.rmtree(out_dir)
    out_dir.mkdir(parents=True)

    geo = build_geometry(room, cabinets, aisles)
    summary = build_engineering_summary(room, cabinets, aisles)

    _write_static(out_dir)
    (out_dir / "system" / "blockMeshDict").write_text(_render_block_mesh_dict(geo))
    (out_dir / "system" / "topoSetDict").write_text(_render_topo_set_dict(geo))
    (out_dir / "constant" / "fvOptions").write_text(_render_fv_options(geo))

    _write_zero_fields(out_dir, geo, room.supply_air_temp_c, room.supply_air_flow_m3s)

    readme = f"""# Otomatik üretilmiş OpenFOAM case

Bu dizin, veri merkezi CFD programı tarafından oda/kabin/koridor verilerinden
otomatik üretilmiştir.

Izgara: {geo.nx} x {geo.ny} sütun ({geo.total_blocks} blok), her sütun
{geo.cell_res_xy}x{geo.cell_res_xy}x{geo.cell_res_z} hücre.
Toplam IT yükü: {summary.total_it_load_kw:.2f} kW
Tahmini koridor ΔT: {summary.estimated_delta_t_c:.1f} °C

Çalıştırma sırası (OpenFOAM ortamı kaynaklanmış olmalı):
    blockMesh
    checkMesh
    topoSet
    buoyantSimpleFoam

Sonuçları görüntülemek için: paraFoam veya ParaView (case.foam dosyası oluşturup açın).
"""
    (out_dir / "README_case.md").write_text(readme)
    (out_dir / "case.foam").write_text("")

    return GeneratedCase(case_dir=out_dir, geometry=geo, summary=summary)
