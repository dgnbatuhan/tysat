import streamlit as st
import requests
import base64
import pandas as pd
from datetime import datetime, timedelta

# --- 1. AYARLAR VE STİL ---
st.set_page_config(page_title="CXY 3D Üretim Paneli", layout="wide")

st.markdown("""
    <style>
    .printer-card { border-left: 5px solid #00d1b2; background: #1a1a1a; padding: 15px; border-radius: 8px; margin-bottom: 10px; }
    .status-ready { color: #23d160; font-weight: bold; font-size: 0.9em; border: 1px solid #23d160; padding: 2px 5px; border-radius: 4px; }
    .status-printing { color: #209cee; font-weight: bold; font-size: 0.9em; border: 1px solid #209cee; padding: 2px 5px; border-radius: 4px; }
    .status-offline { color: #ff3860; font-weight: bold; font-size: 0.9em; border: 1px solid #ff3860; padding: 2px 5px; border-radius: 4px; }
    .color-dot { height: 12px; width: 12px; border-radius: 50%; display: inline-block; margin-right: 5px; }
    </style>
    """, unsafe_allow_html=True)

# --- 2. API KONFİGÜRASYONU ---
TY_SELLER_ID = st.secrets.get("SELLER_ID", "401517")
TY_API_KEY = st.secrets.get("API_KEY", "")
TY_API_SECRET = st.secrets.get("API_SECRET", "")

CR_TOKEN = "93723387ea968d36080037134506c0bef04a5583b7f8bbd349c545a53a01b449"
CR_UID = "4015175710"
DN_LIST = ["16108425001480", "92927125000C46", "404785280424C2", "99541588005024", 
           "63891925006F30", "73407988005093", "95745025000D7D", "2273122500149E"]

RENK_HARITASI = {
    "Siyah": "#000000", "Beyaz": "#FFFFFF", "Kırmızı": "#FF0000", 
    "Mavi": "#0000FF", "Gri": "#808080", "Altın": "#D4AF37", "Belirsiz": "#444"
}

# --- 3. FONKSİYONLAR ---
def get_machine_logic(dev):
    n_temp = dev.get('nozzleTemp') if dev.get('nozzleTemp') is not None else 0
    b_temp = dev.get('bedTemp') if dev.get('bedTemp') is not None else 0
    is_online = (dev.get('deviceState') == 1) or (n_temp > 0)
    
    p_info = dev.get('printInfo', {}) or {}
    progress = p_info.get('printProgress', 0) if p_info.get('printProgress') is not None else 0
    p_state = p_info.get('printState', 0)

    if not is_online: return "OFFLINE", False
    if progress > 0 or p_state == 2: return f"BASIYOR (%{progress})", False
    return "BOŞTA", True

def get_ty_headers():
    auth_str = f"{TY_API_KEY}:{TY_API_SECRET}"
    encoded = base64.b64encode(auth_str.encode()).decode()
    return {"Authorization": f"Basic {encoded}", "User-Agent": f"{TY_SELLER_ID}-Integration"}

@st.cache_data(ttl=20)
def fetch_data():
    ty_url = f"https://apigw.trendyol.com/integration/order/sellers/{TY_SELLER_ID}/orders"
    ty_orders = []
    try:
        res = requests.get(ty_url, headers=get_ty_headers(), params={"status": "Created,Picking,Invoiced", "size": 30})
        ty_orders = res.json().get("content", [])
    except: pass

    cr_url = "https://www.crealitycloud.com/api/rest/print/cluster/devices/pollState"
    cr_printers = []
    try:
        res = requests.post(cr_url, headers={"__cxy_token_": CR_TOKEN, "__cxy_uid_": CR_UID}, json={"dnList": DN_LIST})
        cr_printers = res.json().get("result", [])
    except: pass
    
    return ty_orders, cr_printers

# --- 4. VERİ YÜKLEME ---
ty_orders, cr_printers = fetch_data()

# --- 5. SIDEBAR: YAZICI İZLEME ---
with st.sidebar:
    st.header("⚙️ Yazıcı Havuzu")
    if st.button("🔄 Anlık Yenile"): st.cache_data.clear(); st.rerun()
    st.divider()

    for dev in cr_printers:
        name = dev.get('aliasName') or dev.get('deviceName')
        status_label, is_available = get_machine_logic(dev)
        
        with st.container():
            c1, c2 = st.columns([2, 1])
            c1.markdown(f"**{name}**")
            
            if status_label == "OFFLINE":
                c2.markdown("<span class='status-offline'>KAPALI</span>", unsafe_allow_html=True)
            elif is_available:
                c2.markdown("<span class='status-ready'>BOŞTA</span>", unsafe_allow_html=True)
            else:
                c2.markdown("<span class='status-printing'>BASIYOR</span>", unsafe_allow_html=True)
            
            st.caption(f"Nozzle: {dev.get('nozzleTemp', 0)}° | Bed: {dev.get('bedTemp', 0)}°")
            if not is_available and "BASIYOR" in status_label:
                prog = dev.get('printInfo', {}).get('printProgress', 0) or 0
                st.progress(int(prog) / 100 if int(prog) <= 100 else 1.0)
            st.divider()

# --- 6. ANA EKRAN ---
st.title("📦 Trendyol & Creality Entegre Panel")
# (Sipariş listeleme kısmı yukarıdaki gibi devam ediyor...)
