from __future__ import annotations

from django import template
from django.utils.html import conditional_escape, mark_safe
import re

register = template.Library()


@register.filter(name="highlight")
def highlight(value: str, needle: str):  # pragma: no cover - presentation logic
    if not value:
        return ""
    if not needle:
        return conditional_escape(value)
    pattern = re.escape(needle)

    def repl(m):
        return f"<mark>{conditional_escape(m.group(0))}</mark>"

    return mark_safe(re.sub(pattern, repl, value, flags=re.IGNORECASE))
