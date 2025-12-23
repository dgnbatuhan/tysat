import streamlit as st
import requests
import base64
import pandas as pd
from datetime import datetime, timedelta

# --- Sayfa Yapılandırması ---
st.set_page_config(page_title="Trendyol Hazırlık Paneli", layout="wide")

# --- API Bilgileri ---
SELLER_ID = st.secrets["SELLER_ID"]
API_KEY = st.secrets["API_KEY"]
API_SECRET = st.secrets["API_SECRET"]

def get_auth_header():
    auth_str = f"{API_KEY}:{API_SECRET}"
    encoded_auth = base64.b64encode(auth_str.encode()).decode()
    return {"Authorization": f"Basic {encoded_auth}", "User-Agent": f"{SELLER_ID}-Integration"}

@st.cache_data(ttl=10) # Hızlı güncelleme için 10 saniye
def fetch_picking_orders():
    # Tarih aralığını çok geniş tutuyoruz ki hazırlıkta bekleyen eski siparişler kaçmasın
    end_dt = datetime.now()
    start_dt = end_dt - timedelta(days=45) # Son 45 günün siparişleri
    
    url = f"https://apigw.trendyol.com/integration/order/sellers/{SELLER_ID}/orders"
    
    # SADECE PANELDE "HAZIRLANIYOR" BUTONUNA BASILMIŞ OLANLAR
    # Picking = Hazırlanıyor, Invoiced = Faturalandı
    params = {
        "status": "Picking,Invoiced", 
        "startDate": str(int(start_dt.timestamp() * 1000)),
        "endDate": str(int(end_dt.timestamp() * 1000)),
        "size": 200
    }
    
    try:
        response = requests.get(url, params=params, headers=get_auth_header())
        if response.status_code == 200:
            return response.json().get("content", [])
        return []
    except:
        return []

# --- Veri İşleme ---
orders = fetch_picking_orders()

st.title("🛠️ Sadece İşleme Alınanlar (Hazırlanıyor)")
st.write(f"Şu an paketleme masasında bekleyen **{len(orders)}** adet işleme alınmış sipariş var.")

if orders:
    single_items = []
    multi_items = []

    for order in orders:
        customer = f"{order.get('shipmentAddress', {}).get('firstName', '')} {order.get('shipmentAddress', {}).get('lastName', '')}"
        lines = order.get("lines", [])
        total_qty = sum(item.get("quantity") for item in lines)
        
        # Statü bilgisini çekelim
        raw_s = order.get("status")
        statu_badge = "🔵 Hazırlanıyor" if raw_s == "Picking" else "🟢 Faturalandı"

        if len(lines) == 1:
            line = lines[0]
            single_items.append({
                "Müşteri": customer,
                "Ürün": line.get("productName"),
                "Barkod": line.get("barcode"),
                "Adet": line.get("quantity"),
                "Detay": f"👤 {customer} - {line.get('quantity')}'li paket ({statu_badge})"
            })
        else:
            package_summary = " + ".join([f"{item.get('quantity')} adet {item.get('productName')}" for item in lines])
            multi_items.append({
                "Müşteri": customer,
                "İçerik": package_summary,
                "Toplam": total_qty,
                "Durum": statu_badge
            })

    # --- Arayüz Sütunları ---
    col1, col2 = st.columns(2)

    with col1:
        st.header("🛒 Tek Çeşit Ürünler")
        if single_items:
            df_s = pd.DataFrame(single_items)
            summary_s = df_s.groupby(["Ürün", "Barkod"]).agg(
                Toplam_Adet=('Adet', 'sum'),
                Liste=('Detay', lambda x: " \n ".join(x))
            ).reset_index()

            for _, row in summary_s.iterrows():
                with st.expander(f"📦 {row['Toplam_Adet']} ADET - {row['Ürün']}"):
                    st.write(f"**Barkod:** `{row['Barkod']}`")
                    st.markdown("---")
                    st.text(row['Liste'])
        else:
            st.info("İşleme alınmış tekli ürün bulunamadı.")

    with col2:
        st.header("🎁 Karma Paketler")
        if multi_items:
            for item in multi_items:
                with st.container(border=True):
                    st.subheader(item["Müşteri"])
                    st.write(f"Durum: {item['Durum']}")
                    st.write(f"📝 {item['İçerik']}")
                    st.write(f"🔢 Toplam: {item['Toplam']} ürün")
        else:
            st.info("İşleme alınmış karma paket bulunamadı.")
else:
    st.warning("⚠️ 'Hazırlanıyor' aşamasında sipariş bulunamadı.")
    st.write("Lütfen Trendyol Panelinde 'Hazırlanıyor' kısmında sipariş olduğundan emin olun.")

if st.sidebar.button("🔄 Verileri Yenile"):
    st.cache_data.clear()
    st.rerun()
