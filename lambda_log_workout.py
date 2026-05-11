# CE308 Cloud Computing - Semester Project
# Lambda Function 1: Log Workout & Calculate Calories
# Triggered by: POST /log-workout via API Gateway

import json
import boto3
import uuid
from datetime import datetime, timezone

# ─── MET Values for Bodyweight Exercises ───────────────────────────────────────
# MET (Metabolic Equivalent of Task) values for common bodyweight exercises.
# Source: Compendium of Physical Activities
MET_VALUES = {
    "push_ups":    3.8,
    "pull_ups":    8.0,
    "squats":      5.0,
    "lunges":      4.0,
    "burpees":     8.0,
    "plank":       4.0,
    "sit_ups":     3.5,
    "mountain_climbers": 8.0,
    "jumping_jacks": 8.0,
    "dips":        3.8,
}

# ─── Caloric Calculation Engine ─────────────────────────────────────────────────
def calculate_calories(exercise_name, sets, reps, body_weight_kg):
    """
    Calculates estimated calories burned using the MET formula.

    Formula: Calories = MET × body_weight_kg × duration_hours
    Duration is estimated as: sets × reps × 3 seconds per rep
    
    Args:
        exercise_name   (str):   Normalized exercise name (e.g., "push_ups")
        sets            (int):   Number of sets performed
        reps            (int):   Repetitions per set
        body_weight_kg  (float): User's body weight in kilograms
    
    Returns:
        float: Estimated calories burned, rounded to 2 decimal places
    """
    # Default to a moderate MET value if exercise is not in our lookup table
    met = MET_VALUES.get(exercise_name.lower().replace(" ", "_"), 5.0)

    # Estimate duration: each rep takes ~3 seconds, convert to hours
    total_reps      = sets * reps
    duration_secs   = total_reps * 3
    duration_hours  = duration_secs / 3600.0

    calories = met * body_weight_kg * duration_hours
    return round(calories, 2)


# ─── Lambda Handler ──────────────────────────────────────────────────────────────
def lambda_handler(event, context):
    """
    Main entry point for API Gateway POST /log-workout

    Expected JSON body from the frontend:
    {
        "user_id":          "cognito-sub-uuid",
        "exercise":         "push_ups",
        "sets":             3,
        "reps":             15,
        "body_weight_kg":   75.0
    }
    """

    # ── 1. Parse the incoming HTTP body ──────────────────────────────────────
    try:
        body = json.loads(event.get("body", "{}"))
    except (json.JSONDecodeError, TypeError):
        return {
            "statusCode": 400,
            "headers": cors_headers(),
            "body": json.dumps({"error": "Invalid JSON in request body."})
        }

    # ── 2. Validate required fields ───────────────────────────────────────────
    required_fields = ["user_id", "exercise", "sets", "reps", "body_weight_kg"]
    for field in required_fields:
        if field not in body:
            return {
                "statusCode": 400,
                "headers": cors_headers(),
                "body": json.dumps({"error": f"Missing required field: '{field}'"})
            }

    user_id        = body["user_id"]
    exercise       = body["exercise"]
    sets           = int(body["sets"])
    reps           = int(body["reps"])
    body_weight_kg = float(body["body_weight_kg"])

    # ── 3. Caloric Calculation ────────────────────────────────────────────────
    calories_burned = calculate_calories(exercise, sets, reps, body_weight_kg)

    # ── 4. Build the DynamoDB item ────────────────────────────────────────────
    timestamp  = datetime.now(timezone.utc).isoformat()
    workout_id = str(uuid.uuid4())  # Unique ID for this log entry

    item = {
        "UserID":         user_id,           # Partition Key
        "Timestamp":      timestamp,          # Sort Key
        "WorkoutID":      workout_id,
        "Exercise":       exercise,
        "Sets":           sets,
        "Reps":           reps,
        "BodyWeightKg":   str(body_weight_kg),
        "CaloriesBurned": str(calories_burned),
    }

    # ── 5. Persist to DynamoDB ────────────────────────────────────────────────
    try:
        dynamodb = boto3.resource("dynamodb", region_name="us-east-1")
        table    = dynamodb.Table("WorkoutLogs")
        table.put_item(Item=item)
    except Exception as e:
        return {
            "statusCode": 500,
            "headers": cors_headers(),
            "body": json.dumps({"error": f"Database write failed: {str(e)}"})
        }

    # ── 6. Return success response ────────────────────────────────────────────
    return {
        "statusCode": 200,
        "headers": cors_headers(),
        "body": json.dumps({
            "message":        "Workout logged successfully!",
            "workout_id":     workout_id,
            "exercise":       exercise,
            "sets":           sets,
            "reps":           reps,
            "body_weight_kg": body_weight_kg,
            "calories_burned": calories_burned,
            "timestamp":      timestamp,
        })
    }


def cors_headers():
    """Returns CORS headers so the S3-hosted frontend can call this API."""
    return {
        "Content-Type":                "application/json",
        "Access-Control-Allow-Origin": "*",
        "Access-Control-Allow-Methods": "POST, OPTIONS",
        "Access-Control-Allow-Headers": "Content-Type, Authorization",
    }
