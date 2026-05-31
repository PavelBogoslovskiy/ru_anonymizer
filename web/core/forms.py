from django import forms
from django.contrib.auth import get_user_model
from django.contrib.auth.forms import UserCreationForm

User = get_user_model()

# Основные метки сущностей
LABEL_CHOICES = [
    ("PERSON", "Персона"),
    ("ORG", "Организация"),
    ("ADDRESS", "Адрес"),
    ("DOC_ID", "Документ"),
    ("MONEY", "Деньги"),
    ("PHONE", "Телефон"),
    ("DATE", "Дата"),
    ("EMAIL", "Email"),
    ("LOC", "Локация"),
]

# Режимы для ADDRESS
ADDRESS_MODE_CHOICES = [
    ("full", "Полная замена"),
    ("part", "Частичная (только номера)"),
]

# Режимы для EMAIL
EMAIL_MODE_CHOICES = [
    ("preserve_domain", "Сохранить домен"),
    ("randomize_domain", "Полная замена"),
]


class RegisterForm(UserCreationForm):
    email = forms.EmailField(required=True, label="Email")

    class Meta:
        model = User
        fields = ("username", "email", "password1", "password2")


class SettingsForm(forms.Form):
    """
    Настройки анонимизации: метки + дополнительные параметры для ADDRESS и EMAIL.
    """
    enabled_labels = forms.MultipleChoiceField(
        choices=LABEL_CHOICES,
        required=False,
        widget=forms.CheckboxSelectMultiple(attrs={"class": "form-check-input"}),
        label="Сущности для анонимизации"
    )
    
    # Дополнительные настройки для ADDRESS
    address_mode = forms.ChoiceField(
        choices=ADDRESS_MODE_CHOICES,
        required=False,
        initial="full",
        widget=forms.RadioSelect(attrs={"class": "form-check-input"}),
        label="Режим анонимизации адресов"
    )
    
    # Дополнительные настройки для EMAIL
    email_mode = forms.ChoiceField(
        choices=EMAIL_MODE_CHOICES,
        required=False,
        initial="preserve_domain",
        widget=forms.RadioSelect(attrs={"class": "form-check-input"}),
        label="Режим анонимизации email"
    )