from django.urls import path, include
from rest_framework.routers import DefaultRouter
from rest_framework_simplejwt.views import (
    TokenObtainPairView,
    TokenRefreshView,
    TokenVerifyView,
)
from . import views

router = DefaultRouter()
router.register(r"businesses", views.BusinessViewSet)
router.register(r"users", views.UserViewSet)

urlpatterns = [
    # Djoser and JWT routes
    path("auth/", include("djoser.urls")),
    path("auth/jwt/create/", TokenObtainPairView.as_view(), name="token_obtain_pair"),
    path("auth/jwt/refresh/", TokenRefreshView.as_view(), name="token_refresh"),
    path("auth/jwt/verify/", TokenVerifyView.as_view(), name="token_verify"),
    # API routes
    path("", include(router.urls)),
]
