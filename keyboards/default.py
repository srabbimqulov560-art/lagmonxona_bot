from aiogram.types import ReplyKeyboardMarkup, KeyboardButton

def get_main_menu_kb(language: str) -> ReplyKeyboardMarkup:
    if language == "uz":
        kb = ReplyKeyboardMarkup(
            keyboard=[
                [KeyboardButton(text="🛒 Menyu")],
                [KeyboardButton(text="🛍 Savat"), KeyboardButton(text="📋 Buyurtmalarim")],
                [KeyboardButton(text="⚙️ Sozlamalar")]
            ],
            resize_keyboard=True
        )
    else:
        kb = ReplyKeyboardMarkup(
            keyboard=[
                [KeyboardButton(text="🛒 Меню")],
                [KeyboardButton(text="🛍 Корзина"), KeyboardButton(text="📋 Мои заказы")],
                [KeyboardButton(text="⚙️ Настройки")]
            ],
            resize_keyboard=True
        )
    return kb