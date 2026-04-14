import asyncio
import aiohttp

async def main():
    url = "https://api-ru.iiko.services/api/1"
    login = "1dc41167ea7443f89430ac220e9d5fdf"

    async with aiohttp.ClientSession() as session:
        # 1. iiko ga ulanamiz
        print("⏳ iiko tizimiga ulanmoqda...")
        resp = await session.post(f"{url}/access_token", json={"apiLogin": login})
        token = (await resp.json()).get("token")
        
        if not token:
            print("❌ API Login xato!")
            return

        # 2. Tashkilotlarni so'raymiz
        headers = {"Authorization": f"Bearer {token}"}
        resp2 = await session.post(f"{url}/organizations", json={"returnAdditionalInfo": True}, headers=headers)
        data = await resp2.json()

        print("\n=== SIZNING IIKO TASHKILOTLARINGIZ (RESTORANLAR) ===")
        for org in data.get("organizations", []):
            print(f"🏢 Nomi: {org.get('name')}")
            print(f"🔑 ID kodi: {org.get('id')}")
            print("-" * 50)

if __name__ == "__main__":
    asyncio.run(main())