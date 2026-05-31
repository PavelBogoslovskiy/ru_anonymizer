from dataclasses import dataclass
from engine.utils.llmodel import LLM
import json
import random
import re
from pathlib import Path

from engine.utils.helper import (
    PromptManager,
    random_except,
    match_case_and_gender,
    DATA_DIR
)


@dataclass
class FakePerson:
    '''
    Структура хранения сгенерированных фейковых данных для одного человека.
    '''
    sex: int
    name: str = None
    surname: str = None
    patronymic: str = None
    name_initial: str = None
    surname_initial: str = None
    patronymic_initial: str = None
    nickname: str = None



class PersonAnonymizer:
    '''
    Основной класс анонимизации персон.
    1. Получает разметку от LLM.
    2. Генерирует согласованные фейковые данные.
    3. Возвращает отображение original → fake.
    '''

    def __init__(self, provider='ollama', model='qwen3:8b', batch_size=20):
        '''
        model: название модели
        batch_size: размер патча для отправки на разметку
        '''
        self.client = LLM(provider=provider, model=model)
        self.batch_size = batch_size

        self.persons = {}
        self.name_map = {}
        self.surname_map = {}
        self.patronymic_map = {}

        self.ALLOWED_TAGS = {'G', 'S', 'P', 'SI', 'GI', 'PI', 'N', 'O'}
        self.DEFAULT_MASK = 'S GI SI'

        self.FIELD_CONFIG = {
            'G': ('name', self.name_map, 'GI'),
            'S': ('surname', self.surname_map, 'SI'),
            'P': ('patronymic', self.patronymic_map, 'PI'),
        }

        with open(DATA_DIR / 'fake_names.json', 'r', encoding='utf-8') as f:
            self.fake_data = json.load(f)

        self.fake_data = {int(k): v for k, v in self.fake_data.items()}
        self.pm = PromptManager()
    
    def reset_state(self):
        '''
        Полностью сбрасывает внутреннее состояние анонимизатора
        '''

        self.persons = {}
        self.name_map = {}
        self.surname_map = {}
        self.patronymic_map = {}
    

    def _tokenize_name(self, text):
        '''
        Разбивает ФИО на токены (учитывает дефисы и инициалы).
        '''
        word_pattern = r"[^\W\d_]+(?:[-'][^\W\d_]+)*"
        initial_pattern = r'[^\W\d_]\.?'
        pattern = f'{word_pattern}|{initial_pattern}'
        return re.findall(pattern, text, flags=re.UNICODE)


    def _validate_mask(self, mask):
        '''
        Проверяет корректность маски.
        Если маска некорректна — возвращает DEFAULT_MASK.
        '''
        if not isinstance(mask, str):
            return self.DEFAULT_MASK

        tokens = [t for t in mask.split() if t in self.ALLOWED_TAGS]
        return ' '.join(tokens) if tokens else self.DEFAULT_MASK


    def _chunk_list(self, lst):
        '''
        Делит список на батчи фиксированного размера
        '''
        for i in range(0, len(lst), self.batch_size):
            yield lst[i:i + self.batch_size]


    def _call_model(self, names_patch):
        '''
        Отправляет батч имен в LLM и возвращает распарсенный JSON
        '''
        prompt = self.pm.get(
            'person_mention_processing',
            names=names_patch
        )
        return self.client.generate(
            prompt=prompt, 
            temperature=0.1
        )


    def _process_patch(self, llm_output, names_patch, prev_max_id):
        '''
        Нормализует и валидирует выход LLM.
        Гарантирует:
        - наличие всех original из names_patch
        - корректные person_id
        - корректную mask
        - корректный sex
        '''

        cleaned = []
        seen_originals = set()

        if not isinstance(llm_output, list):
            llm_output = []

        for item in llm_output:
            if not isinstance(item, dict):
                continue

            # original
            original = item.get('original')
            if not original:
                continue
            seen_originals.add(original)

            # person_id
            try:
                pid = int(item.get('person_id', prev_max_id + 1))
            except:
                pid = prev_max_id + 1

            # sex
            sex = item.get('sex')
            if sex not in (0, 1):
                sex = random.choice([0, 1])

            # mask
            mask = self._validate_mask(item.get('mask'))
            mask_tokens = mask.split()

            # если вся маска — O
            auto_fixed = False
            if all(t == 'O' for t in mask_tokens):
                mask = self.DEFAULT_MASK
                auto_fixed = True

            cleaned.append({
                'original': original,
                'person_id': pid,
                'mask': mask,
                'sex': sex,
                'auto_fixed': auto_fixed
            })

        # добавляем пропущенные original
        next_id = prev_max_id + 1
        for name in names_patch:
            if name not in seen_originals:
                cleaned.append({
                    'original': name,
                    'person_id': next_id,
                    'mask': self.DEFAULT_MASK,
                    'sex': 1,
                    'auto_fixed': True
                })
                next_id += 1

        # перенумерация ID
        id_mapping = {}
        next_id = prev_max_id + 1
        for item in cleaned:
            old_id = item['person_id']
            if old_id not in id_mapping:
                id_mapping[old_id] = next_id
                next_id += 1
            item['person_id'] = id_mapping[old_id]

        new_max_id = next_id - 1
        return cleaned, new_max_id
 

    def anonymize_list(self, names_list):
        '''
        Получает от LLM список сущностей с масками и полом.
        Исправляет проблемы в выхоле LLM.
        Согласовывает person_id между чанками
        '''
        final_output = []
        current_max_id = 0

        for patch in self._chunk_list(names_list):

            llm_output = self._call_model(patch)

            cleaned_patch, current_max_id = self._process_patch(
                llm_output,
                patch,
                current_max_id
            )

            final_output.extend(cleaned_patch)
        self.llm_check = final_output
        return final_output


    def _assign_field(self, person: FakePerson, tag, orig, sex):
        '''
        Назначает фейковое имя/фамилию/отчество
        с сохранением согласованности.
        '''
        field_type, storage_map, initial_key = self.FIELD_CONFIG[tag]

        fake = storage_map.get(orig)

        if not fake:
            fake = random_except(
                self.fake_data[sex][field_type],
                orig,
                drop_l=list(storage_map.values()),
            )
            storage_map[orig] = fake

        setattr(person, field_type, fake)
        setattr(person, f'{field_type}_initial', fake[0] + '.')

        if tag == 'G':
            person.nickname = self.fake_data[sex]['nickname'].get(fake, fake)


    def _gen_fake(self, llm_persons):
        '''
        Двухпроходная генерация фейковых данных.

        1 PASS:
            - назначаем поля согласно mask
            - сохраняем согласованность через storage_map

        2 PASS:
            - дозаполняем отсутствующие G/S/P
            - гарантируем, что у каждой персоны есть все основные поля
        '''

        # 1 PASS
        for el in llm_persons:

            pid = el['person_id']
            sex = el['sex']

            # Получаем или создаём объект персоны
            person = self.persons.get(pid)
            if not person:
                person = FakePerson(sex=sex)

            # Если запись автофикснута — просто сохраняем и идём дальше
            if el.get('auto_fixed'):
                self.persons[pid] = person
                continue

            mask = el['mask'].split()
            token_orig = self._tokenize_name(el['original'])

            for i, tag in enumerate(mask):

                if i >= len(token_orig):
                    break

                if tag not in self.FIELD_CONFIG:
                    continue

                field_type, storage_map, _ = self.FIELD_CONFIG[tag]

                # Если поле уже назначено — пропускаем
                if getattr(person, field_type) is not None:
                    continue

                orig = token_orig[i]

                # Берём из storage_map для согласованности
                fake = storage_map.get(orig)

                if not fake:
                    fake = random_except(
                        self.fake_data[sex][field_type],
                        orig,
                        drop_l=list(storage_map.values())
                    )
                    storage_map[orig] = fake

                # Назначаем основное поле
                setattr(person, field_type, fake)

                # Назначаем инициал
                setattr(person, f'{field_type}_initial', fake[0] + '.')

                # Если это имя — добавляем nickname
                if tag == 'G':
                    person.nickname = self.fake_data[sex]['nickname'].get(fake, fake)

            self.persons[pid] = person

        # 2 PASS
        for el in llm_persons:

            pid = el['person_id']
            sex = el['sex']

            person = self.persons[pid]

            for tag, (field_type, storage_map, _) in self.FIELD_CONFIG.items():

                # Если поле уже есть — пропускаем
                if getattr(person, field_type) is not None:
                    continue

                fake = random_except(
                    self.fake_data[sex][field_type],
                    '',
                    drop_l=list(storage_map.values())
                )

                # ВАЖНО: сохраняем согласованность через уникальный ключ
                storage_map[f'{pid}_{tag}'] = fake

                setattr(person, field_type, fake)
                setattr(person, f'{field_type}_initial', fake[0] + '.')

                if tag == 'G':
                    person.nickname = self.fake_data[sex]['nickname'].get(fake, fake)

            self.persons[pid] = person
    

    def anonymize(self, input):
        '''
        Полный цикл анонимизации.
        Возвращает словарь original -> fake.
        '''
        if not input:
            return {}
            
        self.reset_state()

        llm_persons = self.anonymize_list(input)
        self._gen_fake(llm_persons)

        result = {}

        for el in llm_persons:

            person = self.persons[el['person_id']]
            mask = el['mask'].split()

            fake_parts = []
            for tag in mask:
                if tag in self.FIELD_CONFIG:
                    field_type, _, _ = self.FIELD_CONFIG[tag]
                    value = getattr(person, field_type)
                    if value:
                        fake_parts.append(value)
                elif tag in ['GI', 'SI', 'PI']:
                    # добавляем инициал соответствующего поля
                    field_map = {'GI': 'name_initial', 'SI': 'surname_initial', 'PI': 'patronymic_initial'}
                    init_value = getattr(person, field_map[tag])
                    if init_value:
                        fake_parts.append(init_value)
                elif tag == 'N' and person.nickname:
                    fake_parts.append(person.nickname)

            fake = ' '.join(fake_parts)
            fake = match_case_and_gender(
                el['original'],
                fake,
                person.sex
            )

            result[el['original']] = fake

        return result
    