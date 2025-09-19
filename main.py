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
import string
import secrets

app = FastAPI()

share_codes = {}  # Maps share_code -> user_id
professional_accounts = {}  # Maps professional_id -> client list

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
    
def generate_share_code():
    """Generate a 6-character share code like XK7M2P"""
    return ''.join(secrets.choice(string.ascii_uppercase + string.digits) for _ in range(6))

class ShareCodeRequest(BaseModel):
    userID: str

class RedeemCodeRequest(BaseModel):
    shareCode: str
    professionalID: str

@app.post("/generate-share-code")
def generate_user_share_code(request: ShareCodeRequest):
    """Free users generate codes to share with professionals"""
    
    # Validate user exists and has data
    if request.userID not in user_data:
        raise HTTPException(404, "User not found. Please use the app first to generate stamina data.")
    
    # Check if user already has a code
    existing_code = None
    for code, uid in share_codes.items():
        if uid == request.userID:
            existing_code = code
            break
    
    if existing_code:
        return {
            "share_code": existing_code,
            "message": "Using existing share code",
            "instructions": "Give this code to your trainer or healthcare provider"
        }
    
    # Generate new code
    code = generate_share_code()
    while code in share_codes:  # Ensure uniqueness
        code = generate_share_code()
    
    share_codes[code] = request.userID
    
    return {
        "share_code": code,
        "message": "Share code generated successfully",
        "instructions": "Give this code to your trainer or healthcare provider"
    }

@app.post("/redeem-share-code")
def redeem_share_code(request: RedeemCodeRequest):
    """Professionals redeem client codes to monitor them"""
    
    # Validate share code exists
    if request.shareCode not in share_codes:
        raise HTTPException(404, "Invalid share code. Please check the code and try again.")
    
    client_user_id = share_codes[request.shareCode]
    
    # Initialize professional account if new
    if request.professionalID not in professional_accounts:
        professional_accounts[request.professionalID] = {
            "clients": [],
            "subscription_tier": "starter",  # Default tier
            "max_clients": 10
        }
    
    professional = professional_accounts[request.professionalID]
    
    # Check if client already added
    if client_user_id in professional["clients"]:
        return {
            "status": "already_added",
            "message": "Client already in your monitoring list",
            "client_count": len(professional["clients"])
        }
    
    # Check subscription limits
    if len(professional["clients"]) >= professional["max_clients"]:
        raise HTTPException(403, f"Client limit reached ({professional['max_clients']}). Please upgrade your subscription.")
    
    # Add client to professional's list
    professional["clients"].append(client_user_id)
    
    return {
        "status": "success",
        "message": "Client added successfully",
        "client_count": len(professional["clients"]),
        "max_clients": professional["max_clients"]
    }

@app.get("/professional/dashboard/{professional_id}")
def get_professional_dashboard(professional_id: str):
    """Get all clients for a professional"""
    
    if professional_id not in professional_accounts:
        return {
            "clients": [],
            "subscription_tier": "none",
            "client_count": 0
        }
    
    professional = professional_accounts[professional_id]
    client_data = []
    
    for client_id in professional["clients"]:
        if client_id in user_data:
            data = user_data[client_id]
            client_data.append({
                "user_display": f"{client_id[:8]}..." if len(client_id) > 8 else client_id,
                "stamina_score": data["staminaScore"],
                "color": data["color"],
                "last_seen": data["timestamp"],
                "status": "connected" if not is_data_stale(data["timestamp"]) else "disconnected"
            })
    
    return {
        "clients": client_data,
        "subscription_tier": professional["subscription_tier"],
        "client_count": len(client_data),
        "max_clients": professional["max_clients"]
    }

def is_data_stale(timestamp_str):
    """Check if data is older than 5 minutes"""
    try:
        # This is a simplified stale check - you can improve this
        return False  # For now, assume all data is fresh
    except:
        return True

# Debug endpoint to see share codes
@app.get("/debug/share-codes")
def debug_share_codes():
    return {
        "total_codes": len(share_codes),
        "codes": [{"code": code, "user": f"{uid[:8]}..."} for code, uid in share_codes.items()],
        "professionals": len(professional_accounts)
    }
