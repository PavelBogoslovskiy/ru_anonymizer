import random
import string


class EmailAnonymizer:
    def __init__(self, mode="preserve_domain"):
        """
        mode:
            preserve_domain  - сохраняем домен
            randomize_domain - рандомизируем весь email
        """
        self.mode = mode

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

        return "".join(result)

    def _randomize_email(self, email):
        if "@" not in email:
            return self._randomize_string(email)

        local_part, domain = email.split("@", 1)

        randomized_local = self._randomize_string(local_part)

        if self.mode == "preserve_domain":
            return f"{randomized_local}@{domain}"

        elif self.mode == "randomize_domain":
            randomized_domain = self._randomize_string(domain)
            return f"{randomized_local}@{randomized_domain}"

        else:
            raise ValueError("mode must be 'preserve_domain' or 'randomize_domain'")

    def anonymize(self, input):
        """
        Принимает список input
        Возвращает словарь:
        {original_email: anonymized_email}
        """
        return {email: self._randomize_email(email) for email in input}