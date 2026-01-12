import json

def lambda_handler(event, context):
    print(f"DEBUG Event: {json.dumps(event)}")
    return {"isAuthorized": True}
