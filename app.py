import streamlit as st
import requests
import base64
import pandas as pd
from datetime import datetime, timedelta

# --- Sayfa Yapılandırması ---
st.set_page_config(page_title="Trendyol Paketleme Masası", layout="wide")

# --- API Bilgileri ---
SELLER_ID = st.secrets["SELLER_ID"]
API_KEY = st.secrets["API_KEY"]
API_SECRET = st.secrets["API_SECRET"]

def get_auth_header():
    auth_str = f"{API_KEY}:{API_SECRET}"
    encoded_auth = base64.b64encode(auth_str.encode()).decode()
    return {"Authorization": f"Basic {encoded_auth}", "User-Agent": f"{SELLER_ID}-Integration"}

@st.cache_data(ttl=30)
def fetch_all_active_orders():
    end_dt = datetime.now()
    start_dt = end_dt - timedelta(days=30)
    
    url = f"https://apigw.trendyol.com/integration/order/sellers/{SELLER_ID}/orders"
    
    # TÜM AKTİF STATÜLER: Yeni, Onaylı, Hazırlanıyor, Faturalandı
    # Bu liste kargoya verilmemiş her şeyi kapsar.
    all_statuses = "Created,Approved,Picking,Invoiced"
    
    params = {
        "status": all_statuses, 
        "startDate": str(int(start_dt.timestamp() * 1000)),
        "endDate": str(int(end_dt.timestamp() * 1000)),
        "size": 200
    }
    
    try:
        response = requests.get(url, params=params, headers=get_auth_header())
        if response.status_code == 200:
            return response.json().get("content", [])
        else:
            st.error(f"API Hatası: {response.status_code}")
            return []
    except Exception as e:
        st.error(f"Bağlantı Hatası: {e}")
        return []

# --- Veri İşleme ---
orders = fetch_all_active_orders()

st.title("📦 Sipariş Hazırlama ve Paketleme Listesi")

if orders:
    single_items = []
    multi_items = []

    for order in orders:
        customer = f"{order.get('shipmentAddress', {}).get('firstName', '')} {order.get('shipmentAddress', {}).get('lastName', '')}"
        lines = order.get("lines", [])
        total_qty = sum(item.get("quantity") for item in lines)
        
        # Trendyol'dan gelen orijinal statü
        raw_status = order.get("status")
        
        # Statüye göre renkli etiketler
        if raw_status == "Created": s_label = "🟡 Yeni"
        elif raw_status == "Picking": s_label = "🔵 Hazırlanıyor"
        elif raw_status == "Invoiced": s_label = "🟢 Faturalandı"
        else: s_label = f"⚪ {raw_status}"

        if len(lines) == 1:
            line = lines[0]
            single_items.append({
                "Müşteri": customer,
                "Ürün": line.get("productName"),
                "Barkod": line.get("barcode"),
                "Adet": line.get("quantity"),
                "Detay": f"{customer} - {line.get('quantity')}'li paket ({s_label})"
            })
        else:
            package_summary = " + ".join([f"{item.get('quantity')} adet {item.get('productName')}" for item in lines])
            multi_items.append({
                "Müşteri": customer,
                "İçerik": package_summary,
                "Toplam": total_qty,
                "Durum": s_label
            })

    col1, col2 = st.columns(2)

    with col1:
        st.header("🛒 Tek Çeşit Ürünler")
        if single_items:
            df_s = pd.DataFrame(single_items)
            summary_s = df_s.groupby(["Ürün", "Barkod"]).agg(
                Toplam_Adet=('Adet', 'sum'),
                Musteri_Listesi=('Detay', lambda x: " \n ".join(x))
            ).reset_index()

            for _, row in summary_s.iterrows():
                with st.expander(f"📦 {row['Toplam_Adet']} Adet - {row['Ürün']}"):
                    st.write(f"**Barkod:** `{row['Barkod']}`")
                    st.markdown("---")
                    st.text(row['Musteri_Listesi'])
        else:
            st.write("Tekli ürün içeren sipariş bulunamadı.")

    with col2:
        st.header("🎁 Karma Paketler")
        if multi_items:
            for item in multi_items:
                with st.container(border=True):
                    st.write(f"👤 **{item['Müşteri']}**")
                    st.write(f"Durum: {item['Durum']}")
                    st.write(f"📝 {item['İçerik']}")
                    st.write(f"🔢 Toplam: {item['Toplam']} ürün")
        else:
            st.write("Karma paket içeren sipariş bulunamadı.")
else:
    st.warning("⚠️ Şu anda kargolanmayı bekleyen aktif bir sipariş bulunamadı.")
    st.info("Eğer panelde sipariş varsa, 'Kargoya Verildi' veya 'İptal' edilip edilmediğini kontrol edin.")

if st.sidebar.button("🔄 Verileri Güncelle"):
    st.cache_data.clear()
    st.rerun()
