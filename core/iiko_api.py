import aiohttp
import time
from core.config import IIKO_API_LOGIN, IIKO_ORGANIZATION_ID, IIKO_TERMINAL_ID

BASE_URL = "https://api-ru.iiko.services/api/1"

# ==========================================
# 1. TOKEN OLISH
# ==========================================
async def get_iiko_token():
    if not IIKO_API_LOGIN or IIKO_API_LOGIN == "Sizning_iiko_api_loginingiz":
        return None
    async with aiohttp.ClientSession() as session:
        try:
            async with session.post(f"{BASE_URL}/access_token", json={"apiLogin": IIKO_API_LOGIN}) as resp:
                data = await resp.json()
                return data.get("token")
        except Exception:
            return None

# ==========================================
# 2. MENYU VA STOP LISTNI OLISH (5 daqiqalik Kesh bilan)
# ==========================================
CACHE = {"menu": None, "time": 0}

async def get_active_menu():
    if CACHE["menu"] and (time.time() - CACHE["time"] < 300):
        return CACHE["menu"]

    token = await get_iiko_token()
    
    if not token:
        CACHE["menu"] = {
            "lagmon": {"name": "🍜 Lag'monlar", "items": [
                {"id": "l1", "name": "Qovurma Lag'mon", "price": 45000, "desc": "Maxsus qovurma lag'mon", "is_stop": False},
                {"id": "l2", "name": "Quyuq Lag'mon", "price": 40000, "desc": "Go'shtli quyuq lag'mon", "is_stop": True} 
            ]},
            "shashlik": {"name": "🍢 Shashliklar", "items": [
                {"id": "s1", "name": "Qiyma Shashlik", "price": 15000, "desc": "Mol go'shtidan qiyma shashlik", "is_stop": False}
            ]}
        }
        CACHE["time"] = time.time()
        return CACHE["menu"]

    headers = {"Authorization": f"Bearer {token}"}
    async with aiohttp.ClientSession() as session:
        try:
            # 1. Stop Listni olamiz
            stop_list_ids = []
            stop_payload = {"organizationIds": [IIKO_ORGANIZATION_ID]}
            async with session.post(f"{BASE_URL}/stop_lists", json=stop_payload, headers=headers) as stop_resp:
                stop_data = await stop_resp.json()
                if "terminalGroupStopLists" in stop_data:
                    for group in stop_data["terminalGroupStopLists"]:
                        for item in group.get("items", []):
                            stop_list_ids.append(item["productId"])

            # 2. Asosiy Menyuni olamiz
            menu_payload = {"organizationId": IIKO_ORGANIZATION_ID}
            async with session.post(f"{BASE_URL}/nomenclature", json=menu_payload, headers=headers) as menu_resp:
                menu_data = await menu_resp.json()
                
                # --- DIAGNOSTIKA UCHUN DATCHIK ---
                print("=== IIKO DIAGNOSTIKA ===")
                print(f"Guruhlar soni: {len(menu_data.get('groups', []))}")
                print(f"Taomlar soni: {len(menu_data.get('products', []))}")
                
                real_menu = {}
                for group in menu_data.get("groups", []):
                    real_menu[group["id"]] = {"name": group["name"], "items": []}
                
                for product in menu_data.get("products", []):
                    if product.get("type") in ["Dish", "Good"]:
                        parent_id = product.get("parentGroup")
                        if parent_id in real_menu:
                            real_menu[parent_id]["items"].append({
                                "id": product["id"],
                                "name": product["name"],
                                "price": product.get("currentPrice", 0) or 0,
                                "desc": product.get("description", "Izoh yo'q") or "Izoh yo'q",
                                "is_stop": product["id"] in stop_list_ids
                            })
                
                eski_soni = len(real_menu)
                real_menu = {k: v for k, v in real_menu.items() if len(v["items"]) > 0}
                print(f"Bo'sh bo'lmagan guruhlar soni: {len(real_menu)} (Jami edi: {eski_soni})")
                print("========================")
                
                CACHE["menu"] = real_menu
                CACHE["time"] = time.time()
                return real_menu
        except Exception as e:
            print(f"Menyuni olishda xatolik: {e}")
            return CACHE["menu"]

# ==========================================
# 3. BUYURTMANI IIKO GA YUBORISH
# ==========================================
async def send_order_to_iiko(order_id: int, phone_number: str, customer_name: str, delivery_type: str, items: list, notes: str):
    token = await get_iiko_token()
    if not token:
        return False, "iiko API kalitlari kiritilmagan."

    order_data = {
        "organizationId": IIKO_ORGANIZATION_ID,
        "terminalGroupId": IIKO_TERMINAL_ID,
        "order": {
            "phone": phone_number,
            "customer": {"name": customer_name},
            "items": items, 
            "comment": f"Bot orqali: #{order_id} | Turi: {delivery_type} | Izoh: {notes}"
        }
    }

    headers = {"Authorization": f"Bearer {token}"}
    async with aiohttp.ClientSession() as session:
        try:
            async with session.post(f"{BASE_URL}/deliveries/create", json=order_data, headers=headers) as resp:
                result = await resp.json()
                if "correlationId" in result:
                    return True, "Muvaffaqiyatli"
                return False, str(result)
        except Exception as e:
            return False, str(e)