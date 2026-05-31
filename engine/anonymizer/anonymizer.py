import yaml
from pathlib import Path
from collections import defaultdict

from .person import PersonAnonymizer
from .organization import OrganizationAnonymizer
from .address import AddressAnonymizer
from .docid import DocIdAnonymizer
from .money import MoneyAnonymizer
from .phone import PhoneAnonymizer
from .date import DateAnonymizer
from .email import EmailAnonymizer
from .location import LocationAnonymizer

AVAILABLE_LABELS = [
    "PERSON",
    "ORG",
    "ADDRESS",
    "DOC_ID",
    "MONEY",
    "PHONE",
    "DATE",
    "EMAIL",
    "LOC"
]

ANONYMIZER_REGISTRY = {
    "PERSON": PersonAnonymizer,
    "ORG": OrganizationAnonymizer,
    "ADDRESS": AddressAnonymizer,
    "DOC_ID": DocIdAnonymizer,
    "MONEY": MoneyAnonymizer,
    "PHONE": PhoneAnonymizer,
    "DATE": DateAnonymizer,
    "EMAIL": EmailAnonymizer,
    "LOC": LocationAnonymizer
}


class Anonymizer:
    """
    Главный анонимизатор.
    
    Конфигурация загружается в порядке приоритета:
    1. config_yaml/config_dict — пользовательский конфиг
    2. data/anonymizer_config.yaml — конфиг по умолчанию
    """

    DEFAULT_CONFIG_PATH = Path(__file__).parent.parent / "data" / "anonymizer_config.yaml"

    def __init__(self, config_yaml=None, config_dict=None, enabled_labels=None):
        """
        Инициализация анонимизатора.
        
        Args:
            config_yaml: YAML-строка с конфигурацией
            config_dict: Словарь с конфигурацией (приоритет выше config_yaml)
            enabled_labels: Список включенных меток (переопределяет enabled в конфиге)
        """
        self.enabled_labels = set()
        self.anonymizers = {}
        self._load_config(config_yaml, config_dict, enabled_labels)

    def _load_config(self, config_yaml, config_dict, enabled_labels):
        """Загрузка конфигурации из различных источников"""
        
        # Загружаем базовый конфиг
        if self.DEFAULT_CONFIG_PATH.exists():
            with open(self.DEFAULT_CONFIG_PATH, "r", encoding="utf-8") as f:
                base_cfg = yaml.safe_load(f) or {}
        else:
            base_cfg = {"anonymizers": {}}
        
        # Пользовательский конфиг (переопределяет базовый)
        user_cfg = {}
        if config_dict:
            user_cfg = config_dict
        elif config_yaml:
            try:
                user_cfg = yaml.safe_load(config_yaml) or {}
            except yaml.YAMLError:
                user_cfg = {}
        
        # Мержим конфиги: user_cfg переопределяет base_cfg
        merged_anonymizers = base_cfg.get("anonymizers", {}).copy()
        for label, params in user_cfg.get("anonymizers", {}).items():
            if label in merged_anonymizers:
                merged_anonymizers[label].update(params)
            else:
                merged_anonymizers[label] = params
        
        # Если передан enabled_labels — используем его для фильтрации
        filter_labels = set(enabled_labels) if enabled_labels else None
        
        for label, params in merged_anonymizers.items():
            # Проверяем enabled в конфиге
            if not params.get("enabled", True):
                continue
            
            # Проверяем фильтр по меткам
            if filter_labels is not None and label not in filter_labels:
                continue
            
            if label not in ANONYMIZER_REGISTRY:
                continue

            anonymizer_cls = ANONYMIZER_REGISTRY[label]

            # Убираем служебный ключ enabled перед передачей в конструктор
            init_params = {k: v for k, v in params.items() if k != "enabled"}

            self.anonymizers[label] = anonymizer_cls(**init_params)
            self.enabled_labels.add(label)

    def anonymize(self, entities):
        """
        Принимает список сущностей:
        [
            {'label': str, 'start': int, 'end': int, 'text': str}
        ]
        Возвращает:
        [
            {'label': str, 'start': int, 'end': int, 'text': str, 'fake': str}
        ]
        """
        if not entities:
            return []

        # Группируем сущности по label
        grouped_entities = defaultdict(list)
        for ent in entities:
            label = ent["label"]
            if label in self.enabled_labels:
                grouped_entities[label].append(ent)

        # Результирующий маппинг: original -> fake
        fake_mappings = {}

        for label, ents in grouped_entities.items():
            texts = [e["text"] for e in ents]
            unique_texts = list(dict.fromkeys(texts))  # дедупликация

            anonymizer = self.anonymizers.get(label)
            if not anonymizer:
                continue

            mapping = anonymizer.anonymize(unique_texts)
            if not mapping:
                continue

            fake_mappings.update(mapping)

        result = []
        for ent in entities:
            original = ent["text"]
            fake = fake_mappings.get(original)
            result.append(
                {
                    "label": ent["label"],
                    "start": ent["start"],
                    "end": ent["end"],
                    "text": original,
                    "fake": fake,
                }
            )

        result.sort(key=lambda x: x["start"])
        return result