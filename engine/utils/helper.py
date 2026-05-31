# engine/utils/helper.py
import yaml
import random
import re
import pymorphy3
from sklearn.neighbors import NearestNeighbors
from sklearn.feature_extraction.text import TfidfVectorizer
import json
from pathlib import Path

morph = pymorphy3.MorphAnalyzer()

# Базовая директория data
DATA_DIR = Path(__file__).parent.parent / "data"


class PromptManager:
    """
    Управляет загрузкой и форматированием промптов из YAML
    """
    def __init__(self, path=None):
        if path is None:
            path = DATA_DIR / "prompts.yaml"
        with open(path, "r", encoding="utf-8") as f:
            self.prompts = yaml.safe_load(f)

    def get(self, key, **kwargs):
        """
        Возвращает отформатированный промпт по ключу
        """
        template = self.prompts[key]["template"]
        return template.format(**kwargs)


def random_except(lst, banned, drop_l=[]):
    """
    Возвращает случайный элемент из lst,
    исключая banned и элементы из drop_l
    """
    choices = [x for x in lst if x != banned and x not in drop_l]

    if not choices:
        print("Список доступных фейков пуст")
        return 'Fake'

    return random.choice(choices)


def extract_json_array(text):
    """
    Извлекает первый валидный JSON-массив из произвольного текста.
    Возвращает строку массива или None
    """
    start = text.find('[')
    if start == -1:
        return None

    bracket_count = 0
    in_string = False
    escape = False

    for i in range(start, len(text)):
        char = text[i]

        # обработка строк внутри JSON
        if char == '"' and not escape:
            in_string = not in_string

        if char == '\\' and not escape:
            escape = True
            continue
        else:
            escape = False

        if not in_string:
            if char == '[':
                bracket_count += 1
            elif char == ']':
                bracket_count -= 1
                if bracket_count == 0:
                    candidate = text[start:i + 1]
                    try:
                        json.loads(candidate)
                        return candidate
                    except json.JSONDecodeError:
                        return None
    return None


def extract_json_object(text):
    """
    Извлекает первый валидный JSON-объект из произвольного текста.
    Возвращает строку объекта или None
    """
    start = text.find('{')
    if start == -1:
        return None

    brace_count = 0
    in_string = False
    escape = False

    for i in range(start, len(text)):
        char = text[i]

        # обработка строк внутри JSON
        if char == '"' and not escape:
            in_string = not in_string

        if char == '\\' and not escape:
            escape = True
            continue
        else:
            escape = False

        if not in_string:
            if char == '{':
                brace_count += 1
            elif char == '}':
                brace_count -= 1
                if brace_count == 0:
                    candidate = text[start:i + 1]
                    try:
                        json.loads(candidate)
                        return candidate
                    except json.JSONDecodeError:
                        return None
    return None


def change_case(word, target_case):
    """
    Склоняет слово в указанный падеж.
    target_case: 'nomn', 'gent', 'datv', 'accs', 'ablt', 'loct'
    """
    words = word.split()
    result = []

    for w in words:
        parse = morph.parse(w)[0]
        inflected = parse.inflect({target_case})
        result.append(inflected.word if inflected else w)

    return " ".join(result)


def match_case_and_gender(original, fake, sex=None):
    """
    Склоняет fake в падеж, соответствующий оригиналу.
    Также учитывает род
    """

    if not original or not fake:
        return fake

    # Определяем наиболее частый падеж оригинала
    cases = {}
    for word in original.split():
        parsed = morph.parse(word)
        if parsed and parsed[0].tag.case:
            case = parsed[0].tag.case
            cases[case] = cases.get(case, 0) + 1

    target_case = max(cases, key=cases.get) if cases else "nomn"

    # Определяем род
    target_gender = None
    if sex is not None:
        target_gender = {0: "femn", 1: "masc"}.get(sex)

    # Склоняем каждое слово fake
    result = []
    for word in fake.split():

        # Инициалы не склоняем
        if re.fullmatch(r"[А-ЯA-Z]\.", word):
            result.append(word)
            continue

        parsed_fake = morph.parse(word)
        if not parsed_fake:
            result.append(word)
            continue

        tags = {target_case}
        if target_gender:
            tags.add(target_gender)

        inflected = parsed_fake[0].inflect(tags)
        result.append(inflected.word if inflected else word)

    return " ".join(result).title()


class CosineRadiusClusterer:

    def __init__(self, similarity_threshold):
        self.vectorizer = vectorizer = TfidfVectorizer(
            analyzer="char_wb",
            ngram_range=(3, 5)
        )
        self.similarity_threshold = similarity_threshold

    def cluster(self, texts):
        """
        Принимает список строк.
        Возвращает список кластеров в виде списков индексов
        """

        if not texts:
            return []

        if len(texts) == 1:
            return [[0]]

        vectors = self.vectorizer.fit_transform(texts)

        nn = NearestNeighbors(
            metric="cosine",
            radius=1 - self.similarity_threshold
        )
        nn.fit(vectors)

        _, indices = nn.radius_neighbors(vectors)

        visited = set()
        clusters = []

        for i, neighbors in enumerate(indices):
            if i in visited:
                continue

            stack = list(neighbors)
            cluster = []

            while stack:
                idx = stack.pop()
                if idx in visited:
                    continue
                visited.add(idx)
                cluster.append(idx)

                _, neigh = nn.radius_neighbors(vectors[idx])
                stack.extend(neigh[0])

            clusters.append(cluster)

        return clusters