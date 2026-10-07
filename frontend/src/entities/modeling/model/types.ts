import type {
  ResponseGetDataset,
  ResponseGetRun,
  ResponseGetModel,
  ResponseRunEvents,
} from "@/shared/api/generated/schema";
export type ModelingDataset = ResponseGetDataset["dataset"];
export type ModelingRun = ResponseGetRun["run"];
export type ModelingVersion = ResponseGetModel["model"];
export type ModelingEvent = ResponseRunEvents["items"][number];
