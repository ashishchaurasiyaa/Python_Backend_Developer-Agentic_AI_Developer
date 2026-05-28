# 04 — PDF & Excel Generation

> Generate invoices, reports, receipts, exports. Common backend job that becomes painful at scale.

---

## PDF Generation

### Approaches

| Tool | Use case |
|---|---|
| **WeasyPrint** | HTML/CSS → PDF (reports, invoices) — easiest |
| **ReportLab** | Programmatic (forms, complex layouts) |
| **Playwright / Puppeteer** | Render web page → PDF (catches modern CSS) |
| **PyMuPDF / fitz** | Read/modify existing PDFs |
| **wkhtmltopdf** | Legacy, deprecated |

---

## WeasyPrint (HTML/CSS → PDF) — Most Common

```bash
pip install weasyprint
```

```python
from weasyprint import HTML, CSS

# From HTML file
HTML("invoice.html").write_pdf("invoice.pdf")

# From HTML string
html_content = "<h1>Invoice #1234</h1><p>Amount: $100</p>"
HTML(string=html_content).write_pdf("invoice.pdf")

# With custom CSS
HTML("invoice.html").write_pdf(
    "invoice.pdf",
    stylesheets=[CSS("style.css")]
)
```

### Jinja2 + WeasyPrint (Standard Pattern)

```python
from jinja2 import Environment, FileSystemLoader
from weasyprint import HTML

env = Environment(loader=FileSystemLoader("templates"))

def generate_invoice(invoice_data):
    template = env.get_template("invoice.html")
    html = template.render(invoice=invoice_data)
    return HTML(string=html).write_pdf()
```

`invoice.html`:
```html
<!DOCTYPE html>
<html>
<head>
    <style>
        body { font-family: Arial; padding: 40px; }
        .header { display: flex; justify-content: space-between; }
        table { width: 100%; border-collapse: collapse; }
        th, td { padding: 8px; border-bottom: 1px solid #ddd; }
        .total { font-weight: bold; }
        @page { size: A4; margin: 1cm; }
    </style>
</head>
<body>
    <div class="header">
        <h1>Invoice #{{ invoice.number }}</h1>
        <div>Date: {{ invoice.date }}</div>
    </div>
    <h2>Bill To: {{ invoice.customer.name }}</h2>
    <table>
        <thead>
            <tr><th>Item</th><th>Qty</th><th>Price</th></tr>
        </thead>
        <tbody>
            {% for item in invoice.items %}
            <tr>
                <td>{{ item.name }}</td>
                <td>{{ item.qty }}</td>
                <td>${{ item.price }}</td>
            </tr>
            {% endfor %}
        </tbody>
    </table>
    <p class="total">Total: ${{ invoice.total }}</p>
</body>
</html>
```

WeasyPrint supports modern CSS (flexbox, grid, custom fonts, page breaks).

### Page breaks
```css
.page-break { page-break-after: always; }
@page { margin: 1cm; size: A4; }
```

### Headers & footers
```css
@page {
    @top-center { content: "My Company Invoice"; }
    @bottom-right { content: "Page " counter(page); }
}
```

### Custom fonts
```css
@font-face {
    font-family: 'Roboto';
    src: url('fonts/Roboto-Regular.ttf');
}
body { font-family: 'Roboto'; }
```

---

## ReportLab (Programmatic)

For complex programmatic PDFs (forms, schedules):

```bash
pip install reportlab
```

```python
from reportlab.lib.pagesizes import letter
from reportlab.platypus import SimpleDocTemplate, Paragraph, Table, TableStyle
from reportlab.lib.styles import getSampleStyleSheet
from reportlab.lib import colors

doc = SimpleDocTemplate("report.pdf", pagesize=letter)
styles = getSampleStyleSheet()

story = []
story.append(Paragraph("Q1 Sales Report", styles["Title"]))
story.append(Paragraph("Generated automatically", styles["Normal"]))

data = [
    ["Region", "Sales"],
    ["North", "$50,000"],
    ["South", "$45,000"],
]
table = Table(data)
table.setStyle(TableStyle([
    ("BACKGROUND", (0, 0), (-1, 0), colors.grey),
    ("TEXTCOLOR", (0, 0), (-1, 0), colors.whitesmoke),
    ("ALIGN", (0, 0), (-1, -1), "CENTER"),
    ("GRID", (0, 0), (-1, -1), 1, colors.black),
]))
story.append(table)

doc.build(story)
```

More control, more verbose. Use when HTML/CSS doesn't fit.

---

## Playwright PDF (Render Real Browser)

When you need modern CSS that WeasyPrint doesn't support (CSS animations, JS-rendered content):

```bash
pip install playwright
playwright install chromium
```

```python
from playwright.async_api import async_playwright

async def html_to_pdf(html_content, output):
    async with async_playwright() as p:
        browser = await p.chromium.launch()
        page = await browser.new_page()
        await page.set_content(html_content)
        await page.pdf(path=output, format="A4", print_background=True)
        await browser.close()
```

Slower (~2-5s per PDF), but most accurate rendering.

---

## PyMuPDF / fitz (Manipulate Existing PDFs)

```bash
pip install pymupdf
```

```python
import fitz

# Open existing
doc = fitz.open("input.pdf")
print(f"{doc.page_count} pages")

# Extract text
for page in doc:
    print(page.get_text())

# Extract images
for page in doc:
    for img_idx, img in enumerate(page.get_images()):
        xref = img[0]
        base_image = doc.extract_image(xref)
        with open(f"img_{img_idx}.png", "wb") as f:
            f.write(base_image["image"])

# Merge PDFs
merged = fitz.open()
for pdf_file in ["a.pdf", "b.pdf"]:
    merged.insert_pdf(fitz.open(pdf_file))
merged.save("merged.pdf")

# Split
doc = fitz.open("big.pdf")
for i, page in enumerate(doc):
    new = fitz.open()
    new.insert_pdf(doc, from_page=i, to_page=i)
    new.save(f"page_{i+1}.pdf")

# Add watermark
for page in doc:
    rect = fitz.Rect(50, 50, 200, 100)
    page.insert_textbox(rect, "CONFIDENTIAL", color=(1, 0, 0))
doc.save("watermarked.pdf")
```

---

## Excel Generation

### openpyxl (modern xlsx)

```bash
pip install openpyxl
```

```python
from openpyxl import Workbook
from openpyxl.styles import Font, PatternFill, Alignment
from openpyxl.utils import get_column_letter

wb = Workbook()
ws = wb.active
ws.title = "Sales"

# Headers with styling
headers = ["Date", "Customer", "Amount", "Status"]
for col, header in enumerate(headers, 1):
    cell = ws.cell(row=1, column=col, value=header)
    cell.font = Font(bold=True, color="FFFFFF")
    cell.fill = PatternFill("solid", fgColor="0066CC")
    cell.alignment = Alignment(horizontal="center")

# Data rows
data = [
    ("2024-01-01", "Alice", 100, "Paid"),
    ("2024-01-02", "Bob", 200, "Pending"),
]
for row in data:
    ws.append(row)

# Auto-size columns
for col in range(1, len(headers) + 1):
    ws.column_dimensions[get_column_letter(col)].width = 15

# Add formula
ws.cell(row=len(data) + 2, column=3, value=f"=SUM(C2:C{len(data) + 1})")

wb.save("sales.xlsx")
```

### Charts
```python
from openpyxl.chart import BarChart, Reference

chart = BarChart()
data = Reference(ws, min_col=3, min_row=1, max_col=3, max_row=len(data) + 1)
chart.add_data(data, titles_from_data=True)
ws.add_chart(chart, "E2")
```

---

## Pandas to Excel (Fast Path)

For tabular data:

```python
import pandas as pd

df = pd.DataFrame({
    "Date": [...],
    "Customer": [...],
    "Amount": [...]
})
df.to_excel("output.xlsx", index=False, sheet_name="Sales")

# Multiple sheets
with pd.ExcelWriter("output.xlsx") as writer:
    df1.to_excel(writer, sheet_name="Sales")
    df2.to_excel(writer, sheet_name="Refunds")
```

Most convenient for data exports.

---

## CSV (Simpler, Larger Datasets)

```python
import csv

with open("export.csv", "w", newline="") as f:
    writer = csv.writer(f)
    writer.writerow(["Date", "Customer", "Amount"])
    writer.writerows(data)

# With dict
with open("export.csv", "w") as f:
    writer = csv.DictWriter(f, fieldnames=["date", "customer", "amount"])
    writer.writeheader()
    writer.writerows(records)
```

For data exports > 100K rows: CSV is faster and smaller than Excel.

---

## Streaming Large Exports

Don't buffer 1M rows in memory.

```python
from fastapi.responses import StreamingResponse
import csv
import io

async def stream_csv(rows_iter):
    buffer = io.StringIO()
    writer = csv.writer(buffer)
    writer.writerow(["id", "name", "amount"])
    yield buffer.getvalue()
    buffer.seek(0); buffer.truncate(0)

    async for row in rows_iter:
        writer.writerow(row)
        yield buffer.getvalue()
        buffer.seek(0); buffer.truncate(0)

@app.get("/export")
async def export(user=Depends(get_user)):
    rows = db.iterate("SELECT * FROM orders WHERE user_id = $1", user.id)
    return StreamingResponse(
        stream_csv(rows),
        media_type="text/csv",
        headers={"Content-Disposition": "attachment; filename=orders.csv"}
    )
```

Sends bytes as generated; memory constant.

---

## Generation in Background (Async)

PDF/Excel generation is slow (1-30s). Don't block API.

### Pattern: async with Celery

```python
@app.post("/reports/generate")
async def request_report(req: ReportRequest, user=Depends(get_user)):
    job_id = str(uuid.uuid4())
    await db.execute(
        "INSERT INTO reports (id, user_id, status) VALUES ($1, $2, 'queued')",
        job_id, user.id
    )
    generate_report_task.delay(job_id, req.dict())
    return {"job_id": job_id}

@celery.task
def generate_report_task(job_id, params):
    # Generate PDF/Excel
    pdf_bytes = generate_pdf(params)
    # Upload to S3
    key = f"reports/{job_id}.pdf"
    s3.put_object(Bucket=BUCKET, Key=key, Body=pdf_bytes)
    # Update status
    db.execute(
        "UPDATE reports SET status = 'done', download_key = $1 WHERE id = $2",
        key, job_id
    )
    # Notify user
    send_email(user, "Your report is ready", f"Download: /reports/{job_id}")

@app.get("/reports/{job_id}/status")
async def report_status(job_id: UUID):
    return await db.fetch_one("SELECT status, download_key FROM reports WHERE id = $1", job_id)
```

---

## Memory Considerations

### PDF
- Each PDF: 1-50 MB depending on content.
- WeasyPrint can use 500+ MB for complex docs.
- Use ProcessPool to isolate memory.

### Excel
- openpyxl loads entire workbook in memory.
- For 100K+ rows: use `write_only` mode:
```python
wb = Workbook(write_only=True)
ws = wb.create_sheet()
ws.append(headers)
for row in millions_of_rows:
    ws.append(row)
wb.save("huge.xlsx")
```

Or stream to CSV instead.

---

## i18n Considerations

### Currency formatting
```python
import locale
locale.setlocale(locale.LC_ALL, "en_IN.UTF-8")
formatted = locale.currency(100000, grouping=True)   # "₹1,00,000.00"
```

### Date formatting
```python
from datetime import datetime
import locale

dt = datetime.now()
locale.setlocale(locale.LC_TIME, "es_ES.UTF-8")
print(dt.strftime("%A, %d de %B de %Y"))   # Spanish format
```

### Right-to-left languages
WeasyPrint supports `direction: rtl` for Arabic/Hebrew.

---

## Common Pitfalls

### 1. Generating PDF in API request
30-second blocking call. Use background queue.

### 2. Loading 1M-row Excel in memory
Use `write_only` mode or stream as CSV.

### 3. Bundling fonts incorrectly
Custom fonts missing → fallback to ugly default.

### 4. Color management
Print PDFs need CMYK; screen PDFs use RGB. WeasyPrint defaults to RGB.

### 5. No file naming convention
Generated reports with same name overwrite. Include timestamp + UUID.

### 6. Exposing internal data in PDFs
Strip sensitive fields before rendering.

### 7. Sync image fetch in templates
Each `<img>` tag fetched serially. Pre-download + base64 encode for templates.

---

## Production Patterns

### Caching
Same parameters → same PDF. Cache by hash of params.

```python
async def get_or_generate_pdf(params):
    cache_key = hashlib.sha256(json.dumps(params, sort_keys=True).encode()).hexdigest()
    cached = await redis.get(f"pdf:{cache_key}")
    if cached:
        return cached
    pdf = await generate_pdf(params)
    await redis.setex(f"pdf:{cache_key}", 3600, pdf)
    return pdf
```

### CDN for static branded PDFs
Generated PDFs uploaded to S3 + served via CloudFront. Long TTL.

### Quotas
Limit PDF generations per user (expensive).

### Audit log
Track who generated what for compliance.

---

## TL;DR

- **PDF:** WeasyPrint (HTML/CSS) for 90% of cases.
- **Excel:** openpyxl or pandas; use `write_only` for huge files.
- **CSV:** For tabular exports > 100K rows.
- **Streaming:** Don't buffer huge exports.
- **Background:** Generation goes to Celery/queue, not API request.
- **Cache** generated files by parameter hash.
- **i18n + fonts**: pre-load and bundle.
- **Memory:** PDF generation is expensive; use ProcessPool.
