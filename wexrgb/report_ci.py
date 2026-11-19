#!/usr/bin/env python3
"""Persist a concise non-secret CI log to the test branch for auditability.

Runs on the GitHub macOS runner with the workflow's GITHUB_TOKEN.
The path ci-report/ is deliberately excluded from workflow push triggers.
"""
import base64,datetime,json,os,pathlib,urllib.request,urllib.error

def main():
    repo=os.environ["GITHUB_REPOSITORY"]
    branch=os.environ["GITHUB_REF_NAME"]
    run=os.environ["GITHUB_RUN_ID"]
    result=os.environ.get("CI_RESULT","unknown")
    token=os.environ["CI_REPORT_TOKEN"]
    root=pathlib.Path(os.environ["GITHUB_WORKSPACE"])
    chunks=[f"CI run: https://github.com/{repo}/actions/runs/{run}",
            f"Branch: {branch}",f"State before reporting: {result}",
            f"Timestamp: {datetime.datetime.now(datetime.timezone.utc).isoformat()}"]
    for name in ("ci_prepare.log","ci_test.log","ci_build.log","ci_package.log"):
        f=root/name
        if f.exists():
            s=f.read_text(errors="replace")
            chunks.append(f"\n===== {name} (last 18000 chars) =====\n{s[-18000:]}")
        else:
            chunks.append(f"\n===== {name} =====\nNot reached.")
    payload="\n".join(chunks)+"\n"
    path="ci-report/latest-colorpolicy.txt"
    url=f"https://api.github.com/repos/{repo}/contents/{path}"
    headers={
        "Authorization":f"Bearer {token}",
        "Accept":"application/vnd.github+json",
        "X-GitHub-Api-Version":"2022-11-28",
        "User-Agent":"Yoga-ColorPolicy-CI"
    }
    sha=None
    req=urllib.request.Request(url,headers=headers,method="GET")
    try:
        with urllib.request.urlopen(req,timeout=30) as r:
            sha=json.load(r)["sha"]
    except urllib.error.HTTPError as e:
        if e.code!=404:raise
    obj={
        "message":f"CI report: native HDMI color policy run {run} ({result})",
        "content":base64.b64encode(payload.encode()).decode(),
        "branch":branch
    }
    if sha:obj["sha"]=sha
    put=urllib.request.Request(url,data=json.dumps(obj).encode(),headers={
        **headers,"Content-Type":"application/json"
    },method="PUT")
    with urllib.request.urlopen(put,timeout=30) as r:
        response=json.load(r)
    print("CI report published:",response.get("content",{}).get("html_url"))
    print("Compilation state:",result)

if __name__=="__main__":main()
