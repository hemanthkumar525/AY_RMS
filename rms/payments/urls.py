from django.urls import path
from . import views

app_name = 'payments'

urlpatterns = [
    # Payment URLs
    path('payments/', views.PaymentListView.as_view(), name='payment_list'),
    path('payments/create/', views.PaymentCreateView.as_view(), name='payment_create'),
    path('payments/<int:pk>/', views.PaymentDetailView.as_view(), name='payment_detail'),
    path('payments/<int:pk>/update/', views.PaymentUpdateView.as_view(), name='payment_update'),
    path('payments/create-intent/<int:payment_id>/', views.create_payment_intent, name='create_payment_intent'),
    path('payments/webhook/', views.stripe_webhook, name='stripe_webhook'),
    path('payments/receipt/<int:pk>/', views.payment_receipt, name='payment_receipt'),
    path('payments/complete/', views.payment_complete, name='payment_complete'),
    path('payments/make/<int:lease_id>/', views.make_payment, name='make_payment'),
    
    # Invoice URLs
    path('invoices/', views.InvoiceListView.as_view(), name='invoice_list'),
    path('invoices/create/', views.InvoiceCreateView.as_view(), name='invoice_create'),
    path('invoices/<int:pk>/', views.InvoiceDetailView.as_view(), name='invoice_detail'),
    path('invoices/<int:pk>/update/', views.InvoiceUpdateView.as_view(), name='invoice_update'),
    path('invoices/<int:invoice_id>/pay/', views.tenant_make_payment, name='tenant_make_payment'),
    path('invoices/<int:pk>/success/', views.payment_success, name='payment_success'),
    
    # AJAX URLs
    path('get-lease-details/', views.get_lease_details, name='get_lease_details'),
]