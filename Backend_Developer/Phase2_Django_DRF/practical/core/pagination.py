"""
Custom DRF Pagination Classes
═══════════════════════════════
INTERVIEW: PageNumber vs Cursor pagination fark?
  PageNumber: ?page=3&page_size=20
    + Easy to implement, jump to any page
    - Inconsistent for rapidly changing data (items shift between pages)
    - Expensive COUNT(*) on large tables

  CursorPagination: ?cursor=<encoded_position>
    + Stable — new items don't shift existing pages
    + No COUNT needed — scalable for huge tables
    - Cannot jump to arbitrary page
    - Best for: feeds, timelines, infinite scroll

  LimitOffset: ?limit=20&offset=40
    + Fine-grained control
    - Same COUNT problem as PageNumber
"""

from rest_framework.pagination import CursorPagination, PageNumberPagination
from rest_framework.response import Response


class StandardCursorPagination(CursorPagination):
    """
    Default pagination — cursor-based for feeds/timelines.
    Ordered by -created_at (newest first).
    """
    page_size            = 20
    page_size_query_param = "page_size"
    max_page_size        = 100
    ordering             = "-created_at"

    def get_paginated_response(self, data):
        return Response({
            "success": True,
            "data": {
                "results":  data,
                "next":     self.get_next_link(),
                "previous": self.get_previous_link(),
                "page_size": self.get_page_size(self.request),
            },
        })

    def get_paginated_response_schema(self, schema):
        return {
            "type": "object",
            "properties": {
                "success": {"type": "boolean"},
                "data": {
                    "type": "object",
                    "properties": {
                        "results":   schema,
                        "next":      {"type": "string", "nullable": True},
                        "previous":  {"type": "string", "nullable": True},
                        "page_size": {"type": "integer"},
                    },
                },
            },
        }


class StandardPageNumberPagination(PageNumberPagination):
    """
    Page-number pagination — for admin panels, search results.
    Provides total count and page info.
    """
    page_size             = 20
    page_size_query_param = "page_size"
    max_page_size         = 200
    page_query_param      = "page"

    def get_paginated_response(self, data):
        return Response({
            "success": True,
            "data": {
                "results":     data,
                "count":       self.page.paginator.count,
                "total_pages": self.page.paginator.num_pages,
                "page":        self.page.number,
                "page_size":   self.get_page_size(self.request),
                "next":        self.get_next_link(),
                "previous":    self.get_previous_link(),
            },
        })
