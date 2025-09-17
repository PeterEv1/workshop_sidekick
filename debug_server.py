#!/usr/bin/env python3
"""
Debug Workshop Sidekick Server - Better error handling and logging
"""

import os
import json
import logging
import boto3
import traceback
from http.server import HTTPServer, BaseHTTPRequestHandler

# Enhanced logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

class WorkshopAgent:
    def __init__(self):
        try:
            self.bedrock = boto3.client('bedrock-runtime', region_name='us-east-1')
            self.model_id = "anthropic.claude-3-sonnet-20240229-v1:0"
            logger.info("Bedrock client initialized successfully")
        except Exception as e:
            logger.error(f"Failed to initialize Bedrock client: {e}")
            self.bedrock = None
    
    def test_bedrock_connection(self):
        """Test if Bedrock is accessible"""
        try:
            if not self.bedrock:
                return False, "Bedrock client not initialized"
            
            # Simple test call
            body = {
                "anthropic_version": "bedrock-2023-05-31",
                "max_tokens": 10,
                "messages": [{"role": "user", "content": "Hello"}]
            }
            
            response = self.bedrock.invoke_model(
                modelId=self.model_id,
                body=json.dumps(body)
            )
            
            logger.info("Bedrock connection test successful")
            return True, "Connected"
            
        except Exception as e:
            logger.error(f"Bedrock connection test failed: {e}")
            return False, str(e)
    
    def process_message(self, message, session_id="default"):
        try:
            logger.info(f"Processing message: {message[:50]}...")
            
            # Test Bedrock first
            connected, error = self.test_bedrock_connection()
            if not connected:
                return f"Bedrock connection failed: {error}"
            
            # Simple workshop context (no file loading for now)
            context = """
AWS S3 Security Workshop - Available Labs:
1. Lab 1 - S3 Security Exercises
2. Lab 2 - S3 Access Grants  
3. Lab 3 - Enabling Malware Protection for S3 by using GuardDuty
4. Lab 4 - S3 Access Control Lists

Key Topics: S3 Block Public Access, Bucket Policies, Encryption, GuardDuty, ACLs
"""
            
            prompt = f"""You are a Workshop Sidekick AI assistant helping participants with an AWS S3 Security workshop.

{context}

User Question: {message}

Provide helpful, accurate answers about S3 security, the workshop labs, and AWS best practices."""

            # Call Bedrock
            body = {
                "anthropic_version": "bedrock-2023-05-31",
                "max_tokens": 1000,
                "messages": [{"role": "user", "content": prompt}]
            }
            
            logger.info("Calling Bedrock...")
            response = self.bedrock.invoke_model(
                modelId=self.model_id,
                body=json.dumps(body)
            )
            
            response_body = json.loads(response['body'].read())
            result = response_body['content'][0]['text']
            
            logger.info(f"Bedrock response received: {len(result)} characters")
            return result
            
        except Exception as e:
            logger.error(f"Error processing message: {e}")
            logger.error(f"Full traceback: {traceback.format_exc()}")
            return f"Error: {str(e)}"

class WorkshopHandler(BaseHTTPRequestHandler):
    agent = None
    
    @classmethod
    def initialize(cls):
        if cls.agent is None:
            logger.info("Initializing Workshop Agent...")
            cls.agent = WorkshopAgent()
    
    def do_POST(self):
        if self.path == '/chat':
            try:
                content_length = int(self.headers['Content-Length'])
                post_data = self.rfile.read(content_length)
                data = json.loads(post_data.decode('utf-8'))
                
                message = data.get('message', '')
                session_id = data.get('session_id', 'default')
                
                logger.info(f"Received chat request: {message}")
                response = self.agent.process_message(message, session_id)
                
                self.send_response(200)
                self.send_header('Content-type', 'application/json')
                self.send_header('Access-Control-Allow-Origin', '*')
                self.end_headers()
                
                self.wfile.write(json.dumps({
                    'response': response,
                    'session_id': session_id
                }).encode())
                
            except Exception as e:
                logger.error(f"Handler error: {e}")
                logger.error(f"Full traceback: {traceback.format_exc()}")
                self.send_error(500, str(e))
        else:
            self.send_error(404)
    
    def do_GET(self):
        if self.path == '/health':
            try:
                # Test Bedrock connection in health check
                connected, status = self.agent.test_bedrock_connection() if self.agent else (False, "Agent not initialized")
                
                self.send_response(200)
                self.send_header('Content-type', 'application/json')
                self.end_headers()
                self.wfile.write(json.dumps({
                    'status': 'healthy',
                    'bedrock_connected': connected,
                    'bedrock_status': status
                }).encode())
            except Exception as e:
                logger.error(f"Health check error: {e}")
                self.send_error(500, str(e))
                
        elif self.path == '/':
            self.send_response(200)
            self.send_header('Content-type', 'text/html')
            self.end_headers()
            html = """<!DOCTYPE html>
<html><head><title>Workshop Sidekick - Debug Mode</title></head>
<body>
<h1>AWS S3 Security Workshop Sidekick</h1>
<p><a href="/health">Check Health & Bedrock Status</a></p>
<div id="chat" style="height:400px;overflow-y:scroll;border:1px solid #ccc;padding:10px;margin:10px 0;background:#f9f9f9;"></div>
<input type="text" id="message" style="width:70%;padding:10px;" placeholder="Ask about S3 security, labs, or troubleshooting...">
<button onclick="send()" style="padding:10px 20px;">Send</button>
<script>
function send() {
    const msg = document.getElementById('message').value;
    if (!msg) return;
    
    document.getElementById('chat').innerHTML += '<p><b>You:</b> ' + msg + '</p>';
    document.getElementById('message').value = '';
    
    fetch('/chat', {
        method: 'POST',
        headers: {'Content-Type': 'application/json'},
        body: JSON.stringify({message: msg})
    })
    .then(r => r.json())
    .then(data => {
        document.getElementById('chat').innerHTML += '<p><b>Workshop Sidekick:</b> ' + data.response + '</p>';
        document.getElementById('chat').scrollTop = document.getElementById('chat').scrollHeight;
    })
    .catch(e => {
        document.getElementById('chat').innerHTML += '<p><b>Error:</b> ' + e + '</p>';
    });
}
document.getElementById('message').addEventListener('keypress', function(e) {
    if (e.key === 'Enter') send();
});
</script>
</body></html>"""
            self.wfile.write(html.encode())
        else:
            self.send_error(404)

def main():
    logger.info("Starting Workshop Sidekick Debug Server...")
    WorkshopHandler.initialize()
    port = int(os.environ.get('PORT', 8000))
    server = HTTPServer(('0.0.0.0', port), WorkshopHandler)
    logger.info(f"Server running on port {port}")
    server.serve_forever()

if __name__ == "__main__":
    main()