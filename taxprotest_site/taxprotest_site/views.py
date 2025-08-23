from django.http import JsonResponse
from django.utils.timezone import now


def health(request):
    return JsonResponse({
        "status": "ok",
        "time": now().isoformat(),
    })
