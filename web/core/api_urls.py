from django.http import JsonResponse
from django.urls import path

def api_root(request):
    return JsonResponse({"status": "ok", "message": "Core API placeholder"})

urlpatterns = [
    path("", api_root, name="api_root"),
]