import streamlit as st
import requests
import base64
import pandas as pd
from datetime import datetime, timedelta

# -------------------------------------------------
# SAYFA AYARLARI
# -------------------------------------------------
st.set_page_config(
    page_title="Trendyol Sipariş Paneli",
    layout="wide"
)

# -------------------------------------------------
# API BİLGİLERİ (Streamlit Secrets)
# -------------------------------------------------
SELLER_ID = st.secrets["SELLER_ID"]
API_KEY = st.secrets["API_KEY"]
API_SECRET = st.secrets["API_SECRET"]

# -------------------------------------------------
# AUTH HEADER
# -------------------------------------------------
def get_auth_header():
    auth_str = f"{API_KEY}:{API_SECRET}"
    encoded_auth = base64.b64encode(auth_str.encode()).decode()
    return {
        "Authorization": f"Basic {encoded_auth}",
        "User-Agent": f"{SELLER_ID}-Integration"
    }

# -------------------------------------------------
# SİPARİŞ ÇEKME FONKSİYONU
# -------------------------------------------------
@st.cache_data(ttl=10)
def fetch_orders(status):
    end_dt = datetime.now()
    start_dt = end_dt - timedelta(days=5)

    url = f"https://apigw.trendyol.com/integration/order/sellers/{SELLER_ID}/orders"

    params = {
        "status": status,
        "startDate": int(start_dt.timestamp() * 1000),
        "endDate": int(end_dt.timestamp() * 1000),
        "size": 200
    }

    try:
        response = requests.get(url, headers=get_auth_header(), params=params)
        if response.status_code == 200:
            return response.json().get("content", [])
        return []
    except:
        return []

# -------------------------------------------------
# BAŞLIK
# -------------------------------------------------
st.title("📦 Trendyol Sipariş Yönetim Paneli")

# -------------------------------------------------
# SEKME YAPISI
# -------------------------------------------------
tab_new, tab_processing = st.tabs([
    "🆕 Yeni Gelen Siparişler",
    "🛠️ İşleme Alınanlar"
])

# -------------------------------------------------
# YENİ GELENLER (CREATED)
# -------------------------------------------------
with tab_new:
    new_orders = fetch_orders("Created")
    st.subheader(f"🆕 Yeni Gelen Siparişler ({len(new_orders)})")

    if new_orders:
        for order in new_orders:
            customer = f"{order.get('shipmentAddress', {}).get('firstName','')} {order.get('shipmentAddress', {}).get('lastName','')}"
            order_no = order.get("orderNumber")

            with st.container(border=True):
                st.markdown(f"### 👤 {customer}")
                st.write(f"🧾 Sipariş No: `{order_no}`")

                for line in order.get("lines", []):
                    st.write(
                        f"• **{line.get('quantity')} x {line.get('productName')}**  "
                        f"(Barkod: `{line.get('barcode')}`)"
                    )
    else:
        st.info("Yeni gelen sipariş yok.")

# -------------------------------------------------
# İŞLEME ALINANLAR (PICKING + INVOICED)
# -------------------------------------------------
with tab_processing:
    orders = fetch_orders("Picking,Invoiced")
    st.subheader(f"🛠️ İşleme Alınan Siparişler ({len(orders)})")

    if orders:
        single_items = []
        multi_items = []

        for order in orders:
            customer = f"{order.get('shipmentAddress', {}).get('firstName','')} {order.get('shipmentAddress', {}).get('lastName','')}"
            lines = order.get("lines", [])
            status = order.get("status")

            badge = "🔵 Hazırlanıyor" if status == "Picking" else "🟢 Faturalandı"
            total_qty = sum(item.get("quantity") for item in lines)

            if len(lines) == 1:
                line = lines[0]
                single_items.append({
                    "Ürün": line.get("productName"),
                    "Barkod": line.get("barcode"),
                    "Adet": line.get("quantity"),
                    "Detay": f"👤 {customer} - {line.get('quantity')} adet ({badge})"
                })
            else:
                package_summary = " + ".join(
                    [f"{i.get('quantity')} adet {i.get('productName')}" for i in lines]
                )
                multi_items.append({
                    "Müşteri": customer,
                    "İçerik": package_summary,
                    "Toplam": total_qty,
                    "Durum": badge
                })

        col1, col2 = st.columns(2)

        # TEK ÜRÜNLER
        with col1:
            st.header("🛒 Tek Çeşit Ürünler")
            if single_items:
                df = pd.DataFrame(single_items)
                summary = df.groupby(["Ürün", "Barkod"]).agg(
                    Toplam_Adet=("Adet", "sum"),
                    Liste=("Detay", lambda x: "\n".join(x))
                ).reset_index()

                for _, row in summary.iterrows():
                    with st.expander(f"📦 {row['Toplam_Adet']} ADET - {row['Ürün']}"):
                        st.write(f"**Barkod:** `{row['Barkod']}`")
                        st.text(row["Liste"])
            else:
                st.info("Tekli ürün yok.")

        # KARMA PAKETLER
        with col2:
            st.header("🎁 Karma Paketler")
            if multi_items:
                for item in multi_items:
                    with st.container(border=True):
                        st.subheader(item["Müşteri"])
                        st.write(item["Durum"])
                        st.write(f"📝 {item['İçerik']}")
                        st.write(f"🔢 Toplam: {item['Toplam']} ürün")
            else:
                st.info("Karma paket yok.")

    else:
        st.warning("İşleme alınmış sipariş yok.")

# -------------------------------------------------
# YENİLEME BUTONU
# -------------------------------------------------
if st.sidebar.button("🔄 Verileri Yenile"):
    st.cache_data.clear()
    st.rerun()
