from django.urls import path
from properties import views
from payments.views import invoice_list
app_name = 'properties'

urlpatterns = [
    # Property URLs
    path('', views.property_list, name='property_list'),
    path('create/', views.property_create, name='property_create'),
    path('<int:pk>/', views.property_detail, name='property_detail'),
    path('webhook/stripe/', views.stripe_webhook, name='stripe_webhook'),
    
    # Property Unit URLs
    path('<int:property_pk>/unit/create/', views.unit_create, name='unit_create'),
    path('<int:property_pk>/unit/<int:pk>/update/', views.unit_update, name='unit_update'),
    path('<int:property_pk>/unit/<int:pk>/delete/', views.unit_delete, name='unit_delete'),
    
    # Lease Agreement URLs
    path('lease/', views.lease_list, name='lease_list'),
    path('<int:property_pk>/lease/create/', views.lease_agreement_create, name='lease_agreement_create'),
    path('lease/<int:pk>/update/', views.lease_agreement_update, name='lease_update'),
    path('<int:property_pk>/lease/<int:pk>/change-status/', views.lease_status_change, name='lease_status_change'),
    path('<int:property_pk>/lease/<int:pk>/delete/', views.lease_delete, name='lease_delete'),
    
    # Maintenance URLs
    path('maintenance/', views.maintenance_request_list, name='maintenance_list'),
    path('<int:property_pk>/maintenance/create/', views.maintenance_request_create, name='maintenance_request_create'),
    
    # Invoice URLs
    path('invoices/', invoice_list, name='invoice_list'),
    path('lease/<int:lease_id>/invoice/create/', views.invoice_create, name='invoice_create'),
    path('invoice/<int:pk>/', views.invoice_detail, name='invoice_detail'),
    path('invoice/<int:pk>/update/', views.invoice_update, name='invoice_update'),
    path('invoice/<int:pk>/mark-paid/', views.mark_invoice_as_paid, name='mark_invoice_paid'),
    path('invoice/<int:pk>/pay/', views.tenant_make_payment, name='tenant_make_payment'),
    path('invoice/<int:pk>/payment/success/', views.payment_success, name='payment_success'),

    # Bank Account URLs
    path('properties/<int:property_pk>/bank-accounts/<int:account_pk>/delete/', views.bank_account_delete, name='bank_account_delete'),
    path('<int:property_pk>/bank-account/create/', views.bank_account_create, name='bank_account_create'),
]