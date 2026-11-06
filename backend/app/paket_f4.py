"""Paket Srikandi format baru (kertas F4 / Folio 21,59 x 35,56 cm) — meniru berkas contoh 1197.pdf / 1198.pdf:

  1 Surat Tugas · 2-3 SPD (depan & belakang) · 4 Surat Pernyataan · 5 Rincian Perjalanan Dinas + Perhitungan SPPD Rampung ·
  6 Laporan Perjalanan Dinas (kronologis + foto kegiatan) · 7 Kwitansi.

Semua halaman digambar langsung di kanvas dengan koordinat dari contoh (satuan pt, titik nol di kiri-ATAS halaman) supaya tata letaknya
sama persis; bagian yang panjangnya berubah (jumlah petugas, teks bungkus, foto) menggeser blok di bawahnya.
mode='srikandi' memakai kode ${nomor_naskah}/${ttd_pengirim}/${nama_pengirim} yang diisi Srikandi; mode='cetak' mencetak nama penandatangan."""
import io
from pathlib import Path

from PIL import Image
from reportlab.lib.utils import ImageReader, simpleSplit
from reportlab.pdfbase.pdfmetrics import stringWidth
from reportlab.pdfgen import canvas

from .core import Gagal
from .dokumen import terbilang, tgl

ASSETS = Path(__file__).parent / "assets"
W, H = 612.0, 1008.0           # F4 / Folio 8,5 x 14 inci
REG, BOLD, ITAL, SERIF, BOLDITAL = "Helvetica", "Helvetica-Bold", "Helvetica-Oblique", "Times-Roman", "Helvetica-BoldOblique"
T_NOMOR, T_TTD, T_NAMA = "${nomor_naskah}", "${ttd_pengirim}", "${nama_pengirim}"
MAKS_FOTO = 6
MAKS_PETUGAS = 11


def rps(n) -> str:
    return "Rp " + f"{int(round(n or 0)):,}".replace(",", ".")


def _kn(v) -> tuple[str, str]:
    a, _, b = str(v or "").partition("|")
    return a.strip(), b.strip()


def _pg(p: dict) -> str:
    gol = str(p.get("golongan") or "").replace("/", " ").strip()
    return " / ".join(x for x in [p.get("pangkat"), gol] if x and x != "-")


class Kv:
    """Pembungkus kanvas: koordinat y dihitung dari ATAS halaman (seperti hasil ekstraksi PDF contoh)."""

    def __init__(self, c: canvas.Canvas):
        self.c = c

    def t(self, x, top, s, size=9.0, font=REG, align="l"):
        s = str(s if s is not None else "")
        if not s:
            return
        self.c.setFont(font, size)
        y = H - (top + 0.905 * size)
        if align == "l":
            self.c.drawString(x, y, s)
        elif align == "c":
            self.c.drawCentredString(x, y, s)
        else:
            self.c.drawRightString(x, y, s)

    def lines(self, x, top, text, width, size=9.0, pitch=None, font=REG, just=False, indent=0.0) -> float:
        """Teks bungkus (opsional rata kiri-kanan); mengembalikan y (atas) baris berikutnya."""
        pitch = pitch or size * 1.15
        parts = []
        for para in str(text or "").split("\n"):
            parts.append(simpleSplit(para, font, size, width - indent) if para.strip() else [""])
        y, first = top, True
        for lines in parts:
            for i, ln in enumerate(lines):
                last = i == len(lines) - 1
                xx = x + (indent if first else 0)
                if just and not last and " " in ln.strip():
                    self._just(xx, y, ln, width - (indent if first else 0), size, font)
                else:
                    self.t(xx, y, ln, size, font)
                first = False
                y += pitch
        return y

    def _just(self, x, top, ln, width, size, font):
        words = ln.split()
        if len(words) < 2:
            self.t(x, top, ln, size, font)
            return
        tot = sum(stringWidth(w, font, size) for w in words)
        gap = (width - tot) / (len(words) - 1)
        self.c.setFont(font, size)
        yy = H - (top + 0.905 * size)
        xx = x
        for w in words:
            self.c.drawString(xx, yy, w)
            xx += stringWidth(w, font, size) + gap

    def hl(self, x0, x1, y, w=1.0):
        self.c.setLineWidth(w)
        self.c.line(x0, H - y, x1, H - y)

    def vl(self, x, y0, y1, w=1.0):
        self.c.setLineWidth(w)
        self.c.line(x, H - y0, x, H - y1)

    def img(self, path, x, top, w, h):
        self.c.drawImage(ImageReader(str(path)), x, H - top - h, w, h, mask="auto")

    def foto(self, data: bytes, x, top, w, h, fokus_y=0.38):
        """Foto diisi penuh (cover) ke kotak w x h; bagian yang terpotong diambil dari fokus vertikal atas."""
        im = Image.open(io.BytesIO(data)).convert("RGB")
        iw, ih = im.size
        tr = w / h
        if iw / ih > tr:
            nw = int(ih * tr)
            x0 = (iw - nw) // 2
            im = im.crop((x0, 0, x0 + nw, ih))
        else:
            nh = int(iw / tr)
            y0 = int((ih - nh) * fokus_y)
            im = im.crop((0, y0, iw, y0 + nh))
        im = im.resize((int(w * 4), int(h * 4)))
        b = io.BytesIO()
        im.save(b, "JPEG", quality=85)
        b.seek(0)
        self.c.drawImage(ImageReader(b), x, H - top - h, w, h)


# ---------------------------------------------------------------- kop
def _kop(k: Kv, kopd: dict, *, y0: float, cx: float, logo: tuple, rule: tuple, tebal3_ukuran=16, tebal2_ukuran=16):
    """logo=(x, top, w, h); rule=(x0, x1, y, tebal)."""
    k.img(ASSETS / "lambang-kapuas.png", *logo)
    k.t(cx, y0, kopd.get("baris1", ""), 14, REG, "c")
    k.t(cx, y0 + 17.8, kopd.get("baris2", ""), tebal2_ukuran, BOLD, "c")
    k.t(cx, y0 + 35.8, kopd.get("baris3", ""), tebal3_ukuran, BOLD, "c")
    al = [x for x in str(kopd.get("alamat") or "").split("\n") if x.strip()]
    for i, s in enumerate(al[:2]):
        k.t(cx, y0 + 54 + 12 * i, s, 10, REG, "c")
    k.hl(rule[0], rule[1], rule[2], rule[3])


def _tte(k: Kv, mode, isi, *, box, tok_x, teks_x, top_box, logo, size=9.0):
    """Kotak 'Ditandatangani secara elektronik oleh' + kode ${ttd_pengirim}/${nama_pengirim} (Srikandi)."""
    x0, x1 = box
    ttd = isi["ttd"]
    k.c.setLineWidth(1.0)
    k.c.rect(x0, H - top_box - 65, x1 - x0, 65)
    k.img(ASSETS / "lambang-kapuas.png", *logo)
    k.t(teks_x, top_box + 5.5, "Ditandatangani secara elektronik oleh:", size)
    k.t(teks_x, top_box + 5.5 + 12, ttd.get("jabatan") or "", size)
    k.t(teks_x, top_box + 5.5 + 30, T_NAMA if mode == "srikandi" else (ttd.get("nama") or ""), size)
    if ttd.get("nip"):
        k.t(teks_x, top_box + 5.5 + 42, f"NIP {ttd['nip']}", size)
    if mode == "srikandi":
        k.t(tok_x, top_box + (23.8 if size > 10 else 22.8), T_TTD, size, REG, "r")


def _nomor(st, mode):
    return T_NOMOR if mode == "srikandi" else (st.get("nomor_srikandi") or st["nomor"])


def _nomor_final(st):
    return st.get("nomor_srikandi") or st["nomor"]


def _pembagi_petugas(isi):
    diperintah = [p for p in isi["petugas"] if p.get("nip") and p.get("status") != "Non ASN"] or isi["petugas"]
    return diperintah, [p for p in isi["petugas"] if p not in diperintah]


# ---------------------------------------------------------------- halaman 1: Surat Tugas
def hal_st(k: Kv, isi, st, mode):
    n = len(isi["petugas"])
    if n > MAKS_PETUGAS:
        raise Gagal(f"Paket Srikandi F4 memuat paling banyak {MAKS_PETUGAS} petugas per Surat Tugas (ini {n}). Pecah menjadi dua ST.")
    _kop(k, isi["kop"], y0=48.6, cx=350.8, logo=(69, 49, 76, 78), rule=(68.5, 554.5, 130.6, 2.0))
    k.t(311.5, 142.1, "SURAT TUGAS", 14, REG, "c")
    nom = _nomor(st, mode)
    k.t(173.5 + stringWidth(T_NOMOR, REG, 11) / 2, 159.9, f"NOMOR : {nom}", 11, REG, "c") if mode != "srikandi" else k.t(173.5, 159.9, f"NOMOR : {nom}", 11)
    k.t(68.5, 183.9, "Dasar", 11)
    k.t(124, 183.9, ":", 11)
    dasar = str(st.get("dasar") or "").strip() or "Peraturan Bupati Kapuas Nomor 8 Tahun 2026 Tanggal 30 April 2026 Tentang Perjalanan Dinas"
    y = k.lines(140.5, 183.9, dasar, 414, 11, 12.6, just=True)
    k.t(311.5, 225.9 + (y - 209.1), "MEMERINTAHKAN :", 11, BOLD, "c")
    y = 250.6 + (y - 209.1)
    k.t(68.5, y, "Kepada", 11)
    k.t(124, y, ":", 11)
    for i, p in enumerate(isi["petugas"], 1):
        if i == 1 or True:
            k.t(134.5, y + 0.2, str(i), 11)
        for j, (lb, v) in enumerate([("Nama", p["nama"]), ("Pangkat/Gol", _pg(p) or "-"), ("NIP", p.get("nip") or "-"), ("Jabatan", p.get("jabatan") or "-")]):
            yy = y + 12 * j
            k.t(164.5, yy, "abcd"[j] + ".", 11)
            k.t(182.5, yy, lb, 11)
            k.t(262, yy, ":", 11)
            k.t(272.5, yy, v, 11)
        y += 54
    # Untuk
    y = y + (358.6 - 358.6)
    k.t(68.5, y, "Untuk", 11)
    k.t(124, y, ": 1", 11)
    k.t(152.5, y, "Melaksanakan perjalanan dinas dalam rangka:", 11)
    y = k.lines(152.5, y + 12, st["maksud"], 402, 11, 12.4, just=True)
    k.t(134.5, y, "2", 11)
    hari = isi["hari"]
    for lb, v, dy in [("Lama Penugasan", f"{hari} ({terbilang(hari).replace(' rupiah', '').capitalize()}) Hari", 0), ("Terhitung Mulai Tanggal", tgl(isi["mulai"]), 12), ("Kembali Tanggal", tgl(isi["selesai"]), 24)]:
        k.t(152.5, y + dy, lb, 11)
        k.t(286, y + dy, ":", 11)
        k.t(296.5, y + dy + (0.2 if dy else 0), v, 11)
    y += 36
    k.t(134.5, y, "3", 11)
    k.t(152.5, y, "Melaporkan hasil perjalanan dinas kepada yang mengeluarkan surat tugas", 11)
    y += 12
    k.t(134.5, y, "4", 11)
    y = k.lines(152.5, y, f"Pembebanan Biaya pada DPA Dinas Kesehatan Unit Puskesmas Melati Nomor DPA : {isi.get('dpa') or '-'}", 402, 11, 12.6, just=True)
    ty = y + 29
    k.t(356.5, ty, f"{isi['kota']}, {tgl(st['tanggal_surat'])}", 11)
    _tte(k, mode, isi, box=(266.5, 554.5), tok_x=262.0, teks_x=356.5, top_box=ty + 18.2, logo=(273, ty + 25, 64, 59), size=11.0)
    k.t(W - 104.2, 987.6, f"Page :{st.get('urut', '')}", 10, ITAL)


# ---------------------------------------------------------------- halaman 2: SPD depan
def hal_spd_depan(k: Kv, isi, st, mode):
    diperintah, ikut = _pembagi_petugas(isi)
    _kop(k, isi["kop"], y0=42.6, cx=324.0, logo=(30, 43, 77, 86), rule=(23.6, 569.6, 123.7, 1.5))
    k.t(335.6, 125.9, "Lembar ke", 9)
    k.t(335.6, 137.9, "Kode No", 9)
    k.t(335.6, 149.9, "Nomor", 9)
    for yy in (125.9, 137.9, 149.9):
        k.t(391.4, yy, ":", 9)
    k.t(401.6, 149.9, _nomor(st, mode), 9)
    k.t(225.1 + stringWidth("SURAT  PERJALANAN DINAS", REG, 11) / 2, 168.3, "SURAT  PERJALANAN DINAS", 11, REG, "c")

    ang = isi.get("anggaran") or {}
    ins_k, ins_n = _kn(ang.get("instansi"))
    prog = [_kn(x) for x in str(ang.get("program") or "").split("\n") if x.strip()]
    keg_k, keg_n = _kn(ang.get("kegiatan"))
    rek_k, rek_n = _kn(ang.get("rekening") or (isi.get("kode_rekening") or ""))

    X = (24.1, 48.7, 246.1, 569.2)
    top = 193.8
    k.hl(X[0], X[3], top, 1.0)
    rows = []   # (top, bottom)

    def baris(tinggi, nomor, label, isi_fn, label_dy=4.9):
        nonlocal top
        bawah = top + tinggi
        k.t(33.1 if len(nomor) < 2 else 30.6, top + label_dy if nomor != "10" else top - 1.2, nomor, 9)
        if label:
            for i, ln in enumerate(str(label).split("\n")):
                k.t(53.6, top + label_dy + 12 * i if nomor != "10" else top - 1.2, ln, 9)
        if isi_fn:
            isi_fn(top)
        k.hl(X[0], X[3], bawah, 1.0)
        rows.append((top, bawah))
        top = bawah

    baris(26.3, "1", "Kuasa Pengguna Anggaran", lambda t: k.t(257.6, t + 4.9, isi["ttd"]["jabatan"], 9))

    def r2(t):
        for i, p in enumerate(diperintah):
            yy = t + 4.9 + 15 * i
            k.t(257.6, yy + 0.6, str(i + 1), 9)
            k.t(275.6, yy, p["nama"], 9)
            k.t(418.4, yy, "/", 9)
            k.t(434.1, yy, f"NIP.{p.get('nip') or '-'}", 9)
    baris(6.3 + 15 * len(diperintah), "2", "Nama NIP Pegawai yang diperintah", r2)

    def r3(t):
        k.t(257.6, t + 4.5, "a", 9)
        for i, p in enumerate(diperintah):
            k.t(275.6, t + 4.5 + 13.5 * i, _pg(p) or "-", 9)
    baris(6.0 + 13.5 * len(diperintah), "3", "a. Pangkat dan Golongan", r3, 4.5)

    def r4(t):
        k.t(257.6, t + 4.4, "b", 9)
        for i, p in enumerate(diperintah):
            k.t(275.6, t + 4.4 + 12.8 * i, p.get("jabatan") or "-", 9)
    baris(5.6 + 12.8 * len(diperintah), "", "b. Jabatan/Instansi", r4, 4.4)
    baris(27.3, "", "c. Tingkat Pegawai", lambda t: (k.t(257.6, t + 4.8, "c", 9), k.t(275.6, t + 4.8, " ".join(str(p.get("tingkat") or "") for p in diperintah), 9)), 4.8)

    ln_maksud = simpleSplit(st["maksud"], REG, 8, 292)
    baris(max(25.0, 7.5 + 9.2 * len(ln_maksud)), "4", "Maksud Perjalanan Dinas", lambda t: k.lines(257.6, t + 5.0, st["maksud"], 292, 8, 9.2, just=True))
    baris(20.0, "5", "Alat angkut yang digunakan", lambda t: k.t(257.6, t + 4.4, isi.get("alat_angkutan") or "Angkutan darat", 9), 4.4)

    def r6(t):
        k.t(257.6, t + 2.4, "a.", 9)
        k.t(275.6, t + 2.4, isi.get("tempat_berangkat_instansi") or "UPT  PUSKESMAS MELATI", 9)
        k.t(257.6, t + 14.4, "b.", 9)
        k.t(275.6, t + 14.4, isi["lokasi"], 9)
    baris(30.5, "6", "a. Tempat Berangkat\nb. Tempat Tujuan", r6, 2.4)

    def r7(t):
        for i, (a, v) in enumerate([("a.", f"{isi['hari']} ({terbilang(isi['hari']).replace(' rupiah', '').capitalize()}) Hari"), ("b.", tgl(isi["mulai"])), ("c.", tgl(isi["selesai"]))]):
            k.t(257.6, t + 1.9 + 12 * i, a, 9)
            k.t(269.6, t + 1.9 + 12 * i, v, 9)
    baris(40.8, "7", "a. Lama Perjalanan Dinas\nb. Tanggal berangkat\nc. Tanggal harus kembali", r7, 1.9)

    def r8(t):
        k.t(257.6, t + 3.8, "Keterangan", 9)
        for i, p in enumerate(ikut):
            k.t(53.6, t + 3.8 + 12 * (i + 1), p["nama"], 9)
            k.t(257.6, t + 3.8 + 12 * (i + 1), p.get("jabatan") or "", 9)
    baris(max(35.7, 12 * (len(ikut) + 1) + 11.7), "8", "Pengikut", r8, 3.8)

    # 9. Pembebanan anggaran (tinggi menyesuaikan teks program)
    t9 = top
    k.t(33.1, t9 + 4.9, "9", 9)
    k.t(53.6, t9 + 4.9, "Pembebanan Anggaran", 9)
    k.t(53.6, t9 + 16.9, "a. Kode dan Nama Instansi", 9)
    k.t(53.6, t9 + 28.9, "b. Kode dan Nama Program", 9)
    y = t9 + 16.9
    k.t(251.6, y, "a.", 9)
    k.t(269.6, y, ins_k, 9)
    k.t(377.6, y, f"({ins_n})" if ins_n else "", 9)
    y += 12
    k.t(251.6, y, "b.", 9)
    for i, (pk, pn) in enumerate(prog or [("", "")]):
        if i:
            y += 1.8
        k.t(269.6, y, pk, 9)
        y += 12.1
        if pn:
            y = k.lines(269.6, y, f"({pn})", 290, 8 if i == 0 else 9, 10.1)
            y += 0
    y += 4
    k.t(65.6, y, "1. Kode Nama Kegiatan", 9)
    k.t(269.6, y, "1.", 9)
    k.t(287.6, y, keg_k, 9)
    y2 = k.lines(287.6, y + 12.1, f"({keg_n})" if keg_n else "", 270, 8, 10.1)
    y = y2 + 7.9
    k.t(65.6, y, "2. Kode Rekening dan Nama Belanja", 9)
    k.t(269.6, y, "2.", 9)
    k.t(287.6, y, rek_k, 9)
    y3 = k.lines(287.6, y + 12.1, f"({rek_n})" if rek_n else "", 270, 8, 10.1)
    bawah9 = y3 + 3.0
    k.hl(X[0], X[3], bawah9, 1.0)
    top = bawah9
    baris(21.2, "10", "Keterangan Lainnya", None)
    # garis tegak
    k.vl(X[0], 193.8, top, 1.0)
    k.vl(X[1], 193.8, top, 1.0)
    k.vl(X[2], 193.8, top, 1.0)
    k.vl(X[3], 193.8, top, 1.0)

    y = top + 13.6
    k.t(371.6, y, "Dikeluarkan di", 9)
    k.t(463.4, y, ":", 9)
    k.t(473.6, y, isi["kota"], 9)
    k.t(371.6, y + 12, "Pada Tanggal", 9)
    k.t(463.4, y + 12, ":", 9)
    k.t(473.6, y + 12.6, tgl(st["tanggal_surat"]), 9)
    k.t(371.6, y + 24, "Kuasa Pengguna Anggaran", 9)
    tb = y + 37.2
    _tte(k, mode, isi, box=(300.1, 569.2), tok_x=297.0, teks_x=371.6, top_box=tb, logo=(306, tb + 5.8, 57, 52))
    # token kiri persis di samping kotak (rata kanan)
    return top


# ---------------------------------------------------------------- halaman 3: SPD belakang
def hal_spd_belakang(k: Kv, isi, st, mode):
    pptk = isi.get("pptk") or {}
    asal = isi.get("tempat_berangkat_instansi") or "UPT  Puskesmas Melati"
    tujuan = isi["lokasi"]
    X0, XM, X1 = 32.5, 297.2, 572.5
    k.hl(X0, X1, 34.8)
    for y in (178.8, 306.4, 411.9, 526.9, 639.8, 657.3, 705.8):
        k.hl(X0, X1, y)
    k.vl(33.0, 34.3, 706.3)
    k.vl(572.0, 34.3, 706.3)
    k.vl(XM, 34.3, 640.3)

    def kanan(top, baris_, val_x, dy0=0.0, pitch=12.0):
        for i, (lb, v) in enumerate(baris_):
            yy = top + dy0 + pitch * i
            k.t(302.5, yy, lb, 9)
            k.t(392.5, yy, ":", 9)
            if v:
                k.t(val_x, yy + (0.6 if lb.startswith("Pada") else 0), v, 9)

    # I
    k.t(302.5, 39.6, "Berangkat dari", 9)
    k.t(392.5, 39.6, ":", 9)
    k.t(416.5, 39.6, asal, 9)
    k.t(302.5, 51.6, "(Tempat Kedudukan)", 9)
    k.t(302.5, 63.6, "Pada Tanggal", 9)
    k.t(392.5, 63.6, ":", 9)
    k.t(416.5, 64.2, tgl(isi["mulai"]), 9)
    k.t(302.5, 75.6, "Ke", 9)
    k.t(392.5, 75.6, ":", 9)
    k.t(416.5, 75.6, tujuan, 9)
    k.t(302.5, 93.6, "Pejabat Pelaksana Teknis Kegiatan (PPTK)", 9)
    k.t(302.5, 147.6, pptk.get("nama") or "..................................", 9)
    if pptk.get("nip"):
        k.t(302.5, 159.6, f"NIP.{pptk['nip']}", 9)
    # II
    k.t(38.5, 183.6, "II", 9)
    k.t(56.5, 183.6, "Tiba di", 9)
    k.t(128.1, 183.6, ":", 9)
    k.t(140.5, 183.6, tujuan, 9)
    k.t(56.5, 207.6, "Pada Tanggal", 9)
    k.t(127.4, 207.6, ":", 9)
    k.t(140.5, 208.2, tgl(isi["mulai"]), 9)
    kanan(183.6, [("Berangkat dari", tujuan)], 410.5)
    k.t(302.5, 207.6, "Ke", 9)
    k.t(392.5, 207.6, ":", 9)
    k.t(410.5, 207.6, asal, 9)
    k.t(302.5, 219.6, "Pada Tanggal", 9)
    k.t(391.4, 219.6, ":", 9)
    k.t(410.5, 220.2, tgl(isi["selesai"]), 9)
    # III & IV (kosong, diisi tangan bila perlu)
    for rom, ty, dy_l in (("III", 309.6, 12), ("IV", 417.6, 12)):
        k.t(38.5, ty, rom, 9)
        k.t(56.5, ty, "Tiba di", 9)
        k.t(128.1, ty, ":", 9)
        k.t(56.5, ty + dy_l, "Pada Tanggal", 9)
        k.t(127.4, ty + dy_l, ":", 9)
        for i, lb in enumerate(["Berangkat dari", "Ke", "Pada Tanggal"]):
            k.t(302.5, ty + 12 * i, lb, 9)
            k.t(392.5, ty + 12 * i, ":", 9)
    # V
    k.t(38.5, 531.6, "V", 9)
    k.t(56.5, 531.6, "Tiba di", 9)
    k.t(124, 531.6, ":", 9)
    k.t(134.5, 531.6, asal, 9)
    k.t(56.5, 543.6, "Pada Tanggal:", 9)
    k.t(134.5, 544.2, tgl(isi["selesai"]), 9)
    k.lines(302.5, 537.6, "Telah diperiksa dengan keterangan bahwa perjalanan tersebut diatas perintahnya dan semata-mata untuk kepentingan jabatan dalam waktu yang sesingkat-singkatnya", 258, 9, 10.2, just=True)
    # VI, VII
    k.t(38.5, 645.8, "VI", 8)
    k.t(56.5, 645.8, "CATATAN LAIN-LAIN", 8)
    k.t(38.5, 657.8, "VII", 8)
    k.t(56.5, 657.8, "Perhatian:", 8)
    k.lines(56.5, 667.7, "PA/KPA yang menerbitkan SPD, Pegawai yang melakukan perjalanan dinas, para pejabat yang mengesahkan tanggal berangkat/tiba serta bendahara pengeluaran bertanggungjawab berdasarkan peraturan dan Perundang-Undangan Keuangan Negara/Daerah, apabila Negara/Daerah menderita/mengalami kerugian akibat kesalahan, kelalaian dan kealpaan.",
            504, 10, 11.8, font=SERIF, just=True)
    k.t(386.5, 717.6, "Kuasa Pengguna Anggaran", 9)
    _tte(k, mode, isi, box=(315.0, 572.0), tok_x=311.5, teks_x=386.5, top_box=730.8, logo=(321, 737, 57, 59))


# ---------------------------------------------------------------- halaman 4: Surat Pernyataan
def hal_pernyataan(k: Kv, isi, st, mode):
    ps = isi["petugas"]
    pptk = isi.get("pptk") or {}
    _kop(k, isi["kop"], y0=49, cx=350.5, logo=(65, 49, 74, 76), rule=(50.5, 554.5, 131.1, 1.6), tebal3_ukuran=14)
    k.t(303, 139, "SURAT PERNYATAAN", 12, BOLD, "c")
    k.t(51, 163, "Yang Bertanda Tangan di Bawah ini :", 11)
    y = 183
    for i, p in enumerate(ps, 1):
        k.t(51, y, str(i), 11)
        for j, (lb, v) in enumerate([("Nama", p["nama"]), ("Pangkat/Gol", _pg(p) or "-"), ("NIP", p.get("nip") or "-"), ("Jabatan", p.get("jabatan") or "-")]):
            k.t(75, y + 12 * j, lb, 11)
            k.t(178, y + 12 * j, ":", 11)
            k.t(189, y + 12 * j, v, 11)
        y += 60
    y += 7
    nomor = _nomor_final(st)
    par = [f"Sebagaimana Surat Perintah Tugas No. {nomor} Tanggal {tgl(st['tanggal_surat'])} dalam rangka {st['maksud']}",
           "Dengan selesainya tugas kedinasan kami, maka kami mengajukan rincian biaya perjalanan dinas, sebagaimana terlampir.",
           "Adapun besaran rincian biaya perjalanan dinas yang diajukan, adalah sesuai dengan peraturan perundang-undangan yang berlaku dan merupakan tanggung jawab sepenuhnya oleh kami. Apabila kemudian hari terjadi temuan dalam pemeriksaan, yang mengakibatkan kerugian Negara maka kami bersedia mengembalikan ke Kas Negara sebesar hasil temuan dari Tim pemeriksa.",
           "Demikian surat pernyataan ini kami buat, untuk dapat dipergunakan sebagaimana mestinya"]
    for pr in par:
        y = k.lines(57, y, pr, 497, 11, 16.4, just=True, indent=36)
    ys = y + 71
    k.t(154, ys, "Mengetahui,", 11, REG, "c")
    k.t(154, ys + 13, "Pejabat Pelaksana Teknis Kegiatan", 11, REG, "c")
    k.t(154, ys + 25, "(PPTK)", 11, REG, "c")
    k.t(154, ys + 66, pptk.get("nama") or "..................................", 11, REG, "c")
    if pptk.get("nip"):
        k.t(154, ys + 78, f"NIP.{pptk['nip']}", 11, REG, "c")
    k.t(327, ys - 6, f"{isi['kota']}, {tgl(st['tanggal_surat'])}", 11)
    k.t(327, ys + 12, "Yang membuat pernyataan :", 11)
    yy = ys + 29
    for i, p in enumerate(ps, 1):
        k.t(327, yy + 1, str(i), 9)
        k.t(351, yy, p["nama"], 9)
        k.t(351, yy + 12, "NIP", 9)
        k.t(375, yy + 12, p.get("nip") or "-", 9)
        k.hl(512.5, 542.5, yy + 20.5, 1.0)
        yy += 26


# ---------------------------------------------------------------- halaman 5: Rincian + SPPD Rampung
def _kata(n: int) -> str:
    return terbilang(n).replace(" rupiah", "").capitalize()


def hal_rincian(k: Kv, isi, st, spds, pejabat, mode):
    nomor = _nomor_final(st)
    k.t(378, 36, "LAMPIRAN", 9)
    k.t(378, 46, "PERATURAN BUPATI", 9)
    k.t(378, 56, "NOMOR", 9)
    k.t(432, 56, ": 8 Tahun 2026", 9)
    k.t(378, 69, "TANGGAL", 9)
    k.t(431, 69, ": 30 April 2026", 9)
    k.hl(30.5, 579.2, 86.5, 1.0)
    k.t(306, 97, "RINCIAN PERJALANAN DINAS", 9, BOLD, "c")
    k.t(30, 114, "Lampiran Surat Perintah Tugas :", 9)
    k.t(186, 114, nomor, 9)
    k.t(30, 124, "Tanggal", 9)
    k.t(173, 124, ":", 9)
    k.t(186, 126, tgl(st["tanggal_surat"]), 9)

    t0, th = 150.9, 172.6
    total = sum(s["total"] for s in spds)
    # isi badan
    blok = []
    for s in spds:
        p = s["petugas"]
        ls = []
        ada_tr = False
        for b in s["biaya"]["baris"]:
            nama = {"UH": "Uang Harian", "TR": "Biaya Transport", "INAP": "Penginapan"}.get(b.get("kode"), b["uraian"])
            sat = {"OH": "Hari"}.get(b["satuan"], b["satuan"])
            ada_tr = ada_tr or b.get("kode") == "TR"
            ls.append((f"{nama} :{b['volume']} ({_kata(b['volume'])}) {sat} x {rps(b['tarif'])}" if b["jumlah"] else nama, b["jumlah"]))
        if not ada_tr:
            ls.append(("Biaya Transport", 0))
        blok.append((p, ls))
    y = th + 2.4
    for i, (p, ls) in enumerate(blok, 1):
        k.t(75, y + 1, str(i), 9)
        k.t(90, y, p["nama"], 9)
        for j, (tx, jml) in enumerate(ls, 1):
            k.t(90, y + 12 * j, tx, 9)
            if jml:
                k.t(294, y + 12 * j, "Rp", 9)
                k.t(365, y + 12 * j, f"{int(jml):,}".replace(",", "."), 9, REG, "r")
        y += 12 * (len(ls) + 1) + 9
    bawah_badan = max(y - 2.3, th + 40)
    # kolom keterangan
    k.lines(390, th + 2.4, st["maksud"], 186, 9, 10.3, just=True)
    ytot = bawah_badan
    k.hl(66.2, 579.2, ytot, 1.0)
    k.t(186, ytot + 4.3, "TOTAL", 9, BOLD)
    k.t(294, ytot + 5.3, "Rp", 9, BOLD)
    k.t(365, ytot + 5.3, f"{int(total):,}".replace(",", "."), 9, BOLD, "r")
    byb = ytot + 22.5
    k.hl(30.5, 579.2, byb, 1.0)
    k.t(36, byb + 2.5, f"Terbilang : {terbilang(total).title()}", 9, BOLDITAL)
    bb = byb + 23.7
    k.hl(30.5, 579.2, bb, 1.0)
    k.hl(30.5, 579.2, t0, 1.0)
    k.hl(30.5, 579.2, th, 1.0)
    k.vl(30.5, t0, bb)
    k.vl(579.2, t0, bb)
    for xv in (66.2, 288.2, 383.4):
        k.vl(xv, t0, byb)
    for tx, xc in (("NO", 48.4), ("Perincian Biaya", 177.2), ("Jumlah", 335.8), ("Keterangan", 481.3)):
        k.t(xc, 157, tx, 9, BOLD, "c")
    # tanda tangan
    d = bb - 308.9
    bend = pejabat.get("bendahara_pembantu") or {}
    pptk = isi.get("pptk") or {}
    k.t(372, 315 + d, f"{isi['kota']},    {tgl(st['tanggal_surat'])}", 9)
    k.t(372, 327 + d, "Telah Diterima Uang Sebesar :", 9)
    k.t(372, 339 + d, rps(total), 9)
    k.t(372, 357 + d, "Yang Menerima :", 9)
    yy = 369 + d
    for i, (p, _) in enumerate(blok, 1):
        k.t(372, yy, str(i), 9)
        k.t(390, yy, p["nama"], 9)
        k.t(390, yy + 12, f"NIP. {p.get('nip') or '-'}", 9)
        k.hl(564, 588, yy + 19.8, 1.0)
        yy += 24
    k.t(36, 327 + d, "Telah Dibayar Sejumlah", 9)
    k.t(36, 340 + d, rps(total), 9, BOLD)
    k.t(36, 351 + d, "Bendahara Pengeluaran Pembantu", 9)
    k.t(36, 393 + d, bend.get("nama") or "", 9)
    if bend.get("nip"):
        k.t(36, 405 + d, f"NIP. {bend['nip']}", 9)
    py = 429 + d
    k.t(174, py, "Pejabat Pelaksana Teknis Kegiatan (PPTK)", 9)
    k.t(174, py + 42, pptk.get("nama") or "", 9)
    if pptk.get("nip"):
        k.t(174, py + 54, f"NIP. {pptk['nip']}", 9)
    # perhitungan SPPD rampung
    sy = max(503 + d, yy + 20, py + 74)
    k.hl(30, 582, sy, 1.6)
    k.t(306, sy + 4, "PERHITUNGAN SPPD RAMPUNG", 9, REG, "c")
    k.hl(30, 582, sy + 19.8, 1.0)
    for j, (lb, v) in enumerate([("Ditetapkan sejumlah", rps(total)), ("Yang telah dibayar semula", ""), ("Sisa kurang/lebih", "")]):
        k.t(36, sy + 22 + 10 * j, lb, 9)
        k.t(162, sy + 22 + 10 * j, ":", 9)
        if v:
            k.t(174, sy + 23, v, 9, BOLD)
    k.hl(30, 582, sy + 56.5, 1.0)
    z = sy + 64
    nama_dkk = spds[0]["petugas"]["nama"] + (" dkk" if len(spds) > 1 else "")
    for lb, dy in (("No. Agenda", 0), ("No. Surat Tugas", 10), ("Dan Tanggal", 20)):
        k.t(36, z + dy, lb, 9)
        k.t(162, z + dy, ":", 9)
    k.t(204, z, f"Berkas An. {nama_dkk}", 9)
    k.t(174, z + 12, nomor, 9)
    k.t(174, z + 24, tgl(st["tanggal_surat"]), 9)
    k.t(360, z + 24, "Kuala Kapuas,", 9)
    k.t(450, z + 24, ":", 9)
    k.t(558, z + 24, str(st["tanggal_surat"])[:4], 9)
    k.t(360, z + 34, "Disetujui Rp.", 9)
    k.t(450, z + 34, ":", 9)
    k.t(480, z + 37, rps(total), 9, BOLD)
    k.t(360, z + 44, "Beban Mata Anggaran", 9)
    k.t(468, z + 44, ":", 9)
    k.t(36, z + 54, "Telah di Verifikasi Kelengkapan Oleh", 9)
    k.t(36, z + 66, "Verifikator UPT. Puskesmas Melati", 9)
    k.t(360, z + 66, "Kuasa Pengguna Anggaran", 9)
    ver = pejabat.get("verifikator") or {}
    k.t(36, z + 108, ver.get("nama") or "", 9)
    if ver.get("nip"):
        k.t(36, z + 120, f"NIP. {ver['nip']}", 9)
    k.t(360, z + 108, isi["ttd"].get("nama") or "", 9)
    if isi["ttd"].get("nip"):
        k.t(360, z + 120, f"NIP. {isi['ttd']['nip']}", 9)


# ---------------------------------------------------------------- halaman 6: Laporan perjalanan dinas
def hal_laporan(k: Kv, isi, st, laporan, fotos):
    ps = isi["petugas"]
    nomor = _nomor_final(st)
    _kop(k, isi["kop"], y0=49, cx=332.0, logo=(81, 49, 72, 72), rule=(68.5, 518.5, 133.6, 2.0))
    k.t(298, 142, "LAPORAN PERJALANAN DINAS", 11, BOLD, "c")
    k.t(73, 160, "A.", 11)
    k.t(93, 160, "Nama Kegiatan", 11)
    y = k.lines(93, 178, st["maksud"], 425, 11, 13, just=True)
    k.t(73, y + 5, "B.", 11)
    k.t(93, y + 5, "Dasar pelaksanaan", 11)
    k.t(93, y + 17, f"Surat Tugas dari  {isi['ttd'].get('jabatan') or 'Kepala UPT Puskesmas Melati'}", 11)
    k.t(93, y + 29, nomor, 11)
    y2 = y + 47
    k.t(73, y2, "C.", 11)
    k.t(93, y2, "Lokasi tujuan", 11)
    k.t(93, y2 + 12, isi["lokasi"], 11)
    y3 = y2 + 43
    k.t(73, y3, "D.", 11)
    k.t(93, y3, "Waktu Pelaksanaan", 11)
    hari = isi["hari"]
    rentang = tgl(isi["mulai"]) + (f" s.d. {tgl(isi['selesai'])}" if hari > 1 else "")
    k.t(93, y3 + 16, f"Dilaksanakan selama {hari} ({_kata(hari).lower()}) hari , tanggal {rentang}", 11)
    y4 = y3 + 40
    k.t(73, y4, "E.", 11)
    k.t(93, y4, "Laporan Kronologis Kegiatan", 11)
    krono = (laporan.get("kronologis") or "").strip() or "............................................................"
    y5 = k.lines(93, y4 + 18, krono, 425, 11, 13, just=True)
    y6 = y5 + 9
    k.t(73, y6, "F.", 11)
    k.t(93, y6, "Foto Kegiatan", 11)
    yf = y6 + 18
    fotos = fotos[:MAKS_FOTO]
    for i, data in enumerate(fotos):
        r, cidx = divmod(i, 2)
        k.foto(data, 93 + cidx * 224, yf + r * 125, 198.5, 113)
    baris = (len(fotos) + 1) // 2 if fotos else 1
    yc = yf + 125 * (baris - 1) + 113 + 6
    k.t(93, yc, "Foto kegiatan :", 8)
    ye = k.lines(153, yc, st["maksud"], 365, 8, 10, just=True)
    ys = ye + 47
    k.t(285, ys, f"{isi['kota']}, {tgl(laporan.get('tanggal') or isi['selesai'])}", 11)
    k.t(285, ys + 18, "Yang membuat laporan, :", 11)
    yy = ys + 35
    for i, p in enumerate(ps, 1):
        k.t(296, yy + 1, str(i), 9)
        k.t(309, yy, p["nama"], 9)
        k.t(309, yy + 12, f"NIP. {p.get('nip') or '-'}", 9)
        k.hl(482.5, 512.5, yy + 20.5, 1.0)
        yy += 26


# ---------------------------------------------------------------- halaman 7: Kwitansi (contoh: kwintansi - Copy.docx)
def hal_kwitansi(k: Kv, isi, st, spds, pejabat):
    ps = [s["petugas"] for s in spds]
    total = sum(s["total"] for s in spds)
    bend = pejabat.get("bendahara_pembantu") or {}
    ang = isi.get("anggaran") or {}
    keg_k, _ = _kn(ang.get("kegiatan"))
    rek_k, _ = _kn(ang.get("rekening") or (isi.get("kode_rekening") or ""))
    LX, RX = 28.1, 612 - 28.1
    top = 14.4
    # kepala kiri
    cx = 28.1 + 95
    k.t(cx, top + 2, "PEMERINTAH KABUPATEN KAPUAS", 10, BOLD, "c")
    k.t(cx, top + 15, "DINAS KESEHATAN", 11, BOLD, "c")
    k.t(cx, top + 29, "UPT PUSKESMAS MELATI", 11, BOLD, "c")
    k.t(LX, top + 70, "Lembaran Ke : I, II,III,IV,V,VI", 9)
    k.t(318, top + 34, "KWITANSI", 14, BOLD, "c")
    k.t(318, top + 34, "", 14)
    # kotak kanan "Dibayar dan dibukukan"
    k.t(405, top + 4, "Dibayar dan dibukukan  :", 10)
    for j, (lb, v) in enumerate([("Pada tanggal", " " * 8 + str(st["tanggal_surat"])[:4].rjust(8)), ("Bukti Kas / No.", ""), ("No. Rekening", keg_k), ("Jenis Pengeluaran", rek_k)]):
        yy = top + 18 + 12.5 * j
        k.t(405, yy, lb, 10)
        k.t(490, yy, ":", 10)
        if v.strip():
            k.t(498, yy, v.strip(), 10)
    k.hl(LX, RX, top + 84, 1.2)
    y = top + 100
    nama_ps = ps[0]["nama"] + (" dkk" if len(ps) > 1 else "")
    k.t(LX, y, "Sudah Terima Dari", 11, BOLD)
    k.t(150, y, ":", 11, BOLD)
    k.t(158, y, f"Bendahara Pengeluaran Pembantu {isi.get('instansi') or 'UPT Puskesmas Melati'}", 11, BOLD)
    y += 24
    k.t(LX, y, "Uang Sebanyak", 11, BOLD)
    k.t(150, y, ":", 11, BOLD)
    k.t(158, y, f"// {terbilang(total).title()} //", 11)
    y += 24
    k.t(LX, y, "Untuk Pembayaran", 11, BOLD)
    k.t(150, y, ":", 11, BOLD)
    uraian = (f"Belanja Perjalanan Dinas Luar Daerah Kegiatan {st['maksud']} Berdasarkan Surat Perintah No. {_nomor_final(st)} "
              f"Tanggal. {tgl(st['tanggal_surat'])} an. {nama_ps}")
    y = k.lines(158, y, uraian, RX - 158, 11, 13.2, just=True)
    y += 14
    k.t(LX, y, f"Terbilang Rp. {int(total):,}".replace(",", ".") + ",-", 14, BOLDITAL)
    y += 30
    k.t(330, y, f"{isi['kota']}, {tgl(st['tanggal_surat'])}", 10)
    y += 18
    kol = [(LX + 30, "Mengetahui/Setuju :", isi["ttd"].get("jabatan") or "Kuasa Pengguna Anggaran", isi["ttd"].get("nama"), isi["ttd"].get("nip")),
           (260, "Telah dibayar  :", "Bendahara Pengeluaran Pembantu", bend.get("nama"), bend.get("nip")),
           (440, "Tanda terima,", "", ps[0]["nama"], ps[0].get("nip"))]
    for xx, a, b, nm, nip in kol:
        k.t(xx, y, a, 10)
        if b:
            k.t(xx, y + 12, b, 10)
        k.t(xx, y + 64, nm or "", 10 if len(nm or "") < 30 else 9)
        if nip:
            k.t(xx, y + 76, f"NIP. {nip}", 10, BOLD)
    y += 100
    k.hl(LX, RX, y, 0.8)
    c3 = [(LX, ["Barang-barang tsb.telah diterima dengan", "Cukup dan dalam keadaan baik oleh.", "", "Nama   : ..........................", "Alamat : .........................."]),
          (205, ["Barang-barang tsb. telah dimasukkan dalam daftar inv/pemakaian  :", "", "Tanggal   : ..........................", "No. Inv  : .........................."]),
          (420, ["Uang tsb. telah dibayar lunas kepada", "Yang berhak menerimanya oleh  :"])]
    for xx, ls, lebar in [(c3[0][0], c3[0][1], 170), (c3[1][0], c3[1][1], 205), (c3[2][0], c3[2][1], 160)]:
        yy = y + 6
        for ln in ls:
            if not ln:
                yy += 10
                continue
            yy = k.lines(xx, yy, ln, lebar, 8, 10)


# ---------------------------------------------------------------- perakit
def buat_paket(isi: dict, st: dict, spds: list, laporan: dict, fotos: list, pejabat: dict, mode: str = "srikandi", judul: str = "Paket Srikandi") -> bytes:
    """spds: [{'petugas': dict, 'biaya': dict, 'total': int}]; fotos: [bytes JPEG]; pejabat: {'bendahara_pembantu': {...}, 'verifikator': {...}}."""
    mode = "srikandi" if mode == "srikandi" else "cetak"
    buf = io.BytesIO()
    c = canvas.Canvas(buf, pagesize=(W, H))
    c.setTitle(judul)
    c.setAuthor("SIKADIN — UPT Puskesmas Melati")
    k = Kv(c)
    for fn in (lambda: hal_st(k, isi, st, mode), lambda: hal_spd_depan(k, isi, st, mode), lambda: hal_spd_belakang(k, isi, st, mode),
               lambda: hal_pernyataan(k, isi, st, mode), lambda: hal_rincian(k, isi, st, spds, pejabat, mode),
               lambda: hal_laporan(k, isi, st, laporan, fotos), lambda: hal_kwitansi(k, isi, st, spds, pejabat)):
        fn()
        c.showPage()
    c.save()
    return buf.getvalue()
