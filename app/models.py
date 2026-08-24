from datetime import datetime, timezone

from sqlalchemy import ForeignKey, String
from sqlalchemy.orm import Mapped, mapped_column, relationship

from .database import Base


def now_utc() -> datetime:
    return datetime.now(timezone.utc)


class Project(Base):
    __tablename__ = "projects"

    id: Mapped[int] = mapped_column(primary_key=True)
    name: Mapped[str] = mapped_column(String(200))
    description: Mapped[str] = mapped_column(String(2000), default="")
    created_at: Mapped[datetime] = mapped_column(default=now_utc)

    rooms: Mapped[list["Room"]] = relationship(back_populates="project", cascade="all, delete-orphan")


class Room(Base):
    """Bir veri merkezi salonu / server odası."""

    __tablename__ = "rooms"

    id: Mapped[int] = mapped_column(primary_key=True)
    project_id: Mapped[int] = mapped_column(ForeignKey("projects.id"))
    name: Mapped[str] = mapped_column(String(200))

    # Oda geometrisi (metre)
    length_x: Mapped[float] = mapped_column(default=10.0)
    width_y: Mapped[float] = mapped_column(default=8.0)
    height_z: Mapped[float] = mapped_column(default=3.0)  # döşemeden tavana oda yüksekliği

    # Yükseltilmiş döşeme (raised floor) plenum yüksekliği
    raised_floor_height: Mapped[float] = mapped_column(default=0.6)

    # Döşeme fayans boyutu (perfore fayans / kablo kanalı modülü)
    tile_size: Mapped[float] = mapped_column(default=0.6)

    # Soğuk koridora üflenen havanın sıcaklığı (CRAC/CRAH çıkışı)
    supply_air_temp_c: Mapped[float] = mapped_column(default=22.0)

    # Perfore fayalardan üflenen toplam debi (m3/s), oda genelinde tahmini
    supply_air_flow_m3s: Mapped[float] = mapped_column(default=2.0)

    notes: Mapped[str] = mapped_column(String(2000), default="")
    created_at: Mapped[datetime] = mapped_column(default=now_utc)

    project: Mapped["Project"] = relationship(back_populates="rooms")
    cabinets: Mapped[list["Cabinet"]] = relationship(back_populates="room", cascade="all, delete-orphan")
    aisles: Mapped[list["Aisle"]] = relationship(back_populates="room", cascade="all, delete-orphan")
    documents: Mapped[list["Document"]] = relationship(back_populates="room", cascade="all, delete-orphan")
    cfd_runs: Mapped[list["CfdRun"]] = relationship(back_populates="room", cascade="all, delete-orphan")


class Cabinet(Base):
    """Sunucu kabini / rack."""

    __tablename__ = "cabinets"

    id: Mapped[int] = mapped_column(primary_key=True)
    room_id: Mapped[int] = mapped_column(ForeignKey("rooms.id"))
    tag: Mapped[str] = mapped_column(String(100))  # örn. "A-01"
    row_name: Mapped[str] = mapped_column(String(100), default="")

    # Kabinin oda içindeki konumu (döşeme üzerinde, sol-alt köşe), metre
    x: Mapped[float] = mapped_column(default=0.0)
    y: Mapped[float] = mapped_column(default=0.0)

    width: Mapped[float] = mapped_column(default=0.6)   # genişlik (x yönü)
    depth: Mapped[float] = mapped_column(default=1.0)    # derinlik (y yönü)
    height: Mapped[float] = mapped_column(default=2.0)   # yükseklik

    power_kw: Mapped[float] = mapped_column(default=5.0)  # ısı yükü (IT gücü)

    # Hava akış yönü: kabin önü hangi koridora bakıyor
    front_orientation: Mapped[str] = mapped_column(String(20), default="+y")  # +x,-x,+y,-y

    room: Mapped["Room"] = relationship(back_populates="cabinets")


class Aisle(Base):
    """Soğuk koridor / sıcak koridor bölgesi (döşeme izdüşümü, dikdörtgen)."""

    __tablename__ = "aisles"

    id: Mapped[int] = mapped_column(primary_key=True)
    room_id: Mapped[int] = mapped_column(ForeignKey("rooms.id"))
    name: Mapped[str] = mapped_column(String(100))
    aisle_type: Mapped[str] = mapped_column(String(10))  # "soguk" | "sicak"

    x: Mapped[float] = mapped_column(default=0.0)
    y: Mapped[float] = mapped_column(default=0.0)
    width_x: Mapped[float] = mapped_column(default=1.2)
    width_y: Mapped[float] = mapped_column(default=4.0)

    containment: Mapped[str] = mapped_column(String(20), default="yok")  # yok|soguk_kapali|sicak_kapali

    room: Mapped["Room"] = relationship(back_populates="aisles")


class Document(Base):
    """Odaya ait yüklenen PDF (kat planı / teknik çizim)."""

    __tablename__ = "documents"

    id: Mapped[int] = mapped_column(primary_key=True)
    room_id: Mapped[int] = mapped_column(ForeignKey("rooms.id"))
    original_filename: Mapped[str] = mapped_column(String(300))
    stored_path: Mapped[str] = mapped_column(String(500))
    description: Mapped[str] = mapped_column(String(1000), default="")
    uploaded_at: Mapped[datetime] = mapped_column(default=now_utc)

    room: Mapped["Room"] = relationship(back_populates="documents")


class CfdRun(Base):
    """Bir odadan üretilen OpenFOAM case çalışması."""

    __tablename__ = "cfd_runs"

    id: Mapped[int] = mapped_column(primary_key=True)
    room_id: Mapped[int] = mapped_column(ForeignKey("rooms.id"))
    case_dir: Mapped[str] = mapped_column(String(500))
    status: Mapped[str] = mapped_column(String(30), default="olusturuldu")
    # olusturuldu -> mesh_calisti -> cozdu -> hata
    log_tail: Mapped[str] = mapped_column(String(8000), default="")
    block_count: Mapped[int] = mapped_column(default=0)
    created_at: Mapped[datetime] = mapped_column(default=now_utc)

    room: Mapped["Room"] = relationship(back_populates="cfd_runs")
