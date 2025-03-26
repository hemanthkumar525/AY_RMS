from django.contrib import admin
from .models import Payment, PaymentReminder, Invoice

class PaymentReminderInline(admin.TabularInline):
    model = PaymentReminder
    extra = 1

class InvoiceInline(admin.TabularInline):
    model = Invoice
    extra = 0
    show_change_link = True

class PaymentAdmin(admin.ModelAdmin):
    list_display = ('lease_agreement', 'payment_type', 'amount', 'due_date', 
                   'status', 'payment_date', 'paid_by')
    list_filter = ('payment_type', 'status', 'due_date', 'payment_date')
    search_fields = ('lease_agreement__property__title', 
                    'lease_agreement__tenant__user__username',
                    'transaction_id')
    raw_id_fields = ('lease_agreement', 'paid_by')
    date_hierarchy = 'due_date'
    inlines = [PaymentReminderInline, InvoiceInline]

    def get_queryset(self, request):
        qs = super().get_queryset(request)
        if request.user.is_superuser:
            return qs
        elif request.user.is_property_owner():
            return qs.filter(lease_agreement__property__owner__user=request.user)
        elif request.user.is_tenant():
            return qs.filter(lease_agreement__tenant__user=request.user)
        return qs.none()

class InvoiceAdmin(admin.ModelAdmin):
    list_display = ('invoice_number', 'payment', 'generated_date', 'due_date', 'is_sent')
    list_filter = ('is_sent', 'generated_date', 'due_date')
    search_fields = ('invoice_number', 'payment__lease_agreement__property__title')
    raw_id_fields = ('payment',)
    date_hierarchy = 'due_date'

    def get_queryset(self, request):
        qs = super().get_queryset(request)
        if request.user.is_superuser:
            return qs
        elif request.user.is_property_owner():
            return qs.filter(payment__lease_agreement__property__owner__user=request.user)
        elif request.user.is_tenant():
            return qs.filter(payment__lease_agreement__tenant__user=request.user)
        return qs.none()

class PaymentReminderAdmin(admin.ModelAdmin):
    list_display = ('payment', 'reminder_date', 'is_sent', 'sent_date')
    list_filter = ('is_sent', 'reminder_date', 'sent_date')
    search_fields = ('payment__lease_agreement__property__title',)
    raw_id_fields = ('payment',)
    date_hierarchy = 'reminder_date'

    def get_queryset(self, request):
        qs = super().get_queryset(request)
        if request.user.is_superuser:
            return qs
        elif request.user.is_property_owner():
            return qs.filter(payment__lease_agreement__property__owner__user=request.user)
        return qs.none()

admin.site.register(Payment, PaymentAdmin)
admin.site.register(Invoice, InvoiceAdmin)
admin.site.register(PaymentReminder, PaymentReminderAdmin)
