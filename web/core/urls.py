from django.urls import path, include
from django.conf import settings
from . import views

app_name = "core"

urlpatterns = [
    # главная (landing)
    path("", views.landing_view, name="landing"),

    # анонимизация (UI)
    path("anonymize/", views.anonymize, name="anonymize"),

    # аутентификация / регистрация
    path("register/", views.register_view, name="register"),
    path("login/", views.login_view, name="login"),
    path("logout/", views.logout_view, name="logout"),

    # функциональные страницы
    path("history/", views.history_view, name="history"),
    path("history/<int:pk>/", views.history_detail_view, name="history_detail"),
    path("history/delete/<int:pk>/", views.delete_history, name="delete_history"),
    path("profile/", views.profile_view, name="profile"),
    path("settings/", views.settings_view, name="settings"),

    # API
    path("api/", include(("web.core.api_urls", "core"), namespace="api")),
]

# Тестовые маршруты для проверки страниц ошибок (только в DEBUG режиме)
if settings.DEBUG:
    urlpatterns += [
        path("test-error/400/", views.error_400, name="test_error_400"),
        path("test-error/403/", views.error_403, name="test_error_403"),
        path("test-error/404/", views.error_404, name="test_error_404"),
        path("test-error/500/", views.error_500, name="test_error_500"),
    ]