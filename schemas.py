"""OpenSpec Hermes tool schemas."""

WORKDIR_PROP = {
    "type": "string",
    "description": (
        "Project directory containing the openspec/ folder. Defaults to the "
        "agent/session working directory. Use an absolute path when known."
    ),
}

OPENSPEC_CONTEXT = {
    "name": "openspec_context",
    "description": (
        "Resolve a copyable OpenSpec identifier into working context. Paste an "
        "identifier like 'puzzletea' (a registered repo, by its vanity name) or "
        "'puzzletea/os_a1b2c3' (a specific change or spec within it) and this returns the "
        "repo path plus the change proposal/tasks/design/specs content, or the spec content. "
        "The bare repo name lists active changes and current specs with their tokens. Use the "
        "returned 'path' as 'workdir' for the other openspec_* tools. Call this "
        "first whenever the user gives you an OpenSpec identifier."
    ),
    "parameters": {
        "type": "object",
        "properties": {
            "identifier": {
                "type": "string",
                "description": "A repo vanity name ('puzzletea') or name/change-token ('puzzletea/os_a1b2c3').",
            },
        },
        "required": ["identifier"],
    },
}


OPENSPEC_LIST = {
    "name": "openspec_list",
    "description": (
        "List OpenSpec changes or specs in a project. Use before choosing a "
        "change/spec to inspect, validate, or coordinate with kanban tasks."
    ),
    "parameters": {
        "type": "object",
        "properties": {
            "workdir": WORKDIR_PROP,
            "kind": {
                "type": "string",
                "enum": ["changes", "specs"],
                "description": "Which OpenSpec items to list. Defaults to changes.",
            },
            "sort": {
                "type": "string",
                "enum": ["recent", "name"],
                "description": "Sort order. Defaults to recent.",
            },
        },
    },
}

OPENSPEC_SHOW = {
    "name": "openspec_show",
    "description": (
        "Show an OpenSpec change or spec as JSON. Use to read proposals, tasks, "
        "designs, specs, deltas, and requirement/scenario content."
    ),
    "parameters": {
        "type": "object",
        "properties": {
            "workdir": WORKDIR_PROP,
            "name": {"type": "string", "description": "Change or spec name to show."},
            "type": {
                "type": "string",
                "enum": ["change", "spec"],
                "description": "Disambiguate item type when needed.",
            },
            "deltas_only": {
                "type": "boolean",
                "description": "For changes, return only requirement deltas.",
            },
            "requirements_only": {
                "type": "boolean",
                "description": "For JSON output, omit scenarios and return requirement text only.",
            },
            "no_scenarios": {
                "type": "boolean",
                "description": "For JSON output, exclude scenario content.",
            },
            "requirement": {
                "type": "string",
                "description": "Optional 1-based requirement id to show, matching openspec --requirement.",
            },
        },
        "required": ["name"],
    },
}

OPENSPEC_VALIDATE = {
    "name": "openspec_validate",
    "description": (
        "Validate OpenSpec artifacts. Use after editing specs/proposals/tasks or "
        "before completing kanban tasks tied to OpenSpec work."
    ),
    "parameters": {
        "type": "object",
        "properties": {
            "workdir": WORKDIR_PROP,
            "target": {
                "type": "string",
                "description": "Specific change/spec name to validate. Omit when using scope.",
            },
            "scope": {
                "type": "string",
                "enum": ["target", "all", "changes", "specs"],
                "description": "Validation scope. Defaults to target if target is supplied, otherwise all.",
            },
            "type": {
                "type": "string",
                "enum": ["change", "spec"],
                "description": "Disambiguate target type when needed.",
            },
            "strict": {
                "type": "boolean",
                "description": "Enable strict validation. Defaults to true.",
            },
        },
    },
}

OPENSPEC_STATUS = {
    "name": "openspec_status",
    "description": (
        "Show artifact completion status for an OpenSpec change as JSON. Useful "
        "for turning proposal/task progress into kanban updates."
    ),
    "parameters": {
        "type": "object",
        "properties": {
            "workdir": WORKDIR_PROP,
            "change": {"type": "string", "description": "OpenSpec change id/name."},
            "schema": {"type": "string", "description": "Optional schema override."},
        },
        "required": ["change"],
    },
}

OPENSPEC_INSTRUCTIONS = {
    "name": "openspec_instructions",
    "description": (
        "Return enriched OpenSpec instructions for creating an artifact or "
        "applying tasks. Use before implementing a spec-driven change."
    ),
    "parameters": {
        "type": "object",
        "properties": {
            "workdir": WORKDIR_PROP,
            "artifact": {
                "type": "string",
                "description": "Artifact/instruction name, e.g. proposal, design, tasks, spec, apply.",
            },
            "change": {"type": "string", "description": "Optional change id/name."},
            "schema": {"type": "string", "description": "Optional schema override."},
        },
    },
}
