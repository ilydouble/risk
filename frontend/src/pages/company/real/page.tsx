import { useSearchParams } from "react-router-dom";
import SampleProfile from "./SampleProfile";
import UploadedProfile from "./UploadedProfile";

export default function CompanyProfilePage() {
  const [params] = useSearchParams();
  return params.get("source") === "uploaded" ? <UploadedProfile /> : <SampleProfile />;
}
