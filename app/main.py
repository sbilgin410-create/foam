from __future__ import annotations

import shutil
import uuid
from pathlib import Path

from fastapi import FastAPI, Form, HTTPException, Request, UploadFile
from fastapi.responses import FileResponse, RedirectResponse
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates
from sqlalchemy.orm import Session

from . import models
from .cfd import runner
from .cfd.case_generator import generate_case
from .cfd.geometry import AisleSpec, CabinetSpec, RoomSpec, build_engineering_summary
from .database import CASES_DIR, UPLOAD_DIR, Base, SessionLocal, engine

Base.metadata.create_all(bind=engine)

APP_DIR = Path(__file__).resolve().parent
app = FastAPI(title="Veri Merkezi CFD Programı")
app.mount("/static", StaticFiles(directory=APP_DIR / "static"), name="static")
templates = Jinja2Templates(directory=APP_DIR / "templates")


def db_session() -> Session:
    return SessionLocal()


def _room_specs(room: models.Room):
    room_spec = RoomSpec(
        length_x=room.length_x,
        width_y=room.width_y,
        height_z=room.height_z,
        raised_floor_height=room.raised_floor_height,
        tile_size=room.tile_size,
        supply_air_temp_c=room.supply_air_temp_c,
        supply_air_flow_m3s=room.supply_air_flow_m3s,
    )
    cabinet_specs = [
        CabinetSpec(
            tag=c.tag,
            x=c.x,
            y=c.y,
            width=c.width,
            depth=c.depth,
            height=c.height,
            power_kw=c.power_kw,
            front_orientation=c.front_orientation,
        )
        for c in room.cabinets
    ]
    aisle_specs = [
        AisleSpec(
            name=a.name,
            aisle_type=a.aisle_type,
            x=a.x,
            y=a.y,
            width_x=a.width_x,
            width_y=a.width_y,
            containment=a.containment,
        )
        for a in room.aisles
    ]
    return room_spec, cabinet_specs, aisle_specs


# --------------------------------------------------------------------------
# Projeler
# --------------------------------------------------------------------------

@app.get("/")
def index(request: Request):
    db = db_session()
    try:
        projects = db.query(models.Project).order_by(models.Project.created_at.desc()).all()
        return templates.TemplateResponse(request, "index.html", {"projects": projects})
    finally:
        db.close()


@app.post("/projects")
def create_project(name: str = Form(...), description: str = Form("")):
    db = db_session()
    try:
        p = models.Project(name=name, description=description)
        db.add(p)
        db.commit()
        return RedirectResponse(f"/projects/{p.id}", status_code=303)
    finally:
        db.close()


@app.get("/projects/{project_id}")
def project_detail(request: Request, project_id: int):
    db = db_session()
    try:
        project = db.get(models.Project, project_id)
        if not project:
            raise HTTPException(404, "Proje bulunamadı")
        return templates.TemplateResponse(request, "project_detail.html", {"project": project})
    finally:
        db.close()


@app.post("/projects/{project_id}/rooms")
def create_room(
    project_id: int,
    name: str = Form(...),
    length_x: float = Form(10.0),
    width_y: float = Form(8.0),
    height_z: float = Form(3.0),
    raised_floor_height: float = Form(0.6),
    tile_size: float = Form(0.6),
    supply_air_temp_c: float = Form(22.0),
    supply_air_flow_m3s: float = Form(2.0),
    notes: str = Form(""),
):
    db = db_session()
    try:
        project = db.get(models.Project, project_id)
        if not project:
            raise HTTPException(404, "Proje bulunamadı")
        room = models.Room(
            project_id=project_id,
            name=name,
            length_x=length_x,
            width_y=width_y,
            height_z=height_z,
            raised_floor_height=raised_floor_height,
            tile_size=tile_size,
            supply_air_temp_c=supply_air_temp_c,
            supply_air_flow_m3s=supply_air_flow_m3s,
            notes=notes,
        )
        db.add(room)
        db.commit()
        return RedirectResponse(f"/rooms/{room.id}", status_code=303)
    finally:
        db.close()


# --------------------------------------------------------------------------
# Oda detayı
# --------------------------------------------------------------------------

@app.get("/rooms/{room_id}")
def room_detail(request: Request, room_id: int):
    db = db_session()
    try:
        room = db.get(models.Room, room_id)
        if not room:
            raise HTTPException(404, "Oda bulunamadı")
        room_spec, cabinet_specs, aisle_specs = _room_specs(room)
        summary = None
        if cabinet_specs or aisle_specs:
            summary = build_engineering_summary(room_spec, cabinet_specs, aisle_specs)
        runs = (
            db.query(models.CfdRun)
            .filter(models.CfdRun.room_id == room_id)
            .order_by(models.CfdRun.created_at.desc())
            .all()
        )
        return templates.TemplateResponse(
            request,
            "room_detail.html",
            {"room": room, "summary": summary, "runs": runs},
        )
    finally:
        db.close()


@app.post("/rooms/{room_id}/cabinets")
def add_cabinet(
    room_id: int,
    tag: str = Form(...),
    row_name: str = Form(""),
    x: float = Form(0.0),
    y: float = Form(0.0),
    width: float = Form(0.6),
    depth: float = Form(1.0),
    height: float = Form(2.0),
    power_kw: float = Form(5.0),
    front_orientation: str = Form("+y"),
):
    db = db_session()
    try:
        if not db.get(models.Room, room_id):
            raise HTTPException(404, "Oda bulunamadı")
        db.add(
            models.Cabinet(
                room_id=room_id,
                tag=tag,
                row_name=row_name,
                x=x,
                y=y,
                width=width,
                depth=depth,
                height=height,
                power_kw=power_kw,
                front_orientation=front_orientation,
            )
        )
        db.commit()
        return RedirectResponse(f"/rooms/{room_id}", status_code=303)
    finally:
        db.close()


@app.post("/cabinets/{cabinet_id}/delete")
def delete_cabinet(cabinet_id: int):
    db = db_session()
    try:
        c = db.get(models.Cabinet, cabinet_id)
        if not c:
            raise HTTPException(404, "Kabin bulunamadı")
        room_id = c.room_id
        db.delete(c)
        db.commit()
        return RedirectResponse(f"/rooms/{room_id}", status_code=303)
    finally:
        db.close()


@app.post("/rooms/{room_id}/aisles")
def add_aisle(
    room_id: int,
    name: str = Form(...),
    aisle_type: str = Form(...),
    x: float = Form(0.0),
    y: float = Form(0.0),
    width_x: float = Form(1.2),
    width_y: float = Form(4.0),
    containment: str = Form("yok"),
):
    db = db_session()
    try:
        if not db.get(models.Room, room_id):
            raise HTTPException(404, "Oda bulunamadı")
        db.add(
            models.Aisle(
                room_id=room_id,
                name=name,
                aisle_type=aisle_type,
                x=x,
                y=y,
                width_x=width_x,
                width_y=width_y,
                containment=containment,
            )
        )
        db.commit()
        return RedirectResponse(f"/rooms/{room_id}", status_code=303)
    finally:
        db.close()


@app.post("/aisles/{aisle_id}/delete")
def delete_aisle(aisle_id: int):
    db = db_session()
    try:
        a = db.get(models.Aisle, aisle_id)
        if not a:
            raise HTTPException(404, "Koridor bulunamadı")
        room_id = a.room_id
        db.delete(a)
        db.commit()
        return RedirectResponse(f"/rooms/{room_id}", status_code=303)
    finally:
        db.close()


# --------------------------------------------------------------------------
# PDF belgeleri
# --------------------------------------------------------------------------

@app.post("/rooms/{room_id}/documents")
async def upload_document(room_id: int, file: UploadFile, description: str = Form("")):
    db = db_session()
    try:
        room = db.get(models.Room, room_id)
        if not room:
            raise HTTPException(404, "Oda bulunamadı")
        if not file.filename.lower().endswith(".pdf"):
            raise HTTPException(400, "Yalnızca PDF dosyaları kabul edilir")

        stored_name = f"{uuid.uuid4().hex}.pdf"
        stored_path = UPLOAD_DIR / stored_name
        with stored_path.open("wb") as out:
            shutil.copyfileobj(file.file, out)

        db.add(
            models.Document(
                room_id=room_id,
                original_filename=file.filename,
                stored_path=str(stored_path),
                description=description,
            )
        )
        db.commit()
        return RedirectResponse(f"/rooms/{room_id}", status_code=303)
    finally:
        db.close()


@app.get("/documents/{document_id}/file")
def get_document(document_id: int):
    db = db_session()
    try:
        doc = db.get(models.Document, document_id)
        if not doc:
            raise HTTPException(404, "Belge bulunamadı")
        return FileResponse(doc.stored_path, media_type="application/pdf", filename=doc.original_filename)
    finally:
        db.close()


@app.post("/documents/{document_id}/delete")
def delete_document(document_id: int):
    db = db_session()
    try:
        doc = db.get(models.Document, document_id)
        if not doc:
            raise HTTPException(404, "Belge bulunamadı")
        room_id = doc.room_id
        Path(doc.stored_path).unlink(missing_ok=True)
        db.delete(doc)
        db.commit()
        return RedirectResponse(f"/rooms/{room_id}", status_code=303)
    finally:
        db.close()


# --------------------------------------------------------------------------
# CFD case üretimi ve çalıştırma (OpenFOAM)
# --------------------------------------------------------------------------

@app.post("/rooms/{room_id}/cfd/generate")
def generate_cfd_case(room_id: int):
    db = db_session()
    try:
        room = db.get(models.Room, room_id)
        if not room:
            raise HTTPException(404, "Oda bulunamadı")
        if not room.cabinets:
            raise HTTPException(400, "Önce en az bir kabin eklemelisiniz")
        if not room.aisles:
            raise HTTPException(400, "Önce en az bir koridor (soğuk/sıcak) eklemelisiniz")

        room_spec, cabinet_specs, aisle_specs = _room_specs(room)
        case_dir = CASES_DIR / f"room_{room_id}_{uuid.uuid4().hex[:8]}"
        try:
            result = generate_case(room_spec, cabinet_specs, aisle_specs, case_dir)
        except ValueError as exc:
            raise HTTPException(400, str(exc))

        run = models.CfdRun(
            room_id=room_id,
            case_dir=str(result.case_dir),
            status="olusturuldu",
            block_count=result.geometry.total_blocks,
            log_tail="Case dosyaları üretildi.",
        )
        db.add(run)
        db.commit()
        return RedirectResponse(f"/rooms/{room_id}", status_code=303)
    finally:
        db.close()


@app.post("/cfd/{run_id}/mesh")
def mesh_cfd_run(run_id: int):
    db = db_session()
    try:
        run = db.get(models.CfdRun, run_id)
        if not run:
            raise HTTPException(404, "CFD çalışması bulunamadı")
        results = runner.run_mesh(Path(run.case_dir))
        run.log_tail = "\n\n".join(f"$ {r.command}\n{r.output}" for r in results)[-8000:]
        run.status = "mesh_calisti" if all(r.ok for r in results) else "hata"
        db.commit()
        return RedirectResponse(f"/rooms/{run.room_id}", status_code=303)
    finally:
        db.close()


@app.post("/cfd/{run_id}/solve")
def solve_cfd_run(run_id: int):
    db = db_session()
    try:
        run = db.get(models.CfdRun, run_id)
        if not run:
            raise HTTPException(404, "CFD çalışması bulunamadı")
        result = runner.run_solver(Path(run.case_dir))
        run.log_tail = f"$ {result.command}\n{result.output}"[-8000:]
        run.status = "cozdu" if result.ok else "hata"
        db.commit()
        return RedirectResponse(f"/rooms/{run.room_id}", status_code=303)
    finally:
        db.close()


@app.post("/cfd/{run_id}/delete")
def delete_cfd_run(run_id: int):
    db = db_session()
    try:
        run = db.get(models.CfdRun, run_id)
        if not run:
            raise HTTPException(404, "CFD çalışması bulunamadı")
        room_id = run.room_id
        shutil.rmtree(run.case_dir, ignore_errors=True)
        db.delete(run)
        db.commit()
        return RedirectResponse(f"/rooms/{room_id}", status_code=303)
    finally:
        db.close()


@app.get("/openfoam-status")
def openfoam_status():
    return {"kurulu": runner.openfoam_available()}
