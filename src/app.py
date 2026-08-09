import streamlit as st
from pydantic import ValidationError
from helpers.helpers import (
    calculate_embeddings_and_search,
    fetch_image_bytes_batch,
    get_logger,
    validate_image_url,
)
from models.models import ArtworkMetadata, SearchParameters
from components.components import (
    render_artwork_card,
    render_search_form,
    validate_and_cache_catalog,
    render_chips,
)

logger = get_logger()
st.set_page_config(layout="wide", page_icon="🏛️")

# Html to compensate Streamlit's limitations
st.html("""
    <style>
    /* Targets images inside your specific gallery container */
    [data-element-user-key="artwork-gallery-component"] img {
        height: 200px !important;
        object-fit: cover !important;
        width: 100% !important;
    }
    [data-testid="stVerticalBlock"] > [data-testid="stContainer"] {
        display: flex;
        flex-direction: column;
        height: 100%;
    }

    [data-testid="stImage"] img {
        width: 864px !important;
        height: 200px !important;
        object-fit: contain; 
    }
    
    </style>
    """)

# Initialize session state variables safely
if "modal_open" not in st.session_state:
    st.session_state.modal_open = False
if "last_submitted_query" not in st.session_state:
    st.session_state.last_submitted_query = ""
if "last_result_nums" not in st.session_state:
    st.session_state.last_result_nums = 10
if "filtered_catalog" not in st.session_state:
    st.session_state.filtered_catalog = []
if "is_loading" not in st.session_state:
    st.session_state.is_loading = False
if "image_cache" not in st.session_state:
    st.session_state.image_cache = {}


def open_modal_callback():
    st.session_state.modal_open = True


@st.dialog("Artwork Details", width="large")
def show_details(item: ArtworkMetadata):
    left_space, center_box, right_space = st.columns([1, 1, 1])
    with center_box:
        st.title(item["title"], text_alignment="center")
        st.subheader(f"By {item['artist_title']}", text_alignment="center")
        logger.info(f"{item["image_url"]} is being used to showcase the image")
        if validate_image_url(item["image_url"]):
            st.image(
                item["image_url"],
                width="stretch",
                link=item["image_url"],
            )
        else:
            st.error("Image unavailable")
        st.space("small")
        st.markdown(f"**Type:** {item['artwork_type_title']}", text_alignment="center")
        st.markdown(f"**Date:** {item['date_display']}", text_alignment="center")
        st.markdown(f"**Origin:** {item['place_of_origin']}", text_alignment="center")
        st.markdown(f"**Medium:** {item['medium_display']}", text_alignment="center")

    col1, col2 = st.columns(2, vertical_alignment="top")
    with col1:
        st.html(
            "<div style='text-align: center; font-weight: 600;'>Subjects</div>",
        )
        subjects_list = (
            item["subject_titles"].split(",") if item.get("subject_titles") else []
        )
        render_chips(subjects_list)

    with col2:
        st.html(
            "<div style='text-align: center; font-weight: 600;'>Terms</div>",
        )
        render_chips(item.get("term_titles", []))


st.title("Digital Louvre", text_alignment="center")
st.divider()

left_container, main_container, right_container = st.columns([1, 3, 1])

with main_container:
    with st.container():
        search_query, result_nums, submit_button = render_search_form()
        st.toast(
            "This app might not function as expected in Safari for iOS devices. Please make sure you use another web browser for the optimum viewing experience.",
            duration="long",
        )

        if len(search_query) > 30:
            st.warning("Search query is too long. Please limit to 30 characters.")
            st.stop()

    if submit_button:
        try:

            search_params = SearchParameters(
                search_query=search_query, result_nums=result_nums
            )
            st.session_state.last_submitted_query = search_query
            st.session_state.last_result_nums = result_nums
            if not search_query.strip():
                st.session_state.filtered_catalog = []
                st.session_state.modal_open = False
            else:
                logger.info(
                    f"Calculating embeddings for {search_query} with a maximum results of {result_nums}"
                )
                st.session_state.filtered_catalog = calculate_embeddings_and_search(
                    search_query, result_nums
                )
        except ValidationError as e:
            for error in e.errors():
                if "search_query" in error.get("loc", ()):
                    st.warning(
                        "Search query is too long. Please limit to 30 characters."
                    )
                else:
                    st.warning(error.get("msg", "Invalid input configuration."))
            st.stop()

    last_query = st.session_state.get("last_submitted_query", "")
    if last_query.strip():
        filtered_catalog = st.session_state.get("filtered_catalog", [])

        if not filtered_catalog:
            st.warning("No items match your search criteria.")
        else:
            validated_catalog = validate_and_cache_catalog(
                filtered_catalog, fetch_image_bytes_batch
            )

            columns = st.columns(3, gap="medium")
            for idx, item in enumerate(filtered_catalog):
                with columns[idx % 3]:
                    render_artwork_card(
                        item["metadata"], idx, open_modal_callback, show_details
                    )
