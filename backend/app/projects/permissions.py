from app.models import ProjectRole

O, A, PM, V = ProjectRole.owner, ProjectRole.analyst, ProjectRole.product_manager, ProjectRole.viewer

PERMISSIONS: dict[str, set[ProjectRole]] = {
    "project.read":      {O, A, PM, V},
    "project.update":    {O},
    "members.manage":    {O},
    "categories.manage": {O},
    "reviews.write":     {O, A},
    "analysis.run":      {O, A},
    "issues.write":      {O, PM},
    "results.export":    {O, A, PM},
    "audit.read":        {O},
}

# Permissions that do not modify the project; still allowed on archived projects.
READ_ONLY = {"project.read", "results.export", "audit.read"}


def has_permission(role: ProjectRole | None, permission: str) -> bool:
    if permission not in PERMISSIONS:
        raise KeyError(f"Unknown permission: {permission}")
    return role is not None and role in PERMISSIONS[permission]
