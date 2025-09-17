"""
Workshop Content Loader - Loads PDF content for agent context
"""

import os
import json
from pathlib import Path

class WorkshopContentLoader:
    def __init__(self):
        self.content_dir = Path("C:/strands_agent_project/zoom_agent_resources/workshop_content/Configuring Amazon S3 security settings and access controls")
        self.workshop_content = self._load_workshop_structure()
    
    def _load_workshop_structure(self):
        """Load workshop structure from PDF filenames"""
        
        if not self.content_dir.exists():
            return {"error": "Workshop content directory not found"}
        
        pdf_files = list(self.content_dir.glob("*.pdf"))
        
        # Organize content by type
        content = {
            "workshop_title": "Configuring Amazon S3 Security Settings and Access Controls",
            "labs": [],
            "setup_guides": [],
            "security_topics": [],
            "tools_and_services": []
        }
        
        for pdf_file in pdf_files:
            filename = pdf_file.stem
            
            if filename.startswith("Lab "):
                content["labs"].append(filename)
            elif any(word in filename for word in ["Setup", "Prepare", "Initial"]):
                content["setup_guides"].append(filename)
            elif any(word in filename for word in ["Security", "Access", "Block", "Encrypt", "HTTPS"]):
                content["security_topics"].append(filename)
            elif any(word in filename for word in ["Athena", "CloudTrail", "GuardDuty", "Config"]):
                content["tools_and_services"].append(filename)
            else:
                content["security_topics"].append(filename)
        
        return content
    
    def get_workshop_context(self):
        """Get formatted workshop context for agent"""
        
        context = f"""
Workshop: {self.workshop_content['workshop_title']}

Available Labs:
{chr(10).join(f"- {lab}" for lab in self.workshop_content['labs'])}

Setup Guides:
{chr(10).join(f"- {guide}" for guide in self.workshop_content['setup_guides'])}

Security Topics Covered:
{chr(10).join(f"- {topic}" for topic in self.workshop_content['security_topics'])}

AWS Services & Tools:
{chr(10).join(f"- {tool}" for tool in self.workshop_content['tools_and_services'])}
        """
        
        return context.strip()
    
    def get_relevant_content(self, query):
        """Get relevant content based on query keywords"""
        
        query_lower = query.lower()
        relevant_content = []
        
        # Check labs
        for lab in self.workshop_content['labs']:
            if any(keyword in lab.lower() for keyword in query_lower.split()):
                relevant_content.append(f"Lab: {lab}")
        
        # Check security topics
        for topic in self.workshop_content['security_topics']:
            if any(keyword in topic.lower() for keyword in query_lower.split()):
                relevant_content.append(f"Topic: {topic}")
        
        # Check tools
        for tool in self.workshop_content['tools_and_services']:
            if any(keyword in tool.lower() for keyword in query_lower.split()):
                relevant_content.append(f"Tool: {tool}")
        
        return relevant_content
    
    def get_troubleshooting_context(self, issue_type):
        """Get troubleshooting context based on issue type"""
        
        context_map = {
            "permission": [
                "Configure S3 Access Grants for IAM user",
                "Attach IAM Role to EC2 Instance", 
                "Restrict Access to an S3 VPC Endpoint"
            ],
            "access": [
                "Configure S3 Block Public Access",
                "Block Public ACLs",
                "Disable S3 ACLs"
            ],
            "security": [
                "Require HTTPS",
                "Require SSE-KMS Encryption",
                "S3 Security Best Practices"
            ],
            "setup": [
                "Prepare Your Lab",
                "S3 Access Grants Lab - Initial Setup"
            ]
        }
        
        return context_map.get(issue_type, [])

# Global instance
workshop_loader = WorkshopContentLoader()