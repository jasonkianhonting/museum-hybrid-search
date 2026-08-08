import streamlit as st
import string
from pydantic import ValidationError
from models.models import ArtworkMetadata
from helpers.helpers import get_logger, validate_image_url


def handle_artwork_click(
    item_metadata: dict, open_modal_callback, show_details_callback
):
    open_modal_callback()
    show_details_callback(item_metadata)


def validate_and_cache_catalog(filtered_catalog: list, fetch_image_bytes_batch_func):
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
    st.session_state.image_cache = fetch_image_bytes_batch_func(all_urls)
    return validated_catalog


def render_search_form():
    with st.container():
        with st.form("data_form", border=False):
            search_query = st.text_input(
                "Search artwork by title, artist, location, subject or term:", value=""
            )
            result_nums = st.slider("Maximum number of results", 10, 20, 10)
            submit_button = st.form_submit_button(label="Search", width="stretch")
    return search_query, result_nums, submit_button


def render_artwork_card(
    item_metadata: dict, idx: int, open_modal_callback, show_details_callback
):
    logger = get_logger()
    img_url = item_metadata.get("image_url", "")

    with st.container(border=True):
        try:
            if img_url and img_url.strip() and validate_image_url(img_url):
                logger.info(f"{img_url} has been validated")
                st.image(img_url, link=img_url)
            else:
                logger.error(f"{img_url} is not valid")
                st.html(f"""
                    <div style="width: 100% ; height: 200px; background-color: #f0f2f6; 
                                border: 2px dashed #d1d5db; border-radius: 8px; display: flex; 
                                align-items: center; justify-content: center; color: #6b7280; flex-direction: column; gap: 4px;">
                        <span>⚠️ Image is not available.</span>
                        <span style="font-size: 11px; opacity: 0.7;"></span>
                    </div>
                """)

        except Exception as ex:
            logger.error(f"Unexpected error occurred. Please review logs: {ex}")
            st.html(f"""
                <div style="width: 100% ; height: 200px; background-color: #f0f2f6; 
                            border: 2px dashed #d1d5db; border-radius: 8px; display: flex; 
                            align-items: center; justify-content: center; color: #6b7280; flex-direction: column; gap: 4px;">
                    <span>⚠️ Image is not available.</span>
                    <span style="font-size: 11px; opacity: 0.7;"></span>
                </div>
            """)

        max_title_chars = 27
        metadata_title = item_metadata.get("title", "Untitled")
        display_title = (
            metadata_title[:max_title_chars] + "..."
            if len(metadata_title) > max_title_chars
            else metadata_title
        )

        st.subheader(display_title)
        st.write(f"**Artist:** {item_metadata.get('artist_title', 'Unknown')}")
        st.write(f"**Date:** {item_metadata.get('date_display', 'Unknown')}")

        st.button(
            "View Details",
            key=f"btn_{idx}",
            width="stretch",
            type="secondary",
            on_click=handle_artwork_click,
            args=(item_metadata, open_modal_callback, show_details_callback),
        )


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
