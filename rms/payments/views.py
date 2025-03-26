from django.shortcuts import render, get_object_or_404, redirect
from django.contrib.auth.decorators import login_required
from django.contrib.auth.mixins import LoginRequiredMixin, UserPassesTestMixin
from django.contrib import messages
from django.views.generic import ListView, DetailView, CreateView, UpdateView
from django.urls import reverse_lazy, reverse
from django.http import HttpResponse, JsonResponse
from django.db.models import Sum, Count, Q
from django.utils import timezone
from django.core.paginator import Paginator
from django.template.loader import render_to_string
from django.conf import settings
from django.views.decorators.csrf import csrf_exempt
import csv
import stripe
from rms.settings import *
from io import BytesIO
from datetime import datetime, timedelta

stripe.api_key = STRIPE_SECRET_KEY

from .models import Payment, PaymentDocument, PaymentHistory
from .forms import (
    PaymentForm, 
    PaymentFilterForm, 
    MakePaymentForm, 
    BulkUploadForm,
    PaymentConfirmationForm
)
from properties.models import Property, LeaseAgreement
from accounts.models import CustomUser, PropertyOwner, Tenant

class PaymentListView(LoginRequiredMixin, ListView):
    model = Payment
    template_name = 'payments/payment_list.html'
    context_object_name = 'payments'
    paginate_by = 10

    def get_queryset(self):
        queryset = Payment.objects.all()
        
        # Filter based on user role
        if self.request.user.is_property_owner:
            queryset = queryset.filter(lease__property__owner=self.request.user.propertyowner)
        elif self.request.user.is_tenant:
            queryset = queryset.filter(lease__tenant=self.request.user.tenant)

        # Apply filters from form
        form = PaymentFilterForm(self.request.GET)
        if form.is_valid():
            status = form.cleaned_data.get('status')
            payment_method = form.cleaned_data.get('payment_method')
            start_date = form.cleaned_data.get('start_date')
            end_date = form.cleaned_data.get('end_date')
            property_id = form.cleaned_data.get('property')
            
            if status:
                queryset = queryset.filter(status=status)
            if payment_method:
                queryset = queryset.filter(payment_method=payment_method)
            if start_date:
                queryset = queryset.filter(payment_date__gte=start_date)
            if end_date:
                queryset = queryset.filter(payment_date__lte=end_date)
            if property_id:
                queryset = queryset.filter(lease__property_id=property_id)

        # Apply sorting
        sort = self.request.GET.get('sort', '-payment_date')
        queryset = queryset.order_by(sort)
        
        return queryset

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        queryset = self.get_queryset()
        
        # Add filter form
        context['filter_form'] = PaymentFilterForm(self.request.GET)
        
        # Add summary statistics
        context['total_amount'] = queryset.aggregate(Sum('amount'))['amount__sum'] or 0
        context['pending_count'] = queryset.filter(status='PENDING').count()
        context['completed_count'] = queryset.filter(status='PAID').count()
        
        return context

class PaymentDetailView(LoginRequiredMixin, UserPassesTestMixin, DetailView):
    model = Payment
    template_name = 'payments/payment_detail.html'
    context_object_name = 'payment'

    def test_func(self):
        payment = self.get_object()
        user = self.request.user
        return (user.is_superadmin or 
                (user.is_property_owner and payment.lease.property.owner == user.propertyowner) or
                (user.is_tenant and payment.lease.tenant == user.tenant))

class PaymentCreateView(LoginRequiredMixin, UserPassesTestMixin, CreateView):
    model = Payment
    form_class = PaymentForm
    template_name = 'payments/payment_form.html'
    success_url = reverse_lazy('payments:payment_list')

    def test_func(self):
        return self.request.user.is_superadmin or self.request.user.is_property_owner

    def get_form_kwargs(self):
        kwargs = super().get_form_kwargs()
        kwargs['user'] = self.request.user
        return kwargs

    def form_valid(self, form):
        payment = form.save(commit=False)
        payment.created_by = self.request.user
        payment.save()
        
        # Create payment history
        PaymentHistory.objects.create(
            payment=payment,
            user=self.request.user,
            action='CREATED',
            description='Payment created'
        )
        
        messages.success(self.request, 'Payment created successfully.')
        return super().form_valid(form)

class PaymentUpdateView(LoginRequiredMixin, UserPassesTestMixin, UpdateView):
    model = Payment
    form_class = PaymentForm
    template_name = 'payments/payment_form.html'
    success_url = reverse_lazy('payments:payment_list')

    def test_func(self):
        payment = self.get_object()
        user = self.request.user
        return (user.is_superadmin or 
                (user.is_property_owner and payment.lease.property.owner == user.propertyowner))

    def get_form_kwargs(self):
        kwargs = super().get_form_kwargs()
        kwargs['user'] = self.request.user
        return kwargs

    def form_valid(self, form):
        payment = form.save()
        
        # Create payment history
        PaymentHistory.objects.create(
            payment=payment,
            user=self.request.user,
            action='UPDATED',
            description='Payment details updated'
        )
        
        messages.success(self.request, 'Payment updated successfully.')
        return super().form_valid(form)
@login_required
def create_payment_intent(request, payment_id):
    payment = get_object_or_404(Payment, id=payment_id)

    # Verify tenant authorization
    if not request.user.is_tenant:
        return JsonResponse({'error': 'Unauthorized'}, status=403)

    try:
        intent = stripe.PaymentIntent.create(
            amount=int(payment.amount * 100),
            currency='usd',
            payment_method_types=['card', 'us_bank_account'],
            metadata={
                'payment_id': payment.id,
                'lease_id': payment.lease_agreement.id,
                'tenant_id': request.user.id,
                'property_id': payment.lease_agreement.property.id
                }
                )
        payment.stripe_payment_intent_id = intent.id
        payment.save()
        

        return JsonResponse({
            'clientSecret': intent.client_secret,
            'payment_id': payment.id
        })
    except Exception as e:
        return JsonResponse({'error': str(e)}, status=400)


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
def make_payment(request, lease_id):
    lease = get_object_or_404(LeaseAgreement, id=lease_id)
    
    # Verify that the logged-in user is the tenant
    if not request.user.is_tenant or request.user.tenant != lease.tenant:
        messages.error(request, 'You are not authorized to make payments for this lease.')
        return redirect('payments:payment_list')
    
    # Create a new payment for this lease if it doesn't exist
    payment = Payment.objects.create(
        lease_agreement_id=lease.id,
        due_date=timezone.now(),
        amount=lease.monthly_rent,
        status='PENDING',
        payment_method='STRIPE',
    )
    
    return render(request, 'payments/make_payment.html', {
        'payment': payment,
        'stripe_public_key': STRIPE_PUBLIC_KEY,
        'lease': lease
    })

@login_required
def confirm_payment(request, pk):
    payment = get_object_or_404(Payment, pk=pk)
    
    # Verify that the logged-in user is the property owner
    if not (request.user.is_superadmin or 
            (request.user.is_property_owner and payment.lease.property.owner == request.user.propertyowner)):
        messages.error(request, 'You are not authorized to confirm this payment.')
        return redirect('payments:payment_list')
    
    if request.method == 'POST':
        form = PaymentConfirmationForm(request.POST)
        if form.is_valid():
            payment.status = 'PAID'
            payment.confirmed_at = timezone.now()
            payment.confirmed_by = request.user
            payment.save()
            
            # Create payment history
            PaymentHistory.objects.create(
                payment=payment,
                user=request.user,
                action='CONFIRMED',
                description='Payment confirmed by property owner'
            )
            
            messages.success(request, 'Payment confirmed successfully.')
            return redirect('payments:payment_detail', pk=payment.pk)
    
    return redirect('payments:payment_detail', pk=payment.pk)

@login_required
def payment_receipt(request, pk):
    payment = get_object_or_404(Payment, pk=pk)
    
    # Verify user authorization
    if not (request.user.is_superadmin or 
            request.user.is_property_owner or 
            request.user.tenant == payment.lease.tenant):
        messages.error(request, 'You are not authorized to view this receipt.')
        return redirect('payments:payment_list')
    
    return render(request, 'payments/payment_receipt.html', {
        'payment': payment
    })

@login_required
def bulk_upload_payments(request):
    if not (request.user.is_superadmin or request.user.is_property_owner):
        messages.error(request, 'You are not authorized to perform bulk uploads.')
        return redirect('payments:payment_list')
    
    if request.method == 'POST':
        form = BulkUploadForm(request.POST, request.FILES)
        if form.is_valid():
            file = request.FILES['file']
            property_id = form.cleaned_data['property']
            
            try:
                # Process CSV file
                decoded_file = file.read().decode('utf-8').splitlines()
                reader = csv.DictReader(decoded_file)
                
                success_count = 0
                error_count = 0
                errors = []
                
                for row in reader:
                    try:
                        # Create payment record
                        payment = Payment.objects.create(
                            lease=LeaseAgreement.objects.get(
                                property_id=property_id,
                                tenant__user__email=row['tenant_email']
                            ),
                            amount=float(row['amount']),
                            payment_date=datetime.strptime(row['payment_date'], '%Y-%m-%d'),
                            payment_method=row['payment_method'],
                            status='PENDING',
                            created_by=request.user
                        )
                        success_count += 1
                    except Exception as e:
                        error_count += 1
                        errors.append(f"Row {reader.line_num}: {str(e)}")
                
                messages.success(
                    request,
                    f'Bulk upload completed. {success_count} payments created successfully. '
                    f'{error_count} errors encountered.'
                )
                if errors:
                    messages.warning(request, 'Errors: ' + '; '.join(errors))
                
                return redirect('payments:payment_list')
            
            except Exception as e:
                messages.error(request, f'Error processing file: {str(e)}')
    else:
        form = BulkUploadForm()
    
    return render(request, 'payments/bulk_upload.html', {
        'form': form
    })

@login_required
def export_payments(request, format='csv'):
    if not (request.user.is_superadmin or request.user.is_property_owner):
        messages.error(request, 'You are not authorized to export payments.')
        return redirect('payments:payment_list')
    
    # Get filtered queryset
    queryset = Payment.objects.all()
    if request.user.is_property_owner:
        queryset = queryset.filter(lease__property__owner=request.user.propertyowner)
    
    # Apply filters from URL parameters
    form = PaymentFilterForm(request.GET)
    if form.is_valid():
        if form.cleaned_data.get('status'):
            queryset = queryset.filter(status=form.cleaned_data['status'])
        if form.cleaned_data.get('payment_method'):
            queryset = queryset.filter(payment_method=form.cleaned_data['payment_method'])
        if form.cleaned_data.get('start_date'):
            queryset = queryset.filter(payment_date__gte=form.cleaned_data['start_date'])
        if form.cleaned_data.get('end_date'):
            queryset = queryset.filter(payment_date__lte=form.cleaned_data['end_date'])
    
    # Prepare the response
    if format == 'csv':
        response = HttpResponse(content_type='text/csv')
        response['Content-Disposition'] = 'attachment; filename="payments.csv"'
        
        writer = csv.writer(response)
        writer.writerow([
            'ID', 'Property', 'Tenant', 'Amount', 'Status', 'Payment Method',
            'Payment Date', 'Reference Number', 'Created At'
        ])
        
        for payment in queryset:
            writer.writerow([
                payment.id,
                payment.lease.property.title,
                payment.lease.tenant.user.get_full_name(),
                payment.amount,
                payment.get_status_display(),
                payment.get_payment_method_display(),
                payment.payment_date,
                payment.reference_number,
                payment.created_at
            ])
    
    else:  # Excel format
        output = BytesIO()
        workbook = xlsxwriter.Workbook(output)
        worksheet = workbook.add_worksheet()
        
        # Add headers
        headers = [
            'ID', 'Property', 'Tenant', 'Amount', 'Status', 'Payment Method',
            'Payment Date', 'Reference Number', 'Created At'
        ]
        for col, header in enumerate(headers):
            worksheet.write(0, col, header)
        
        # Add data
        for row, payment in enumerate(queryset, start=1):
            worksheet.write(row, 0, payment.id)
            worksheet.write(row, 1, payment.lease.property.title)
            worksheet.write(row, 2, payment.lease.tenant.user.get_full_name())
            worksheet.write(row, 3, float(payment.amount))
            worksheet.write(row, 4, payment.get_status_display())
            worksheet.write(row, 5, payment.get_payment_method_display())
            worksheet.write(row, 6, payment.payment_date.strftime('%Y-%m-%d'))
            worksheet.write(row, 7, payment.reference_number or '')
            worksheet.write(row, 8, payment.created_at.strftime('%Y-%m-%d %H:%M:%S'))
        
        workbook.close()
        output.seek(0)
        
        response = HttpResponse(
            output.read(),
            content_type='application/vnd.openxmlformats-officedocument.spreadsheetml.sheet'
        )
        response['Content-Disposition'] = 'attachment; filename="payments.xlsx"'
    
    return response

@login_required
def payment_complete(request):
    payment_intent_id = request.GET.get('payment_intent')
    payment_intent_client_secret = request.GET.get('payment_intent_client_secret')
    
    if not payment_intent_id:
        messages.error(request, 'No payment information found.')
        return redirect('payments:payment_list')
    
    try:
        # Retrieve the payment intent from Stripe
        payment_intent = stripe.PaymentIntent.retrieve(payment_intent_id)
        
        # Find the corresponding payment in our database
        payment = Payment.objects.get(stripe_payment_intent_id=payment_intent_id)
        
        if payment_intent.status == 'succeeded':
            # Update payment status
            payment.status = 'completed'
            payment.payment_date = timezone.now()
            payment.transaction_id = payment_intent_id
            payment.payment_method = 'stripe'
            payment.save()
            
            # Create payment history
            PaymentHistory.objects.create(
                payment=payment,
                user=request.user,
                action='COMPLETED',
                description='Payment completed via Stripe'
            )
            
            messages.success(request, 'Payment completed successfully!')
        else:
            messages.error(request, 'Payment was not successful. Please try again.')
            
        return redirect('payments:payment_detail', pk=payment.id)
        
    except stripe.error.StripeError as e:
        messages.error(request, f'Payment error: {str(e)}')
        return redirect('payments:payment_list')
    except Payment.DoesNotExist:
        messages.error(request, 'Payment record not found.')
        return redirect('payments:payment_list')

@login_required
def payment_detail(request, pk):
    # Retrieve the payment object by primary key (id)
    payment = get_object_or_404(Payment, pk=pk)
    
    user = request.user
    
    # Authorization check: user must be a superadmin, property owner, or the tenant who made the payment
    if not (
        user.is_superadmin or 
        (user.is_property_owner and payment.lease.property.owner == user.propertyowner) or
        (user.is_tenant and payment.lease.tenant == user.tenant)
    ):
        messages.error(request, 'You are not authorized to view this payment.')
        return redirect('payments:payment_list')

    # Prepare context data for the template
    context = {
        'payment': payment,
        'lease': payment.amount,
    }

    return render(request, 'payments/payment_detail.html', context)
