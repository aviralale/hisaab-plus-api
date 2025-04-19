from rest_framework import permissions


class IsBusinessOwnerOrAdmin(permissions.BasePermission):
    """
    Permission to allow only business owners/admins to manage their business
    """

    def has_object_permission(self, request, view, obj):
        # Read permissions are allowed to any authenticated user
        if request.method in permissions.SAFE_METHODS:
            return True

        # Only owners/admins of the business or superusers can edit
        user = request.user
        if user.is_superuser:
            return True

        # Check if user belongs to the business and has appropriate role
        if user.business == obj and (user.is_owner() or user.is_admin()):
            return True

        return False


class IsAdminUser(permissions.BasePermission):
    """
    Permission to allow only admins or owners to perform certain actions
    """

    def has_permission(self, request, view):
        user = request.user
        return user.is_authenticated and (
            user.is_admin() or user.is_owner() or user.is_superuser
        )


class IsSameUserOrAdmin(permissions.BasePermission):
    """
    Permission to allow users to edit their own data or admins to edit any user
    """

    def has_object_permission(self, request, view, obj):
        user = request.user
        # Users can edit themselves
        if obj == user:
            return True

        # Admins/owners can edit users in their business
        if user.business == obj.business and (
            user.is_admin() or user.is_owner() or user.is_superuser
        ):
            return True

        return False
