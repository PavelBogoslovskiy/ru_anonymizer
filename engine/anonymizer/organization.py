from engine.utils.llmodel import LLM
import re
from engine.utils.helper import PromptManager, CosineRadiusClusterer, match_case_and_gender


class OrganizationAnonymizer:
    '''
    Класс анонимизации организаций
    '''

    STATE_KEYWORDS = {
        "министерство", "федераль", "служб", "агентство",
        "департамент", "комитет", "управлен",
        "администрац", "правительств",
        "суд", "прокуратур",
        "гбу", "фгбу", "муниципаль",
        "государствен", "поликлиник", "больниц", "полиц"
    }


    def __init__(self, provider='ollama', model='qwen3:8b', similarity_threshold=0.75, batch_size=20):
        '''
        model: название модели
        similarity_threshold: порог косинусной близости
        batch_size: размер патча для отправки в LLM
        '''

        self.client = LLM(provider=provider, model=model)
        self.batch_size = batch_size

        self.clusterer = CosineRadiusClusterer(similarity_threshold)

        self.mapping = {}
        self.used_fakes = set()
        self.counter = 1

        self.pm = PromptManager()


    def reset_state(self):
        '''
        Полностью сбрасывает внутреннее состояние анонимизатора
        '''

        self.mapping = {}
        self.used_fakes = set()
        self.counter = 1


    def _normalize(self, text):
        '''
        Нормализует название организации:
        - lowercase
        - удаление кавычек
        - удаление пунктуации
        - удаление юр. форм
        '''
        text = text.lower()
        text = re.sub(r'[«»"]', ' ', text)
        text = re.sub(r'[^\w\s]', ' ', text)
        text = re.sub(
            r'\b(ооо|ао|пао|ип|гбу|фгбу|муниципальное|акционерное)\b',
            ' ',
            text
        )
        text = re.sub(r'\s+', ' ', text).strip()
        return text


    def _cluster(self, orgs):
        '''
        Кластеризация организаций по косинусной близости
        '''

        norm_to_originals = {}

        for org in orgs:
            norm = self._normalize(org)
            norm_to_originals.setdefault(norm, []).append(org)

        unique_norms = list(norm_to_originals.keys())

        if not unique_norms:
            return []

        clusters_idx = self.clusterer.cluster(unique_norms)

        result = []

        for cluster in clusters_idx:
            group = []
            for idx in cluster:
                group.extend(norm_to_originals[unique_norms[idx]])
            result.append(group)

        return result


    def _select_canonical(self, cluster):
        '''
        Самый длинный вариант строки
        '''
        return max(cluster, key=len)


    def _chunk_list(self, lst):
        '''
        Делит список на батчи фиксированного размера
        '''
        for i in range(0, len(lst), self.batch_size):
            yield lst[i:i + self.batch_size]


    def _call_model(self, canonicals_patch):
        '''
        Отправляет батч в LLM
        Ожидает JSON формата:
        {
            "original_name": "fake_name"
        }
        '''

        if not canonicals_patch:
            return {}

        prompt = self.pm.get(
            'organization_direct_replacement',
            names=f'{canonicals_patch}'.replace("'", '"')
        )

        return self.client.generate(
            prompt=prompt,
            temperature=0.25,
            output_format='json_object'
        )


    def _is_state(self, text):
        '''
        Определяет, является ли организация государственной
        '''
        t = text.lower()
        return any(kw in t for kw in self.STATE_KEYWORDS)


    def _generate_fallback(self, original):
        '''
        Генерирует fallback-имя
        '''
        base = (
            "Государственная организация"
            if self._is_state(original)
            else "Компания"
        )
        return f"{base} {self.counter}"


    def _fallback(self, original):
        '''
        Fallback используется если:
        - LLM не вернул ответ
        - fake не прошёл валидацию
        '''

        while True:
            fake = self._generate_fallback(original)
            self.counter += 1

            if self._is_valid(original, fake):
                self.used_fakes.add(fake)
                self.mapping[original] = fake
                return fake


    def _is_valid(self, original, fake):
        '''
        Проверяет корректность fake:

        - не пустой
        - не совпадает с original
        - не совпадает в нормализованном виде
        - не использован ранее
        - не содержит original как подстроку
        '''

        if not isinstance(fake, str):
            return False

        fake = fake.strip()
        if not fake:
            return False

        if fake == original:
            return False

        if self._normalize(fake) == self._normalize(original):
            return False

        if fake in self.used_fakes:
            return False

        if self._normalize(original) in self._normalize(fake):
            return False

        return True


    def anonymize(self, input):

        if not input:
            return {}
        
        self.reset_state()

        clusters = self._cluster(input)

        canonical_to_cluster = {}
        canonicals_to_generate = []

        # собираем canonical
        for cluster in clusters:
            canonical = self._select_canonical(cluster)
            canonical_to_cluster[canonical] = cluster

            if canonical not in self.mapping:
                canonicals_to_generate.append(canonical)

        # отправка в LLM батчами
        llm_generated = {}

        for patch in self._chunk_list(canonicals_to_generate):
            batch_result = self._call_model(patch)
            llm_generated.update(batch_result)

        result = {}

        # обработка canonical
        for canonical, cluster in canonical_to_cluster.items():

            if canonical in self.mapping:
                fake = self.mapping[canonical]
            else:
                candidate = llm_generated.get(canonical)

                if self._is_valid(canonical, candidate):
                    fake = candidate.strip()
                    self.used_fakes.add(fake)
                    self.mapping[canonical] = fake
                else:
                    fake = self._fallback(canonical)

            # распространение на весь кластер с согласованием падежа
            for org in cluster:
                adjusted_fake = match_case_and_gender(org, fake)
                # adjusted_fake = fake
                self.mapping[org] = adjusted_fake
                result[org] = adjusted_fake

        return result