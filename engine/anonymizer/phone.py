import random
import string


class PhoneAnonymizer:
    def _randomize_phone(self, phone):
        result = []

        # сколько цифр сохраняем
        if phone.startswith("+"):
            preserve_digits = 0
            for ch in phone[1:]:
                if ch.isdigit():
                    preserve_digits += 1
                else:
                    break
        else:
            preserve_digits = 2

        digit_seen = 0

        for ch in phone:
            if ch.isdigit():
                digit_seen += 1
                if digit_seen <= preserve_digits:
                    result.append(ch)
                else:
                    result.append(random.choice(string.digits))
            else:
                result.append(ch)

        return "".join(result)

    def anonymize(self, input):
        return {phone: self._randomize_phone(phone) for phone in input}