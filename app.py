import streamlit as st
import requests
import base64
import pandas as pd
from datetime import datetime, timedelta

# --- Sayfa Yapılandırması ---
st.set_page_config(page_title="Trendyol Detaylı Paketleme", layout="wide")

# --- API Bilgileri ---
SELLER_ID = st.secrets["SELLER_ID"]
API_KEY = st.secrets["API_KEY"]
API_SECRET = st.secrets["API_SECRET"]

def get_auth_header():
    auth_str = f"{API_KEY}:{API_SECRET}"
    encoded_auth = base64.b64encode(auth_str.encode()).decode()
    return {"Authorization": f"Basic {encoded_auth}", "User-Agent": f"{SELLER_ID}-Integration"}

@st.cache_data(ttl=300)
def fetch_orders():
    end_dt = datetime.now()
    start_dt = end_dt - timedelta(days=5)
    url = f"https://apigw.trendyol.com/integration/order/sellers/{SELLER_ID}/orders"
    params = {
        "status": "Created",
        "startDate": str(int(start_dt.timestamp() * 1000)),
        "endDate": str(int(end_dt.timestamp() * 1000)),
        "size": 200
    }
    response = requests.get(url, params=params, headers=get_auth_header())
    return response.json().get("content", []) if response.status_code == 200 else []

# --- Veri İşleme ---
orders = fetch_orders()

if orders:
    single_items = []  # Sadece 1 çeşit ürün içeren paketler
    multi_items = []   # Birden fazla veya karma ürün içeren paketler

    for order in orders:
        customer = f"{order.get('shipmentAddress', {}).get('firstName', '')} {order.get('shipmentAddress', {}).get('lastName', '')}"
        lines = order.get("lines", [])
        
        # Toplam ürün adedi (tüm satırlardaki miktarların toplamı)
        total_qty_in_package = sum(item.get("quantity") for item in lines)
        
        # Paket türünü belirle
        if len(lines) == 1:
            # Tek bir satır var (örn: Sadece Kalem almış, ama 1 tane veya 5 tane olabilir)
            line = lines[0]
            single_items.append({
                "Müşteri": customer,
                "Ürün": line.get("productName"),
                "Barkod": line.get("barcode"),
                "Adet": line.get("quantity"),
                "Detay": f"{customer} - {line.get('quantity')}'li paket"
            })
        else:
            # Karma paket (örn: 1 Kalem + 1 Silgi almış)
            package_summary = " + ".join([f"{item.get('quantity')} adet {item.get('productName')}" for item in lines])
            multi_items.append({
                "Müşteri": customer,
                "İçerik": package_summary,
                "Toplam Ürün": total_qty_in_package,
                "Detay": f"{customer} - Karma Paket ({total_qty_in_package} Ürün)"
            })

    # --- ARAYÜZ ---
    st.title("📦 Detaylı Sipariş Hazırlık Listesi")

    # SOL SÜTUN: TEKLİ PAKETLER
    col1, col2 = st.columns(2)

    with col1:
        st.header("🛒 Tek Çeşit Ürün Paketleri")
        st.info("Bu listedeki paketlerin içinde sadece aynı barkodlu ürünler vardır.")
        
        if single_items:
            df_s = pd.DataFrame(single_items)
            # Ürün bazlı özet tablo
            summary_s = df_s.groupby(["Ürün", "Barkod"]).agg(
                Toplam_Adet=('Adet', 'sum'),
                Paket_Sayisi=('Adet', 'count'),
                Musteri_Listesi=('Detay', lambda x: " \n ".join(x))
            ).reset_index()

            for _, row in summary_s.iterrows():
                with st.expander(f"🔴 {row['Toplam_Adet']} Adet - {row['Ürün']}"):
                    st.write(f"**Barkod:** `{row['Barkod']}`")
                    st.write("**Paketlenecek Kişiler:**")
                    st.text(row['Musteri_Listesi'])
        else:
            st.write("Tekli sipariş bulunamadı.")

    # SAĞ SÜTUN: ÇOKLU / KARMA PAKETLER
    with col2:
        st.header("🎁 Çoklu/Karma Paketler")
        st.warning("Bu paketlerin içine birden fazla farklı ürün koyulmalıdır!")
        
        if multi_items:
            for item in multi_items:
                with st.container(border=True):
                    st.subheader(item["Müşteri"])
                    st.write(f"📝 **Paket İçeriği:** {item['İçerik']}")
                    st.write(f"🔢 **Toplam:** {item['Toplam Ürün']} parça ürün")
        else:
            st.write("Karma sipariş bulunamadı.")

else:
    st.success("Hazırlanacak yeni sipariş yok!")
