from accounts.models import Business, User
from django.db import models
from django.utils import timezone
from django.core.validators import MinValueValidator
from django.core.exceptions import ValidationError


class Category(models.Model):
    name = models.CharField(max_length=100, unique=True)
    description = models.TextField(blank=True)
    business = models.ForeignKey(
        Business,
        on_delete=models.CASCADE,
        null=True,
        blank=True,
        related_name="categories",
    )
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    def __str__(self):
        return self.name

    class Meta:
        verbose_name_plural = "Categories"
        ordering = ["name"]
        # Ensure uniqueness per business if business field is used
        unique_together = ["name", "business"]


class Supplier(models.Model):
    name = models.CharField(max_length=150)
    contact_person = models.CharField(max_length=100, blank=True)
    phone = models.CharField(max_length=20, blank=True)
    email = models.EmailField(blank=True)
    address = models.TextField(blank=True)
    image = models.ImageField(upload_to="suppliers/", blank=True, null=True)
    business = models.ForeignKey(
        Business, on_delete=models.CASCADE, related_name="suppliers"
    )
    is_active = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    def __str__(self):
        return self.name

    class Meta:
        ordering = ["name"]
        # Ensure uniqueness per business
        unique_together = ["name", "business"]


class Product(models.Model):
    UNIT_CHOICES = [
        ("kg", "Kilogram"),
        ("g", "Gram"),
        ("l", "Liter"),
        ("ml", "Milliliter"),
        ("pcs", "Piece"),
        ("box", "Box"),
        ("pack", "Pack"),
    ]

    name = models.CharField(max_length=200)
    business = models.ForeignKey(
        Business, on_delete=models.CASCADE, related_name="products"
    )
    sku = models.CharField(max_length=50, verbose_name="SKU")
    description = models.TextField(blank=True)
    category = models.ForeignKey(
        Category, on_delete=models.CASCADE, related_name="products"
    )
    unit = models.CharField(max_length=50, choices=UNIT_CHOICES, default="pcs")
    cost_price = models.DecimalField(
        max_digits=10, decimal_places=2, validators=[MinValueValidator(0)]
    )
    selling_price = models.DecimalField(
        max_digits=10, decimal_places=2, validators=[MinValueValidator(0)]
    )
    stock = models.IntegerField(default=0)
    reorder_level = models.PositiveIntegerField(
        default=10, help_text="Minimum stock level before reordering"
    )
    supplier = models.ForeignKey(
        Supplier, on_delete=models.CASCADE, related_name="products"
    )
    image = models.ImageField(upload_to="products_images/", blank=True, null=True)
    barcode = models.CharField(max_length=100, blank=True)
    is_active = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    created_by = models.ForeignKey(
        User, on_delete=models.SET_NULL, null=True, related_name="created_products"
    )

    def __str__(self):
        return self.name

    @property
    def profit_margin(self):
        """Calculate profit margin percentage"""
        if not self.cost_price or self.cost_price <= 0:
            return 0
        return ((self.selling_price - self.cost_price) / self.cost_price) * 100

    @property
    def stock_value(self):
        """Calculate total stock value"""
        if not self.cost_price or not self.stock:
            return 0
        return self.stock * self.cost_price

    @property
    def needs_reorder(self):
        """Check if product needs reordering"""
        return self.stock <= self.reorder_level

    def clean(self):
        """
        Custom validation to ensure SKU is unique per business
        This replaces the unique_together constraint that used supplier__business
        """
        super().clean()

        # Check if this is a new product or if the SKU has changed
        if self.pk is None or Product.objects.get(pk=self.pk).sku != self.sku:
            # Only validate if supplier is set (for when creating via admin)
            if self.supplier_id:
                # Find products with the same SKU in the same business
                same_sku_products = Product.objects.filter(
                    sku=self.sku, supplier__business=self.supplier.business
                ).exclude(pk=self.pk)

                if same_sku_products.exists():
                    raise ValidationError(
                        {
                            "sku": f'A product with SKU "{self.sku}" already exists in this business.'
                        }
                    )

    def save(self, *args, **kwargs):
        """
        Override save method to run clean() for validation
        This ensures the validation happens even when save() is called directly
        """
        self.clean()
        super().save(*args, **kwargs)

    class Meta:
        ordering = ["name"]
        # Changed to only include direct fields - not using supplier__business anymore
        unique_together = ["sku", "supplier"]


class StockEntry(models.Model):
    ENTRY_TYPE_CHOICES = [
        ("purchase", "Purchase"),
        ("return", "Return"),
        ("adjustment", "Adjustment"),
    ]

    product = models.ForeignKey(
        Product, on_delete=models.CASCADE, related_name="stock_entries"
    )
    quantity = models.PositiveIntegerField(validators=[MinValueValidator(1)])
    entry_type = models.CharField(
        max_length=20, choices=ENTRY_TYPE_CHOICES, default="purchase"
    )
    unit_price = models.DecimalField(
        max_digits=10, decimal_places=2, validators=[MinValueValidator(0)]
    )
    date_added = models.DateTimeField(default=timezone.now)
    invoice_number = models.CharField(max_length=100, blank=True)
    notes = models.TextField(blank=True)
    created_by = models.ForeignKey(
        User, on_delete=models.SET_NULL, null=True, related_name="stock_entries"
    )

    def __str__(self):
        return f"{self.product.name} - {self.quantity} {self.product.unit} ({self.entry_type})"

    def save(self, *args, **kwargs):
        """Update product stock when entry is saved"""
        is_new = self.pk is None
        if is_new:
            # If this is a new entry, add to product stock
            self.product.stock += self.quantity
            self.product.save()
        super().save(*args, **kwargs)

    class Meta:
        verbose_name_plural = "Stock Entries"
        ordering = ["-date_added"]


class Sale(models.Model):
    PAYMENT_METHOD_CHOICES = [
        ("cash", "Cash"),
        ("card", "Card"),
        ("mobile_payment", "Mobile Payment"),
        ("cheque", "Cheque"),
        ("bank_transfer", "Bank Transfer"),
        ("credit", "Credit"),
    ]
    invoice_number = models.CharField(max_length=100)
    customer_name = models.CharField(max_length=200, blank=True)
    sale_date = models.DateTimeField(default=timezone.now)
    total_amount = models.DecimalField(max_digits=12, decimal_places=2, default=0)
    payment_method = models.CharField(
        max_length=20, choices=PAYMENT_METHOD_CHOICES, default="cash"
    )
    paid_amount = models.DecimalField(max_digits=12, decimal_places=2, default=0)
    notes = models.TextField(blank=True)
    business = models.ForeignKey(
        Business, on_delete=models.CASCADE, related_name="sales"
    )
    created_by = models.ForeignKey(
        User, on_delete=models.SET_NULL, null=True, related_name="sales"
    )
    created_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return f"Invoice #{self.invoice_number}"

    @property
    def balance(self):
        """Calculate remaining balance"""
        return self.total_amount - self.paid_amount

    class Meta:
        ordering = ["-sale_date"]
        # Ensure invoice numbers are unique per business
        unique_together = ["invoice_number", "business"]


class SaleItem(models.Model):
    sale = models.ForeignKey(Sale, on_delete=models.CASCADE, related_name="items")
    product = models.ForeignKey(Product, on_delete=models.CASCADE)
    quantity = models.PositiveIntegerField(validators=[MinValueValidator(1)])
    unit_price = models.DecimalField(max_digits=10, decimal_places=2)

    def __str__(self):
        return f"{self.product.name} - {self.quantity}"

    def save(self, *args, **kwargs):
        """Update product stock when sale item is saved"""
        is_new = self.pk is None
        if is_new:
            # If this is a new sale item, subtract from product stock
            self.product.stock -= self.quantity
            self.product.save()
        super().save(*args, **kwargs)

    @property
    def subtotal(self):
        if self.quantity is None or self.unit_price is None:
            return 0
        return self.quantity * self.unit_price
