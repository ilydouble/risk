from pydantic import BaseModel, ConfigDict, Field


class SearchCompaniesInput(BaseModel):
    model_config = ConfigDict(extra="forbid", str_strip_whitespace=True)
    keyword: str = Field(min_length=1, max_length=100)


class ShowCompanyGraphInput(BaseModel):
    model_config = ConfigDict(extra="forbid", str_strip_whitespace=True)
    company_id: str = Field(min_length=1, max_length=64)
    depth: int = Field(default=2, ge=1, le=3)
