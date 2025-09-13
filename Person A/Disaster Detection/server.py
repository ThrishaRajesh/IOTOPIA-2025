from fastapi import FastAPI, File, UploadFile, Form
from fastapi.responses import JSONResponse
from fastapi.staticfiles import StaticFiles
from transformers import pipeline
from PIL import Image
import io
import json
from datetime import datetime
import os

app = FastAPI()

# Global variables for models
fire_model = None
disaster_model = None
general_model = None

# Storage for disaster reports (in production, use a proper database)
disaster_reports = []

def load_models():
    """Load all disaster detection models"""
    global fire_model, disaster_model, general_model
    
    print("Loading disaster detection models...")
    
    try:
        # Fire and smoke detection model
        print("Loading fire detection model...")
        fire_model = pipeline(
            model="prithivMLmods/Forest-Fire-Detection",
            task="image-classification"
        )
        print("✓ Fire detection model loaded")
    except Exception as e:
        print(f"Warning: Could not load fire model: {e}")
    
    try:
        # Use a more general vision model instead of LADI-v2 for better earthquake detection
        print("Loading general vision model for disaster detection...")
        disaster_model = pipeline(
            model="google/vit-base-patch16-224",
            task="image-classification"
        )
        print("✓ General vision model loaded")
    except Exception as e:
        print(f"Warning: Could not load disaster model: {e}")
    
    try:
        # Backup general classification model
        print("Loading ResNet model...")
        general_model = pipeline(
            model="microsoft/resnet-50",
            task="image-classification"
        )
        print("✓ ResNet model loaded")
    except Exception as e:
        print(f"Warning: Could not load general model: {e}")
    
    print("All models loaded successfully!")

# Load models on startup
load_models()

@app.post("/predict/")
async def predict(
    file: UploadFile = File(...), 
    latitude: float = Form(None), 
    longitude: float = Form(None),
    address: str = Form(None)
):
    try:
        # Read and process image
        img_bytes = await file.read()
        img = Image.open(io.BytesIO(img_bytes))
        
        print(f"Processing image - Mode: {img.mode}, Size: {img.size}")
        if latitude and longitude:
            print(f"Location: {latitude}, {longitude}")
            if address:
                print(f"Address: {address}")

        if img.mode != "RGB":
            img = img.convert("RGB")

        all_predictions = {}
        
        # Fire Detection
        if fire_model:
            try:
                fire_results = fire_model(img)
                fire_results = sorted(fire_results, key=lambda x: x['score'], reverse=True)
                all_predictions["fire_detection"] = [
                    {"label": r["label"], "score": float(r["score"])} 
                    for r in fire_results
                ]
                print("Fire detection completed")
            except Exception as e:
                print(f"Fire detection error: {e}")
                all_predictions["fire_detection"] = [{"error": str(e)}]
        
        # General Vision Model (better for ground-level disaster detection)
        if disaster_model:
            try:
                disaster_results = disaster_model(img, top_k=15)
                disaster_results = sorted(disaster_results, key=lambda x: x['score'], reverse=True)
                all_predictions["vision_detection"] = [
                    {"label": r["label"], "score": float(r["score"])} 
                    for r in disaster_results
                ]
                print("Vision-based disaster detection completed")
            except Exception as e:
                print(f"Vision detection error: {e}")
                all_predictions["vision_detection"] = [{"error": str(e)}]
        
        # General Classification (for other disaster types)
        if general_model:
            try:
                general_results = general_model(img, top_k=10)
                all_predictions["general_classification"] = [
                    {"label": r["label"], "score": float(r["score"])} 
                    for r in general_results
                ]
                print("General classification completed")
            except Exception as e:
                print(f"General classification error: {e}")
                all_predictions["general_classification"] = [{"error": str(e)}]
        
        # Analyze results and provide disaster summary
        disaster_summary = analyze_disaster_type(all_predictions)
        
        # Store disaster report with location
        disaster_report = {
            "timestamp": datetime.now().isoformat(),
            "disaster_type": disaster_summary["primary_disaster"],
            "confidence": disaster_summary["confidence"],
            "risk_level": disaster_summary["risk_level"],
            "detected_features": disaster_summary["detected_features"],
            "location": {
                "latitude": latitude,
                "longitude": longitude,
                "address": address
            },
            "filename": file.filename
        }
        
        # Save report (in production, save to database)
        disaster_reports.append(disaster_report)
        save_reports_to_file()
        
        return JSONResponse(content={
            "disaster_analysis": disaster_summary,
            "detailed_predictions": all_predictions,
            "location_data": {
                "latitude": latitude,
                "longitude": longitude,
                "address": address,
                "timestamp": disaster_report["timestamp"]
            }
        })

    except Exception as e:
        print(f"Error during prediction: {str(e)}")
        return JSONResponse(content={"error": str(e)})

def analyze_disaster_type(predictions):
    """Analyze all model predictions to determine disaster type"""
    disaster_summary = {
        "primary_disaster": "unknown",
        "confidence": 0.0,
        "detected_features": [],
        "risk_level": "low"
    }
    
    high_confidence_threshold = 0.6
    medium_confidence_threshold = 0.3
    
    # Check fire detection FIRST (highest priority)
    if "fire_detection" in predictions and not any("error" in p for p in predictions["fire_detection"]):
        for pred in predictions["fire_detection"]:
            if pred["score"] > high_confidence_threshold:
                if "fire" in pred["label"].lower():
                    disaster_summary["primary_disaster"] = "fire"
                    disaster_summary["confidence"] = pred["score"]
                    disaster_summary["detected_features"].append(f"Fire detected ({pred['score']:.1%})")
                    disaster_summary["risk_level"] = "high"
                    return disaster_summary  # Return immediately for fire
                elif "smoke" in pred["label"].lower():
                    disaster_summary["detected_features"].append(f"Smoke detected ({pred['score']:.1%})")
                    if disaster_summary["primary_disaster"] == "unknown":
                        disaster_summary["primary_disaster"] = "smoke/potential fire"
                        disaster_summary["confidence"] = pred["score"]
                        disaster_summary["risk_level"] = "medium"
    
    # Analyze vision model predictions for earthquake/collapse detection
    earthquake_indicators = ["rubble", "debris", "wreck", "destroyed", "collapsed", "ruin", "demolish", "damage", "broken", "shatter", "crash"]
    building_indicators = ["building", "house", "structure", "wall", "concrete", "brick", "construction"]
    water_indicators = ["water", "flood", "river", "lake", "ocean", "sea", "wet", "liquid"]
    
    earthquake_score = 0
    water_score = 0
    building_damage_detected = False
    
    if "vision_detection" in predictions and not any("error" in p for p in predictions["vision_detection"]):
        for pred in predictions["vision_detection"]:
            label_lower = pred["label"].lower()
            score = pred["score"]
            
            # Check for earthquake/collapse indicators
            if any(indicator in label_lower for indicator in earthquake_indicators):
                earthquake_score += score * 2  # Higher weight for earthquake indicators
                disaster_summary["detected_features"].append(f"Destruction detected: {pred['label']} ({score:.1%})")
                
            # Check for building-related terms
            if any(indicator in label_lower for indicator in building_indicators):
                building_damage_detected = True
                disaster_summary["detected_features"].append(f"Building-related: {pred['label']} ({score:.1%})")
                
            # Check for water indicators
            if any(indicator in label_lower for indicator in water_indicators):
                water_score += score
    
    # Also check general classification for more earthquake indicators
    if "general_classification" in predictions and not any("error" in p for p in predictions["general_classification"]):
        for pred in predictions["general_classification"]:
            label_lower = pred["label"].lower()
            score = pred["score"]
            
            if any(indicator in label_lower for indicator in earthquake_indicators):
                earthquake_score += score
                disaster_summary["detected_features"].append(f"Damage indicator: {pred['label']} ({score:.1%})")
    
    # Decision logic: Prefer earthquake over flood if we have strong earthquake indicators
    if earthquake_score > 0.4 or (earthquake_score > 0.2 and building_damage_detected):
        disaster_summary["primary_disaster"] = "earthquake/building collapse"
        disaster_summary["confidence"] = min(earthquake_score, 0.95)  # Cap confidence
        disaster_summary["risk_level"] = "high" if earthquake_score > 0.6 else "medium"
        
    elif water_score > 0.5 and earthquake_score < 0.3:
        disaster_summary["primary_disaster"] = "flood"
        disaster_summary["confidence"] = water_score
        disaster_summary["risk_level"] = "high" if water_score > 0.7 else "medium"
        disaster_summary["detected_features"].append(f"Water/flooding detected ({water_score:.1%})")
        
    elif building_damage_detected:
        disaster_summary["primary_disaster"] = "structural damage"
        disaster_summary["confidence"] = 0.6
        disaster_summary["risk_level"] = "medium"
    
    # Set default if nothing detected
    if disaster_summary["primary_disaster"] == "unknown":
        disaster_summary["primary_disaster"] = "no clear disaster detected"
        disaster_summary["risk_level"] = "low"
        disaster_summary["confidence"] = 0.1
    
    return disaster_summary

def save_reports_to_file():
    """Save disaster reports to JSON file"""
    try:
        with open("disaster_reports.json", "w") as f:
            json.dump(disaster_reports, f, indent=2)
        print(f"Saved {len(disaster_reports)} disaster reports")
    except Exception as e:
        print(f"Error saving reports: {e}")

@app.get("/reports/")
async def get_reports():
    """Get all disaster reports with locations"""
    return JSONResponse(content={"reports": disaster_reports})

@app.get("/health")
async def health_check():
    """Health check endpoint"""
    model_status = {
        "fire_model": fire_model is not None,
        "disaster_model": disaster_model is not None, 
        "general_model": general_model is not None
    }
    return {
        "status": "healthy", 
        "models_loaded": model_status,
        "total_reports": len(disaster_reports)
    }

# Load existing reports on startup
try:
    if os.path.exists("disaster_reports.json"):
        with open("disaster_reports.json", "r") as f:
            disaster_reports = json.load(f)
        print(f"Loaded {len(disaster_reports)} existing disaster reports")
except Exception as e:
    print(f"Could not load existing reports: {e}")

# Mount static files AFTER defining API routes
app.mount("/", StaticFiles(directory=".", html=True), name="static")