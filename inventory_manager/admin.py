from django.contrib import admin
from django.utils.html import format_html
from django.db.models import Sum, F, DecimalField
from django.urls import reverse
from django.contrib.auth.admin import UserAdmin as BaseUserAdmin

from .models import Category, Supplier, Product, StockEntry, Sale, SaleItem

from accounts.models import User, Business, UserRoles


# Register Business model
@admin.register(Business)
class BusinessAdmin(admin.ModelAdmin):
    list_display = ("name", "created_at", "user_count")
    search_fields = ("name", "address")
    readonly_fields = ("created_at",)

    def user_count(self, obj):
        return obj.users.count()

    user_count.short_description = "Number of Users"


# Custom User Admin
@admin.register(User)
class UserAdmin(BaseUserAdmin):
    list_display = (
        "email",
        "full_name",
        "business",
        "role",
        "is_active",
        "date_joined",
    )
    list_filter = ("is_active", "role", "business")
    search_fields = ("email", "full_name", "phone")
    ordering = ("email",)
    fieldsets = (
        (None, {"fields": ("email", "password")}),
        ("Personal info", {"fields": ("full_name", "phone")}),
        ("Business info", {"fields": ("business", "role")}),
        (
            "Permissions",
            {
                "fields": (
                    "is_active",
                    "is_staff",
                    "is_superuser",
                    "groups",
                    "user_permissions",
                )
            },
        ),
        ("Important dates", {"fields": ("last_login", "date_joined")}),
    )
    add_fieldsets = (
        (
            None,
            {
                "classes": ("wide",),
                "fields": (
                    "email",
                    "full_name",
                    "password1",
                    "password2",
                    "business",
                    "role",
                    "is_active",
                    "is_staff",
                ),
            },
        ),
    )
    filter_horizontal = (
        "groups",
        "user_permissions",
    )


# Category Admin
@admin.register(Category)
class CategoryAdmin(admin.ModelAdmin):
    list_display = ("name", "business", "product_count", "created_at")
    list_filter = ("business",)
    search_fields = ("name", "description")
    readonly_fields = ("created_at", "updated_at")

    def product_count(self, obj):
        return obj.products.count()

    product_count.short_description = "Products"


# Supplier Admin
@admin.register(Supplier)
class SupplierAdmin(admin.ModelAdmin):
    list_display = ("name", "contact_person", "business", "phone", "email", "is_active")
    list_filter = ("is_active", "business")
    search_fields = ("name", "contact_person", "email", "phone")
    readonly_fields = ("created_at", "updated_at")
    list_editable = ("is_active",)

    fieldsets = (
        (None, {"fields": ("name", "business", "is_active")}),
        (
            "Contact Information",
            {"fields": ("contact_person", "phone", "email", "address")},
        ),
        ("Image", {"fields": ("image",)}),
    )


# Product Admin
@admin.register(Product)
class ProductAdmin(admin.ModelAdmin):
    list_display = (
        "name",
        "sku",
        "category",
        "stock",
        "cost_price",
        "selling_price",
        "profit_margin_display",
        "supplier",
        "is_active",
        "stock_status",
    )
    list_filter = ("is_active", "category", "supplier", "unit")
    search_fields = ("name", "sku", "description", "barcode")
    readonly_fields = (
        "created_at",
        "updated_at",
        "created_by",
        "profit_margin",
        "stock_value",
    )
    list_editable = ("is_active",)

    fieldsets = (
        (None, {"fields": ("name", "sku", "description", "barcode", "is_active")}),
        ("Category & Supplier", {"fields": ("category", "supplier")}),
        ("Stock Information", {"fields": ("unit", "stock", "reorder_level")}),
        (
            "Pricing",
            {"fields": ("cost_price", "selling_price", "profit_margin", "stock_value")},
        ),
        ("Image", {"fields": ("image",)}),
        (
            "Meta Information",
            {
                "fields": ("created_at", "updated_at", "created_by"),
                "classes": ("collapse",),
            },
        ),
    )

    def profit_margin_display(self, obj):
        try:
            margin = float(obj.profit_margin)
        except (ValueError, TypeError):
            return "-"

        if margin < 10:
            color = "red"
        elif margin < 20:
            color = "orange"
        else:
            color = "green"

        # Make sure margin is a float before formatting
        formatted = "{:.2f}".format(margin)
        return format_html('<span style="color: {};">{}%</span>', color, formatted)

    profit_margin_display.short_description = "Profit Margin"

    def stock_status(self, obj):
        if obj.needs_reorder:
            return format_html('<span style="color: red;">Low Stock</span>')
        return format_html('<span style="color: green;">OK</span>')

    stock_status.short_description = "Stock Status"

    def save_model(self, request, obj, form, change):
        if not obj.created_by:
            obj.created_by = request.user
        super().save_model(request, obj, form, change)


# StockEntry Admin
@admin.register(StockEntry)
class StockEntryAdmin(admin.ModelAdmin):
    list_display = (
        "product",
        "quantity",
        "entry_type",
        "unit_price",
        "total_cost",
        "date_added",
        "created_by",
    )
    list_filter = ("entry_type", "date_added", "product__category")
    search_fields = ("product__name", "invoice_number", "notes")
    readonly_fields = ("created_by",)

    fieldsets = (
        (None, {"fields": ("product", "quantity", "unit_price", "entry_type")}),
        (
            "Additional Information",
            {"fields": ("invoice_number", "date_added", "notes")},
        ),
        ("Meta Information", {"fields": ("created_by",), "classes": ("collapse",)}),
    )

    def total_cost(self, obj):
        return obj.quantity * obj.unit_price

    total_cost.short_description = "Total Cost"

    def save_model(self, request, obj, form, change):
        if not obj.created_by:
            obj.created_by = request.user
        super().save_model(request, obj, form, change)


# SaleItem Inline for Sale Admin
class SaleItemInline(admin.TabularInline):
    model = SaleItem
    extra = 1
    fields = ("product", "quantity", "unit_price", "subtotal")
    readonly_fields = ("subtotal",)

    def subtotal(self, obj):
        if obj.pk:
            return obj.subtotal
        return 0

    subtotal.short_description = "Subtotal"


# Sale Admin
@admin.register(Sale)
class SaleAdmin(admin.ModelAdmin):
    list_display = (
        "invoice_number",
        "customer_name",
        "business",
        "sale_date",
        "total_amount",
        "paid_amount",
        "balance_due",
        "created_by",
    )
    list_filter = ("sale_date", "business")
    search_fields = ("invoice_number", "customer_name", "notes")
    readonly_fields = ("created_at", "created_by", "balance")
    inlines = [SaleItemInline]

    fieldsets = (
        (
            None,
            {"fields": ("invoice_number", "customer_name", "business", "sale_date")},
        ),
        ("Financial", {"fields": ("total_amount", "paid_amount", "balance")}),
        ("Additional Information", {"fields": ("notes",)}),
        (
            "Meta Information",
            {"fields": ("created_at", "created_by"), "classes": ("collapse",)},
        ),
    )

    def balance_due(self, obj):
        balance = obj.balance
        if balance > 0:
            return format_html('<span style="color: red;">{:.2f}</span>', balance)
        return format_html('<span style="color: green;">0.00</span>')

    balance_due.short_description = "Balance Due"

    def save_model(self, request, obj, form, change):
        if not obj.created_by:
            obj.created_by = request.user
        super().save_model(request, obj, form, change)


# Optional: Register SaleItem separately (though it's already in an inline)
@admin.register(SaleItem)
class SaleItemAdmin(admin.ModelAdmin):
    list_display = ("sale", "product", "quantity", "unit_price", "subtotal")
    list_filter = ("sale__sale_date",)
    search_fields = ("product__name", "sale__invoice_number")
    readonly_fields = ("subtotal",)

    def subtotal(self, obj):
        return obj.subtotal

    subtotal.short_description = "Subtotal"
