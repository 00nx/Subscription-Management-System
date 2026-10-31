"""Tabular PDF for reports (A4 landscape): title, filter/summary lines, repeated column header, page numbers."""
from datetime import date

from fpdf import FPDF

from app.core.config import get_settings

PDF_ROW_LIMIT = 2_000  # a PDF is for reading; use CSV for the complete data


def _t(v) -> str:
    return ("" if v is None else str(v.value if hasattr(v, "value") else v)).encode("latin-1", "replace").decode("latin-1")


class _ReportPDF(FPDF):
    def __init__(self, title: str, columns: list[str]):
        super().__init__(orientation="L", format="A4")
        self.title_text, self.columns, self.col_w = title, columns, (277 / max(len(columns), 1))
        self.set_margins(10, 10, 10)
        self.set_auto_page_break(auto=True, margin=16)
        self.alias_nb_pages()
        self.body_started = False

    def header(self):
        if self.page_no() > 1:
            self.set_font("Helvetica", "B", 10)
            self.cell(0, 6, _t(f"{self.title_text} (continued)"), new_x="LMARGIN", new_y="NEXT")
        if self.body_started:
            self.col_header()

    def footer(self):
        self.set_y(-12)
        self.set_font("Helvetica", "", 8)
        self.set_text_color(100, 116, 139)
        self.cell(0, 5, _t(f"{get_settings().business_name} - generated {date.today().isoformat()}"), align="L")
        self.set_x(10)
        self.cell(0, 5, f"Page {self.page_no()} of {{nb}}", align="R")
        self.set_text_color(15, 23, 42)

    def col_header(self):
        self.set_fill_color(241, 245, 249)
        self.set_font("Helvetica", "B", 8)
        for c in self.columns:
            self.cell(self.col_w, 6, _t(c.replace("_", " ").title()), fill=True)
        self.ln()
        self.set_font("Helvetica", "", 8)


def render_table_pdf(title: str, lines: list[str], columns: list[str], rows: list[dict], truncated: bool = False) -> bytes:
    pdf = _ReportPDF(title, columns)
    pdf.add_page()
    pdf.set_font("Helvetica", "B", 16)
    pdf.set_text_color(79, 70, 229)
    pdf.cell(0, 9, _t(f"{get_settings().business_name} - {title}"), new_x="LMARGIN", new_y="NEXT")
    pdf.set_text_color(15, 23, 42)
    pdf.set_font("Helvetica", "", 9)
    for ln in lines:
        pdf.cell(0, 5, _t(ln), new_x="LMARGIN", new_y="NEXT")
    pdf.ln(3)
    pdf.body_started = True
    pdf.col_header()
    for r in rows:
        for c in columns:
            pdf.cell(pdf.col_w, 5.5, _t(r.get(c))[: max(int(pdf.col_w / 1.9), 8)])
        pdf.ln()
    if not rows:
        pdf.cell(0, 8, "No rows match these filters.", new_x="LMARGIN", new_y="NEXT")
    if truncated:
        pdf.ln(2)
        pdf.cell(0, 5, f"Showing the first {PDF_ROW_LIMIT} rows. Export CSV for the complete data.", new_x="LMARGIN", new_y="NEXT")
    return bytes(pdf.output())
