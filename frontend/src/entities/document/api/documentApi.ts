import { http } from "@/shared/api/http";
import type {
  RequestCompleteUpload, RequestCreateDownload, RequestCreateUpload, RequestListDocuments,
  ResponseCompleteUpload, ResponseCreateDownload, ResponseCreateUpload, ResponseListDocuments,
} from "@/shared/api/generated/schema";

export const requestCreateUpload = http.post<RequestCreateUpload, ResponseCreateUpload>("/document/create-upload");
export const requestCompleteUpload = http.post<RequestCompleteUpload, ResponseCompleteUpload>("/document/complete-upload");
export const requestListDocuments = http.post<RequestListDocuments, ResponseListDocuments>("/document/list");
export const requestCreateDownload = http.post<RequestCreateDownload, ResponseCreateDownload>("/document/create-download");
