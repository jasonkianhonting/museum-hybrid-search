import concurrent.futures
import requests
import streamlit as st
import logging
from pinecone import Pinecone
from urllib.parse import urlparse


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
    results = {}

    with concurrent.futures.ThreadPoolExecutor(max_workers=5) as executor:
        future_to_url = {
            executor.submit(fetch_single, url): url for url in url_list if url
        }
        for future in concurrent.futures.as_completed(future_to_url):
            url, data = future.result()
            if data:
                results[url] = data

    return results


def fetch_single(url):
    logger = get_logger()
    if not url:
        return url, None
    try:
        headers = {
            "User-Agent": (
                "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36"
                " (KHTML, like Gecko) Chrome/122.0.0.0 Safari/537.36"
            ),
            "Referer": "https://www.artic.edu/",
            "Accept": (
                "image/avif,image/webp,image/apng,image/svg+xml,image/*,*/*;q=0.8"
            ),
        }
        logger.info(f"Attempting to fetch image from {url}")
        response = requests.get(url, headers=headers, timeout=10)
        logger.info(f"Successfully fetched image from {url}. See response, {response}")
        response.raise_for_status()
        return url, response.content
    except requests.exceptions.RequestException as request_exception:
        logger.error(
            f"Failed to fetch image from {url}. Exception message: {request_exception}"
        )
        return url, None


def validate_image_url(url: str):
    logger = get_logger()
    try:
        result = urlparse(url).path.strip("/").split("/")
        image_id = result[2]
        if image_id.lower() == "none":
            logger.error("Image Id is null")
            return False

        return True

    except Exception as ex:
        logger.error(f"Unexpected error occurred, please review log: {ex}")
        return False


@st.cache_resource
def get_logger(name: str = "DigitalLouvreApp"):
    logger = logging.getLogger(name)
    logger.setLevel(logging.INFO)

    # Check if handlers already exist to prevent stacking/initialising more loggers
    if not logger.handlers:
        console_handler = logging.StreamHandler()
        formatter = logging.Formatter(
            "%(asctime)s | %(levelname)s | %(name)s | %(message)s"
        )
        console_handler.setFormatter(formatter)
        logger.addHandler(console_handler)

        file_handler = logging.FileHandler("app.log")
        file_handler.setFormatter(formatter)
        logger.addHandler(file_handler)

    return logger
