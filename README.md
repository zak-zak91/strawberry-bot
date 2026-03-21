# 🍓 WhatsApp Бот — Клубника в шоколаде
## Полная инструкция по запуску

---

## Что делает бот

- Приветствует клиента на русском или казахском (автоопределение)
- Показывает каталог товаров с ценами (8 позиций)
- Принимает заказы пошагово (имя → товар → доставка/самовывоз → оплата → подтверждение)
- Передаёт заказ менеджеру в Telegram мгновенно
- Отвечает на свободные вопросы через Claude AI
- После AI-ответа снова показывает меню

---

## Схема диалога

```
Клиент пишет
      ↓
[Главное меню]
  📦 Каталог    → список товаров → детали → Заказать
  🛒 Заказ      → имя → товар → доставка/самовывоз → оплата → подтверждение
  👨‍💼 Менеджер  → уведомление в Telegram + контакт
      ↓
Свободный вопрос → Claude AI отвечает → снова показывает меню
```

---

## Шаг 1 — Получи токены (регистрации)

### 1.1 Meta (WhatsApp)
1. Зайди на https://developers.facebook.com
2. Создай приложение → тип **Business**
3. Добавь продукт **WhatsApp**
4. Скопируй:
   - `Phone Number ID`
   - `Access Token` (временный — потом сделай постоянный через System User)
5. В Webhook настрой:
   - URL: `https://твой-домен.railway.app/webhook`
   - Verify Token: `strawberry_bot_2024`
   - Subscribe on: `messages`

### 1.2 Anthropic (Claude AI)
1. Зайди на https://console.anthropic.com
2. API Keys → Create Key
3. Пополни баланс от $5

### 1.3 Telegram бот для менеджера
1. Напиши @BotFather в Telegram
2. `/newbot` → придумай имя → получи токен
3. Чтобы узнать свой chat_id — напиши @userinfobot

### 1.4 Railway (хостинг)
1. Зарегистрируйся на https://railway.app через GitHub
2. New Project → Deploy from GitHub repo

---

## Шаг 2 — Загрузи код на GitHub

```bash
# В папке с файлами:
git init
git add .
git commit -m "Initial bot"
git branch -M main
git remote add origin https://github.com/ВАШ_НИК/strawberry-bot.git
git push -u origin main
```

**Создай `.gitignore`:**
```
.env
__pycache__/
*.pyc
```

---

## Шаг 3 — Деплой на Railway

1. На Railway: New Project → Deploy from GitHub → выбери репо
2. Зайди в **Variables** и добавь переменные окружения:

| Переменная     | Значение                    |
|----------------|-----------------------------|
| WA_TOKEN       | токен из Meta               |
| PHONE_ID       | Phone Number ID из Meta     |
| CLAUDE_API_KEY | ключ из console.anthropic   |
| TG_BOT_TOKEN   | токен от @BotFather         |
| TG_MANAGER_ID  | твой chat_id в Telegram     |

3. Railway автоматически задеплоит и даст URL вида:
   `https://strawberry-bot-production.up.railway.app`

---

## Шаг 4 — Подключи Webhook в Meta

В Meta Developer Console → WhatsApp → Configuration:
- Webhook URL: `https://твой-url.railway.app/webhook`
- Verify Token: `strawberry_bot_2024`
- Нажми **Verify and Save**
- В Webhook Fields подпишись на `messages`

---

## Шаг 5 — Тест

1. Напиши своему WhatsApp Business номеру "Привет"
2. Должно появиться главное меню с 3 кнопками
3. Проверь каждый сценарий
4. Проверь что заказы приходят в Telegram

---

## Обновление каталога

В файле `app.py` найди раздел `CATALOG` и редактируй:

```python
CATALOG = [
    {"id": 1, "name": "Название RU", "name_kz": "Атауы KZ", "price": 2500, "unit": "500г"},
    # добавляй или убирай позиции
]
```

После изменений — `git push`, Railway задеплоит автоматически.

---

## Стоимость в месяц

| Сервис       | Цена                          |
|--------------|-------------------------------|
| Railway      | Бесплатно (500 часов/мес)    |
| Meta API     | Бесплатно (1000 диал/мес)    |
| Claude API   | ~$3-10 в зависимости от нагрузки |
| Telegram Bot | Бесплатно                    |
| **Итого**    | **~$3-10/мес**               |

---

## Частые вопросы

**Бот не отвечает?**
→ Проверь что Webhook верифицирован в Meta
→ Проверь переменные окружения на Railway
→ Посмотри логи на Railway → Deployments → View Logs

**Кнопки не работают?**
→ WhatsApp Business API поддерживает кнопки только для верифицированных номеров
→ На тестовом номере Meta кнопки работают сразу

**Как добавить новый язык?**
→ В функции `detect_lang` добавь проверку символов
→ В каждой функции добавь ветку `elif lang == "новый_язык"`
