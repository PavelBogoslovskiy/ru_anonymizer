from django.contrib import admin
from django.urls import path, include
from django.contrib.auth import views as auth_views
from web.core import views as core_views

urlpatterns = [
    path("admin/", admin.site.urls),

    # core app (namespaced)
    path("", include(("web.core.urls", "core"), namespace="core")),

    # глобальные имена, которые могут использоваться в шаблонах без namespace
    path("register/", core_views.register_view, name="register"),
    path(
        "login/",
        auth_views.LoginView.as_view(template_name="registration/login.html"),
        name="login",
    ),
    path(
        "logout/",
        auth_views.LogoutView.as_view(next_page="/"),
        name="logout",
    ),
]

# Обработчики ошибок
handler400 = 'web.core.views.error_400'
handler403 = 'web.core.views.error_403'
handler404 = 'web.core.views.error_404'
handler500 = 'web.core.views.error_500'