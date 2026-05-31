# Система анонимизации текстов

Веб-приложение для автоматической анонимизации персональных данных в текстах на русском языке.

## Возможности

- Распознавание именованных сущностей (NER): имена, организации, адреса, телефоны, email, даты, суммы, номера документов
- Замена на реалистичные фейковые данные
- Сохранение истории анонимизации
- Загрузка/выгрузка файлов (.txt)

## Структура проекта

```
anonim_project/
├── web/                    # Django веб-приложение
│   ├── core/               # Основное приложение
│   ├── templates/          # HTML шаблоны
│   └── settings.py         # Настройки Django
├── engine/                 # Ядро анонимизации
│   ├── anonymizer/         # Анонимизаторы по типам сущностей
│   ├── finder/             # NER модель
│   ├── services/           # Сервисный слой
│   ├── utils/              # Вспомогательные утилиты
│   └── data/               # Конфигурации и данные
├── manage.py
├── requirements.txt
├── train_ner.ipynb         # Обучение NER
├── Dockerfile
└── docker-compose.yml
```

---

## Запуск без Docker

### 1. Создание виртуального окружения

```bash
python3 -m venv .venv
source .venv/bin/activate  # macOS/Linux
# или
.venv\Scripts\activate     # Windows
```

### 2. Установка зависимостей

```bash
pip install -r requirements.txt
```

### 3. Применение миграций

```bash
python manage.py migrate
```

### 4. Запуск сервера

```bash
python manage.py runserver
```

Приложение доступно по адресу: http://127.0.0.1:8000

### 5. Ollama для LLM

```bash
# Установка Ollama: https://ollama.ai
ollama pull qwen3:8b
ollama serve
```

---

## Запуск с Docker

### 1. Сборка и запуск

```bash
docker-compose up --build
```

### 2. Запуск в фоне

```bash
docker-compose up -d --build
```

### 3. Загрузка модели Ollama

```bash
docker-compose exec ollama ollama pull qwen3:8b
```

### 4. Остановка

```bash
docker-compose down
```

Приложение доступно по адресу: http://localhost:8000

---

## Переменные окружения

| Переменная | Описание | По умолчанию |
|------------|----------|--------------|
| `DJANGO_DEBUG` | Режим отладки (1/0) | `0` |
| `DJANGO_SECRET` | Секретный ключ Django | `dev-secret-key` |
| `OLLAMA_HOST` | Адрес Ollama API | `http://localhost:11434` |

---

## Разработка

```bash
# Создание суперпользователя
python manage.py createsuperuser

# Сбор статики (для продакшена)
python manage.py collectstatic
```

## Лицензия

MIT
