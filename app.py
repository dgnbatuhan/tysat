import streamlit as st
import requests
import base64
import pandas as pd
from datetime import datetime, timedelta

# --- SAYFA AYARLARI ---
st.set_page_config(page_title="3D Yazıcı Üretim Paneli", layout="wide")

# --- CSS: Makine Kartları İçin ---
st.markdown("""
    <style>
    .printer-card {
        border: 2px solid #4B4B4B;
        border-radius: 10px;
        padding: 10px;
        background-color: #262730;
        margin-bottom: 10px;
    }
    .color-indicator {
        height: 20px;
        width: 20px;
        border-radius: 50%;
        display: inline-block;
        margin-right: 10px;
        border: 1px solid white;
    }
    </style>
    """, unsafe_allow_html=True)

# --- API BİLGİLERİ (Secrets'tan gelir) ---
SELLER_ID = st.secrets["SELLER_ID"]
API_KEY = st.secrets["API_KEY"]
API_SECRET = st.secrets["API_SECRET"]

# --- SABİTLER ---
MAKINE_SAYISI = 8
RENK_HARITASI = {
    "Siyah": "#000000", "Beyaz": "#FFFFFF", "Kırmızı": "#FF0000", 
    "Mavi": "#0000FF", "Gri": "#808080", "Altın": "#D4AF37"
}

# --- SESSION STATE (Üretim Takibi) ---
if "makine_durumu" not in st.session_state:
    st.session_state.makine_durumu = {f"Makine {i+1}": {"is": None, "renk": "Boş"} for i in range(MAKINE_SAYISI)}

# --- YARDIMCI FONKSİYONLAR ---
def get_auth_header():
    auth_str = f"{API_KEY}:{API_SECRET}"
    encoded_auth = base64.b64encode(auth_str.encode()).decode()
    return {"Authorization": f"Basic {encoded_auth}", "User-Agent": f"{SELLER_ID}-Integration"}

def renk_bul(urun_adi):
    """Ürün adından renk tahmin eder"""
    for renk in RENK_HARITASI.keys():
        if renk.lower() in urun_adi.lower():
            return renk
    return "Belirsiz"

@st.cache_data(ttl=60)
def fetch_orders(status):
    end_dt = datetime.now()
    start_dt = end_dt - timedelta(days=3)
    url = f"https://apigw.trendyol.com/integration/order/sellers/{SELLER_ID}/orders"
    params = {"status": status, "startDate": int(start_dt.timestamp() * 1000), "endDate": int(end_dt.timestamp() * 1000)}
    try:
        response = requests.get(url, headers=get_auth_header(), params=params)
        return response.json().get("content", []) if response.status_code == 200 else []
    except: return []

# --- SIDEBAR: MAKİNE DURUMLARI (ANLIK) ---
with st.sidebar:
    st.header("🤖 Makinelerin Durumu")
    for m_name, m_info in st.session_state.makine_durumu.items():
        with st.container():
            st.markdown(f"**{m_name}**")
            if m_info["is"]:
                st.caption(f"🔥 Çalışıyor: {m_info['is']}")
                st.markdown(f"<span class='color-indicator' style='background-color:{RENK_HARITASI.get(m_info['renk'], '#444')}'></span> {m_info['renk']}", unsafe_allow_html=True)
                if st.button(f"Bitir", key=f"finish_{m_name}"):
                    st.session_state.makine_durumu[m_name] = {"is": None, "renk": "Boş"}
                    st.rerun()
            else:
                st.success("✅ Müsait")
            st.divider()

# --- ANA PANEL ---
st.title("🚀 3D Yazıcı Üretim & Sipariş Otomasyonu")

# Verileri Çek
orders = fetch_orders("Created,Picking,Invoiced")

# --- ÖZET METRİKLER ---
c1, c2, c3 = st.columns(3)
c1.metric("Bekleyen Toplam Sipariş", len(orders))
c2.metric("Dolu Makine", sum(1 for v in st.session_state.makine_durumu.values() if v["is"]))
c3.metric("Boş Makine", MAKINE_SAYISI - sum(1 for v in st.session_state.makine_durumu.values() if v["is"]))

st.divider()

# --- SİPARİŞ ATAMA ALANI ---
st.subheader("📋 Üretim Bekleyenler")

if orders:
    for o in orders:
        customer = f"{o.get('shipmentAddress', {}).get('firstName','')} {o.get('shipmentAddress', {}).get('lastName','')}"
        for line in o.get("lines", []):
            urun = line.get("productName")
            renk = renk_bul(urun)
            
            with st.expander(f"📦 {urun} - ({customer})", expanded=True):
                col_info, col_assign = st.columns([3, 2])
                
                with col_info:
                    st.write(f"**Müşteri:** {customer}")
                    st.write(f"**Renk:** {renk}")
                    # G-Code Eşleştirme (Burada barkoda göre bir sözlükten gcode ismi çekebilirsiniz)
                    st.warning(f"📄 G-Code: {line.get('barcode')}.gcode")
                
                with col_assign:
                    # Sadece boş makineleri listele
                    available_machines = [m for m, v in st.session_state.makine_durumu.items() if v["is"] is None]
                    
                    if available_machines:
                        selected_m = st.selectbox("Makine Seç", available_machines, key=f"sel_{line.get('id')}")
                        if st.button("Üretime Gönder 🚀", key=f"btn_{line.get('id')}"):
                            # Makineyi doldur
                            st.session_state.makine_durumu[selected_m] = {
                                "is": f"{customer} - {urun[:20]}...",
                                "renk": renk
                            }
                            st.toast(f"{selected_m} üzerine iş atandı!")
                            st.rerun()
                    else:
                        st.error("Tüm makineler dolu!")
else:
    st.info("Şu an üretim bekleyen yeni sipariş bulunamadı.")
