"""HTTP entry point; model operations run through the model-owned CLI."""

import argparse

import uvicorn


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("command", choices=["serve"])
    parser.parse_args()
    uvicorn.run(
        "model_service.app:create_app", factory=True, host="0.0.0.0", port=8000, access_log=False
    )


if __name__ == "__main__":
    main()
