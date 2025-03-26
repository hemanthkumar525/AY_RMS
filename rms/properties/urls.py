from django.urls import path
from . import views

app_name = 'properties'

urlpatterns = [
    # Property URLs
    path('', views.property_list, name='property_list'),
    path('create/', views.property_create, name='property_create'),
    path('<int:pk>/', views.property_detail, name='property_detail'),
    
    # Property Unit URLs
    path('<int:property_pk>/unit/create/', views.unit_create, name='unit_create'),
    path('<int:property_pk>/unit/<int:pk>/update/', views.unit_update, name='unit_update'),
    path('<int:property_pk>/unit/<int:pk>/delete/', views.unit_delete, name='unit_delete'),
    
    # Lease Agreement URLs
    path('lease/', views.lease_list, name='lease_list'),
    path('<int:property_pk>/lease/create/', views.lease_agreement_create, name='lease_create'),
    path('<int:property_pk>/lease/<int:lease_pk>/change-status/', views.lease_status_change, name='lease_status_change'),
    
    # Maintenance URLs
    path('maintenance/', views.maintenance_request_list, name='maintenance_list'),
    path('<int:property_pk>/maintenance/create/', views.maintenance_request_create, name='maintenance_create'),
    
    # Invoice URLs
    path('invoices/', views.invoice_list, name='invoice_list'),
    path('lease/<int:lease_id>/invoice/create/', views.invoice_create, name='invoice_create'),
    path('invoice/<int:pk>/', views.invoice_detail, name='invoice_detail'),
    path('invoice/<int:pk>/update/', views.invoice_update, name='invoice_update'),
    path('invoice/<int:pk>/mark-paid/', views.mark_invoice_as_paid, name='mark_invoice_paid'),
]
