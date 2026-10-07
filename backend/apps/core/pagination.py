from rest_framework.pagination import PageNumberPagination


class PageNumberWithSize(PageNumberPagination):
    """25 per page; ?page_size= up to 200 for pickers and short reference lists."""

    page_size = 25
    page_size_query_param = "page_size"
    max_page_size = 200
