from django.contrib.auth.models import (
    BaseUserManager,
    AbstractBaseUser,
    PermissionsMixin,
)
from django.db import models
from django.utils import timezone


# Role choices for users
class UserRoles(models.TextChoices):
    ADMIN = "admin", "Admin"
    STAFF = "staff", "Staff"
    ACCOUNTANT = "accountant", "Accountant"
    OWNER = "owner", "Owner"


# Each business has its own users (multi-tenancy)
class Business(models.Model):
    name = models.CharField(max_length=255)
    address = models.TextField(blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return self.name


class UserManager(BaseUserManager):
    def create_user(self, email, full_name=None, password=None, **extra_fields):
        if not email:
            raise ValueError("Users must have an email address")
        email = self.normalize_email(email)
        user = self.model(email=email, full_name=full_name, **extra_fields)
        user.set_password(password)
        user.save(using=self._db)
        return user

    def create_superuser(self, email, full_name=None, password=None, **extra_fields):
        extra_fields.setdefault("is_staff", True)
        extra_fields.setdefault("is_superuser", True)
        extra_fields.setdefault("role", UserRoles.ADMIN)

        if extra_fields.get("is_staff") is not True:
            raise ValueError("Superuser must have is_staff=True.")
        if extra_fields.get("is_superuser") is not True:
            raise ValueError("Superuser must have is_superuser=True.")
        return self.create_user(email, full_name, password, **extra_fields)


class User(AbstractBaseUser, PermissionsMixin):
    email = models.EmailField(unique=True)
    full_name = models.CharField(max_length=255)
    phone = models.CharField(max_length=20, blank=True, null=True)

    business = models.ForeignKey(
        Business, on_delete=models.CASCADE, null=True, blank=True, related_name="users"
    )
    role = models.CharField(
        max_length=20, choices=UserRoles.choices, default=UserRoles.STAFF
    )

    is_active = models.BooleanField(default=True)
    is_staff = models.BooleanField(default=False)

    date_joined = models.DateTimeField(default=timezone.now)
    last_login = models.DateTimeField(blank=True, null=True)

    objects = UserManager()

    USERNAME_FIELD = "email"
    REQUIRED_FIELDS = ["full_name"]

    def __str__(self):
        return f"{self.full_name} ({self.email})"

    def is_owner(self):
        return self.role == UserRoles.OWNER

    def is_admin(self):
        return self.role == UserRoles.ADMIN
