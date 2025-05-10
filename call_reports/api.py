from fastapi import FastAPI, HTTPException, Body, status
from fastapi.responses import JSONResponse
from fastapi.encoders import jsonable_encoder
from motor.motor_asyncio import AsyncIOMotorClient
from pymongo.errors import ServerSelectionTimeoutError
from bson import ObjectId
from typing import List
import os
from dotenv import load_dotenv

from .models import Report, CallLog

load_dotenv()

app = FastAPI(title="Call Reports API")

try:
    client = AsyncIOMotorClient(os.environ.get("MONGO_DB_URI"))
    db = client.gdg_ai_hack
    reports_collection = db.reports
    call_logs_collection = db.call_logs
except ServerSelectionTimeoutError:
    raise HTTPException(status_code=503, detail="Failed to connect to MongoDB")


@app.get("/")
async def read_root():
    return {"status": "API is running", "version": "1.0"}


@app.get("/reports", response_model=List[Report])
async def get_all_reports():
    """
    Get all reports from the database
    """
    reports = await reports_collection.find().to_list(1000)
    return reports


@app.get("/reports/{report_id}", response_model=Report)
async def get_report(report_id: str):
    """
    Get a single report by ID
    """
    if not ObjectId.is_valid(report_id):
        raise HTTPException(status_code=400, detail="Invalid report ID format")

    report = await reports_collection.find_one({"_id": ObjectId(report_id)})
    if report is None:
        raise HTTPException(status_code=404, detail="Report not found")

    return report


@app.post("/reports", response_model=Report)
async def create_report(report: Report = Body(...)):
    """
    Create a new report in the database
    """
    report = jsonable_encoder(report)
    new_report = await reports_collection.insert_one(report)
    created_report = await reports_collection.find_one({"_id": new_report.inserted_id})

    return JSONResponse(status_code=status.HTTP_201_CREATED, content=created_report)


@app.get("/call-logs", response_model=List[CallLog])
async def get_all_call_logs():
    """
    Get all call logs from the database
    """
    call_logs = await call_logs_collection.find().to_list(1000)
    return call_logs


@app.get("/call-logs/{call_log_id}", response_model=CallLog)
async def get_call_log(call_log_id: str):
    """
    Get a single call log by ID
    """
    if not ObjectId.is_valid(call_log_id):
        raise HTTPException(status_code=400, detail="Invalid call log ID format")

    call_log = await call_logs_collection.find_one({"_id": ObjectId(call_log_id)})
    if call_log is None:
        raise HTTPException(status_code=404, detail="Call log not found")

    return call_log


@app.post("/call-logs", response_model=CallLog)
async def create_call_log(call_log: CallLog = Body(...)):
    """
    Create a new call log in the database
    """
    call_log = jsonable_encoder(call_log)
    new_call_log = await call_logs_collection.insert_one(call_log)
    created_call_log = await call_logs_collection.find_one(
        {"_id": new_call_log.inserted_id}
    )

    return JSONResponse(status_code=status.HTTP_201_CREATED, content=created_call_log)
