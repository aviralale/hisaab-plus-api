from rest_framework import serializers
from .models import Category, Supplier, Product, StockEntry, Sale, SaleItem, Business
from decimal import Decimal


class BusinessSerializer(serializers.ModelSerializer):
    """Serializer for business details"""

    class Meta:
        model = Business
        fields = [
            "id",
            "name",
            "address",
            "email",
            "phone",
        ]


class CategorySerializer(serializers.ModelSerializer):
    # Add business details instead of just ID
    business_details = BusinessSerializer(source="business", read_only=True)

    class Meta:
        model = Category
        fields = "__all__"


class SupplierSerializer(serializers.ModelSerializer):
    # Add business details instead of just ID
    business_details = BusinessSerializer(source="business", read_only=True)

    class Meta:
        model = Supplier
        fields = "__all__"


class ProductListSerializer(serializers.ModelSerializer):
    category_name = serializers.ReadOnlyField(source="category.name")
    supplier_name = serializers.ReadOnlyField(source="supplier.name")
    profit_margin = serializers.ReadOnlyField()
    needs_reorder = serializers.ReadOnlyField()
    # Add business details instead of just ID
    business_details = BusinessSerializer(source="business", read_only=True)

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
            "business",
            "business_details",
        ]


class ProductDetailSerializer(serializers.ModelSerializer):
    category_name = serializers.ReadOnlyField(source="category.name")
    supplier_name = serializers.ReadOnlyField(source="supplier.name")
    profit_margin = serializers.ReadOnlyField()
    stock_value = serializers.ReadOnlyField()
    needs_reorder = serializers.ReadOnlyField()
    # Add business details instead of just ID
    business_details = BusinessSerializer(source="business", read_only=True)

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
    # Add business details instead of just ID
    business_details = BusinessSerializer(source="business", read_only=True)

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
    payment_method = serializers.SerializerMethodField()

    class Meta:
        model = SaleItem
        fields = [
            "id",
            "product",
            "product_name",
            "payment_method",
            "quantity",
            "unit_price",
            "subtotal",
        ]

    def get_payment_method(self, obj):
        return obj.sale.payment_method if obj.sale else None


class SaleSerializer(serializers.ModelSerializer):
    items = SaleItemSerializer(many=True, read_only=True)
    balance = serializers.ReadOnlyField()
    # Add business details instead of just ID
    business_details = BusinessSerializer(source="business", read_only=True)

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


class ProductStockEntrySerializer(serializers.ModelSerializer):
    """Serializer for stock entries specific to a product"""

    created_by = serializers.CharField(read_only=True)
    entry_type_display = serializers.SerializerMethodField()

    class Meta:
        model = StockEntry
        fields = [
            "id",
            "date_added",
            "entry_type",
            "entry_type_display",
            "quantity",
            "unit_price",
            "notes",
            "created_by",
        ]

    def get_entry_type_display(self, obj):
        return dict(StockEntry.ENTRY_TYPE_CHOICES).get(obj.entry_type, obj.entry_type)


class ProductSaleItemSerializer(serializers.ModelSerializer):
    """Serializer for sale items specific to a product"""

    sale_date = serializers.DateTimeField(source="sale.sale_date")
    invoice_number = serializers.CharField(source="sale.invoice_number")
    customer_name = serializers.CharField(source="sale.customer_name", default="")
    payment_status = serializers.SerializerMethodField()
    # Add business details through sale relationship
    business_details = serializers.SerializerMethodField()

    class Meta:
        model = SaleItem
        fields = [
            "id",
            "sale_id",
            "sale_date",
            "invoice_number",
            "customer_name",
            "quantity",
            "unit_price",
            "subtotal",
            "payment_status",
            "business_details",
        ]

    def get_payment_status(self, obj):
        if obj.sale.paid_amount >= obj.sale.total_amount:
            return "Paid"
        elif obj.sale.paid_amount == 0:
            return "Unpaid"
        return "Partial"

    def get_business_details(self, obj):
        if hasattr(obj.sale, "business"):
            return BusinessSerializer(obj.sale.business).data
        return None


class ProductStatsSerializer(serializers.Serializer):
    """Serializer for product statistics"""

    product = serializers.DictField()
    sales = serializers.DictField()
    stock = serializers.DictField()
    # Add business details
    business_details = serializers.DictField()


class RecentSaleSerializer(serializers.Serializer):
    """Serializer for recent sales on dashboard"""

    id = serializers.IntegerField()
    customer = serializers.CharField()
    amount = serializers.DecimalField(max_digits=12, decimal_places=2)
    status = serializers.CharField()
    sale_date = serializers.DateTimeField()
    # Add business details
    business_details = serializers.DictField(required=False)


class LowStockProductSerializer(serializers.Serializer):
    """Serializer for low stock products on dashboard"""

    id = serializers.IntegerField()
    name = serializers.CharField()
    sku = serializers.CharField()
    stock = serializers.IntegerField()
    reorder_level = serializers.IntegerField()
    # Add business details
    business_details = serializers.DictField(required=False)


class MonthlySalesDataSerializer(serializers.Serializer):
    """Serializer for monthly sales data for charts"""

    name = serializers.CharField()  # Month name
    amount = serializers.DecimalField(max_digits=12, decimal_places=2)


class DashboardStatsSerializer(serializers.Serializer):
    """Serializer for dashboard statistics"""

    # Basic stats
    business_name = serializers.CharField()
    # Add full business details instead of just name
    business_details = serializers.DictField()
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
    # Add business details
    business_details = serializers.DictField(required=False)


class DashboardSerializer(serializers.Serializer):
    """Main dashboard serializer combining all data"""

    dashboard_stats = DashboardStatsSerializer()


class TopSellingProductSerializer(serializers.Serializer):
    """Serializer for top selling products"""

    id = serializers.IntegerField()
    name = serializers.CharField()
    sold_quantity = serializers.IntegerField()
    revenue = serializers.DecimalField(max_digits=12, decimal_places=2)
    # Add business details
    business_details = serializers.DictField(required=False)


class ProductSaleHistorySerializer(serializers.ModelSerializer):
    sale_date = serializers.DateTimeField(source="sale.sale_date")
    invoice_number = serializers.CharField(source="sale.invoice_number")
    customer_name = serializers.CharField(source="sale.customer_name", default="")
    subtotal = serializers.DecimalField(max_digits=12, decimal_places=2)

    class Meta:
        model = SaleItem
        fields = [
            "id",
            "sale_id",
            "sale_date",
            "invoice_number",
            "customer_name",
            "quantity",
            "unit_price",
            "subtotal",
        ]
