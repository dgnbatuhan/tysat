import streamlit as st
import requests
import base64
import pandas as pd
from datetime import datetime, timedelta

# --- Sayfa Yapılandırması ---
st.set_page_config(page_title="Trendyol Tüm Siparişler Paneli", layout="wide")

# --- API Bilgileri (Streamlit Secrets üzerinden) ---
# Not: Localde çalıştırırken .streamlit/secrets.toml dosyasına yazmalısınız.
SELLER_ID = st.secrets["SELLER_ID"]
API_KEY = st.secrets["API_KEY"]
API_SECRET = st.secrets["API_SECRET"]

def get_auth_header():
    auth_str = f"{API_KEY}:{API_SECRET}"
    encoded_auth = base64.b64encode(auth_str.encode()).decode()
    return {"Authorization": f"Basic {encoded_auth}", "User-Agent": f"{SELLER_ID}-Integration"}

@st.cache_data(ttl=60) # Veriyi daha sık güncellemek için 1 dakikaya indirdim
def fetch_orders():
    end_dt = datetime.now()
    # Geriye dönük 15 günü çekelim ki kargolanmamış tüm siparişleri yakalayalım
    start_dt = end_dt - timedelta(days=15) 
    
    url = f"https://apigw.trendyol.com/integration/order/sellers/{SELLER_ID}/orders"
    
    # STATUS DEĞİŞİKLİĞİ: Sadece 'Created' değil, kargolanmamış tüm durumlar
    # Created: Yeni, Approved: Onaylanmış, Invoiced: Faturalanmış
    params = {
        "status": "Created,Approved,Invoiced", 
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
orders = fetch_orders()

st.title("📦 Tüm Hazırlanacak Siparişler (Genel Liste)")
st.caption(f"Toplam {len(orders)} adet paket kargolanmayı bekliyor.")

if orders:
    single_items = []
    multi_items = []

    for order in orders:
        # Müşteri adı
        first_name = order.get('shipmentAddress', {}).get('firstName', '')
        last_name = order.get('shipmentAddress', {}).get('lastName', '')
        customer = f"{first_name} {last_name}".strip()
        
        # Sipariş Durumu (Created, Approved vb.)
        status = order.get("status")
        status_tr = "Yeni" if status == "Created" else "Onaylı/Hazırlanıyor"
        
        lines = order.get("lines", [])
        total_qty_in_package = sum(item.get("quantity") for item in lines)
        
        if len(lines) == 1:
            line = lines[0]
            single_items.append({
                "Müşteri": customer,
                "Ürün": line.get("productName"),
                "Barkod": line.get("barcode"),
                "Adet": line.get("quantity"),
                "Durum": status_tr,
                "Detay": f"{customer} ({status_tr}) - {line.get('quantity')}'li paket"
            })
        else:
            package_summary = " + ".join([f"{item.get('quantity')} adet {item.get('productName')}" for item in lines])
            multi_items.append({
                "Müşteri": customer,
                "İçerik": package_summary,
                "Toplam Ürün": total_qty_in_package,
                "Durum": status_tr,
                "Detay": f"{customer} - Karma Paket ({total_qty_in_package} Ürün)"
            })

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
                with st.expander(f"🔵 {row['Toplam_Adet']} Adet | {row['Ürün']}"):
                    st.write(f"**Barkod:** `{row['Barkod']}`")
                    st.markdown("**Paket Dağılımı:**")
                    st.info(row['Musteri_Listesi'])
        else:
            st.write("Sipariş bulunamadı.")

    with col2:
        st.header("🎁 Karma Paketler")
        if multi_items:
            for item in multi_items:
                with st.container(border=True):
                    st.subheader(item["Müşteri"])
                    st.write(f"🏷️ **Durum:** {item['Durum']}")
                    st.write(f"📝 **İçerik:** {item['İçerik']}")
                    st.write(f"🔢 **Miktar:** {item['Toplam Ürün']} parça")
        else:
            st.write("Karma sipariş bulunamadı.")
else:
    st.success("Tüm siparişler paketlenmiş veya gönderilmiş!")

# Manuel Yenileme
if st.sidebar.button("🔄 Verileri Yenile"):
    st.cache_data.clear()
    st.rerun()
