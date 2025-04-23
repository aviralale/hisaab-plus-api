from rest_framework import serializers
from .models import Category, Supplier, Product, StockEntry, Sale, SaleItem
from decimal import Decimal


# The original serializers remain unchanged
class CategorySerializer(serializers.ModelSerializer):
    class Meta:
        model = Category
        fields = "__all__"


class SupplierSerializer(serializers.ModelSerializer):
    class Meta:
        model = Supplier
        fields = "__all__"


class ProductListSerializer(serializers.ModelSerializer):
    category_name = serializers.ReadOnlyField(source="category.name")
    supplier_name = serializers.ReadOnlyField(source="supplier.name")
    profit_margin = serializers.ReadOnlyField()
    needs_reorder = serializers.ReadOnlyField()

    class Meta:
        model = Product
        fields = [
            "id",
            "name",
            "sku",
            "image",
            "category_name",
            "supplier_name",
            "stock",
            "cost_price",
            "selling_price",
            "profit_margin",
            "needs_reorder",
            "is_active",
        ]


class ProductDetailSerializer(serializers.ModelSerializer):
    category_name = serializers.ReadOnlyField(source="category.name")
    supplier_name = serializers.ReadOnlyField(source="supplier.name")
    profit_margin = serializers.ReadOnlyField()
    stock_value = serializers.ReadOnlyField()
    needs_reorder = serializers.ReadOnlyField()

    class Meta:
        model = Product
        fields = "__all__"


class ProductCreateUpdateSerializer(serializers.ModelSerializer):
    class Meta:
        model = Product
        fields = "__all__"

    def validate(self, data):
        """
        Check that selling price is not lower than cost price
        """
        if data.get("selling_price") and data.get("cost_price"):
            if data["selling_price"] < data["cost_price"]:
                raise serializers.ValidationError(
                    {"selling_price": "Selling price cannot be lower than cost price"}
                )
        return data


class StockEntrySerializer(serializers.ModelSerializer):
    product_name = serializers.ReadOnlyField(source="product.name")

    class Meta:
        model = StockEntry
        fields = "__all__"
        read_only_fields = ["created_by"]  # Typically set in the view

    def create(self, validated_data):
        # The product stock will be updated in the model's save method
        return super().create(validated_data)


class SaleItemSerializer(serializers.ModelSerializer):
    product_name = serializers.ReadOnlyField(source="product.name")
    subtotal = serializers.ReadOnlyField()

    class Meta:
        model = SaleItem
        fields = ["id", "product", "product_name", "quantity", "unit_price", "subtotal"]


class SaleSerializer(serializers.ModelSerializer):
    items = SaleItemSerializer(many=True, read_only=True)
    balance = serializers.ReadOnlyField()

    class Meta:
        model = Sale
        fields = "__all__"


class SaleCreateSerializer(serializers.ModelSerializer):
    items = SaleItemSerializer(many=True)
    balance = serializers.ReadOnlyField()

    class Meta:
        model = Sale
        fields = "__all__"

    def create(self, validated_data):
        items_data = validated_data.pop("items")
        sale = Sale.objects.create(**validated_data)

        total_amount = 0
        for item_data in items_data:
            product = item_data["product"]
            quantity = item_data["quantity"]
            unit_price = item_data["unit_price"]

            # Check if enough stock is available
            if product.stock < quantity:
                raise serializers.ValidationError(
                    f"Not enough stock for {product.name}. Available: {product.stock}"
                )

            sale_item = SaleItem.objects.create(sale=sale, **item_data)
            total_amount += sale_item.subtotal

        # Update the total amount
        sale.total_amount = total_amount
        sale.save()

        return sale


class RecentSaleSerializer(serializers.Serializer):
    """Serializer for recent sales on dashboard"""

    id = serializers.IntegerField()
    customer = serializers.CharField()
    amount = serializers.DecimalField(max_digits=12, decimal_places=2)
    status = serializers.CharField()
    sale_date = serializers.DateTimeField()


class LowStockProductSerializer(serializers.Serializer):
    """Serializer for low stock products on dashboard"""

    id = serializers.IntegerField()
    name = serializers.CharField()
    sku = serializers.CharField()
    stock = serializers.IntegerField()
    reorder_level = serializers.IntegerField()


class MonthlySalesDataSerializer(serializers.Serializer):
    """Serializer for monthly sales data for charts"""

    name = serializers.CharField()  # Month name
    amount = serializers.DecimalField(max_digits=12, decimal_places=2)


class DashboardStatsSerializer(serializers.Serializer):
    """Serializer for dashboard statistics"""

    # Basic stats
    business_name = serializers.CharField()
    total_products = serializers.IntegerField()
    low_stock_count = serializers.IntegerField()
    out_of_stock_products = serializers.IntegerField()
    total_suppliers = serializers.IntegerField()
    total_categories = serializers.IntegerField()

    # Financial metrics
    sales_today = serializers.DecimalField(max_digits=12, decimal_places=2)
    sales_yesterday = serializers.DecimalField(max_digits=12, decimal_places=2)
    sales_this_month = serializers.DecimalField(max_digits=12, decimal_places=2)
    inventory_value = serializers.DecimalField(max_digits=12, decimal_places=2)
    percentage_increase_from_yesterday = serializers.FloatField()
    percentage_increase_from_24h_ago = serializers.FloatField()
    percentage_increase_from_30_days_ago = serializers.FloatField()

    # Nested data for charts and tables
    recent_sales = RecentSaleSerializer(many=True)
    low_stock_products = LowStockProductSerializer(many=True)
    monthly_sales_data = MonthlySalesDataSerializer(many=True)


class SalesTrendSerializer(serializers.Serializer):
    """Serializer for daily sales trend data"""

    date = serializers.DateField()
    amount = serializers.DecimalField(max_digits=12, decimal_places=2)
    percentage_change_from_yesterday = serializers.FloatField()
    percentage_change_from_30_days_ago = serializers.FloatField()


class DashboardSerializer(serializers.Serializer):
    """Main dashboard serializer combining all data"""

    dashboard_stats = DashboardStatsSerializer()


class TopSellingProductSerializer(serializers.Serializer):
    """Serializer for top selling products"""

    id = serializers.IntegerField()
    name = serializers.CharField()
    sold_quantity = serializers.IntegerField()
    revenue = serializers.DecimalField(max_digits=12, decimal_places=2)
