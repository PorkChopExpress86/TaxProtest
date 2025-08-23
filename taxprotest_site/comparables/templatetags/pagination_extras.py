from django import template

register = template.Library()

@register.filter
def page_range(total_pages, current_page):
    """Generate a range of page numbers around current page."""
    try:
        total = int(total_pages)
        current = int(current_page)
        start = max(1, current - 2)
        end = min(total, current + 2)
        return range(start, end + 1)
    except (ValueError, TypeError):
        return range(1, 2)
