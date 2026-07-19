"""Console entry point for the optional HTTP backend."""

from .app import app


def main() -> None:
    try:
        import uvicorn
    except ModuleNotFoundError as exc:
        raise SystemExit("Install API dependencies first: pip install -e .[api]") from exc
    if app is None:
        raise SystemExit("FastAPI application could not be created")
    uvicorn.run(app, host="127.0.0.1", port=8000, reload=False)


if __name__ == "__main__":
    main()
