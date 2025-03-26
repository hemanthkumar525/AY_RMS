from django.urls import path
from . import views

app_name = 'accounts'

urlpatterns = [
    # Authentication
    path('', views.user_login, name='login'),
    path('logout/', views.user_logout, name='logout'),
    
    # Registration
    path('register/property-owner/', views.register_property_owner, name='register_property_owner'),
    path('register/tenant/<int:property_id>/', views.register_tenant, name='register_tenant'),
    path('tenant_list/',views.tenant_list, name='tenant_list'),
    
    
    # Dashboard
    path('dashboard/', views.dashboard, name='dashboard'),
    path('superadmin/dashboard/', views.superadmin_dashboard, name='superadmin_dashboard'),
    
    # Subscription Management
    path('payment/', views.subscription_view, name='payment'),
    path('stripe_webhook', views.stripe_webhook, name='stripe_webhook'),
    path('payment_successful/', views.payment_successful, name='payment_successful'),
    path('payment_cancelled/', views.payment_cancelled,name="payment_cancelled" ),
    
    
    # Notifications
    path('notifications/', views.notifications_list, name='notifications_list'),
    path('notifications/<int:notification_id>/mark-as-read/', views.mark_as_read, name='mark_as_read'),
]