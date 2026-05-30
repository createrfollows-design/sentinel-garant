import os
import logging
import sqlite3
from datetime import datetime
from telegram import (
    Update, InlineKeyboardButton, InlineKeyboardMarkup,
    WebAppInfo, MenuButtonWebApp
)
from telegram.ext import (
    Application, CommandHandler, CallbackQueryHandler,
    MessageHandler, filters, ContextTypes, ConversationHandler
)
from telegram.constants import ParseMode

logging.basicConfig(
    format="%(asctime)s | %(levelname)s | %(message)s",
    level=logging.INFO
)
logger = logging.getLogger(__name__)

BOT_TOKEN = os.environ.get("BOT_TOKEN", "8854032121:AAHpgjOPH0tS5w-VwoT7KUQblNbpo8koTow")
ADMIN_ID = 8514275237
ADMIN_USERNAME = "@SentinelGarant"
SUPPORT_USERNAME = "@Sentinelsup"
CHANNEL_LINK = "https://t.me/SentinelGarantGroup"
MINI_APP_URL = os.environ.get("MINI_APP_URL", "https://createrfollows-design.github.io/sentinel-garant/")
COMMISSION = 0

DB_PATH = "sentinel.db"

AWAIT_NFT_LINK = 1
AWAIT_STARS_AMOUNT = 2
AWAIT_BUYER = 3

def init_db():
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()
    c.execute("""
        CREATE TABLE IF NOT EXISTS deals (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            seller_id INTEGER,
            seller_username TEXT,
            buyer_id INTEGER,
            buyer_username TEXT,
            nft_link TEXT,
            stars_amount INTEGER,
            status TEXT DEFAULT 'pending',
            created_at TEXT,
            completed_at TEXT
        )
    """)
    conn.commit()
    conn.close()

def db():
    return sqlite3.connect(DB_PATH)

def fmt_deal_status(status: str) -> str:
    icons = {
        "pending": "🟡 Ожидание",
        "nft_sent": "🔵 NFT получен",
        "stars_sent": "🟣 Stars получены",
        "completed": "✅ Завершена",
        "cancelled": "❌ Отменена",
    }
    return icons.get(status, status)

def main_keyboard(user_id: int):
    buttons = [
        [InlineKeyboardButton("✨ Новая сделка", callback_data="new_deal"),
         InlineKeyboardButton("📋 Мои сделки", callback_data="my_deals")],
        [InlineKeyboardButton("ℹ️ Как это работает", callback_data="how_it_works"),
         InlineKeyboardButton("💬 Поддержка", url=f"https://t.me/{SUPPORT_USERNAME.lstrip('@')}")],
        [InlineKeyboardButton("🌐 Открыть Mini App", web_app=WebAppInfo(url=MINI_APP_URL))],
        [InlineKeyboardButton("📢 Наш канал", url=CHANNEL_LINK)],
    ]
    if user_id == ADMIN_ID:
        buttons.append([InlineKeyboardButton("⚙️ Панель администратора", callback_data="admin_panel")])
    return InlineKeyboardMarkup(buttons)

WELCOME_TEXT = """
╔══════════════════════════════╗
║   🛡️  SENTINEL GARANT        ║
║   Гарант-сервис №1           ║
╚══════════════════════════════╝

Добро пожаловать в <b>Sentinel Garant</b> — ваш надёжный посредник для безопасного обмена NFT-подарками и Telegram Stars.

<b>Почему нам доверяют:</b>
▸ Комиссия <b>0%</b> — платите только за саму сделку
▸ Ручная верификация каждой транзакции
▸ Прозрачная история всех операций
▸ Моментальная поддержка 24/7

<b>Гарант:</b> {admin} · <b>Канал:</b> <a href="{channel}">SentinelGarantGroup</a>

Выберите действие 👇
""".format(admin=ADMIN_USERNAME, channel=CHANNEL_LINK)

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = update.effective_user
    await update.message.reply_text(
        WELCOME_TEXT,
        parse_mode=ParseMode.HTML,
        reply_markup=main_keyboard(user.id),
        disable_web_page_preview=True
    )

async def button_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    user = query.from_user
    data = query.data

    if data == "new_deal":
        await query.message.edit_text(
            "🛡️ <b>Создание новой сделки</b>\n\n"
            "Вы выступаете как <b>продавец</b>.\n\n"
            "📎 Отправьте ссылку на ваш NFT-подарок или его описание.\n"
            "<i>Пример: https://t.me/nft/...</i>",
            parse_mode=ParseMode.HTML,
            reply_markup=InlineKeyboardMarkup([[
                InlineKeyboardButton("❌ Отмена", callback_data="cancel")
            ]])
        )
        return AWAIT_NFT_LINK

    elif data == "my_deals":
        conn = db()
        c = conn.cursor()
        c.execute("""
            SELECT id, status, nft_link, stars_amount, created_at, buyer_username, seller_username
            FROM deals
            WHERE seller_id=? OR buyer_id=?
            ORDER BY id DESC LIMIT 10
        """, (user.id, user.id))
        rows = c.fetchall()
        conn.close()

        if not rows:
            text = (
                "📋 <b>Мои сделки</b>\n\n"
                "У вас пока нет сделок.\n"
                "Нажмите <b>«✨ Новая сделка»</b> чтобы начать."
            )
        else:
            text = "📋 <b>Мои сделки</b> (последние 10)\n\n"
            for row in rows:
                deal_id, status, nft_link, stars, created, buyer_un, seller_un = row
                role = "Продавец" if seller_un and seller_un == (user.username or "") else "Покупатель"
                text += (
                    f"<b>#{deal_id}</b> · {fmt_deal_status(status)}\n"
                    f"├ Роль: {role}\n"
                    f"├ NFT: <code>{(nft_link or '—')[:40]}</code>\n"
                    f"├ Stars: {stars or '—'}\n"
                    f"└ Дата: {created or '—'}\n\n"
                )

        await query.message.edit_text(
            text, parse_mode=ParseMode.HTML,
            reply_markup=InlineKeyboardMarkup([[
                InlineKeyboardButton("🔙 Назад", callback_data="back_main")
            ]])
        )

    elif data == "how_it_works":
        text = (
            "📖 <b>Как работает Sentinel Garant</b>\n\n"
            "<b>Схема сделки:</b>\n\n"
            "1️⃣ <b>Продавец</b> создаёт сделку в боте и передаёт NFT-подарок гаранту "
            f"({ADMIN_USERNAME} · ID: <code>{ADMIN_ID}</code>)\n\n"
            "2️⃣ <b>Покупатель</b> отправляет Stars гаранту в указанном количестве\n\n"
            "3️⃣ <b>Гарант</b> проверяет обе стороны и:\n"
            "   ▸ Переводит NFT покупателю\n"
            "   ▸ Переводит Stars продавцу\n\n"
            "4️⃣ Сделка закрыта. Комиссия <b>0%</b>.\n\n"
            "━━━━━━━━━━━━━━━━━━━━━━\n"
            "🔒 <b>Безопасность:</b>\n"
            "▸ Гарант — реальный человек, не бот\n"
            "▸ Все сделки логируются\n"
            "▸ Спорные ситуации решаются вручную\n\n"
            f"❓ Вопросы: {SUPPORT_USERNAME}"
        )
        await query.message.edit_text(
            text, parse_mode=ParseMode.HTML,
            reply_markup=InlineKeyboardMarkup([[
                InlineKeyboardButton("🔙 Назад", callback_data="back_main")
            ]])
        )

    elif data == "back_main":
        await query.message.edit_text(
            WELCOME_TEXT, parse_mode=ParseMode.HTML,
            reply_markup=main_keyboard(user.id),
            disable_web_page_preview=True
        )

    elif data == "cancel":
        await query.message.edit_text(
            "❌ Действие отменено.",
            reply_markup=InlineKeyboardMarkup([[
                InlineKeyboardButton("🔙 На главную", callback_data="back_main")
            ]])
        )
        return ConversationHandler.END

    elif data == "admin_panel" and user.id == ADMIN_ID:
        conn = db()
        c = conn.cursor()
        c.execute("SELECT COUNT(*) FROM deals WHERE status='pending'")
        pending = c.fetchone()[0]
        c.execute("SELECT COUNT(*) FROM deals WHERE status='completed'")
        completed = c.fetchone()[0]
        c.execute("SELECT COUNT(*) FROM deals")
        total = c.fetchone()[0]
        conn.close()

        text = (
            "⚙️ <b>Панель администратора</b>\n\n"
            f"📊 Всего сделок: <b>{total}</b>\n"
            f"🟡 Ожидают: <b>{pending}</b>\n"
            f"✅ Завершено: <b>{completed}</b>\n"
        )
        await query.message.edit_text(
            text, parse_mode=ParseMode.HTML,
            reply_markup=InlineKeyboardMarkup([
                [InlineKeyboardButton("📋 Активные сделки", callback_data="admin_active")],
                [InlineKeyboardButton("🔙 Назад", callback_data="back_main")]
            ])
        )

    elif data == "admin_active" and user.id == ADMIN_ID:
        conn = db()
        c = conn.cursor()
        c.execute("""
            SELECT id, seller_username, buyer_username, nft_link, stars_amount, status, created_at
            FROM deals WHERE status NOT IN ('completed','cancelled')
            ORDER BY id DESC LIMIT 20
        """)
        rows = c.fetchall()
        conn.close()

        if not rows:
            text = "⚙️ <b>Активные сделки</b>\n\nНет активных сделок."
        else:
            text = "⚙️ <b>Активные сделки</b>\n\n"
            for row in rows:
                did, seller, buyer, nft, stars, status, created = row
                text += (
                    f"<b>#{did}</b> {fmt_deal_status(status)}\n"
                    f"├ Продавец: {seller or '—'}\n"
                    f"├ Покупатель: {buyer or '—'}\n"
                    f"├ NFT: <code>{(nft or '—')[:35]}</code>\n"
                    f"├ Stars: {stars or '—'}\n"
                    f"└ {created or '—'}\n\n"
                )

        keyboard = []
        for row in rows:
            did = row[0]
            keyboard.append([
                InlineKeyboardButton(f"✅ Завершить #{did}", callback_data=f"complete_{did}"),
                InlineKeyboardButton(f"❌ Отменить #{did}", callback_data=f"cancel_deal_{did}"),
            ])
        keyboard.append([InlineKeyboardButton("🔙 Назад", callback_data="admin_panel")])

        await query.message.edit_text(
            text, parse_mode=ParseMode.HTML,
            reply_markup=InlineKeyboardMarkup(keyboard)
        )

    elif data.startswith("complete_") and user.id == ADMIN_ID:
        deal_id = int(data.split("_")[1])
        conn = db()
        c = conn.cursor()
        c.execute(
            "UPDATE deals SET status='completed', completed_at=? WHERE id=?",
            (datetime.now().strftime("%Y-%m-%d %H:%M"), deal_id)
        )
        c.execute("SELECT seller_id, buyer_id, nft_link, stars_amount FROM deals WHERE id=?", (deal_id,))
        row = c.fetchone()
        conn.commit()
        conn.close()

        await query.answer(f"✅ Сделка #{deal_id} завершена!", show_alert=True)

        if row:
            seller_id, buyer_id, nft_link, stars = row
            msg = (
                f"✅ <b>Сделка #{deal_id} завершена!</b>\n\n"
                f"NFT передан покупателю, Stars переведены продавцу.\n"
                f"Спасибо за использование Sentinel Garant! 🛡️"
            )
            try:
                await context.bot.send_message(seller_id, msg, parse_mode=ParseMode.HTML)
            except Exception:
                pass
            try:
                await context.bot.send_message(buyer_id, msg, parse_mode=ParseMode.HTML)
            except Exception:
                pass

        await query.message.edit_text(
            f"✅ Сделка <b>#{deal_id}</b> успешно завершена.",
            parse_mode=ParseMode.HTML,
            reply_markup=InlineKeyboardMarkup([[
                InlineKeyboardButton("🔙 К активным", callback_data="admin_active")
            ]])
        )

    elif data.startswith("cancel_deal_") and user.id == ADMIN_ID:
        deal_id = int(data.split("_")[2])
        conn = db()
        c = conn.cursor()
        c.execute("UPDATE deals SET status='cancelled' WHERE id=?", (deal_id,))
        conn.commit()
        conn.close()
        await query.answer(f"❌ Сделка #{deal_id} отменена.", show_alert=True)

async def receive_nft_link(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = update.effective_user
    nft_link = update.message.text.strip()
    context.user_data["nft_link"] = nft_link

    await update.message.reply_text(
        f"✅ <b>NFT получен:</b>\n<code>{nft_link[:100]}</code>\n\n"
        "💫 Теперь укажите количество <b>Telegram Stars</b>, которые вы хотите получить за этот NFT.\n"
        "<i>Только число, например: 500</i>",
        parse_mode=ParseMode.HTML,
        reply_markup=InlineKeyboardMarkup([[
            InlineKeyboardButton("❌ Отмена", callback_data="cancel")
        ]])
    )
    return AWAIT_STARS_AMOUNT

async def receive_stars_amount(update: Update, context: ContextTypes.DEFAULT_TYPE):
    text = update.message.text.strip()
    if not text.isdigit() or int(text) <= 0:
        await update.message.reply_text(
            "⚠️ Введите корректное число Stars (например: <b>500</b>)",
            parse_mode=ParseMode.HTML
        )
        return AWAIT_STARS_AMOUNT

    context.user_data["stars_amount"] = int(text)

    await update.message.reply_text(
        f"👤 Укажите <b>@username покупателя</b> (если уже договорились) "
        f"или отправьте <b>«нет»</b> чтобы оставить открытым.\n\n"
        f"<i>Покупатель сможет присоединиться позже.</i>",
        parse_mode=ParseMode.HTML,
        reply_markup=InlineKeyboardMarkup([[
            InlineKeyboardButton("❌ Отмена", callback_data="cancel")
        ]])
    )
    return AWAIT_BUYER

async def receive_buyer(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = update.effective_user
    buyer_text = update.message.text.strip()
    buyer_username = None if buyer_text.lower() in ("нет", "no", "-") else buyer_text.lstrip("@")

    nft_link = context.user_data.get("nft_link", "")
    stars_amount = context.user_data.get("stars_amount", 0)

    conn = db()
    c = conn.cursor()
    c.execute("""
        INSERT INTO deals (seller_id, seller_username, buyer_username, nft_link, stars_amount, status, created_at)
        VALUES (?, ?, ?, ?, ?, 'pending', ?)
    """, (
        user.id,
        f"@{user.username}" if user.username else str(user.id),
        f"@{buyer_username}" if buyer_username else None,
        nft_link,
        stars_amount,
        datetime.now().strftime("%Y-%m-%d %H:%M")
    ))
    deal_id = c.lastrowid
    conn.commit()
    conn.close()

    seller_tag = f"@{user.username}" if user.username else f"ID:{user.id}"

    confirm_text = (
        f"🎉 <b>Сделка #{deal_id} создана!</b>\n\n"
        f"━━━━━━━━━━━━━━━━━━━━━\n"
        f"📦 NFT: <code>{nft_link[:80]}</code>\n"
        f"💫 Цена: <b>{stars_amount} Stars</b>\n"
        f"👤 Покупатель: {('@' + buyer_username) if buyer_username else 'открытая сделка'}\n"
        f"━━━━━━━━━━━━━━━━━━━━━\n\n"
        f"<b>Следующий шаг:</b>\n"
        f"Отправьте ваш NFT-подарок гаранту:\n"
        f"👤 {ADMIN_USERNAME} · ID: <code>{ADMIN_ID}</code>\n\n"
        f"После этого покупатель отправит Stars гаранту, и сделка будет завершена.\n\n"
        f"<i>Номер сделки #{deal_id} — сохраните его.</i>"
    )

    await update.message.reply_text(
        confirm_text, parse_mode=ParseMode.HTML,
        reply_markup=main_keyboard(user.id)
    )

    admin_notify = (
        f"🔔 <b>Новая сделка #{deal_id}</b>\n\n"
        f"👤 Продавец: {seller_tag} (ID: <code>{user.id}</code>)\n"
        f"📦 NFT: <code>{nft_link[:100]}</code>\n"
        f"💫 Сумма: <b>{stars_amount} Stars</b>\n"
        f"👥 Покупатель: {('@' + buyer_username) if buyer_username else 'не указан'}\n"
        f"📅 {datetime.now().strftime('%Y-%m-%d %H:%M')}"
    )
    try:
        await context.bot.send_message(ADMIN_ID, admin_notify, parse_mode=ParseMode.HTML)
    except Exception as e:
        logger.warning(f"Не удалось уведомить админа: {e}")

    return ConversationHandler.END

async def cancel_conv(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text(
        "❌ Отменено.",
        reply_markup=main_keyboard(update.effective_user.id)
    )
    return ConversationHandler.END

async def post_init(application: Application):
    await application.bot.set_my_commands([
        ("start", "🛡️ Главное меню"),
        ("deals", "📋 Мои сделки"),
        ("new", "✨ Новая сделка"),
        ("help", "ℹ️ Помощь"),
    ])
    await application.bot.set_chat_menu_button(
        menu_button=MenuButtonWebApp(text="🌐 Открыть App", web_app=WebAppInfo(url=MINI_APP_URL))
    )

def main():
    init_db()

    app = Application.builder().token(BOT_TOKEN).post_init(post_init).build()

    conv = ConversationHandler(
        entry_points=[CallbackQueryHandler(button_handler, pattern="^new_deal$")],
        states={
            AWAIT_NFT_LINK: [MessageHandler(filters.TEXT & ~filters.COMMAND, receive_nft_link)],
            AWAIT_STARS_AMOUNT: [MessageHandler(filters.TEXT & ~filters.COMMAND, receive_stars_amount)],
            AWAIT_BUYER: [MessageHandler(filters.TEXT & ~filters.COMMAND, receive_buyer)],
        },
        fallbacks=[
            CallbackQueryHandler(button_handler, pattern="^cancel$"),
            CommandHandler("start", start),
        ],
        per_message=False,
    )

    app.add_handler(CommandHandler("start", start))
    app.add_handler(CommandHandler("deals", lambda u, c: button_handler(
        type("Q", (), {"callback_query": type("CQ", (), {
            "from_user": u.effective_user,
            "message": u.message,
            "data": "my_deals",
            "answer": lambda **kw: None
        })(), "effective_user": u.effective_user})(), c
    )))
    app.add_handler(conv)
    app.add_handler(CallbackQueryHandler(button_handler))

    logger.info("🛡️ Sentinel Garant запущен")
    app.run_polling(drop_pending_updates=True)

if __name__ == "__main__":
    main()
