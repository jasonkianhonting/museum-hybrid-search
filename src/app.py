import streamlit as st
import time
import string

st.set_page_config(layout="wide")

mock_catalog = []

# Helper functions


def open_modal_callback():
    st.session_state.modal_open = True


def render_chips(tags_list):
    clean_tags = sorted(
        list(set(string.capwords(tag.strip()) for tag in tags_list if tag.strip()))
    )
    chip_style = """
    <style>
        .chip-container {
            display: flex;
            flex-wrap: wrap;
            gap: 8px;
            margin-top: 5px;
            margin-bottom: 15px;
            justify-content: center;
        }
        .chip {
            background-color: #f0f2f6;
            color: #31333F;
            padding: 4px 12px;  
            border-radius: 16px;
            font-size: 0.85rem;
            font-family: inherit;
            border: 1px solid #e0e0e0;
        }
    </style>
    """
    chips_html = "".join([f'<span class="chip">{tag}</span>' for tag in clean_tags])
    st.html(f"{chip_style}<div class='chip-container'>{chips_html}</div>")


# Define the Dialog function
@st.dialog("Artwork Details", width="large")
def show_details(item):

    left_space, center_box, right_space = st.columns([1, 1, 1])
    with center_box:
        st.title(item["title"], text_alignment="center")
        st.subheader(f"By {item['artist_title']}", text_alignment="center")
        st.image(item["image_url"], width="stretch")
        st.space("small")
        st.markdown(f"**Type:** {item['artwork_type_title']}", text_alignment="center")
        st.markdown(f"**Date:** {item['date_display']}", text_alignment="center")
        st.markdown(f"**Origin:** {item['place_of_origin']}", text_alignment="center")
        st.markdown(f"**Medium:** {item['medium_display']}", text_alignment="center")

    col1, col2 = st.columns(2, vertical_alignment="center")
    with col1:
        st.markdown("**Subjects**", text_alignment="center")
        subjects_list = item["subject_titles"].split(",")
        render_chips(subjects_list)

    with col2:

        st.markdown("**Terms**", text_alignment="center")
        render_chips(item["term_titles"])


# Sidebar Configuration
with st.sidebar:
    st.title("Digital Louvre")
    search_query = st.text_input(
        "Search artwork by title, artist or location:", value=""
    )

# Main App Interface
st.title("Digital Louvre")

st.divider()

if not search_query.strip():
    st.info("Use the sidebar text field to search and filter the art catalog.")
    st.session_state.modal_open = False
else:
    # Filter data based on query
    filtered_catalog = [
        item
        for item in mock_catalog
        if (
            search_query.lower() in item["title"].lower()
            or search_query.lower() in item["artist_title"].lower()
            or search_query.lower() in item["place_of_origin"].lower()
        )
    ]

    gallery_view = st.empty()

    if not st.session_state.modal_open:
        with gallery_view.container():

            with st.container(border=True):
                st.skeleton(height=400)
                st.write("")
                st.skeleton(height=35)
                st.write("")

            time.sleep(0.8)

    with gallery_view.container():
        if not filtered_catalog:
            st.warning("No items match your search criteria.")
        else:
            columns = st.columns(3)
            for idx, item in enumerate(filtered_catalog):
                with columns[idx % 3]:
                    with st.container(border=True):
                        st.image(item["image_url"], width="stretch")
                        st.subheader(item["title"])
                        st.write(f"**Artist:** {item['artist_title']}")

                        if st.button(
                            "View Details",
                            key=f"btn_{idx}",
                            use_container_width=True,
                            type="primary",
                            on_click=open_modal_callback,
                        ):
                            show_details(item)

    st.session_state.modal_open = False
