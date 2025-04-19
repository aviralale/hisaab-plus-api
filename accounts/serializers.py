from rest_framework import serializers
from django.contrib.auth import get_user_model
from djoser.serializers import UserCreateSerializer, UserSerializer
from .models import Business

User = get_user_model()


class BusinessSerializer(serializers.ModelSerializer):
    class Meta:
        model = Business
        fields = ["id", "name", "address", "created_at"]


class BusinessCreateSerializer(serializers.ModelSerializer):
    class Meta:
        model = Business
        fields = ["name", "address"]


class CustomUserCreateSerializer(UserCreateSerializer):
    business = serializers.PrimaryKeyRelatedField(
        queryset=Business.objects.all(), required=False, allow_null=True
    )

    class Meta(UserCreateSerializer.Meta):
        model = User
        fields = ["id", "email", "full_name", "phone", "password", "business", "role"]


class CustomUserSerializer(UserSerializer):
    business_details = BusinessSerializer(source="business", read_only=True)
    role_display = serializers.CharField(source="get_role_display", read_only=True)

    class Meta(UserSerializer.Meta):
        model = User
        fields = [
            "id",
            "email",
            "full_name",
            "phone",
            "business",
            "business_details",
            "role",
            "role_display",
            "is_active",
            "date_joined",
            "last_login",
        ]
        read_only_fields = ["date_joined", "last_login"]


class UserUpdateSerializer(serializers.ModelSerializer):
    class Meta:
        model = User
        fields = ["full_name", "phone", "business", "role", "is_active"]

    def validate_business(self, value):
        # Only allow admins and owners to change the business
        user = self.context["request"].user
        if not (user.is_admin() or user.is_owner() or user.is_superuser):
            if self.instance.business != value:
                raise serializers.ValidationError(
                    "You don't have permission to change the business"
                )
        return value

    def validate_role(self, value):
        # Only allow admins and owners to change roles
        user = self.context["request"].user
        if not (user.is_admin() or user.is_owner() or user.is_superuser):
            if self.instance.role != value:
                raise serializers.ValidationError(
                    "You don't have permission to change user roles"
                )
        return value


class PasswordChangeSerializer(serializers.Serializer):
    current_password = serializers.CharField(required=True)
    new_password = serializers.CharField(required=True)

    def validate_current_password(self, value):
        user = self.context["request"].user
        if not user.check_password(value):
            raise serializers.ValidationError("Current password is incorrect")
        return value

    def validate_new_password(self, value):
        # Add password validation if needed
        if len(value) < 8:
            raise serializers.ValidationError(
                "Password must be at least 8 characters long"
            )
        return value


class BusinessUsersSerializer(serializers.ModelSerializer):
    users_count = serializers.SerializerMethodField()

    class Meta:
        model = Business
        fields = ["id", "name", "address", "created_at", "users_count"]

    def get_users_count(self, obj):
        return obj.users.count()
