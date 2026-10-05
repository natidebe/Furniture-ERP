from rest_framework.permissions import SAFE_METHODS, BasePermission


class HasRole(BasePermission):
    allowed_roles: tuple[str, ...] = ()

    def has_permission(self, request, view):
        return bool(request.user and request.user.is_authenticated
                    and request.user.role in self.allowed_roles)


def role_permission(*roles):
    return type("RolePermission", (HasRole,), {"allowed_roles": roles})


IsAdmin = role_permission("admin")
IsAccountantOrAdmin = role_permission("accountant", "admin")
IsSalesStaff = role_permission("salesperson", "accountant", "admin")
IsStorekeeper = role_permission("storekeeper", "admin")


class IsAdminOrReadOnly(BasePermission):
    """Any signed-in user can read; only admins can write."""

    def has_permission(self, request, view):
        if not (request.user and request.user.is_authenticated):
            return False
        return request.method in SAFE_METHODS or request.user.role == "admin"
