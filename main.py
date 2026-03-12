#!/usr/bin/env python3
"""
WAR OTP WhatsApp - API History Checker
Ambil langsung dari API hero-sms.com - cek history pembelian dan SMS yang masuk
"""

import requests
import json
import time
from typing import List, Dict, Optional
from datetime import datetime
import threading

# ============================================================================
# KONFIGURASI
# ============================================================================

HEROSMS_API_KEY = ""
TELEGRAM_BOT_TOKEN = ""
TELEGRAM_CHAT_ID = ""

HEROSMS_BASE_URL = "https://hero-sms.com/stubs/handler_api.php"
SERVICE_CODE = "wa"  # WhatsApp
MAX_PRICE = 0.23

# ============================================================================
# DAFTAR NEGARA
# ============================================================================

COUNTRIES_DATA = [
    {"id": 6, "name": "Indonesia", "code": "+62", "hero_id": 6},
    {"id": 36, "name": "Canada", "code": "+1", "hero_id": 36},
    {"id": 4, "name": "Philippines", "code": "+63", "hero_id": 4},
    {"id": 33, "name": "Colombia", "code": "+57", "hero_id": 33},
    {"id": 16, "name": "United Kingdom", "code": "+44", "hero_id": 16},
    {"id": 73, "name": "Brazil", "code": "+55", "hero_id": 73},
    {"id": 10, "name": "Vietnam", "code": "+84", "hero_id": 10},
    {"id": 52, "name": "Thailand", "code": "+66", "hero_id": 52},
    {"id": 37, "name": "Morocco", "code": "+212", "hero_id": 37},
    {"id": 31, "name": "South Africa", "code": "+27", "hero_id": 31},
    {"id": 48, "name": "Netherlands", "code": "+31", "hero_id": 48},
    {"id": 117, "name": "Portugal", "code": "+351", "hero_id": 117},
    {"id": 43, "name": "Germany", "code": "+49", "hero_id": 43},
    {"id": 46, "name": "Sweden", "code": "+46", "hero_id": 46},
    {"id": 187, "name": "USA", "code": "+1", "hero_id": 187},
    {"id": 151, "name": "Chile", "code": "+56", "hero_id": 151},
    {"id": 54, "name": "Mexico", "code": "+52", "hero_id": 54},
    {"id": 7, "name": "Malaysia", "code": "+60", "hero_id": 7},
    {"id": 56, "name": "Spain", "code": "+34", "hero_id": 56},
    {"id": 39, "name": "Argentina", "code": "+54", "hero_id": 39},
    {"id": 62, "name": "Turkey", "code": "+90", "hero_id": 62},
    {"id": 78, "name": "France", "code": "+33", "hero_id": 78},
    {"id": 14, "name": "Hong Kong", "code": "+852", "hero_id": 14},
    {"id": 8, "name": "Kenya", "code": "+254", "hero_id": 8},
    {"id": 182, "name": "Japan", "code": "+81", "hero_id": 182},
]

class HeroSMSClient:
    """Client untuk API hero-sms.com"""
    
    def __init__(self, api_key: str):
        self.api_key = api_key
        self.base_url = HEROSMS_BASE_URL
        self.last_checked_id = 0
    
    def get_balance(self) -> Optional[float]:
        """Ambil balance"""
        try:
            params = {
                "action": "getBalance",
                "api_key": self.api_key
            }
            resp = requests.get(self.base_url, params=params, timeout=10)
            text = resp.text.strip()
            
            if text.startswith("ACCESS_BALANCE:"):
                balance_str = text.split(":")[1]
                return float(balance_str)
            return None
        except:
            return None
    
    def buy_number(self, country_id: int) -> Optional[Dict]:
        """Beli nomor WhatsApp"""
        try:
            url = f"{self.base_url}?action=getNumberV2&service={SERVICE_CODE}&country={country_id}&maxPrice={MAX_PRICE}&api_key={self.api_key}"
            resp = requests.get(url, timeout=10)
            text = resp.text.strip()
            
            try:
                data = json.loads(text)
                if isinstance(data, dict) and "activationId" in data and "phoneNumber" in data:
                    return {
                        "activationId": str(data["activationId"]),
                        "phoneNumber": str(data["phoneNumber"]),
                        "cost": float(data.get("activationCost", MAX_PRICE)),
                    }
            except:
                if text.startswith("ACCESS_NUMBER:"):
                    parts = text.split(":")
                    if len(parts) >= 3:
                        return {
                            "activationId": parts[1],
                            "phoneNumber": parts[2],
                            "cost": MAX_PRICE,
                        }
            
            return None
                
        except:
            return None
    
    def get_activation_status(self, activation_id: str) -> Optional[Dict]:
        """Cek status aktivasi (dengan SMS code jika ada)"""
        try:
            params = {
                "action": "getStatus",
                "id": activation_id,
                "api_key": self.api_key
            }
            resp = requests.get(self.base_url, params=params, timeout=10)
            text = resp.text.strip()
            
            if text.startswith("STATUS_OK:"):
                code = text.split(":")[1]
                return {"status": "OK", "code": code}
            elif text == "STATUS_WAIT_CODE":
                return {"status": "WAITING", "code": None}
            else:
                return {"status": text, "code": None}
        except:
            return None
    
    def get_active_activations(self) -> Optional[List[Dict]]:
        """Ambil semua aktivasi yang sedang berjalan dari API"""
        try:
            params = {
                "action": "getActiveActivations",
                "api_key": self.api_key
            }
            resp = requests.get(self.base_url, params=params, timeout=10)
            text = resp.text.strip()
            
            if text.startswith("ERROR"):
                return []
            
            # Parse format: id:phoneNumber:status:smsCode|id:phoneNumber:status:smsCode|...
            activations = []
            if text and text != "ERROR_NO_ACTIVATIONS":
                for line in text.split("|"):
                    if not line.strip():
                        continue
                    
                    parts = line.split(":")
                    if len(parts) >= 3:
                        act_id = parts[0]
                        phone = parts[1]
                        status = parts[2]
                        code = parts[3] if len(parts) > 3 else None
                        
                        activations.append({
                            "id": act_id,
                            "phone": phone,
                            "status": status,
                            "code": code
                        })
            
            return activations
        except:
            return []

class TelegramNotifier:
    """Notifikasi ke Telegram"""
    
    def __init__(self, bot_token: str, chat_id: str):
        self.bot_token = bot_token
        self.chat_id = chat_id
    
    def send_message(self, text: str, parse_mode: str = "HTML") -> bool:
        """Kirim pesan ke Telegram"""
        try:
            url = f"https://api.telegram.org/bot{self.bot_token}/sendMessage"
            data = {
                "chat_id": self.chat_id,
                "text": text,
                "parse_mode": parse_mode
            }
            resp = requests.post(url, json=data, timeout=10)
            return resp.status_code == 200
        except:
            return False

def monitor_api_history_thread(herosms: HeroSMSClient, telegram: TelegramNotifier, stop_event: threading.Event):
    """Thread untuk cek history API dan kirim SMS yang masuk ke Telegram"""
    last_sent_ids = set()
    
    while not stop_event.is_set():
        try:
            # Ambil aktivasi aktif dari API
            activations = herosms.get_active_activations()
            
            if activations:
                for activation in activations:
                    act_id = activation['id']
                    phone = activation['phone']
                    status = activation['status']
                    code = activation['code']
                    
                    # Jika ada SMS code dan belum dikirim ke Telegram
                    if code and act_id not in last_sent_ids:
                        print(f"\n📬 SMS MASUK: {phone} -> {code}")
                        telegram.send_message(f"📬 <b>SMS Received!</b>\n\n📱 {phone}\n🔐 Code: <code>{code}</code>\n🆔 ID: <code>{act_id}</code>\n⏰ Time: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
                        last_sent_ids.add(act_id)
            
            time.sleep(5)
        except:
            time.sleep(5)

def print_all_countries():
    """Tampilkan daftar negara"""
    print("\n" + "="*80)
    print("📍 DAFTAR SEMUA NEGARA".center(80))
    print("="*80)
    print(f"\n{'ID':<5} {'Negara':<20} {'Kode':<8}")
    print("-"*80)
    
    for country in COUNTRIES_DATA:
        print(f"{country['id']:<5} {country['name']:<20} {country['code']:<8}")
    
    print("\n" + "="*80 + "\n")

def show_api_history(herosms: HeroSMSClient):
    """Tampilkan history dari API"""
    print("\n💾 Mengambil data dari API hero-sms.com...\n")
    
    activations = herosms.get_active_activations()
    
    if not activations:
        print("Tidak ada aktivasi yang sedang berjalan\n")
        return
    
    print("="*100)
    print("📊 AKTIVASI YANG SEDANG BERJALAN (dari API)".center(100))
    print("="*100)
    print(f"\n{'ID':<15} {'Nomor':<20} {'Status':<15} {'SMS Code':<20} {'Waktu':<20}")
    print("-"*100)
    
    for activation in activations:
        act_id = activation['id']
        phone = activation['phone']
        status = activation['status']
        code = activation['code'] or "-"
        
        print(f"{act_id:<15} {phone:<20} {status:<15} {code:<20} {datetime.now().strftime('%Y-%m-%d %H:%M:%S'):<20}")
    
    print("\n" + "="*100 + "\n")

def main():
    """Main function"""
    print("\n" + "="*80)
    print("⚡ WAR OTP WhatsApp - API History Mode".center(80))
    print("="*80)
    
    # Setup clients
    herosms = HeroSMSClient(HEROSMS_API_KEY)
    telegram = TelegramNotifier(TELEGRAM_BOT_TOKEN, TELEGRAM_CHAT_ID)
    
    # Start monitor thread
    stop_event = threading.Event()
    monitor_thread = threading.Thread(
        target=monitor_api_history_thread,
        args=(herosms, telegram, stop_event),
        daemon=True
    )
    monitor_thread.start()
    
    while True:
        print("\n📋 MENU:")
        print("1. 📍 Lihat daftar negara")
        print("2. 💰 Cek balance")
        print("3. 🚀 Mulai SPAM BUY OTP")
        print("4. 📊 Lihat history API (aktivasi berjalan)")
        print("5. ❌ Exit")
        print()
        
        choice = input("Pilih menu (1-5): ").strip()
        
        if choice == "1":
            print_all_countries()
        
        elif choice == "2":
            print("\n💰 Mengecek balance...")
            balance = herosms.get_balance()
            if balance is not None:
                print(f"✅ Balance Anda: ${balance:.4f}\n")
            else:
                print("❌ Gagal cek balance\n")
        
        elif choice == "3":
            # Input target countries
            while True:
                try:
                    target_input = input("\n📌 Masukkan Country ID (pisahkan dengan koma):\nContoh: 4,10,182\nInput: ").strip()
                    target_ids = [int(x.strip()) for x in target_input.split(",") if x.strip()]
                    
                    if not target_ids:
                        print("❌ Tidak ada Country ID!")
                        continue
                    
                    break
                except ValueError:
                    print("❌ Error: Country ID harus angka!")
                    continue
            
            # Validasi country ID
            target_countries = []
            for cid in target_ids:
                for country in COUNTRIES_DATA:
                    if country['id'] == cid:
                        target_countries.append(country)
                        break
            
            if not target_countries:
                print("❌ Tidak ada country yang valid!\n")
                continue
            
            # Display target
            print("\n" + "="*80)
            print("🎯 TARGET NEGARA".center(80))
            print("="*80)
            print(f"\n{'Negara':<20} {'Kode':<8}")
            print("-"*80)
            for country in target_countries:
                print(f"{country['name']:<20} {country['code']:<8}")
            print("="*80)
            
            # Check balance
            print("\n💰 Mengecek balance...")
            initial_balance = herosms.get_balance()
            if initial_balance is None:
                print("❌ Gagal cek balance\n")
                continue
            
            print(f"✅ Balance: ${initial_balance:.4f}\n")
            print("⚠️  PERINGATAN:")
            print("Script akan SPAM BUY sampai balance habis!")
            print("History otomatis diambil dari API\n")
            
            confirm = input("Lanjutkan? (yes/no): ").strip().lower()
            
            if confirm == 'yes':
                print("\n" + "="*80)
                print("⚡ SPAM BUY DIMULAI (API History Mode)".center(80))
                print("="*80 + "\n")
                
                telegram.send_message(f"⚡ <b>SPAM BUY Dimulai</b>\n\n💰 Balance: ${initial_balance:.4f}\n🎯 Target: {', '.join([c['name'] for c in target_countries])}\n⚡ Mode: API History - SMS akan dikirim otomatis saat masuk")
                
                total_spent = 0.0
                total_purchases = 0
                purchases_by_country = {c['name']: 0 for c in target_countries}
                round_num = 0
                
                try:
                    while True:
                        round_num += 1
                        
                        # Check balance
                        current_balance = herosms.get_balance()
                        if current_balance is None:
                            print("⚠️  Koneksi hilang...")
                            time.sleep(5)
                            continue
                        
                        if current_balance < 0.05:
                            print(f"\n⛔ Balance habis! (Sisa: ${current_balance:.4f})")
                            break
                        
                        print(f"[R{round_num}]", end="", flush=True)
                        round_purchases = 0
                        
                        for country in target_countries:
                            current_balance = herosms.get_balance()
                            if current_balance is None or current_balance < 0.05:
                                break
                            
                            # SPAM BUY 50x tanpa delay
                            for attempt in range(50):
                                result = herosms.buy_number(country['hero_id'])
                                
                                if result:
                                    phone = result['phoneNumber']
                                    cost = result['cost']
                                    act_id = result['activationId']
                                    
                                    total_spent += cost
                                    total_purchases += 1
                                    purchases_by_country[country['name']] += 1
                                    round_purchases += 1
                                    
                                    print(f"✅{country['name'][:3]}", end="", flush=True)
                                    
                                    # Telegram async
                                    threading.Thread(target=lambda p=phone, c=country['name']: telegram.send_message(f"✅ <b>OTP Acquired!</b>\n\n📱 {c}: <code>{p}</code>\n💵 Cost: ${cost:.4f}\n⏰ Time: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}"), daemon=True).start()
                                    break
                        
                        print()
                
                except KeyboardInterrupt:
                    print("\n\n⚠️  Program dihentikan!")
                    print("Monitor SMS tetap berjalan di background\n")
                
                # Summary
                final_balance = herosms.get_balance()
                if final_balance is None:
                    final_balance = current_balance
                
                print("\n" + "="*80)
                print("📊 RINGKASAN".center(80))
                print("="*80)
                print(f"Initial Balance:        ${initial_balance:.4f}")
                print(f"Total Pengeluaran:      ${total_spent:.4f}")
                print(f"Final Balance:          ${final_balance:.4f}")
                print(f"Total Pembelian:        {total_purchases}")
                
                print(f"\nPembelian per negara:")
                for country_name, count in purchases_by_country.items():
                    if count > 0:
                        print(f"  • {country_name:<20} : {count} OTP")
                
                print("="*80)
                print(f"\n⏳ Monitor API berjalan di background")
                print("   SMS akan otomatis dikirim ke Telegram saat masuk\n")
                
                telegram.send_message(f"⛔ <b>SPAM BUY Selesai</b>\n\n💰 Initial: ${initial_balance:.4f}\n💸 Spent: ${total_spent:.4f}\n💰 Final: ${final_balance:.4f}\n📊 Total: {total_purchases} OTP\n\n⏳ Monitor SMS tetap aktif")
            
            else:
                print("❌ Dibatalkan\n")
        
        elif choice == "4":
            show_api_history(herosms)
        
        elif choice == "5":
            print("\n👋 Terima kasih! Program selesai.\n")
            stop_event.set()
            break
        
        else:
            print("❌ Menu tidak valid!\n")

if __name__ == "__main__":
    main()
