from django.db import models
from accounts.models import PropertyOwner, Tenant, CustomUser
from django.contrib.auth.models import AbstractUser
from django.core.validators import MinValueValidator, MaxValueValidator

# Create your models here.

class Property(models.Model):
    PROPERTY_TYPE_CHOICES = (
        ('apartment', 'Apartment'),
        ('house', 'House'),
        ('commercial', 'Commercial'),
        ('office', 'Office Space'),
    )
    
    owner = models.ForeignKey(PropertyOwner, on_delete=models.CASCADE)
    title = models.CharField(max_length=200)
    property_type = models.CharField(max_length=20, choices=PROPERTY_TYPE_CHOICES)
    address = models.TextField()
    city = models.CharField(max_length=100)
    state = models.CharField(max_length=100)
    is_available = models.BooleanField(default=True)
    postal_code = models.CharField(max_length=10)
    description = models.TextField(blank=True)  # Add back description field
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    def get_available_account_types(self):
        """Get payment gateway types available for this property"""
        return BankAccount.ACCOUNT_TYPES 

    @property
    def active_leases_count(self):
        """Returns the count of active lease agreements for this property"""
        return self.leaseagreement_set.filter(status='active').count()

    def __str__(self):
        return self.title



    # Keep only property-wide fields
    
class PropertyUnit(models.Model):
    
    
    property = models.ForeignKey(Property, on_delete=models.CASCADE, related_name='units')
    unit_number = models.CharField(max_length=20)
    monthly_rent = models.DecimalField(max_digits=10, decimal_places=2)
    bedrooms = models.PositiveIntegerField()
    bathrooms = models.DecimalField(max_digits=3, decimal_places=1)
    square_feet = models.PositiveIntegerField()
    is_available = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    def __str__(self):
        return f"{self.property.title} - {self.unit_number}"
    


class PropertyImage(models.Model):
    property = models.ForeignKey(Property, related_name='images', on_delete=models.CASCADE)
    image = models.ImageField(upload_to='property_images/')
    caption = models.CharField(max_length=200, blank=True)
    
    def __str__(self):
        return f"Image for {self.property.title}"


class BankAccount(models.Model):
    

    ACCOUNT_TYPES = (
        ('Paypal', 'Paypal'),
        ('Stripe', 'Stripe'),
    )
    
    STATUS_CHOICES = (
        ('Active', 'Active'),
        ('Inactive', 'Inactive'),
    )
    
    MODE_CHOICES = (
        ('Sandbox', 'Sandbox'),
        ('Live', 'Live'),
    )
    
    property = models.ForeignKey(Property, on_delete=models.CASCADE, related_name='bank_accounts')
    title = models.CharField(max_length=100)
    account_type = models.CharField(max_length=20, choices=ACCOUNT_TYPES)
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default='Active')
    account_mode = models.CharField(max_length=20, choices=MODE_CHOICES, default='Sandbox')
    client_id = models.CharField(max_length=255)
    secret_key = models.CharField(max_length=255)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    def __str__(self):
        return f"{self.title} - {self.account_type}"

    class Meta:
        ordering = ['-created_at']

   



class LeaseAgreement(models.Model):
    STATUS_CHOICES = (
        ('pending', 'Pending'),
        ('active', 'Active'),
        ('terminated', 'Terminated'),
        ('expired', 'Expired'),
    )
    
    property = models.ForeignKey(Property, on_delete=models.CASCADE)
    tenant = models.ForeignKey(Tenant, on_delete=models.CASCADE)
    bank_account = models.ForeignKey(BankAccount, on_delete=models.SET_NULL, null=True, blank=True)
    start_date = models.DateField()
    end_date = models.DateField()
    monthly_rent = models.DecimalField(max_digits=10, decimal_places=2)
    security_deposit = models.DecimalField(max_digits=10, decimal_places=2)
    rent_due_day = models.PositiveIntegerField(
        help_text="Day of the month when rent is due (1-31)",
        validators=[MinValueValidator(1), MaxValueValidator(31)],
        default=1
    )
    status = models.CharField(max_length=20, choices=STATUS_CHOICES)
    terms_and_conditions = models.TextField()
    signed_by_tenant = models.BooleanField(default=False)
    signed_by_owner = models.BooleanField(default=False)
    document = models.FileField(upload_to='lease_documents/', null=True, blank=True)
    property_unit = models.ForeignKey(PropertyUnit, on_delete=models.SET_NULL, null=True, blank=True, related_name='lease_agreements')
    created_at = models.DateTimeField(auto_now_add=True)
    
    def __str__(self):
        return f"Lease for {self.property.title} - {self.tenant.user.get_full_name()}"


class TenantProperty(models.Model):
    STATUS_CHOICES = (
        ('pending', 'Pending'),
        ('active', 'Active'),
        ('inactive', 'Inactive'),
    )
    
    tenant = models.ForeignKey(Tenant, on_delete=models.CASCADE, related_name='tenant_properties')
    property = models.ForeignKey(Property, on_delete=models.CASCADE, related_name='property_tenants')
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default='pending')
    start_date = models.DateTimeField(null=True, blank=True)
    end_date = models.DateTimeField(null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name_plural = "Tenant Properties"
        ordering = ['-created_at']
        unique_together = ['tenant', 'property']  # Prevent duplicate tenant-property relationships

    def __str__(self):
        return f"{self.tenant.user.email} - {self.property.title}"

    def get_status_active(self):
        return self.status == 'active'


class PropertyMaintenance(models.Model):
    STATUS_CHOICES = (
        ('pending', 'Pending'),
        ('in_progress', 'In Progress'),
        ('completed', 'Completed'),
        ('cancelled', 'Cancelled'),
    )
    
    property = models.ForeignKey(Property, on_delete=models.CASCADE)
    reported_by = models.ForeignKey(CustomUser, on_delete=models.CASCADE)
    title = models.CharField(max_length=200)
    description = models.TextField()
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default='pending')
    priority = models.CharField(max_length=20, choices=[('low', 'Low'), ('medium', 'Medium'), ('high', 'High')])
    reported_date = models.DateTimeField(auto_now_add=True)
    resolved_date = models.DateTimeField(null=True, blank=True)
    
    def __str__(self):
        return f"{self.title} - {self.property.title}"


class Invoice(models.Model):
    STATUS_CHOICES = (
        ('pending', 'Pending'),
        ('paid', 'Paid'),
        ('overdue', 'Overdue'),
        ('cancelled', 'Cancelled'),
    )

    PAYMENT_TYPE_CHOICES = (
        ('rent', 'Rent'),
        ('security_deposit', 'Security Deposit'),
        ('maintenance', 'Maintenance'),
        ('utility', 'Utility'),
        ('other', 'Other'),
    )

    lease_agreement = models.ForeignKey(LeaseAgreement, on_delete=models.CASCADE, related_name='invoices')
    property = models.ForeignKey(Property, on_delete=models.CASCADE)
    tenant = models.ForeignKey('accounts.Tenant', on_delete=models.CASCADE)
    invoice_number = models.CharField(max_length=50, unique=True)
    amount = models.DecimalField(max_digits=10, decimal_places=2)
    payment_type = models.CharField(max_length=20, choices=PAYMENT_TYPE_CHOICES)
    description = models.TextField(blank=True)
    due_date = models.DateField()
    issue_date = models.DateField(auto_now_add=True)
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default='pending')
    payment_date = models.DateField(null=True, blank=True)
    late_fee = models.DecimalField(max_digits=10, decimal_places=2, default=0)
    total_amount = models.DecimalField(max_digits=10, decimal_places=2)
    bank_account = models.ForeignKey(BankAccount, on_delete=models.SET_NULL, null=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    def save(self, *args, **kwargs):
        # Generate invoice number if not set
        if not self.invoice_number:
            last_invoice = Invoice.objects.order_by('-id').first()
            invoice_id = (last_invoice.id + 1) if last_invoice else 1
            self.invoice_number = f'INV-{self.property.id}-{invoice_id:06d}'
        
        # Calculate total amount including late fee
        self.total_amount = self.amount + self.late_fee
        
        super().save(*args, **kwargs)

    def __str__(self):
        return f'{self.invoice_number} - {self.tenant.user.get_full_name()}'

    class Meta:
        ordering = ['-created_at']
