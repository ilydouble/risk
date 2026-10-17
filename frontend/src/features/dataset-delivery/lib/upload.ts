import { requestCreateDatasetUpload, requestCompleteDatasetUpload } from "@/entities/modeling/api/modelingApi";
import { uploadObject } from "@/shared/api/objectTransfer";

export async function uploadDatasetPackage(file: File, name: string, options: {
  sourcePreparationId?: string;
  progress: (value: number) => void;
  created?: (datasetId: string) => void;
}) {
  const ticket = await requestCreateDatasetUpload({ name, filename: file.name,
    contentType: file.type || "application/zip", size: file.size,
    sourcePreparationId: options.sourcePreparationId });
  options.created?.(ticket.datasetId);
  await uploadObject(ticket.url, ticket.headers, file, options.progress);
  await requestCompleteDatasetUpload({ datasetId: ticket.datasetId });
  return ticket.datasetId;
}
