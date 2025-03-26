from django.db import models
from properties.models import LeaseAgreement
from accounts.models import CustomUser

# Create your models here.

class Payment(models.Model):
    PAYMENT_STATUS_CHOICES = (
        ('pending', 'Pending'),
        ('processing', 'Processing'),
        ('completed', 'Completed'),
        ('failed', 'Failed'),
        ('refunded', 'Refunded'),
    )
    
    PAYMENT_TYPE_CHOICES = (
        ('rent', 'Rent'),
        ('security_deposit', 'Security Deposit'),
        ('maintenance', 'Maintenance Fee'),
        ('late_fee', 'Late Fee'),
    )
    
    lease_agreement = models.ForeignKey(LeaseAgreement, on_delete=models.CASCADE)
    payment_type = models.CharField(max_length=20, choices=PAYMENT_TYPE_CHOICES)
    amount = models.DecimalField(max_digits=10, decimal_places=2)
    due_date = models.DateField()
    payment_date = models.DateTimeField(null=True, blank=True)
    status = models.CharField(max_length=20, choices=PAYMENT_STATUS_CHOICES, default='pending')
    payment_method = models.CharField(max_length=50, blank=True)
    transaction_id = models.CharField(max_length=100, blank=True)
    stripe_payment_intent_id = models.CharField(max_length=100, blank=True)
    stripe_payment_method_id = models.CharField(max_length=100, blank=True)
    paid_by = models.ForeignKey(CustomUser, on_delete=models.SET_NULL, null=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    
    def __str__(self):
        return f"{self.payment_type} - {self.lease_agreement.property.title}"

    class Meta:
        ordering = ['-due_date']

class PaymentReminder(models.Model):
    payment = models.ForeignKey(Payment, on_delete=models.CASCADE)
    reminder_date = models.DateField()
    is_sent = models.BooleanField(default=False)
    sent_date = models.DateTimeField(null=True, blank=True)
    
    def __str__(self):
        return f"Reminder for {self.payment}"

class Invoice(models.Model):
    payment = models.OneToOneField(Payment, on_delete=models.CASCADE)
    invoice_number = models.CharField(max_length=50, unique=True)
    generated_date = models.DateTimeField(auto_now_add=True)
    due_date = models.DateField()
    notes = models.TextField(blank=True)
    is_sent = models.BooleanField(default=False)
    
    def __str__(self):
        return f"Invoice #{self.invoice_number} - {self.payment.lease_agreement.property.title}"

class PaymentDocument(models.Model):
    payment = models.ForeignKey(Payment, on_delete=models.CASCADE, related_name='documents')
    document = models.FileField(upload_to='payment_documents/')
    document_type = models.CharField(max_length=50)
    uploaded_by = models.ForeignKey(CustomUser, on_delete=models.SET_NULL, null=True)
    uploaded_at = models.DateTimeField(auto_now_add=True)
    description = models.TextField(blank=True)

    def __str__(self):
        return f"{self.document_type} - {self.payment}"

    class Meta:
        ordering = ['-uploaded_at']

class PaymentHistory(models.Model):
    ACTION_CHOICES = (
        ('CREATED', 'Created'),
        ('UPDATED', 'Updated'),
        ('SUBMITTED', 'Submitted'),
        ('CONFIRMED', 'Confirmed'),
        ('REJECTED', 'Rejected'),
        ('REFUNDED', 'Refunded'),
    )

    payment = models.ForeignKey(Payment, on_delete=models.CASCADE, related_name='history')
    user = models.ForeignKey(CustomUser, on_delete=models.SET_NULL, null=True)
    action = models.CharField(max_length=20, choices=ACTION_CHOICES)
    description = models.TextField()
    created_at = models.DateTimeField(auto_now_add=True)
    metadata = models.JSONField(default=dict, blank=True)

    def __str__(self):
        return f"{self.action} - {self.payment} by {self.user}"

    class Meta:
        ordering = ['-created_at']
        verbose_name_plural = 'Payment histories'