"""Project roles as the API names them, with labels for display."""

ROLE_LABELS = {
    "owner": "Owner",
    "analyst": "Analyst",
    "product_manager": "Product Manager",
    "viewer": "Viewer",
}
ROLES = list(ROLE_LABELS)


def label(role: str | None) -> str:
    return ROLE_LABELS.get(role, role or "")
