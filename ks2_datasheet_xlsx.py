#!/usr/bin/env python3
# -*- coding: utf-8 -*-
import openpyxl
from openpyxl.styles import Font, PatternFill, Alignment, Border, Side
from openpyxl.comments import Comment

FONT = "Arial"
wb = openpyxl.Workbook()

# renkler
BASLIK_FILL = PatternFill("solid", fgColor="1F4E78")
HDR_FILL = PatternFill("solid", fgColor="2E75B6")
TOP_FILL = PatternFill("solid", fgColor="DDEBF7")
ALT_FILL = PatternFill("solid", fgColor="F2F7FC")
WHITE = Font(name=FONT, color="FFFFFF", bold=True, size=11)
BOLD = Font(name=FONT, bold=True, size=11)
NORM = Font(name=FONT, size=10)
thin = Side(style="thin", color="BFBFBF")
BORDER = Border(left=thin, right=thin, top=thin, bottom=thin)
CTR = Alignment(horizontal="center", vertical="center", wrap_text=True)
LEFT = Alignment(horizontal="left", vertical="center", wrap_text=True)

# benzersiz model verileri (datasheet)
# (model, adet, tip, brut_kW, net_kW, debi_m3h, kosul, guven, kaynak)
MODELLER = [
    ("UNİFLAİR TDCV4300A", 16, "Chilled-water, downflow, 3 fan",
     128.0, 122.0, 29400, "7/12°C su, 24°C/50%RH (katalog)", "Yüksek",
     "Uniflair CW katalog (Mouser) / Schneider TDCV tablosu"),
    ("DMA092DPSIS4PE1", 10, "Liebert PDX, DX, çift devre R410A",
     92.5, 72.0, 17950, "Maks. ESP 180 Pa", "Yüksek",
     "Vertiv Liebert PDX 15–165 kW brochure"),
    ("DMC092DPSNS4PE1", 1, "Liebert PDX, 92 kW sınıfı",
     92.5, 72.0, 17950, "Maks. ESP 180 Pa", "Yüksek",
     "Vertiv Liebert PDX brochure (92 kW sınıfı)"),
    ("DMA065DPSIS4PE1", 7, "Liebert PDX, ~64 kW sınıfı, çift devre",
     64.0, 60.0, 15500, "30°C/35%RH, %80 mod., 18°C besleme", "Orta",
     "Vertiv PDX PI datasheet (PI062 ~64 kW sınıfı)"),
    ("DMA045DPSIS4PE1", 1, "Liebert PDX, 45 kW sınıfı, tek devre",
     44.6, 39.1, 10900, "Maks. ESP 100 Pa", "Yüksek",
     "Vertiv Liebert PDX brochure (PX045)"),
    ("DCPro-DX-52", 1, "DX, ~52 kW sınıfı (farklı marka)",
     52.0, None, 11000, "TEYİT GEREK (datasheet bulunamadı)", "Düşük",
     "Benzer 52 kW DX sınıfı (tahmini)"),
]

# ============================================================
# SAYFA 1: MODEL OZETI
# ============================================================
s1 = wb.active
s1.title = "Model Ozeti"
s1.sheet_view.showGridLines = False

s1["A1"] = "KS2 - Soğutma Üniteleri Datasheet Özeti"
s1["A1"].font = Font(name=FONT, bold=True, size=14, color="FFFFFF")
s1["A1"].fill = BASLIK_FILL
s1.merge_cells("A1:K1")
s1["A1"].alignment = Alignment(horizontal="left", vertical="center")
s1.row_dimensions[1].height = 26

s1["A2"] = ("Datasheet nominal değerleri. Kapasite; dönüş havası sıcaklığı/nem ve "
            "(TDCV için) giriş su sıcaklığına göre ±%20 değişir. 'Net duyulur' = net sensible.")
s1["A2"].font = Font(name=FONT, italic=True, size=9, color="595959")
s1.merge_cells("A2:K2")
s1.row_dimensions[2].height = 26
s1["A2"].alignment = Alignment(horizontal="left", vertical="center", wrap_text=True)

hdr = ["Model", "Adet", "Tip", "Brüt soğutma [kW]", "Net duyulur [kW]",
       "Nominal debi [m³/h]", "Rating koşulu", "Güven", "Kaynak",
       "Toplam brüt [kW]", "Toplam debi [m³/h]"]
for j, h in enumerate(hdr, start=1):
    c = s1.cell(row=3, column=j, value=h)
    c.font = WHITE; c.fill = HDR_FILL; c.alignment = CTR; c.border = BORDER
s1.row_dimensions[3].height = 40

r = 4
for (model, adet, tip, brut, net, debi, kosul, guven, kaynak) in MODELLER:
    s1.cell(r, 1, model).font = BOLD
    s1.cell(r, 2, adet)
    s1.cell(r, 3, tip)
    s1.cell(r, 4, brut)
    s1.cell(r, 5, net if net is not None else "—")
    s1.cell(r, 6, debi)
    s1.cell(r, 7, kosul)
    s1.cell(r, 8, guven)
    s1.cell(r, 9, kaynak)
    s1.cell(r, 10, "=B%d*D%d" % (r, r))          # toplam brut
    s1.cell(r, 11, "=B%d*F%d" % (r, r))          # toplam debi
    for j in range(1, 12):
        cell = s1.cell(r, j)
        if j not in (1,):
            cell.font = NORM
        cell.border = BORDER
        cell.alignment = LEFT if j in (3, 7, 9) else CTR
        if r % 2 == 0:
            if cell.fill.fgColor.rgb in (None, "00000000"):
                cell.fill = ALT_FILL
    r += 1

# DCPro net duyulur notu
s1.cell(5 + 4 - 1, 5)  # noop
dcpro_row = 4 + 5
s1.cell(dcpro_row, 7).comment = Comment(
    "DCPro-DX-52: Vertiv değil; marka datasheet'i bulunamadı. ~52 kW DX "
    "sınıfı için temsili debi. PDF paylaşılırsa kesin değer işlenir.", "KS2")
s1.cell(8, 7).comment = Comment(  # DMA065 row (4+4=8)
    "DMA065: kataloglarda tam '065' etiketli boyut yok; en yakın gerçek "
    "kayıt ~64 kW brüt (PI062) -> ~15.500 m³/h. Kesin için sipariş koduna "
    "ait datasheet gerekir.", "KS2")

# TOPLAM satiri
tr = r
s1.cell(tr, 1, "TOPLAM (36 cihaz)").font = BOLD
s1.cell(tr, 2, "=SUM(B4:B%d)" % (r - 1)).font = BOLD
s1.cell(tr, 10, "=SUM(J4:J%d)" % (r - 1)).font = BOLD
s1.cell(tr, 11, "=SUM(K4:K%d)" % (r - 1)).font = BOLD
for j in range(1, 12):
    c = s1.cell(tr, j); c.fill = TOP_FILL; c.border = BORDER
    if c.alignment is None or c.alignment.horizontal is None:
        c.alignment = CTR

# sayi formatlari
for rr in range(4, tr + 1):
    s1.cell(rr, 4).number_format = '#,##0.0'
    if isinstance(s1.cell(rr, 5).value, (int, float)):
        s1.cell(rr, 5).number_format = '#,##0.0'
    s1.cell(rr, 6).number_format = '#,##0'
    s1.cell(rr, 10).number_format = '#,##0.0'
    s1.cell(rr, 11).number_format = '#,##0'

genislik = {"A": 22, "B": 7, "C": 30, "D": 15, "E": 15, "F": 16,
            "G": 26, "H": 9, "I": 30, "J": 15, "K": 16}
for col, w in genislik.items():
    s1.column_dimensions[col].width = w
s1.freeze_panes = "A4"

# ============================================================
# SAYFA 2: CIHAZ LISTESI (36 satir, formulle cekilir)
# ============================================================
s2 = wb.create_sheet("Cihaz Listesi")
s2.sheet_view.showGridLines = False

SIRA = [
    "UNİFLAİR TDCV4300A","UNİFLAİR TDCV4300A","UNİFLAİR TDCV4300A","UNİFLAİR TDCV4300A",
    "UNİFLAİR TDCV4300A","UNİFLAİR TDCV4300A","DMC092DPSNS4PE1","DMA092DPSIS4PE1",
    "DMA065DPSIS4PE1","DMA092DPSIS4PE1","DCPro-DX-52","UNİFLAİR TDCV4300A",
    "DMA065DPSIS4PE1","DMA065DPSIS4PE1","DMA065DPSIS4PE1","UNİFLAİR TDCV4300A",
    "UNİFLAİR TDCV4300A","UNİFLAİR TDCV4300A","UNİFLAİR TDCV4300A","UNİFLAİR TDCV4300A",
    "UNİFLAİR TDCV4300A","UNİFLAİR TDCV4300A","UNİFLAİR TDCV4300A","UNİFLAİR TDCV4300A",
    "DMA092DPSIS4PE1","DMA092DPSIS4PE1","DMA092DPSIS4PE1","DMA092DPSIS4PE1",
    "DMA045DPSIS4PE1","DMA065DPSIS4PE1","DMA092DPSIS4PE1","DMA092DPSIS4PE1",
    "DMA092DPSIS4PE1","DMA065DPSIS4PE1","DMA065DPSIS4PE1","DMA092DPSIS4PE1",
]

s2["A1"] = "KS2 - Cihaz Listesi (36 adet)  —  değerler 'Model Ozeti' sayfasından çekilir"
s2["A1"].font = Font(name=FONT, bold=True, size=13, color="FFFFFF")
s2["A1"].fill = BASLIK_FILL
s2.merge_cells("A1:E1")
s2["A1"].alignment = Alignment(horizontal="left", vertical="center")
s2.row_dimensions[1].height = 24

h2 = ["#", "Marka/Model", "Brüt soğutma [kW]", "Net duyulur [kW]", "Nominal debi [m³/h]"]
for j, h in enumerate(h2, start=1):
    c = s2.cell(row=2, column=j, value=h)
    c.font = WHITE; c.fill = HDR_FILL; c.alignment = CTR; c.border = BORDER
s2.row_dimensions[2].height = 32

ozet_a = "'Model Ozeti'!$A$4:$A$9"
ozet_d = "'Model Ozeti'!$D$4:$D$9"
ozet_e = "'Model Ozeti'!$E$4:$E$9"
ozet_f = "'Model Ozeti'!$F$4:$F$9"
rr = 3
for i, model in enumerate(SIRA, start=1):
    s2.cell(rr, 1, i)
    s2.cell(rr, 2, model).font = NORM
    s2.cell(rr, 3, "=INDEX(%s,MATCH(B%d,%s,0))" % (ozet_d, rr, ozet_a))
    s2.cell(rr, 4, "=INDEX(%s,MATCH(B%d,%s,0))" % (ozet_e, rr, ozet_a))
    s2.cell(rr, 5, "=INDEX(%s,MATCH(B%d,%s,0))" % (ozet_f, rr, ozet_a))
    for j in range(1, 6):
        c = s2.cell(rr, j); c.border = BORDER
        c.alignment = LEFT if j == 2 else CTR
        if j != 2:
            c.font = NORM
        if rr % 2 == 1:
            c.fill = ALT_FILL
    s2.cell(rr, 3).number_format = '#,##0.0'
    s2.cell(rr, 4).number_format = '#,##0.0'
    s2.cell(rr, 5).number_format = '#,##0'
    rr += 1

# toplam satiri (capraz kontrol)
tr2 = rr
s2.cell(tr2, 2, "TOPLAM").font = BOLD
s2.cell(tr2, 3, "=SUM(C3:C%d)" % (rr - 1)).font = BOLD
s2.cell(tr2, 4, "=SUM(D3:D%d)" % (rr - 1)).font = BOLD
s2.cell(tr2, 5, "=SUM(E3:E%d)" % (rr - 1)).font = BOLD
for j in range(1, 6):
    c = s2.cell(tr2, j); c.fill = TOP_FILL; c.border = BORDER; c.alignment = CTR
s2.cell(tr2, 3).number_format = '#,##0.0'
s2.cell(tr2, 4).number_format = '#,##0.0'
s2.cell(tr2, 5).number_format = '#,##0'

for col, w in {"A": 5, "B": 24, "C": 17, "D": 17, "E": 18}.items():
    s2.column_dimensions[col].width = w
s2.freeze_panes = "A3"

wb.save("/home/user/foam/ks2_sogutma_datasheet.xlsx")
print("yazildi: /home/user/foam/ks2_sogutma_datasheet.xlsx")
