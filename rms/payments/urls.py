from django.urls import path
from . import views

app_name = 'payments'

urlpatterns = [
    # ... your existing urls ...
    path('create-intent/<int:payment_id>/', views.create_payment_intent, name='create_payment_intent'),
    path('webhook/', views.stripe_webhook, name='stripe_webhook'),
    path('detail/<int:pk>/', views.payment_detail, name='payment_detail'),
    path('receipt/<int:pk>/', views.payment_receipt, name='payment_receipt'),
    path('complete/', views.payment_complete, name='payment_complete'),
    path('make/<int:lease_id>/', views.make_payment, name='make_payment'),
]