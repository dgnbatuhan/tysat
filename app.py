import streamlit as st
import requests
import base64
import pandas as pd
from datetime import datetime, timedelta

# --- 1. SAYFA AYARLARI & CSS ---
st.set_page_config(page_title="3D Fabrika Üretim Merkezi", layout="wide")

st.markdown("""
    <style>
    .printer-card { border: 1px solid #444; border-radius: 10px; padding: 15px; background: #1e1e1e; margin-bottom: 10px; }
    .status-on { color: #23d160; font-weight: bold; }
    .status-off { color: #ff3860; font-weight: bold; }
    .color-dot { height: 12px; width: 12px; border-radius: 50%; display: inline-block; margin-right: 5px; }
    </style>
    """, unsafe_allow_html=True)

# --- 2. API SABİTLERİ (Secrets'tan Alınır) ---
# Trendyol
TY_SELLER_ID = st.secrets["SELLER_ID"]
TY_API_KEY = st.secrets["API_KEY"]
TY_API_SECRET = st.secrets["API_SECRET"]
# Creality
CR_TOKEN = "93723387ea968d36080037134506c0bef04a5583b7f8bbd349c545a53a01b449"
CR_UID = "4015175710"
DN_LIST = ["16108425001480", "92927125000C46", "404785280424C2", "99541588005024", 
           "63891925006F30", "73407988005093", "95745025000D7D", "2273122500149E"]

RENK_HARITASI = {
    "Siyah": "#000000", "Beyaz": "#FFFFFF", "Kırmızı": "#FF0000", 
    "Mavi": "#0000FF", "Gri": "#808080", "Altın": "#D4AF37", "Belirsiz": "#444"
}

# --- 3. VERİ ÇEKME FONKSİYONLARI ---

def get_ty_headers():
    auth_str = f"{TY_API_KEY}:{TY_API_SECRET}"
    encoded = base64.b64encode(auth_str.encode()).decode()
    return {"Authorization": f"Basic {encoded}", "User-Agent": f"{TY_SELLER_ID}-Integration"}

@st.cache_data(ttl=60)
def fetch_ty_orders():
    url = f"https://apigw.trendyol.com/integration/order/sellers/{TY_SELLER_ID}/orders"
    params = {"status": "Created,Picking,Invoiced", "size": 50}
    try:
        res = requests.get(url, headers=get_ty_headers(), params=params)
        return res.json().get("content", [])
    except: return []

def fetch_creality_status():
    url = "https://www.crealitycloud.com/api/rest/print/cluster/devices/pollState"
    headers = {"Content-Type": "application/json", "__cxy_token_": CR_TOKEN, "__cxy_uid_": CR_UID}
    try:
        res = requests.post(url, headers=headers, json={"dnList": DN_LIST})
        return res.json().get("result", [])
    except: return []

def renk_bul(urun_adi):
    for renk in RENK_HARITASI.keys():
        if renk.lower() in urun_adi.lower(): return renk
    return "Belirsiz"

# --- 4. SESSION STATE ---
if "assigned_tasks" not in st.session_state:
    st.session_state.assigned_tasks = {} # {DN: {"customer": x, "product": y}}

# --- 5. SOL PANEL: GERÇEK MAKİNE DURUMLARI ---
printers = fetch_creality_status()

with st.sidebar:
    st.title("🤖 Yazıcı Çiftliği")
    if st.button("🔄 Verileri Tazele"): st.rerun()
    st.divider()
    
    for dev in printers:
        dn = dev['deviceName']
        name = dev['aliasName'] or dn
        is_online = dev['deviceState'] == 1
        p_info = dev.get('printInfo', {})
        prog = p_info.get('printProgress', 0)
        
        with st.container(border=True):
            col_s1, col_s2 = st.columns([3, 1])
            status_text = "ÇEVRİMİÇİ" if is_online else "ÇEVRİMDIŞI"
            status_cls = "status-on" if is_online else "status-off"
            col_s1.markdown(f"**{name}**")
            col_s2.markdown(f"<span class='{status_cls}'>{status_text}</span>", unsafe_allow_html=True)
            
            if is_online:
                st.caption(f"🌡️ N: {dev['nozzleTemp']}°C | B: {dev['bedTemp']}°C")
                if prog > 0:
                    st.progress(prog / 100)
                    st.caption(f"⌛ Baskıda: {p_info.get('modelName', '')[:20]}... (%{prog})")
                else:
                    st.success("💎 Müsait - İş Bekliyor")
                
                # Manuel İş Bitirme (Eğer sistem dışı atandıysa)
                if dn in st.session_state.assigned_tasks:
                    task = st.session_state.assigned_tasks[dn]
                    st.info(f"📌 Atanan: {task['customer']}")
                    if st.button("İşi Temizle", key=f"clr_{dn}"):
                        del st.session_state.assigned_tasks[dn]
                        st.rerun()

# --- 6. ANA PANEL: TRENDYOL SİPARİŞLERİ ---
st.title("🚀 Üretim Yönlendirme Paneli")
orders = fetch_ty_orders()

col_main, col_stats = st.columns([3, 1])

with col_stats:
    st.subheader("📊 Özet")
    st.metric("Bekleyen Sipariş", len(orders))
    online_count = sum(1 for d in printers if d['deviceState'] == 1)
    st.metric("Aktif Makineler", f"{online_count}/{len(DN_LIST)}")

with col_main:
    st.subheader("📋 Bekleyen Üretimler")
    if not orders:
        st.info("Yeni sipariş bulunamadı.")
    else:
        for o in orders:
            customer = f"{o['shipmentAddress']['firstName']} {o['shipmentAddress']['lastName']}"
            order_id = o['orderNumber']
            
            for line in o.get("lines", []):
                item_id = line['id']
                urun = line['productName']
                renk = renk_bul(urun)
                renk_kod = RENK_HARITASI.get(renk, "#444")
                
                with st.expander(f"📦 {customer} - {urun[:40]}...", expanded=True):
                    c1, c2, c3 = st.columns([2, 2, 2])
                    
                    with c1:
                        st.markdown(f"<span class='color-dot' style='background:{renk_kod}'></span> **Renk:** {renk}", unsafe_allow_html=True)
                        st.write(f"**Barkod:** `{line['barcode']}`")
                    
                    with c2:
                        # Sadece Online ve Baskıda Olmayan Makineleri Getir
                        available = [d for d in printers if d['deviceState'] == 1 and d.get('printInfo', {}).get('printProgress', 0) == 0]
                        options = {d['deviceName']: (d['aliasName'] or d['deviceName']) for d in available}
                        
                        if options:
                            target_dn = st.selectbox("Yazıcı Seç", options.keys(), format_func=lambda x: options[x], key=f"sel_{item_id}")
                        else:
                            st.warning("Boş makine yok!")
                    
                    with c3:
                        if options and st.button("Üretime Gönder 🚀", key=f"btn_{item_id}"):
                            # Session state'e kaydet (Takip için)
                            st.session_state.assigned_tasks[target_dn] = {"customer": customer, "product": urun}
                            st.toast(f"İş {options[target_dn]} makinesine atandı!")
                            # NOT: Gerçekten yazıcıyı başlatmak için buraya Creality StartPrint API isteği eklenebilir.
                            st.rerun()
