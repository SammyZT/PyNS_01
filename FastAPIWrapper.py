from fastapi import FastAPI, Request, Response
from fastapi.staticfiles import StaticFiles
from PyNS import Log, Survey
from typing import Optional
from fastapi.responses import RedirectResponse
from uuid import uuid4
from pydantic import BaseModel
import pandas as pd
import numpy as np

app = FastAPI()

class AddLogRequest(BaseModel):
    log_path: str
    name: str = "Position 1"
    session_id: str = "default"

class GetResRequest(BaseModel):
    session_id: str = "default"

class SetPeriodsRequest(BaseModel):
    session_id: str = "default"
    times: Optional[list] = None  # List of time periods to set, e.g., ["day", "evening", "night"]

class GetPeriodsRequest(BaseModel):
    session_id: str = "default"
    times: Optional[list] = None  # List of time periods to set, e.g., ["day", "evening", "night"]

class GetL90s(BaseModel):
    session_id: str = "default"
    cols: list = None
    by_date: bool = True
    day_t: str = "60min" 
    evening_t: str = "60min"
    night_t: str = "15min"

class GetLmaxSpectra(BaseModel):

    session_id: str = "default"
    n: int = 10
    t: str = "2min"
    period: str = "nights"
    
class GetLAeqSpectra(BaseModel):
    session_id: str = "default"
    leq_cols: list = None  

# In-memory store for Survey objects, keyed by session or user id (for demo, use a global singleton)
survey_store = {}

@app.post("/survey/on_load")
def survey_on_load():
    # In a real-world app, verify user credentials here
    session_id = str(uuid4())
    #sions[session_id] = {"user": "example_user", "preferences": {}}
    
    # Set the session ID in a cookie
    return "loaded"

@app.post("/survey/add_log")
def survey_add_log(req: AddLogRequest):
    print(f"Adding log: {req.log_path} with name: {req.name} for session_id: {req.session_id}")
    if not req.log_path:
        return {"error": "Log path is required."}
    session_id = req.session_id
    survey = survey_store.get(session_id)
    if survey is None:
        print(f"Creating new survey for session_id: {session_id}")
        survey = Survey()
        survey_store[session_id] = survey
    log = Log(req.log_path)
    survey.add_log(log, req.name)
    return {"status": f"Log {req.name} added", "session_id": session_id}

@app.post("/survey/set_periods")
def survey_set_periods(req: SetPeriodsRequest):
    survey = survey_store.get(req.session_id)
    if survey is None:
        return {"error": f"No survey found for {req.session_id} . Please add a log first."}
    survey.set_periods(times=req.times)
    return {"status": "periods set", "session_id": req.session_id}

@app.post("/survey/get_periods")
def survey_get_periods(req: GetPeriodsRequest ):
    survey = survey_store.get(req.session_id)
    if survey is None:
        return {"error": "No survey found for this session. Please add a log first."}
    
    result = survey.get_periods
    if isinstance(result, pd.DataFrame):
        result = CleanDataFrame(result)
        return result
    else:
        return {"error": f"Expected DataFrame, got {type(result)}"}

@app.post("/survey/resi_summary")
def survey_resi_summary(req: GetResRequest):
    print(f"Processing survey_resi_summary for session_id: {req.session_id}")
    # Defensive: ensure req.session_id exists and is a string
    session_id = getattr(req, 'session_id', None)
    if not session_id or not isinstance(session_id, str):
        return {"error": "session_id is required in the JSON body as a string."}
    survey = survey_store.get(session_id)

    if survey is None:
        return {"error": "No survey found for this session. Please add a log first."}

    result = survey.resi_summary()

    if isinstance(result, pd.DataFrame):
        result = CleanDataFrame(result)
        return result
    else:
        return {"error": f"Expected DataFrame, got {type(result)}"}

@app.post("/survey/modal_l90")
def survey_modal_l90(req: GetL90s):
    survey = survey_store.get(req.session_id)
    if survey is None:
        return {"error": "No survey found for this session. Please add a log first."}
    result = survey.modal_l90(cols=req.cols, by_date=req.by_date, day_t=req.day_t, evening_t=req.evening_t, night_t=req.night_t)

    return result.to_dict()

@app.post("/survey/lmax_spectra")
def survey_lmax_spectra(req: GetLmaxSpectra):
    survey = survey_store.get(req.session_id)
    if survey is None:
        return {"error": "No survey found for this session. Please add a log first."}
    result = survey.lmax_spectra(n=req.n, t=req.t, period=req.period)
    return result.to_dict()

@app.post("/survey/typical_leq_spectra")
def survey_typical_leq_spectra(req: GetLAeqSpectra):
    survey = survey_store.get(req.session_id)
    if survey is None:
        return {"error": "No survey found for this session. Please add a log first."}
    result = survey.typical_leq_spectra(leq_cols=req.leq_cols)
    #return result.to_dict(orient='records')
    return result.to_dict(orient='list')


# Serve static files (including test_api.html) from the current directory
app.mount("/static", StaticFiles(directory="."), name="static")

@app.get("/")
def root():
    return RedirectResponse(url="/static/test_api.html")


def CleanDataFrame(result: pd.DataFrame) -> dict:
    
    """
    Clean a DataFrame for JSON serialization:
    """
    # Convert all column names to strings
    result.columns = [str(col) for col in result.columns]
    # Reset index if it's not a simple RangeIndex
    if not isinstance(result.index, pd.RangeIndex):
        result = result.reset_index()
    # Replace NaN/inf/-inf values with None for JSON compliance
    result = result.replace([np.nan, np.inf, -np.inf], None)

    return {"data": result.to_dict(orient='records')}

# --- MCP ENDPOINTS ---
@app.get("/v1/health")
def mcp_health():
    return {"status": "ok"}

@app.get("/v1/models")
def mcp_models():
    log_methods = [m for m in dir(Log) if not m.startswith('_') and callable(getattr(Log, m))]
    survey_methods = [m for m in dir(Survey) if not m.startswith('_') and callable(getattr(Survey, m))]
    return {
        "object": "list",
        "data": [
            {"id": f"log.{m}", "object": "model"} for m in log_methods
        ] + [
            {"id": f"survey.{m}", "object": "model"} for m in survey_methods
        ]
    }

@app.post("/v1/completions")
async def mcp_completions(request: Request):
    body = await request.json()
    model = body.get("model")
    input_data = body.get("input", {})
    # Parse model string
    if model and model.startswith("log."):
        method = model.split(".", 1)[1]
        obj = Log(**input_data.get("init", {}))
    elif model and model.startswith("survey."):
        method = model.split(".", 1)[1]
        # Use session_id if provided, else create new Survey
        session_id = input_data.get("session_id")
        if session_id and session_id in survey_store:
            obj = survey_store[session_id]
        else:
            obj = Survey(**input_data.get("init", {}))
            if session_id:
                survey_store[session_id] = obj
    else:
        return {"error": "Unknown model"}
    # Call the method
    func = getattr(obj, method, None)
    if not func or not callable(func):
        return {"error": f"Method {method} not found"}
    params = input_data.get("params", {})
    try:
        output = func(**params) if params else func()
    except Exception as e:
        return {"error": str(e)}
    # If output is a DataFrame, convert to records
    try:
        import pandas as pd
        import numpy as np
        if isinstance(output, pd.DataFrame):
            output = output.replace([np.nan, np.inf, -np.inf], None)
            output = output.to_dict(orient='records')
    except Exception:
        pass
    return {
        "object": "completion",
        "model": model,
        "output": output
    }