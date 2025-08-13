# osintmagic-plus

Этичный, асинхронный OSINT-парсер (CLI) с HTML-отчётом.  
Создан: 2025-08-13

## Быстрый старт

```bash
python -m venv .venv
source .venv/bin/activate  # Windows: .venv\Scripts\activate
pip install -U pip
pip install -e .
cp .env.example .env
```

Запуск:

```bash
osintmagic-plus   --name "Алишер Моргенштерн"   --phone "+79161234567"   --username "morgenshtern"   --email "a.morgen@example.com"   --birth-year 1998   --city "Москва"   --country "Россия"   --providers brave   --output-format html   --log-level info   --timeout 10   --max-concurrent 50   --no-darkweb   --cache-ttl 86400   --depth 2
```

### Переменные окружения (.env)

- `BRAVE_API_KEY` — ключ Brave Search API (опционально)
- `HIBP_API_KEY` — ключ HaveIBeenPwned (опционально)
- `HTTP_PROXY` и/или `HTTPS_PROXY` — при необходимости
- `TOR_SOCKS` — например, `socks5://127.0.0.1:9050` (используется только при `--tor`)

## Глубины поиска

- 1 — до 50 сетевых запросов
- 2 — до 100
- 3 — до 150
- 4 — до 300

Планировщик запросов гарантирует тематическое разнообразие на любой глубине.

## Этика и законность

- Только общедоступные данные
- Уважение `robots.txt`
- Троттлинг и ограничение частоты
- Поддержка Tor только при явном флаге `--tor`
- Данные остаются локально
