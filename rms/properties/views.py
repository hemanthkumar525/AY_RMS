from django.shortcuts import render, redirect, get_object_or_404
from django.contrib.auth.decorators import login_required
from django.contrib import messages
from django.http import JsonResponse, HttpResponseForbidden
from django.urls import reverse
from django.views.decorators.csrf import csrf_exempt
from django.conf import settings
import json
import logging
import stripe
from notifications.utils import create_notification
from .models import Property, PropertyUnit, LeaseAgreement, BankAccount, PropertyMaintenance
from accounts.models import Tenant
from payments.models import Invoice

logger = logging.getLogger(__name__)

from django.forms import inlineformset_factory
from django.db.models import Q
from django.core.paginator import Paginator
from django.utils import timezone
from datetime import datetime, timedelta
from .forms import (
    PropertyForm, PropertyImageForm, LeaseAgreementForm,
    PropertyMaintenanceForm, PropertySearchForm, PropertyUnitForm, BankAccountForm
)
from accounts.models import PropertyOwner, Tenant
from django.db import transaction
from payments.models import Invoice
from payments.forms import InvoiceForm

UnitFormSet = inlineformset_factory(
    Property, 
    PropertyUnit,
    form=PropertyUnitForm,  
    fields=['unit_number', 'monthly_rent', 
           'bedrooms', 'bathrooms', 'square_feet', 'is_available'],
    extra=1,
    can_delete=True
)


@login_required
def property_list(request):
    form = PropertySearchForm(request.GET)
    
    # Filter properties based on user role
    if request.user.is_property_owner():
        properties = Property.objects.filter(owner__user=request.user)
    else:
        properties = Property.objects.all()
    
    if form.is_valid():
        keyword = form.cleaned_data.get('keyword')
        property_type = form.cleaned_data.get('property_type')
        city = form.cleaned_data.get('city')
        price_range = form.cleaned_data.get('price_range')
        bedrooms = form.cleaned_data.get('bedrooms')
        
        if keyword:
            properties = properties.filter(
                Q(title__icontains=keyword) |
                Q(description__icontains=keyword) |
                Q(address__icontains=keyword)
            )
        if property_type:
            properties = properties.filter(property_type=property_type)
        if city:
            properties = properties.filter(city__icontains=city)
        if price_range:
            min_price, max_price = map(int, price_range.split('-'))
            properties = properties.filter(monthly_rent__range=(min_price, max_price))
        if bedrooms:
            if bedrooms == '6+':
                properties = properties.filter(bedrooms__gte=6)
            else:
                properties = properties.filter(bedrooms=int(bedrooms))
    
    return render(request, 'properties/property_list.html', {
        'properties': properties,
        'form': form
    })

@login_required
def property_detail(request, pk):
    property = get_object_or_404(Property, pk=pk)
    if request.user != property.owner.user:
        return HttpResponseForbidden()
        
    # Handle lease creation
    if request.method == 'POST':
        if 'create_lease' in request.POST:
            lease_form = LeaseAgreementForm(request.POST, request.FILES, property=property)
            if lease_form.is_valid():
                lease = lease_form.save(commit=False)
                lease.property = property
                lease.status = 'pending'
                lease.save()
                messages.success(request, 'Lease agreement created successfully!')
                return redirect('properties:property_detail', pk=pk)
            bank_form = BankAccountForm(property=property)
        elif 'create_bank_account' in request.POST:
            bank_form = BankAccountForm(request.POST, property=property)
            if bank_form.is_valid():
                bank_account = bank_form.save(commit=False)
                bank_account.property = property
                bank_account.save()
                messages.success(request, 'Payment account added successfully!')
                return redirect('properties:property_detail', pk=pk)
            lease_form = LeaseAgreementForm(property=property)
        else:
            lease_form = LeaseAgreementForm(property=property)
            bank_form = BankAccountForm(property=property)
    else:
        lease_form = LeaseAgreementForm(property=property)
        bank_form = BankAccountForm(property=property)
    
    # Get active bank accounts for lease creation
    active_accounts = property.bank_accounts.filter(status='Active')
    
    images = property.images.all()
    lease_agreements = LeaseAgreement.objects.filter(property=property)
    maintenance_requests = PropertyMaintenance.objects.filter(property=property)
    
    # Get all invoices for this property using the property_invoices relation
    invoices = property.property_invoices.all().order_by('-issue_date')
    
    context = {
        'property': property,
        'lease_form': lease_form,
        'bank_form': bank_form,
        'unit_form': PropertyUnitForm(),
        'has_active_accounts': active_accounts.exists(),
        'images': images,
        'lease_agreements': lease_agreements,
        'maintenance_requests': maintenance_requests,
        'invoices': invoices,  # Add invoices to context
    }
    return render(request, 'properties/property_detail.html', context)


@login_required
def property_create(request):
    if request.method == 'POST':
        form = PropertyForm(request.POST)
        if form.is_valid():
            property = form.save(commit=False)
            property.owner = request.user.propertyowner
            property.save()
            if property.pk ==1:
                return redirect('properties:unit_create', 1)
            else:
                return redirect('properties:unit_create', pk=property.pk)
    else:
        form = PropertyForm()
    
    return render(request, 'properties/property_form.html', {
        'form': form
    })

@login_required
def property_unit(request, property_pk):
    property = get_object_or_404(Property, property_pk)
    if request.method == 'POST':
        form = Property_unit(request.POST)
        
        if form.is_valid():
            property = form.save(commit=False)
            property.owner = PropertyOwner.objects.get(user=request.user)
            property.save()
            
            
            messages.success(request, 'Property listed successfully!')

            return redirect('properties:property_detail', pk = property.pk)
    else:
        form = PropertyForm()
    return render(request, 'properties/property_unit.html', {'property': property})

@login_required
def lease_agreement_create(request, property_pk):
    property = get_object_or_404(Property, pk=property_pk)
    
    # Check if user is property owner
    if request.user != property.owner.user:
        return HttpResponseForbidden("Only property owner can create lease agreements.")
    
    # Get unit if specified, otherwise None
    unit_pk = request.GET.get('unit')
    unit = get_object_or_404(PropertyUnit, pk=unit_pk, property=property) if unit_pk else None
    
    # Get active bank accounts
    active_accounts = property.bank_accounts.filter(status='Active')
    
    if request.method == 'POST':
        form = LeaseAgreementForm(request.POST, request.FILES, property=property)
        if form.is_valid():
            lease = form.save(commit=False)
            lease.property = property
            lease.status = 'pending'
            
            # Mark the unit as occupied and save both lease and unit
            with transaction.atomic():
                lease.save()
                if lease.property_unit:
                    lease.property_unit.is_available = False
                    lease.property_unit.save()
            
            # Create notification for tenant
            create_notification(
                recipient=lease.tenant.user,
                notification_type='lease_update',
                title='New Lease Agreement',
                message=f'A new lease agreement has been created for {property.id}.',
                related_object=lease
            )
            
            # Create notification for property owner
            create_notification(
                recipient=property.owner.user,
                notification_type='lease_update',
                title='New Lease Agreement Created',
                message=f'New lease agreement created for {lease.tenant.user.get_full_name()} at {property.id}.',
                related_object=lease
            )
            
            messages.success(request, 'Lease agreement created successfully!')
            return redirect('properties:property_detail', pk=property.pk)
    else:
        initial = {}
        if unit:
            initial['property_unit'] = unit
            initial['monthly_rent'] = unit.monthly_rent
        if active_accounts.exists():
            initial['bank_account'] = active_accounts.first()
            
        form = LeaseAgreementForm(initial=initial, property=property)
    
    return render(request, 'properties/lease_agreement_form.html', {
        'form': form,
        'property': property,
        'unit': unit,
        'has_active_accounts': active_accounts.exists()
    })

@login_required
def lease_agreement_update(request, pk):
    lease = get_object_or_404(LeaseAgreement, pk=pk)
    
    # Check if user is property owner
    if request.user != lease.property.owner.user:
        return HttpResponseForbidden("Only property owner can update lease agreements.")
    
    if request.method == 'POST':
        form = LeaseAgreementForm(request.POST, request.FILES, instance=lease)
        if form.is_valid():
            lease = form.save()
            
            # Create notification for tenant
            create_notification(
                recipient=lease.tenant.user,
                notification_type='lease_update',
                title='Lease Agreement Updated',
                message=f'Your lease agreement for {lease.property.name} has been updated.',
                related_object=lease
            )
            
            # Create notification for property owner
            create_notification(
                recipient=lease.property.owner.user,
                notification_type='lease_update',
                title='Lease Agreement Updated',
                message=f'Lease agreement for {lease.tenant.user.get_full_name()} at {lease.property.name} has been updated.',
                related_object=lease
            )
            
            messages.success(request, 'Lease agreement updated successfully!')
            return redirect('properties:property_detail', pk=lease.property.pk)
    
    # Rest of your view logic here

@login_required
def maintenance_request_create(request, property_pk):
    property = get_object_or_404(Property, pk=property_pk)
    
    if request.method == 'POST':
        form = PropertyMaintenanceForm(request.POST)
        if form.is_valid():
            maintenance = form.save(commit=False)
            maintenance.property = property
            maintenance.reported_by = request.user
            maintenance.save()
            messages.success(request, 'Maintenance request submitted successfully!')
            return redirect('property_detail', pk=property_pk)
    else:
        form = PropertyMaintenanceForm()
    
    return render(request, 'properties/maintenance_form.html', {
        'form': form,
        'property': property
    })

@login_required
def maintenance_request_list(request):
    if request.user.is_property_owner():
        maintenance_requests = PropertyMaintenance.objects.filter(
            property__owner__user=request.user
        ).order_by('-reported_date')
    elif request.user.is_tenant():
        maintenance_requests = PropertyMaintenance.objects.filter(
            reported_by=request.user
        ).order_by('-reported_date')
    else:
        maintenance_requests = PropertyMaintenance.objects.all().order_by('-reported_date')
    
    return render(request, 'properties/maintenance_list.html', {
        'maintenance_requests': maintenance_requests
    })
@login_required
def lease_list(request):
    if request.user.is_property_owner():
        leases = LeaseAgreement.objects.filter(
            property__owner__user=request.user
        ).order_by('-start_date')
    elif request.user.is_tenant():
        leases = LeaseAgreement.objects.filter(
            tenant__user=request.user
        ).order_by('-start_date')
    else:
        leases = LeaseAgreement.objects.all().order_by('-start_date')
    
    return render(request, 'properties/lease_list.html', {
        'leases': leases
    })

@login_required
def unit_create(request, property_pk):
    property = get_object_or_404(Property, pk=property_pk)
    
    # Check if user is the property owner
    if not request.user.is_property_owner() or property.owner.user != request.user:
        messages.error(request, "You don't have permission to add units to this property.")
        return redirect('properties:property_detail', pk=property_pk)
    
    if request.method == 'POST':
        form = PropertyUnitForm(request.POST)
        if form.is_valid():
            unit = form.save(commit=False)
            unit.property = property
            unit.save()
            messages.success(request, 'Property unit created successfully.')
            return redirect('properties:property_detail', pk=property_pk)
    else:
        form = PropertyUnitForm()
    
    return render(request, 'properties/unit_form.html', {
        'form': form,
        'property': property,
        'action': 'Create'
    })

@login_required
def unit_update(request, unit_pk):
    unit = get_object_or_404(PropertyUnit, pk=unit_pk)
    if request.method == 'POST':
        form = PropertyUnitForm(request.POST, instance=unit)
        if form.is_valid():
            form.save()
            messages.success(request, 'Unit updated successfully!')
            return redirect('properties:property_detail', pk=unit.property.pk)
    else:
        form = PropertyUnitForm(instance=unit)
    
    return render(request, 'properties/unit_form.html', {
        'form': form,
        'property': unit.property
    })

@login_required
def unit_delete(request, unit_pk):
    unit = get_object_or_404(PropertyUnit, pk=unit_pk)
    property = unit.property
    
    # Check if user is the property owner
    if not request.user.is_property_owner or property.owner.user != request.user:
        messages.error(request, 'You do not have permission to delete this unit.')
        return redirect('properties:property_detail', pk=property.id)
    
    try:
        unit.delete()
        messages.success(request, 'Property unit deleted successfully.')
    except Exception as e:
        messages.error(request, f'Error deleting unit: {str(e)}')
    
    return redirect('properties:property_detail', pk=property.id)

@login_required
def bank_account_create(request, property_pk):
    property = get_object_or_404(Property, pk=property_pk)
    
    if request.method == 'POST':
        form = BankAccountForm(request.POST)
        if form.is_valid():
            account = form.save(commit=False)
            account.property = property
            account.created_by = request.user
            account.save()
            messages.success(request, 'Payment account created successfully!')
            return redirect('properties:property_detail', pk=property.pk)
    else:
        form = BankAccountForm(initial={'property': property})
    
    return render(request, 'properties/bank_account_form.html', {
        'form': form,
        'property': property
    })

@login_required 
def bank_account_delete(request, account_id):
    try:
        account = BankAccount.objects.get(id=account_id)
        # Check if the user is the property owner
        if request.user.is_property_owner and account.property.owner.user == request.user:
            account.delete()
            return JsonResponse({'status': 'success', 'message': 'Bank account deleted successfully'})
        else:
            return JsonResponse({'status': 'error', 'message': 'Permission denied'}, status=403)
    except BankAccount.DoesNotExist:
        return JsonResponse({'status': 'error', 'message': 'Bank account not found'}, status=404)

@login_required
def lease_status_change(request, property_pk, pk):
    """Change lease agreement status"""
    try:
        property = get_object_or_404(Property, pk=property_pk)
        lease = get_object_or_404(LeaseAgreement, pk=pk, property=property)
        
        if request.user != property.owner.user:
            return JsonResponse({'error': 'Unauthorized'}, status=403)
        
        data = json.loads(request.body)
        new_status = data.get('status')
        
        if new_status not in dict(LeaseAgreement.STATUS_CHOICES):
            return JsonResponse({'error': 'Invalid status'}, status=400)
        
        lease.status = new_status
        lease.save()
        
        # Create notification for tenant
        create_notification(
            recipient=lease.tenant.user,
            notification_type='lease_update',
            title='Lease Agreement Status Updated',
            message=f'The status of your lease agreement for {property.id} has been updated to {new_status}.',
            related_object=lease
        )
        
        # Create notification for property owner
        create_notification(
            recipient=property.owner.user,
            notification_type='lease_update',
            title='Lease Agreement Status Updated',
            message=f'The status of the lease agreement for {lease.tenant.user.get_full_name()} at {property.id} has been updated to {new_status}.',
            related_object=lease
        )
        
        return JsonResponse({'status': 'success'})
    except json.JSONDecodeError:
        return JsonResponse({'error': 'Invalid JSON'}, status=400)
    except Exception as e:
        return JsonResponse({'error': str(e)}, status=500)

@login_required
def tenant_make_payment(request, pk):
    try:
        # Get the invoice first
        invoice = get_object_or_404(Invoice, id=pk)
        
        # Validate permissions
        if not request.user.is_tenant or invoice.tenant.user != request.user:
            messages.error(request, "Unauthorized payment attempt")
            return redirect('properties:invoice_detail', pk=pk)

        # Get bank account and validate Stripe configuration
        if not invoice.bank_account or not invoice.bank_account.secret_key:
            messages.error(request, "Payment system is not properly configured for this invoice")
            return redirect('properties:invoice_detail', pk=pk)

        # Use the bank account's Stripe secret key
        stripe.api_key = invoice.bank_account.secret_key

        # Create Stripe session
        try:
            session = stripe.checkout.Session.create(
                payment_method_types=['card', 'us_bank_account'],
                line_items=[{
                    'price_data': {
                        'currency': 'usd',
                        'unit_amount': int(invoice.total_amount * 100),
                        'product_data': {
                            'name': f'Invoice #{invoice.invoice_number}',
                            'description': invoice.description or 'Payment for rental services',
                        },
                    },
                    'quantity': 1,
                }],
                mode='payment',
                success_url=request.build_absolute_uri(
                    reverse('properties:payment_success', kwargs={'pk': invoice.id})
                ),
                cancel_url=request.build_absolute_uri(
                    reverse('properties:invoice_detail', kwargs={'pk': invoice.id})
                ),
                metadata={'invoice_id': invoice.id}
            )

            # Update invoice with Stripe session info
            invoice.stripe_checkout_id = session.id
            invoice.stripe_payment_intent_id = session.payment_intent
            invoice.save()

            # Redirect to Stripe checkout
            return redirect(session.url)

        except stripe.error.StripeError as e:
            logger.error(f'Stripe payment error for invoice {invoice.id}: {str(e)}')
            messages.error(request, f"Payment processing error: {str(e)}")
            return redirect('properties:invoice_detail', pk=pk)

    except Exception as e:
        logger.error(f'Error processing payment: {str(e)}')
        messages.error(request, "An error occurred processing your payment")
        return redirect('properties:invoice_detail', pk=pk)

@login_required
def payment_success(request, pk):
    invoice = get_object_or_404(Invoice, id=pk)
    
    if not request.user.is_tenant or invoice.tenant.user != request.user:
        messages.error(request, "You don't have permission to view this payment.")
        return redirect('properties:invoice_detail', pk=pk)
    
    # Verify payment status with Stripe
    import stripe
    from django.conf import settings
    
    # Use the bank account's Stripe secret key
    stripe.api_key = invoice.bank_account.secret_key
    
    try:
        session = stripe.checkout.Session.retrieve(invoice.stripe_checkout_id)
        if session.payment_status == 'paid':
            # Mark invoice as paid if not already
            if invoice.status != 'paid':
                invoice.stripe_payment_intent_id = session.payment_intent
                owner_invoice = invoice.mark_as_paid()
                messages.success(request, 'Payment successful! Invoice has been marked as paid.')
            else:
                messages.info(request, 'Invoice was already marked as paid.')
        else:
            messages.warning(request, 'Payment is still pending. Please contact support if you think this is an error.')
    except Exception as e:
        messages.error(request, f'Error verifying payment: {str(e)}')
    
    return redirect('properties:invoice_detail', pk=pk)


@csrf_exempt
def stripe_webhook(request):
    webhook_secret = STRIPE_WEBHOOK_SECRET
    payload = request.body
    sig_header = request.META.get('HTTP_STRIPE_SIGNATURE')

    try:
        event = stripe.Webhook.construct_event(
            payload, sig_header, webhook_secret
        )
    except ValueError as e:
        return HttpResponse(status=400)
    except stripe.error.SignatureVerificationError as e:
        return HttpResponse(status=400)

    if event['type'] == 'payment_intent.succeeded':
        intent = event['data']['object']
        payment_id = intent['metadata']['payment_id']
        payment = Payment.objects.get(id=payment_id)
        
        # Update payment status
        payment.status = 'completed'
        payment.payment_date = timezone.now()
        payment.transaction_id = intent['id']
        payment.payment_method = 'stripe'
        payment.save()
        
        # Create payment history
        PaymentHistory.objects.create(
            payment=payment,
            user=payment.paid_by,
            action='COMPLETED',
            description='Payment completed via Stripe'
        )
    
    elif event['type'] == 'payment_intent.payment_failed':
        intent = event['data']['object']
        payment_id = intent['metadata']['payment_id']
        payment = Payment.objects.get(id=payment_id)
        
        # Update payment status
        payment.status = 'failed'
        payment.save()
        
        # Create payment history
        PaymentHistory.objects.create(
            payment=payment,
            user=payment.paid_by,
            action='FAILED',
            description='Payment failed via Stripe'
        )

    return HttpResponse(status=200)


@login_required
def mark_invoice_as_paid(request, pk):
    invoice = get_object_or_404(Invoice, id=pk)
    
    # Only property owner can mark as paid
    if not request.user.is_property_owner or invoice.property.owner.user != request.user:
        messages.error(request, "You don't have permission to update this invoice.")
        return redirect('properties:invoice_detail', pk=invoice.id)
    
    try:
        # Mark invoice as paid and create owner invoice
        owner_invoice = invoice.mark_as_paid()
        messages.success(request, 'Invoice marked as paid and owner invoice created.')
        return redirect('properties:invoice_detail', pk=owner_invoice.id)
    except Exception as e:
        messages.error(request, f'Error marking invoice as paid: {str(e)}')
        return redirect('properties:invoice_detail', pk=invoice.id)

@login_required
def lease_delete(request, property_pk, lease_pk):
    lease = get_object_or_404(LeaseAgreement, pk=lease_pk, property_id=property_pk)
    
    # Check if user is property owner
    if request.user != lease.property.owner.user:
        return HttpResponseForbidden("Only property owner can delete lease agreements.")
    
    if request.method == 'POST':
        # Store the unit for redirection
        property_id = lease.property.id
        # Delete the lease
        lease.delete()
        messages.success(request, 'Lease agreement deleted successfully.')
        return redirect('properties:property_detail', pk=property_id)
    
    return render(request, 'properties/lease_delete_confirm.html', {
        'lease': lease
    })

@login_required
def invoice_list(request):
    """List all invoices for the current user"""
    if request.user.is_property_owner:
        invoices = Invoice.objects.filter(property__owner=request.user.propertyowner)
    elif request.user.is_tenant:
        invoices = Invoice.objects.filter(tenant=request.user.tenant)
    else:
        invoices = Invoice.objects.all()
        
    paginator = Paginator(invoices.order_by('-created_at'), 10)
    page = request.GET.get('page')
    invoices = paginator.get_page(page)
    
    return render(request, 'payments/invoice_list.html', {
        'invoices': invoices
    })

@login_required
def invoice_detail(request, pk):
    """View invoice details"""
    invoice = get_object_or_404(Invoice, pk=pk)
    
    # Check permissions
      
    return render(request, 'properties/invoice_detail.html', {
        'invoice': invoice
    })

@login_required
def invoice_create(request, lease_id):
    """Create a new invoice for a lease agreement"""
    lease = get_object_or_404(LeaseAgreement, id=lease_id)
    
    # Check permissions
    if not request.user.is_superuser and not request.user.is_property_owner:
        return HttpResponseForbidden("You don't have permission to create invoices")
    
    if request.user.is_property_owner and lease.property.owner != request.user.propertyowner:
        return HttpResponseForbidden("You don't have permission to create invoices for this lease")
        
    if request.method == 'POST':
        form = InvoiceForm(request.POST, user=request.user)
        if form.is_valid():
            invoice = form.save(commit=False)
            invoice.lease_agreement = lease
            invoice.property = lease.property
            invoice.property_unit = lease.property_unit
            invoice.tenant = lease.tenant
            invoice.save()
            messages.success(request, 'Invoice created successfully.')
            return redirect('properties:invoice_detail', pk=invoice.pk)
    else:
        initial = {
            'lease_agreement': lease,
            'property_unit': lease.property_unit,
            'tenant': lease.tenant,
            'amount': lease.monthly_rent,
            'due_date': timezone.now() + timedelta(days=30)
        }
        form = InvoiceForm(user=request.user, initial=initial)
    
    return render(request, 'payments/invoice_form.html', {
        'form': form,
        'lease': lease,
        'title': 'Create Invoice'
    })

@login_required
def invoice_update(request, pk):
    """Update an existing invoice"""
    invoice = get_object_or_404(Invoice, pk=pk)
    
    # Check permissions
    if not request.user.is_superuser and not request.user.is_property_owner:
        return HttpResponseForbidden("You don't have permission to update invoices")
        
    if request.user.is_property_owner and invoice.property.owner != request.user.propertyowner:
        return HttpResponseForbidden("You don't have permission to update this invoice")
        
    if request.method == 'POST':
        form = InvoiceForm(request.POST, instance=invoice, user=request.user)
        if form.is_valid():
            form.save()
            messages.success(request, 'Invoice updated successfully.')
            return redirect('properties:invoice_detail', pk=invoice.pk)
    else:
        form = InvoiceForm(instance=invoice, user=request.user)
    
    return render(request, 'payments/invoice_form.html', {
        'form': form,
        'invoice': invoice,
        'title': 'Update Invoice'
    })