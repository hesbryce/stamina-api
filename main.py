# This is a REST API that receives stamina scores from your watch and stores them for web display.
# POST /stamina: Receives stamina score + userID, stores per user
# GET /latest: Returns stored stamina data for specific user
# GET /: API documentation
# GET /health: Server status check

from fastapi import FastAPI, HTTPException, Query
from pydantic import BaseModel
from datetime import datetime
from fastapi.middleware.cors import CORSMiddleware
from typing import Optional
import pytz
import re

app = FastAPI()

# CORS middleware
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["GET", "POST", "OPTIONS"],
    allow_headers=["*"],
    allow_credentials=False,
)

# Multi-user storage - dictionary keyed by userID
user_data = {}

class StaminaData(BaseModel):
    staminaScore: int  # Comes pre-calculated from watch
    userID: str  # Required - comes from Apple Sign In

def is_valid_user_id(user_id: str) -> bool:
    """Basic validation for Apple userID format"""
    # Apple userIDs are typically alphanumeric strings
    return bool(re.match(r'^[a-zA-Z0-9._-]+$', user_id)) and len(user_id) > 5

def get_color(stamina_score):
    if stamina_score >= 91:
        return "blue"
    elif stamina_score >= 86:
        return "green"
    elif stamina_score >= 76:
        return "green-yellow"
    elif stamina_score >= 51:
        return "yellow"
    elif stamina_score >= 40:
        return "yellow-orange"
    elif stamina_score >= 30:
        return "orange"
    else:
        return "red"

@app.get("/")
def root():
    cst = pytz.timezone('America/Chicago')
    timestamp = datetime.now(cst).strftime("%I:%M:%S %p CST")
    return {
        "message": "Stamina API with Apple Sign In support!",
        "status": "healthy",
        "timestamp": timestamp,
        "authentication": "Apple Sign In (userID required)",
        "endpoints": {
            "POST /stamina": "Store stamina score from watch (requires userID)",
            "GET /health": "Health check endpoint",
            "GET /latest?userID=xxx": "Fetch the most recent stamina result for user"
        }
    }

@app.get("/health")
def health():
    cst = pytz.timezone('America/Chicago')
    timestamp = datetime.now(cst).strftime("%I:%M:%S %p CST")
    return {
        "status": "ok",
        "timestamp": timestamp,
        "service": "stamina-api",
        "users_count": len(user_data)
    }

@app.post("/stamina")
def store_stamina(data: StaminaData):
    # Validate userID
    if not is_valid_user_id(data.userID):
        raise HTTPException(status_code=400, detail="Invalid userID format")
    
    # Validate stamina score range
    if not (0 <= data.staminaScore <= 100):
        raise HTTPException(status_code=400, detail="Stamina score must be between 0-100")
    
    # Determine color from stamina score
    color = get_color(data.staminaScore)
    cst = pytz.timezone('America/Chicago')
    timestamp = datetime.now(cst).strftime("%I:%M:%S %p CST")
    
    # Store user data
    result = {
        "staminaScore": data.staminaScore,
        "color": color,
        "timestamp": timestamp,
        "userID": data.userID
    }
    
    user_data[data.userID] = result
    
    # Log successful request (with truncated userID for privacy)
    user_display = f"{data.userID[:8]}..." if len(data.userID) > 8 else data.userID
    print(f"✅ User {user_display} - Stamina: {data.staminaScore}% — Zone: {color}")
    
    return {"status": "success", "message": "Stamina data stored"}

@app.get("/latest")
def latest(userID: str = Query(..., description="User ID from Apple Sign In")):
    # Validate userID
    if not is_valid_user_id(userID):
        raise HTTPException(status_code=400, detail="Invalid userID format")
    
    # Check if user has data
    if userID not in user_data:
        raise HTTPException(
            status_code=404,
            detail=f"No data found for user. Send stamina to /stamina first."
        )
    
    return user_data[userID]

# Debug endpoint to see how many users we have (remove in production)
@app.get("/debug/users")
def debug_users():
    return {
        "total_users": len(user_data),
        "user_ids": [f"{uid[:8]}..." for uid in user_data.keys()]
    }
