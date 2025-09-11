# This is a REST API that receives heart rate data from your watch and converts it to stamina scores for web display.
# POST /stamina: Receives heart rate, calculates stamina, stores result (REQUIRES AUTH OR USER_ID)
# GET /latest: Returns stored stamina data for web dashboard (REQUIRES AUTH OR USER_ID)
# GET /: API documentation
# GET /health: Server status check

from fastapi import FastAPI, HTTPException, Depends, Query
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from pydantic import BaseModel
from datetime import datetime
from fastapi.middleware.cors import CORSMiddleware
from typing import Optional
import pytz
import os
import re

app = FastAPI()

# CORS middleware - updated for authentication
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["GET", "POST", "OPTIONS"],
    allow_headers=["*", "Authorization"],
    allow_credentials=False,
)

# Security setup
security = HTTPBearer()

# Get secret token from environment variable (for backward compatibility)
SECRET_TOKEN = os.getenv("SECRET_TOKEN")
if not SECRET_TOKEN:
    raise RuntimeError("SECRET_TOKEN environment variable is not set")

# Multi-user storage - dictionary keyed by userID
user_data = {}
# Keep single-user storage for backward compatibility
latest_value = None

class HeartRateData(BaseModel):
    heartRate: float
    userID: Optional[str] = None

def verify_token(credentials: HTTPAuthorizationCredentials = Depends(security)):
    """Verify the bearer token for backward compatibility"""
    if credentials.credentials != SECRET_TOKEN:
        raise HTTPException(
            status_code=401,
            detail="Invalid authentication token",
            headers={"WWW-Authenticate": "Bearer"}
        )
    return credentials

def validate_user_id(user_id: str) -> bool:
    """Basic validation for Apple userID format"""
    if not user_id or len(user_id) < 10:
        return False
    # Apple user IDs: 6 digits, dot, 32 hex chars, dot, 4 digits
    # Example: 000301.87512a694c344ba585b5d437e995bf62.2105
    if not re.match(r'^\d{6}\.[a-f0-9]{32}\.\d{4}$', user_id):
        return False
    return True

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

# Public endpoints (no auth required)
@app.get("/")
def root():
    cst = pytz.timezone('America/Chicago')
    timestamp = datetime.now(cst).strftime("%I:%M:%S %p CST")
    return {
        "message": "Stamina API is running!",
        "status": "healthy",
        "timestamp": timestamp,
        "endpoints": {
            "POST /stamina": "Calculate stamina score from heart rate (requires auth or userID)",
            "GET /health": "Health check endpoint",
            "GET /latest": "Fetch the most recent stamina result (requires auth or userID)"
        },
        "users_active": len(user_data)
    }

@app.get("/health")
def health():
    cst = pytz.timezone('America/Chicago')
    timestamp = datetime.now(cst).strftime("%I:%M:%S %p CST")
    return {
        "status": "ok",
        "timestamp": timestamp,
        "service": "stamina-api",
        "active_users": len(user_data)
    }

# Protected endpoints (auth required OR userID provided)
@app.post("/stamina")
def get_stamina(data: HeartRateData, token: Optional[HTTPAuthorizationCredentials] = Depends(security)):
    global latest_value
    
    bpm = round(data.heartRate)
    score = heart_rate_to_stamina.get(bpm, 0)
    color = get_color(score)
    cst = pytz.timezone('America/Chicago')
    timestamp = datetime.now(cst).strftime("%I:%M:%S %p CST")
    
    result = {
        "heartRate": bpm,
        "staminaScore": score,
        "color": color,
        "timestamp": timestamp
    }
    
    # Handle multi-user mode (userID provided)
    if data.userID:
        print(f"DEBUG: Received userID: '{data.userID}'")
        print(f"DEBUG: UserID length: {len(data.userID)}")
        is_valid = validate_user_id(data.userID)
        print(f"DEBUG: UserID validation result: {is_valid}")
        
        if not is_valid:
            print(f"DEBUG: UserID validation failed for: {data.userID}")
            raise HTTPException(status_code=400, detail="Invalid userID format")
        
        user_data[data.userID] = result
        print(f"✅ Multi-user request - User: {data.userID[:8]}... Score: {score}% — Zone: {color}")
        return result
    
    # Handle single-user mode (bearer token required)
    if not token or token.credentials != SECRET_TOKEN:
        raise HTTPException(
            status_code=401,
            detail="Authentication required: provide valid bearer token or userID",
            headers={"WWW-Authenticate": "Bearer"}
        )
    
    latest_value = result
    print(f"✅ Single-user authenticated request - Score: {score}% — Zone: {color}")
    return result

@app.get("/latest")
def latest(user_id: Optional[str] = Query(None), token: Optional[HTTPAuthorizationCredentials] = Depends(security)):
    # Handle multi-user mode (userID provided)
    if user_id:
        if not validate_user_id(user_id):
            raise HTTPException(status_code=400, detail="Invalid userID format")
        
        if user_id in user_data:
            return user_data[user_id]
        else:
            return {"message": f"No data yet for user {user_id[:8]}..."}
    
    # Handle single-user mode (bearer token required)
    if not token or token.credentials != SECRET_TOKEN:
        raise HTTPException(
            status_code=401,
            detail="Authentication required: provide valid bearer token or userID parameter",
            headers={"WWW-Authenticate": "Bearer"}
        )
    
    if latest_value:
        return latest_value
    return {"message": "No data yet. Post to /stamina first."}
