from model_service.adapters.contracts import (
    AdapterError,
    AdapterSpec,
    Artifact,
    ArtifactSpec,
    ExecutionContext,
    InputSpec,
    InspectionStatus,
    MetricEvent,
    ModelAdapter,
    Operation,
    OperationRequest,
    OperationResult,
    OperationSpec,
    StageEvent,
)

from .schemas import (
    EvaluationSummary,
    InspectionSummary,
    InspectParameters,
    Parameters,
    PredictionSummary,
    PredictParameters,
    TrainingSummary,
    TrainParameters,
)


class RiskGNNAdapter(ModelAdapter):
    runner_id = "riskgnn-node-edge"

    @classmethod
    def describe(cls) -> AdapterSpec:
        source = {"dataset": InputSpec(kind="file", formats=["zip"])}
        model = {"model": InputSpec(kind="directory", formats=["riskgnn-model-v1"])}
        return AdapterSpec(
            adapter_id=cls.runner_id,
            adapter_version="1.0.0",
            name=cls.runner_id,
            description="Singapore smoke-v1; existing research network and frozen subset",
            operations={
                Operation.INSPECT: OperationSpec(
                    inputs=source,
                    parameters_schema=InspectParameters.model_json_schema(),
                    default_parameters=InspectParameters().model_dump(),
                    result_schema=InspectionSummary.model_json_schema(),
                ),
                Operation.TRAIN: OperationSpec(
                    inputs=source,
                    parameters_schema=TrainParameters.model_json_schema(),
                    default_parameters=TrainParameters().model_dump(),
                    result_schema=TrainingSummary.model_json_schema(),
                    artifacts={"model": ArtifactSpec(kind="directory", format="riskgnn-model-v1")},
                ),
                Operation.EVALUATE: OperationSpec(
                    inputs=model,
                    parameters_schema=Parameters.model_json_schema(),
                    result_schema=EvaluationSummary.model_json_schema(),
                    artifacts={
                        "report": ArtifactSpec(kind="directory", format="riskgnn-evaluation-v1")
                    },
                ),
                Operation.PREDICT: OperationSpec(
                    inputs=model,
                    parameters_schema=PredictParameters.model_json_schema(),
                    result_schema=PredictionSummary.model_json_schema(),
                ),
            },
        )

    def execute(self, request: OperationRequest, context: ExecutionContext) -> OperationResult:
        context.check_cancelled()
        try:
            if request.operation == Operation.INSPECT:
                return self._inspect(request, context)
            if request.operation == Operation.TRAIN:
                return self._train(request, context)
            if request.operation == Operation.EVALUATE:
                return self._evaluate(request, context)
            if request.operation == Operation.PREDICT:
                return self._predict(request, context)
            raise AdapterError("ADAPTER_OPERATION_UNSUPPORTED", str(request.operation))
        except AdapterError:
            raise
        except (ValueError, KeyError, FileNotFoundError) as error:
            raise AdapterError("RISKGNN_INPUT_INVALID", str(error)) from error

    def _inspect(self, request: OperationRequest, context: ExecutionContext) -> OperationResult:
        from model_service.datasets.dispatch import validate

        context.emit(StageEvent(stage="validating"))
        try:
            data = validate(request.inputs["dataset"].path, context.work_dir / "validated")
        except (ValueError, KeyError, FileNotFoundError) as error:
            return OperationResult(
                data={
                    "compatibility": InspectionStatus.INCOMPATIBLE,
                    "issues": [{"code": "RISKGNN_DATASET_INVALID", "message": str(error)}],
                }
            )
        compatible = self.runner_id in data["supportedRunnerIds"]
        return OperationResult(
            data={
                **data,
                "compatibility": InspectionStatus.COMPATIBLE
                if compatible
                else InspectionStatus.INCOMPATIBLE,
                "issues": []
                if compatible
                else [
                    {
                        "code": "RISKGNN_ANALYSIS_ONLY",
                        "message": "No training runner for this dataset",
                    }
                ],
            },
            effective_config=request.parameters,
        )

    def _train(self, request: OperationRequest, context: ExecutionContext) -> OperationResult:
        from model_service.adapters.prepare import prepare
        from model_service.adapters.singapore import validate
        from model_service.files import read_json
        from model_service.training.pipeline import train

        parameters = TrainParameters.model_validate(request.parameters)
        context.emit(StageEvent(stage="validating"))
        validated = context.work_dir / "validated"
        validate(request.inputs["dataset"].path, validated)
        context.emit(StageEvent(stage="preparing"))
        prepared = context.work_dir / "prepared"
        prepare(validated, prepared)
        context.emit(StageEvent(stage="training"))
        model = context.output_dir / "model"

        def metric(row):
            for name, group in (("trainLoss", "train"), ("validationLoss", "validation")):
                context.emit(
                    MetricEvent(name="loss", value=row[name], step=row["epoch"], group=group)
                )

        profile = train(
            prepared, model, parameters.epochs, runner_id=self.runner_id, metric_callback=metric
        )
        return OperationResult(
            data={"profile": profile, "companies": read_json(model / "ids.json")[:100]},
            artifacts={"model": Artifact(path="model", format="riskgnn-model-v1")},
            effective_config=parameters.model_dump(),
        )

    def _evaluate(self, request: OperationRequest, context: ExecutionContext) -> OperationResult:
        from model_service.files import write_json
        from model_service.training.pipeline import evaluate

        context.emit(StageEvent(stage="testing"))
        report = evaluate(request.inputs["model"].path, output=context.output_dir / "report")
        report["modelSha256"] = request.inputs["model"].sha256
        write_json(context.output_dir / "report" / "metrics.json", report)
        return OperationResult(
            data={"report": report},
            artifacts={"report": Artifact(path="report", format="riskgnn-evaluation-v1")},
        )

    def _predict(self, request: OperationRequest, context: ExecutionContext) -> OperationResult:
        import torch

        from model_service.runtime.predictor import Predictor

        torch.set_num_threads(2)
        parameters = PredictParameters.model_validate(request.parameters)
        context.emit(StageEvent(stage="predicting"))
        try:
            items = Predictor(request.inputs["model"].path).predict(parameters.company_ids)
        except KeyError as error:
            raise AdapterError(
                "RISKGNN_COMPANY_NOT_FOUND", str(error), path="/company_ids"
            ) from error
        return OperationResult(
            data={"items": [dict(item) for item in items]}, effective_config=parameters.model_dump()
        )


class RiskGNNNodeOnlyAdapter(RiskGNNAdapter):
    runner_id = "riskgnn-node-only"
