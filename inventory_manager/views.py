from django.db.models import Sum, Count, Q, F
from django.utils import timezone
from rest_framework import viewsets, filters, status, serializers
from rest_framework.decorators import action
from rest_framework.response import Response
from rest_framework.permissions import IsAuthenticated
from django_filters.rest_framework import DjangoFilterBackend
from datetime import datetime, timedelta

from .models import Category, Supplier, Product, StockEntry, Sale, SaleItem
from .serializers import (
    CategorySerializer,
    SupplierSerializer,
    ProductListSerializer,
    ProductDetailSerializer,
    ProductCreateUpdateSerializer,
    StockEntrySerializer,
    SaleSerializer,
    SaleCreateSerializer,
    DashboardStatsSerializer,
)


class BusinessSpecificPermission(IsAuthenticated):
    """Base permission class to restrict access to business-specific data"""

    def has_permission(self, request, view):
        if not super().has_permission(request, view):
            return False

        # Superusers can access everything
        if request.user.is_superuser:
            return True

        # User must have a business association
        if not request.user.business:
            return False

        # Check role-based permissions
        method = request.method
        role = request.user.role

        # Read permissions
        if method in ["GET", "HEAD", "OPTIONS"]:
            # Everyone can read
            return True

        # Write permissions
        if method in ["POST", "PUT", "PATCH", "DELETE"]:
            # Only staff, admin, and owner can modify
            if role in ["staff", "admin", "owner"]:
                return True

            # Accountants can only create/modify sales, stock entries
            if role == "accountant" and view.basename in ["sale", "stockentry"]:
                return True

        return False

    def has_object_permission(self, request, view, obj):
        if request.user.is_superuser:
            return True

        # Check if the object belongs to the user's business
        business = request.user.business

        # For models with direct business field
        if hasattr(obj, "business"):
            return obj.business == business

        # For models with business through supplier
        if hasattr(obj, "supplier") and hasattr(obj.supplier, "business"):
            return obj.supplier.business == business

        # For sales, check if any associated products belong to the business
        if hasattr(obj, "items"):
            # For sale objects, check associated products
            for item in obj.items.all():
                if item.product.supplier.business != business:
                    return False
            return True

        # For stock entries, check product's supplier business
        if hasattr(obj, "product") and hasattr(obj.product, "supplier"):
            return obj.product.supplier.business == business

        # Default deny
        return False


class BusinessQuerySetMixin:
    """Mixin to filter querysets to only include objects from user's business"""

    def get_queryset(self):
        queryset = super().get_queryset()
        user = self.request.user

        # Superusers can see everything
        if user.is_superuser:
            return queryset

        # Filter by business
        business = user.business
        if not business:
            return queryset.none()  # No business, no data

        # Apply business filter depending on model
        model_name = queryset.model.__name__

        if model_name == "Category":
            # Categories might be shared across businesses or business-specific
            if hasattr(queryset.model, "business"):
                return queryset.filter(business=business)
            return queryset

        elif model_name == "Supplier":
            return queryset.filter(business=business)

        elif model_name == "Product":
            return queryset.filter(supplier__business=business)

        elif model_name == "StockEntry":
            return queryset.filter(product__supplier__business=business)

        elif model_name == "Sale":
            # This is more complex - sales might need a separate business field
            # or we filter based on products sold
            if hasattr(queryset.model, "business"):
                return queryset.filter(business=business)
            # Alternatively filter by items if there's a product relationship
            return queryset.filter(
                items__product__supplier__business=business
            ).distinct()

        # Default case
        return queryset.none()


class CategoryViewSet(BusinessQuerySetMixin, viewsets.ModelViewSet):
    queryset = Category.objects.all()
    serializer_class = CategorySerializer
    permission_classes = [BusinessSpecificPermission]
    filter_backends = [filters.SearchFilter, filters.OrderingFilter]
    search_fields = ["name", "description"]
    ordering_fields = ["name", "created_at"]


class SupplierViewSet(BusinessQuerySetMixin, viewsets.ModelViewSet):
    queryset = Supplier.objects.all()
    serializer_class = SupplierSerializer
    permission_classes = [BusinessSpecificPermission]
    filter_backends = [
        filters.SearchFilter,
        filters.OrderingFilter,
        DjangoFilterBackend,
    ]
    search_fields = ["name", "contact_person", "email", "phone"]
    filterset_fields = ["is_active"]
    ordering_fields = ["name", "created_at"]

    def perform_create(self, serializer):
        # Automatically set the business to the user's business
        serializer.save(business=self.request.user.business)

    @action(detail=True, methods=["get"])
    def products(self, request, pk=None):
        """List all products from this supplier"""
        supplier = self.get_object()
        products = supplier.products.all()
        serializer = ProductListSerializer(products, many=True)
        return Response(serializer.data)


class ProductViewSet(BusinessQuerySetMixin, viewsets.ModelViewSet):
    queryset = Product.objects.all()
    permission_classes = [BusinessSpecificPermission]
    filter_backends = [
        filters.SearchFilter,
        filters.OrderingFilter,
        DjangoFilterBackend,
    ]
    search_fields = ["name", "sku", "description", "barcode"]
    filterset_fields = ["category", "supplier", "is_active"]
    ordering_fields = ["name", "stock", "cost_price", "selling_price", "created_at"]

    def get_serializer_class(self):
        if self.action == "list":
            return ProductListSerializer
        elif self.action in ["create", "update", "partial_update"]:
            return ProductCreateUpdateSerializer
        return ProductDetailSerializer

    def get_queryset(self):
        queryset = super().get_queryset()

        # Additional filter for role-based access
        user = self.request.user

        # Accountants can only see active products
        if user.role == "accountant":
            queryset = queryset.filter(is_active=True)

        return queryset

    @action(detail=True, methods=["get"])
    def stock_entries(self, request, pk=None):
        """List all stock entries for this product"""
        product = self.get_object()
        entries = product.stock_entries.all()
        serializer = StockEntrySerializer(entries, many=True)
        return Response(serializer.data)

    @action(detail=False, methods=["get"])
    def low_stock(self, request):
        """List all products that need reordering"""
        products = self.get_queryset().filter(stock__lte=F("reorder_level"))
        serializer = ProductListSerializer(products, many=True)
        return Response(serializer.data)


class StockEntryViewSet(BusinessQuerySetMixin, viewsets.ModelViewSet):
    queryset = StockEntry.objects.all()
    serializer_class = StockEntrySerializer
    permission_classes = [BusinessSpecificPermission]
    filter_backends = [filters.OrderingFilter, DjangoFilterBackend]
    filterset_fields = ["product", "entry_type"]
    ordering_fields = ["date_added"]

    def perform_create(self, serializer):
        # Verify the product belongs to the user's business
        product = serializer.validated_data.get("product")
        if product and product.supplier.business != self.request.user.business:
            raise serializers.ValidationError(
                "You can only add stock entries for products in your business."
            )

        # Add the current user as the creator
        serializer.save(created_by=self.request.user.username)


class SaleViewSet(BusinessQuerySetMixin, viewsets.ModelViewSet):
    queryset = Sale.objects.all()
    permission_classes = [BusinessSpecificPermission]
    filter_backends = [filters.SearchFilter, filters.OrderingFilter]
    search_fields = ["invoice_number", "customer_name"]
    ordering_fields = ["sale_date", "total_amount"]

    def get_serializer_class(self):
        if self.action in ["create", "update", "partial_update"]:
            return SaleCreateSerializer
        return SaleSerializer

    def perform_create(self, serializer):
        # Add the business to the sale if the model has a business field
        if hasattr(serializer.Meta.model, "business"):
            serializer.save(business=self.request.user.business)
        else:
            serializer.save()


class DashboardViewSet(viewsets.ViewSet):
    permission_classes = [BusinessSpecificPermission]
    basename = "dashboard"  # Required for permission checking

    def list(self, request):
        """Get dashboard statistics"""
        # Get current date
        today = timezone.now().date()
        start_of_month = today.replace(day=1)

        # Get user's business
        business = request.user.business

        # Business filter for queries
        business_filter = Q()
        if business and not request.user.is_superuser:
            business_filter = Q(supplier__business=business)

        # Calculate statistics
        total_products = Product.objects.filter(business_filter).count()
        low_stock_products = Product.objects.filter(
            business_filter, stock__lte=F("reorder_level")
        ).count()
        out_of_stock_products = Product.objects.filter(business_filter, stock=0).count()

        # Supplier and category counts
        supplier_filter = Q()
        if business and not request.user.is_superuser:
            supplier_filter = Q(business=business)
        total_suppliers = Supplier.objects.filter(supplier_filter).count()

        # Categories might be shared or business-specific
        category_filter = Q()
        if business and not request.user.is_superuser and hasattr(Category, "business"):
            category_filter = Q(business=business)
        total_categories = Category.objects.filter(category_filter).count()

        # Sales stats with business filter
        sales_filter = Q()
        if business and not request.user.is_superuser:
            if hasattr(Sale, "business"):
                sales_filter = Q(business=business)
            else:
                sales_filter = Q(items__product__supplier__business=business)

        sales_today = Sale.objects.filter(
            sales_filter, sale_date__date=today
        ).aggregate(total=Sum("total_amount", default=0))["total"]

        sales_this_month = Sale.objects.filter(
            sales_filter,
            sale_date__date__gte=start_of_month,
            sale_date__date__lte=today,
        ).aggregate(total=Sum("total_amount", default=0))["total"]

        # Inventory value (only for business's products)
        business_products = Product.objects.filter(business_filter)
        inventory_value = sum(product.stock_value for product in business_products)

        # Create stats object
        stats = {
            "total_products": total_products,
            "low_stock_products": low_stock_products,
            "out_of_stock_products": out_of_stock_products,
            "total_suppliers": total_suppliers,
            "total_categories": total_categories,
            "sales_today": sales_today,
            "sales_this_month": sales_this_month,
            "inventory_value": inventory_value,
        }

        serializer = DashboardStatsSerializer(stats)
        return Response(serializer.data)

    @action(detail=False, methods=["get"])
    def recent_sales(self, request):
        """Get recent sales for dashboard"""
        business = request.user.business

        # Business filter
        sales_filter = Q()
        if business and not request.user.is_superuser:
            if hasattr(Sale, "business"):
                sales_filter = Q(business=business)
            else:
                sales_filter = Q(items__product__supplier__business=business)

        recent_sales = (
            Sale.objects.filter(sales_filter).order_by("-sale_date").distinct()[:10]
        )
        serializer = SaleSerializer(recent_sales, many=True)
        return Response(serializer.data)

    @action(detail=False, methods=["get"])
    def top_selling_products(self, request):
        """Get top selling products for dashboard"""
        # Time period - default to last 30 days
        days = int(request.query_params.get("days", 30))
        start_date = timezone.now() - timedelta(days=days)

        # Business filter
        business = request.user.business
        business_filter = Q()
        if business and not request.user.is_superuser:
            business_filter = Q(supplier__business=business)

        top_products = (
            Product.objects.filter(
                business_filter, saleitem__sale__sale_date__gte=start_date
            )
            .annotate(
                sold_quantity=Sum("saleitem__quantity"),
                revenue=Sum(F("saleitem__quantity") * F("saleitem__unit_price")),
            )
            .order_by("-sold_quantity")[:10]
        )

        data = []
        for product in top_products:
            data.append(
                {
                    "id": product.id,
                    "name": product.name,
                    "sold_quantity": product.sold_quantity,
                    "revenue": product.revenue,
                }
            )

        return Response(data)
