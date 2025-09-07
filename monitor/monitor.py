import os
import json
from datetime import datetime, timedelta, timezone
from dateutil import parser
import requests

GITHUB_OWNER = os.getenv("GITHUB_OWNER")
GITHUB_REPO = os.getenv("GITHUB_REPO")
GITHUB_TOKEN = os.getenv("GITHUB_TOKEN")
SLACK_WEBHOOK_URL = os.getenv("SLACK_WEBHOOK_URL")
LOOKBACK_MINUTES = int(os.getenv("LOOKBACK_MINUTES", "10"))
SEND_ANALYTICS = os.getenv("SEND_ANALYTICS", "true").lower() == "true"

HEADERS = {
    "Authorization": f"Bearer {GITHUB_TOKEN}",
    "Accept": "application/vnd.github+json",
}

API_BASE = f"https://api.github.com/repos/{GITHUB_OWNER}/{GITHUB_REPO}"


def _gh(url: str):
    r = requests.get(url, headers=HEADERS, timeout=30)
    r.raise_for_status()
    return r.json()


def fetch_runs(per_page: int = 50):
    url = f"{API_BASE}/actions/runs?per_page={per_page}"
    data = _gh(url)
    return data.get("workflow_runs", [])


def within_lookback(iso_ts: str, minutes: int) -> bool:
    t = parser.isoparse(iso_ts)
    return (datetime.now(timezone.utc) - t) <= timedelta(minutes=minutes)


def slack_post(text: str, blocks=None):
    payload = {"text": text}
    if blocks:
        payload["blocks"] = blocks
    
    try:
        r = requests.post(SLACK_WEBHOOK_URL, json=payload, timeout=20)
        r.raise_for_status()
    except requests.exceptions.HTTPError as e:
        print(f"Slack webhook error: {e}")
        print(f"Response status: {r.status_code}")
        print(f"Response text: {r.text}")
        print(f"Payload sent: {payload}")
        # Don't re-raise to avoid failing the entire workflow
        print("Continuing without Slack notification...")
    except Exception as e:
        print(f"Unexpected error sending to Slack: {e}")
        print("Continuing without Slack notification...")


def format_failure_block(run):
    url = run.get("html_url")
    name = run.get("name") or run.get("display_title") or "Workflow"
    conclusion = run.get("conclusion")
    branch = run.get("head_branch")
    sha = run.get("head_sha", "")[:7]

    head_commit = run.get("head_commit") or {}
    message = (head_commit.get("message") or "").splitlines()[0]
    author = (head_commit.get("author") or {}).get("name") or "unknown"

    updated = run.get("updated_at")

    return [
        {"type": "section", "text": {"type": "mrkdwn", "text": f"*🚨 CI/CD failure:* `{name}` on *{branch}@{sha}*"}},
        {"type": "context", "elements": [
            {"type": "mrkdwn", "text": f"*Conclusion:* `{conclusion}`"},
            {"type": "mrkdwn", "text": f"*By:* {author}"},
            {"type": "mrkdwn", "text": f"*When:* {updated}"},
        ]},
        {"type": "section", "text": {"type": "mrkdwn", "text": f"*Commit:* {message}\n<{url}|Open run>"}},
        {"type": "divider"}
    ]


def analyze(runs):
    subset = runs[:30]  # last 30 runs
    succ = [r for r in subset if r.get("conclusion") == "success"]
    fail = [r for r in subset if r.get("conclusion") == "failure"]

    # average duration (mins)
    durations = []
    for r in subset:
        s = r.get("run_started_at")
        u = r.get("updated_at")
        if s and u:
            s, u = parser.isoparse(s), parser.isoparse(u)
            durations.append((u - s).total_seconds())
    avg = round(sum(durations) / len(durations) / 60.0, 2) if durations else None

    # MTTR (mins): for each failure, time until the next success after it
    mttrs = []
    for i, fr in enumerate(subset):
        if fr.get("conclusion") != "failure":
            continue
        ftime = parser.isoparse(fr["updated_at"]) if fr.get("updated_at") else None
        if not ftime:
            continue
        for sr in subset:
            if sr.get("conclusion") != "success":
                continue
            stime = parser.isoparse(sr["updated_at"]) if sr.get("updated_at") else None
            if stime and stime > ftime:
                mttrs.append((stime - ftime).total_seconds())
                break
    mttr = round(sum(mttrs) / len(mttrs) / 60.0, 2) if mttrs else None

    return {
        "window": len(subset),
        "successes": len(succ),
        "failures": len(fail),
        "avg_duration_min": avg,
        "mttr_min": mttr,
    }


def main():
    runs = fetch_runs()

    # 1) Alerts for *newly completed* failed runs in LOOKBACK window
    failures = [
        r for r in runs
        if r.get("status") == "completed"
        and r.get("conclusion") in {"failure", "timed_out", "cancelled"}
        and r.get("updated_at") and within_lookback(r["updated_at"], LOOKBACK_MINUTES)
    ]

    if failures:
        blocks = []
        for r in failures:
            blocks.extend(format_failure_block(r))
        slack_post(f"{len(failures)} CI/CD failure(s) detected in {GITHUB_OWNER}/{GITHUB_REPO}", blocks)

    # 2) Lightweight analytics (last 30 runs)
    if SEND_ANALYTICS:
        metrics = analyze(runs)
        text = (
            f"📊 *Workflow analytics* for {GITHUB_OWNER}/{GITHUB_REPO}\n"
            f"Window: last {metrics['window']} runs | "
            f"Success: {metrics['successes']} | Failure: {metrics['failures']}\n"
            f"Avg duration: {metrics['avg_duration_min']} min | MTTR: {metrics['mttr_min']} min"
        )
        slack_post(text)


if __name__ == "__main__":
    # basic validation
    for var in ["GITHUB_OWNER", "GITHUB_REPO", "GITHUB_TOKEN", "SLACK_WEBHOOK_URL"]:
        if not globals().get(var):
            raise SystemExit(f"Missing required env var: {var}")
    main()
