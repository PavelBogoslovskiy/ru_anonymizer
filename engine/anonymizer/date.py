import re
import random
from datetime import datetime, timedelta
from dateutil import parser
from engine.utils.helper import match_case_and_gender


class DateAnonymizer:
    '''
    Анонимизатор дат
    '''

    MONTHS_RU = {
        1: 'январь', 2: 'февраль', 3: 'март', 4: 'апрель',
        5: 'май', 6: 'июнь', 7: 'июль', 8: 'август',
        9: 'сентябрь', 10: 'октябрь', 11: 'ноябрь', 12: 'декабрь'
    }

    MONTH_PATTERN = re.compile(
        r'\b(' + '|'.join(MONTHS_RU.values()) + r')\w*\b',
        flags=re.IGNORECASE
    )

    RANGE_PATTERN = re.compile(
        r'(\d{1,2}[./-]?\d{0,2}[./-]?\d{2,4}'
        r'|[а-яА-Я]+ \d{4})'
    )

    def anonymize(self, input):
        result = {}
        offset_days = random.choice([
            random.randint(-1000, -50),
            random.randint(50, 1000)
        ])

        mapping = {}

        for original in input:

            fake = original

            # обработка дат
            segments = self.RANGE_PATTERN.findall(original)

            for seg in segments:
                key = seg.strip()

                if key not in mapping:
                    dt = self._parse_single_date(key)

                    if dt:
                        shifted = dt + timedelta(days=offset_days)
                        mapping[key] = self._format_same_style(key, shifted)
                    else:
                        mapping[key] = key

                fake = re.sub(
                    re.escape(key),
                    mapping[key],
                    fake,
                    count=1
                )

            # обработка одиночного месяца
            month_matches = list(self.MONTH_PATTERN.finditer(fake))

            for match in month_matches:
                month_word = match.group(0)

                if month_word not in mapping:
                    shifted_month = self._shift_month_only(
                        month_word,
                        offset_days
                    )
                    mapping[month_word] = shifted_month

                fake = fake.replace(month_word, mapping[month_word], 1)

            result[original] = fake

        return result


    def _parse_single_date(self, text):
        try:
            return parser.parse(text, dayfirst=True, fuzzy=True)
        except Exception:
            return None


    def _format_same_style(self, original, dt):

        original_clean = original.strip()

        # год
        if re.fullmatch(r'\d{4}', original_clean):
            return dt.strftime('%Y')

        if re.fullmatch(r'\d{2}', original_clean):
            return dt.strftime('%y')

        # месяц + год (без дня)
        if re.fullmatch(r'[а-яА-Я]+\s+\d{4}', original_clean):
            month_name = self.MONTHS_RU[dt.month]
            base = f"{month_name} {dt.year}"
            return match_case_and_gender(original, base)

        # день + месяц + год
        if re.search(r'\d{1,2}.*[а-яА-Я]+.*\d{4}', original_clean):
            month_name = self.MONTHS_RU[dt.month]
            base = f"{dt.day} {month_name} {dt.year}"
            return match_case_and_gender(original, base)

        # текстовая дата без года
        if re.search(r'[а-яА-Я]+', original_clean):
            month_name = self.MONTHS_RU[dt.month]
            base = f"{dt.day} {month_name} {dt.year}"
            return match_case_and_gender(original, base)

        # числовые даты
        sep = '.'
        if '-' in original:
            sep = '-'
        elif '/' in original:
            sep = '/'

        year_match = re.search(r'(\d+)$', original_clean)

        if year_match and len(year_match.group(1)) == 2:
            year_format = '%y'
        else:
            year_format = '%Y'

        return f"{dt.day:02d}{sep}{dt.month:02d}{sep}{dt.strftime(year_format)}"


    def _shift_month_only(self, original, offset_days):
        """
        Сдвигает только месяц в дате, оставляя день и год без изменений
        """
        lower = original.lower()

        month_num = None
        for k, v in self.MONTHS_RU.items():
            if lower.startswith(v):
                month_num = k
                break

        if not month_num:
            return original

        base_dt = datetime(year=2000, month=month_num, day=1)
        shifted = base_dt + timedelta(days=offset_days)

        new_month_base = self.MONTHS_RU[shifted.month]

        # сохраняем падеж
        return match_case_and_gender(original, new_month_base)