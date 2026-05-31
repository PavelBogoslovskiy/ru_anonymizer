import re
import random
import math


class MoneyAnonymizer:
    '''
    Анонимайзер денежных сумм.

    Поддерживает:
    - числовую форму
    - словесную форму
    - смешанную форму (число + слова в скобках)
    - сокращения (млн, млрд)
    - валюты
    - корректную морфологию
    - сохранение порядка величины
    - согласованность частей
    '''

    UNITS = {
        0: 'ноль',
        1: 'один',
        2: 'два',
        3: 'три',
        4: 'четыре',
        5: 'пять',
        6: 'шесть',
        7: 'семь',
        8: 'восемь',
        9: 'девять',
        10: 'десять',
        11: 'одиннадцать',
        12: 'двенадцать',
        13: 'тринадцать',
        14: 'четырнадцать',
        15: 'пятнадцать',
        16: 'шестнадцать',
        17: 'семнадцать',
        18: 'восемнадцать',
        19: 'девятнадцать'
    }

    TENS = {
        20: 'двадцать',
        30: 'тридцать',
        40: 'сорок',
        50: 'пятьдесят',
        60: 'шестьдесят',
        70: 'семьдесят',
        80: 'восемьдесят',
        90: 'девяносто'
    }

    HUNDREDS = {
        100: 'сто',
        200: 'двести',
        300: 'триста',
        400: 'четыреста',
        500: 'пятьсот',
        600: 'шестьсот',
        700: 'семьсот',
        800: 'восемьсот',
        900: 'девятьсот'
    }

    CURRENCY_PATTERN = r'(₽|руб\.?|рублей|рубля|рубль|доллар(?:ов|а)?|USD|\$|EUR|€)'

    def _extract_currency(self, text):
        match = re.search(self.CURRENCY_PATTERN, text, re.IGNORECASE)
        return match.group(0) if match else ''


    def _split_parentheses(self, text):
        '''
        Разделяет:
        "1 200 000 руб (один миллион)"
        '''
        match = re.match(r'^(.*?)\s*\((.*?)\)\s*$', text)
        if match:
            return match.group(1).strip(), match.group(2).strip()
        return text, None


    def _parse_numeric(self, text):

        num_match = re.search(r'\d+(?:[\s.,]\d+)*', text)
        if not num_match:
            return None

        raw = num_match.group(0)
        clean = raw.replace(' ', '').replace(',', '.')
        value = float(clean)

        if 'млрд' in text.lower():
            value *= 1_000_000_000
        elif 'млн' in text.lower():
            value *= 1_000_000
        elif 'тыс' in text.lower():
            value *= 1_000

        return int(value)


    def _words_to_number(self, text):

        text = text.lower()

        total = 0
        current = 0

        word_map = {v: k for k, v in self.UNITS.items()}
        word_map.update({v: k for k, v in self.TENS.items()})
        word_map.update({v: k for k, v in self.HUNDREDS.items()})

        tokens = re.findall(r'[а-яё]+', text)

        for token in tokens:

            if token in word_map:
                current += word_map[token]

            elif token.startswith('тысяч'):
                total += current * 1_000
                current = 0

            elif token.startswith('миллион'):
                total += current * 1_000_000
                current = 0

            elif token.startswith('миллиард'):
                total += current * 1_000_000_000
                current = 0

        total += current
        return total if total > 0 else None

    def _parse_amount(self, text):

        numeric = self._parse_numeric(text)
        if numeric is not None:
            return numeric

        words = self._words_to_number(text)
        return words

    def _generate_same_order(self, value):

        order = int(math.log10(value))
        lower = 10 ** order
        upper = 10 ** (order + 1) - 1

        while True:
            new_value = random.randint(lower, upper)
            if new_value != value:
                return new_value

    def _plural_form(self, number, forms):
        '''
        Правильная форма слова:
        ('рубль', 'рубля', 'рублей')
        '''
        n = abs(number) % 100
        if 11 <= n <= 19:
            return forms[2]
        n = n % 10
        if n == 1:
            return forms[0]
        if 2 <= n <= 4:
            return forms[1]
        return forms[2]


    def _number_to_words(self, number):

        def convert_hundreds(n):
            words = []
            if n >= 100:
                words.append(self.HUNDREDS[(n // 100) * 100])
                n %= 100
            if 20 <= n:
                words.append(self.TENS[(n // 10) * 10])
                n %= 10
            if 0 < n < 20:
                words.append(self.UNITS[n])
            return words

        parts = []

        billions = number // 1_000_000_000
        millions = (number // 1_000_000) % 1_000
        thousands = (number // 1_000) % 1_000
        remainder = number % 1_000

        if billions:
            parts += convert_hundreds(billions)
            parts.append(self._plural_form(billions, ('миллиард', 'миллиарда', 'миллиардов')))

        if millions:
            parts += convert_hundreds(millions)
            parts.append(self._plural_form(millions, ('миллион', 'миллиона', 'миллионов')))

        if thousands:
            parts += convert_hundreds(thousands)
            parts.append(self._plural_form(thousands, ('тысяча', 'тысячи', 'тысяч')))

        if remainder:
            parts += convert_hundreds(remainder)

        return ' '.join(parts)


    def anonymize(self, input):
        '''
        Основная функция анонимизатора
        Одинаковые суммы → одинаковые fake в рамках одного вызова.
        '''

        result = {}

        # локальный mapping для одного батча
        value_mapping = {}

        for original in input:

            main_part, words_part = self._split_parentheses(original)
            currency = self._extract_currency(original)

            value = self._parse_amount(main_part)

            if value is None and words_part:
                value = self._parse_amount(words_part)

            if value is None:
                result[original] = original
                continue

            if value not in value_mapping:
                value_mapping[value] = self._generate_same_order(value)

            new_value = value_mapping[value]

            numeric_form = f"{new_value:,}".replace(',', ' ')
            words_form = self._number_to_words(new_value)

            if words_part is not None:
                fake = f"{numeric_form} {currency} ({words_form})".strip()

            elif re.search(r'\d', original):
                fake = f"{numeric_form} {currency}".strip()

            else:
                fake = f"{words_form} {currency}".strip()

            result[original] = fake

        return result