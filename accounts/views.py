from rest_framework import viewsets, generics, permissions, status
from rest_framework.decorators import action
from rest_framework.response import Response
from django.contrib.auth import get_user_model
from .models import Business
from .serializers import (
    BusinessSerializer,
    BusinessCreateSerializer,
    CustomUserSerializer,
    UserUpdateSerializer,
    PasswordChangeSerializer,
)
from .permissions import IsBusinessOwnerOrAdmin, IsAdminUser, IsSameUserOrAdmin

User = get_user_model()


class BusinessViewSet(viewsets.ModelViewSet):
    queryset = Business.objects.all()
    permission_classes = [permissions.IsAuthenticated]

    def get_serializer_class(self):
        if self.action in ["create", "update", "partial_update"]:
            return BusinessCreateSerializer
        return BusinessSerializer

    def get_permissions(self):
        if self.action in ["update", "partial_update", "destroy"]:
            return [IsBusinessOwnerOrAdmin()]
        return super().get_permissions()

    @action(detail=True, methods=["get"])
    def users(self, request, pk=None):
        """Get all users for a business"""
        business = self.get_object()
        users = business.users.all()
        serializer = CustomUserSerializer(users, many=True)
        return Response(serializer.data)


class UserViewSet(viewsets.ModelViewSet):
    queryset = User.objects.all()
    serializer_class = CustomUserSerializer
    permission_classes = [permissions.IsAuthenticated]

    def get_queryset(self):
        user = self.request.user
        # Superusers can see all users
        if user.is_superuser:
            return User.objects.all()
        # Non-admin users can only see users from their business
        if not (user.is_admin() or user.is_owner()):
            if user.business:
                return User.objects.filter(business=user.business)
            return User.objects.filter(id=user.id)  # Only themselves
        # Admins and owners can see all users from their business
        if user.business:
            return User.objects.filter(business=user.business)
        return User.objects.filter(id=user.id)  # Only themselves

    def get_serializer_class(self):
        if self.action in ["update", "partial_update"]:
            return UserUpdateSerializer
        return CustomUserSerializer

    def get_permissions(self):
        if self.action in ["update", "partial_update"]:
            return [IsSameUserOrAdmin()]
        if self.action in ["create", "destroy"]:
            return [IsAdminUser()]
        return super().get_permissions()

    @action(detail=False, methods=["get"])
    def me(self, request):
        """Get current user details"""
        serializer = self.get_serializer(request.user)
        return Response(serializer.data)

    @action(detail=True, methods=["post"])
    def change_password(self, request, pk=None):
        """Change password for a user"""
        user = self.get_object()
        # Only the user themselves or an admin can change password
        if user != request.user and not (
            request.user.is_admin()
            or request.user.is_owner()
            or request.user.is_superuser
        ):
            return Response(
                {"detail": "You don't have permission to change this user's password."},
                status=status.HTTP_403_FORBIDDEN,
            )

        serializer = PasswordChangeSerializer(
            data=request.data, context={"request": request}
        )
        if serializer.is_valid():
            user.set_password(serializer.validated_data["new_password"])
            user.save()
            return Response({"detail": "Password changed successfully."})
        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)
