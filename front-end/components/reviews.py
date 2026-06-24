import streamlit as st
from services.mongo_service import add_review
from components.utils import smart_form_submit_button

def render_reviews(reviews: list[dict]) -> None:
    if not reviews:
        st.caption("Nessuna recensione ancora. Sii il primo a recensire!")
        return

    for rev in reversed(reviews):
        rating = rev.get("rating", 0)
        stars_text = f"{rating}/5"
        username = rev.get("username", "Anonimo")
        text = rev.get("text", "")
        created_at = rev.get("created_at", "")[:10]

        st.markdown(
            f"""
            <div class="result-card" style="margin-bottom:0.5rem">
              <div style="display:flex; justify-content:space-between; align-items:center">
                <span class="result-name" style="font-size:0.9rem">{username}</span>
                <span style="font-size:0.82rem; color:#94a3b8">{created_at}</span>
              </div>
              <div style="margin:0.2rem 0; font-size:0.85rem; color:#a78bfa">Voto: {stars_text}</div>
              <p class="result-desc" style="margin:0">{text}</p>
            </div>
            """,
            unsafe_allow_html=True,
        )


def render_add_review_form(collection: str, doc_id: str, username: str) -> None:
    st.markdown("<p class='section-label'>Aggiungi la tua recensione</p>", unsafe_allow_html=True)

    with st.form(key=f"review_form_{doc_id}", clear_on_submit=True):
        rating = st.slider("Valutazione (1-5)", min_value=1, max_value=5, value=3)
        text = st.text_area(
            "Commento",
            placeholder="Scrivi qui la tua esperienza...",
            max_chars=500,
        )
        submitted = smart_form_submit_button("Invia recensione", type="primary")

    if submitted:
        if not text.strip():
            st.warning("Scrivi un commento prima di inviare.")
            return
        add_review(collection, doc_id, username, rating, text.strip())
        st.success("Recensione pubblicata!")
        st.rerun()
