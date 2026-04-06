import asyncio
import os
from aiohttp import web
from aiogram import Bot, Dispatcher
from aiogram.fsm.storage.redis import RedisStorage
from core.config import BOT_TOKEN, REDIS_URL
from handlers import registration, main_menu, ordering, admin 
from db.engine import init_db

# Render uchun soxta sahifa javobi
async def health_check(request):
    return web.Response(text="Bot muvaffaqiyatli ishlamoqda!")

async def main():
    # 1. PostgreSQL bazani ishga tushirish
    await init_db()
    
    bot = Bot(token=BOT_TOKEN)
    
    # 2. Redis xotirani FSM ga ulash
    storage = RedisStorage.from_url(REDIS_URL)
    dp = Dispatcher(storage=storage)

    # Routerlarni ulash
    dp.include_router(registration.router)
    dp.include_router(main_menu.router)
    dp.include_router(ordering.router)
    dp.include_router(admin.router)

    # ==========================================
    # 3. RENDER UCHUN SOXTA WEB-SERVER
    # ==========================================
    app = web.Application()
    app.router.add_get('/', health_check)
    runner = web.AppRunner(app)
    await runner.setup()
    
    # Render o'zi beradigan portni olamiz (yoki 10000)
    port = int(os.environ.get("PORT", 10000))
    site = web.TCPSite(runner, '0.0.0.0', port)
    await site.start()
    # ==========================================

    print(f"🚀 Lag'monxona Durujba boti {port}-portda ishga tushdi...")
    await dp.start_polling(bot)

if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        print("Bot to'xtatildi.")