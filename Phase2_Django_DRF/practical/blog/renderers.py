"""
Custom DRF Renderers
═══════════════════════════════════════════════
INTERVIEW: Renderer kya hota hai?
  Serializer → Python dict → Renderer → HTTP Response body
  Default: JSONRenderer
  Custom: CSV, XML, PDF, Excel

INTERVIEW: Kab custom renderer use karte hain?
  - Data export (CSV, Excel download)
  - Legacy XML API support
  - PDF report generation
  - Different response formats for different clients
"""

import csv
import io
from rest_framework.renderers import BaseRenderer, JSONRenderer


class CSVRenderer(BaseRenderer):
    """
    Render queryset/list as downloadable CSV.

    Usage in view:
        renderer_classes = [CSVRenderer, JSONRenderer]

    Client request:
        Accept: text/csv              → CSV response
        GET /posts/?format=csv         → CSV response
        (default / Accept: application/json) → JSON
    """
    media_type = "text/csv"
    format     = "csv"
    charset    = "utf-8-sig"  # BOM for Excel compatibility

    def render(self, data, accepted_media_type=None, renderer_context=None):
        # Handle paginated response
        if isinstance(data, dict):
            if "results" in data:
                rows = data["results"]
            elif "data" in data and isinstance(data["data"], list):
                rows = data["data"]
            else:
                rows = [data]
        elif isinstance(data, list):
            rows = data
        else:
            return ""

        if not rows:
            return ""

        output  = io.StringIO()
        headers = list(rows[0].keys()) if rows else []
        writer  = csv.DictWriter(output, fieldnames=headers, extrasaction="ignore")
        writer.writeheader()

        for row in rows:
            # Flatten nested dicts (e.g., author: {id:1, email:...} → author_email)
            flat = self._flatten(row)
            writer.writerow(flat)

        return output.getvalue()

    def _flatten(self, d: dict, parent_key: str = "", sep: str = "_") -> dict:
        """Flatten nested dict for CSV columns."""
        items = {}
        for k, v in d.items():
            new_key = f"{parent_key}{sep}{k}" if parent_key else k
            if isinstance(v, dict):
                items.update(self._flatten(v, new_key, sep=sep))
            elif isinstance(v, list):
                items[new_key] = ", ".join(str(i) for i in v)
            else:
                items[new_key] = v
        return items


class PlainTextRenderer(BaseRenderer):
    """For streaming text responses (LLM tokens, logs)."""
    media_type = "text/plain"
    format     = "txt"
    charset    = "utf-8"

    def render(self, data, accepted_media_type=None, renderer_context=None):
        if isinstance(data, str):
            return data
        return str(data)
