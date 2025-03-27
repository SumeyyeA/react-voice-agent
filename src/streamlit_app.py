import streamlit as st
import subprocess
import os
import sys
import time
from app import brand_name

# Sabit değişkenler
APP_PORT = 3000  # app.py'nin kullandığı port

# Session state kontrolü
if "process" not in st.session_state:
    st.session_state.process = None

def start_server():
    """app.py dosyasını uvicorn üzerinden başlatır."""
    try:
        env = os.environ.copy()
        script_dir = os.path.dirname(os.path.abspath(__file__))
        app_path = os.path.join(script_dir, "server", "app.py")
        if not os.path.exists(app_path):
            app_path = os.path.join(script_dir, "app.py")
            if not os.path.exists(app_path):
                st.error(f"app.py dosyası bulunamadı: {app_path}")
                return False

        cmd = [sys.executable, app_path]
        process = subprocess.Popen(
            cmd,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
            env=env
        )
        st.session_state.process = process
        return True
    except Exception as e:
        st.error(f"Sunucu başlatılamadı: {e}")
        return False

def stop_server():
    """Çalışan sunucuyu durdurur."""
    if st.session_state.process:
        st.session_state.process.terminate()
        st.session_state.process = None
        return True
    return False

def main():
    st.set_page_config(
        page_title=f"{brand_name} Müşteri Temsilcisi",
        page_icon="🎤",
        layout="wide"
    )
    
    st.title(f"{brand_name} Müşteri Temsilcisi")
    
    col1, col2 = st.columns(2)
    
    with col1:
        if not st.session_state.get("process"):
            if st.button("Ses Asistanını Başlat", use_container_width=True):
                with st.spinner("Ses asistanı başlatılıyor..."):
                    success = start_server()
                    if success:
                        st.success("Ses asistanı başlatıldı!")
                        time.sleep(2)  # Sunucunun başlaması için bekleme
                    else:
                        st.error("Ses asistanı başlatılamadı!")
        else:
            if st.button("Ses Asistanını Durdur", use_container_width=True):
                stop_server()
                st.warning("Ses asistanı durduruldu")
    
    with col2:
        if st.session_state.get("process"):
            st.success("🟢 Ses asistanı çalışıyor")
            server_url = f"http://localhost:{APP_PORT}"
            st.write(f"Web Arayüzü: [{server_url}]({server_url})")
        else:
            st.error("🔴 Ses asistanı durduruldu")
    
    # Sunucu çalışıyorsa arayüzü iframe içinde gösteriyoruz.
    if st.session_state.get("process"):
        st.subheader("Ses Asistanı Arayüzü")
        st.markdown(f"""
        <iframe
            src="http://localhost:{APP_PORT}"
            width="100%"
            height="300px"
            style="border:none; border-radius: 10px; box-shadow: 0 4px 6px rgba(0,0,0,0.1);"
            allow="microphone; camera; autoplay; display-capture; clipboard-write"
            allowfullscreen
        ></iframe>
        """, unsafe_allow_html=True)
        
        st.markdown("---")
        st.info("""
        **Not:** Mikrofon izinleriyle ilgili sorun yaşarsanız, uygulamayı yeni bir sekmede açıp izinleri kontrol edin.
        """)
        st.markdown(f"""
        <div style="text-align: center; margin: 20px 0;">
            <a href="http://localhost:{APP_PORT}" target="_blank" style="
                display: inline-block;
                background-color: #0078ff;
                color: white;
                padding: 12px 24px;
                text-decoration: none;
                border-radius: 4px;
                font-weight: bold;
            ">Yeni Sekmede Aç</a>
        </div>
        """, unsafe_allow_html=True)
    else:
        st.info("Ses asistanını kullanmak için 'Ses Asistanını Başlat' düğmesine tıklayın.")

if __name__ == "__main__":
    main()
