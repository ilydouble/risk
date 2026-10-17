import { useEnterpriseSource } from "@/features/enterprise-browser/model/useEnterpriseSource";
import EnterpriseSourcePicker from "@/features/enterprise-browser/ui/EnterpriseSourcePicker";
import SampleOverview from "./components/SampleOverview";
import UploadedOverview from "./components/UploadedOverview";

export default function OverviewPage() {
  const source = useEnterpriseSource();
  return <div><EnterpriseSourcePicker source={source} sampleTerm="演示" />
    {!source.loading && !source.error && (source.mode === "sample" ? <SampleOverview /> : <UploadedOverview key={source.datasetId} datasetId={source.datasetId} onImported={source.retry} />)}
  </div>;
}
