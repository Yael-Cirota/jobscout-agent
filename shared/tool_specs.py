"""Names, descriptions and JSON schemas for the 7 tools (single source of truth)."""

_STATUSES = ["saved", "applied", "interview", "offer", "rejected"]

SPECS = {
    "search_jobs": {
        "description": (
            "Search the careers boards of the saved companies for developer jobs in Israel. "
            "Returns short rows only (id, title, company, city, url) - never descriptions. "
            "Defaults to the profile's roles and cities. Use only_new=true for 'anything new?'. "
            "'outside_cities' lists matching jobs hidden by the city filter."),
        "input_schema": {
            "type": "object",
            "properties": {
                "roles": {"type": "array", "items": {"type": "string"},
                          "description": "e.g. backend, fullstack. Defaults to profile roles."},
                "cities": {"type": "array", "items": {"type": "string"},
                           "description": "Defaults to profile cities."},
                "only_new": {"type": "boolean", "default": False,
                             "description": "Skip jobs already shown."},
                "limit": {"type": "integer", "default": 10, "maximum": 20},
            },
        },
    },
    "get_job_details": {
        "description": ("Fetch the cleaned description of ONE job. Call only when the user asks about "
                        "a specific job, never during a search. job_id comes from search_jobs."),
        "input_schema": {
            "type": "object",
            "properties": {"job_id": {"type": "string", "description": "e.g. gh:lightrun:4012345"}},
            "required": ["job_id"],
        },
    },
    "track_job": {
        "description": ("Save a job or move it to a new status "
                        "(saved/applied/interview/offer/rejected). job_id comes from search_jobs."),
        "input_schema": {
            "type": "object",
            "properties": {
                "job_id": {"type": "string"},
                "status": {"type": "string", "enum": _STATUSES},
                "note": {"type": "string", "default": ""},
            },
            "required": ["job_id", "status"],
        },
    },
    "get_tracker": {
        "description": "List tracked jobs, one line per job, optionally filtered by status.",
        "input_schema": {
            "type": "object",
            "properties": {"status": {"type": "string", "enum": _STATUSES}},
        },
    },
    "update_profile": {
        "description": (
            "Change the user's saved preferences and record why. Each list field REPLACES the old "
            "list, so when adding a city pass the existing cities too. Only call this after the user "
            "clearly asked for the change."),
        "input_schema": {
            "type": "object",
            "properties": {
                "reason": {"type": "string", "description": "Why, quoting the user's request."},
                "roles": {"type": "array", "items": {"type": "string"}},
                "cities": {"type": "array", "items": {"type": "string"}},
                "strict_cities": {"type": "boolean",
                                  "description": "true = never show jobs outside the cities."},
                "skip_companies": {"type": "array", "items": {"type": "string"}},
            },
            "required": ["reason"],
        },
    },
    "get_profile": {
        "description": "Return the full saved profile, including the log of past changes.",
        "input_schema": {"type": "object", "properties": {}},
    },
    "manage_companies": {
        "description": ("List, add or remove companies that are searched. Adding validates the "
                        "board token with one request."),
        "input_schema": {
            "type": "object",
            "properties": {
                "action": {"type": "string", "enum": ["list", "add", "remove"]},
                "name": {"type": "string"},
                "ats": {"type": "string", "enum": ["greenhouse", "lever"]},
                "token": {"type": "string", "description": "Board token / company slug."},
            },
            "required": ["action"],
        },
    },
}
