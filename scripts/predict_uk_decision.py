"""Compatibility entry point for the model service's prediction CLI."""

from model_service.modules.decision.prediction_cli import main

if __name__ == "__main__":
    raise SystemExit(main())
