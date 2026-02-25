"""
team_tools.py - LangChain @tool wrappers for the team module.
"""

import json
import logging
import uuid

from langchain_core.tools import tool

from backend.app.team import get_bus, get_team

logger = logging.getLogger(__name__)


@tool
def spawn_teammate(name: str, role: str, prompt: str) -> str:
    """Spawn a persistent teammate agent in its own thread. The teammate can use tools and communicate via inboxes."""
    logger.info("spawn_teammate: name=%s role=%s", name, role)
    return get_team().spawn(name, role, prompt)


@tool
def list_teammates() -> str:
    """List all teammates with their name, role, and current status."""
    return get_team().list_all()


@tool
def send_message(to: str, content: str, msg_type: str = "message") -> str:
    """Send a message to a teammate's inbox. msg_type: message, broadcast, shutdown_request, shutdown_response, plan_approval_response."""
    logger.info("send_message: to=%s type=%s", to, msg_type)
    return get_bus().send("lead", to, content, msg_type)


@tool
def read_inbox() -> str:
    """Read and drain the lead's inbox. Returns all pending messages as JSON."""
    return json.dumps(get_bus().read_inbox("lead"), indent=2)


@tool
def broadcast(content: str) -> str:
    """Send a message to all teammates."""
    logger.info("broadcast: %s", content[:80])
    return get_bus().broadcast("lead", content, get_team().member_names())


@tool
def shutdown_request(teammate: str) -> str:
    """Request a teammate to shut down gracefully. Returns a request_id for tracking."""
    from backend.app.team.state import shutdown_requests, tracker_lock
    req_id = str(uuid.uuid4())[:8]
    with tracker_lock:
        shutdown_requests[req_id] = {"target": teammate, "status": "pending"}
    get_bus().send("lead", teammate, "Please shut down gracefully.",
                   "shutdown_request", {"request_id": req_id})
    return f"Shutdown request {req_id} sent to '{teammate}' (status: pending)"


@tool
def check_shutdown_status(request_id: str) -> str:
    """Check the status of a shutdown request by request_id."""
    from backend.app.team.state import shutdown_requests, tracker_lock
    with tracker_lock:
        return json.dumps(shutdown_requests.get(request_id, {"error": "not found"}))


@tool
def plan_approval(request_id: str, approve: bool, feedback: str = "") -> str:
    """Approve or reject a teammate's submitted plan. Provide request_id and approve=True/False."""
    from backend.app.team.state import plan_requests, tracker_lock
    with tracker_lock:
        req = plan_requests.get(request_id)
    if not req:
        return f"Error: Unknown plan request_id '{request_id}'"
    with tracker_lock:
        req["status"] = "approved" if approve else "rejected"
    get_bus().send("lead", req["from"], feedback, "plan_approval_response",
                   {"request_id": request_id, "approve": approve, "feedback": feedback})
    return f"Plan {req['status']} for '{req['from']}'"


@tool
def idle() -> str:
    """Enter idle state (for lead -- rarely used)."""
    return "Lead does not idle."


@tool
def claim_task(task_id: int) -> str:
    """Claim a task from the shared board by ID."""
    from backend.app.team.state import claim_task as _claim
    return _claim(task_id, "lead")


def drain_lead_inbox() -> list:
    """Return and clear all pending messages in the lead's inbox."""
    return get_bus().read_inbox("lead")
