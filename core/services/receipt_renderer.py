"""
Receipt HTML renderer.

Shared by the desktop app (opens the HTML in the browser, which provides the
print dialog) and the web app (opens it in a new window and prints). Rendering
purely from the STORED sale + sale_items means a reprint never recalculates and
never creates new records — the printed totals always match what was saved.
"""
import html
import json

# Physical widths for the printable area per paper size.
_PAPER_WIDTH = {
    "58mm":   "54mm",
    "80mm":   "72mm",
    "Letter": "8.5in",
    "A4":     "210mm",
}


def _peso(n) -> str:
    try:
        return f"₱{float(n):,.2f}"
    except (TypeError, ValueError):
        return "₱0.00"


def _esc(s) -> str:
    return html.escape(str(s if s is not None else ""))


def render_receipt_html(sale: dict, settings: dict = None) -> str:
    """
    Build a standalone, printable HTML receipt.

    ``sale`` is the dict returned by PosService.get_sale_detail (header fields
    plus an ``items`` list). ``settings`` overrides the receipt-print options;
    when omitted the snapshot stored on the sale is used so old receipts keep
    their original store name / footer.
    """
    snap = {}
    if sale.get("receipt_snapshot"):
        try:
            snap = json.loads(sale["receipt_snapshot"])
        except (ValueError, TypeError):
            snap = {}
    cfg = dict(snap)
    if settings:
        cfg.update(settings)

    paper = cfg.get("paper_size", "80mm")
    width = _PAPER_WIDTH.get(paper, "72mm")
    is_narrow = paper in ("58mm", "80mm")
    show_sku = cfg.get("show_sku", True)
    show_cashier = cfg.get("show_cashier", True)
    show_tax = cfg.get("show_tax_breakdown", True)

    store_name = cfg.get("store_name") or "Inventra Store"
    address = cfg.get("store_address") or ""
    phone = cfg.get("store_phone") or ""
    footer = cfg.get("receipt_footer") or ""

    # ── Line items ───────────────────────────────────────────────────
    rows = []
    for it in sale.get("items", []):
        name = _esc(it.get("name"))
        sku = _esc(it.get("sku"))
        qty = it.get("quantity", 0)
        price = it.get("unit_price", 0)
        disc = it.get("discount", 0) or 0
        total = it.get("line_total", 0)
        name_cell = name
        if show_sku and sku:
            name_cell += f'<div class="sku">{sku}</div>'
        disc_note = f' <span class="disc">(−{_peso(disc)})</span>' if disc else ""
        rows.append(
            f'<tr><td class="it">{name_cell}'
            f'<div class="ql">{qty} × {_peso(price)}{disc_note}</div></td>'
            f'<td class="amt">{_peso(total)}</td></tr>'
        )
    items_html = "".join(rows)

    # ── Totals ───────────────────────────────────────────────────────
    total_rows = [_total_row("Subtotal", sale.get("subtotal", 0))]
    if (sale.get("discount_total") or 0) > 0:
        disc_label = "Discount"
        if sale.get("discount_type") == "percent" and sale.get("discount_value"):
            disc_label = f"Discount ({sale.get('discount_value'):g}%)"
        total_rows.append(_total_row(disc_label, -abs(sale.get("discount_total", 0))))
    if show_tax and sale.get("tax_enabled"):
        rate = sale.get("tax_rate", 0)
        tname = _esc(sale.get("tax_name") or "Tax")
        total_rows.append(_total_row("Taxable", sale.get("taxable_amount", 0)))
        total_rows.append(_total_row(f"{tname} ({rate:g}%)", sale.get("tax_amount", 0)))
    fees = sale.get("fees") or []
    if fees:
        for f in fees:
            total_rows.append(_total_row(f.get("name", "Fee"), f.get("amount", 0)))
    elif (sale.get("labor_amount") or 0) > 0:   # legacy sales w/o itemized fees
        total_rows.append(_total_row("Labor", sale.get("labor_amount", 0)))
    total_rows.append(_total_row("TOTAL", sale.get("grand_total", 0), strong=True))
    total_rows.append(_total_row(
        f"Paid ({_esc(sale.get('payment_method'))})", sale.get("amount_received", 0)))
    if (sale.get("change_due") or 0) > 0:
        total_rows.append(_total_row("Change", sale.get("change_due", 0)))
    totals_html = "".join(total_rows)

    meta_rows = [
        f'<div><span>Receipt</span><b>{_esc(sale.get("receipt_no"))}</b></div>',
        f'<div><span>Date</span><b>{_esc((sale.get("sale_date") or "")[:19].replace("T", " "))}</b></div>',
    ]
    if show_cashier:
        meta_rows.append(f'<div><span>Cashier</span><b>{_esc(sale.get("cashier"))}</b></div>')
    meta_html = "".join(meta_rows)

    body_font = "12px" if is_narrow else "13px"
    head_size = "16px" if is_narrow else "20px"

    return f"""<!DOCTYPE html>
<html><head><meta charset="utf-8"><title>Receipt {_esc(sale.get('receipt_no'))}</title>
<style>
  * {{ box-sizing: border-box; }}
  body {{ margin: 0; background: #f3f3f3; font-family: 'Courier New', monospace;
          color: #111; }}
  .receipt {{ width: {width}; max-width: 100%; margin: 12px auto; background: #fff;
              padding: 14px 14px 18px; font-size: {body_font}; line-height: 1.4; }}
  .store {{ text-align: center; }}
  .store h1 {{ font-size: {head_size}; margin: 0 0 4px; }}
  .store .sub {{ font-size: 11px; color: #444; }}
  hr {{ border: none; border-top: 1px dashed #999; margin: 10px 0; }}
  .meta div {{ display: flex; justify-content: space-between; font-size: 11px; }}
  .meta span {{ color: #555; }}
  table {{ width: 100%; border-collapse: collapse; }}
  td.it {{ padding: 3px 0; }}
  td.amt {{ padding: 3px 0; text-align: right; white-space: nowrap; vertical-align: top; }}
  .sku {{ font-size: 10px; color: #777; }}
  .ql {{ font-size: 11px; color: #555; }}
  .disc {{ color: #b00; }}
  .totals div {{ display: flex; justify-content: space-between; padding: 2px 0; }}
  .totals .strong {{ font-weight: bold; font-size: 14px; border-top: 1px solid #000;
                     margin-top: 4px; padding-top: 6px; }}
  .footer {{ text-align: center; margin-top: 12px; font-size: 11px; white-space: pre-line; }}
  .pbar {{ text-align: center; margin: 10px; }}
  .pbar button {{ font: inherit; padding: 8px 18px; cursor: pointer; }}
  @media print {{ body {{ background: #fff; }} .receipt {{ margin: 0; }} .pbar {{ display: none; }} }}
</style></head>
<body>
  <div class="pbar"><button onclick="window.print()">Print</button></div>
  <div class="receipt">
    <div class="store">
      <h1>{_esc(store_name)}</h1>
      {f'<div class="sub">{_esc(address)}</div>' if address else ''}
      {f'<div class="sub">{_esc(phone)}</div>' if phone else ''}
    </div>
    <hr>
    <div class="meta">{meta_html}</div>
    <hr>
    <table>{items_html}</table>
    <hr>
    <div class="totals">{totals_html}</div>
    {f'<div class="footer">{_esc(footer)}</div>' if footer else ''}
  </div>
</body></html>"""


def _total_row(label, value, strong=False):
    cls = ' class="strong"' if strong else ""
    return f'<div{cls}><span>{_esc(label)}</span><span>{_peso(value)}</span></div>'
