from unittest.mock import MagicMock, patch
import pytest
import streamlit as st
import app


@pytest.fixture(autouse=True)
def mock_streamlit_secrets(monkeypatch):
    fake_secrets = {
        "PINECONE_API_KEY": "fake_key",
        "PINECONE_HOST_INDEX": "fake_host",
        "PINECONE_NAMESPACE_INDEX": "fake_namespace",
        "DENSE_EMBEDDING_MODEL": "dense_model",
        "SPARSE_EMBEDDING_MODEL": "sparse_model",
    }
    monkeypatch.setattr(st, "secrets", fake_secrets)

    for key in list(st.session_state.keys()):
        del st.session_state[key]
    yield


@pytest.fixture(autouse=True)
def run_around_tests():
    for key in list(st.session_state.keys()):
        del st.session_state[key]
    yield


@patch("app.Pinecone")
def test_calculate_embeddings_and_search(mock_pinecone):
    mock_index = MagicMock()
    mock_pc_instance = MagicMock()
    mock_pc_instance.Index.return_value = mock_index

    mock_pc_instance.inference.embed.side_effect = [
        [{"values": [0.1, 0.2]}],  # dense embedding
        [{"sparse_indices": [1], "sparse_values": [0.5]}],  # sparse embedding
    ]

    mock_query_result = MagicMock()
    mock_query_result.matches = [{"id": "1", "metadata": {"title": "Test Art"}}]
    mock_index.query.return_value = mock_query_result

    mock_pinecone.return_value = mock_pc_instance

    results = app.calculate_embeddings_and_search("Monet", 10)
    assert len(results) == 1
    assert results[0]["metadata"]["title"] == "Test Art"


@patch("app.requests.get")
def test_fetch_image_bytes_batch_success(mock_requests_get):
    mock_response = MagicMock()
    mock_response.status_code = 200
    mock_response.content = b"fake_image_bytes"
    mock_requests_get.return_value = mock_response

    urls = ("https://www.artic.edu/iiif/2/test/full/843,/0/default.jpg",)
    results = app.fetch_image_bytes_batch(urls)

    assert urls[0] in results
    assert results[urls[0]] == b"fake_image_bytes"


@patch("app.requests.get")
def test_fetch_image_bytes_batch_failure(mock_requests_get):
    mock_requests_get.side_effect = app.requests.exceptions.RequestException("Error")

    urls = ("https://www.artic.edu/iiif/2/bad/full/843,/0/default.jpg",)
    results = app.fetch_image_bytes_batch(urls)

    assert len(results) == 0


def test_open_modal_callback():
    app.open_modal_callback()
    assert st.session_state.modal_open is True


@patch("app.st.html")
def test_render_chips(mock_st_html):
    tags = [" Impressionism ", "painting", "", "Impressionism"]
    app.render_chips(tags)
    mock_st_html.assert_called_once()
    called_arg = mock_st_html.call_args[0][0]
    assert "Impressionism" in called_arg
    assert "Painting" in called_arg
