"""Laporan Perjalanan Dinas: laporan kronologis kegiatan + foto kegiatan per Surat Tugas.
Dipakai pada halaman 'Laporan Perjalanan Dinas' di paket Srikandi F4 (lihat paket_f4.py). Foto disimpan ternormalisasi (JPEG, sisi terpanjang 1600 px)."""
import datetime as dt
import io

from fastapi import APIRouter, Body, Depends, Request
from fastapi.responses import Response
from PIL import Image, ImageOps

from .core import Gagal, audit, auth, get_db


router = APIRouter(prefix="/api/laporan-kegiatan")
MAKS_FOTO = 6
MAKS_BYTE = 8 * 1024 * 1024

SKEMA = """
CREATE TABLE IF NOT EXISTS laporan_kegiatan(
  st_id INTEGER PRIMARY KEY REFERENCES surat_tugas(id), kronologis TEXT NOT NULL DEFAULT '', tanggal TEXT,
  diubah_oleh TEXT, diubah_pada TEXT DEFAULT (datetime('now','localtime')));
CREATE TABLE IF NOT EXISTS laporan_foto(
  id INTEGER PRIMARY KEY, st_id INTEGER NOT NULL REFERENCES surat_tugas(id), nama TEXT NOT NULL, ukuran INTEGER NOT NULL, data BLOB NOT NULL,
  diunggah_oleh TEXT, diunggah_pada TEXT DEFAULT (datetime('now','localtime')));
CREATE INDEX IF NOT EXISTS ix_laporan_foto ON laporan_foto(st_id);
"""


def pasang(con) -> None:
    con.executescript(SKEMA)
    # Pejabat 'Verifikator' (halaman Perhitungan SPPD Rampung); isi dari contoh format baru, dapat diubah di Master Data → Pejabat.
    con.execute("""INSERT INTO pejabat(peran,nama,nip,pangkat,jabatan,aktif)
                   SELECT 'Verifikator','MUHAMAD HUSIN, S.K.M','197007141997031012','','Verifikator UPT Puskesmas Melati',1
                   WHERE NOT EXISTS (SELECT 1 FROM pejabat WHERE peran LIKE '%Verifikator%')""")


def _st(db, user, sid, ubah=False):
    from .surat import _boleh_lihat   # impor tertunda (surat.py mengimpor modul ini)
    s = db.execute("SELECT * FROM surat_tugas WHERE id=?", (sid,)).fetchone()
    if not s:
        raise Gagal("Surat Tugas tidak ditemukan.", 404)
    boleh, _ = _boleh_lihat(db, user, s)
    if not boleh:
        raise Gagal("Anda tidak berhak atas Surat Tugas ini.", 403)
    if ubah and s["status"] != "Terbit":
        raise Gagal("Surat Tugas yang dibatalkan tidak dapat diberi laporan.")
    return s


def ambil(db, sid) -> dict:
    """Dipakai juga oleh pembuat dokumen: {'kronologis','tanggal','foto':[{id,nama,ukuran}]}."""
    r = db.execute("SELECT kronologis, tanggal FROM laporan_kegiatan WHERE st_id=?", (sid,)).fetchone() or {"kronologis": "", "tanggal": None}
    foto = db.execute("SELECT id, nama, ukuran, diunggah_oleh, diunggah_pada FROM laporan_foto WHERE st_id=? ORDER BY id", (sid,)).fetchall()
    return {"kronologis": r["kronologis"] or "", "tanggal": r["tanggal"], "foto": foto}


def data_foto(db, sid) -> list[bytes]:
    return [r["data"] for r in db.execute("SELECT data FROM laporan_foto WHERE st_id=? ORDER BY id", (sid,)).fetchall()]


@router.get("/{sid:int}")
def lihat(sid: int, user=Depends(auth), db=Depends(get_db)):
    _st(db, user, sid)
    return ambil(db, sid)


@router.put("/{sid:int}")
def simpan(sid: int, body: dict = Body(default={}), user=Depends(auth), db=Depends(get_db)):
    s = _st(db, user, sid, ubah=True)
    krono = str(body.get("kronologis") or "").replace("\r", "").strip()
    if len(krono) > 4000:
        raise Gagal("Laporan kronologis maksimal 4.000 karakter.")
    tanggal = str(body.get("tanggal") or "").strip() or None
    if tanggal:
        try:
            tanggal = dt.date.fromisoformat(tanggal[:10]).isoformat()
        except ValueError:
            raise Gagal("Tanggal laporan tidak valid.")
    lama = db.execute("SELECT kronologis, tanggal FROM laporan_kegiatan WHERE st_id=?", (sid,)).fetchone()
    db.execute("""INSERT INTO laporan_kegiatan(st_id,kronologis,tanggal,diubah_oleh) VALUES(?,?,?,?)
                  ON CONFLICT(st_id) DO UPDATE SET kronologis=excluded.kronologis, tanggal=excluded.tanggal, diubah_oleh=excluded.diubah_oleh, diubah_pada=datetime('now','localtime')""",
               (sid, krono, tanggal, user["username"]))
    audit(db, user, "laporan_kegiatan", sid, "UBAH" if lama else "TAMBAH", lama, {"kronologis": krono[:200], "tanggal": tanggal})
    return ambil(db, sid)


def _normal(data: bytes) -> bytes:
    try:
        im = Image.open(io.BytesIO(data))
        im = ImageOps.exif_transpose(im).convert("RGB")
    except Exception:
        raise Gagal("Berkas bukan foto yang dapat dibaca. Gunakan JPG, PNG, atau WebP.")
    im.thumbnail((1600, 1600))
    b = io.BytesIO()
    im.save(b, "JPEG", quality=82, optimize=True)
    return b.getvalue()


@router.post("/{sid:int}/foto")
async def unggah(sid: int, request: Request, nama: str = "foto", user=Depends(auth), db=Depends(get_db)):
    """Unggah satu foto kegiatan (badan permintaan = berkas mentah). Maksimal 6 foto per Surat Tugas."""
    _st(db, user, sid, ubah=True)
    data = await request.body()
    if not data:
        raise Gagal("Berkas kosong.")
    if len(data) > MAKS_BYTE:
        raise Gagal(f"Foto terlalu besar ({len(data) // 1024} KB); maksimal {MAKS_BYTE // 1024 // 1024} MB.")
    if db.execute("SELECT COUNT(*) c FROM laporan_foto WHERE st_id=?", (sid,)).fetchone()["c"] >= MAKS_FOTO:
        raise Gagal(f"Maksimal {MAKS_FOTO} foto per Surat Tugas.")
    jpg = _normal(data)
    bersih = "".join(ch for ch in nama if ch.isalnum() or ch in " ._-")[:60].strip(". ") or "foto"
    fid = db.execute("INSERT INTO laporan_foto(st_id,nama,ukuran,data,diunggah_oleh) VALUES(?,?,?,?,?)", (sid, bersih, len(jpg), jpg, user["username"])).lastrowid
    audit(db, user, "laporan_foto", fid, "UNGGAH", None, {"st_id": sid, "nama": bersih, "ukuran": len(jpg)})
    return {"id": fid, "nama": bersih, "ukuran": len(jpg)}


@router.get("/foto/{fid:int}")
def foto(fid: int, user=Depends(auth), db=Depends(get_db)):
    r = db.execute("SELECT * FROM laporan_foto WHERE id=?", (fid,)).fetchone()
    if not r:
        raise Gagal("Foto tidak ditemukan.", 404)
    _st(db, user, r["st_id"])
    return Response(r["data"], media_type="image/jpeg", headers={"Cache-Control": "private, max-age=3600"})


@router.delete("/foto/{fid:int}")
def hapus(fid: int, user=Depends(auth), db=Depends(get_db)):
    r = db.execute("SELECT id, st_id, nama FROM laporan_foto WHERE id=?", (fid,)).fetchone()
    if not r:
        raise Gagal("Foto tidak ditemukan.", 404)
    _st(db, user, r["st_id"], ubah=True)
    db.execute("DELETE FROM laporan_foto WHERE id=?", (fid,))
    audit(db, user, "laporan_foto", fid, "HAPUS", {"st_id": r["st_id"], "nama": r["nama"]}, None)
    return {"ok": 1}
