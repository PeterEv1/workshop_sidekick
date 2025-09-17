#!/usr/bin/env python3
"""
App Runner Server for Workshop Sidekick
"""

import os
import json
import logging
from http.server import HTTPServer, BaseHTTPRequestHandler
from working_agent import WorkshopSidekickAgent
from workshop_content_loader import WorkshopContentLoader

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

class WorkshopHandler(BaseHTTPRequestHandler):
    agent = None
    content_loader = None
    
    @classmethod
    def initialize(cls):
        if cls.agent is None:
            cls.agent = WorkshopSidekickAgent()
            cls.content_loader = WorkshopContentLoader()
    
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
<h1>Workshop Sidekick</h1>
<div id="chat" style="height:400px;overflow-y:scroll;border:1px solid #ccc;padding:10px;margin:10px 0;"></div>
<input type="text" id="message" style="width:80%;" placeholder="Ask about the S3 security workshop...">
<button onclick="send()">Send</button>
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
        document.getElementById('chat').innerHTML += '<p><b>Agent:</b> ' + data.response + '</p>';
        document.getElementById('chat').scrollTop = document.getElementById('chat').scrollHeight;
    })
    .catch(e => console.error(e));
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
    logger.info(f"Starting server on port {port}")
    server.serve_forever()

if __name__ == "__main__":
    main()