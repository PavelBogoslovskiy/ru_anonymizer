from django.db import models
from django.conf import settings
from django.contrib.auth import get_user_model
import json

User = get_user_model()


class Profile(models.Model):
    """
    Профиль пользователя с настройками анонимизации.
    
    Поля:
        config_yaml: YAML-конфигурация анонимизаторов (переопределяет anonymizer_config.yaml)
        enabled_labels: JSON-список включенных типов сущностей (фильтр)
    """
    user = models.OneToOneField(User, on_delete=models.CASCADE, related_name="profile")
    config_yaml = models.TextField(blank=True, default="", help_text="YAML конфигурация анонимизаторов")
    enabled_labels = models.TextField(blank=True, default="[]", help_text="JSON-список включенных меток")

    def set_enabled_labels(self, labels):
        """Сохраняет список меток в JSON"""
        try:
            self.enabled_labels = json.dumps(list(labels or []))
        except Exception:
            self.enabled_labels = "[]"

    def get_enabled_labels(self):
        """Возвращает список меток из JSON"""
        try:
            return json.loads(self.enabled_labels) if self.enabled_labels else []
        except Exception:
            return []

    def __str__(self):
        return f"Profile({self.user.username})"


class AnonymizationHistory(models.Model):
    """
    История анонимизаций пользователя.
    
    Хранит оригинальный текст, результат и найденные сущности для подсветки.
    """
    user = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name="anonymizations")
    title = models.CharField(max_length=255, blank=True)
    original = models.TextField()
    result = models.TextField()
    entities = models.TextField(blank=True, default="[]")  # JSON-строка с данными сущностей
    created_at = models.DateTimeField(auto_now_add=True)

    def set_entities(self, entities_list):
        """Сохраняет сущности в JSON"""
        try:
            self.entities = json.dumps(entities_list or [], ensure_ascii=False)
        except Exception:
            self.entities = "[]"

    def get_entities(self):
        """Возвращает сущности из JSON"""
        try:
            return json.loads(self.entities) if self.entities else []
        except Exception:
            return []

    class Meta:
        ordering = ["-created_at"]
        verbose_name = "История анонимизации"
        verbose_name_plural = "История анонимизаций"