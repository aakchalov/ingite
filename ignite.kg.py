import logging
import re
from telegram import InlineKeyboardButton, InlineKeyboardMarkup, Update
from telegram.ext import (
    Application, CommandHandler, CallbackQueryHandler,
    MessageHandler, ContextTypes, filters
)

# 🔐 Токен и ID группы
BOT_TOKEN = "7452262699:AAFbZZYaWW3eBNgAEVKyLgCjphPgrLJNWAs"
GROUP_CHAT_ID = -1002616109064

# 🛍 Каталог товаров
products = {
    "Blubery ice - Черника со льдом": {"price": 1300, "desc": "никотин: 5% \n Затяжек: 5000"},
    "Blue Raspberry ice - Голубая малина": {"price": 1300, "desc": "никотин: 5% \n Затяжек: 5000"},
    "Green Apple - Зеленая яблоко": {"price": 1300, "desc": "никотин: 5% \n Затяжек: 5000"},
    "Mixed Berries - Ягодный Микс": {"price": 1300, "desc": "никотин: 5% \n Затяжек: 5000"},
    "Menthol - Ментол мята": {"price": 1300, "desc": "никотин: 5% \n Затяжек: 5000"},
    "Strawberry banana - Клубника Банан": {"price": 1300, "desc": "никотин: 5% \n Затяжек: 5000"},
    "Aloe Grape - Алое Виноград": {"price": 1300, "desc": "никотин: 5% \n Затяжек: 5000"},
    "Watermelon Mix - Арбузный Микс": {"price": 1300, "desc": "никотин: 5% \n Затяжек: 5000"},
    "Peach Raspberry - Персик малина": {"price": 1300, "desc": "никотин: 5% \n Затяжек: 5000"},
    "Blue Dream": {"price": 1700, "desc": "никотин: 5% \n Затяжек: 5000"}
}

PHONE_REGEX = re.compile(r"^\+?\d{9,15}$")
logging.basicConfig(level=logging.INFO)

# /start — с кнопкой "Начать заказ"
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    context.user_data.clear()
    context.user_data["cart"] = {}
    keyboard = [[InlineKeyboardButton("🛍 Начать заказ", callback_data="restart")]]
    markup = InlineKeyboardMarkup(keyboard)

    if update.message:
        await update.message.reply_text(
            "👋 Добро пожаловать!\nНажмите кнопку ниже, чтобы начать оформление заказа:",
            reply_markup=markup
        )
    elif update.callback_query:
        await update.callback_query.edit_message_text(
            "👋 Добро пожаловать!\nНажмите кнопку ниже, чтобы начать оформление заказа:",
            reply_markup=markup
        )

# Показать список товаров
async def show_product_list(reply_func):
    keyboard = [
        [InlineKeyboardButton(name, callback_data=f"select:{name}")]
        for name in products
    ]
    keyboard.append([InlineKeyboardButton("✅ Завершить выбор", callback_data="done")])
    markup = InlineKeyboardMarkup(keyboard)
    await reply_func(
        "🛍 Выберите товары (по одному), затем нажмите '✅ Завершить выбор':",
        reply_markup=markup
    )

# Выбор товара → бот спрашивает количество
async def select_product(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    product = query.data.split("select:")[1]
    context.user_data["current_product"] = product

    keyboard = [
        [InlineKeyboardButton(f"{i} шт", callback_data=f"qty:{i}")]
        for i in range(1, 6)
    ]
    keyboard.append([InlineKeyboardButton("⬅️ Назад", callback_data="back_to_list")])
    markup = InlineKeyboardMarkup(keyboard)
    await query.edit_message_text(
        f"📦 {product}\n📝 {products[product]['desc']}\n💰 {products[product]['price']} сом\n\nВыберите количество:",
        reply_markup=markup
    )

# Назад к списку товаров
async def back_to_list(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    await show_product_list(query.edit_message_text)

# Добавление в корзину
async def quantity_selected(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    qty = int(query.data.split("qty:")[1])
    product = context.user_data["current_product"]

    cart = context.user_data.get("cart", {})
    cart[product] = qty
    context.user_data["cart"] = cart
    context.user_data.pop("current_product", None)

    await show_product_list(query.edit_message_text)

# Завершение выбора → запрос телефона
async def done_selection(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()

    if not context.user_data.get("cart"):
        await query.edit_message_text("❌ Вы не выбрали ни одного товара.")
        return

    context.user_data["awaiting_phone"] = True
    await query.edit_message_text("📞 Введите ваш номер телефона:")

# Обработка телефона и адреса
async def text_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    text = update.message.text.strip()

    if context.user_data.get("awaiting_phone"):
        if not PHONE_REGEX.match(text):
            await update.message.reply_text("❌ Неверный номер. Пример: +996XXXXXXXXX")
            return
        context.user_data["phone"] = text
        context.user_data["awaiting_phone"] = False
        context.user_data["awaiting_address"] = True
        await update.message.reply_text("📍 Введите адрес доставки: \n \n P.S. Доставка платная, зависит от Трафика Яндекс🚕")
        return

    elif context.user_data.get("awaiting_address"):
        context.user_data["address"] = text
        context.user_data["awaiting_address"] = False
        await confirm_order(update, context)
        return

    else:
        await update.message.reply_text("⚠️ Сначала начните заказ с кнопки ниже или через /start.")

# Подтверждение заказа пользователем
async def confirm_order(update: Update, context: ContextTypes.DEFAULT_TYPE):
    cart = context.user_data.get("cart", {})
    phone = context.user_data.get("phone")
    address = context.user_data.get("address")

    if not cart:
        await update.message.reply_text("❌ Корзина пуста.")
        return

    order_lines = []
    total = 0
    for product, qty in cart.items():
        price = products[product]["price"]
        line = f"• {product} — {qty} шт × {price} сом = {qty * price} сом"
        order_lines.append(line)
        total += qty * price

    cart_text = "\n".join(order_lines)
    summary = (
        f"📝 Подтвердите ваш заказ:\n\n"
        f"{cart_text}\n"
        f"💰 Общая сумма: {total} сом\n"
        f"📞 Телефон: {phone}\n"
        f"📍 Адрес: {address}"
    )

    keyboard = [[InlineKeyboardButton("✅ Подтвердить заказ", callback_data="final_confirm")]]
    await update.message.reply_text(summary, reply_markup=InlineKeyboardMarkup(keyboard))

# Окончательное подтверждение и отправка в группу
async def final_confirm_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()

    cart = context.user_data.get("cart", {})
    phone = context.user_data.get("phone")
    address = context.user_data.get("address")
    user = update.effective_user

    if not cart or not phone or not address:
        await query.edit_message_text("❌ Не хватает данных для оформления заказа.")
        return

    total = 0
    order_lines = []
    for product, qty in cart.items():
        price = products[product]["price"]
        line = f"• {product} — {qty} шт × {price} сом = {qty * price} сом"
        order_lines.append(line)
        total += qty * price

    order_summary = "\n".join(order_lines)
    msg = (
        f"🆕 Новый заказ!\n"
        f"👤 @{user.username or user.first_name} (ID: {user.id})\n"
        f"{order_summary}\n"
        f"💰 Общая сумма: {total} сом\n"
        f"📞 Телефон: {phone}\n"
        f"📍 Адрес: {address}"
    )
    await context.bot.send_message(chat_id=GROUP_CHAT_ID, text=msg)

    await query.edit_message_text("✅ Ваш заказ отправлен! Скоро мы с вами свяжемся.")

    keyboard = [[InlineKeyboardButton("🛍 Начать новый заказ", callback_data="restart")]]
    await context.bot.send_message(chat_id=query.message.chat.id, text="Хотите сделать новый заказ?", reply_markup=InlineKeyboardMarkup(keyboard))

    context.user_data.clear()

# Перезапуск заказа
async def restart(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    context.user_data.clear()
    context.user_data["cart"] = {}
    await show_product_list(query.edit_message_text)

# Запуск бота
def main():
    app = Application.builder().token(BOT_TOKEN).build()

    app.add_handler(CommandHandler("start", start))
    app.add_handler(CallbackQueryHandler(select_product, pattern="^select:"))
    app.add_handler(CallbackQueryHandler(quantity_selected, pattern="^qty:"))
    app.add_handler(CallbackQueryHandler(back_to_list, pattern="^back_to_list$"))
    app.add_handler(CallbackQueryHandler(done_selection, pattern="^done$"))
    app.add_handler(CallbackQueryHandler(final_confirm_handler, pattern="^final_confirm$"))
    app.add_handler(CallbackQueryHandler(restart, pattern="^restart$"))
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, text_handler))

    print("🤖 Бот запущен.")
    app.run_polling()

if __name__ == "__main__":
    main()
