"""
Queen State Manager — CLI helper for persisting and inspecting Queen agent state.

Usage:
    py -m tools.queen_state init <task_id> <goal>
    py -m tools.queen_state update <task_id> <subtask_id> <status> [result_file]
    py -m tools.queen_state status <task_id>
    py -m tools.queen_state list
    py -m tools.queen_state report <task_id>

State lives in .motor/queen_state/ as JSON files.
"""

import json
import os
import sys
from datetime import datetime

QUEEN_STATE_DIR = os.path.join(os.path.dirname(os.path.dirname(__file__)), ".motor", "queen_state")
PLANS_DIR = os.path.join(QUEEN_STATE_DIR, "plans")
TASKS_DIR = os.path.join(QUEEN_STATE_DIR, "tasks")
REPORTS_DIR = os.path.join(QUEEN_STATE_DIR, "reports")
LOGS_DIR = os.path.join(QUEEN_STATE_DIR, "logs")


def _ensure_dirs():
    for d in [PLANS_DIR, TASKS_DIR, REPORTS_DIR, LOGS_DIR]:
        os.makedirs(d, exist_ok=True)


def _load_json(path):
    if not os.path.exists(path):
        return None
    with open(path, "r", encoding="utf-8") as f:
        return json.load(f)


def _save_json(path, data):
    with open(path, "w", encoding="utf-8") as f:
        json.dump(data, f, indent=2, ensure_ascii=False)


def cmd_init(task_id, goal):
    _ensure_dirs()
    plan = {
        "task_id": task_id,
        "created_at": datetime.now().isoformat(),
        "goal": goal,
        "status": "in_progress",
        "subtasks": [],
        "final_report": None,
    }
    _save_json(os.path.join(PLANS_DIR, f"{task_id}.json"), plan)
    _save_json(os.path.join(TASKS_DIR, f"{task_id}.json"), {"status": "in_progress", "steps_completed": 0, "steps_failed": 0})
    print(f"Plan initialized: {task_id}")
    print(f"  Goal: {goal}")
    print(f"  Plan: {PLANS_DIR}/{task_id}.json")


def cmd_update(task_id, subtask_id, status, result_file=None):
    plan_path = os.path.join(PLANS_DIR, f"{task_id}.json")
    plan = _load_json(plan_path)
    if not plan:
        print(f"Error: No plan found for task_id '{task_id}'", file=sys.stderr)
        sys.exit(1)

    for st in plan["subtasks"]:
        if st["id"] == subtask_id:
            st["status"] = status
            if result_file:
                result = _load_json(result_file)
                st["result"] = result
            break
    else:
        plan["subtasks"].append({
            "id": subtask_id,
            "status": status,
            "result": _load_json(result_file) if result_file else None,
        })

    _save_json(plan_path, plan)

    task_path = os.path.join(TASKS_DIR, f"{task_id}.json")
    task = _load_json(task_path) or {"status": "in_progress", "steps_completed": 0, "steps_failed": 0}
    if status == "completed":
        task["steps_completed"] += 1
    elif status == "failed":
        task["steps_failed"] += 1
    _save_json(task_path, task)

    print(f"Subtask {subtask_id} -> {status}")


def cmd_status(task_id):
    plan = _load_json(os.path.join(PLANS_DIR, f"{task_id}.json"))
    if not plan:
        print(f"No plan found: {task_id}")
        sys.exit(1)
    task = _load_json(os.path.join(TASKS_DIR, f"{task_id}.json"))

    print(f"Task: {task_id}")
    print(f"Goal: {plan['goal']}")
    print(f"Status: {plan['status']}")
    if task:
        print(f"Steps completed: {task.get('steps_completed', 0)}")
        print(f"Steps failed: {task.get('steps_failed', 0)}")
    print(f"\nSubtasks ({len(plan['subtasks'])}):")
    for st in plan["subtasks"]:
        marker = {"completed": "[OK]", "failed": "[FAIL]", "running": "[RUN]", "pending": "[--]"}
        icon = marker.get(st.get("status", "pending"), "[??]")
        print(f"  {icon} {st['id']}: {st.get('status', 'pending')}")
        if st.get("result") and st["result"].get("summary"):
            print(f"       {st['result']['summary']}")


def cmd_list():
    _ensure_dirs()
    plans = [f.replace(".json", "") for f in os.listdir(PLANS_DIR) if f.endswith(".json")]
    if not plans:
        print("No plans found.")
        return
    print(f"Tasks ({len(plans)}):")
    for pid in sorted(plans, reverse=True):
        plan = _load_json(os.path.join(PLANS_DIR, f"{pid}.json"))
        if plan:
            status_icon = {"in_progress": "[RUN]", "completed": "[OK]", "failed": "[FAIL]"}
            icon = status_icon.get(plan.get("status", ""), "[??]")
            print(f"  {icon} {pid}: {plan.get('goal', '?')[:60]}")


def cmd_report(task_id):
    plan = _load_json(os.path.join(PLANS_DIR, f"{task_id}.json"))
    if not plan:
        print(f"No plan found: {task_id}")
        sys.exit(1)
    report = {
        "task_id": task_id,
        "goal": plan["goal"],
        "status": plan["status"],
        "subtasks": [
            {"id": st["id"], "status": st.get("status"), "result_summary": st.get("result", {}).get("summary") if st.get("result") else None}
            for st in plan["subtasks"]
        ],
        "generated_at": datetime.now().isoformat(),
    }
    _save_json(os.path.join(REPORTS_DIR, f"{task_id}.json"), report)
    print(json.dumps(report, indent=2, ensure_ascii=False))


def main():
    if len(sys.argv) < 2:
        print(__doc__)
        sys.exit(1)

    command = sys.argv[1]

    if command == "init":
        if len(sys.argv) < 4:
            print("Usage: py -m tools.queen_state init <task_id> <goal>")
            sys.exit(1)
        cmd_init(sys.argv[2], sys.argv[3])

    elif command == "update":
        if len(sys.argv) < 5:
            print("Usage: py -m tools.queen_state update <task_id> <subtask_id> <status> [result_file]")
            sys.exit(1)
        cmd_update(sys.argv[2], sys.argv[3], sys.argv[4], sys.argv[5] if len(sys.argv) > 5 else None)

    elif command == "status":
        if len(sys.argv) < 3:
            print("Usage: py -m tools.queen_state status <task_id>")
            sys.exit(1)
        cmd_status(sys.argv[2])

    elif command == "list":
        cmd_list()

    elif command == "report":
        if len(sys.argv) < 3:
            print("Usage: py -m tools.queen_state report <task_id>")
            sys.exit(1)
        cmd_report(sys.argv[2])

    else:
        print(f"Unknown command: {command}", file=sys.stderr)
        print(__doc__)
        sys.exit(1)


if __name__ == "__main__":
    main()
