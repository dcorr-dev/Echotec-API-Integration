from fastapi import FastAPI

app = FastAPI(title="Echotec API Integration")


@app.get("/health")
def health() -> dict[str, str]:
    return {"status": "ok"}
