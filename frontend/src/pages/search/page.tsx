import { useEnterpriseSource } from "@/features/enterprise-browser/model/useEnterpriseSource";
import EnterpriseSourcePicker from "@/features/enterprise-browser/ui/EnterpriseSourcePicker";
import SampleSearch from "./components/SampleSearch";
import UploadedSearch from "./components/UploadedSearch";

export default function SearchPage() {
  const source = useEnterpriseSource();
  return <div><EnterpriseSourcePicker source={source} />
    {!source.loading && !source.error && (source.mode === "sample" ? <SampleSearch /> : <UploadedSearch key={source.datasetId} datasetId={source.datasetId} source={source.selected} onImported={source.retry} />)}
  </div>;
}
