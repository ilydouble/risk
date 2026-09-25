from pydantic import BaseModel, Field


class DocumentDTO(BaseModel):
    id: str
    companyId: str
    filename: str
    contentType: str
    size: int
    createdAt: str


class RequestCreateUpload(BaseModel):
    companyId: str
    filename: str = Field(min_length=1, max_length=255)
    contentType: str = Field(min_length=1, max_length=128)
    size: int = Field(gt=0, le=10_000_000)


class ResponseCreateUpload(BaseModel):
    documentId: str
    url: str
    headers: dict[str, str]
    expiresIn: int = 60


class RequestCompleteUpload(BaseModel):
    documentId: str


class ResponseCompleteUpload(BaseModel):
    document: DocumentDTO


class RequestListDocuments(BaseModel):
    companyId: str


class ResponseListDocuments(BaseModel):
    items: list[DocumentDTO]


class RequestCreateDownload(BaseModel):
    documentId: str


class ResponseCreateDownload(BaseModel):
    url: str
    expiresIn: int = 60
