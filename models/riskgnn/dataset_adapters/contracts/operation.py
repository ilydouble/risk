from riskgnn.dataset_adapters.contracts.enterprise import EnterpriseExportSummary
from riskgnn.dataset_adapters.contracts.inspection import ValidatedDataset


class InspectionOutput(ValidatedDataset):
    """Public inspect result after successful validation AND enterprise export."""

    enterpriseData: EnterpriseExportSummary
