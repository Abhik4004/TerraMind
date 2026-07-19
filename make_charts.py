from openpyxl import Workbook
from openpyxl.styles import Font, PatternFill, Alignment, Border, Side
from openpyxl.chart import LineChart, Reference

wb = Workbook()

# ── Styles ────────────────────────────────────────────────────
HDR_FILL  = PatternFill("solid", fgColor="1F3864")
HDR_FONT  = Font(name="Arial", bold=True, color="FFFFFF", size=11)
SUB_FILL  = PatternFill("solid", fgColor="2E75B6")
SUB_FONT  = Font(name="Arial", bold=True, color="FFFFFF", size=10)
COL_FILL  = PatternFill("solid", fgColor="BDD7EE")
ALT_FILL  = PatternFill("solid", fgColor="DCE6F1")
GRN_FILL  = PatternFill("solid", fgColor="E2EFDA")
thin      = Side(border_style="thin", color="B8CCE4")
BDR       = Border(left=thin, right=thin, top=thin, bottom=thin)

def hdr(cell, text, fill=HDR_FILL, font=HDR_FONT):
    cell.value = text
    cell.fill  = fill
    cell.font  = font
    cell.alignment = Alignment(horizontal="center", vertical="center", wrap_text=True)
    cell.border = BDR

def dat(cell, value, bold=False, center=True, fill=None, color="000000"):
    cell.value = value
    cell.font  = Font(name="Arial", size=10, bold=bold, color=color)
    cell.alignment = Alignment(horizontal="center" if center else "left", vertical="center")
    cell.border = BDR
    if fill:
        cell.fill = fill

# ═══════════════════════════════════════════════════════════════
# SHEET 1 — Benchmark Data
# ═══════════════════════════════════════════════════════════════
ws = wb.active
ws.title = "Benchmark Data"
ws.sheet_view.showGridLines = False
ws.column_dimensions["A"].width = 24
for col in ["B","C","D","E","F"]:
    ws.column_dimensions[col].width = 20

# Title
ws.merge_cells("A1:F1")
hdr(ws["A1"], "TerraMind Benchmark Results  ·  llama3.1:8b  ·  v3")
ws.row_dimensions[1].height = 28
ws.merge_cells("A2:F2")
ws["A2"].value = "Source: benchmark_results.json"
ws["A2"].font  = Font(name="Arial", size=9, italic=True, color="666666")
ws["A2"].alignment = Alignment(horizontal="center")

# ── Concurrency ───────────────────────────────────────────────
ws.merge_cells("A4:D4")
hdr(ws["A4"], "Fig 3(a)+(c)  ·  SR & Overhead vs. Concurrency", SUB_FILL, SUB_FONT)
ws.row_dimensions[4].height = 22
for i, h in enumerate(["Concurrency (workers)","Queries Run","Success Rate (%)","Avg Overhead (s)"], 1):
    hdr(ws.cell(5, i), h, COL_FILL, Font(name="Arial", bold=True, size=10))
for r, row in enumerate([(1,1,100.0,33.4),(2,2,100.0,48.1),(4,4,100.0,60.6)], 6):
    f = ALT_FILL if r % 2 == 0 else None
    dat(ws.cell(r,1), row[0], fill=f)
    dat(ws.cell(r,2), row[1], fill=f)
    dat(ws.cell(r,3), row[2], bold=True, fill=GRN_FILL, color="375623")
    dat(ws.cell(r,4), row[3], fill=f)

# ── Fault Rate ────────────────────────────────────────────────
ws.merge_cells("A10:D10")
hdr(ws["A10"], "Fig 3(b)  ·  SR & Overhead vs. Fault Injection Rate", SUB_FILL, SUB_FONT)
ws.row_dimensions[10].height = 22
for i, h in enumerate(["Fault Rate (%)","Queries Run","Success Rate (%)","Avg Overhead (s)"], 1):
    hdr(ws.cell(11, i), h, COL_FILL, Font(name="Arial", bold=True, size=10))
for r, row in enumerate([(0,4,100.0,0.002),(25,4,100.0,8.3),(50,4,100.0,34.2)], 12):
    f = ALT_FILL if r % 2 == 0 else None
    dat(ws.cell(r,1), row[0], fill=f)
    dat(ws.cell(r,2), row[1], fill=f)
    dat(ws.cell(r,3), row[2], bold=True, fill=GRN_FILL, color="375623")
    dat(ws.cell(r,4), row[3], fill=f)

# ── Workload ──────────────────────────────────────────────────
ws.merge_cells("A16:F16")
hdr(ws["A16"], "Fig 3(d)  ·  Overhead Breakdown vs. Workload Size", SUB_FILL, SUB_FONT)
ws.row_dimensions[16].height = 22
for i, h in enumerate(["Workload (queries)","Success Rate (%)","Total Overhead (s)","LLM Inference (s)","Cache + I/O (s)","Wall Time (s)"], 1):
    hdr(ws.cell(17, i), h, COL_FILL, Font(name="Arial", bold=True, size=10))
for r, row in enumerate([(2,100.0,64.1,39.7,24.4,91.5),(4,100.0,59.9,37.1,22.8,100.9),(8,100.0,67.5,41.9,25.7,151.1)], 18):
    f = ALT_FILL if r % 2 == 0 else None
    dat(ws.cell(r,1), row[0], fill=f)
    dat(ws.cell(r,2), row[1], bold=True, fill=GRN_FILL, color="375623")
    dat(ws.cell(r,3), row[2], fill=f)
    dat(ws.cell(r,4), row[3], fill=f)
    dat(ws.cell(r,5), row[4], fill=f)
    dat(ws.cell(r,6), row[5], fill=f)

# ── Cache Stats ───────────────────────────────────────────────
ws.merge_cells("A22:D22")
hdr(ws["A22"], "Cache State at Benchmark End", SUB_FILL, SUB_FONT)
ws.row_dimensions[22].height = 22
for i, h in enumerate(["Cache Tier","Entries","Contents","Total Size (MB)"], 1):
    hdr(ws.cell(23, i), h, COL_FILL, Font(name="Arial", bold=True, size=10))
cache_rows = [
    ("Response",  2, "Saved final answers",         ""),
    ("Embedding", 5, "nomic-embed-text vectors",    ""),
    ("Tool",      1, "OpenWeatherMap API result",   ""),
    ("TOTAL",     8, "",                             0.045),
]
for r, row in enumerate(cache_rows, 24):
    is_total = row[0] == "TOTAL"
    f = HDR_FILL if is_total else (ALT_FILL if r % 2 == 0 else None)
    c = "FFFFFF" if is_total else "000000"
    dat(ws.cell(r,1), row[0], bold=is_total, fill=f, color=c)
    dat(ws.cell(r,2), row[1], bold=is_total, fill=f, color=c)
    dat(ws.cell(r,3), row[2], center=False, fill=f, color=c)
    dat(ws.cell(r,4), row[3] if row[3] else "", fill=f, color=c)

# ═══════════════════════════════════════════════════════════════
# SHEET 2 — Charts (seed data + 5 charts)
# ═══════════════════════════════════════════════════════════════
wc = wb.create_sheet("Charts")
wc.sheet_view.showGridLines = False
wc.column_dimensions["A"].width = 3

# Title row
wc.merge_cells("B1:O1")
hdr(wc["B1"], "TerraMind  ·  Fig. 3 Performance Charts", HDR_FILL,
    Font(name="Arial", bold=True, color="FFFFFF", size=13))
wc.row_dimensions[1].height = 30

# ── Seed data in hidden cols (Q+) ─────────────────────────────
def seed(sheet, sr, sc, headers, rows):
    for ci, h in enumerate(headers):
        c = sheet.cell(sr, sc + ci)
        c.value = h
        c.font  = Font(name="Arial", bold=True, size=9, color="FFFFFF")
        c.fill  = PatternFill("solid", fgColor="2E75B6")
        c.alignment = Alignment(horizontal="center")
    for ri, row in enumerate(rows):
        for ci, val in enumerate(row):
            c = sheet.cell(sr + 1 + ri, sc + ci)
            c.value = val
            c.font  = Font(name="Arial", size=9)
            c.alignment = Alignment(horizontal="center")

seed(wc, 3, 17, ["Workers","Overhead (s)"],           [(1,33.4),(2,48.1),(4,60.6)])
seed(wc, 3, 20, ["Fault%","Overhead (s)"],             [(0,0.002),(25,8.3),(50,34.2)])
seed(wc, 3, 23, ["Workers","SR (%)"],                  [(1,100),(2,100),(4,100)])
seed(wc, 3, 26, ["Fault%","SR (%)"],                   [(0,100),(25,100),(50,100)])
seed(wc, 3, 29, ["Queries","Total(s)","LLM(s)","I/O(s)","Wall(s)"],
     [(2,64.1,39.7,24.4,91.5),(4,59.9,37.1,22.8,100.9),(8,67.5,41.9,25.7,151.1)])

def make_line(title, y_title, x_title, y_max, h=12, w=18):
    ch = LineChart()
    ch.title   = title
    ch.style   = 10
    ch.height  = h
    ch.width   = w
    ch.y_axis.title = y_title
    ch.x_axis.title = x_title
    ch.y_axis.numFmt = "0.0"
    ch.y_axis.scaling.min = 0
    ch.y_axis.scaling.max = y_max
    ch.legend.position = "b"
    return ch

# Chart 1 — Overhead vs Concurrency
ch1 = make_line("Fig 3(c)  Avg Overhead vs. Concurrency", "Overhead (s)", "Workers", 70)
ch1.add_data(Reference(wc, min_col=18, min_row=3, max_row=6), titles_from_data=True)
ch1.set_categories(Reference(wc, min_col=17, min_row=4, max_row=6))
ch1.series[0].graphicalProperties.line.solidFill = "2E75B6"
ch1.series[0].graphicalProperties.line.width = 28000
ch1.series[0].marker.symbol = "circle"; ch1.series[0].marker.size = 8
wc.add_chart(ch1, "B3")

# Chart 2 — Overhead vs Fault Rate
ch2 = make_line("Fig 3(b-ii)  Overhead vs. Fault Rate", "Overhead (s)", "Fault Rate (%)", 40)
ch2.add_data(Reference(wc, min_col=21, min_row=3, max_row=6), titles_from_data=True)
ch2.set_categories(Reference(wc, min_col=20, min_row=4, max_row=6))
ch2.series[0].graphicalProperties.line.solidFill = "ED7D31"
ch2.series[0].graphicalProperties.line.width = 28000
ch2.series[0].marker.symbol = "diamond"; ch2.series[0].marker.size = 8
wc.add_chart(ch2, "K3")

# Chart 3 — SR vs Concurrency
ch3 = make_line("Fig 3(a)  Success Rate vs. Concurrency", "Success Rate (%)", "Workers", 100)
ch3.y_axis.numFmt = "0"
ch3.add_data(Reference(wc, min_col=24, min_row=3, max_row=6), titles_from_data=True)
ch3.set_categories(Reference(wc, min_col=23, min_row=4, max_row=6))
ch3.series[0].graphicalProperties.line.solidFill = "70AD47"
ch3.series[0].graphicalProperties.line.width = 28000
ch3.series[0].marker.symbol = "square"; ch3.series[0].marker.size = 8
wc.add_chart(ch3, "B22")

# Chart 4 — SR vs Fault Rate
ch4 = make_line("Fig 3(b)  Success Rate vs. Fault Rate", "Success Rate (%)", "Fault Rate (%)", 100)
ch4.y_axis.numFmt = "0"
ch4.add_data(Reference(wc, min_col=27, min_row=3, max_row=6), titles_from_data=True)
ch4.set_categories(Reference(wc, min_col=26, min_row=4, max_row=6))
ch4.series[0].graphicalProperties.line.solidFill = "70AD47"
ch4.series[0].graphicalProperties.line.width = 28000
ch4.series[0].marker.symbol = "square"; ch4.series[0].marker.size = 8
wc.add_chart(ch4, "K22")

# Chart 5 — Workload Breakdown (multi-series)
ch5 = make_line("Fig 3(d)  Overhead Breakdown vs. Workload", "Time (s)", "Concurrent Queries", 160, h=14, w=38)
ch5.y_axis.numFmt = "0"
ch5.add_data(Reference(wc, min_col=30, min_row=3, max_row=6, max_col=34), titles_from_data=True)
ch5.set_categories(Reference(wc, min_col=29, min_row=4, max_row=6))
clrs  = ["1F3864","2E75B6","70AD47","ED7D31"]
mks   = ["circle","diamond","square","triangle"]
for i, (col, mk) in enumerate(zip(clrs, mks)):
    ch5.series[i].graphicalProperties.line.solidFill  = col
    ch5.series[i].graphicalProperties.line.width = 24000
    ch5.series[i].marker.symbol = mk
    ch5.series[i].marker.size   = 7
wc.add_chart(ch5, "B41")

out = r"D:\Programming\Personal_Projects\TerraMind\FIG3_Performance_Charts.xlsx"
wb.save(out)
print("saved:", out)
