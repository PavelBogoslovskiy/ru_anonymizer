import torch
from transformers import AutoTokenizer, AutoModelForTokenClassification
from pathlib import Path

class NERPredictor:
    """
    NER предсказатель для длинных текстов с разбиением на чанки
    Возвращает список сущностей в формате {'label', 'start', 'end', 'text'}
    """
    
    # Путь к модели относительно этого файла
    DEFAULT_MODEL_PATH = Path(__file__).parent.parent / "data" / "ner_model"
    
    def __init__(self, model_path=None, max_tokens=400, stride=125, device=None):
        self.model_path = str(model_path or self.DEFAULT_MODEL_PATH)
        self.max_tokens = max_tokens
        self.stride = stride

        self.tokenizer = AutoTokenizer.from_pretrained(self.model_path)
        self.model = AutoModelForTokenClassification.from_pretrained(self.model_path)

        if device is None:
            if torch.cuda.is_available():
                device = "cuda"
            elif getattr(torch.backends, "mps", None) is not None and torch.backends.mps.is_available():
                device = "mps"
            else:
                device = "cpu"
        self.device = torch.device(device)
        self.model.to(self.device)
        self.model.eval()

        raw = getattr(self.model.config, "id2label", {}) or {}
        # robust ordering of labels by numeric key when possible
        def _key(k):
            try:
                return int(k)
            except Exception:
                return k
        items = sorted(raw.items(), key=lambda kv: _key(kv[0]))
        self.label_list = [v for _, v in items]

    def _chunk_text(self, text):
        enc = self.tokenizer(text, return_offsets_mapping=True, truncation=False)
        input_ids = enc["input_ids"]
        offsets = enc["offset_mapping"]

        chunks = []
        start = 0
        n = len(input_ids)
        while start < n:
            end = min(start + self.max_tokens, n)
            chunks.append({"input_ids": input_ids[start:end], "offsets": offsets[start:end]})
            if end == n:
                break
            start = end - self.stride
        return chunks

    def _predict_chunk(self, chunk):
        input_ids = torch.tensor([chunk["input_ids"]], device=self.device)
        attention_mask = torch.ones_like(input_ids, device=self.device)
        with torch.no_grad():
            outputs = self.model(input_ids=input_ids, attention_mask=attention_mask)
            logits = outputs.logits
            preds = torch.argmax(logits, dim=2).squeeze().cpu().numpy()

        res = []
        offsets = chunk.get("offsets", [])
        for i, p in enumerate(preds):
            if i >= len(offsets):
                break
            offset = offsets[i]
            if not offset or (isinstance(offset, (tuple, list)) and offset[0] == offset[1] == 0):
                continue
            try:
                label = self.label_list[int(p)]
            except Exception:
                label = "O"
            res.append((offset, label))
        return res

    def _clean_label(self, label):
        """Убирает префиксы B- и I- из меток"""
        if label and (label.startswith("B-") or label.startswith("I-")):
            return label[2:]
        return label

    def _merge_entities(self, text, chunks_preds):
        """Объединяет соседние токены одной сущности"""
        entities = []
        curr = None
        occupied = set()

        for chunk_pred in chunks_preds:
            for (start, end), label in chunk_pred:
                # Пропускаем уже обработанные позиции
                if any(pos in occupied for pos in range(start, end)):
                    continue

                if label == "O":
                    if curr:
                        entities.append(curr)
                        occupied.update(range(curr["start"], curr["end"]))
                        curr = None
                    continue

                clean = self._clean_label(label)

                if curr is None:
                    curr = {"label": clean, "start": start, "end": end, "text": text[start:end]}
                    continue

                # Проверяем можно ли объединить с предыдущим токеном
                can_merge = False
                if curr["label"] == clean:
                    if start <= curr["end"]:
                        can_merge = True
                    else:
                        gap = text[curr["end"]:start]
                        # Объединяем если между токенами только пробелы
                        if gap.strip() == "" or all(not ch.isalnum() for ch in gap):
                            can_merge = True

                if can_merge:
                    curr["end"] = max(curr["end"], end)
                    curr["text"] = text[curr["start"]: curr["end"]]
                else:
                    entities.append(curr)
                    occupied.update(range(curr["start"], curr["end"]))
                    curr = {"label": clean, "start": start, "end": end, "text": text[start:end]}

        if curr:
            entities.append(curr)
            occupied.update(range(curr["start"], curr["end"]))

        return sorted(entities, key=lambda x: x["start"])

    def predict(self, text):
        """Основной метод - предсказывает сущности в тексте"""
        chunks = self._chunk_text(text)
        chunks_preds = [self._predict_chunk(c) for c in chunks]
        entities = self._merge_entities(text, chunks_preds)
        return entities
