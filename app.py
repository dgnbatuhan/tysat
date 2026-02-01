import streamlit as st
import requests
import base64
import pandas as pd
from datetime import datetime, timedelta

# --- 1. AYARLAR VE STİL ---
st.set_page_config(page_title="CXY 3D Üretim Üssü", layout="wide")

st.markdown("""
    <style>
    .printer-card { border-left: 5px solid #00d1b2; background: #1a1a1a; padding: 15px; border-radius: 8px; margin-bottom: 10px; }
    .status-ready { color: #23d160; font-weight: bold; font-size: 0.9em; }
    .status-printing { color: #209cee; font-weight: bold; font-size: 0.9em; }
    .status-offline { color: #ff3860; font-weight: bold; font-size: 0.9em; }
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

def get_ty_headers():
    auth_str = f"{TY_API_KEY}:{TY_API_SECRET}"
    encoded = base64.b64encode(auth_str.encode()).decode()
    return {"Authorization": f"Basic {encoded}", "User-Agent": f"{TY_SELLER_ID}-Integration"}

@st.cache_data(ttl=30)
def fetch_data():
    # Trendyol Siparişleri
    ty_url = f"https://apigw.trendyol.com/integration/order/sellers/{TY_SELLER_ID}/orders"
    ty_orders = []
    try:
        res = requests.get(ty_url, headers=get_ty_headers(), params={"status": "Created,Picking,Invoiced", "size": 30})
        ty_orders = res.json().get("content", [])
    except: pass

    # Creality Makine Durumları
    cr_url = "https://www.crealitycloud.com/api/rest/print/cluster/devices/pollState"
    cr_printers = []
    try:
        res = requests.post(cr_url, headers={"__cxy_token_": CR_TOKEN, "__cxy_uid_": CR_UID}, json={"dnList": DN_LIST})
        cr_printers = res.json().get("result", [])
    except: pass
    
    return ty_orders, cr_printers

def get_machine_logic(dev):
    """Makinelerin boşta mı basıyor mu olduğunu çözen mantık"""
    is_online = dev.get('deviceState') == 1
    p_info = dev.get('printInfo', {})
    progress = p_info.get('printProgress', 0) or 0
    p_state = p_info.get('printState', 0) # 2 genelde printing

    if not is_online: return "OFFLINE", False
    if progress > 0 or p_state == 2: return f"BASIYOR (%{progress})", False
    return "BOŞTA", True

def renk_bul(urun_adi):
    for renk in RENK_HARITASI.keys():
        if renk.lower() in urun_adi.lower(): return renk
    return "Belirsiz"

# --- 4. VERİ YÜKLEME ---
ty_orders, cr_printers = fetch_data()

# --- 5. SIDEBAR: YAZICI İZLEME ---
with st.sidebar:
    st.header("⚙️ Yazıcı Havuzu")
    if st.button("🔄 Manuel Yenile"): st.rerun()
    st.divider()

    for dev in cr_printers:
        dn = dev['deviceName']
        name = dev.get('aliasName') or dn
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
            
            if status_label != "OFFLINE":
                st.caption(f"Nozzle: {dev.get('nozzleTemp')}° | Bed: {dev.get('bedTemp')}°")
                if not is_available:
                    st.progress(int(dev.get('printInfo', {}).get('printProgress', 0)))
            st.divider()

# --- 6. ANA EKRAN: SİPARİŞ ATAMA ---
st.title("📦 Trendyol Üretim Kuyruğu")

if not ty_orders:
    st.info("İşlenecek yeni sipariş bulunamadı.")
else:
    for order in ty_orders:
        customer = f"{order['shipmentAddress']['firstName']} {order['shipmentAddress']['lastName']}"
        
        for line in order.get("lines", []):
            item_id = line['id']
            urun = line['productName']
            renk = renk_bul(urun)
            renk_kod = RENK_HARITASI[renk]
            
            with st.container(border=True):
                col_info, col_action = st.columns([3, 2])
                
                with col_info:
                    st.markdown(f"### {customer}")
                    st.markdown(f"<span class='color-dot' style='background:{renk_kod}'></span> **Renk:** {renk}", unsafe_allow_html=True)
                    st.write(f"🛠️ **Ürün:** {urun}")
                    st.caption(f"Barkod: {line['barcode']} | Sipariş No: {order['orderNumber']}")
                
                with col_action:
                    st.write("🔧 **Makine Ata**")
                    # Sadece BOŞTA olan makineleri filtrele
                    available_machines = {d['deviceName']: (d['aliasName'] or d['deviceName']) 
                                         for d in cr_printers if get_machine_logic(d)[1]}
                    
                    if available_machines:
                        selected_dn = st.selectbox("Uygun Yazıcılar", 
                                                   options=available_machines.keys(), 
                                                   format_func=lambda x: available_machines[x],
                                                   key=f"select_{item_id}")
                        
                        col_btn1, col_btn2 = st.columns(2)
                        if col_btn1.button("Üretime Başla 🚀", key=f"go_{item_id}"):
                            st.toast(f"{available_machines[selected_dn]} için komut gönderildi!")
                            # Buraya Creality StartPrint API'si eklenebilir.
                        
                        # PHP Dosyalarına hızlı link
                        col_btn2.markdown(f"[🎥 Kamera](camera.php?dn={selected_dn})")
                    else:
                        st.error("⚠️ Şu an boşta makine yok. Üretimin bitmesini bekle.")

# --- 7. OTOMATİK YENİLEME ---
# st.empty() kullanarak ufak bir JavaScript ile sayfayı canlı tutabiliriz
# veya Streamlit'in yerleşik auto-refresh özelliğini bekleyebiliriz.
