"""
Zoom Integration MCP Server - Production Version
Real participant tracking and engagement analytics
"""

from mcp.server import FastMCP
import json
from datetime import datetime
from typing import List, Dict
import boto3
from botocore.exceptions import ClientError

# Create MCP server
mcp = FastMCP("Zoom Integration Server")

# Use DynamoDB for persistent storage in production
def get_dynamodb_table():
    """Get DynamoDB table for storing engagement data"""
    try:
        dynamodb = boto3.resource('dynamodb')
        table_name = 'workshop-sidekick-engagement'
        
        # Try to get existing table
        table = dynamodb.Table(table_name)
        table.load()
        return table
    except ClientError:
        # Table doesn't exist, create it
        dynamodb = boto3.client('dynamodb')
        try:
            table = dynamodb.create_table(
                TableName=table_name,
                KeySchema=[
                    {'AttributeName': 'session_id', 'KeyType': 'HASH'},
                    {'AttributeName': 'timestamp', 'KeyType': 'RANGE'}
                ],
                AttributeDefinitions=[
                    {'AttributeName': 'session_id', 'AttributeType': 'S'},
                    {'AttributeName': 'timestamp', 'AttributeType': 'S'}
                ],
                BillingMode='PAY_PER_REQUEST'
            )
            return boto3.resource('dynamodb').Table(table_name)
        except ClientError:
            # Fallback to in-memory storage
            return None

@mcp.tool(description="Track participant engagement activity")
def track_participant_activity(participant_name: str, activity_type: str, details: str = "", session_id: str = "default") -> str:
    """Track and log participant engagement to DynamoDB"""
    
    activity = {
        "timestamp": datetime.now().isoformat(),
        "participant": participant_name,
        "activity": activity_type,
        "details": details,
        "session_id": session_id
    }
    
    try:
        table = get_dynamodb_table()
        if table:
            # Store in DynamoDB
            table.put_item(Item=activity)
            storage_type = "DynamoDB"
        else:
            # Fallback to CloudWatch Logs
            logs_client = boto3.client('logs')
            log_group = '/aws/workshop-sidekick/engagement'
            
            try:
                logs_client.create_log_group(logGroupName=log_group)
            except ClientError:
                pass  # Log group already exists
            
            try:
                logs_client.create_log_stream(
                    logGroupName=log_group,
                    logStreamName=session_id
                )
            except ClientError:
                pass  # Log stream already exists
            
            logs_client.put_log_events(
                logGroupName=log_group,
                logStreamName=session_id,
                logEvents=[{
                    'timestamp': int(datetime.now().timestamp() * 1000),
                    'message': json.dumps(activity)
                }]
            )
            storage_type = "CloudWatch Logs"
        
        return json.dumps({
            "tracked": True,
            "participant": participant_name,
            "activity": activity_type,
            "storage": storage_type,
            "session_id": session_id
        })
        
    except Exception as e:
        return json.dumps({
            "tracked": False,
            "error": f"Failed to track activity: {str(e)}",
            "participant": participant_name,
            "activity": activity_type
        })

@mcp.tool(description="Get current workshop participants from session data")
def get_participants(session_id: str = "default") -> str:
    """Get list of current workshop participants from stored data"""
    
    try:
        table = get_dynamodb_table()
        participants = {}
        
        if table:
            # Query DynamoDB
            response = table.query(
                KeyConditionExpression=boto3.dynamodb.conditions.Key('session_id').eq(session_id)
            )
            
            for item in response['Items']:
                participant = item['participant']
                if participant not in participants:
                    participants[participant] = {
                        "name": participant,
                        "status": "active",
                        "join_time": item['timestamp'],
                        "activity_count": 1,
                        "last_activity": item['timestamp']
                    }
                else:
                    participants[participant]["activity_count"] += 1
                    participants[participant]["last_activity"] = item['timestamp']
        
        else:
            # Fallback to CloudWatch Logs
            logs_client = boto3.client('logs')
            log_group = '/aws/workshop-sidekick/engagement'
            
            try:
                response = logs_client.get_log_events(
                    logGroupName=log_group,
                    logStreamName=session_id
                )
                
                for event in response['events']:
                    try:
                        activity = json.loads(event['message'])
                        participant = activity['participant']
                        
                        if participant not in participants:
                            participants[participant] = {
                                "name": participant,
                                "status": "active",
                                "join_time": activity['timestamp'],
                                "activity_count": 1,
                                "last_activity": activity['timestamp']
                            }
                        else:
                            participants[participant]["activity_count"] += 1
                            participants[participant]["last_activity"] = activity['timestamp']
                            
                    except json.JSONDecodeError:
                        continue
                        
            except ClientError:
                # No data available, return empty
                pass
        
        participant_list = list(participants.values())
        active_count = len([p for p in participant_list if p["status"] == "active"])
        
        return json.dumps({
            "total_participants": len(participant_list),
            "participants": participant_list,
            "active_count": active_count,
            "timestamp": datetime.now().isoformat(),
            "session_id": session_id
        })
        
    except Exception as e:
        return json.dumps({
            "total_participants": 0,
            "participants": [],
            "active_count": 0,
            "error": f"Failed to get participants: {str(e)}",
            "timestamp": datetime.now().isoformat()
        })

@mcp.tool(description="Get comprehensive engagement analytics from stored data")
def get_engagement_analytics(session_id: str = "default") -> str:
    """Get detailed engagement analytics for the workshop"""
    
    try:
        table = get_dynamodb_table()
        activities = []
        
        if table:
            # Query DynamoDB
            response = table.query(
                KeyConditionExpression=boto3.dynamodb.conditions.Key('session_id').eq(session_id)
            )
            activities = response['Items']
            
        else:
            # Fallback to CloudWatch Logs
            logs_client = boto3.client('logs')
            log_group = '/aws/workshop-sidekick/engagement'
            
            try:
                response = logs_client.get_log_events(
                    logGroupName=log_group,
                    logStreamName=session_id
                )
                
                for event in response['events']:
                    try:
                        activity = json.loads(event['message'])
                        activities.append(activity)
                    except json.JSONDecodeError:
                        continue
                        
            except ClientError:
                activities = []
        
        # Calculate analytics
        activity_types = {}
        participant_activity = {}
        
        for activity in activities:
            # Count activity types
            activity_type = activity.get("activity", "unknown")
            activity_types[activity_type] = activity_types.get(activity_type, 0) + 1
            
            # Count per participant
            participant = activity.get("participant", "unknown")
            participant_activity[participant] = participant_activity.get(participant, 0) + 1
        
        # Find most active participants
        top_participants = sorted(participant_activity.items(), key=lambda x: x[1], reverse=True)[:5]
        
        # Calculate engagement score
        total_activities = len(activities)
        unique_participants = len(participant_activity)
        engagement_score = min(100, (total_activities * 2) + (unique_participants * 10))
        
        # Generate recommendations
        recommendations = []
        question_count = activity_types.get("question", 0)
        chat_count = activity_types.get("chat_message", 0)
        
        if engagement_score > 70:
            recommendations.append("High engagement detected - workshop is going well")
        elif engagement_score < 30:
            recommendations.append("Low engagement - consider encouraging more participation")
        
        if question_count > 5:
            recommendations.append("Many questions being asked - consider extending Q&A time")
        elif question_count < 2:
            recommendations.append("Few questions - consider prompting for questions")
        
        if chat_count > 10:
            recommendations.append("Good chat interaction")
        else:
            recommendations.append("Encourage more chat participation")
        
        return json.dumps({
            "total_activities": total_activities,
            "unique_participants": unique_participants,
            "engagement_score": engagement_score,
            "activity_breakdown": activity_types,
            "top_participants": dict(top_participants),
            "recommendations": recommendations,
            "session_id": session_id,
            "timestamp": datetime.now().isoformat()
        })
        
    except Exception as e:
        return json.dumps({
            "total_activities": 0,
            "unique_participants": 0,
            "engagement_score": 0,
            "error": f"Analytics generation failed: {str(e)}",
            "timestamp": datetime.now().isoformat()
        })

@mcp.tool(description="Send message to workshop participants via SNS")
def send_workshop_message(message: str, participant_emails: List[str] = None, topic_arn: str = None) -> str:
    """Send message to workshop participants via SNS"""
    
    try:
        sns = boto3.client('sns')
        
        if topic_arn:
            # Send to SNS topic
            response = sns.publish(
                TopicArn=topic_arn,
                Message=message,
                Subject="Workshop Sidekick Notification"
            )
            
            return json.dumps({
                "status": "sent",
                "method": "SNS Topic",
                "message_id": response['MessageId'],
                "timestamp": datetime.now().isoformat()
            })
            
        elif participant_emails:
            # Send individual messages
            message_ids = []
            
            for email in participant_emails:
                try:
                    response = sns.publish(
                        PhoneNumber=email,  # Can be email if configured
                        Message=message
                    )
                    message_ids.append(response['MessageId'])
                except ClientError:
                    continue
            
            return json.dumps({
                "status": "sent",
                "method": "Individual SNS",
                "message_ids": message_ids,
                "recipients": len(message_ids),
                "timestamp": datetime.now().isoformat()
            })
        
        else:
            return json.dumps({
                "status": "error",
                "error": "No recipients specified (topic_arn or participant_emails required)",
                "timestamp": datetime.now().isoformat()
            })
            
    except Exception as e:
        return json.dumps({
            "status": "error",
            "error": f"Failed to send message: {str(e)}",
            "timestamp": datetime.now().isoformat()
        })

@mcp.tool(description="Get real-time workshop statistics")
def get_workshop_stats(session_id: str = "default") -> str:
    """Get comprehensive real-time workshop statistics"""
    
    try:
        # Get participant data
        participants_data = json.loads(get_participants(session_id))
        
        # Get engagement data
        analytics_data = json.loads(get_engagement_analytics(session_id))
        
        # Calculate session duration (approximate)
        if participants_data["participants"]:
            earliest_join = min(p["join_time"] for p in participants_data["participants"])
            start_time = datetime.fromisoformat(earliest_join.replace('Z', '+00:00'))
            duration_minutes = int((datetime.now() - start_time.replace(tzinfo=None)).total_seconds() / 60)
        else:
            duration_minutes = 0
        
        stats = {
            "session_info": {
                "session_id": session_id,
                "start_time": earliest_join if participants_data["participants"] else datetime.now().isoformat(),
                "current_time": datetime.now().isoformat(),
                "duration_minutes": duration_minutes,
                "status": "active"
            },
            "participation": {
                "currently_joined": participants_data["active_count"],
                "total_participants": participants_data["total_participants"],
                "peak_attendance": participants_data["total_participants"]  # Simplified
            },
            "engagement": {
                "total_activities": analytics_data["total_activities"],
                "questions_asked": analytics_data["activity_breakdown"].get("question", 0),
                "chat_messages": analytics_data["activity_breakdown"].get("chat_message", 0),
                "engagement_score": analytics_data["engagement_score"]
            },
            "technical_health": {
                "storage_status": "DynamoDB" if get_dynamodb_table() else "CloudWatch Logs",
                "data_collection": "active",
                "last_update": datetime.now().isoformat()
            }
        }
        
        return json.dumps(stats)
        
    except Exception as e:
        return json.dumps({
            "session_id": session_id,
            "error": f"Failed to get workshop stats: {str(e)}",
            "timestamp": datetime.now().isoformat()
        })

if __name__ == "__main__":
    mcp.run(transport="stdio")