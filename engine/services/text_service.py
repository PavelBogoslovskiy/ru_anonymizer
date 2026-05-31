import logging

from engine.anonymizer.anonymizer import Anonymizer
from engine.finder.predictor import NERPredictor

logger = logging.getLogger(__name__)


class ServiceError(Exception):
    """Ошибка сервиса для показа пользователю"""

    def __init__(self, user_message, internal=None):
        super().__init__(user_message)
        self.user_message = user_message
        self.internal = internal


class TextAnonymizerService:
    """
    Сервис анонимизации текстов
    """
    
    def __init__(self):
        # NER модель создаётся один раз
        try:
            self.ner = NERPredictor()
        except Exception as e:
            logger.exception("Не удалось создать NERPredictor")
            raise ServiceError("Ошибка инициализации NER модели", e)

    def _get_anonymizer(self, settings=None):
        """
        Создаёт анонимизатор с учётом настроек.
        
        settings может содержать:
            - config_yaml: YAML-строка с конфигурацией
            - config_dict: словарь с конфигурацией
            - enabled_labels: список включенных меток
        """
        config_yaml = None
        config_dict = None
        enabled_labels = None
        
        if settings:
            config_yaml = settings.get("config_yaml")
            config_dict = settings.get("config_dict")
            enabled_labels = settings.get("enabled_labels")
        
        try:
            return Anonymizer(
                config_yaml=config_yaml,
                config_dict=config_dict,
                enabled_labels=enabled_labels,
            )
        except Exception as e:
            logger.exception("Не удалось создать Anonymizer")
            raise ServiceError("Ошибка инициализации анонимайзера", e)

    def _extract_entities(self, text):
        """Извлечение сущностей"""
        try:
            entities = self.ner.predict(text)
        except Exception as e:
            logger.exception("Ошибка предсказания NER")
            raise ServiceError("Не удалось распознать сущности", e)

        if not entities:
            return []

        return entities

    def _apply_replacements(self, text, anon_result):
        """Применяет замены к тексту"""

        for item in sorted(anon_result, key=lambda x: x["start"], reverse=True):

            fake = item.get("fake")
            if not fake:
                continue

            start = item["start"]
            end = item["end"]

            if start < 0 or end > len(text) or start >= end:
                continue

            text = text[:start] + fake + text[end:]

        return text


    def anonymize_text_with_entities(self, text, settings=None):
        """
        Основной метод анонимизации текста с возвратом сущностей
        """
        if not isinstance(text, str) or not text.strip():
            return {"text": text, "original_entities": []}

        # Извлекаем сущности с позициями
        entities = self._extract_entities(text)
        if not entities:
            return {"text": text, "original_entities": []}

        # Фильтруем по включенным меткам
        enabled_labels = settings.get("enabled_labels") if settings else None
        if enabled_labels:
            entities = [e for e in entities if e["label"] in set(enabled_labels)]
        
        if not entities:
            return {"text": text, "original_entities": []}

        # Сохраняем позиции для подсветки
        original_entities = [
            {
                "label": e.get("label", "UNKNOWN"),
                "start": e["start"],
                "end": e["end"],
                "text": e.get("text", text[e["start"]:e["end"]])
            }
            for e in entities
        ]

        # Создаём анонимизатор с настройками пользователя
        anonymizer = self._get_anonymizer(settings)
        
        # Анонимизируем
        try:
            anon_result = anonymizer.anonymize(entities)
        except Exception as e:
            logger.exception("Ошибка в anonymizer")
            raise ServiceError("Ошибка анонимизации текста", e)

        if not anon_result:
            return {"text": text, "original_entities": original_entities}

        # Применяем замены
        result_text = self._apply_replacements(text, anon_result)

        return {"text": result_text, "original_entities": original_entities}