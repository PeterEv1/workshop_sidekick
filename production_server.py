#!/usr/bin/env python3
"""
Production Workshop Sidekick Server - Direct Bedrock Integration
"""

import os
import json
import logging
import boto3
from http.server import HTTPServer, BaseHTTPRequestHandler
from workshop_content_loader import WorkshopContentLoader

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

class WorkshopAgent:
    def __init__(self):
        self.bedrock = boto3.client('bedrock-runtime', region_name='us-east-1')
        self.content_loader = WorkshopContentLoader()
        self.model_id = "anthropic.claude-3-sonnet-20240229-v1:0"
    
    def process_message(self, message, session_id="default"):
        try:
            # Get relevant workshop content
            context = self.content_loader.get_relevant_content(message)
            
            # Create prompt with workshop context
            prompt = f"""You are a Workshop Sidekick AI assistant helping participants with an AWS S3 Security workshop.

Workshop Context:
{context}

User Question: {message}

Provide helpful, accurate answers about S3 security, the workshop labs, and AWS best practices. If the question is about technical issues, provide troubleshooting steps."""

            # Call Bedrock
            body = {
                "anthropic_version": "bedrock-2023-05-31",
                "max_tokens": 1000,
                "messages": [
                    {
                        "role": "user",
                        "content": prompt
                    }
                ]
            }
            
            response = self.bedrock.invoke_model(
                modelId=self.model_id,
                body=json.dumps(body)
            )
            
            response_body = json.loads(response['body'].read())
            return response_body['content'][0]['text']
            
        except Exception as e:
            logger.error(f"Error processing message: {e}")
            return f"I'm having trouble processing your request. Error: {str(e)}"

class WorkshopHandler(BaseHTTPRequestHandler):
    agent = None
    
    @classmethod
    def initialize(cls):
        if cls.agent is None:
            cls.agent = WorkshopAgent()
    
    def do_POST(self):
        if self.path == '/chat':
            try:
                content_length = int(self.headers['Content-Length'])
                post_data = self.rfile.read(content_length)
                data = json.loads(post_data.decode('utf-8'))
                
                message = data.get('message', '')
                session_id = data.get('session_id', 'default')
                
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
                logger.error(f"Error: {e}")
                self.send_error(500, str(e))
        else:
            self.send_error(404)
    
    def do_GET(self):
        if self.path == '/health':
            self.send_response(200)
            self.send_header('Content-type', 'application/json')
            self.end_headers()
            self.wfile.write(json.dumps({'status': 'healthy'}).encode())
        elif self.path == '/':
            self.send_response(200)
            self.send_header('Content-type', 'text/html')
            self.end_headers()
            html = """<!DOCTYPE html>
<html><head><title>Workshop Sidekick</title></head>
<body>
<h1>AWS S3 Security Workshop Sidekick</h1>
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
    WorkshopHandler.initialize()
    port = int(os.environ.get('PORT', 8000))
    server = HTTPServer(('0.0.0.0', port), WorkshopHandler)
    logger.info(f"Starting Workshop Sidekick server on port {port}")
    server.serve_forever()

if __name__ == "__main__":
    main()