from fastapi import FastAPI

app = FastAPI(title="Upload Module")


@app.get("/health")
async def health() -> dict[str, str]:
    return {"status": "ok"}
