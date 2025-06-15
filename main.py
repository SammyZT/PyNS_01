from FastAPIWrapper import app

# Optionally, you can add a __main__ block for local testing:
if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)