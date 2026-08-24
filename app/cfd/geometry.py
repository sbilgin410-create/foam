"""Oda / kabin / koridor verisinden yapılandırılmış (structured) blockMesh
sütun ızgarası ve rack ısı-kaynağı bölgelerini üreten geometri katmanı.

Yaklaşım: döşeme izdüşümü, fayans boyutuna (tile_size) göre Nx x Ny adet
düşey hex "sütun" bloğuna bölünür. Her sütun döşemeden (z=0) tavana
(z=height_z) kadar uzanır. Sütunun taban yüzü, hangi bölgeye denk geldiğine
göre (soğuk koridor / sıcak koridor-diğer döşeme) bir sınır (patch) grubuna
atanır. Kabinler, gerçek katı geometri olarak mesh'e işlenmez; bunun yerine
ayak izlerine karşılık gelen hücre bölgeleri (cellSet) `fvOptions` ile ısı
kaynağı olarak tanımlanır. Bu, oda ölçekli soğuk/sıcak koridor CFD
analizlerinde yaygın kullanılan, hesap maliyetini makul tutan basitleştirilmiş
bir modelleme yaklaşımıdır.
"""

from __future__ import annotations

import math
from dataclasses import dataclass, field


@dataclass
class RoomSpec:
    length_x: float
    width_y: float
    height_z: float
    raised_floor_height: float
    tile_size: float = 0.6
    supply_air_temp_c: float = 22.0
    supply_air_flow_m3s: float = 2.0


@dataclass
class CabinetSpec:
    tag: str
    x: float
    y: float
    width: float
    depth: float
    height: float
    power_kw: float
    front_orientation: str = "+y"


@dataclass
class AisleSpec:
    name: str
    aisle_type: str  # "soguk" | "sicak"
    x: float
    y: float
    width_x: float
    width_y: float
    containment: str = "yok"


@dataclass
class Column:
    ci: int
    cj: int
    x0: float
    x1: float
    y0: float
    y1: float
    floor_patch: str  # "soguk_giris" | "zemin_sicak_koridor" | "zemin_diger"


@dataclass
class RackZone:
    tag: str
    x0: float
    x1: float
    y0: float
    y1: float
    z0: float
    z1: float
    power_w: float


@dataclass
class CaseGeometry:
    nx: int
    ny: int
    dx: float
    dy: float
    height_z: float
    columns: list[Column]
    racks: list[RackZone]
    cell_res_xy: int
    cell_res_z: int

    @property
    def total_blocks(self) -> int:
        return self.nx * self.ny

    def vertex_index(self, i: int, j: int, k: int) -> int:
        return k * (self.nx + 1) * (self.ny + 1) + j * (self.nx + 1) + i


MAX_BLOCKS = 3000


def _point_in_rect(px: float, py: float, x: float, y: float, w: float, h: float) -> bool:
    return x <= px <= x + w and y <= py <= y + h


def build_geometry(
    room: RoomSpec,
    cabinets: list[CabinetSpec],
    aisles: list[AisleSpec],
    cell_res_xy: int = 2,
    cell_res_z: int = 10,
) -> CaseGeometry:
    if room.length_x <= 0 or room.width_y <= 0 or room.height_z <= 0:
        raise ValueError("Oda boyutları pozitif olmalı")
    if room.tile_size <= 0:
        raise ValueError("Döşeme fayans boyutu pozitif olmalı")

    nx = max(1, round(room.length_x / room.tile_size))
    ny = max(1, round(room.width_y / room.tile_size))

    if nx * ny > MAX_BLOCKS:
        raise ValueError(
            f"Izgara çok büyük olurdu ({nx}x{ny}={nx*ny} blok, sınır {MAX_BLOCKS}). "
            "Döşeme fayans boyutunu (tile_size) büyütün."
        )

    dx = room.length_x / nx
    dy = room.width_y / ny

    cold_rects = [(a.x, a.y, a.width_x, a.width_y) for a in aisles if a.aisle_type == "soguk"]
    hot_rects = [(a.x, a.y, a.width_x, a.width_y) for a in aisles if a.aisle_type == "sicak"]

    columns: list[Column] = []
    for cj in range(ny):
        for ci in range(nx):
            x0, x1 = ci * dx, (ci + 1) * dx
            y0, y1 = cj * dy, (cj + 1) * dy
            cx, cy = (x0 + x1) / 2.0, (y0 + y1) / 2.0

            if any(_point_in_rect(cx, cy, *r) for r in cold_rects):
                patch = "soguk_giris"
            elif any(_point_in_rect(cx, cy, *r) for r in hot_rects):
                patch = "zemin_sicak_koridor"
            else:
                patch = "zemin_diger"

            columns.append(Column(ci, cj, x0, x1, y0, y1, patch))

    racks = [
        RackZone(
            tag=c.tag,
            x0=c.x,
            x1=c.x + c.width,
            y0=c.y,
            y1=c.y + c.depth,
            z0=0.0,
            z1=min(c.height, room.height_z),
            power_w=c.power_kw * 1000.0,
        )
        for c in cabinets
    ]

    return CaseGeometry(
        nx=nx,
        ny=ny,
        dx=dx,
        dy=dy,
        height_z=room.height_z,
        columns=columns,
        racks=racks,
        cell_res_xy=cell_res_xy,
        cell_res_z=cell_res_z,
    )


@dataclass
class EngineeringSummary:
    total_it_load_kw: float
    cold_aisle_count: int
    hot_aisle_count: int
    contained_aisle_count: int
    supply_flow_m3s: float
    estimated_delta_t_c: float
    warnings: list[str] = field(default_factory=list)


AIR_DENSITY = 1.2  # kg/m3, ~22C
AIR_CP = 1006.0  # J/kgK


def build_engineering_summary(room: RoomSpec, cabinets: list[CabinetSpec], aisles: list[AisleSpec]) -> EngineeringSummary:
    total_kw = sum(c.power_kw for c in cabinets)
    cold = [a for a in aisles if a.aisle_type == "soguk"]
    hot = [a for a in aisles if a.aisle_type == "sicak"]
    contained = [a for a in aisles if a.containment != "yok"]

    mass_flow = room.supply_air_flow_m3s * AIR_DENSITY
    delta_t = (total_kw * 1000.0) / (mass_flow * AIR_CP) if mass_flow > 0 else float("inf")

    warnings: list[str] = []
    if not cold:
        warnings.append("Tanımlı soğuk koridor yok: CFD modelinde soğuk hava girişi olmayacak.")
    if not hot:
        warnings.append("Tanımlı sıcak koridor yok: dönüş havası bölgesi belirsiz.")
    if delta_t > 15:
        warnings.append(
            f"Tahmini koridor ΔT çok yüksek (~{delta_t:.1f}°C). Üfleme debisini artırın veya IT yükünü azaltın."
        )
    if not contained and (cold or hot):
        warnings.append("Hiçbir koridor kapatılmamış (containment yok): sıcak/soğuk hava karışımı beklenir.")

    return EngineeringSummary(
        total_it_load_kw=total_kw,
        cold_aisle_count=len(cold),
        hot_aisle_count=len(hot),
        contained_aisle_count=len(contained),
        supply_flow_m3s=room.supply_air_flow_m3s,
        estimated_delta_t_c=delta_t,
        warnings=warnings,
    )
