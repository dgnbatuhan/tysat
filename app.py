import streamlit as st
import requests
import base64
import pandas as pd
from datetime import datetime, timedelta

# --- Sayfa Yapılandırması ---
st.set_page_config(page_title="Trendyol İşleme Alınanlar", layout="wide")

# --- API Bilgileri (Secrets'tan çekilir) ---
SELLER_ID = st.secrets["SELLER_ID"]
API_KEY = st.secrets["API_KEY"]
API_SECRET = st.secrets["API_SECRET"]

def get_auth_header():
    auth_str = f"{API_KEY}:{API_SECRET}"
    encoded_auth = base64.b64encode(auth_str.encode()).decode()
    return {"Authorization": f"Basic {encoded_auth}", "User-Agent": f"{SELLER_ID}-Integration"}

@st.cache_data(ttl=30) # 30 saniyede bir taze veri
def fetch_picking_orders():
    end_dt = datetime.now()
    # İşleme alınanlar bazen listede bekleyebilir, 30 gün geriye bakıyoruz.
    start_dt = end_dt - timedelta(days=30) 
    
    url = f"https://apigw.trendyol.com/integration/order/sellers/{SELLER_ID}/orders"
    
    # Picking: Toplanıyor/Hazırlanıyor
    # Invoiced: Faturalandı (Paketleniyor)
    # Approved: Onaylandı (İşleme başlanmış olabilir)
    params = {
        "status": "Picking,Invoiced,Approved", 
        "startDate": str(int(start_dt.timestamp() * 1000)),
        "endDate": str(int(end_dt.timestamp() * 1000)),
        "size": 200
    }
    
    try:
        response = requests.get(url, params=params, headers=get_auth_header())
        if response.status_code == 200:
            return response.json().get("content", [])
        else:
            st.error(f"⚠️ Trendyol API Hatası ({response.status_code}): {response.text}")
            return []
    except Exception as e:
        st.error(f"❌ Bağlantı Hatası: {e}")
        return []

# --- Veri İşleme ---
orders = fetch_picking_orders()

st.title("🛠️ Paketleme Masası: İşleme Alınan Siparişler")

if orders:
    single_items = []
    multi_items = []

    for order in orders:
        # Müşteri Bilgisi
        addr = order.get('shipmentAddress', {})
        customer = f"{addr.get('firstName', '')} {addr.get('lastName', '')}".strip()
        
        # Statü Türkçeleştirme
        s = order.get("status")
        statu_tr = "🏗️ Hazırlanıyor" if s == "Picking" else "📄 Faturalandı" if s == "Invoiced" else "✅ Onaylı"
        
        lines = order.get("lines", [])
        total_qty = sum(item.get("quantity") for item in lines)

        if len(lines) == 1:
            line = lines[0]
            single_items.append({
                "Müşteri": customer,
                "Ürün": line.get("productName"),
                "Barkod": line.get("barcode"),
                "Adet": line.get("quantity"),
                "Detay": f"{customer} - {line.get('quantity')}'li paket ({statu_tr})"
            })
        else:
            contents = " + ".join([f"{l.get('quantity')} adet {l.get('productName')}" for l in lines])
            multi_items.append({
                "Müşteri": customer,
                "İçerik": contents,
                "Toplam": total_qty,
                "Durum": statu_tr
            })

    # Arayüz Sütunları
    c1, c2 = st.columns(2)

    with c1:
        st.subheader("🛒 Tekli Paketler")
        if single_items:
            df_s = pd.DataFrame(single_items)
            summary_s = df_s.groupby(["Ürün", "Barkod"]).agg(
                Toplam_Adet=('Adet', 'sum'),
                Liste=('Detay', lambda x: " \n ".join(x))
            ).reset_index()

            for _, row in summary_s.iterrows():
                with st.expander(f"📦 {row['Toplam_Adet']} Adet - {row['Ürün']}"):
                    st.write(f"**Barkod:** `{row['Barkod']}`")
                    st.text(row['Liste'])
        else:
            st.write("Hazırlanıyor aşamasında tekli ürün yok.")

    with c2:
        st.subheader("🎁 Çoklu/Karma Paketler")
        if multi_items:
            for item in multi_items:
                with st.container(border=True):
                    st.write(f"👤 **{item['Müşteri']}** ({item['Durum']})")
                    st.write(f"📝 {item['İçerik']}")
                    st.write(f"🔢 Toplam: {item['Toplam']} Ürün")
        else:
            st.write("Hazırlanıyor aşamasında karma paket yok.")

else:
    st.warning("⚠️ 'Hazırlanıyor' veya 'Faturalandı' statüsünde sipariş bulunamadı.")
    st.info("Eğer Trendyol panelinde siparişleri görüyorsanız, lütfen henüz kargolanmadıklarından emin olun.")

# Sidebar Yenileme
if st.sidebar.button("🔄 Listeyi Güncelle"):
    st.cache_data.clear()
    st.rerun()
