from pydantic import BaseModel, Field
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


class SearchParameters(BaseModel):
    search_query: str = Field(
        ..., max_length=30, description="User search query up to 30 chars"
    )
    result_nums: int = Field(
        ..., ge=10, le=20, description="Slider limit between 10 and 20"
    )
