import re
from aiogram import Router, F
from aiogram.filters import CommandStart
from aiogram.types import (
    Message, CallbackQuery, 
    ReplyKeyboardMarkup, KeyboardButton, 
    InlineKeyboardMarkup, InlineKeyboardButton, ReplyKeyboardRemove
)
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import StatesGroup, State

from sqlalchemy.future import select
from db.engine import AsyncSessionLocal
from db.models import User
from keyboards.default import get_main_menu_kb 

router = Router()

class Registration(StatesGroup):
    language = State()
    full_name = State()
    phone = State()

# ==========================================
# 1. /START BUYRUG'I VA ASOSIY KUTIB OLISH
# ==========================================
@router.message(CommandStart())
async def cmd_start(message: Message, state: FSMContext):
    await state.clear() 
    telegram_id = message.from_user.id
    
    # Restoran haqida chiroyli ma'lumot va linklar (Ijtimoiy tarmoqlar matn ichida)
    welcome_text = (
        "🍜 <b>\"Lag'monxona Durujba\"</b> oilaviy restoranining rasmiy botiga xush kelibsiz!\n\n"
        "📍 <b>Manzil:</b> Toshkent sh. Islom Karimov ko'chasi (Xalqlar Do'stligi metrosi yonida).\n"
        "🗺 <a href='https://yandex.uz/maps/-/CDq~rM~I'>Joylashuvni xaritada ko'rish</a>\n\n"
        "📞 <b>Aloqa uchun telefonlar:</b>\n"
        "▫️ +998 90 979 23 93\n"
        "▫️ +998 90 480 23 93\n\n"
        "📱 <b>Bizning ijtimoiy tarmoqlar:</b>\n"
        "▫️ <a href='http://t.me/lagmonxona_1'>Telegram</a>\n"
        "▫️ <a href='https://www.instagram.com/lagmonxona.uz?igsh=MXVvYnJjZHlxa2c4ZA=='>Instagram</a>"
    )

    # Mijoz bazada bormi tekshiramiz
    async with AsyncSessionLocal() as session:
        result = await session.execute(select(User).where(User.telegram_id == telegram_id))
        user = result.scalars().first()

    if user:
        # AGAR BAZADA BO'LSA: To'g'ridan-to'g'ri menyuni beramiz
        text = welcome_text + "\n\n👇 <b>Quyidagi menyu orqali buyurtma berishingiz mumkin:</b>"
        await message.answer(text, reply_markup=get_main_menu_kb(user.language), parse_mode="HTML", disable_web_page_preview=True)
    else:
        # AGAR YANGI MIJOZ BO'LSA: Buyurtma berish / Ro'yxatdan o'tish tugmasini beramiz
        text = welcome_text + "\n\n👇 <b>Buyurtma berish uchun ro'yxatdan o'ting:</b>"
        kb = InlineKeyboardMarkup(inline_keyboard=[
            [InlineKeyboardButton(text="🛍 Buyurtma berish", callback_data="start_register")]
        ])
        await message.answer(text, reply_markup=kb, parse_mode="HTML", disable_web_page_preview=True)

# ==========================================
# 2. RO'YXATDAN O'TISH BOSQICHLARI
# ==========================================

# Til tanlash (Buyurtma berish tugmasi bosilganda)
@router.callback_query(F.data == "start_register")
async def start_register(callback: CallbackQuery, state: FSMContext):
    lang_kb = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="🇺🇿 O'zbekcha", callback_data="lang_uz")],
        [InlineKeyboardButton(text="🇷🇺 Русский", callback_data="lang_ru")]
    ])
    await callback.message.edit_text(
        "Iltimos, o'zingizga qulay tilni tanlang:\n\nПожалуйста, выберите удобный вам язык:", 
        reply_markup=lang_kb
    )
    await state.set_state(Registration.language)

# Tilni saqlash va Ism so'rash
@router.callback_query(Registration.language, F.data.startswith("lang_"))
async def process_language(callback: CallbackQuery, state: FSMContext):
    lang = callback.data.split("_")[1] 
    await state.update_data(language=lang)
    
    text = "Iltimos, ism va familiyangizni kiriting:" if lang == "uz" else "Пожалуйста, введите ваше имя и фамилию:"
        
    await callback.message.delete()
    await callback.message.answer(text)
    await state.set_state(Registration.full_name)

# Ismni saqlash va Raqam so'rash
@router.message(Registration.full_name, F.text)
async def process_name(message: Message, state: FSMContext):
    await state.update_data(full_name=message.text)
    
    user_data = await state.get_data()
    lang = user_data.get("language")
    
    phone_kb = ReplyKeyboardMarkup(keyboard=[
        [KeyboardButton(text="📞 Telefon raqamni yuborish" if lang == "uz" else "📞 Отправить номер телефона", request_contact=True)]
    ], resize_keyboard=True)
    
    if lang == "uz":
        text = (
            "Rahmat! 📱 Endi telefon raqamingizni yuboring.\n\n"
            "❗️ <i>Kuryerimiz siz bilan bog'lanishi uchun aniq ishlaydigan raqam kiriting.</i>\n\n"
            "Pastdagi tugmani bosishingiz yoki raqamingizni qo'lda yozishingiz mumkin (Masalan: 93 123 45 67 )."
        )
    else:
        text = (
            "Спасибо! 📱 Теперь отправьте свой номер телефона.\n\n"
            "❗️ <i>Введите действующий номер, чтобы наш курьер мог с вами связаться.</i>\n\n"
            "Вы можете нажать кнопку ниже или ввести номер вручную (Например: 93 123 45 67)."
        )
        
    await message.answer(text, reply_markup=phone_kb, parse_mode="HTML")
    await state.set_state(Registration.phone)

# Raqamni saqlash va Bazaga yozish (Aqlli tekshiruv bilan)
@router.message(Registration.phone)
async def process_phone(message: Message, state: FSMContext):
    # Agar tugma orqali yuborgan bo'lsa
    if message.contact:
        phone_number = message.contact.phone_number
        if not phone_number.startswith('+'):
            phone_number = '+' + phone_number
    # Agar qo'lda yozgan bo'lsa
    elif message.text:
        clean_phone = re.sub(r'\D', '', message.text)
        
        if len(clean_phone) == 9:
            phone_number = f"+998{clean_phone}"
        elif len(clean_phone) == 12 and clean_phone.startswith("998"):
            phone_number = f"+{clean_phone}"
        else:
            err_text = "⚠️ Iltimos, to'g'ri telefon raqamini kiriting.\n(Masalan: <b>93 123 45 67</b> yoki <b>+998931234567</b>)"
            await message.answer(err_text, parse_mode="HTML")
            return
    else:
        await message.answer("⚠️ Iltimos, raqamingizni yuboring.")
        return

    telegram_id = message.from_user.id
    user_data = await state.get_data()
    language = user_data.get("language")
    full_name = user_data.get("full_name")
    
    # Ma'lumotlar bazasiga saqlash
    async with AsyncSessionLocal() as session:
        result = await session.execute(select(User).where(User.telegram_id == telegram_id))
        user = result.scalars().first()

        if not user:
            new_user = User(
                telegram_id=telegram_id,
                full_name=full_name,
                phone_number=phone_number,
                language=language
            )
            session.add(new_user)
            await session.commit()
    
    text = "✅ Ro'yxatdan muvaffaqiyatli o'tdingiz!\n\n👇 Quyidagi menyu orqali buyurtma berishingiz mumkin:" if language == "uz" else "✅ Вы успешно зарегистрировались!\n\n👇 Вы можете сделать заказ через меню ниже:"
    await message.answer(text, reply_markup=get_main_menu_kb(language), parse_mode="HTML")
    await state.clear()