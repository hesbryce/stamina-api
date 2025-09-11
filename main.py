# This is a REST API that receives heart rate data from your watch and converts it to stamina scores for web display.
# POST /stamina: Receives heart rate + userID, calculates stamina, stores per user
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
    staminaScore: int  # New format
    userID: str
    
def is_valid_user_id(user_id: str) -> bool:
    """Basic validation for Apple userID format"""
    # Apple userIDs are typically alphanumeric strings
    return bool(re.match(r'^[a-zA-Z0-9._-]+$', user_id)) and len(user_id) > 5

def generate_heart_rate_map():
    map = {}
    mappings = [
        (range(0, 60), 100), (range(60, 64), 99), (range(64, 68), 98), (range(68, 72), 97), (range(72, 76), 96),
        (range(76, 80), 95), (range(80, 84), 94), (range(84, 88), 93), (range(88, 92), 92), (range(92, 96), 91),
        (range(96, 99), 90), (range(99, 100), 89), (range(100, 104), 88), (range(104, 106), 87), (range(106, 108), 86),
        (range(108, 110), 85), (range(110, 112), 84), (range(112, 114), 83), (range(114, 116), 82), (range(116, 120), 81),
        (range(120, 121), 80), (range(121, 123), 79), (range(123, 125), 78), (range(125, 126), 77),
        (range(126, 127), 76), (range(127, 129), 75), (range(129, 131), 74), (range(131, 133), 72),
        (range(133, 135), 70), (range(135, 137), 68), (range(137, 141), 67), (range(141, 143), 65),
        (range(143, 145), 64), (range(145, 147), 62), (range(147, 149), 61), (range(149, 151), 59),
        (range(151, 153), 58), (range(153, 155), 57), (range(155, 157), 55), (range(157, 159), 54),
        (range(159, 161), 53), (range(161, 163), 51), (range(163, 165), 49), (range(165, 167), 47),
        (range(167, 169), 45), (range(169, 171), 41), (range(171, 173), 39), (range(173, 175), 35),
        (range(175, 177), 33), (range(177, 179), 29), (range(179, 181), 27), (range(181, 183), 25),
        (range(183, 185), 23), (range(185, 187), 21), (range(187, 189), 19), (range(189, 191), 17),
        (range(191, 193), 15), (range(193, 195), 13), (range(195, 197), 11), (range(197, 205), 10),
    ]
    for hr_range, stamina in mappings:
        for bpm in hr_range:
            map[bpm] = stamina
    return map

heart_rate_to_stamina = generate_heart_rate_map()

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
            "POST /stamina": "Calculate stamina score from heart rate (requires userID)",
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
def get_stamina(data: HeartRateData):
    # Validate userID
    if not is_valid_user_id(data.userID):
        raise HTTPException(status_code=400, detail="Invalid userID format")
    
    # Calculate stamina
    bpm = round(data.heartRate)
    score = heart_rate_to_stamina.get(bpm, 0)
    color = get_color(score)
    cst = pytz.timezone('America/Chicago')
    timestamp = datetime.now(cst).strftime("%I:%M:%S %p CST")
    
    # Store per user
    result = {
        "heartRate": bpm,
        "staminaScore": score,
        "color": color,
        "timestamp": timestamp,
        "userID": data.userID
    }
    
    user_data[data.userID] = result
    
    # Log successful request (with truncated userID for privacy)
    user_display = f"{data.userID[:8]}..." if len(data.userID) > 8 else data.userID
    print(f"✅ User {user_display} - HR: {bpm} → Score: {score}% — Zone: {color}")
    
    return result

@app.get("/latest")
def latest(userID: str = Query(..., description="User ID from Apple Sign In")):
    # Validate userID
    if not is_valid_user_id(userID):
        raise HTTPException(status_code=400, detail="Invalid userID format")
    
    # Check if user has data
    if userID not in user_data:
        raise HTTPException(
            status_code=404,
            detail=f"No data found for user. Send heart rate to /stamina first."
        )
    
    return user_data[userID]

# Debug endpoint to see how many users we have (remove in production)
@app.get("/debug/users")
def debug_users():
    return {
        "total_users": len(user_data),
        "user_ids": [f"{uid[:8]}..." for uid in user_data.keys()]
    }
