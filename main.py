import asyncio
from aiogram import Bot, Dispatcher
from aiogram.fsm.storage.redis import RedisStorage # YANGI: Redis importi
from core.config import BOT_TOKEN, REDIS_URL
from handlers import registration, main_menu, ordering, admin 
from db.engine import init_db

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

    print("🚀 Lag'monxona Durujba boti PostgreSQL va Redis bilan ishga tushdi...")
    await dp.start_polling(bot)

if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        print("Bot to'xtatildi.")