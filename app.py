import streamlit as st
import requests
import base64
import pandas as pd
from datetime import datetime, timedelta

# --- 1. AYARLAR ---
st.set_page_config(page_title="CXY 3D Fabrika", layout="wide")

st.markdown("""
    <style>
    .printer-card { border-left: 5px solid #00d1b2; background: #1a1a1a; padding: 15px; border-radius: 8px; margin-bottom: 10px; }
    .status-ready { color: #23d160; font-weight: bold; border: 1px solid #23d160; padding: 2px 5px; border-radius: 4px; }
    .status-printing { color: #209cee; font-weight: bold; border: 1px solid #209cee; padding: 2px 5px; border-radius: 4px; }
    .status-offline { color: #ff3860; font-weight: bold; border: 1px solid #ff3860; padding: 2px 5px; border-radius: 4px; }
    .color-dot { height: 12px; width: 12px; border-radius: 50%; display: inline-block; margin-right: 5px; }
    </style>
    """, unsafe_allow_html=True)

# --- 2. API BİLGİLERİ ---
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

# --- 3. GÜVENLİ MANTIK FONKSİYONU ---
def get_machine_logic(dev):
    # Sıcaklık verilerini çek ve sayıya çevir (Hata almamak için float() kullanıyoruz)
    try:
        n_temp = float(dev.get('nozzleTemp', 0) or 0)
        b_temp = float(dev.get('bedTemp', 0) or 0)
    except:
        n_temp, b_temp = 0, 0

    # Makine Online mı? (Durum 1 ise VEYA sıcaklık varsa)
    is_online = (dev.get('deviceState') == 1) or (n_online := n_temp > 0) or (b_temp > 0)
    
    # Yazdırma bilgilerini çek
    p_info = dev.get('printInfo') or {}
    progress = p_info.get('printProgress', 0) or 0
    p_state = p_info.get('printState', 0)

    if not is_online:
        return "OFFLINE", False
    
    # Baskıda mı?
    if progress > 0 or p_state == 2:
        return f"BASIYOR (%{progress})", False
        
    return "BOŞTA", True

# --- 4. VERİ ÇEKME ---
def get_ty_headers():
    auth_str = f"{TY_API_KEY}:{TY_API_SECRET}"
    encoded = base64.b64encode(auth_str.encode()).decode()
    return {"Authorization": f"Basic {encoded}", "User-Agent": f"{TY_SELLER_ID}-Integration"}

@st.cache_data(ttl=20)
def fetch_all_data():
    # Trendyol
    ty_orders = []
    try:
        res = requests.get(f"https://apigw.trendyol.com/integration/order/sellers/{TY_SELLER_ID}/orders", 
                           headers=get_ty_headers(), params={"status": "Created,Picking,Invoiced", "size": 30})
        ty_orders = res.json().get("content", [])
    except: pass

    # Creality
    cr_printers = []
    try:
        res = requests.post("https://www.crealitycloud.com/api/rest/print/cluster/devices/pollState", 
                            headers={"__cxy_token_": CR_TOKEN, "__cxy_uid_": CR_UID}, json={"dnList": DN_LIST})
        cr_printers = res.json().get("result", [])
    except: pass
    
    return ty_orders, cr_printers

ty_orders, cr_printers = fetch_all_data()

# --- 5. SIDEBAR: MAKİNELER ---
with st.sidebar:
    st.header("🤖 Makineler")
    if st.button("🔄 Yenile"): st.cache_data.clear(); st.rerun()
    
    for dev in cr_printers:
        name = dev.get('aliasName') or dev.get('deviceName')
        status_label, is_ready = get_machine_logic(dev)
        
        with st.container(border=True):
            col1, col2 = st.columns([2, 1])
            col1.write(f"**{name}**")
            
            if status_label == "OFFLINE":
                col2.markdown("<span class='status-offline'>KAPALI</span>", unsafe_allow_html=True)
            elif is_ready:
                col2.markdown("<span class='status-ready'>BOŞTA</span>", unsafe_allow_html=True)
            else:
                col2.markdown("<span class='status-printing'>BASIYOR</span>", unsafe_allow_html=True)
            
            n_t = dev.get('nozzleTemp', 0) or 0
            b_t = dev.get('bedTemp', 0) or 0
            st.caption(f"🌡️ {n_t}°C / {b_t}°C")

# --- 6. ANA PANEL: SİPARİŞLER ---
st.title("📦 Üretim ve Sipariş Takibi")

if not ty_orders:
    st.info("Yeni sipariş yok.")
else:
    for order in ty_orders:
        customer = f"{order['shipmentAddress']['firstName']} {order['shipmentAddress']['lastName']}"
        for line in order.get("lines", []):
            urun = line['productName']
            renk = next((r for r in RENK_HARITASI.keys() if r.lower() in urun.lower()), "Belirsiz")
            
            with st.container(border=True):
                c_inf, c_act = st.columns([3, 2])
                with c_inf:
                    st.markdown(f"**{customer}**")
                    st.markdown(f"<span class='color-dot' style='background:{RENK_HARITASI[renk]}'></span> {renk} - {urun[:50]}...")
                
                with c_act:
                    # Sadece MÜSAİT olanları göster
                    müsaitler = {d['deviceName']: (d['aliasName'] or d['deviceName']) 
                                 for d in cr_printers if get_machine_logic(d)[1]}
                    
                    if müsaitler:
                        selected = st.selectbox("Makine Seç", müsaitler.keys(), format_func=lambda x: müsaitler[x], key=f"s_{line['id']}")
                        if st.button("Ata 🚀", key=f"b_{line['id']}"):
                            st.success(f"{müsaitler[selected]} atandı!")
                    else:
                        st.warning("Boş makine yok.")
