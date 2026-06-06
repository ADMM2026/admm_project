import streamlit as st
from pathlib import Path


def load_css() -> None:
    css_path = Path(__file__).parent.parent / "style.css"
    if css_path.exists():
        st.markdown(f"<style>{css_path.read_text(encoding='utf-8')}</style>", unsafe_allow_html=True)


def require_login(allowed_roles: list[str] | None = None) -> dict:
    user = st.session_state.get("user")
    if not user:
        st.error("⛔ Devi effettuare il login per accedere a questa pagina.")
        if st.button("Vai al Login"):
            st.switch_page("app.py")
        st.stop()

    if allowed_roles and user.get("role") not in allowed_roles:
        st.error(f"⛔ Accesso riservato a: {', '.join(allowed_roles)}.")
        st.stop()

    return user
