"""
Working Zoom Call Agent - starts MCP servers automatically
"""

from strands import Agent
from strands.tools.mcp import MCPClient
from mcp import stdio_client, StdioServerParameters
from bedrock_agentcore.runtime import BedrockAgentCoreApp
from workshop_content_loader import workshop_loader
import json
from datetime import datetime
import subprocess
import time
import threading
import os
import sys

class WorkingZoomAgent:
    def __init__(self):
        self.workshop_context = ""
        self.chat_history = []
        self.mcp_processes = []
        
    def start_mcp_servers(self):
        """Start MCP servers as separate processes"""
        
        # Start Workshop Studio MCP server
        workshop_cmd = [sys.executable, "workshop_mcp_server.py"]
        workshop_proc = subprocess.Popen(
            workshop_cmd,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            cwd=os.getcwd()
        )
        self.mcp_processes.append(workshop_proc)
        
        # Start Zoom Integration MCP server  
        zoom_cmd = [sys.executable, "zoom_mcp_server.py"]
        zoom_proc = subprocess.Popen(
            zoom_cmd,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            cwd=os.getcwd()
        )
        self.mcp_processes.append(zoom_proc)
        
        # Give servers time to start
        time.sleep(3)
        
        return workshop_proc, zoom_proc
    
    def stop_mcp_servers(self):
        """Stop all MCP server processes"""
        for proc in self.mcp_processes:
            try:
                proc.terminate()
                proc.wait(timeout=5)
            except:
                proc.kill()
    
    def set_workshop_context(self, workshop_title: str = None, agenda: str = None):
        """Set the current workshop context"""
        if workshop_title is None:
            # Use loaded workshop content
            self.workshop_context = workshop_loader.get_workshop_context()
        else:
            self.workshop_context = f"Workshop: {workshop_title}\nAgenda: {agenda}"
    
    def process_chat_message(self, participant_name: str, message: str) -> str:
        """Process chat message using direct tool calls"""
        
        # Log the message
        self.chat_history.append({
            "timestamp": datetime.now().isoformat(),
            "participant": participant_name,
            "message": message,
            "type": "chat"
        })
        
        # Check if it's a question for the bot
        if any(trigger in message.lower() for trigger in ["@bot", "question:", "help", "stuck", "issue"]):
            # Determine if it's a technical issue
            if any(keyword in message.lower() for keyword in ["login", "access", "permission", "error", "stuck", "deploy"]):
                return self._handle_technical_issue(participant_name, message)
            else:
                return self._handle_general_question(participant_name, message)
        
        return None
    
    def _handle_technical_issue(self, participant_name: str, message: str) -> str:
        """Handle technical issues using Workshop Studio tools directly"""
        
        # Import and use tools directly
        from workshop_mcp_server import get_troubleshooting_steps
        
        # Determine issue type
        issue_type = "login" if "login" in message.lower() else \
                    "permission" if any(word in message.lower() for word in ["permission", "access", "iam", "role"]) else \
                    "security" if any(word in message.lower() for word in ["security", "encrypt", "https", "acl"]) else \
                    "setup" if any(word in message.lower() for word in ["setup", "prepare", "lab"]) else \
                    "deployment" if any(word in message.lower() for word in ["deploy", "error", "stuck"]) else \
                    "general"
        
        # Get troubleshooting steps
        result = get_troubleshooting_steps(issue_type, message)
        troubleshooting_data = json.loads(result)
        
        # Get relevant workshop content
        relevant_content = workshop_loader.get_troubleshooting_context(issue_type)
        
        response = f"Hi {participant_name}! I can help with that {issue_type} issue. Here are some steps to try:\n\n"
        for i, step in enumerate(troubleshooting_data['steps'], 1):
            response += f"{i}. {step}\n"
        
        if relevant_content:
            response += f"\nRelevant workshop materials:\n"
            for content in relevant_content:
                response += f"- {content}\n"
        
        # Log the escalation
        self.chat_history.append({
            "timestamp": datetime.now().isoformat(),
            "participant": participant_name,
            "issue": message,
            "response": response,
            "type": "technical_support",
            "priority": "high"
        })
        
        return response
    
    def _handle_general_question(self, participant_name: str, question: str) -> str:
        """Handle general workshop questions"""
        
        # Get relevant content from workshop materials
        relevant_content = workshop_loader.get_relevant_content(question)
        
        # Create a basic agent for general questions
        agent = Agent(model="us.anthropic.claude-3-5-sonnet-20241022-v2:0")
        
        # Create context-aware prompt with workshop content
        prompt = f"""
        Workshop Context: {self.workshop_context}
        
        Relevant Materials: {', '.join(relevant_content) if relevant_content else 'General workshop content'}
        
        Participant {participant_name} asked: {question}
        
        Provide a helpful, concise answer about the S3 security workshop content. Reference specific labs or topics when relevant. If you're not confident about the answer, suggest asking the facilitator.
        """
        
        response = agent(prompt)
        
        # Log the Q&A
        self.chat_history.append({
            "timestamp": datetime.now().isoformat(),
            "participant": participant_name,
            "question": question,
            "response": response.message,
            "type": "qa",
            "relevant_content": relevant_content
        })
        
        return response.message
    
    def generate_engagement_summary(self) -> str:
        """Generate engagement summary using Zoom tools directly"""
        
        from zoom_mcp_server import get_participants, get_engagement_analytics
        
        # Get current participants
        participants_result = get_participants()
        participants_data = json.loads(participants_result)
        
        # Get engagement analytics
        analytics_result = get_engagement_analytics()
        analytics_data = json.loads(analytics_result)
        
        # Calculate metrics from chat history
        total_interactions = len(self.chat_history)
        unique_participants = len(set(entry.get("participant", "") for entry in self.chat_history))
        questions_asked = len([entry for entry in self.chat_history if entry.get("type") == "qa"])
        technical_issues = len([entry for entry in self.chat_history if entry.get("type") == "technical_support"])
        
        engagement_score = min(100, (questions_asked * 10) + (unique_participants * 5) + (total_interactions * 2))
        
        summary = f"""
Workshop Engagement Summary
==============================

Active Participants: {participants_data['active_count']}
Total Interactions: {total_interactions}
Questions Answered: {questions_asked}
Technical Issues Resolved: {technical_issues}
Engagement Score: {engagement_score}/100

Current Participants:
"""
        
        for p in participants_data['participants'][:5]:  # Show first 5
            status = "ACTIVE" if p['status'] == 'active' else "AWAY"
            summary += f"- {p['name']} ({status}) - activities: {p.get('activity_count', 0)}\n"
        
        if technical_issues > 0:
            summary += f"\nCommon Issues:\n"
            issue_types = {}
            for entry in self.chat_history:
                if entry.get("type") == "technical_support":
                    issue = entry.get("issue", "").lower()
                    if "login" in issue:
                        issue_types["login"] = issue_types.get("login", 0) + 1
                    elif "permission" in issue:
                        issue_types["permission"] = issue_types.get("permission", 0) + 1
                    else:
                        issue_types["other"] = issue_types.get("other", 0) + 1
            
            for issue_type, count in issue_types.items():
                summary += f"- {issue_type.title()} issues: {count}\n"
        
        summary += f"\nRecommendations:\n"
        if technical_issues > 3:
            summary += "- Consider live demo of common troubleshooting steps\n"
        if questions_asked > 10:
            summary += "- High engagement - consider extending Q&A time\n"
        if technical_issues == 0 and questions_asked < 3:
            summary += "- Low interaction - encourage questions or add polls\n"
        if not summary.endswith("Recommendations:\n"):
            summary += "- Workshop running smoothly!\n"
        
        return summary.strip()

# AgentCore wrapper
app = BedrockAgentCoreApp()

@app.entrypoint
def invoke(payload):
    """AgentCore entrypoint"""
    
    # Initialize the agent
    zoom_agent = WorkingZoomAgent()
    
    # Extract input from payload
    input_data = payload.get("input", {})
    action = input_data.get("action", "chat")
    
    try:
        if action == "chat":
            participant_name = input_data.get("participant_name", "Anonymous")
            message = input_data.get("message", "")
            workshop_title = input_data.get("workshop_title", "AWS Workshop")
            agenda = input_data.get("agenda", "Workshop content")
            
            # Set context - use loaded workshop content if no title provided
            if workshop_title == "AWS Workshop":
                zoom_agent.set_workshop_context()  # Use loaded S3 security content
            else:
                zoom_agent.set_workshop_context(workshop_title, agenda)
            
            # Process the message
            response = zoom_agent.process_chat_message(participant_name, message)
            
            return {
                "output": {
                    "response": response,
                    "timestamp": datetime.now().isoformat(),
                    "agent": "zoom-call-agent"
                }
            }
        
        elif action == "summary":
            workshop_title = input_data.get("workshop_title", "AWS Workshop")
            agenda = input_data.get("agenda", "Workshop content")
            
            # Set context - use loaded workshop content if no title provided
            if workshop_title == "AWS Workshop":
                zoom_agent.set_workshop_context()  # Use loaded S3 security content
            else:
                zoom_agent.set_workshop_context(workshop_title, agenda)
            
            # Generate summary
            summary = zoom_agent.generate_engagement_summary()
            
            return {
                "output": {
                    "summary": summary,
                    "timestamp": datetime.now().isoformat(),
                    "agent": "zoom-call-agent"
                }
            }
        
        else:
            return {
                "output": {
                    "error": f"Unknown action: {action}",
                    "supported_actions": ["chat", "summary"]
                }
            }
    
    except Exception as e:
        return {
            "output": {
                "error": str(e),
                "timestamp": datetime.now().isoformat()
            }
        }

if __name__ == "__main__":
    app.run()