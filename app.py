import streamlit as st
import requests
import base64
import pandas as pd
from datetime import datetime, timedelta

# --- SAYFA AYARLARI ---
st.set_page_config(page_title="Trendyol Sipariş Paneli", layout="wide")

# --- API BİLGİLERİ ---
SELLER_ID = st.secrets["SELLER_ID"]
API_KEY = st.secrets["API_KEY"]
API_SECRET = st.secrets["API_SECRET"]

# --- AUTH HEADER ---
def get_auth_header():
    auth_str = f"{API_KEY}:{API_SECRET}"
    encoded_auth = base64.b64encode(auth_str.encode()).decode()
    return {"Authorization": f"Basic {encoded_auth}", "User-Agent": f"{SELLER_ID}-Integration"}

# --- SİPARİŞ ÇEKME ---
@st.cache_data(ttl=10)
def fetch_orders(status):
    end_dt = datetime.now()
    start_dt = end_dt - timedelta(days=15) # Aralığı biraz genişlettik
    url = f"https://apigw.trendyol.com/integration/order/sellers/{SELLER_ID}/orders"
    params = {
        "status": status,
        "startDate": int(start_dt.timestamp() * 1000),
        "endDate": int(end_dt.timestamp() * 1000),
        "size": 200
    }
    try:
        response = requests.get(url, headers=get_auth_header(), params=params)
        return response.json().get("content", []) if response.status_code == 200 else []
    except:
        return []

# --- SESSION STATE (Hazır Paket Takibi İçin) ---
if "ready_packages" not in st.session_state:
    st.session_state.ready_packages = []

# --- SIDEBAR (HAZIR PAKETLER LİSTESİ) ---
with st.sidebar:
    st.header("✅ Hazır Paketler")
    if st.session_state.ready_packages:
        for p in st.session_state.ready_packages:
            st.success(f"📦 {p}")
        if st.button("🗑️ Listeyi Temizle"):
            st.session_state.ready_packages = []
            st.rerun()
    else:
        st.info("Henüz işaretlenmiş paket yok.")
    
    st.divider()
    if st.button("🔄 Verileri Yenile", use_container_width=True):
        st.cache_data.clear()
        st.rerun()

# --- ANA BAŞLIK ---
st.title("📦 Trendyol Sipariş Yönetim Paneli")

tab_new, tab_processing = st.tabs(["🆕 Yeni Gelenler (Özet)", "🛠️ İşleme Alınanlar"])

# -------------------------------------------------
# 1. SEKME: YENİ GELENLER (ÖZET GÖRÜNÜM)
# -------------------------------------------------
with tab_new:
    new_orders = fetch_orders("Created")
    if new_orders:
        new_list = []
        for o in new_orders:
            for l in o.get("lines", []):
                new_list.append({
                    "Ürün": l.get("productName"),
                    "Barkod": l.get("barcode"),
                    "Adet": l.get("quantity")
                })
        
        df_new = pd.DataFrame(new_list)
        summary_new = df_new.groupby(["Ürün", "Barkod"]).agg(Toplam=("Adet", "sum"), Siparis_Sayisi=("Adet", "count")).reset_index()
        
        st.subheader(f"📢 Toplam {summary_new['Toplam'].sum()} Ürün Bekliyor")
        
        for _, row in summary_new.iterrows():
            with st.container(border=True):
                c1, c2 = st.columns([4, 1])
                c1.write(f"**{row['Ürün']}**")
                c1.caption(f"Barkod: {row['Barkod']}")
                c2.subheader(f"{row['Toplam']} Adet")
    else:
        st.info("Yeni gelen sipariş yok.")

# -------------------------------------------------
# 2. SEKME: İŞLEME ALINANLAR (DETAY + CHECKBOX)
# -------------------------------------------------
with tab_processing:
    orders = fetch_orders("Picking,Invoiced")
    st.subheader(f"🛠️ Paketlenecek Siparişler ({len(orders)})")

    if orders:
        single_items = []
        multi_items = []

        for order in orders:
            customer = f"{order.get('shipmentAddress', {}).get('firstName','')} {order.get('shipmentAddress', {}).get('lastName','')}"
            lines = order.get("lines", [])
            status = order.get("status")
            badge = "🔵 Hazırlanıyor" if status == "Picking" else "🟢 Faturalandı"
            
            if len(lines) == 1:
                line = lines[0]
                single_items.append({
                    "Ürün": line.get("productName"),
                    "Barkod": line.get("barcode"),
                    "Adet": line.get("quantity"),
                    "Müşteri": customer,
                    "Statü": badge
                })
            else:
                package_summary = " + ".join([f"{i.get('quantity')} x {i.get('productName')}" for i in lines])
                multi_items.append({
                    "Müşteri": customer,
                    "İçerik": package_summary,
                    "Durum": badge
                })

        col1, col2 = st.columns(2)

        # --- TEKLİ ÜRÜNLER (GRUPLU) ---
        with col1:
            st.header("🛒 Tekli Paketler")
            if single_items:
                df_p = pd.DataFrame(single_items)
                summary_p = df_p.groupby(["Ürün", "Barkod"]).agg(
                    Toplam=("Adet", "sum"),
                    Detaylar=("Müşteri", list),
                    Adetler=("Adet", list)
                ).reset_index()

                for _, row in summary_p.iterrows():
                    with st.expander(f"📦 {row['Toplam']} Adet - {row['Ürün']}"):
                        st.caption(f"Barkod: {row['Barkod']}")
                        for m, a in zip(row['Detaylar'], row['Adetler']):
                            label = f"{m} ({a} Adet)"
                            # Checkbox ile hazır paket takibi
                            is_ready = st.checkbox(label, key=f"check_{m}_{row['Barkod']}")
                            if is_ready and label not in st.session_state.ready_packages:
                                st.session_state.ready_packages.append(label)
            else:
                st.info("Tekli paket yok.")

        # --- KARMA PAKETLER ---
        with col2:
            st.header("🎁 Karma Paketler")
            if multi_items:
                for item in multi_items:
                    with st.container(border=True):
                        st.subheader(item["Müşteri"])
                        st.write(item["Durum"])
                        st.info(f"📝 {item['İçerik']}")
                        
                        label_multi = f"{item['Müşteri']} (Karma)"
                        is_ready_m = st.checkbox("Paket Hazır", key=f"multi_{item['Müşteri']}")
                        if is_ready_m and label_multi not in st.session_state.ready_packages:
                            st.session_state.ready_packages.append(label_multi)
            else:
                st.info("Karma paket yok.")
    else:
        st.warning("İşleme alınmış sipariş yok.")
