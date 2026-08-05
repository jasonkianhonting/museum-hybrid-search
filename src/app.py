import concurrent.futures
import requests
import streamlit as st
import string
from pinecone import Pinecone
from pydantic import BaseModel, Field, ValidationError
from typing import List, Optional


class ArtworkMetadata(BaseModel):
    title: str = Field(default="Untitled")
    artist_title: str = Field(default="Unknown")
    image_url: str = ""
    artwork_type_title: Optional[str] = "Unknown"
    date_display: Optional[str] = "Unknown"
    place_of_origin: Optional[str] = "Unknown"
    medium_display: Optional[str] = "Unknown"
    subject_titles: Optional[str] = ""
    term_titles: List[str] = Field(default_factory=list)


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


# Helper functions
@st.cache_data(show_spinner="Searching for results")
def calculate_embeddings_and_search(input: str, max_results: int):
    API_KEY = st.secrets["PINECONE_API_KEY"]
    HOST = st.secrets["PINECONE_HOST_INDEX"]
    NAMESPACE_INDEX = st.secrets["PINECONE_NAMESPACE_INDEX"]

    pc = Pinecone(api_key=API_KEY)

    index = pc.Index(host=HOST)

    # Convert the query into a dense vector
    dense_query_embedding = pc.inference.embed(
        model=st.secrets["DENSE_EMBEDDING_MODEL"],
        inputs=input,
        parameters={"input_type": "query", "truncate": "END"},
    )

    # Convert the query into a sparse vector
    sparse_query_embedding = pc.inference.embed(
        model=st.secrets["SPARSE_EMBEDDING_MODEL"],
        inputs=input,
        parameters={"input_type": "query", "truncate": "END"},
    )

    query_response = None

    for dense, sparse in zip(dense_query_embedding, sparse_query_embedding):
        query_response = index.query(
            namespace=NAMESPACE_INDEX,
            top_k=max_results,
            vector=dense["values"],
            sparse_vector={
                "indices": sparse["sparse_indices"],
                "values": sparse["sparse_values"],
            },
            include_values=False,
            include_metadata=True,
        )
    return query_response.matches if query_response else []


# This is created as it appears Streamlit's image function does a generic api call
# and uses a very generic if not, no headers at all, causing HTTP 430 errors
@st.cache_data(show_spinner="Downloading batches of images...")
def fetch_image_bytes_batch(url_list: tuple[str, ...]) -> dict[str, bytes]:
    headers = {
        "User-Agent": (
            "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36"
            " (KHTML, like Gecko) Chrome/122.0.0.0 Safari/537.36"
        ),
        "Referer": "https://www.artic.edu/",
        "Accept": ("image/avif,image/webp,image/apng,image/svg+xml,image/*,*/*;q=0.8"),
    }

    results = {}

    def fetch_single(url):
        if not url:
            return url, None
        try:
            response = requests.get(url, headers=headers, timeout=10)
            response.raise_for_status()
            return url, response.content
        except requests.exceptions.RequestException:
            return url, None

    with concurrent.futures.ThreadPoolExecutor(max_workers=5) as executor:
        future_to_url = {
            executor.submit(fetch_single, url): url for url in url_list if url
        }
        for future in concurrent.futures.as_completed(future_to_url):
            url, data = future.result()
            if data:
                results[url] = data

    return results


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


@st.dialog("Artwork Details", width="large")
def show_details(item: ArtworkMetadata):
    left_space, center_box, right_space = st.columns([1, 1, 1])
    with center_box:
        st.title(item["title"], text_alignment="center")
        st.subheader(f"By {item['artist_title']}", text_alignment="center")
        if item["image_url"] in st.session_state.image_cache:
            st.image(
                st.session_state.image_cache[item["image_url"]],
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
        with st.form("data_form", border=False):
            search_query = st.text_input(
                "Search artwork by title, artist, location, subject or term:", value=""
            )
            result_nums = st.slider("Maximum number of results", 10, 20, 10)
            submit_button = st.form_submit_button(label="Search", width="stretch")

        if len(search_query) > 30:
            st.warning("Search query is too long. Please limit to 30 characters.")
            st.stop()

    if submit_button:
        st.session_state.last_submitted_query = search_query
        st.session_state.last_result_nums = result_nums
        if not search_query.strip():
            st.session_state.filtered_catalog = []
            st.session_state.modal_open = False
        else:
            st.session_state.filtered_catalog = calculate_embeddings_and_search(
                search_query, result_nums
            )

    if st.session_state.last_submitted_query.strip():
        filtered_catalog = st.session_state.filtered_catalog

        if not filtered_catalog:
            st.warning("No items match your search criteria.")
        else:
            validated_catalog = []
            for item in filtered_catalog:
                raw_metadata = item.get("metadata", {})
                try:
                    validated_meta = ArtworkMetadata(**raw_metadata)
                    validated_catalog.append({"metadata": validated_meta.model_dump()})
                except ValidationError:
                    continue

            all_urls = tuple(
                item["metadata"].get("image_url", "") for item in validated_catalog
            )
            st.session_state.image_cache = fetch_image_bytes_batch(all_urls)
            columns = st.columns(3, gap="medium")
            for idx, item in enumerate(validated_catalog):
                item_metadata = item["metadata"]
                img_url = item_metadata.get("image_url", "")

                with columns[idx % 3]:
                    with st.container(border=True):
                        if img_url in st.session_state.image_cache:
                            st.image(
                                st.session_state.image_cache[img_url],
                                link=img_url,
                            )
                        else:
                            st.error("Image unavailable")

                        st.subheader(item_metadata.get("title", "Untitled"))
                        st.write(
                            f"**Artist:** {item_metadata.get('artist_title', 'Unknown')}"
                        )

                        st.button(
                            "View Details",
                            key=f"btn_{idx}",
                            width="stretch",
                            type="secondary",
                            on_click=lambda data=item_metadata: (
                                open_modal_callback(),
                                show_details(data),
                            ),
                        )
