import os, yaml
import re
from django.shortcuts import render, redirect, get_object_or_404
from django.contrib import messages
from django.contrib.auth import authenticate, login, logout
from django.contrib.auth.decorators import login_required
from django.db import IntegrityError

from .models import AnonymizationHistory, Profile
from .forms import RegisterForm, SettingsForm
import json
import base64
from django.http import JsonResponse, HttpResponseForbidden, HttpResponseBadRequest
from engine.services.text_service import TextAnonymizerService, ServiceError
import logging

logger = logging.getLogger(__name__)

anonymizer_service = TextAnonymizerService()

# Список всех поддерживаемых меток
DEFAULT_ANON_LABELS = ["PERSON", "ORG", "ADDRESS", "DOC_ID", "MONEY", "PHONE", "DATE", "EMAIL", "LOC"]

# Русские названия меток для интерфейса
LABEL_NAMES_RU = {
    "PERSON": "Персона",
    "ORG": "Организация",
    "ADDRESS": "Адрес",
    "DOC_ID": "Документ",
    "MONEY": "Деньги",
    "PHONE": "Телефон",
    "DATE": "Дата",
    "EMAIL": "Email",
    "LOC": "Локация",
}

@login_required
def anonymize(request):
    profile, _ = Profile.objects.get_or_create(user=request.user)
    settings = None
    text = ""
    result_text = ""
    original_entities = []

    if request.method == "POST":
        text = request.POST.get("text", "") or ""
        
        # Загрузка текста из файла
        uploaded_file = request.FILES.get("file")
        if uploaded_file:
            if not uploaded_file.name.lower().endswith('.txt'):
                messages.error(request, "Поддерживаются только файлы .txt")
            elif uploaded_file.size > 1024 * 1024:
                messages.error(request, "Файл слишком большой. Максимальный размер: 1 МБ")
            else:
                try:
                    file_content = uploaded_file.read()
                    # Пробуем utf-8, потом cp1251 для виндовых файлов
                    try:
                        text = file_content.decode('utf-8')
                    except UnicodeDecodeError:
                        try:
                            text = file_content.decode('cp1251')
                        except UnicodeDecodeError:
                            text = file_content.decode('utf-8', errors='replace')
                except Exception:
                    logger.exception("Ошибка чтения файла")
                    messages.error(request, "Не удалось прочитать файл")
        
        # Приводим переносы строк к единому формату
        text = text.replace('\r\n', '\n').replace('\r', '\n')
        
        # Формируем settings для сервиса анонимизации
        settings = {}
        
        # 1. config_yaml из профиля (полная конфигурация анонимизаторов)
        if profile.config_yaml:
            settings["config_yaml"] = profile.config_yaml
        
        # 2. enabled_labels: из формы > из профиля > все по умолчанию
        if 'labels' in request.POST:
            enabled_labels_form = request.POST.getlist("labels")
            settings["enabled_labels"] = enabled_labels_form
            enabled_for_user = enabled_labels_form
        else:
            profile_labels = profile.get_enabled_labels()
            if profile_labels:
                settings["enabled_labels"] = profile_labels
                enabled_for_user = profile_labels
            else:
                enabled_for_user = DEFAULT_ANON_LABELS

        try:
            # используем новый метод с возвратом сущностей для подсветки
            anon_result = anonymizer_service.anonymize_text_with_entities(text, settings=settings if settings else None)
            result_text = anon_result["text"]
            original_entities = anon_result["original_entities"]  # позиции в ОРИГИНАЛЬНОМ тексте
            # сохранение в истории анонимизации (включая entities)
            try:
                title = (text[:80] + "...") if len(text) > 80 else text
                history_item = AnonymizationHistory(
                    user=request.user,
                    title=title,
                    original=text,
                    result=result_text,
                )
                history_item.set_entities(original_entities)
                history_item.save()
            except Exception:
                logger.exception("Ошибка сохранения истории")
        except ServiceError as se:
            logger.exception("Ошибка сервиса: %s", se.internal)
            messages.error(request, se.user_message)
            result_text = ""
            original_entities = []
        except Exception:
            logger.exception("Ошибка анонимизации")
            messages.error(request, "Ошибка при анонимизации. Попробуйте позже.")
            result_text = ""
            original_entities = []

    # Загружаем историю пользователя
    history = AnonymizationHistory.objects.filter(user=request.user)[:50]

    # Формируем данные истории в base64 для передачи в шаблон
    history_items = []
    for h in history:
        payload = json.dumps({
            "original": h.original,
            "result": h.result,
            "entities": h.get_entities()
        }, ensure_ascii=False)
        b64 = base64.b64encode(payload.encode("utf-8")).decode("ascii")
        history_items.append({"obj": h, "payload": b64})

    # Все доступные метки для фильтров
    all_labels = DEFAULT_ANON_LABELS
    # Список меток с русскими названиями для чекбоксов
    labels_with_names = [(label, LABEL_NAMES_RU.get(label, label)) for label in all_labels]

    # Какие метки отмечены: из формы, потом из профиля, потом все по умолчанию
    if 'enabled_for_user' in locals() and enabled_for_user is not None:
        pass
    else:
        profile_labels = profile.get_enabled_labels()
        enabled_for_user = profile_labels if profile_labels else all_labels

    # Получаем текущие настройки mode из config_yaml
    current_config = {}
    if profile.config_yaml:
        try:
            current_config = yaml.safe_load(profile.config_yaml) or {}
        except yaml.YAMLError:
            current_config = {}
    
    anonymizers_config = current_config.get("anonymizers", {})
    address_mode = anonymizers_config.get("ADDRESS", {}).get("mode", "full")
    email_mode = anonymizers_config.get("EMAIL", {}).get("mode", "preserve_domain")

    # Готовим entities как JSON для подсветки в оригинальном тексте
    entities_json = json.dumps(original_entities if 'original_entities' in locals() else [], ensure_ascii=False)
    label_names_json = json.dumps(LABEL_NAMES_RU, ensure_ascii=False)
    return render(request, "anonymize.html", {
        "original_text": text,
        "result_text": result_text,
        "original_entities_json": entities_json,
        "labels_with_names": labels_with_names,
        "label_names_json": label_names_json,
        "enabled_labels": enabled_for_user,
        "history_items": history_items,
        "address_mode": address_mode,
        "email_mode": email_mode,
    })


@login_required
def settings_view(request):
    profile, _ = Profile.objects.get_or_create(user=request.user)
    
    # Парсим текущий config_yaml для получения настроек
    current_config = {}
    if profile.config_yaml:
        try:
            current_config = yaml.safe_load(profile.config_yaml) or {}
        except yaml.YAMLError:
            current_config = {}
    
    anonymizers_config = current_config.get("anonymizers", {})
    
    # Текущие значения mode
    address_mode = anonymizers_config.get("ADDRESS", {}).get("mode", "full")
    email_mode = anonymizers_config.get("EMAIL", {}).get("mode", "preserve_domain")

    if request.method == "POST":
        labels = request.POST.getlist('enabled_labels') or []
        new_address_mode = request.POST.get('address_mode') or "full"
        new_email_mode = request.POST.get('email_mode') or "preserve_domain"
        
        # Сохраняем enabled_labels
        profile.set_enabled_labels(labels)
        
        # Генерируем config_yaml с настройками mode
        config = {"anonymizers": {}}
        
        if new_address_mode != "full":  # Сохраняем только если отличается от дефолта
            config["anonymizers"]["ADDRESS"] = {"mode": new_address_mode}
        
        if new_email_mode != "preserve_domain":  # Сохраняем только если отличается от дефолта
            config["anonymizers"]["EMAIL"] = {"mode": new_email_mode}
        
        # Если есть настройки — сохраняем YAML, иначе пустая строка
        if config["anonymizers"]:
            profile.config_yaml = yaml.dump(config, allow_unicode=True, default_flow_style=False)
        else:
            profile.config_yaml = ""
        
        profile.save()
        
        # AJAX запрос — возвращаем JSON
        if request.headers.get('x-requested-with') == 'XMLHttpRequest':
            from django.http import HttpResponse
            return HttpResponse(status=200)
        
        # Обычный POST — редирект
        messages.success(request, "Настройки сохранены.")
        return redirect("core:settings")
    else:
        initial = {
            "enabled_labels": profile.get_enabled_labels(),
            "address_mode": address_mode,
            "email_mode": email_mode,
        }
        form = SettingsForm(initial=initial)

    # Передаём текущие enabled_labels и mode для шаблона
    enabled_labels = profile.get_enabled_labels() or DEFAULT_ANON_LABELS
    
    return render(request, "settings.html", {
        "form": form,
        "enabled_labels": enabled_labels,
        "address_mode": address_mode,
        "email_mode": email_mode,
    })


def validate_username(username):
    """Проверяет корректность имени пользователя"""
    errors = []
    if len(username) < 3:
        errors.append("Имя пользователя должно содержать минимум 3 символа.")
    if len(username) > 30:
        errors.append("Имя пользователя не должно превышать 30 символов.")
    if not re.match(r'^[\w.@+-]+$', username):
        errors.append("Имя пользователя может содержать только буквы, цифры и символы @/./+/-/_")
    return errors

def validate_password(password, password_confirm):
    """Проверяет корректность пароля"""
    errors = []
    if len(password) < 8:
        errors.append("Пароль должен содержать минимум 8 символов.")
    if not re.search(r'[A-Za-zА-Яа-яЁё]', password):
        errors.append("Пароль должен содержать хотя бы одну букву.")
    if not re.search(r'\d', password):
        errors.append("Пароль должен содержать хотя бы одну цифру.")
    if password != password_confirm:
        errors.append("Пароли не совпадают.")
    return errors

def register_view(request):
    # Если уже авторизован - на главную
    if request.user.is_authenticated:
        return redirect("core:anonymize")
    
    if request.method == "POST":
        username = request.POST.get("username", "").strip()
        password = request.POST.get("password", "")
        password_confirm = request.POST.get("password_confirm", "")

        # Валидация имени пользователя
        username_errors = validate_username(username)
        for error in username_errors:
            messages.error(request, error)
        
        # Валидация пароля
        password_errors = validate_password(password, password_confirm)
        for error in password_errors:
            messages.error(request, error)
        
        # Если есть ошибки валидации - возвращаем форму
        if username_errors or password_errors:
            return render(request, "register.html", {"username": username})

        # Проверка существования пользователя
        from django.contrib.auth.models import User
        if User.objects.filter(username=username).exists():
            messages.error(request, "Пользователь с таким именем уже существует.")
            return render(request, "register.html", {"username": username})

        try:
            user = User.objects.create_user(username=username, password=password)
        except Exception:
            logger.exception("Не удалось создать пользователя")
            messages.error(request, "Не удалось создать пользователя. Попробуйте позже.")
            return render(request, "register.html", {"username": username})

        # создаём профиль
        try:
            Profile.objects.get_or_create(user=user)
        except Exception:
            logger.exception("Не удалось создать профиль для нового пользователя")

        messages.success(request, "Аккаунт успешно создан! Войдите в систему.")
        return redirect("login")

    return render(request, "register.html", {})

def login_view(request):
    # Если уже авторизован - на главную
    if request.user.is_authenticated:
        return redirect("core:anonymize")
    
    error = None
    if request.method == "POST":
        username = request.POST.get("username")
        password = request.POST.get("password")
        user = authenticate(request, username=username, password=password)
        if user:
            login(request, user)
            next_url = request.GET.get("next") or request.POST.get("next")
            if next_url:
                return redirect(next_url)
            return redirect("core:landing")
        error = "Неверное имя пользователя или пароль"
    return render(request, "login.html", {"error": error})

def logout_view(request):
    logout(request)
    return redirect("login")

def landing_view(request):
    if request.user.is_authenticated:
        return redirect("core:anonymize")
    return render(request, "anonymize_landing.html", {"can_anonymize": False})


@login_required
def history_view(request):
    history = AnonymizationHistory.objects.filter(user=request.user)
    return render(request, "history.html", {"history": history})

@login_required
def history_detail_view(request, pk: int):
    item = get_object_or_404(AnonymizationHistory, pk=pk, user=request.user)
    return render(request, "history_detail.html", {"item": item})

@login_required
def profile_view(request):
    # Страница профиля
    return render(request, "profile.html", {"user": request.user})


@login_required
def delete_history(request, pk: int):
    if request.method != 'POST':
        return HttpResponseBadRequest('Only POST allowed')
    try:
        item = AnonymizationHistory.objects.get(pk=pk)
    except AnonymizationHistory.DoesNotExist:
        logger.info('delete_history: запись %s не найдена', pk)
        return JsonResponse({'ok': False, 'error': 'not found'}, status=404)

    if item.user_id != request.user.id:
        logger.warning('delete_history: пользователь %s пытается удалить чужую запись %s', request.user.id, pk)
        return JsonResponse({'ok': False, 'error': 'forbidden'}, status=403)

    item.delete()
    return JsonResponse({'ok': True})


# Обработчики ошибок

def error_400(request, exception=None):
    return render(request, '400.html', status=400)

def error_403(request, exception=None):
    return render(request, '403.html', status=403)

def error_404(request, exception=None):
    return render(request, '404.html', status=404)

def error_500(request):
    return render(request, '500.html', status=500)