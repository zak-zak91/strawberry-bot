from flask import Flask, request, jsonify
import requests
import anthropic
import json
import os
from datetime import datetime

app = Flask(__name__)

def normalize_phone(phone):
    """Нормализация для казахских номеров"""
    if phone.startswith("77") and len(phone) == 11:
        # Вставляем 8 после 7: 77073648466 → 787073648466
        phone = "78" + phone[1:]
    return phone

# ─── НАСТРОЙКИ (заменить на свои) ───────────────────────────────
VERIFY_TOKEN     = "strawberry_bot_2024"          # придумай сам
WA_TOKEN         = os.getenv("WA_TOKEN", "ВАШ_WHATSAPP_TOKEN")
PHONE_ID         = os.getenv("PHONE_ID", "ВАШ_PHONE_NUMBER_ID")
CLAUDE_API_KEY   = os.getenv("CLAUDE_API_KEY", "ВАШ_CLAUDE_API_KEY")
TG_BOT_TOKEN     = os.getenv("TG_BOT_TOKEN", "ВАШ_TELEGRAM_BOT_TOKEN")
TG_MANAGER_ID    = os.getenv("TG_MANAGER_ID", "ВАШ_TELEGRAM_CHAT_ID")  # твой chat_id в Telegram
# ────────────────────────────────────────────────────────────────

claude = anthropic.Anthropic(api_key=CLAUDE_API_KEY)

# ─── КАТАЛОГ ТОВАРОВ ────────────────────────────────────────────
CATALOG = [
    {"id": 1, "name": "Клубника в белом шоколаде",       "name_kz": "Ақ шоколадтағы құлпынай",       "price": 2500, "unit": "500г"},
    {"id": 2, "name": "Клубника в тёмном шоколаде",      "name_kz": "Қара шоколадтағы құлпынай",     "price": 2500, "unit": "500г"},
    {"id": 3, "name": "Клубника в молочном шоколаде",    "name_kz": "Сүт шоколадтағы құлпынай",      "price": 2500, "unit": "500г"},
    {"id": 4, "name": "Ассорти (3 вида шоколада)",       "name_kz": "Ассорти (3 түрлі шоколад)",     "price": 2800, "unit": "500г"},
    {"id": 5, "name": "Подарочный бокс S",                "name_kz": "Сыйлық бокс S",                 "price": 4500, "unit": "12 шт"},
    {"id": 6, "name": "Подарочный бокс M",                "name_kz": "Сыйлық бокс M",                 "price": 7500, "unit": "24 шт"},
    {"id": 7, "name": "Подарочный бокс L",                "name_kz": "Сыйлық бокс L",                 "price": 12000, "unit": "36 шт"},
    {"id": 8, "name": "Корпоративный заказ (от 50 шт)",  "name_kz": "Корпоративтік тапсырыс (50+)", "price": None,  "unit": "под запрос"},
]

# ─── СОСТОЯНИЯ ДИАЛОГОВ ─────────────────────────────────────────
# Структура: { phone: { "state": "...", "order": {...}, "lang": "ru" } }
sessions = {}

def get_session(phone):
    if phone not in sessions:
        sessions[phone] = {"state": "start", "order": {}, "lang": "ru"}
    return sessions[phone]

def set_state(phone, state):
    sessions[phone]["state"] = state

# ─── ОТПРАВКА СООБЩЕНИЙ ─────────────────────────────────────────
def send_text(phone, text):
    url = f"https://graph.facebook.com/v19.0/{PHONE_ID}/messages"
    headers = {"Authorization": f"Bearer {WA_TOKEN}", "Content-Type": "application/json"}
    payload = {
        "messaging_product": "whatsapp",
        "to": phone,
        "type": "text",
        "text": {"body": text}
    }
    requests.post(url, json=payload, headers=headers)

def send_buttons(phone, body, buttons):
    url = f"https://graph.facebook.com/v19.0/{PHONE_ID}/messages"
    headers = {"Authorization": f"Bearer {WA_TOKEN}", "Content-Type": "application/json"}
    payload = {
        "messaging_product": "whatsapp",
        "to": phone,
        "type": "interactive",
        "interactive": {
            "type": "button",
            "body": {"text": body},
            "action": {
                "buttons": [
                    {"type": "reply", "reply": {"id": btn["id"], "title": btn["title"]}}
                    for btn in buttons
                ]
            }
        }
    }
    r = requests.post(url, json=payload, headers=headers)
    print(f"send_buttons response: {r.status_code} {r.text}")

def send_list(phone, body, button_label, sections):
    """Отправить список с разделами (для каталога)"""
    url = f"https://graph.facebook.com/v19.0/{PHONE_ID}/messages"
    headers = {"Authorization": f"Bearer {WA_TOKEN}", "Content-Type": "application/json"}
    payload = {
        "messaging_product": "whatsapp",
        "to": phone,
        "type": "interactive",
        "interactive": {
            "type": "list",
            "body": {"text": body},
            "action": {
                "button": button_label,
                "sections": sections
            }
        }
    }
    requests.post(url, json=payload, headers=headers)

# ─── ГЛАВНОЕ МЕНЮ ───────────────────────────────────────────────
def send_main_menu(phone, lang="ru"):
    if lang == "ru":
        text = "🍓 Привет! Добро пожаловать в *Клубника в шоколаде*!\n\nЧем могу помочь?"
        buttons = [
            {"id": "catalog",  "title": "📦 Каталог"},
            {"id": "order",    "title": "🛒 Сделать заказ"},
            {"id": "manager",  "title": "👨‍💼 Менеджер"},
        ]
    else:
        text = "🍓 Сәлем! *Шоколадтағы құлпынай* дүкеніне қош келдіңіз!\n\nҚалай көмектесе аламын?"
        buttons = [
            {"id": "catalog",  "title": "📦 Каталог"},
            {"id": "order",    "title": "🛒 Тапсырыс беру"},
            {"id": "manager",  "title": "👨‍💼 Менеджер"},
        ]
    send_buttons(phone, text, buttons)
    set_state(phone, "main_menu")

# ─── КАТАЛОГ ────────────────────────────────────────────────────
def send_catalog(phone, lang="ru"):
    items = []
    for item in CATALOG:
        name = item["name"] if lang == "ru" else item["name_kz"]
        price_str = f"{item['price']} тг" if item["price"] else "по запросу"
        items.append({
            "id": f"cat_{item['id']}",
            "title": name[:24],  # WA ограничение 24 символа
            "description": f"{price_str} / {item['unit']}"
        })

    sections = [{"title": "🍓 Наши товары" if lang == "ru" else "🍓 Біздің тауарлар", "rows": items}]
    body = "Выберите товар для подробной информации 👇" if lang == "ru" else "Толығырақ білу үшін тауарды таңдаңыз 👇"
    btn_label = "Открыть каталог" if lang == "ru" else "Каталогты ашу"
    send_list(phone, body, btn_label, sections)
    set_state(phone, "catalog")

# ─── ДЕТАЛИ ТОВАРА ──────────────────────────────────────────────
def send_item_detail(phone, item_id, lang="ru"):
    item = next((i for i in CATALOG if i["id"] == item_id), None)
    if not item:
        return
    name = item["name"] if lang == "ru" else item["name_kz"]
    price_str = f"{item['price']} тг" if item["price"] else "уточните у менеджера"

    if lang == "ru":
        text = f"*{name}*\n\n💰 Цена: {price_str}\n📦 Объём: {item['unit']}\n\nХотите заказать?"
        buttons = [
            {"id": f"buy_{item['id']}", "title": "🛒 Заказать"},
            {"id": "catalog",           "title": "◀️ Назад"},
            {"id": "main_menu",         "title": "🏠 Главное меню"},
        ]
    else:
        text = f"*{name}*\n\n💰 Баға: {price_str}\n📦 Көлемі: {item['unit']}\n\nТапсырыс бергіңіз келе ме?"
        buttons = [
            {"id": f"buy_{item['id']}", "title": "🛒 Тапсырыс"},
            {"id": "catalog",           "title": "◀️ Артқа"},
            {"id": "main_menu",         "title": "🏠 Басты мәзір"},
        ]
    send_buttons(phone, text, buttons)

# ─── СБОР ЗАКАЗА ────────────────────────────────────────────────
def start_order(phone, lang="ru", item_id=None):
    session = get_session(phone)
    if item_id:
        item = next((i for i in CATALOG if i["id"] == item_id), None)
        if item:
            session["order"]["product"] = item["name"] if lang == "ru" else item["name_kz"]
            session["order"]["price"] = item["price"]

    if lang == "ru":
        send_text(phone, "📝 Оформляем заказ!\n\nКак вас зовут?")
    else:
        send_text(phone, "📝 Тапсырысты рәсімдейміз!\n\nАтыңыз кім?")
    set_state(phone, "order_name")

def ask_delivery(phone, lang="ru"):
    if lang == "ru":
        body = "Как получите заказ?"
        buttons = [
            {"id": "delivery",  "title": "🚗 Доставка"},
            {"id": "pickup",    "title": "🏪 Самовывоз"},
        ]
    else:
        body = "Тапсырысты қалай аласыз?"
        buttons = [
            {"id": "delivery",  "title": "🚗 Жеткізу"},
            {"id": "pickup",    "title": "🏪 Өзі алу"},
        ]
    send_buttons(phone, body, buttons)
    set_state(phone, "order_delivery")

def ask_payment(phone, lang="ru"):
    if lang == "ru":
        body = "Способ оплаты?"
        buttons = [
            {"id": "pay_cash",  "title": "💵 Наличные"},
            {"id": "pay_kaspi", "title": "📱 Kaspi Pay"},
        ]
    else:
        body = "Төлем тәсілі?"
        buttons = [
            {"id": "pay_cash",  "title": "💵 Қолма-қол"},
            {"id": "pay_kaspi", "title": "📱 Kaspi Pay"},
        ]
    send_buttons(phone, body, buttons)
    set_state(phone, "order_payment")

def confirm_order(phone, lang="ru"):
    session = get_session(phone)
    order = session["order"]

    product  = order.get("product", "—")
    name     = order.get("name", "—")
    phone_no = order.get("phone", "—")
    delivery = order.get("delivery", "—")
    address  = order.get("address", "")
    payment  = order.get("payment", "—")
    price    = order.get("price")
    price_str = f"{price} тг" if price else "по запросу"

    if lang == "ru":
        summary = (
            f"✅ *Подтвердите заказ:*\n\n"
            f"🍓 Товар: {product}\n"
            f"💰 Сумма: {price_str}\n"
            f"👤 Имя: {name}\n"
            f"📞 Телефон: {phone_no}\n"
            f"🚗 Получение: {delivery}\n"
            + (f"📍 Адрес: {address}\n" if address else "")
            + f"💳 Оплата: {payment}"
        )
        buttons = [
            {"id": "confirm_yes", "title": "✅ Подтвердить"},
            {"id": "confirm_no",  "title": "❌ Отменить"},
        ]
    else:
        summary = (
            f"✅ *Тапсырысты растаңыз:*\n\n"
            f"🍓 Тауар: {product}\n"
            f"💰 Сомасы: {price_str}\n"
            f"👤 Аты: {name}\n"
            f"📞 Телефон: {phone_no}\n"
            f"🚗 Алу: {delivery}\n"
            + (f"📍 Мекенжай: {address}\n" if address else "")
            + f"💳 Төлем: {payment}"
        )
        buttons = [
            {"id": "confirm_yes", "title": "✅ Растау"},
            {"id": "confirm_no",  "title": "❌ Болдырмау"},
        ]
    send_buttons(phone, summary, buttons)
    set_state(phone, "order_confirm")

def finalize_order(phone, lang="ru"):
    session = get_session(phone)
    order = session["order"]
    notify_manager(phone, order)

    if lang == "ru":
        send_text(phone, "🎉 Заказ принят! Менеджер свяжется с вами в течение 15 минут.\n\nСпасибо, что выбрали нас! 🍓")
    else:
        send_text(phone, "🎉 Тапсырыс қабылданды! Менеджер 15 минут ішінде хабарласады.\n\nБізді таңдағаныңызға рахмет! 🍓")

    # Сбрасываем заказ
    sessions[phone]["order"] = {}
    set_state(phone, "start")

# ─── УВЕДОМЛЕНИЕ МЕНЕДЖЕРУ В TELEGRAM ──────────────────────────
def notify_manager(phone, order):
    product  = order.get("product", "—")
    name     = order.get("name", "—")
    delivery = order.get("delivery", "—")
    address  = order.get("address", "")
    payment  = order.get("payment", "—")
    price    = order.get("price")
    price_str = f"{price} тг" if price else "по запросу"
    time_str  = datetime.now().strftime("%d.%m.%Y %H:%M")

    msg = (
        f"🍓 *НОВЫЙ ЗАКАЗ* — {time_str}\n\n"
        f"📦 Товар: {product}\n"
        f"💰 Сумма: {price_str}\n"
        f"👤 Клиент: {name}\n"
        f"📞 WhatsApp: +{phone}\n"
        f"🚗 Получение: {delivery}\n"
        + (f"📍 Адрес: {address}\n" if address else "")
        + f"💳 Оплата: {payment}"
    )
    requests.post(
        f"https://api.telegram.org/bot{TG_BOT_TOKEN}/sendMessage",
        json={"chat_id": TG_MANAGER_ID, "text": msg, "parse_mode": "Markdown"}
    )

# ─── AI ОТВЕТ (Claude) ──────────────────────────────────────────
def get_ai_response(question, lang="ru"):
    catalog_text = "\n".join([
        f"- {i['name']} ({i['name_kz']}): {i['price'] or 'по запросу'} тг / {i['unit']}"
        for i in CATALOG
    ])
    system = f"""Ты помощник магазина «Клубника в шоколаде» (Казахстан).
Отвечай на русском и казахском языках в зависимости от вопроса.
Будь дружелюбным, кратким, используй эмодзи 🍓.

Наш каталог:
{catalog_text}

Условия:
- Доставка и самовывоз
- Оплата: наличные и Kaspi Pay
- Время работы: 9:00–21:00
- Минимальный заказ: 1 позиция

Если не знаешь ответа — скажи что передашь вопрос менеджеру.
Никогда не выдумывай цены и факты."""

    response = claude.messages.create(
        model="claude-haiku-4-5-20251001",
        max_tokens=400,
        system=system,
        messages=[{"role": "user", "content": question}]
    )
    return response.content[0].text

# ─── ОПРЕДЕЛЕНИЕ ЯЗЫКА ──────────────────────────────────────────
# ─── ОПРЕДЕЛЕНИЕ ЯЗЫКА ──────────────────────────────────────────
def detect_lang(text):
    """
    Определяет язык по символам и ключевым словам.
    Возвращает 'kz' если казахский, иначе 'ru'.
    """
    text_lower = text.lower()

    # Явные казахские символы — однозначно KZ
    kz_chars = set("әіңғүұқөһ")
    if any(c in kz_chars for c in text_lower):
        return "kz"

    # Явные русские символы (ё, ъ, ы в начале слова) — скорее RU
    ru_specific = set("ёъ")
    if any(c in ru_specific for c in text_lower):
        return "ru"

    # Ключевые слова-маркеры
    kz_words = {"сәлем", "рахмет", "иә", "жоқ", "қалай", "бар", "жақсы",
                "тапсырыс", "каталог", "баға", "алу", "беру"}
    ru_words = {"привет", "спасибо", "да", "нет", "как", "есть", "хорошо",
                "заказ", "каталог", "цена", "купить", "доставка"}

    words = set(text_lower.split())
    kz_hits = len(words & kz_words)
    ru_hits = len(words & ru_words)

    if kz_hits > ru_hits:
        return "kz"
    if ru_hits > kz_hits:
        return "ru"

    # Если не определили — оставляем текущий язык сессии (не меняем)
    return None


# ─── ОСНОВНАЯ ЛОГИКА ДИАЛОГА ────────────────────────────────────
def handle_message(phone, text=None, button_id=None):
    session = get_session(phone)
    state   = session["state"]
    lang    = session.get("lang", "ru")

    # Определяем язык только по тексту, и только если определилось однозначно
    if text:
        detected = detect_lang(text)
        if detected is not None:          # ← не перезаписываем если None
            session["lang"] = detected
            lang = detected

    # ... остальной код handle_message без изменений

    # Обработка кнопок
    if button_id:
        if button_id == "main_menu":
            send_main_menu(phone, lang)
            return
        if button_id == "catalog":
            send_catalog(phone, lang)
            return
        if button_id == "manager":
            if lang == "ru":
                send_text(phone, "👨‍💼 Менеджер свяжется с вами в ближайшее время!\n📞 Или напишите напрямую: wa.me/77XXXXXXXXX")
            else:
                send_text(phone, "👨‍💼 Менеджер жақын арада сізбен байланысады!\n📞 Немесе тікелей жазыңыз: wa.me/77XXXXXXXXX")
            notify_manager(phone, {"product": "Запрос менеджера", "name": "—", "phone": phone, "delivery": "—", "payment": "—"})
            return
        if button_id.startswith("cat_"):
            item_id = int(button_id.replace("cat_", ""))
            send_item_detail(phone, item_id, lang)
            return
        if button_id.startswith("buy_"):
            item_id = int(button_id.replace("buy_", ""))
            start_order(phone, lang, item_id)
            return
        if button_id == "order":
            start_order(phone, lang)
            return
        if button_id == "delivery":
            session["order"]["delivery"] = "Доставка" if lang == "ru" else "Жеткізу"
            if lang == "ru":
                send_text(phone, "📍 Укажите адрес доставки:")
            else:
                send_text(phone, "📍 Жеткізу мекенжайын көрсетіңіз:")
            set_state(phone, "order_address")
            return
        if button_id == "pickup":
            session["order"]["delivery"] = "Самовывоз" if lang == "ru" else "Өзі алу"
            ask_payment(phone, lang)
            return
        if button_id == "pay_cash":
            session["order"]["payment"] = "Наличные" if lang == "ru" else "Қолма-қол"
            confirm_order(phone, lang)
            return
        if button_id == "pay_kaspi":
            session["order"]["payment"] = "Kaspi Pay"
            confirm_order(phone, lang)
            return
        if button_id == "confirm_yes":
            finalize_order(phone, lang)
            return
        if button_id == "confirm_no":
            session["order"] = {}
            send_main_menu(phone, lang)
            return

    # Обработка текста по состоянию
    if text:
        greetings = ["привет", "сәлем", "hi", "hello", "start", "/start", "начать"]
        if text.lower() in greetings or state == "start":
            send_main_menu(phone, lang)
            return

        if state == "order_name":
            session["order"]["name"] = text
            session["order"]["phone"] = phone
            if lang == "ru":
                send_text(phone, f"Приятно познакомиться, {text}! 😊\n\nКакой товар хотите заказать? (напишите название или нажмите /catalog)")
            else:
                send_text(phone, f"Танысқаныма қуаныштымын, {text}! 😊\n\nҚандай тауар тапсырғыңыз келеді?")
            set_state(phone, "order_product")
            return

        if state == "order_product":
            session["order"]["product"] = text
            ask_delivery(phone, lang)
            return

        if state == "order_address":
            session["order"]["address"] = text
            ask_payment(phone, lang)
            return

        # Если не попали в сценарий — отвечает AI
        ai_reply = get_ai_response(text, lang)
        send_text(phone, ai_reply)

        # После AI ответа предлагаем меню
        if lang == "ru":
            send_buttons(phone, "Могу ещё чем-то помочь?", [
                {"id": "catalog", "title": "📦 Каталог"},
                {"id": "order",   "title": "🛒 Заказать"},
                {"id": "manager", "title": "👨‍💼 Менеджер"},
            ])
        else:
            send_buttons(phone, "Басқа бірдеңемен көмектесе аламын ба?", [
                {"id": "catalog", "title": "📦 Каталог"},
                {"id": "order",   "title": "🛒 Тапсырыс"},
                {"id": "manager", "title": "👨‍💼 Менеджер"},
            ])

# ─── WEBHOOK ENDPOINTS ──────────────────────────────────────────
@app.route("/webhook", methods=["GET"])
def verify():
    if request.args.get("hub.verify_token") == VERIFY_TOKEN:
        return request.args.get("hub.challenge")
    return "Forbidden", 403

@app.route("/webhook", methods=["POST"])
def webhook():
    data = request.json
    try:
        value = data["entry"][0]["changes"][0]["value"]

        if "messages" not in value:
            return jsonify({"status": "ok"})

        msg   = value["messages"][0]
        phone = normalize_phone(msg["from"])
        print(f"Incoming phone: {phone}")

        # Текстовое сообщение
        if msg["type"] == "text":
            handle_message(phone, text=msg["text"]["body"])

        # Нажатие кнопки или выбор из списка
        elif msg["type"] == "interactive":
            itype = msg["interactive"]["type"]
            if itype == "button_reply":
                btn_id = msg["interactive"]["button_reply"]["id"]
                handle_message(phone, button_id=btn_id)
            elif itype == "list_reply":
                list_id = msg["interactive"]["list_reply"]["id"]
                handle_message(phone, button_id=list_id)

    except (KeyError, IndexError) as e:
        print(f"Webhook error: {e}")

    return jsonify({"status": "ok"})

@app.route("/", methods=["GET"])
def health():
    return "🍓 Strawberry Bot is running!"

if __name__ == "__main__":
    app.run(host="0.0.0.0", port=5000, debug=False)
