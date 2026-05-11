# CE308 Cloud Computing - Semester Project
# Lambda Function 2: View Workout Progress
# Triggered by: GET /view-progress via API Gateway

import json
import boto3
from boto3.dynamodb.conditions import Key
from datetime import datetime, timezone, timedelta


# ─── Lambda Handler ──────────────────────────────────────────────────────────────
def lambda_handler(event, context):
    """
    Main entry point for API Gateway GET /view-progress

    Expected Query String Parameters:
        user_id  (str):  The Cognito user ID (sub)
        days     (int):  Optional. Number of past days to fetch (default: 30)

    Example request:
        GET /view-progress?user_id=cognito-uuid&days=7
    """

    # ── 1. Extract query parameters ───────────────────────────────────────────
    params  = event.get("queryStringParameters") or {}
    user_id = params.get("user_id")
    days    = int(params.get("days", 30))

    if not user_id:
        return {
            "statusCode": 400,
            "headers": cors_headers(),
            "body": json.dumps({"error": "Missing required query parameter: 'user_id'"})
        }

    # ── 2. Calculate the start timestamp (ISO 8601 format) ────────────────────
    since_dt  = datetime.now(timezone.utc) - timedelta(days=days)
    since_str = since_dt.isoformat()

    # ── 3. Query DynamoDB for all workouts in the time range ──────────────────
    try:
        dynamodb = boto3.resource("dynamodb", region_name="us-east-1")
        table    = dynamodb.Table("WorkoutLogs")

        response = table.query(
            KeyConditionExpression=(
                Key("UserID").eq(user_id) &
                Key("Timestamp").gte(since_str)
            ),
            ScanIndexForward=False  # Most recent first
        )
        items = response.get("Items", [])

    except Exception as e:
        return {
            "statusCode": 500,
            "headers": cors_headers(),
            "body": json.dumps({"error": f"Database query failed: {str(e)}"})
        }

    # ── 4. Aggregate summary statistics ───────────────────────────────────────
    total_workouts      = len(items)
    total_calories      = sum(float(item.get("CaloriesBurned", 0)) for item in items)
    exercise_breakdown  = {}

    for item in items:
        ex = item.get("Exercise", "unknown")
        if ex not in exercise_breakdown:
            exercise_breakdown[ex] = {"count": 0, "total_calories": 0.0}
        exercise_breakdown[ex]["count"]          += 1
        exercise_breakdown[ex]["total_calories"] += float(item.get("CaloriesBurned", 0))

    # Round totals for cleaner output
    for ex in exercise_breakdown:
        exercise_breakdown[ex]["total_calories"] = round(
            exercise_breakdown[ex]["total_calories"], 2
        )

    # ── 5. Format individual log entries for the frontend ─────────────────────
    logs = []
    for item in items:
        logs.append({
            "workout_id":     item.get("WorkoutID"),
            "exercise":       item.get("Exercise"),
            "sets":           item.get("Sets"),
            "reps":           item.get("Reps"),
            "body_weight_kg": float(item.get("BodyWeightKg", 0)),
            "calories_burned": float(item.get("CaloriesBurned", 0)),
            "timestamp":      item.get("Timestamp"),
        })

    # ── 6. Return the response ────────────────────────────────────────────────
    return {
        "statusCode": 200,
        "headers": cors_headers(),
        "body": json.dumps({
            "user_id":           user_id,
            "period_days":       days,
            "total_workouts":    total_workouts,
            "total_calories":    round(total_calories, 2),
            "exercise_breakdown": exercise_breakdown,
            "logs":              logs,
        })
    }


def cors_headers():
    """Returns CORS headers so the S3-hosted frontend can call this API."""
    return {
        "Content-Type":                "application/json",
        "Access-Control-Allow-Origin": "*",
        "Access-Control-Allow-Methods": "GET, OPTIONS",
        "Access-Control-Allow-Headers": "Content-Type, Authorization",
    }
