from pydantic import BaseModel, ConfigDict, JsonValue

type JsonObject = dict[str, JsonValue]


class Contract(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True, allow_inf_nan=False)
