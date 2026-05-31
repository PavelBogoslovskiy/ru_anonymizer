import re
import json
import random
import pymorphy3
from engine.utils.helper import CosineRadiusClusterer, DATA_DIR, match_case_and_gender


class LocationAnonymizer:
    """
    Класс для анонимизации локаций (регионов, городов, деревень и т.д.).
    Страны не анонимизируются
    """

    REGION_STOP = {
        'область', 'обл', 'край', 'республика', 'респ', 
        'автономный округ', 'ао', 'округ'
    }

    CITY_STOP = {'г', 'город'}
    VILLAGE_STOP = {'село', 'деревня', 'поселок', 'посёлок', 'пгт', 'хутор', 'поселение'}

    ALL_STOP = REGION_STOP | CITY_STOP | VILLAGE_STOP

    def __init__(self, similarity_threshold=0.8):
        """
        similarity_threshold — порог косинусной схожести
        для объединения локаций в один кластер
        """

        with open(DATA_DIR / 'region_data.json', 'r', encoding='utf-8') as f:
            self.regions = json.load(f)

        with open(DATA_DIR / 'countries.json', 'r', encoding='utf-8') as f:
            self.countries = set(json.load(f))

        self.clusterer = CosineRadiusClusterer(similarity_threshold)

        self.morph = pymorphy3.MorphAnalyzer()

        # чтобы фейки не повторялись между кластерами
        self.used_fakes = set()

    def reset_state(self):
        '''
        Полностью сбрасывает внутреннее состояние анонимизатора
        '''
        self.used_fakes = set()

    def is_country(self, text):
        """
        Проверяет, является ли текст названием страны
        """
        normalized = re.sub(r'[^\w\s]', ' ', text.lower())
        normalized = ' '.join(normalized.split())
        
        return normalized in self.countries

    def anonymize(self, input):
        """
        Основной метод.
        Принимает список локаций.
        Возвращает словарь original -> fake.
        Страны НЕ анонимизируются — возвращаются как есть.
        """

        if not input:
            return {}

        self.reset_state()
        
        result = {}
        locations_to_process = []
        
        # Разделяем страны и локации для анонимизации
        for loc in input:
            if self.is_country(loc):
                result[loc] = loc
            else:
                locations_to_process.append(loc)

        # Если нет локаций для анонимизации, возвращаем результат
        if not locations_to_process:
            return result

        # Дедупликация локаций для обработки
        unique_locations = list(set(locations_to_process))

        # Очистка + извлечение стоп-слов
        norm_data = []
        for loc in unique_locations:
            cleaned, stops = self._extract_stop_words(loc)
            norm_data.append((loc, cleaned, stops))

        cleaned_texts = [x[1] for x in norm_data]

        if not cleaned_texts:
            return result

        # Кластеризация
        clusters_idx = self.clusterer.cluster(cleaned_texts)

        # Подготовка кластеров и токенов
        clusters = {}
        clusters_tokens = {}

        for cid, cluster in enumerate(clusters_idx):
            for idx in cluster:
                clusters.setdefault(cid, []).append(norm_data[idx])

                tokens = set(
                    re.sub(r'[^\w\s]', ' ', norm_data[idx][0].lower()).split()
                )
                clusters_tokens.setdefault(cid, set()).update(tokens)

        # Генерация фейков для локаций
        for cid in clusters:

            fake_region, fake_city, fake_village = \
                self._generate_cluster_fake(clusters_tokens[cid])

            for original, _, stops in clusters[cid]:

                parts = []

                if self.REGION_STOP & stops:
                    parts.append(match_case_and_gender(original, fake_region))

                if self.CITY_STOP & stops:
                    parts.append(match_case_and_gender(original, fake_city))

                if self.VILLAGE_STOP & stops:
                    parts.append(match_case_and_gender(original, fake_village))

                if not parts:
                    parts.append(match_case_and_gender(original, fake_city))

                result[original] = ', '.join(parts)

        return result

    def _extract_stop_words(self, text):
        """
        Убирает стоп-слова (типы локаций).
        Возвращает:
        - очищенную строку для кластеризации
        - найденные стоп-слова
        """

        lower = text.lower()
        stops_found = set()

        for stop in self.ALL_STOP:
            if stop in lower:
                stops_found.add(stop)

        cleaned = re.sub(r'[^\w\s]', ' ', lower)

        tokens = [
            self.morph.parse(t)[0].normal_form
            for t in cleaned.split()
            if t not in self.ALL_STOP
        ]

        return ' '.join(sorted(tokens)), stops_found


    def _generate_cluster_fake(self, cluster_tokens):
        """
        Генерирует фейковый регион, город и деревню для кластера.

        Условия:
        - не должны встречаться в cluster_tokens
        - не должны быть использованы ранее
        """

        # фильтрация регионов без цикла
        valid_regions = [
            r for r in self.regions
            if (
                r['name'].lower() not in cluster_tokens
                and r['full_name'] not in self.used_fakes
            )
        ]

        if not valid_regions:
            print("Нет доступных регионов для генерации фейка. Выбран случайный регион")
            fake = random.choice(self.regions)
        else:
            fake = random.choice(valid_regions)

        fake_region = fake['full_name']
        fake_city = random.choice(fake['city'])
        fake_village = random.choice(fake['village'])

        if cluster_tokens & {
                fake['name'].lower(),
                fake_city.lower(),
                fake_village.lower()
            }:
            return self._generate_cluster_fake(cluster_tokens)

        # запоминаем чтобы не использовать повторно
        self.used_fakes.add(fake_region)

        return fake_region, fake_city, fake_village