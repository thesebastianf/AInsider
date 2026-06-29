"""
AInsider Tracker – Global Application State
Holds thread-safe or global variables for the running application.
"""

app_state = {
    "is_pipeline_running": False,
    "last_pipeline_run": None,
    "scheduler_interval_minutes": None,
    "price_update_interval_minutes": None,
}
