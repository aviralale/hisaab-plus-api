from rest_framework import serializers
from django.contrib.auth import get_user_model
from djoser.serializers import UserCreateSerializer, UserSerializer
from .models import Business, UserRoles

User = get_user_model()


class BusinessSerializer(serializers.ModelSerializer):
    class Meta:
        model = Business
        fields = [
            "id",
            "name",
            "legal_name",
            "business_type",
            "industry",
            "email",
            "phone",
            "address",
            "city",
            "state",
            "zip_code",
            "country",
            "tax_id",
            "fiscal_year_end",
            "currency_code",
            "timezone",
            "is_active",
            "created_at",
        ]


class BusinessCreateSerializer(serializers.ModelSerializer):
    # Structured data for nested objects in the frontend
    contactInfo = serializers.SerializerMethodField(required=False)
    address = serializers.SerializerMethodField(required=False)
    taxInfo = serializers.SerializerMethodField(required=False)
    settings = serializers.SerializerMethodField(required=False)

    class Meta:
        model = Business
        fields = [
            "name",
            "legal_name",
            "business_type",
            "industry",
            "contactInfo",
            "address",
            "taxInfo",
            "settings",
        ]

    def get_contactInfo(self, obj):
        # Not used for creation, but helps with validation
        return {}

    def get_address(self, obj):
        # Not used for creation, but helps with validation
        return {}

    def get_taxInfo(self, obj):
        # Not used for creation, but helps with validation
        return {}

    def get_settings(self, obj):
        # Not used for creation, but helps with validation
        return {}

    def create(self, validated_data):
        # Extract nested data from the request
        request_data = self.context.get("request").data
        user = self.context.get("request").user

        # Process contact info
        contact_info = request_data.get("contactInfo", {})
        validated_data["email"] = contact_info.get("email")
        validated_data["phone"] = contact_info.get("phone")

        # Process address
        address_data = request_data.get("address", {})
        validated_data["address"] = address_data.get("street")
        validated_data["city"] = address_data.get("city")
        validated_data["state"] = address_data.get("state")
        validated_data["zip_code"] = address_data.get("zipCode")
        validated_data["country"] = address_data.get("country")

        # Process tax info
        tax_info = request_data.get("taxInfo", {})
        validated_data["tax_id"] = tax_info.get("taxId")
        validated_data["fiscal_year_end"] = tax_info.get("fiscalYearEnd")

        # Process settings
        settings = request_data.get("settings", {})
        validated_data["currency_code"] = settings.get("currencyCode")
        validated_data["timezone"] = settings.get("timezone")
        validated_data["is_active"] = settings.get("isActive", True)

        # Create the business
        business = super().create(validated_data)

        # Set the user as the owner of this business
        if user.is_authenticated:
            user.business = business
            user.role = UserRoles.OWNER
            user.save()

        return business


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
