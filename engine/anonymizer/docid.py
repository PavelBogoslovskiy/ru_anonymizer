import random
import string


class DocIdAnonymizer:
    def _randomize_string(self, text):
        result = []

        for ch in text:
            if ch.isalpha():
                if ch.islower():
                    result.append(random.choice(string.ascii_lowercase))
                else:
                    result.append(random.choice(string.ascii_uppercase))
            elif ch.isdigit():
                result.append(random.choice(string.digits))
            else:
                result.append(ch)

        return ''.join(result)

    def anonymize(self, input):
        '''
        Принимает список input
        Возвращает словарь сопоставлений:
        {original_doc_id: anonymized_doc_id}
        '''
        return {doc_id: self._randomize_string(doc_id) for doc_id in input}