import streamlit as st
import requests
import base64
import pandas as pd
from datetime import datetime, timedelta

# --- Sayfa Yapılandırması ---
st.set_page_config(page_title="Trendyol İşleme Alınanlar", layout="wide")

# --- API Bilgileri ---
SELLER_ID = st.secrets["SELLER_ID"]
API_KEY = st.secrets["API_KEY"]
API_SECRET = st.secrets["API_SECRET"]

def get_auth_header():
    auth_str = f"{API_KEY}:{API_SECRET}"
    encoded_auth = base64.b64encode(auth_str.encode()).decode()
    return {"Authorization": f"Basic {encoded_auth}", "User-Agent": f"{SELLER_ID}-Integration"}

@st.cache_data(ttl=60) # İşleme alınanlar hızlı değiştiği için cache süresini düşürdük
def fetch_orders():
    end_dt = datetime.now()
    # İşleme alınmış (Hazırlanıyor aşamasında) siparişler için daha geniş bir zaman aralığı (15 gün)
    start_dt = end_dt - timedelta(days=15) 
    url = f"https://apigw.trendyol.com/integration/order/sellers/{SELLER_ID}/orders"
    
    # KRİTİK DEĞİŞİKLİK: Sadece "Picking" (Toplanıyor/İşleme Alınan) ve "Invoiced" (Faturalanmış) olanlar
    params = {
        "status": "Picking,Invoiced", 
        "startDate": str(int(start_dt.timestamp() * 1000)),
        "endDate": str(int(end_dt.timestamp() * 1000)),
        "size": 200
    }
    response = requests.get(url, params=params, headers=get_auth_header())
    return response.json().get("content", []) if response.status_code == 200 else []

# --- Veri İşleme ---
orders = fetch_orders()

if orders:
    single_items = []  # Tek çeşit ürün içeren paketler
    multi_items = []   # Karma ürün içeren paketler

    for order in orders:
        customer = f"{order.get('shipmentAddress', {}).get('firstName', '')} {order.get('shipmentAddress', {}).get('lastName', '')}"
        lines = order.get("lines", [])
        total_qty_in_package = sum(item.get("quantity") for item in lines)
        
        # Siparişin şu anki statüsünü belirleyelim (Görsel bilgi için)
        raw_status = order.get("status")
        status_text = "🏗️ İşleme Alındı" if raw_status == "Picking" else "📄 Faturalandı"
        
        if len(lines) == 1:
            line = lines[0]
            single_items.append({
                "Müşteri": customer,
                "Ürün": line.get("productName"),
                "Barkod": line.get("barcode"),
                "Adet": line.get("quantity"),
                "Detay": f"{customer} - {line.get('quantity')}'li paket ({status_text})"
            })
        else:
            package_summary = " + ".join([f"{item.get('quantity')} adet {item.get('productName')}" for item in lines])
            multi_items.append({
                "Müşteri": customer,
                "İçerik": package_summary,
                "Toplam Ürün": total_qty_in_package,
                "Detay": f"{customer} - Karma Paket ({total_qty_in_package} Ürün) - {status_text}"
            })

    # --- ARAYÜZ ---
    st.title("🛠️ İşleme Alınmış (Hazırlanıyor) Siparişler")
    st.write(f"Şu an paketleme aşamasında olan toplam **{len(orders)}** sipariş bulundu.")

    col1, col2 = st.columns(2)

    with col1:
        st.header("🛒 Tek Çeşit Ürünler")
        if single_items:
            df_s = pd.DataFrame(single_items)
            summary_s = df_s.groupby(["Ürün", "Barkod"]).agg(
                Toplam_Adet=('Adet', 'sum'),
                Paket_Sayisi=('Adet', 'count'),
                Musteri_Listesi=('Detay', lambda x: " \n ".join(x))
            ).reset_index()

            for _, row in summary_s.iterrows():
                with st.expander(f"🔵 {row['Toplam_Adet']} Adet - {row['Ürün']}"):
                    st.write(f"**Barkod:** `{row['Barkod']}`")
                    st.write("**Paketlenecek Kişiler:**")
                    st.text(row['Musteri_Listesi'])
        else:
            st.write("İşleme alınmış tekli sipariş bulunmuyor.")

    with col2:
        st.header("🎁 Çoklu/Karma Paketler")
        if multi_items:
            for item in multi_items:
                with st.container(border=True):
                    st.subheader(item["Müşteri"])
                    st.write(f"📝 **İçerik:** {item['İçerik']}")
                    st.write(f"🔢 **Toplam:** {item['Toplam Ürün']} parça ürün")
                    st.caption(item["Detay"])
        else:
            st.write("İşleme alınmış karma sipariş bulunmuyor.")

else:
    st.warning("⚠️ İşleme alınmış (Hazırlanıyor aşamasında) sipariş bulunamadı. Lütfen Trendyol panelinden siparişleri 'Hazırlanıyor'a çekin.")

# Manuel Güncelleme Butonu
if st.sidebar.button("🔄 Listeyi Yenile"):
    st.cache_data.clear()
    st.rerun()
