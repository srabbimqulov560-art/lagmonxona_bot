from aiogram import Router, F
from aiogram.types import Message, CallbackQuery, InlineKeyboardMarkup, InlineKeyboardButton, ReplyKeyboardMarkup, KeyboardButton
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import StatesGroup, State
from sqlalchemy.future import select
import re
from db.engine import AsyncSessionLocal
from db.models import Order, OrderItem, User
from handlers.ordering import PRODUCTS
from keyboards.default import get_main_menu_kb

router = Router()

# Sozlamalar uchun FSM holati
class SettingsState(StatesGroup):
    new_name = State()
    new_phone = State()

# ==========================================
# ⚙️ SOZLAMALAR BO'LIMI
# ==========================================
@router.message(F.text.in_(["⚙️ Sozlamalar", "⚙️ Настройки"]))
async def show_settings(message: Message):
    settings_kb = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="👤 Ismni o'zgartirish", callback_data="setting_name")],
        [InlineKeyboardButton(text="📞 Raqamni o'zgartirish", callback_data="setting_phone")],
        [InlineKeyboardButton(text="🌐 Tilni o'zgartirish", callback_data="setting_lang")]
    ])
    await message.answer("⚙️ <b>Sozlamalar:</b>\n\nO'zgartirmoqchi bo'lgan ma'lumotingizni tanlang:", reply_markup=settings_kb, parse_mode="HTML")

# 1. ISM O'ZGARTIRISH
@router.callback_query(F.data == "setting_name")
async def ask_new_name(callback: CallbackQuery, state: FSMContext):
    await callback.message.delete()
    await callback.message.answer("📝 Iltimos, yangi ism-familiyangizni kiriting:")
    await state.set_state(SettingsState.new_name)

@router.message(SettingsState.new_name, F.text)
async def save_new_name(message: Message, state: FSMContext):
    async with AsyncSessionLocal() as session:
        user = (await session.execute(select(User).where(User.telegram_id == message.from_user.id))).scalars().first()
        if user:
            user.full_name = message.text
            await session.commit()
            
    await message.answer("✅ Ismingiz muvaffaqiyatli o'zgartirildi!", reply_markup=get_main_menu_kb("uz"))
    await state.clear()

# YANGILANGAN: Sozlamalardan raqam o'zgartirish
@router.callback_query(F.data == "setting_phone")
async def ask_new_phone(callback: CallbackQuery, state: FSMContext):
    await callback.message.delete()
    kb = ReplyKeyboardMarkup(keyboard=[[KeyboardButton(text="📞 Telegram raqamni yuborish", request_contact=True)]], resize_keyboard=True)
    
    text = (
        "📞 <b>Yangi telefon raqamingizni yuboring:</b>\n\n"
        "❗️ <i>Kuryer sizga oson bog'lanishi uchun doimiy ishlaydigan raqam kiriting.</i>\n\n"
        "Pastdagi tugmadan foydalaning yoki raqamni qo'lda yozing (Masalan: +998901234567)."
    )
    await callback.message.answer(text, reply_markup=kb, parse_mode="HTML")
    await state.set_state(SettingsState.new_phone)

@router.message(SettingsState.new_phone)
async def save_new_phone(message: Message, state: FSMContext):
    if message.contact:
        phone_number = message.contact.phone_number
        if not phone_number.startswith('+'):
            phone_number = '+' + phone_number
    elif message.text:
        clean_phone = re.sub(r'\D', '', message.text)
        
        if len(clean_phone) == 9:
            phone_number = f"+998{clean_phone}"
        elif len(clean_phone) == 12 and clean_phone.startswith("998"):
            phone_number = f"+{clean_phone}"
        else:
            await message.answer("⚠️ Iltimos, to'g'ri telefon raqamini kiriting.\n(Masalan: <b>93 123 45 67</b> yoki <b>+998931234567</b>)", parse_mode="HTML")
            return
    else:
        await message.answer("⚠️ Iltimos, raqamingizni yuboring.")
        return

    async with AsyncSessionLocal() as session:
        user = (await session.execute(select(User).where(User.telegram_id == message.from_user.id))).scalars().first()
        if user:
            user.phone_number = phone_number
            await session.commit()
            
    await message.answer(f"✅ Raqamingiz muvaffaqiyatli <b>{phone_number}</b> ga o'zgartirildi!", reply_markup=get_main_menu_kb("uz"), parse_mode="HTML")
    await state.clear()

# 3. TIL O'ZGARTIRISH
@router.callback_query(F.data == "setting_lang")
async def ask_new_lang(callback: CallbackQuery):
    kb = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="🇺🇿 O'zbekcha", callback_data="setlang_uz")],
        [InlineKeyboardButton(text="🇷🇺 Русский", callback_data="setlang_ru")]
    ])
    await callback.message.edit_text("🌐 O'zingizga qulay tilni tanlang:", reply_markup=kb)

@router.callback_query(F.data.startswith("setlang_"))
async def save_new_lang(callback: CallbackQuery):
    lang = callback.data.split("_")[1]
    async with AsyncSessionLocal() as session:
        user = (await session.execute(select(User).where(User.telegram_id == callback.from_user.id))).scalars().first()
        if user:
            user.language = lang
            await session.commit()
            
    text = "✅ Til o'zgartirildi!" if lang == "uz" else "✅ Язык успешно изменен!"
    await callback.message.delete()
    await callback.message.answer(text, reply_markup=get_main_menu_kb(lang))


# ==========================================
# 📋 BUYURTMALARIM BO'LIMI (O'zgarishsiz qoladi)
# ==========================================
@router.message(F.text.in_(["📋 Buyurtmalarim", "📋 Мои заказы"]))
async def show_orders(message: Message):
    telegram_id = message.from_user.id
    async with AsyncSessionLocal() as session:
        orders = (await session.execute(select(Order).where(Order.telegram_id == telegram_id).order_by(Order.created_at.desc()).limit(5))).scalars().all()
        if not orders:
            await message.answer("Sizda hozircha buyurtmalar yo'q 🤷‍♂️")
            return
            
        await message.answer("📋 <b>Sizning oxirgi buyurtmalaringiz:</b>", parse_mode="HTML")
        for order in orders:
            items = (await session.execute(select(OrderItem).where(OrderItem.order_id == order.id))).scalars().all()
            status_text = "🟢 Faol" if order.status == "active" else "✅ Yetkazilgan"
            date_time = order.created_at.strftime("%d.%m.%Y %H:%M")
            order_number = order.daily_order_number if order.daily_order_number else order.id
            
            text = f"🧾 <b>Buyurtma #{order_number}</b> | {status_text}\n🕒 Sana: {date_time}\n\n🍽 <b>Taomlar:</b>\n"
            for item in items:
                prod_name = next((p["name"] for cat in PRODUCTS.values() for p in cat if p["id"] == item.product_id), "Noma'lum")
                text += f"— {prod_name} ({item.quantity} ta)\n"
            text += f"\n💳 Jami summa: {order.total_price:,.0f} so'm\n"
            
            reorder_kb = InlineKeyboardMarkup(inline_keyboard=[[InlineKeyboardButton(text="🔄 Shu savatni qayta buyurtma qilish", callback_data=f"reorder_{order.id}")]])
            await message.answer(text, reply_markup=reorder_kb, parse_mode="HTML")