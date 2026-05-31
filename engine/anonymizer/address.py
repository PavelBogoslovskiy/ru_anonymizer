import re
import random
from engine.utils.helper import CosineRadiusClusterer, DATA_DIR


class AddressAnonymizer:
    '''
    Класс для анонимизации адресов.
    Поддерживает два режима:
    - 'part': только заменяем цифры в номерах домов, квартир и т.п.
    - 'full': заменяем весь адрес на фейковый, при этом одинаковые адреса
      получают одинаковый фейк.
    '''
    STOP_WORDS = {
        'ул', 'улица', 'д', 'дом',
        'кв', 'квартира', 'г', 'город',
        'рф', 'россия', 'обл', 'область',
        'край', 'республика', 'корп', 'корпус',
        'стр', 'строение', 'офис', 'помещение',
        'подъезд', 'эт', 'этаж', 'индекс', 'подъезд', 'прт', 
        'наб', 'проспект', 'набережная', 'аллея', 'ал', 
        'проезд', 'шоссе', 'ш', 'село', 'деревня', 'пгт', 
        'прд', 'площадь', 'строение', 'бульвар', 'переулок'
    }


    def __init__(self, mode='part', similarity_threshold=0.8):
        '''
        mode: режим работы ('part' или 'full')
        similarity_threshold: порог схожести для объединения адресов в кластеры
        '''
        self.mode = mode
        self.clusterer = CosineRadiusClusterer(similarity_threshold)

        self.mapping = {}
        self.token_pattern = re.compile(r'\b\S+\b')
        with open(DATA_DIR / 'fake_street.txt', 'r', encoding='utf-8') as f:
            self.FAKE_STREETS = [line.strip() for line in f if line.strip()]
    

    def reset_state(self):
        '''
        Полностью сбрасывает внутреннее состояние анонимизатора
        '''
        self.mapping = {}


    # PART
    def _randomize_token(self, token):
        '''
        Генерирует случайную замену для токена, содержащего цифры.
        Цифры заменяются на случайные цифры, буквы на случайные буквы.
        '''
        result = []
        for c in token:
            if c.isdigit(): result.append(random.choice('0123456789'))
            elif c.isalpha(): result.append(random.choice('abcdefghijklmnopqrstuvwxyz' if c.islower() else 'ABCDEFGHIJKLMNOPQRSTUVWXYZ'))
            else: result.append(c)
        return ''.join(result)


    def _replace(self, match):
        tok = match.group(0)
        if any(c.isdigit() for c in tok):
            if tok not in self.mapping:
                self.mapping[tok] = self._randomize_token(tok)
            return self.mapping[tok]
        return tok


    def _part_anonymize(self, addresses):
        '''
        Частичная анонимизация: заменяем только номера домов, квартир и т.д.
        '''
        return [self.token_pattern.sub(self._replace, addr) for addr in addresses]


    # FULL
    def _normalize(self, addr):
        '''
        Нормализует адрес для объединения похожих вариантов:
        - переводим в нижний регистр
        - убираем пунктуацию
        - удаляем стоп-слова
        - сортируем токены
        '''
        addr = addr.lower()
        addr = re.sub(r'[^\w\s]', ' ', addr)
        tokens = [t for t in addr.split() if t not in self.STOP_WORDS and len(t) > 1]
        tokens = sorted(tokens)
        return ' '.join(tokens)


    def _generate_fake(self):
        '''
        Генерирует фейковый адрес с улицей, домом и квартирой.
        Улицы берутся из файла с фейковыми улицами.
        '''
        street = random.choice(self.FAKE_STREETS)
        house = random.randint(1, 200)
        letter = random.choice(['а', 'б', 'в', 'г', 'д', 'е', 'ж', 'з'])
        flat = random.randint(1, 1000)
        return f'ул. {street}, д. {house}{letter}, кв. {flat}'


    def _full_anonymize(self, addresses):
        """
        Полная анонимизация:
        - нормализуем и дедублицируем адреса
        - кластеризуем нормализованные формы
        - генерируем один фейк на кластер
        - возвращаем original -> fake
        """

        if not addresses:
            return {}

        # Нормализация + дедупликация
        norm_to_originals = {}
        for addr in addresses:
            norm = self._normalize(addr)
            norm_to_originals.setdefault(norm, []).append(addr)

        unique_norms = list(norm_to_originals.keys())

        # Кластеризация
        clusters_idx = self.clusterer.cluster(unique_norms)
        result = {}

        for cluster in clusters_idx:
            fake = self._generate_fake()

            for idx in cluster:
                norm = unique_norms[idx]
                originals = norm_to_originals[norm]

                for orig in originals:
                    result[orig] = fake

        return result


    def anonymize(self, input):
        '''
        Основной метод анонимизации.
        Возвращает словарь оригинал -> фейк.
        Выбирает режим в зависимости от self.mode ('part' или 'full').
        '''
        if self.mode == 'part':
            part_result = self._part_anonymize(input)
            return dict(zip(input, part_result))
        elif self.mode == 'full':
            return self._full_anonymize(input)