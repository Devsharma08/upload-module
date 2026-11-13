from fastapi import FastAPI


app = FastAPI(
    title="EGCA Pipeline — Stage 1",
    version="0.1.0",
    description="Upload intake and preparation control-plane API.",
)


@app.get("/healthz", tags=["operations"])
def health_check() -> dict[str, str]:
    return {"status": "ok"}
