"""Real end-to-end integration test runner for Screen-Aware GUI Subagent."""

import json
import time
from backend.agent.subagents.youtube_workflow import youtube_workflow
from backend.utils.logger import logger


def run_real_test():
    print("======================================================================")
    print("      REAL END-TO-END INTEGRATION TEST: YOUTUBE SEARCH TASK           ")
    print("======================================================================")
    print("Task: 'Open YouTube and search for Python tutorials.'")
    print("Mode: Live desktop execution (No mocks)")
    print("----------------------------------------------------------------------")

    start_t = time.perf_counter()
    result = youtube_workflow.execute_youtube_search(query="Python tutorials")
    total_time = time.perf_counter() - start_t

    report = {
        "task_name": "Open YouTube and search for Python tutorials",
        "final_status": "SUCCESS" if result.success else "FAILED",
        "initial_active_window": result.initial_active_window,
        "search_query": result.query,
        "grounding_method_used": result.grounding_method_used,
        "grounded_coordinates": result.grounded_coordinates,
        "executed_actions": result.executed_actions,
        "verification_message": result.verification_message,
        "recovery_steps_taken": result.recovery_steps_taken,
        "latencies": {
            "total_duration_seconds": round(total_time, 2),
            "observation_latency_ms": result.observation_latency_ms,
            "grounding_latency_ms": result.grounding_latency_ms,
            "action_latency_ms": result.action_latency_ms,
            "verification_latency_ms": result.verification_latency_ms,
        }
    }

    print("\n---------------- INTEGRATION TEST REPORT ----------------")
    print(json.dumps(report, indent=2))
    print("======================================================================\n")
    return report


if __name__ == "__main__":
    run_real_test()
