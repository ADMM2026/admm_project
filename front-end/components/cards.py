"""
Card components per attrazioni e alloggi.
"""
import streamlit as st


def _location_str(item: dict) -> str:
    loc = item.get("location", {})
    if isinstance(loc, dict):
        mun = loc.get("municipality", "")
        prov = loc.get("province", "")
        return f"{mun}" + (f" ({prov})" if prov else "")
    return ""


def render_attraction_card(item: dict, idx: int) -> bool:
    """
    Renders a card for an attraction.
    Returns True if the user clicked 'Vedi dettagli'.
    """
    name = item.get("name", "N/D")
    category = item.get("category", "")
    location = _location_str(item)
    description = item.get("description", "")
    short_desc = description[:140] + "..." if len(description) > 140 else description

    cat_badge = f"<span class='badge badge-blue'>{category}</span>" if category else ""
    desc_html = f"<p class='result-desc'>{short_desc}</p>" if short_desc else ""

    st.markdown(
        f"""
        <div class="result-card">
          <div class="result-name">{name}</div>
          <div class="result-meta">{location}</div>
          <div style="margin-top:0.4rem">
            <span class="badge badge-green">Attrazione</span>{cat_badge}
          </div>
          {desc_html}
        </div>
        """,
        unsafe_allow_html=True,
    )
    return st.button("Vedi dettagli", key=f"det_att_{idx}", use_container_width=True)


def render_accommodation_card(item: dict, idx: int) -> bool:
    """
    Renders a card for an accommodation.
    Returns True if the user clicked 'Vedi dettagli'.
    """
    name = item.get("name", "N/D")
    structure_type = item.get("structure_type", "")
    stars = item.get("stars")
    location = _location_str(item)

    type_badge = f"<span class='badge badge-blue'>{structure_type}</span>" if structure_type else ""
    stars_str = f"{int(stars)} stelle" if stars and str(stars).isdigit() else ""

    st.markdown(
        f"""
        <div class="result-card">
          <div class="result-name">{name}</div>
          <div class="result-meta">{location}</div>
          <div style="margin-top:0.4rem">
            <span class="badge badge-purple">Alloggio</span>{type_badge}
          </div>
          <p class="result-desc">{stars_str}</p>
        </div>
        """,
        unsafe_allow_html=True,
    )
    return st.button("Vedi dettagli", key=f"det_acc_{idx}", use_container_width=True)
