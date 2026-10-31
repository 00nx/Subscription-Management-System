from fpdf import FPDF

from app.core.config import get_settings
from app.modules.invoices.models import Invoice

BRAND = (79, 70, 229)
INK = (15, 23, 42)
MUTED = (100, 116, 139)
WIDTHS = [64, 12, 26, 24, 14, 22, 28]  # sums to 190 (A4 width minus 10 mm margins)
HEADS = ["Description", "Qty", "Unit price", "Discount", "Tax %", "Tax", "Total"]


def _t(s) -> str:
    """Core PDF fonts are latin-1 only: replace anything else rather than crash."""
    return str(s if s is not None else "").encode("latin-1", "replace").decode("latin-1")


class _InvoicePDF(FPDF):
    def __init__(self, inv: Invoice):
        super().__init__(format="A4")
        self.inv, self.table_open = inv, False
        self.set_margins(10, 10, 10)
        self.set_auto_page_break(auto=True, margin=22)
        self.alias_nb_pages()

    def header(self):
        # Page 1 carries the full letterhead (drawn in render); later pages get a slim header and the table header again.
        if self.page_no() > 1:
            self.set_font("Helvetica", "B", 10)
            self.set_text_color(*BRAND)
            self.cell(95, 6, _t(get_settings().business_name))
            self.set_text_color(*INK)
            self.cell(0, 6, _t(f"Invoice {self.inv.number} (continued)"), align="R", new_x="LMARGIN", new_y="NEXT")
            self.ln(2)
            if self.table_open:
                self.table_header()

    def footer(self):
        self.set_y(-14)
        self.set_font("Helvetica", "", 8)
        self.set_text_color(*MUTED)
        self.cell(0, 5, _t(f"{get_settings().business_name} - {self.inv.number}"), align="L")
        self.set_x(10)
        self.cell(0, 5, f"Page {self.page_no()} of {{nb}}", align="R")

    def table_header(self):
        self.set_fill_color(241, 245, 249)
        self.set_text_color(*INK)
        self.set_font("Helvetica", "B", 9)
        for w, h in zip(WIDTHS, HEADS):
            self.cell(w, 7, h, fill=True, align="L" if h == "Description" else "R")
        self.ln()
        self.set_font("Helvetica", "", 9)


def render_invoice_pdf(inv: Invoice) -> bytes:
    cfg, c, cur = get_settings(), inv.customer_snapshot or {}, inv.currency
    pdf = _InvoicePDF(inv)
    pdf.add_page()

    # Letterhead: business on the left, invoice identity on the right
    pdf.set_text_color(*BRAND)
    pdf.set_font("Helvetica", "B", 22)
    pdf.cell(110, 10, _t(cfg.business_name))
    pdf.set_text_color(*INK)
    pdf.set_font("Helvetica", "B", 16)
    pdf.cell(0, 10, "INVOICE", align="R", new_x="LMARGIN", new_y="NEXT")
    pdf.set_font("Helvetica", "", 9)
    pdf.set_text_color(*MUTED)
    biz = [cfg.business_tagline, *cfg.business_address.splitlines(), cfg.business_email, cfg.business_phone, f"Tax ID: {cfg.business_tax_id}" if cfg.business_tax_id else ""]
    meta = [f"No. {inv.number}", f"Status: {inv.status.value.replace('_', ' ').title()}" + (" (overdue)" if inv.is_overdue else "")]
    for i in range(max(len(biz), len(meta))):
        pdf.cell(110, 4.5, _t(biz[i] if i < len(biz) else ""))
        pdf.cell(0, 4.5, _t(meta[i] if i < len(meta) else ""), align="R", new_x="LMARGIN", new_y="NEXT")
    pdf.set_text_color(*INK)
    pdf.ln(6)

    pdf.set_font("Helvetica", "B", 10)
    pdf.cell(110, 5, "Bill to")
    pdf.cell(0, 5, "Details", new_x="LMARGIN", new_y="NEXT")
    pdf.set_font("Helvetica", "", 10)
    left = [c.get("name"), c.get("company_name"), c.get("email"), *(c.get("billing_address") or "").splitlines(), f"Tax ID: {c['tax_id']}" if c.get("tax_id") else None]
    right = [f"Issue date: {inv.issue_date}", f"Due date: {inv.due_date}", f"Payment terms: {inv.payment_terms_days} day(s)",
             f"Subscription: {inv.subscription_number}" if inv.subscription_number else None,
             f"Billing period: {inv.period_start} to {inv.period_end}" if inv.period_start else None]
    left, right = [x for x in left if x], [x for x in right if x]
    for i in range(max(len(left), len(right))):
        pdf.cell(110, 5, _t(left[i] if i < len(left) else ""))
        pdf.cell(0, 5, _t(right[i] if i < len(right) else ""), new_x="LMARGIN", new_y="NEXT")
    pdf.ln(6)

    pdf.table_open = True
    pdf.table_header()
    for l in inv.lines:
        extra = [f"{v.get('attribute')}: {v.get('value')} (+{v.get('additional_price')})" for v in (l.variants or [])]
        h = 6 + 4 * len(extra)
        if pdf.get_y() + h > pdf.h - 22:  # keep a line and its variants together; the table header repeats via header()
            pdf.add_page()
        y = pdf.get_y()
        pdf.set_font("Helvetica", "", 9)
        for w, v, head in zip(WIDTHS, [l.description, l.quantity, l.unit_price, l.discount_amount, l.tax_rate, l.tax_amount, l.line_total], HEADS):
            pdf.cell(w, 6, _t(v)[:40] if head == "Description" else _t(v), align="L" if head == "Description" else "R")
        pdf.ln()
        pdf.set_font("Helvetica", "I", 8)
        pdf.set_text_color(*MUTED)
        for e in extra:
            pdf.set_x(12)
            pdf.cell(WIDTHS[0] - 2, 4, _t(e)[:48], new_x="LMARGIN", new_y="NEXT")
        pdf.set_text_color(*INK)
        pdf.line(10, pdf.get_y() + 0.5, 200, pdf.get_y() + 0.5) if y else None
        pdf.ln(1)
    pdf.table_open = False
    pdf.ln(3)

    def need(h):
        if pdf.get_y() + h > pdf.h - 22:
            pdf.add_page()

    def row(label, value, bold=False):
        pdf.set_font("Helvetica", "B" if bold else "", 10)
        pdf.cell(110, 6, "")
        pdf.cell(50, 6, _t(label), align="R")
        pdf.cell(30, 6, _t(f"{cur} {value}"), align="R", new_x="LMARGIN", new_y="NEXT")

    need(70)
    row("Subtotal", inv.subtotal)
    for d in inv.discount_breakdown or []:  # each applied discount by name
        row(f"Discount: {d['name']}"[:34], f"-{d['amount']}")
    if inv.discount_total and not inv.discount_breakdown:
        row("Discount", f"-{inv.discount_total}")
    for t in inv.tax_breakdown or []:
        row(f"{t['name']} ({t['rate']}%)"[:34], t["amount"])
    if not inv.tax_breakdown:
        row("Tax", inv.tax_total)
    row("Total", inv.total, True)
    row("Paid", inv.amount_paid)
    row("Outstanding", inv.outstanding, True)
    pdf.ln(8)
    pdf.set_font("Helvetica", "B", 9)
    pdf.set_text_color(*INK)
    pdf.cell(0, 5, "Payment instructions", new_x="LMARGIN", new_y="NEXT")
    pdf.set_font("Helvetica", "", 9)
    pdf.set_text_color(*MUTED)
    pdf.multi_cell(0, 5, _t(cfg.payment_instructions) + f"\nReference: {inv.number}. Due by {inv.due_date}.")
    if inv.notes:
        pdf.ln(2)
        pdf.multi_cell(0, 5, _t("Notes: " + inv.notes))
    return bytes(pdf.output())
