# app.py
from __future__ import annotations
import time
from datetime import datetime, timezone
import streamlit as st
import pandas as pd

# --- AUTH ---
import streamlit_authenticator as stauth

# --- SHEETS ---
import gspread
from google.oauth2.service_account import Credentials

st.set_page_config(page_title="Bayi Anketi", page_icon="📝", layout="centered")

# ======================
# Utils
# ======================
def get_gspread_client():
    """
    st.secrets'taki servis hesabı JSON'uyla Google Sheets'e bağlanır.
    """
    sa_info = st.secrets["google_drive_service_account"]
    scopes = [
        "https://www.googleapis.com/auth/spreadsheets",
        "https://www.googleapis.com/auth/drive"
    ]
    credentials = Credentials.from_service_account_info(sa_info, scopes=scopes)
    return gspread.authorize(credentials)

@st.cache_resource(show_spinner=False)
def open_worksheet(spreadsheet_url: str, sheet_name: str):
    """
    Spreadsheet'i ve ilgili sayfayı açar; yoksa yaratır.
    """
    gc = get_gspread_client()
    sh = gc.open_by_url(spreadsheet_url)
    try:
        ws = sh.worksheet(sheet_name)
    except gspread.WorksheetNotFound:
        ws = sh.add_worksheet(title=sheet_name, rows=1000, cols=50)
        # Başlık satırı
        ws.append_row([
            "timestamp_utc", "username", "name", "email",
            "Q1_kalite", "Q2_çeşitlilik", "Q3_ambalaj",
            "Q4_fiyat_konum", "Q5_kar_marjı",
            "Q6_loji_memnuniyet", "Q7_stok_sıkıntısı",
            "Q8_iletisim", "Q9_acik_öneri"
        ])
    return ws

def user_already_submitted(ws, username: str) -> bool:
    """
    Kullanıcı daha önce yanıt vermiş mi?
    """
    try:
        data = ws.get_all_records()
        df = pd.DataFrame(data)
        if df.empty:
            return False
        return (df["username"] == username).any()
    except Exception:
        return False

def append_response(ws, row: list):
    ws.append_row(row)

# ======================
# Auth Config (st.secrets)
# ======================
auth_conf = {
    "credentials": {
        "usernames": {}
    },
    "cookie": {
        "name": "bayi_anketi_cookie",
        "key": st.secrets["auth"]["cookie_key"],
        "expiry_days": 1
    },
    "preauthorized": {
        "emails": []
    }
}

# st.secrets["auth"]["users"] => {"bayi1":{"name":"...","email":"...","password":"$2b$12$..."} , ...}
for uname, uinfo in st.secrets["auth"]["users"].items():
    auth_conf["credentials"]["usernames"][uname] = {
        "name": uinfo.get("name", uname),
        "email": uinfo.get("email", ""),
        "password": uinfo["password"]  # bcrypt hash
    }

authenticator = stauth.Authenticate(
    auth_conf["credentials"],
    auth_conf["cookie"]["name"],
    auth_conf["cookie"]["key"],
    auth_conf["cookie"]["expiry_days"],
)

# ======================
# UI: Login
# ======================
st.title("📝 Bayi Anketi – Ürün ve İşbirliği Değerlendirmesi")

with st.container():
    st.markdown(
        """
        **Değerli iş ortağımız,**  
        Ürün ve hizmetlerimizi geliştirmek için görüşleriniz bizim için çok kıymetli.  
        Lütfen aşağıdaki kısa anketi doldurun. Yanıtlarınız gizli tutulur ve yalnızca değerlendirme amacıyla kullanılır.
        """
    )

name, auth_status, username = authenticator.login("Giriş Yap", "main")

if auth_status is False:
    st.error("Kullanıcı adı/şifre hatalı.")
elif auth_status is None:
    st.info("Lütfen kullanıcı adınızı ve şifrenizi girin.")
else:
    # Giriş başarılı
    authenticator.logout("Çıkış Yap", "sidebar")
    st.success(f"Hoş geldiniz, {name}!")

    # Sheets bağlantısı
    SPREADSHEET_URL = st.secrets["sheets"]["url"]
    RESP_SHEET = st.secrets["sheets"].get("responses_sheet", "Yanıtlar")
    ws = open_worksheet(SPREADSHEET_URL, RESP_SHEET)

    # Tek yanıt kuralı (dilerseniz kaldırabilirsiniz)
    already = user_already_submitted(ws, username)
    if already and not st.secrets["options"].get("allow_resubmit", False):
        st.warning("Bu kullanıcı ile daha önce anket yanıtı gönderilmiş görünüyor. Tekrar gönderime kapalıdır.")
        st.stop()

    st.divider()
    st.subheader("Anket Soruları")

    # 1) ÜRÜN MEMNUNİYETİ
    q1 = st.radio(
        "1) Ürünlerimizin genel kalitesinden ne kadar memnunsunuz?",
        ["Çok memnunum", "Memnunum", "Kararsızım", "Memnun değilim", "Hiç memnun değilim"],
        index=1
    )

    q2 = st.radio(
        "2) Ürün çeşitliliğimiz (farklı tatlar, ambalaj boyutları vb.) beklentilerinizi karşılıyor mu?",
        ["Evet, tamamen", "Kısmen", "Hayır"],
        index=1
    )

    q3 = st.radio(
        "3) Ürün ambalajlarımızın görünümü ve dayanıklılığı hakkında ne düşünüyorsunuz?",
        ["Çok beğeniyorum", "İyi", "Geliştirilebilir", "Yetersiz"],
        index=1
    )

    # 2) FİYAT VE REKABET
    q4 = st.radio(
        "4) Ürün fiyatlarımız piyasadaki benzer ürünlerle karşılaştırıldığında sizce nasıl konumlanıyor?",
        ["Daha uygun", "Benzer", "Biraz yüksek", "Çok yüksek"],
        index=1
    )

    q5 = st.radio(
        "5) Bayi kâr marjınızı yeterli buluyor musunuz?",
        ["Evet", "Kısmen", "Hayır"],
        index=1
    )

    # 3) DAĞITIM VE LOJİSTİK
    q6 = st.radio(
        "6) Teslimat süreleri, stok durumu ve lojistik süreçlerinden memnun musunuz?",
        ["Evet", "Kısmen", "Hayır"],
        index=1
    )

    q7 = st.radio(
        "7) Talep ettiğiniz ürünlerde stok sıkıntısı yaşadığınız oluyor mu?",
        ["Hiçbir zaman", "Ara sıra", "Sık sık"],
        index=1
    )

    # 4) İLETİŞİM VE DESTEK
    q8 = st.radio(
        "8) Satış ekibimizle iletişim, kampanya bilgilendirmeleri ve destek süreçlerini nasıl değerlendiriyorsunuz?",
        ["Çok başarılı", "İyi", "Geliştirilmeli", "Zayıf"],
        index=1
    )

    # 5) GELİŞTİRME ÖNERİSİ
    q9 = st.text_area(
        "9) Ürünlerimiz veya işbirliğimizle ilgili geliştirilmesini istediğiniz konular nelerdir? (Opsiyonel)",
        placeholder="Örn: 2100 g ambalaj kapak kalitesi, sevkiyat planlarının haftalık paylaşımı vb."
    )

    st.divider()
    st.caption("⚠️ Göndermeden önce cevaplarınızı kontrol edin.")

    col1, col2 = st.columns([1,1])
    with col1:
        submit = st.button("Yanıtları Gönder", type="primary")
    with col2:
        clear = st.button("Formu Temizle")

    if clear:
        st.experimental_rerun()

    if submit:
        with st.spinner("Kaydediliyor..."):
            # Kullanıcı meta (secrets'ten)
            user_info = st.secrets["auth"]["users"].get(username, {})
            email = user_info.get("email", "")
            display_name = user_info.get("name", username)

            row = [
                datetime.now(timezone.utc).isoformat(),
                username,
                display_name,
                email,
                q1, q2, q3, q4, q5, q6, q7, q8, q9.strip()
            ]
            append_response(ws, row)
            time.sleep(0.5)

        st.success("Yanıtlarınız başarıyla kaydedildi. Teşekkür ederiz! 🙏")
        if st.secrets["options"].get("allow_resubmit", False):
            st.info("Not: Bu kullanıcı için tekrar yanıt gönderimine izin veriliyor (allow_resubmit=True).")
        else:
            st.info("Bu kullanıcı için tekrar yanıt gönderimi kapatıldı.")
        st.balloons()

    st.divider()

    # --- Admin görünümü (opsiyonel) ---
    # admin rolü: st.secrets["options"]["admins"] içinde listelenen username'ler
    admins = st.secrets["options"].get("admins", [])
    if username in admins:
        st.subheader("🔐 Admin Paneli – Sonuçlar")
        try:
            data = ws.get_all_records()
            df = pd.DataFrame(data)
            st.dataframe(df, use_container_width=True)
            if not df.empty:
                st.download_button(
                    "Excel indir (xlsx)",
                    data=df.to_csv(index=False).encode("utf-8"),
                    file_name="bayi_anketi_sonuclari.csv",
                    mime="text/csv"
                )
        except Exception as e:
            st.error(f"Sonuçlar okunamadı: {e}")
