import streamlit as st
from components.utils import load_css, smart_form_submit_button
from services import auth

st.set_page_config(
    page_title="Turismo Piemonte - Login",
    page_icon="P",
    layout="centered",
)
load_css()

if st.session_state.get("user"):
    role = st.session_state["user"].get("role")
    st.switch_page("pages/dashboard.py" if role == "manager" else "pages/search.py")

st.markdown(
    """
    <div class="hero-section">
      <p class="hero-title">Turismo Piemonte</p>
      <p class="hero-sub">Esplora attrazioni e alloggi del Piemonte</p>
    </div>
    """,
    unsafe_allow_html=True,
)

st.divider()

tab_login, tab_reg = st.tabs(["Accedi", "Registrati"])

with tab_login:
    st.write("")
    with st.form("form_login", clear_on_submit=False):
        username = st.text_input("Username")
        password = st.text_input("Password", type="password")
        login_btn = smart_form_submit_button("Accedi", type="primary")

    if login_btn:
        if not username.strip() or not password:
            st.warning("Inserisci username e password.")
        else:
            user, msg = auth.login_user(username.strip(), password)
            if user:
                st.session_state["user"] = user
                st.rerun()
            else:
                st.error(msg)

with tab_reg:
    st.write("")
    with st.form("form_register", clear_on_submit=True):
        new_user = st.text_input("Username")
        new_email = st.text_input("Email (opzionale)")
        new_pw = st.text_input("Password", type="password")
        new_pw2 = st.text_input("Conferma password", type="password")
        reg_btn = smart_form_submit_button("Crea account", type="primary")

    if reg_btn:
        if not new_user.strip() or not new_pw:
            st.warning("Username e password sono obbligatori.")
        elif new_pw != new_pw2:
            st.error("Le password non coincidono.")
        elif len(new_pw) < 6:
            st.warning("La password deve essere di almeno 6 caratteri.")
        else:
            ok, msg = auth.register_user(new_user.strip(), new_pw, new_email.strip())
            if ok:
                st.success(f"{msg} Ora puoi accedere dal tab Accedi.")
            else:
                st.error(msg)