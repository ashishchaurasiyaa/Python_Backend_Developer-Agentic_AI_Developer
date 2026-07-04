"""Milestone 8 — FastMCP Slack notifier for CRITICAL security alerts."""
import os
import httpx
from fastmcp import FastMCP

mcp = FastMCP("slack-notifier")


@mcp.tool()
async def send_slack_alert(channel: str, pr_url: str, severity: str, description: str) -> dict:
    """
    Send a CRITICAL security alert to a Slack channel.

    Args:
        channel: Slack channel name or ID (e.g. '#security-alerts')
        pr_url: Full GitHub PR URL
        severity: Issue severity — should be CRITICAL for alerts
        description: One-line description of the issue
    """
    webhook_url = os.getenv("SLACK_WEBHOOK_URL")
    if not webhook_url:
        print(f"[slack] No SLACK_WEBHOOK_URL — would have sent: {description}")
        return {"status": "skipped", "reason": "no webhook url"}

    message = {
        "text": f":rotating_light: *{severity} Security Issue* — <{pr_url}|View PR>",
        "blocks": [
            {
                "type": "section",
                "text": {
                    "type": "mrkdwn",
                    "text": (
                        f":rotating_light: *{severity} Security Issue Found*\n"
                        f"*PR:* <{pr_url}|{pr_url}>\n"
                        f"*Issue:* {description}\n"
                        f"*Action required:* Human review needed before merge."
                    ),
                },
            },
            {"type": "divider"},
            {
                "type": "context",
                "elements": [{"type": "mrkdwn", "text": "Sent by Multi-Agent Code Review System"}],
            },
        ],
    }

    async with httpx.AsyncClient() as client:
        resp = await client.post(webhook_url, json=message)

    if resp.status_code == 200:
        return {"status": "sent", "channel": channel}
    else:
        return {"status": "failed", "code": resp.status_code, "body": resp.text}


@mcp.tool()
async def send_slack_message(channel: str, message: str) -> dict:
    """Send a plain text message to a Slack channel."""
    webhook_url = os.getenv("SLACK_WEBHOOK_URL")
    if not webhook_url:
        return {"status": "skipped", "reason": "no webhook url"}

    async with httpx.AsyncClient() as client:
        resp = await client.post(webhook_url, json={"text": message, "channel": channel})

    return {"status": "sent" if resp.status_code == 200 else "failed"}


if __name__ == "__main__":
    mcp.run()
