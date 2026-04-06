from aiogram import Router, F, Bot
from aiogram.types import CallbackQuery
from sqlalchemy.future import select
from db.engine import AsyncSessionLocal
from db.models import Order

router = Router()

# Admin guruhidagi tugmalar bosilganda ishlaydigan funksiya
@router.callback_query(F.data.startswith("status_"))
async def change_order_status(callback: CallbackQuery, bot: Bot):
    # Callback datadan ma'lumotlarni ajratib olamiz
    # Format: status_completed_orderID_userID
    parts = callback.data.split("_")
    action = parts[1] # "completed" yoki "cancelled"
    order_id = int(parts[2])
    user_id = int(parts[3])

    async with AsyncSessionLocal() as session:
        # Bazadan buyurtmani topamiz
        result = await session.execute(select(Order).where(Order.id == order_id))
        order = result.scalars().first()

        if order:
            if action == "completed":
                order.status = "completed"
                await session.commit()
                # Mijozga xabar yuborish
                text = f"✅ Sizning <b>#{order.daily_order_number}</b> raqamli buyurtmangiz muvaffaqiyatli yetkazildi! Yoqimli ishtaha!"
                await bot.send_message(chat_id=user_id, text=text, parse_mode="HTML")
                
                # Guruhdagi xabarni o'zgartirish (tugmalarni yo'qotish)
                await callback.message.edit_text(callback.message.html_text + "\n\n🟢 <b>HOLAT: YETKAZILDI</b>", parse_mode="HTML")
            
            elif action == "cancelled":
                order.status = "cancelled"
                await session.commit()
                # Mijozga xabar yuborish
                text = f"❌ Sizning <b>#{order.daily_order_number}</b> raqamli buyurtmangiz bekor qilindi."
                await bot.send_message(chat_id=user_id, text=text, parse_mode="HTML")
                
                await callback.message.edit_text(callback.message.html_text + "\n\n🔴 <b>HOLAT: BEKOR QILINDI</b>", parse_mode="HTML")

    await callback.answer("Buyurtma holati o'zgartirildi!")