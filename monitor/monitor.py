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
INCLUDE_CANCELLED = os.getenv("INCLUDE_CANCELLED", "false").lower() == "true"

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


def _parse_ts(ts):
    try:
        return parser.isoparse(ts) if ts else None
    except Exception:
        return None

def analyze(runs):
    # 1) Exclude the monitor workflow itself by name
    ci_cd_runs = [r for r in runs if r.get("name") not in ["Monitor Workflows", "monitor", "Monitor"]]
    cutoff = datetime.now(timezone.utc) - timedelta(minutes=LOOKBACK_MINUTES)
    ci_cd_runs = [r for r in ci_cd_runs if _parse_ts(r.get("updated_at")) and _parse_ts(r["updated_at"]) >= cutoff]


    # 2) Sort newest first and keep only the latest run per commit (head_sha)
    ci_cd_runs.sort(key=lambda r: _parse_ts(r.get("updated_at")) or datetime.min.replace(tzinfo=timezone.utc), reverse=True)
    latest_by_sha = {}
    for r in ci_cd_runs:
        sha = r.get("head_sha")
        if sha and sha not in latest_by_sha:
            latest_by_sha[sha] = r
    deduped = list(latest_by_sha.values())

    # 3) Consider only the most recent N after dedupe
    subset = deduped[:30]

    print(f"Analytics - Total workflow runs fetched: {len(runs)}")
    print(f"Analytics - CI/CD runs (excluding monitor): {len(ci_cd_runs)}")
    print(f"Analytics - After dedupe by head_sha: {len(deduped)}")
    print(f"Analytics - Analyzing last {len(subset)} CI/CD runs (deduped)")

    if not subset:
        return {
            "window": 0,
            "successes": 0,
            "failures": 0,
            "avg_duration_min": None,
            "mttr_min": None,
        }

    # 4) Only completed runs count for S/F
    completed = [r for r in subset if r.get("status") == "completed"]

    # 5) Count outcomes
    successes = [r for r in completed if r.get("conclusion") == "success"]
    failure_states = {"failure", "timed_out"}
    if INCLUDE_CANCELLED:
        failure_states.add("cancelled")
    failures = [r for r in completed if r.get("conclusion") in failure_states]

    print(f"Analytics - Success: {len(successes)}, Failures: {len(failures)}")

    # 6) Show a few for sanity
    print("Analytics - Recent (deduped) runs:")
    for i, r in enumerate(subset[:5]):
        print(f"  {i+1}. {r.get('name')} - {r.get('status')} - {r.get('conclusion')} - {r.get('updated_at', 'N/A')[:19]}")

    # 7) Average duration (mins) using completed runs only
    durations = []
    for r in completed:
        s = _parse_ts(r.get("run_started_at"))
        u = _parse_ts(r.get("updated_at"))
        if s and u:
            durations.append((u - s).total_seconds())
    avg = round(sum(durations) / len(durations) / 60.0, 2) if durations else None

    # 8) MTTR: for each failure, time to the next success AFTER it (within completed set)
    mttrs = []
    for fr in completed:
        if fr.get("conclusion") not in failure_states:
            continue
        ftime = _parse_ts(fr.get("updated_at"))
        if not ftime:
            continue
        later_successes = [sr for sr in completed if sr.get("conclusion") == "success" and _parse_ts(sr.get("updated_at")) and _parse_ts(sr["updated_at"]) > ftime]
        if later_successes:
            stime = min(_parse_ts(sr["updated_at"]) for sr in later_successes)
            mttrs.append((stime - ftime).total_seconds())
    mttr = round(sum(mttrs) / len(mttrs) / 60.0, 2) if mttrs else None

    return {
        "window": len(completed),      # number of completed runs in the analyzed window
        "successes": len(successes),
        "failures": len(failures),
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
