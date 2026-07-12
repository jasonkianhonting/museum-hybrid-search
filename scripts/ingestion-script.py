import os
import json
import glob
from dotenv import load_dotenv
from pinecone import Pinecone

# Constants initialisation

load_dotenv()

INPUT_FOLDER = os.getenv("JSON_FILE_PATH")

OUTPUT_FOLDER = os.getenv("OUTPUT_FILE_PATH")

PINECONE_API_KEY = os.getenv("PINECONE_API_KEY")

PINECONE_HOST_INDEX = os.getenv("PINECONE_HOST_INDEX")

pc = Pinecone(api_key=PINECONE_API_KEY)

RAW_INPUT_FOLDER = glob.glob(os.path.join(INPUT_FOLDER, "*.json"))

# Refer to https://api.artic.edu/docs/#images for more information regarding how image url is constructed

IMAGE_PREFIX = "https://www.artic.edu/iiif/2/"

IMAGE_POSTFIX = "/full/843,/0/default.jpg"


def extract_and_format_context(target_keys, max_records=10000, batch_size=96):
    # Batch size is set to 96 due to the sparse model used otherwise it would've thrown 400 error

    valid_items = []
    total_count = 0

    print(f"Processing source files (Target cap: {max_records})...")

    for path in RAW_INPUT_FOLDER:
        if total_count >= max_records:
            break

        if not os.path.exists(path):
            print(f"File skipped (not found): {path}")
            continue

        try:
            with open(path, "r", encoding="utf-8") as f:
                raw_data = json.load(f)

            extracted_item = {key: raw_data.get(key) for key in target_keys}

            # Baseline validation (only retrieves data that's valid)
            if (
                not extracted_item.get("title")
                or extracted_item.get("place_of_origin") is None
                or not extracted_item.get("artist_title")
                or extracted_item.get("medium_display") is None
                or extracted_item.get("artwork_type_title") is None
            ):
                continue

            # Build prose text
            context_string = generate_text_embedding(extracted_item)
            extracted_item["text_for_embedding"] = context_string

            # Fixed the nested quote syntax error here
            img_id = extracted_item.get("image_id", "")
            extracted_item["image_id"] = f"{IMAGE_PREFIX}{img_id}{IMAGE_POSTFIX}"

            valid_items.append(extracted_item)
            total_count += 1

        except json.JSONDecodeError:
            print(f"Syntax Error: Failed to parse valid JSON out of '{path}'.")

    print(
        f"Loaded {len(valid_items)} valid records. Generating embeddings in batches..."
    )

    processed_records = []
    record_id = 1

    for i in range(0, len(valid_items), batch_size):
        batch = valid_items[i : i + batch_size]
        batch_texts = [item["text_for_embedding"] for item in batch]

        try:
            # Batch call for Dense Embeddings
            dense_response = pc.inference.embed(
                model="llama-text-embed-v2",
                inputs=batch_texts,
                parameters={"input_type": "passage", "truncate": "END"},
            )

            # Batch call for Sparse Embeddings
            sparse_response = pc.inference.embed(
                model="pinecone-sparse-english-v0",
                inputs=batch_texts,
                parameters={"input_type": "passage", "truncate": "END"},
            )

            # Zip results back together
            for j, extracted_item in enumerate(batch):
                dense_vals = dense_response.data[j].values
                sparse_indices = sparse_response.data[j].sparse_indices
                sparse_vals = sparse_response.data[j].sparse_values

                # Safe list-to-string transformation for metadata
                subjects = extracted_item.get("subject_titles")
                subject_str = (
                    ", ".join(subjects) if isinstance(subjects, list) else "Unknown"
                )
                final_processed_item = {
                    "id": f"museum_artwork_{record_id}",
                    "values": dense_vals,
                    "sparse_values": {
                        "indices": sparse_indices,
                        "values": sparse_vals,
                    },
                    "metadata": {
                        "title": extracted_item.get("title"),
                        "place_of_origin": extracted_item.get("place_of_origin"),
                        "medium_display": extracted_item.get("medium_display"),
                        "artist_title": extracted_item.get("artist_title"),
                        "subject_titles": subject_str,
                        "date_display": extracted_item.get("date_display"),
                        "artwork_type_title": extracted_item.get("artwork_type_title"),
                        "term_titles": extracted_item.get("term_titles"),
                        "image_url": extracted_item.get("image_id"),
                    },
                }
                processed_records.append(final_processed_item)
                record_id += 1

            print(
                f"Processed {len(processed_records)} / {len(valid_items)} embeddings..."
            )

        except Exception as e:
            print(f"Error during batch inference: {e}")

    return processed_records


def generate_text_embedding(item: dict) -> str:
    # Transforms raw structured museum JSON into fluent prose optimised for dense vector semantic similarity models.
    title = item.get("title") or "Untitled"
    artist = item.get("artist_title") or "Unknown Artist"
    origin = item.get("place_of_origin") or "an unknown region"
    medium = item.get("medium_display") or "unspecified materials"
    date = item.get("date_display") or "an unknown date"
    art_type = item.get("artwork_type_title") or "Artwork"
    subject_titles = item.get("subject_titles") or []
    cleam_subject_titles = [
        subject_title.strip().lower()
        for subject_title in subject_titles
        if subject_title
    ]
    term_titles = item.get("term_titles") or []
    clean_terms = [
        term_title.strip().lower() for term_title in term_titles if term_title
    ]

    # Build a rich, conversational paragraph
    prose = f"A {art_type} artwork titled '{title}' created by {artist} in {date} in {origin}. "
    prose += f"This piece features {medium.lower()}. "

    if cleam_subject_titles:
        prose += (
            f"Associated subject keywords include: {", ".join(cleam_subject_titles)}"
        )

    if clean_terms:
        # e.g., "Associated styles and methods include: modernism, textile, weaving."
        prose += f"Associated styles and methods include: {', '.join(clean_terms)}."

    return prose


# Helper function to prevent overuse of inference tokens. Alternatively, could use model hosted locally and skip this plan b
def save_curated_dataset(data_list, output_filename):
    if not data_list:
        print("Save operation aborted: The provided data array is empty.")
        return False

    try:
        print(f"Committing dataset securely to disk at: '{output_filename}'...")
        with open(output_filename, "w", encoding="utf-8") as out_file:
            json.dump(data_list, out_file, indent=2, ensure_ascii=False)

        print(f"File successfully compiled! Saved {len(data_list)} items.")
        return True

    except Exception as e:
        print(f"Failed to save file to system path: {str(e)}")
        return False


def import_data_to_index(data: list):
    BATCH_SIZE = 250

    try:
        pc = Pinecone(api_key=PINECONE_API_KEY)
        index = pc.Index(host=PINECONE_HOST_INDEX)
        print(f"Streaming {len(data)} vectors to Pinecone...")

        index.upsert(
            namespace=os.getenv("PINECONE_NAMESPACE_INDEX"),
            vectors=data,
            batch_size=BATCH_SIZE,
            show_progress=True,
        )

        print("Successfully uploaded hybrid vectors!")
    except Exception as err:
        print(f"Something went wrong, please try again. Error encountered: {err}")


def load_data_from_file(file_path: str):
    with open(file_path, "r") as file:
        data_list = json.load(file)
        return data_list


if __name__ == "__main__":

    TARGET_DATAKEY = [
        "title",
        "place_of_origin",
        "medium_display",
        "artist_title",
        "subject_titles",
        "date_display",
        "artwork_type_title",
        "term_titles",
        "image_id",
    ]
    allRecords = extract_and_format_context(TARGET_DATAKEY)
    save_curated_dataset(allRecords, OUTPUT_FOLDER)
    import_data_to_index(allRecords)
