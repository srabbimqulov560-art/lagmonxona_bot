import asyncio
from aiogram import Router, F, Bot
from aiogram.types import Message, CallbackQuery, InlineKeyboardMarkup, InlineKeyboardButton
from aiogram.filters import Command
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import StatesGroup, State

from sqlalchemy.future import select
from db.engine import AsyncSessionLocal
from db.models import User
from core.config import ADMIN_ID

router = Router()

class AdminState(StatesGroup):
    waiting_for_broadcast = State()

# ==========================================
# 1. YASHIRIN ADMIN PANELGA KIRISH
# ==========================================
@router.message(Command("admin"))
async def show_admin_panel(message: Message):
    # Faqat sizni (ADMIN_ID) o'tkazadi
    if message.from_user.id != ADMIN_ID:
        return
    
    kb = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="📢 Barchaga xabar tarqatish", callback_data="start_broadcast")]
    ])
    
    await message.answer("👨‍💻 <b>Boshqaruv paneliga xush kelibsiz!</b>\n\nNima ish qilamiz?", reply_markup=kb, parse_mode="HTML")

# ==========================================
# 2. XABARNI QABUL QILISH
# ==========================================
@router.callback_query(F.data == "start_broadcast")
async def ask_broadcast_message(callback: CallbackQuery, state: FSMContext):
    if callback.from_user.id != ADMIN_ID:
        return
        
    await callback.message.delete()
    text = (
        "📝 <b>Tarqatmoqchi bo'lgan xabaringizni yuboring.</b>\n\n"
        "<i>💡 Maslahat: Matn, Rasm, Video yoki Ovozli xabar ham yuborishingiz mumkin. Bot aynan siz yuborgan narsaning nusxasini hammaga tarqatadi.</i>\n\n"
        "Bekor qilish uchun /cancel ni bosing."
    )
    await callback.message.answer(text, parse_mode="HTML")
    await state.set_state(AdminState.waiting_for_broadcast)

# ==========================================
# 3. TARQATISH JARAYONI (BROADCAST)
# ==========================================
@router.message(AdminState.waiting_for_broadcast)
async def process_broadcasting(message: Message, state: FSMContext, bot: Bot):
    if message.text == "/cancel":
        await state.clear()
        await message.answer("🛑 Xabar tarqatish bekor qilindi.")
        return

    await state.clear()
    status_msg = await message.answer("⏳ <i>Xabar tarqatish boshlandi... Iltimos, kuting.</i>", parse_mode="HTML")
    
    success = 0
    fail = 0
    
    # Bazadan barcha mijozlarning ID larini olamiz
    async with AsyncSessionLocal() as session:
        result = await session.execute(select(User.telegram_id))
        users = result.scalars().all()
        
    for user_id in users:
        try:
            # send_copy funksiyasi - rasm, tekst, videoni farqiga bormay aynan o'zini "Forward" qilinmagan holatda yuboradi
            await message.send_copy(chat_id=user_id)
            success += 1
            # Telegram API bloklab qo'ymasligi uchun biroz pauza (sekundiga 20 ta xabar limiti bor)
            await asyncio.sleep(0.05)
        except Exception:
            # Agar kimdir botni bloklagan bo'lsa, xatolik berib to'xtab qolmasligi uchun Except ishlatiladi
            fail += 1
            
    result_text = (
        f"✅ <b>Xabar muvaffaqiyatli tarqatildi!</b>\n\n"
        f"🟢 Yetib bordi: <b>{success} ta mijozga</b>\n"
        f"🔴 Botni bloklaganlar: <b>{fail} ta mijoz</b>\n\n"
        f"📊 Jami bazadagi odamlar: {len(users)} ta"
    )
    await status_msg.edit_text(result_text, parse_mode="HTML")