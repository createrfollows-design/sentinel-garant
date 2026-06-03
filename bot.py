import os
import logging
import sqlite3
import random
import string
from datetime import datetime
from urllib.parse import urlencode
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup, WebAppInfo
from telegram.ext import (
    Application, CommandHandler, CallbackQueryHandler,
    MessageHandler, filters, ContextTypes, ConversationHandler
)

# ═══════════════════════════════════════════════════════
#  CONFIG
# ═══════════════════════════════════════════════════════
BOT_TOKEN    = os.environ.get("BOT_TOKEN", "")
ADMIN_ID     = int(os.environ.get("ADMIN_ID", "8514275237"))
SUPPORT_USER = "SentinelGarant"
BOT_USERNAME = "SentinelGarantBot"
GROUP_URL    = "https://t.me/SentinelGarantGroup"
WEBAPP_URL   = "https://createrfollows-design.github.io/sentinel-garant/"
COMMISSION   = 25
# ═══════════════════════════════════════════════════════

logging.basicConfig(
    format="%(asctime)s - %(levelname)s - %(message)s",
    level=logging.INFO
)

ENTER_NFT, ENTER_PRICE, ENTER_BUYER = range(3)

STATUS_MAP = {
    "pending":    ("⏳", "Ожидает"),
    "nft_sent":   ("📦", "NFT получен"),
    "stars_sent": ("⭐", "Оплачено"),
    "completed":  ("✅", "Завершена"),
    "cancelled":  ("❌", "Отменена"),
    "dispute":    ("⚠️", "Спор"),
}

# ─────────────────── DATABASE ───────────────────────────
def init_db():
    with sqlite3.connect("deals.db") as c:
        c.execute("""
            CREATE TABLE IF NOT EXISTS deals (
                id           TEXT PRIMARY KEY,
                seller_id    INTEGER,
                seller_name  TEXT,
                buyer_name   TEXT,
                nft_link     TEXT,
                nft_name     TEXT,
                price        INTEGER,
                commission   INTEGER DEFAULT 25,
                status       TEXT DEFAULT 'pending',
                created      TEXT,
                updated      TEXT
            )
        """)
        c.execute("""
            CREATE TABLE IF NOT EXISTS users (
                user_id    INTEGER PRIMARY KEY,
                username   TEXT,
                first_name TEXT,
                joined     TEXT
            )
        """)

def register_user(user):
    with sqlite3.connect("deals.db") as c:
        c.execute(
            "INSERT OR IGNORE INTO users VALUES (?,?,?,?)",
            (user.id, user.username or "", user.first_name or "",
             datetime.now().strftime("%d.%m.%Y"))
        )

def save_deal(d):
    with sqlite3.connect("deals.db") as c:
        c.execute(
            "INSERT INTO deals VALUES (?,?,?,?,?,?,?,?,?,?,?)",
            (d["id"], d["seller_id"], d["seller_name"], d["buyer_name"],
             d["nft_link"], d["nft_name"], d["price"], d["commission"],
             d["status"], d["created"], d["created"])
        )

def get_deal(deal_id):
    with sqlite3.connect("deals.db") as c:
        row = c.execute("SELECT * FROM deals WHERE id=?", (deal_id,)).fetchone()
    if not row:
        return None
    keys = ["id","seller_id","seller_name","buyer_name","nft_link",
            "nft_name","price","commission","status","created","updated"]
    return dict(zip(keys, row))

def set_status(deal_id, status):
    """Статус меняется ТОЛЬКО здесь — только через эту функцию."""
    with sqlite3.connect("deals.db") as c:
        c.execute(
            "UPDATE deals SET status=?, updated=? WHERE id=?",
            (status, datetime.now().strftime("%d.%m.%Y %H:%M"), deal_id)
        )

def user_deals(seller_id):
    with sqlite3.connect("deals.db") as c:
        rows = c.execute(
            "SELECT * FROM deals WHERE seller_id=? ORDER BY created DESC LIMIT 10",
            (seller_id,)
        ).fetchall()
    keys = ["id","seller_id","seller_name","buyer_name","nft_link",
            "nft_name","price","commission","status","created","updated"]
    return [dict(zip(keys, r)) for r in rows]

def get_stats():
    with sqlite3.connect("deals.db") as c:
        total  = c.execute("SELECT COUNT(*) FROM deals").fetchone()[0]
        done   = c.execute("SELECT COUNT(*) FROM deals WHERE status='completed'").fetchone()[0]
        users  = c.execute("SELECT COUNT(*) FROM users").fetchone()[0]
        volume = c.execute(
            "SELECT COALESCE(SUM(price),0) FROM deals WHERE status='completed'"
        ).fetchone()[0]
        active = c.execute(
            "SELECT COUNT(*) FROM deals WHERE status NOT IN ('completed','cancelled')"
        ).fetchone()[0]
    return total, done, users, volume, active

def get_active_deals():
    with sqlite3.connect("deals.db") as c:
        rows = c.execute(
            "SELECT * FROM deals WHERE status NOT IN ('completed','cancelled') ORDER BY created DESC"
        ).fetchall()
    keys = ["id","seller_id","seller_name","buyer_name","nft_link",
            "nft_name","price","commission","status","created","updated"]
    return [dict(zip(keys, r)) for r in rows]

def gen_id():
    return "".join(random.choices(string.ascii_uppercase + string.digits, k=8))

def deal_url(deal_id):
    return f"https://t.me/{BOT_USERNAME}?start=deal_{deal_id}"

def webapp_url(d):
    return WEBAPP_URL + "?" + urlencode({
        "id": d["id"], "nft": d["nft_name"], "link": d["nft_link"],
        "price": d["price"], "commission": d["commission"],
        "seller": d["seller_name"], "buyer": d["buyer_name"],
        "status": d["status"], "created": d["created"],
    })

# ─────────────────── KEYBOARDS ──────────────────────────
def main_kb():
    return InlineKeyboardMarkup([
        [InlineKeyboardButton("🤝 Создать сделку",   callback_data="create")],
        [
            InlineKeyboardButton("📋 Мои сделки",    callback_data="mydeals"),
            InlineKeyboardButton("📊 Статистика",    callback_data="stats"),
        ],
        [InlineKeyboardButton("📖 Как это работает", callback_data="howto")],
        [
            InlineKeyboardButton("💬 Поддержка",     callback_data="support"),
            InlineKeyboardButton("👥 Сообщество",    url=GROUP_URL),
        ],
    ])

def back_kb():
    return InlineKeyboardMarkup([
        [InlineKeyboardButton("◀️ Главное меню", callback_data="main")]
    ])

def cancel_kb():
    return InlineKeyboardMarkup([
        [InlineKeyboardButton("✕ Отмена", callback_data="cancel_conv")]
    ])

def deal_view_kb(deal_id, url):
    return InlineKeyboardMarkup([
        [InlineKeyboardButton("🔍 Открыть сделку", web_app=WebAppInfo(url=url))],
        [InlineKeyboardButton("💬 Связаться с гарантом", url=f"https://t.me/{SUPPORT_USER}")],
        [InlineKeyboardButton("◀️ Главное меню", callback_data="main")],
    ])

# ── ADMIN KEYBOARD — только для ADMIN_ID ────────────────
def admin_deal_kb(deal_id):
    return InlineKeyboardMarkup([
        [
            InlineKeyboardButton("📦 NFT получен",    callback_data=f"adm_nft_{deal_id}"),
            InlineKeyboardButton("⭐ Stars получены", callback_data=f"adm_stars_{deal_id}"),
        ],
        [
            InlineKeyboardButton("✅ Завершить сделку", callback_data=f"adm_done_{deal_id}"),
        ],
        [
            InlineKeyboardButton("❌ Отменить",  callback_data=f"adm_cancel_{deal_id}"),
            InlineKeyboardButton("⚠️ Спор",     callback_data=f"adm_dispute_{deal_id}"),
        ],
    ])

def admin_after_kb(deal_id):
    """Кнопки после частичного подтверждения."""
    return InlineKeyboardMarkup([
        [InlineKeyboardButton("✅ Завершить сделку", callback_data=f"adm_done_{deal_id}")],
        [
            InlineKeyboardButton("❌ Отменить", callback_data=f"adm_cancel_{deal_id}"),
            InlineKeyboardButton("⚠️ Спор",    callback_data=f"adm_dispute_{deal_id}"),
        ],
    ])

# ─────────────────── TEXTS ──────────────────────────────
WELCOME = (
    "🛡 *Sentinel Garant*\n"
    "━━━━━━━━━━━━━━━━━━━━\n\n"
    "Профессиональный сервис безопасных\n"
    "сделок с Telegram NFT и Stars.\n\n"
    "▸ Каждая сделка под контролем гаранта\n"
    "▸ Ручное подтверждение каждого этапа\n"
    "▸ Защита обеих сторон\n"
    "▸ Поддержка 24/7\n\n"
    "Выберите действие:"
)

HOWTO_TEXT = (
    "📖 *Как проходит сделка*\n"
    "━━━━━━━━━━━━━━━━━━━━\n\n"
    "*1. Создание сделки*\n"
    "Продавец создаёт сделку через бота, "
    "указывает NFT, цену и покупателя.\n\n"
    "*2. Отправка NFT*\n"
    f"Продавец переводит NFT гаранту @{SUPPORT_USER}.\n\n"
    "*3. Оплата Stars*\n"
    f"Покупатель отправляет Stars + {COMMISSION}⭐ комиссию гаранту @{SUPPORT_USER}.\n\n"
    "*4. Подтверждение гарантом*\n"
    "Гарант вручную проверяет получение "
    "NFT и Stars, затем завершает сделку.\n\n"
    "*5. Завершение*\n"
    "Гарант передаёт NFT покупателю "
    "и Stars продавцу.\n\n"
    f"💰 *Комиссия:* {COMMISSION}⭐ Stars\n"
    "⚠️ *Никогда не переводите средства напрямую!*"
)

# ─────────────────── HANDLERS ───────────────────────────
async def cmd_start(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    register_user(update.effective_user)
    args = ctx.args
    if args and args[0].startswith("deal_"):
        deal = get_deal(args[0][5:])
        if deal:
            icon, label = STATUS_MAP.get(deal["status"], ("❓", deal["status"]))
            url = webapp_url(deal)
            total = deal["price"] + deal["commission"]
            await update.message.reply_text(
                f"🤝 *Сделка #{deal['id']}*\n"
                f"━━━━━━━━━━━━━━━━━━━━\n\n"
                f"🖼 NFT: *{deal['nft_name']}*\n"
                f"⭐ Цена: *{deal['price']} Stars*\n"
                f"💰 Комиссия: *{deal['commission']} Stars*\n"
                f"💎 Итого: *{total} Stars*\n"
                f"👤 Продавец: @{deal['seller_name']}\n"
                f"👤 Покупатель: @{deal['buyer_name']}\n"
                f"📊 Статус: {icon} {label}\n"
                f"📅 {deal['created']}",
                parse_mode="Markdown",
                reply_markup=deal_view_kb(deal["id"], url)
            )
            return
        await update.message.reply_text("❌ Сделка не найдена.")
        return
    await update.message.reply_text(
        WELCOME, parse_mode="Markdown", reply_markup=main_kb()
    )

async def btn_main(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    q = update.callback_query
    await q.answer()
    await q.message.edit_text(WELCOME, parse_mode="Markdown", reply_markup=main_kb())

async def btn_howto(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    q = update.callback_query
    await q.answer()
    await q.message.edit_text(HOWTO_TEXT, parse_mode="Markdown", reply_markup=back_kb())

async def btn_stats(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    q = update.callback_query
    await q.answer()
    total, done, users, volume, active = get_stats()
    rate = f"{round(done/total*100)}%" if total else "—"
    await q.message.edit_text(
        f"📊 *Статистика Sentinel Garant*\n"
        f"━━━━━━━━━━━━━━━━━━━━\n\n"
        f"📋 Всего сделок: *{total}*\n"
        f"🔄 Активных: *{active}*\n"
        f"✅ Завершено: *{done}*\n"
        f"📈 Успешность: *{rate}*\n"
        f"👥 Пользователей: *{users}*\n"
        f"💰 Оборот: *{volume:,} Stars*\n\n"
        f"_Обновлено: {datetime.now().strftime('%d.%m.%Y %H:%M')}_",
        parse_mode="Markdown",
        reply_markup=back_kb()
    )

async def btn_support(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    q = update.callback_query
    await q.answer()
    await q.message.edit_text(
        f"💬 *Поддержка*\n"
        f"━━━━━━━━━━━━━━━━━━━━\n\n"
        f"Обращайтесь к гаранту по любым вопросам:\n\n"
        f"👤 @{SUPPORT_USER}\n\n"
        f"⏱ Время ответа: до 15 минут\n"
        f"🕐 Режим работы: ежедневно",
        parse_mode="Markdown",
        reply_markup=InlineKeyboardMarkup([
            [InlineKeyboardButton("✉️ Написать гаранту", url=f"https://t.me/{SUPPORT_USER}")],
            [InlineKeyboardButton("👥 Сообщество",       url=GROUP_URL)],
            [InlineKeyboardButton("◀️ Главное меню",     callback_data="main")],
        ])
    )

# ── СОЗДАНИЕ СДЕЛКИ ─────────────────────────────────────
async def btn_create(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    q = update.callback_query
    await q.answer()
    await q.message.edit_text(
        "🤝 *Создание сделки — Шаг 1 из 3*\n"
        "━━━━━━━━━━━━━━━━━━━━\n\n"
        "Отправьте ссылку на Telegram NFT:\n\n"
        "Пример:\n`https://t.me/nft/PlushPepe-111`",
        parse_mode="Markdown",
        reply_markup=cancel_kb()
    )
    return ENTER_NFT

async def step_nft(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    text = update.message.text.strip()
    if "t.me/nft/" not in text and "t.me/gifts/" not in text:
        await update.message.reply_text(
            "❌ Некорректная ссылка.\n\nПример: `https://t.me/nft/PlushPepe-111`",
            parse_mode="Markdown", reply_markup=cancel_kb()
        )
        return ENTER_NFT
    name = text.rstrip("/").split("/")[-1]
    ctx.user_data["nft_link"] = text
    ctx.user_data["nft_name"] = name
    await update.message.reply_text(
        f"✅ NFT принят: *{name}*\n\n"
        "🤝 *Шаг 2 из 3 — Цена*\n"
        "━━━━━━━━━━━━━━━━━━━━\n\n"
        "Введите цену в Telegram Stars:\n\n"
        f"_Комиссия гаранта {COMMISSION}⭐ добавляется автоматически_",
        parse_mode="Markdown", reply_markup=cancel_kb()
    )
    return ENTER_PRICE

async def step_price(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    try:
        price = int(update.message.text.strip())
        if price < 1: raise ValueError
    except ValueError:
        await update.message.reply_text(
            "❌ Введите целое число больше нуля.",
            reply_markup=cancel_kb()
        )
        return ENTER_PRICE
    ctx.user_data["price"] = price
    await update.message.reply_text(
        f"✅ Цена: *{price} ⭐*\n\n"
        "🤝 *Шаг 3 из 3 — Покупатель*\n"
        "━━━━━━━━━━━━━━━━━━━━\n\n"
        "Введите username покупателя (без @):",
        parse_mode="Markdown", reply_markup=cancel_kb()
    )
    return ENTER_BUYER

async def step_buyer(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    buyer  = update.message.text.strip().lstrip("@")
    seller = update.effective_user
    sname  = seller.username or str(seller.id)
    total  = ctx.user_data["price"] + COMMISSION

    deal = {
        "id":          gen_id(),
        "seller_id":   seller.id,
        "seller_name": sname,
        "buyer_name":  buyer,
        "nft_link":    ctx.user_data["nft_link"],
        "nft_name":    ctx.user_data["nft_name"],
        "price":       ctx.user_data["price"],
        "commission":  COMMISSION,
        "status":      "pending",
        "created":     datetime.now().strftime("%d.%m.%Y %H:%M"),
    }
    save_deal(deal)
    link = deal_url(deal["id"])
    url  = webapp_url(deal)

    # Продавцу
    await update.message.reply_text(
        f"🎉 *Сделка успешно создана!*\n"
        f"━━━━━━━━━━━━━━━━━━━━\n\n"
        f"🆔 ID: `{deal['id']}`\n"
        f"🖼 NFT: *{deal['nft_name']}*\n"
        f"⭐ Цена: *{deal['price']} Stars*\n"
        f"💰 Комиссия: *{COMMISSION} Stars*\n"
        f"💎 Итого покупателю: *{total} Stars*\n"
        f"👤 Покупатель: @{buyer}\n\n"
        f"📤 *Ссылка для покупателя:*\n`{link}`\n\n"
        f"_Гарант получил уведомление и ожидает активности._",
        parse_mode="Markdown",
        reply_markup=deal_view_kb(deal["id"], url)
    )

    # Гаранту (ADMIN) — панель управления
    try:
        await ctx.bot.send_message(
            ADMIN_ID,
            f"🔔 *НОВАЯ СДЕЛКА*\n"
            f"━━━━━━━━━━━━━━━━━━━━\n\n"
            f"🆔 `{deal['id']}`\n"
            f"🖼 {deal['nft_name']}\n"
            f"🔗 {deal['nft_link']}\n"
            f"⭐ {deal['price']} Stars + {COMMISSION}⭐ комиссия\n"
            f"💎 Итого: {total} Stars\n"
            f"👤 Продавец: @{sname}\n"
            f"👤 Покупатель: @{buyer}\n"
            f"📅 {deal['created']}\n\n"
            f"🔗 {link}\n\n"
            f"_Нажмите кнопки для управления сделкой:_",
            parse_mode="Markdown",
            reply_markup=admin_deal_kb(deal["id"])
        )
    except Exception as e:
        logging.warning(f"Не удалось уведомить гаранта: {e}")

    ctx.user_data.clear()
    return ConversationHandler.END

async def cancel_conv(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    q = update.callback_query
    await q.answer()
    ctx.user_data.clear()
    await q.message.edit_text(WELCOME, parse_mode="Markdown", reply_markup=main_kb())
    return ConversationHandler.END

async def cmd_cancel(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    ctx.user_data.clear()
    await update.message.reply_text("✕ Отменено.", reply_markup=main_kb())
    return ConversationHandler.END

# ── МОИ СДЕЛКИ ──────────────────────────────────────────
async def btn_mydeals(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    q = update.callback_query
    await q.answer()
    deals = user_deals(q.from_user.id)
    if not deals:
        await q.message.edit_text(
            "📋 *Мои сделки*\n━━━━━━━━━━━━━━━━━━━━\n\nУ вас пока нет сделок.",
            parse_mode="Markdown",
            reply_markup=InlineKeyboardMarkup([
                [InlineKeyboardButton("🤝 Создать сделку", callback_data="create")],
                [InlineKeyboardButton("◀️ Главное меню",   callback_data="main")],
            ])
        )
        return
    lines = ["📋 *Ваши сделки:*\n━━━━━━━━━━━━━━━━━━━━\n"]
    for d in deals:
        icon, label = STATUS_MAP.get(d["status"], ("❓", d["status"]))
        lines.append(f"{icon} `#{d['id']}` *{d['nft_name']}*\n   {d['price']}⭐ → @{d['buyer_name']} · {label}\n")
    await q.message.edit_text(
        "\n".join(lines), parse_mode="Markdown", reply_markup=back_kb()
    )

# ── ADMIN CALLBACKS — статус ТОЛЬКО через эти кнопки ────
async def admin_callback(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    q = update.callback_query

    # Строгая проверка — только ADMIN_ID
    if q.from_user.id != ADMIN_ID:
        await q.answer("⛔ Нет доступа", show_alert=True)
        return
    await q.answer()

    parts   = q.data.split("_", 2)   # adm_action_DEALID
    action  = parts[1]
    deal_id = parts[2]
    deal    = get_deal(deal_id)

    if not deal:
        await q.answer("Сделка не найдена", show_alert=True)
        return

    ACTIONS = {
        "nft":     ("nft_sent",   "📦 NFT получен гарантом"),
        "stars":   ("stars_sent", "⭐ Stars получены гарантом"),
        "done":    ("completed",  "✅ Сделка завершена"),
        "cancel":  ("cancelled",  "❌ Сделка отменена"),
        "dispute": ("dispute",    "⚠️ Открыт спор"),
    }

    if action not in ACTIONS:
        return

    status, label = ACTIONS[action]
    set_status(deal_id, status)   # единственное место изменения статуса

    # Обновляем сообщение у гаранта
    kb = admin_after_kb(deal_id) if action in ("nft", "stars") else None
    try:
        await q.message.edit_text(
            q.message.text + f"\n\n*{label}*\n_{datetime.now().strftime('%d.%m.%Y %H:%M')}_",
            parse_mode="Markdown",
            reply_markup=kb
        )
    except Exception:
        pass

    # Уведомляем продавца при завершении
    if action == "done":
        try:
            await ctx.bot.send_message(
                deal["seller_id"],
                f"✅ *Сделка #{deal_id} завершена!*\n\n"
                f"NFT передан покупателю, Stars зачислены вам.\n"
                f"Спасибо что воспользовались Sentinel Garant!",
                parse_mode="Markdown",
                reply_markup=main_kb()
            )
        except Exception:
            pass

    elif action == "cancel":
        try:
            await ctx.bot.send_message(
                deal["seller_id"],
                f"❌ *Сделка #{deal_id} отменена гарантом.*\n\n"
                f"По вопросам обращайтесь: @{SUPPORT_USER}",
                parse_mode="Markdown"
            )
        except Exception:
            pass

    elif action == "dispute":
        try:
            await ctx.bot.send_message(
                deal["seller_id"],
                f"⚠️ *По сделке #{deal_id} открыт спор.*\n\n"
                f"Гарант разберётся в ситуации. Ожидайте.\n"
                f"Связь: @{SUPPORT_USER}",
                parse_mode="Markdown"
            )
        except Exception:
            pass

# ── FORCE CLOSE — принудительное закрытие ───────────────
async def cmd_force_close(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    if update.effective_user.id != ADMIN_ID:
        await update.message.reply_text("⛔ Нет доступа.")
        return

    args = ctx.args
    valid = list(STATUS_MAP.keys())

    if len(args) < 2:
        await update.message.reply_text(
            f"Использование:\n`/force_close DEAL_ID STATUS`\n\n"
            f"Доступные статусы:\n" + "\n".join(f"• `{s}`" for s in valid),
            parse_mode="Markdown"
        )
        return

    deal_id = args[0].upper()
    status  = args[1].lower()

    if status not in valid:
        await update.message.reply_text(
            f"❌ Неверный статус. Доступные:\n" + "\n".join(f"• `{s}`" for s in valid),
            parse_mode="Markdown"
        )
        return

    deal = get_deal(deal_id)
    if not deal:
        await update.message.reply_text(f"❌ Сделка `{deal_id}` не найдена.", parse_mode="Markdown")
        return

    set_status(deal_id, status)
    icon, label = STATUS_MAP[status]

    await update.message.reply_text(
        f"✅ *Сделка #{deal_id} принудительно закрыта*\n\n"
        f"Новый статус: {icon} *{label}*\n"
        f"Время: {datetime.now().strftime('%d.%m.%Y %H:%M')}",
        parse_mode="Markdown"
    )

    # Уведомить продавца
    try:
        await ctx.bot.send_message(
            deal["seller_id"],
            f"📢 *Статус сделки #{deal_id} обновлён гарантом*\n\n"
            f"Статус: {icon} {label}\n\n"
            f"Вопросы: @{SUPPORT_USER}",
            parse_mode="Markdown"
        )
    except Exception:
        pass

# ── ADMIN: список активных сделок ───────────────────────
async def cmd_deals(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    if update.effective_user.id != ADMIN_ID:
        await update.message.reply_text("⛔ Нет доступа.")
        return
    deals = get_active_deals()
    if not deals:
        await update.message.reply_text("Активных сделок нет.")
        return
    lines = ["📋 *Активные сделки:*\n"]
    for d in deals:
        icon, label = STATUS_MAP.get(d["status"], ("❓", d["status"]))
        total = d["price"] + d["commission"]
        lines.append(
            f"{icon} `#{d['id']}` *{d['nft_name']}*\n"
            f"   @{d['seller_name']} → @{d['buyer_name']}\n"
            f"   {total}⭐ · {label}\n"
        )
    await update.message.reply_text(
        "\n".join(lines), parse_mode="Markdown"
    )

# ─────────────────── MAIN ───────────────────────────────
def main():
    init_db()
    app = Application.builder().token(BOT_TOKEN).build()

    conv = ConversationHandler(
        entry_points=[CallbackQueryHandler(btn_create, pattern="^create$")],
        states={
            ENTER_NFT:   [MessageHandler(filters.TEXT & ~filters.COMMAND, step_nft)],
            ENTER_PRICE: [MessageHandler(filters.TEXT & ~filters.COMMAND, step_price)],
            ENTER_BUYER: [MessageHandler(filters.TEXT & ~filters.COMMAND, step_buyer)],
        },
        fallbacks=[
            CommandHandler("cancel", cmd_cancel),
            CallbackQueryHandler(cancel_conv, pattern="^cancel_conv$"),
        ],
        allow_reentry=True,
    )

    app.add_handler(CommandHandler("start",       cmd_start))
    app.add_handler(CommandHandler("force_close", cmd_force_close))
    app.add_handler(CommandHandler("deals",       cmd_deals))
    app.add_handler(conv)
    app.add_handler(CallbackQueryHandler(btn_main,       pattern="^main$"))
    app.add_handler(CallbackQueryHandler(btn_howto,      pattern="^howto$"))
    app.add_handler(CallbackQueryHandler(btn_stats,      pattern="^stats$"))
    app.add_handler(CallbackQueryHandler(btn_support,    pattern="^support$"))
    app.add_handler(CallbackQueryHandler(btn_mydeals,    pattern="^mydeals$"))
    app.add_handler(CallbackQueryHandler(admin_callback, pattern="^adm_"))

    print("✅ Sentinel Garant запущен!")
    app.run_polling(drop_pending_updates=True)

if __name__ == "__main__":
    main()
