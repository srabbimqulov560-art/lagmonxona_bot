import math
import asyncio
from aiogram import Router, F, Bot
from aiogram.types import (
    Message, CallbackQuery, 
    InlineKeyboardMarkup, InlineKeyboardButton, 
    ReplyKeyboardMarkup, KeyboardButton, 
    LabeledPrice, PreCheckoutQuery
)
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import StatesGroup, State

from sqlalchemy.future import select
from sqlalchemy import func
from datetime import datetime, time

from core.config import ADMIN_GROUP_ID, PAYMENT_TOKEN
from db.engine import AsyncSessionLocal
from db.models import Order, OrderItem, Cart, CartItem, User
from keyboards.default import get_main_menu_kb

router = Router()

# ==========================================
# ASOSIY SOZLAMALAR VA CONSTANTALAR
# ==========================================
DELIVERY_FEE = 10000
RESTAURANT_LAT = 41.31124 
RESTAURANT_LON = 69.24435  
MAX_DISTANCE_KM = 2.5     

# Faol buyurtmalarning budilniklarini ushlab turuvchi xotira
ACTIVE_ALERTS = {}

class Checkout(StatesGroup):
    location = State()
    notes = State()
    payment = State()

PRODUCTS = {
    "lagmon": [
        {"id": "l1", "name": "Qovurma Lag'mon", "price": 45000, "desc": "Maxsus qovurma lag'mon"},
        {"id": "l2", "name": "Quyuq Lag'mon", "price": 40000, "desc": "Go'shtli quyuq lag'mon"}
    ],
    "shashlik": [
        {"id": "s1", "name": "Qiyma Shashlik", "price": 15000, "desc": "Mol go'shtidan qiyma shashlik"},
        {"id": "s2", "name": "Jigar Shashlik", "price": 14000, "desc": "Yumshoq jigar shashlik"}
    ],
    "drinks": [
        {"id": "d1", "name": "Coca-Cola 1L", "price": 12000, "desc": "Muzdek Coca-Cola"},
        {"id": "d2", "name": "Qora Choy", "price": 5000, "desc": "Eron qora choyi"}
    ]
}

# ==========================================
# YORDAMCHI FUNKSIYALAR
# ==========================================
def calculate_distance(lat1, lon1, lat2, lon2):
    R = 6371.0 
    dlat = math.radians(lat2 - lat1)
    dlon = math.radians(lon2 - lon1)
    a = math.sin(dlat / 2)**2 + math.cos(math.radians(lat1)) * math.cos(math.radians(lat2)) * math.sin(dlon / 2)**2
    c = 2 * math.atan2(math.sqrt(a), math.sqrt(1 - a))
    return R * c

async def get_or_create_cart(session, telegram_id):
    result = await session.execute(select(Cart).where(Cart.telegram_id == telegram_id))
    cart = result.scalars().first()
    if not cart:
        cart = Cart(telegram_id=telegram_id)
        session.add(cart)
        await session.commit()
        await session.refresh(cart)
    return cart

async def get_menu_and_cart_content(session, telegram_id):
    cart = await get_or_create_cart(session, telegram_id)
    result = await session.execute(select(CartItem).where(CartItem.cart_id == cart.id))
    cart_items = result.scalars().all()

    text = "🍔 <b>Lag'monxona Durujba menyusi:</b>\n\n"
    total_price = DELIVERY_FEE 
    has_items = False

    if cart_items:
        has_items = True
        text += "🛒 <b>JORIY SAVAT:</b>\n"
        for idx, item in enumerate(cart_items, 1):
            prod_info = next((p for cat in PRODUCTS.values() for p in cat if p["id"] == item.product_id), None)
            if prod_info:
                item_total = prod_info["price"] * item.quantity
                total_price += item_total
                text += f"{idx}. {prod_info['name']} | {item.quantity} ta = {item_total:,.0f} so'm\n"
        
        text += f"〰️〰️〰️〰️〰️〰️〰️〰️〰️\n"
        text += f"🛵 <b>Yetkazib berish:</b> {DELIVERY_FEE:,.0f} so'm\n"
        text += f"💳 <b>Jami:</b> {total_price:,.0f} so'm\n\n"
    else:
        text += "🛒 <i>Savatingiz hozircha bo'sh.</i>\n\n"

    text += "👇 <b>Qaysi bo'limdan taom tanlaysiz?</b>"

    inline_kb = [
        [InlineKeyboardButton(text="🍜 Lag'monlar", callback_data="category_lagmon")],
        [InlineKeyboardButton(text="🍢 Shashliklar", callback_data="category_shashlik")],
        [InlineKeyboardButton(text="🥤 Ichimliklar", callback_data="category_drinks")]
    ]

    if has_items:
        inline_kb.append([InlineKeyboardButton(text="✅ Buyurtma berish", callback_data="checkout")])
        inline_kb.append([InlineKeyboardButton(text="🗑 Savatni tozalash", callback_data="clear_cart")])

    return text, InlineKeyboardMarkup(inline_keyboard=inline_kb)

# ==========================================
# ⏰ TINIMSIZ XABAR JONATISH TSIKLI (YANGI)
# ==========================================
async def order_alert_task(bot: Bot, order_id: int, telegram_id: int, short_text: str, full_text: str, chat_id: int):
    kb = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="📥 QABUL QILISH", callback_data=f"accept_{order_id}_{telegram_id}")]
    ])
    
    # 1. Birinchi xabarni yuboramiz
    try:
        msg = await bot.send_message(chat_id, short_text, reply_markup=kb, parse_mode="HTML")
        ACTIVE_ALERTS[order_id] = {
            "stop": False,
            "last_message_id": msg.message_id,
            "full_text": full_text
        }
    except Exception as e:
        print(f"Xabar yuborishda xato: {e}")
        return
        
    # 2. To'xtatilmaguncha har 5 soniyada yangilab turamiz
    while order_id in ACTIVE_ALERTS and not ACTIVE_ALERTS[order_id]["stop"]:
        await asyncio.sleep(5)
        
        if order_id not in ACTIVE_ALERTS or ACTIVE_ALERTS[order_id]["stop"]:
            break
            
        old_msg_id = ACTIVE_ALERTS[order_id]["last_message_id"]
        
        # Eskisini o'chiramiz
        try:
            await bot.delete_message(chat_id, old_msg_id)
        except Exception:
            pass 
            
        # Yangisini yuboramiz
        try:
            new_msg = await bot.send_message(chat_id, short_text, reply_markup=kb, parse_mode="HTML")
            ACTIVE_ALERTS[order_id]["last_message_id"] = new_msg.message_id
        except Exception:
            pass 

# ==========================================
# QABUL QILISH VA CHEK CHIQARISH TUGMALARI (YANGI MANTIQ)
# ==========================================
@router.callback_query(F.data.startswith("accept_"))
async def process_accept_order(callback: CallbackQuery, bot: Bot):
    parts = callback.data.split("_")
    order_id = int(parts[1])
    telegram_id = int(parts[2])
    
    if order_id in ACTIVE_ALERTS:
        # Budilnikni to'xtatamiz
        ACTIVE_ALERTS[order_id]["stop"] = True 
        full_text = ACTIVE_ALERTS[order_id]["full_text"]
        
        # 1-BOSQICH: Faqat "Chek chiqarish" va "Bekor qilish" chiqadi (Yetkazildi hozircha yo'q)
        admin_kb = InlineKeyboardMarkup(inline_keyboard=[
            [InlineKeyboardButton(text="🖨 Chek chiqarish (iiko)", callback_data=f"print_{order_id}_{telegram_id}")],
            [InlineKeyboardButton(text="❌ Bekor qilish", callback_data=f"status_cancelled_{order_id}_{telegram_id}")]
        ])
        
        try:
            await callback.message.edit_text(text=full_text, reply_markup=admin_kb, parse_mode="HTML", disable_web_page_preview=True)
        except Exception:
            pass
            
        await callback.answer("✅ Buyurtma qabul qilindi!", show_alert=False)
        del ACTIVE_ALERTS[order_id]
    else:
        await callback.answer("Bu buyurtma allaqachon qabul qilingan.", show_alert=True)

@router.callback_query(F.data.startswith("print_"))
async def process_print_receipt(callback: CallbackQuery):
    parts = callback.data.split("_")
    order_id = int(parts[1])
    telegram_id = int(parts[2])

    await callback.answer("🖨 iiko tizimiga uzatildi. Chek chiqdi!", show_alert=False)

    # 2-BOSQICH: Chek bosilgach, uning o'rniga "Yetkazildi" tugmasi keladi
    new_admin_kb = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="✅ Yetkazildi", callback_data=f"status_completed_{order_id}_{telegram_id}")],
        [InlineKeyboardButton(text="❌ Bekor qilish", callback_data=f"status_cancelled_{order_id}_{telegram_id}")]
    ])
    
    try:
        # Xabarning faqat pastdagi tugmalarini yangilaymiz (matn o'zgarmaydi)
        await callback.message.edit_reply_markup(reply_markup=new_admin_kb)
    except Exception:
        pass


# ==========================================
# ASOSIY BUYURTMA SAQLASH (YANGILANGAN)
# ==========================================
async def save_order_and_notify(message: Message, state: FSMContext, bot: Bot, payment_type: str, payment_info: dict = None):
    telegram_id = message.from_user.id
    checkout_data = await state.get_data()
    
    async with AsyncSessionLocal() as session:
        user_result = await session.execute(select(User).where(User.telegram_id == telegram_id))
        user = user_result.scalars().first()
        phone_number = user.phone_number if user else "Noma'lum"

        cart = await get_or_create_cart(session, telegram_id)
        result = await session.execute(select(CartItem).where(CartItem.cart_id == cart.id))
        cart_items = result.scalars().all()
        
        total_price = DELIVERY_FEE
        for item in cart_items:
            price = next((p["price"] for cat in PRODUCTS.values() for p in cat if p["id"] == item.product_id), 0)
            total_price += price * item.quantity
        
        today_start = datetime.combine(datetime.today(), time.min)
        order_result = await session.execute(
            select(func.max(Order.daily_order_number)).where(Order.created_at >= today_start)
        )
        new_daily_number = (order_result.scalar() or 0) + 1
        
        new_order = Order(
            telegram_id=telegram_id,
            daily_order_number=new_daily_number,
            total_price=total_price,
            latitude=checkout_data.get("latitude"),
            longitude=checkout_data.get("longitude"),
            courier_notes=checkout_data.get("notes")
        )
        session.add(new_order)
        await session.flush() 
        
        items_text = ""
        for item in cart_items:
            prod_info = next((p for cat in PRODUCTS.values() for p in cat if p["id"] == item.product_id), None)
            if prod_info:
                o_item = OrderItem(order_id=new_order.id, product_id=item.product_id, quantity=item.quantity, price=prod_info["price"])
                session.add(o_item)
                items_text += f"— {prod_info['name']} ({item.quantity} ta)\n"
        
        await session.execute(CartItem.__table__.delete().where(CartItem.cart_id == cart.id))
        await session.commit()
    
    await state.clear()
    
    # Mijozga javob
    text = (
        f"✅ <b>Buyurtma muvaffaqiyatli qabul qilindi!</b>\n\n"
        f"🧾 <b>Buyurtma raqami:</b> #{new_daily_number}\n"
        f"💳 <b>To'lov:</b> {payment_type}\n"
        f"💰 <b>Jami to'langan summa:</b> {total_price:,.0f} so'm\n\n"
        f"🕒 Oshxona tayyorlashni boshladi."
    )
    await message.answer(text, reply_markup=get_main_menu_kb("uz"), parse_mode="HTML")

    receipt_text = ""
    if payment_info:
        receipt_text = (
            f"🧾 <b>To'lov cheki ma'lumotlari:</b>\n"
            f"▪️ Payme/Click Tranzaksiya ID:\n<code>{payment_info['provider_charge_id']}</code>\n"
            f"▪️ Telegram Tranzaksiya ID:\n<code>{payment_info['telegram_charge_id']}</code>\n\n"
        )

    # 1. Admin guruhiga tinimsiz boradigan QISQA xabar
    short_alert_text = (
        f"🚨 <b>DIQQAT! YANGI BUYURTMA #{new_daily_number}</b>\n\n"
        f"📞 <b>Tel:</b> {phone_number}\n"
        f"🍽 <b>Menyu:</b>\n{items_text}\n"
        f"<i>⚠️ Qabul qilinmaguncha bu xabar har 5 soniyada yangilanadi!</i>"
    )

    # 2. Qabul qilingandan keyin ko'rinadigan TO'LIQ xabar (Kuryer va lokatsiya bilan)
    full_admin_text = (
        f"🆕 <b>BUYURTMA #{new_daily_number} (QABUL QILINGAN)</b>\n\n"
        f"👤 Mijoz: {message.from_user.full_name} (@{message.from_user.username})\n"
        f"📞 Telefon: {phone_number}\n\n"
        f"🍽 <b>Buyurtma tarkibi:</b>\n{items_text}\n"
        f"📍 <a href='https://yandex.ru/maps/?pt={checkout_data.get('longitude')},{checkout_data.get('latitude')}&z=18&l=map'>Mijoz lokatsiyasi (Xarita)</a>\n"
        f"📝 Izoh: {checkout_data.get('notes')}\n"
        f"💳 To'lov turi: <b>{payment_type}</b>\n\n"
        f"{receipt_text}"
        f"💰 <b>Jami summa: {total_price:,.0f} so'm</b>\n"
    )
    
    # Fon vazifasini (Budilnikni) ishga tushiramiz
    asyncio.create_task(
        order_alert_task(
            bot=bot, 
            order_id=new_order.id, 
            telegram_id=telegram_id,
            short_text=short_alert_text, 
            full_text=full_admin_text, 
            chat_id=ADMIN_GROUP_ID
        )
    )

# ==========================================
# MENYU VA SAVAT BO'LIMI 
# ==========================================
@router.message(F.text.in_(["🛒 Menyu", "🛒 Меню", "🛍 Savat", "🛍 Корзина"]))
async def show_main_menu(message: Message):
    async with AsyncSessionLocal() as session:
        text, kb = await get_menu_and_cart_content(session, message.from_user.id)
        await message.answer(text, reply_markup=kb, parse_mode="HTML")

@router.callback_query(F.data == "back_to_categories")
async def back_to_categories(callback: CallbackQuery):
    async with AsyncSessionLocal() as session:
        text, kb = await get_menu_and_cart_content(session, callback.from_user.id)
        await callback.message.edit_text(text, reply_markup=kb, parse_mode="HTML")

@router.callback_query(F.data.startswith("category_"))
async def show_products(callback: CallbackQuery):
    cat_id = callback.data.split("_")[1]
    products = PRODUCTS.get(cat_id, [])
    
    inline_kb = [
        [InlineKeyboardButton(text=f"{p['name']} - {p['price']:,.0f} so'm", callback_data=f"prod_{cat_id}_{p['id']}")]
        for p in products
    ]
    inline_kb.append([InlineKeyboardButton(text="🔙 Ortga (Menyuga)", callback_data="back_to_categories")])
    kb = InlineKeyboardMarkup(inline_keyboard=inline_kb)
    await callback.message.edit_text("👇 <b>Taomlardan birini tanlang:</b>", reply_markup=kb, parse_mode="HTML")

@router.callback_query(F.data.startswith("prod_"))
async def show_product_quantity(callback: CallbackQuery):
    _, cat_id, prod_id = callback.data.split("_")
    product = next((p for p in PRODUCTS[cat_id] if p["id"] == prod_id), None)
    
    if product:
        quantity = 1 
        kb = InlineKeyboardMarkup(inline_keyboard=[
            [
                InlineKeyboardButton(text="➖", callback_data=f"qty_minus_{cat_id}_{prod_id}_{quantity}"),
                InlineKeyboardButton(text=f"{quantity} ta", callback_data="ignore"),
                InlineKeyboardButton(text="➕", callback_data=f"qty_plus_{cat_id}_{prod_id}_{quantity}")
            ],
            [InlineKeyboardButton(text="🛒 Savatga qo'shish", callback_data=f"add_{prod_id}_{quantity}")],
            [InlineKeyboardButton(text="🔙 Ortga", callback_data=f"category_{cat_id}")]
        ])
        text = f"🍽 <b>{product['name']}</b>\n\n📝 {product['desc']}\n\n💸 Narxi: {product['price']:,.0f} so'm\n\n<i>Nechta buyurtma qilasiz?</i>"
        await callback.message.edit_text(text, reply_markup=kb, parse_mode="HTML")

@router.callback_query(F.data.startswith("qty_"))
async def change_quantity(callback: CallbackQuery):
    parts = callback.data.split("_")
    action = parts[1]
    cat_id = parts[2]
    prod_id = parts[3]
    current_qty = int(parts[4])
    
    new_qty = current_qty + 1 if action == "plus" else (current_qty - 1 if current_qty > 1 else current_qty)
        
    kb = InlineKeyboardMarkup(inline_keyboard=[
        [
            InlineKeyboardButton(text="➖", callback_data=f"qty_minus_{cat_id}_{prod_id}_{new_qty}"),
            InlineKeyboardButton(text=f"{new_qty} ta", callback_data="ignore"),
            InlineKeyboardButton(text="➕", callback_data=f"qty_plus_{cat_id}_{prod_id}_{new_qty}")
        ],
        [InlineKeyboardButton(text="🛒 Savatga qo'shish", callback_data=f"add_{prod_id}_{new_qty}")],
        [InlineKeyboardButton(text="🔙 Ortga", callback_data=f"category_{cat_id}")]
    ])
    await callback.message.edit_reply_markup(reply_markup=kb)

@router.callback_query(F.data.startswith("add_"))
async def add_to_cart_db(callback: CallbackQuery):
    parts = callback.data.split("_")
    prod_id = parts[1]
    quantity = int(parts[2])
    telegram_id = callback.from_user.id
    
    product_name = next((p["name"] for cat in PRODUCTS.values() for p in cat if p["id"] == prod_id), "")
                
    async with AsyncSessionLocal() as session:
        cart = await get_or_create_cart(session, telegram_id)
        result = await session.execute(select(CartItem).where(CartItem.cart_id == cart.id, CartItem.product_id == prod_id))
        item = result.scalars().first()
        
        if item:
            item.quantity += quantity
        else:
            new_item = CartItem(cart_id=cart.id, product_id=prod_id, quantity=quantity)
            session.add(new_item)
        await session.commit()
        text, kb = await get_menu_and_cart_content(session, telegram_id)
        
    await callback.answer(f"✅ {product_name} ({quantity} ta) savatga qo'shildi!", show_alert=False)
    await callback.message.edit_text(text, reply_markup=kb, parse_mode="HTML")

@router.callback_query(F.data == "clear_cart")
async def clear_cart(callback: CallbackQuery):
    telegram_id = getattr(callback.from_user, "id", callback.from_user.id)
    async with AsyncSessionLocal() as session:
        cart = await get_or_create_cart(session, telegram_id)
        await session.execute(CartItem.__table__.delete().where(CartItem.cart_id == cart.id))
        await session.commit()
        text, kb = await get_menu_and_cart_content(session, telegram_id)
        
    await callback.answer("Savat tozalandi!", show_alert=True)
    await callback.message.edit_text(text, reply_markup=kb, parse_mode="HTML")

@router.callback_query(F.data.startswith("reorder_"))
async def process_reorder(callback: CallbackQuery):
    order_id = int(callback.data.split("_")[1])
    telegram_id = callback.from_user.id
    
    async with AsyncSessionLocal() as session:
        result = await session.execute(select(OrderItem).where(OrderItem.order_id == order_id))
        order_items = result.scalars().all()
        cart = await get_or_create_cart(session, telegram_id)
        
        for o_item in order_items:
            res = await session.execute(select(CartItem).where(CartItem.cart_id == cart.id, CartItem.product_id == o_item.product_id))
            c_item = res.scalars().first()
            if c_item:
                c_item.quantity += o_item.quantity
            else:
                new_c = CartItem(cart_id=cart.id, product_id=o_item.product_id, quantity=o_item.quantity)
                session.add(new_c)
        await session.commit()
        text, kb = await get_menu_and_cart_content(session, telegram_id)
        
    await callback.answer("✅ Tarixdagi buyurtma savatga qo'shildi!", show_alert=True)
    await callback.message.answer(text, reply_markup=kb, parse_mode="HTML")


# ==========================================
# BUYURTMANI RASMIYLASHTIRISH (CHECKOUT)
# ==========================================
@router.callback_query(F.data == "checkout")
async def start_checkout(callback: CallbackQuery, state: FSMContext):
    kb = ReplyKeyboardMarkup(keyboard=[
        [KeyboardButton(text="📍 Lokatsiyani yuborish", request_location=True)],
        [KeyboardButton(text="❌ Bekor qilish")]
    ], resize_keyboard=True)
    
    await callback.message.delete()
    await callback.message.answer("📍 Kuryerimiz manzilni aniq topishi uchun <b>Lokatsiyangizni yuboring:</b>", reply_markup=kb, parse_mode="HTML")
    await state.set_state(Checkout.location)

@router.message(Checkout.location, F.location)
async def process_location(message: Message, state: FSMContext):
    user_lat = message.location.latitude
    user_lon = message.location.longitude
    
    distance = calculate_distance(RESTAURANT_LAT, RESTAURANT_LON, user_lat, user_lon)
    
    if distance > MAX_DISTANCE_KM:
        text = (
            f"❗️ <b>Kechirasiz, siz restorandan {distance:.1f} km masofada joylashgansiz.</b>\n\n"
            f"Bizning xususiy yetkazib berish xizmatimiz faqat <b>{MAX_DISTANCE_KM} km</b> radiusda ishlaydi."
        )
        await state.clear()
        await message.answer(text, reply_markup=get_main_menu_kb("uz"), parse_mode="HTML")
        return

    await state.update_data(latitude=user_lat, longitude=user_lon)
    kb = ReplyKeyboardMarkup(keyboard=[[KeyboardButton(text="O'tkazib yuborish ⏭")]], resize_keyboard=True)
    await message.answer("📝 <b>Kuryer uchun qo'shimcha izoh qoldiring:</b>\n(Masalan: Uy raqami, podyezd, domofon kodi)", reply_markup=kb, parse_mode="HTML")
    await state.set_state(Checkout.notes)

@router.message(Checkout.notes, F.text)
async def process_notes(message: Message, state: FSMContext):
    notes = message.text if message.text != "O'tkazib yuborish ⏭" else "Izoh yo'q"
    await state.update_data(notes=notes)
    kb = ReplyKeyboardMarkup(keyboard=[
        [KeyboardButton(text="💵 Naqd pul")],
        [KeyboardButton(text="💳 Payme/Click")]
    ], resize_keyboard=True)
    await message.answer("💳 <b>To'lov turini tanlang:</b>", reply_markup=kb, parse_mode="HTML")
    await state.set_state(Checkout.payment)

@router.message(Checkout.payment, F.text == "💵 Naqd pul")
async def process_cash_payment(message: Message, state: FSMContext, bot: Bot):
    await save_order_and_notify(message, state, bot, payment_type="Naqd pul")

@router.message(Checkout.payment, F.text == "💳 Payme/Click")
async def send_invoice(message: Message, state: FSMContext, bot: Bot):
    telegram_id = message.from_user.id
    
    async with AsyncSessionLocal() as session:
        cart = await get_or_create_cart(session, telegram_id)
        result = await session.execute(select(CartItem).where(CartItem.cart_id == cart.id))
        cart_items = result.scalars().all()
        
        total_price = DELIVERY_FEE
        for item in cart_items:
            price = next((p["price"] for cat in PRODUCTS.values() for p in cat if p["id"] == item.product_id), 0)
            total_price += price * item.quantity

    prices = [LabeledPrice(label="Lag'monxona Durujba - Buyurtma", amount=int(total_price * 100))]
    
    try:
        await bot.send_invoice(
            chat_id=message.chat.id,
            title="Taomlar uchun to'lov",
            description="Iltimos, buyurtmani tasdiqlash uchun to'lovni amalga oshiring.",
            payload=f"buyurtma_{telegram_id}",
            provider_token=PAYMENT_TOKEN,
            currency="UZS",
            prices=prices,
            start_parameter="test-payment"
        )
    except Exception as e:
        err_msg = f"⚠️ <b>To'lov tizimida xatolik yuz berdi:</b>\n\n<code>{e}</code>\n\nIltimos, tekshiring."
        await message.answer(err_msg, parse_mode="HTML")
        print(f"INVOICE XATOLIGI: {e}")

@router.pre_checkout_query()
async def pre_checkout_query_handler(pre_checkout_query: PreCheckoutQuery, bot: Bot):
    await bot.answer_pre_checkout_query(pre_checkout_query.id, ok=True)

@router.message(F.successful_payment)
async def successful_payment_handler(message: Message, state: FSMContext, bot: Bot):
    payment_info = {
        "telegram_charge_id": message.successful_payment.telegram_payment_charge_id,
        "provider_charge_id": message.successful_payment.provider_payment_charge_id
    }
    await save_order_and_notify(
        message, 
        state, 
        bot, 
        payment_type="Karta orqali (TO'LANDI ✅)", 
        payment_info=payment_info
    )

@router.message(F.text == "❌ Bekor qilish")
async def cancel_checkout(message: Message, state: FSMContext):
    await state.clear()
    await message.answer("🛑 Buyurtma berish bekor qilindi.", reply_markup=get_main_menu_kb("uz"))