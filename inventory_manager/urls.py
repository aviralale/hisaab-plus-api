from django.urls import path, include
from rest_framework.routers import DefaultRouter
from . import views

router = DefaultRouter()
router.register(r"categories", views.CategoryViewSet)
router.register(r"suppliers", views.SupplierViewSet)
router.register(r"products", views.ProductViewSet)
router.register(r"stock-entries", views.StockEntryViewSet)
router.register(r"sales", views.SaleViewSet)
router.register(r"dashboard", views.DashboardViewSet, basename="dashboard")

urlpatterns = [
    path("", include(router.urls)),
]
