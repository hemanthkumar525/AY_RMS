from django.shortcuts import render, redirect, get_object_or_404
from django.forms import inlineformset_factory
import json
from django.http import JsonResponse, HttpResponseNotAllowed, HttpResponseForbidden
from django.contrib.auth.decorators import login_required
from django.contrib import messages
from django.db.models import Q
from django.core.paginator import Paginator
from .models import Property, PropertyUnit, PropertyImage, LeaseAgreement, PropertyMaintenance,BankAccount, Invoice
from .forms import (
    PropertyForm, PropertyImageForm, LeaseAgreementForm,
    PropertyMaintenanceForm, PropertySearchForm, PropertyUnitForm, BankAccountForm, InvoiceForm  # Add this
)
from accounts.models import PropertyOwner, Tenant
from django.db import transaction
from django.utils import timezone

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
    
    context = {
        'property': property,
        'lease_form': lease_form,
        'bank_form': bank_form,
        'unit_form': PropertyUnitForm(),
        'has_active_accounts': active_accounts.exists(),
        'images': images,
        'lease_agreements': lease_agreements,
        'maintenance_requests': maintenance_requests,
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
            # Immediately redirect to unit creation after property save
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
            
            messages.success(request, 'Lease agreement created successfully!')
            return redirect('properties:property_detail', pk=property_pk)
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
def unit_create(request, pk):
    property = get_object_or_404(Property, pk=pk)
    if request.method == 'POST':
        form = PropertyUnitForm(request.POST)
        if form.is_valid():
            unit = form.save(commit=False)
            unit.property = property
            unit.save()
            messages.success(request, 'Unit added successfully!')
            return redirect('properties:property_detail', pk=pk)
    else:
        form = PropertyUnitForm()
    
    return render(request, 'properties/unit_form.html', {
        'form': form,
        'property': property
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
    if not request.user.is_property_owner() or property.owner.user != request.user:
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
def bank_account_delete(request, property_pk, account_pk):
    bank_account = get_object_or_404(BankAccount, pk=account_pk)
    # Add permission check - only owner can delete
    if request.user != bank_account.property.owner.user:
        return HttpResponseForbidden()
    bank_account.delete()
    messages.success(request, 'Bank account deleted')
    return redirect('properties:property_detail', pk=property_pk)



@login_required
def lease_status_change(request, property_pk, lease_pk):
    if request.method != 'POST':
        return HttpResponseNotAllowed(['POST'])
    
    property = get_object_or_404(Property, pk=property_pk)
    lease = get_object_or_404(LeaseAgreement, pk=lease_pk, property=property)
    
    # Check if user is property owner
    if request.user != property.owner.user:
        return HttpResponseForbidden("Only property owner can change lease status.")
    
    try:
        data = json.loads(request.body)
        new_status = data.get('status')
        
        if new_status not in dict(LeaseAgreement.STATUS_CHOICES):
            return JsonResponse({'error': 'Invalid status'}, status=400)
        
        lease.status = new_status
        lease.save()
        
        return JsonResponse({'status': 'success'})
    except json.JSONDecodeError:
        return JsonResponse({'error': 'Invalid JSON'}, status=400)

@login_required
def invoice_list(request):
    if request.user.is_property_owner:
        # Property owners see invoices for their properties
        invoices = Invoice.objects.filter(property__owner__user=request.user).select_related(
            'property', 'tenant__user', 'lease_agreement'
        )
    else:
        # Tenants see their own invoices
        invoices = Invoice.objects.filter(tenant__user=request.user).select_related(
            'property', 'tenant__user', 'lease_agreement'
        )
    
    return render(request, 'properties/invoice_list.html', {'invoices': invoices})

@login_required
def invoice_create(request, lease_id):
    lease = get_object_or_404(LeaseAgreement, id=lease_id)
    
    # Only property owner can create invoices
    if not request.user.is_property_owner or lease.property.owner.user != request.user:
        messages.error(request, "You don't have permission to create invoices.")
        return redirect('properties:property_detail', pk=lease.property.id)
    
    if request.method == 'POST':
        form = InvoiceForm(request.POST)
        if form.is_valid():
            invoice = form.save(commit=False)
            invoice.lease_agreement = lease
            invoice.property = lease.property
            invoice.tenant = lease.tenant
            invoice.save()
            messages.success(request, 'Invoice created successfully.')
            return redirect('properties:invoice_detail', pk=invoice.id)
    else:
        initial = {
            'amount': lease.rent_amount,
            'payment_type': 'rent',
            'due_date': timezone.now().date() + timezone.timedelta(days=30),
        }
        form = InvoiceForm(initial=initial)
    
    return render(request, 'properties/invoice_form.html', {
        'form': form,
        'lease': lease,
        'title': 'Create Invoice'
    })

@login_required
def invoice_detail(request, pk):
    invoice = get_object_or_404(Invoice, id=pk)
    
    # Check permissions
    if not (request.user.is_property_owner and invoice.property.owner.user == request.user) and \
       not (invoice.tenant.user == request.user):
        messages.error(request, "You don't have permission to view this invoice.")
        return redirect('dashboard')
    
    return render(request, 'properties/invoice_detail.html', {'invoice': invoice})

@login_required
def invoice_update(request, pk):
    invoice = get_object_or_404(Invoice, id=pk)
    
    # Only property owner can update invoices
    if not request.user.is_property_owner or invoice.property.owner.user != request.user:
        messages.error(request, "You don't have permission to update this invoice.")
        return redirect('properties:invoice_detail', pk=invoice.id)
    
    if request.method == 'POST':
        form = InvoiceForm(request.POST, instance=invoice)
        if form.is_valid():
            form.save()
            messages.success(request, 'Invoice updated successfully.')
            return redirect('properties:invoice_detail', pk=invoice.id)
    else:
        form = InvoiceForm(instance=invoice)
    
    return render(request, 'properties/invoice_form.html', {
        'form': form,
        'invoice': invoice,
        'title': 'Update Invoice'
    })

@login_required
def mark_invoice_as_paid(request, pk):
    invoice = get_object_or_404(Invoice, id=pk)
    
    # Only property owner can mark as paid
    if not request.user.is_property_owner or invoice.property.owner.user != request.user:
        messages.error(request, "You don't have permission to update this invoice.")
        return redirect('properties:invoice_detail', pk=invoice.id)
    
    invoice.status = 'paid'
    invoice.payment_date = timezone.now().date()
    invoice.save()
    messages.success(request, 'Invoice marked as paid.')
    return redirect('properties:invoice_detail', pk=invoice.id)