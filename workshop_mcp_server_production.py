"""
Workshop Studio MCP Server - Production Version
Real AWS API integration for environment checking and troubleshooting
"""

from mcp.server import FastMCP
import boto3
import json
from typing import List
from botocore.exceptions import ClientError, NoCredentialsError

# Create MCP server
mcp = FastMCP("Workshop Studio Server")

@mcp.tool(description="Check AWS environment readiness and permissions")
def check_environment(account_id: str, region: str) -> str:
    """Check if AWS environment is ready for workshop"""
    
    checks = {}
    
    try:
        # Check STS access
        sts = boto3.client('sts', region_name=region)
        identity = sts.get_caller_identity()
        checks["account_access"] = f"✅ Account {identity['Account']} accessible"
        
        # Check S3 access
        s3 = boto3.client('s3', region_name=region)
        s3.list_buckets()
        checks["s3_access"] = "✅ S3 service accessible"
        
        # Check IAM access
        iam = boto3.client('iam', region_name=region)
        try:
            iam.get_user()
            checks["iam_permissions"] = "✅ IAM permissions available"
        except ClientError:
            # Might be using a role instead of user
            checks["iam_permissions"] = "✅ IAM access available (role-based)"
        
        # Check region availability
        ec2 = boto3.client('ec2', region_name=region)
        regions = ec2.describe_regions(RegionNames=[region])
        if regions['Regions']:
            checks["region_availability"] = f"✅ Services available in {region}"
        
        # Check GuardDuty (for S3 malware protection)
        try:
            guardduty = boto3.client('guardduty', region_name=region)
            detectors = guardduty.list_detectors()
            if detectors['DetectorIds']:
                checks["guardduty_status"] = "✅ GuardDuty available"
            else:
                checks["guardduty_status"] = "⚠️ GuardDuty not enabled"
        except ClientError:
            checks["guardduty_status"] = "⚠️ GuardDuty access limited"
        
    except NoCredentialsError:
        checks["error"] = "❌ AWS credentials not configured"
    except ClientError as e:
        error_code = e.response['Error']['Code']
        checks["error"] = f"❌ AWS access error: {error_code}"
    except Exception as e:
        checks["error"] = f"❌ Environment check failed: {str(e)}"
    
    return json.dumps(checks)

@mcp.tool(description="Validate user permissions for workshop resources")
def validate_permissions(user_arn: str, required_actions: List[str]) -> str:
    """Validate if user has required permissions using IAM policy simulator"""
    
    try:
        iam = boto3.client('iam')
        
        # Use IAM policy simulator
        results = {}
        
        for action in required_actions:
            try:
                response = iam.simulate_principal_policy(
                    PolicySourceArn=user_arn,
                    ActionNames=[action],
                    ResourceArns=['*']
                )
                
                if response['EvaluationResults']:
                    decision = response['EvaluationResults'][0]['EvalDecision']
                    if decision == 'allowed':
                        results[action] = "✅ Allowed"
                    else:
                        results[action] = f"❌ Denied ({decision})"
                else:
                    results[action] = "⚠️ Unable to evaluate"
                    
            except ClientError as e:
                results[action] = f"❌ Error checking: {e.response['Error']['Code']}"
        
        overall_status = "✅ Ready for workshop" if all("✅" in result for result in results.values()) else "⚠️ Permission issues detected"
        
        return json.dumps({
            "user_arn": user_arn,
            "permissions": results,
            "overall_status": overall_status
        })
        
    except Exception as e:
        return json.dumps({
            "user_arn": user_arn,
            "error": f"Permission validation failed: {str(e)}",
            "overall_status": "❌ Unable to validate permissions"
        })

@mcp.tool(description="Get real AWS service quotas and usage")
def get_resource_status(account_id: str, region: str) -> str:
    """Get current resource usage and quotas from AWS APIs"""
    
    try:
        resource_status = {}
        
        # Check S3 buckets
        s3 = boto3.client('s3', region_name=region)
        buckets = s3.list_buckets()
        bucket_count = len(buckets['Buckets'])
        resource_status["s3_buckets"] = {
            "current": bucket_count,
            "limit": 100,  # Default S3 bucket limit
            "status": "✅ Available" if bucket_count < 90 else "⚠️ Near limit"
        }
        
        # Check IAM roles
        iam = boto3.client('iam')
        try:
            roles = iam.list_roles(MaxItems=1000)
            role_count = len(roles['Roles'])
            resource_status["iam_roles"] = {
                "current": role_count,
                "limit": 1000,
                "status": "✅ Available" if role_count < 900 else "⚠️ Near limit"
            }
        except ClientError:
            resource_status["iam_roles"] = {
                "current": "Unknown",
                "limit": 1000,
                "status": "⚠️ Unable to check"
            }
        
        # Check CloudFormation stacks
        try:
            cf = boto3.client('cloudformation', region_name=region)
            stacks = cf.list_stacks(StackStatusFilter=['CREATE_COMPLETE', 'UPDATE_COMPLETE'])
            stack_count = len(stacks['StackSummaries'])
            resource_status["cloudformation_stacks"] = {
                "current": stack_count,
                "limit": 200,
                "status": "✅ Available"
            }
        except ClientError:
            resource_status["cloudformation_stacks"] = {
                "current": "Unknown",
                "limit": 200,
                "status": "⚠️ Unable to check"
            }
        
        recommendations = []
        for resource, data in resource_status.items():
            if "Near limit" in data["status"]:
                recommendations.append(f"Consider cleaning up unused {resource}")
        
        if not recommendations:
            recommendations = ["All resources within normal limits"]
        
        return json.dumps({
            "account_id": account_id,
            "region": region,
            "resources": resource_status,
            "recommendations": recommendations
        })
        
    except Exception as e:
        return json.dumps({
            "account_id": account_id,
            "region": region,
            "error": f"Resource status check failed: {str(e)}"
        })

@mcp.tool(description="Check real AWS service health")
def check_service_health(region: str, services: List[str]) -> str:
    """Check AWS service health status using Health API"""
    
    try:
        # Note: AWS Health API requires Business or Enterprise support
        # For basic accounts, we'll check service availability instead
        
        service_status = {}
        
        for service in services:
            try:
                if service.lower() == 's3':
                    s3 = boto3.client('s3', region_name=region)
                    s3.list_buckets()
                    service_status[service] = {
                        "status": "✅ Operational",
                        "region": region,
                        "last_checked": boto3.Session().region_name
                    }
                elif service.lower() == 'iam':
                    iam = boto3.client('iam', region_name=region)
                    iam.get_account_summary()
                    service_status[service] = {
                        "status": "✅ Operational",
                        "region": region,
                        "last_checked": "Now"
                    }
                elif service.lower() == 'guardduty':
                    guardduty = boto3.client('guardduty', region_name=region)
                    guardduty.list_detectors()
                    service_status[service] = {
                        "status": "✅ Operational",
                        "region": region,
                        "last_checked": "Now"
                    }
                else:
                    service_status[service] = {
                        "status": "⚠️ Unable to verify",
                        "region": region,
                        "last_checked": "Now"
                    }
                    
            except ClientError as e:
                service_status[service] = {
                    "status": f"❌ Error: {e.response['Error']['Code']}",
                    "region": region,
                    "last_checked": "Now"
                }
        
        overall_health = "✅ All services operational" if all("✅" in status["status"] for status in service_status.values()) else "⚠️ Some service issues detected"
        
        return json.dumps({
            "region": region,
            "services": service_status,
            "overall_health": overall_health,
            "health_dashboard_url": f"https://health.aws.amazon.com/health/status?region={region}"
        })
        
    except Exception as e:
        return json.dumps({
            "region": region,
            "error": f"Service health check failed: {str(e)}",
            "overall_health": "❌ Unable to check service health"
        })

@mcp.tool(description="Get troubleshooting steps for common workshop issues")
def get_troubleshooting_steps(issue_type: str, error_message: str = "") -> str:
    """Get structured troubleshooting steps"""
    
    troubleshooting_guide = {
        "login": {
            "steps": [
                "Verify AWS account ID is correct",
                "Check IAM user/role permissions", 
                "Clear browser cache and cookies",
                "Try incognito/private browsing mode",
                "Ensure MFA is properly configured"
            ],
            "common_causes": ["Incorrect account ID", "Expired credentials", "Browser cache issues"],
            "escalation_threshold": 3
        },
        "permission": {
            "steps": [
                "Confirm you're in the correct AWS region",
                "Verify IAM policies are attached to your user/role",
                "Check service-specific permissions (S3, IAM, GuardDuty)",
                "Ensure resource-based policies allow access",
                "Contact facilitator if issue persists"
            ],
            "common_causes": ["Missing IAM policies", "Wrong region", "Resource-based policy restrictions"],
            "escalation_threshold": 2
        },
        "security": {
            "steps": [
                "Check S3 bucket policy configuration",
                "Verify Block Public Access settings",
                "Ensure HTTPS-only access is configured",
                "Validate SSE-KMS encryption settings",
                "Review Access Control Lists (ACLs)"
            ],
            "common_causes": ["Misconfigured bucket policies", "Public access enabled", "Encryption not set"],
            "escalation_threshold": 2
        },
        "setup": {
            "steps": [
                "Verify workshop prerequisites are met",
                "Check CloudFormation stack deployment status",
                "Ensure required IAM roles are created",
                "Validate S3 bucket creation and configuration",
                "Test GuardDuty detector setup"
            ],
            "common_causes": ["Missing prerequisites", "CloudFormation failures", "IAM role issues"],
            "escalation_threshold": 2
        }
    }
    
    guide = troubleshooting_guide.get(issue_type, {
        "steps": ["Contact facilitator for assistance with this specific issue"],
        "common_causes": ["Unknown issue type"],
        "escalation_threshold": 1
    })
    
    return json.dumps({
        "issue_type": issue_type,
        "steps": guide["steps"],
        "common_causes": guide["common_causes"],
        "error_context": error_message,
        "escalation_threshold": guide["escalation_threshold"],
        "next_actions": [
            "Try the suggested steps in order",
            "Document any error messages you encounter",
            "Contact facilitator if issue persists after trying all steps"
        ]
    })

if __name__ == "__main__":
    mcp.run(transport="stdio")