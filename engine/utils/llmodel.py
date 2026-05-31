# engine/utils/llmodel.py
import os
import json
from ollama import Client
from engine.utils.helper import extract_json_array, extract_json_object

# Хост Ollama (для Docker: http://ollama:11434)
OLLAMA_HOST = os.environ.get("OLLAMA_HOST", "http://localhost:11434")


class LLM:
    def __init__(self, provider, model):
        """
        provider: 'ollama' | 'giga'
        model: название модели
        """
        self.provider = provider.lower()
        self.model = model

    def generate(self, prompt, temperature=0.25, output_format='json_array', think=False):
        """
        Универсальный метод генерации
        """

        if self.provider == "ollama":
            self.client = Client(host=OLLAMA_HOST)
            return self._generate_ollama(prompt, temperature, output_format, think)

        elif self.provider == "giga":
            return self._generate_giga(prompt, temperature, output_format)

        else:
            raise ValueError(f"Unsupported provider: {self.provider}")

    def _generate_ollama(self, prompt, temperature, output_format, think):
        response = self.client.generate(
            model=self.model,
            prompt=prompt,
            options={"temperature": temperature},
            think=think
        )
        text = response.response.strip()
        if output_format == 'json_array':
            json_block = extract_json_array(text)
            try:
                return json.loads(json_block)
            except Exception:
                return []
        elif output_format == 'json_object':
            json_block = extract_json_object(text)
            try:
                return json.loads(json_block)
            except Exception:
                return []
        return text

    def _generate_giga(self, prompt, temperature):
        pass