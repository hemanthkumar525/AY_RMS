from django.shortcuts import render, redirect, get_object_or_404,reverse
from .models import Notification
from django.views.decorators.csrf import csrf_exempt
from django.http import JsonResponse
from django.contrib.auth import login, logout, authenticate
from django.contrib.auth.decorators import login_required
from django.contrib import messages
from django.views.generic import CreateView, UpdateView
from django.urls import reverse_lazy
from .forms import (
    CustomUserCreationForm, PropertyOwnerRegistrationForm,
    TenantRegistrationForm, PropertyOwnerUpdateForm,
    TenantUpdateForm, UserLoginForm
)
from .models import  PropertyOwner, Tenant, Subscription, PropertyOwnerSubscription
from properties.models import LeaseAgreement, Property, TenantProperty
from payments.models import Payment
from django.utils import timezone
from datetime import timedelta
from django.core import signing
from django.conf import settings
import stripe
from django.db import transaction

@login_required
def superadmin_dashboard(request):
    if not request.user.is_superadmin():
        messages.error(request, 'Access denied. Superadmin privileges required.')
        return redirect('accounts:dashboard')
    
    context = {
        'user': request.user,
        'property_owners': PropertyOwner.objects.all(),
        'total_tenants': Tenant.objects.count(),
        'total_lease_agreements': LeaseAgreement.objects.count()
    }
    return render(request, 'accounts/superadmin_dashboard.html', context)

@login_required
def dashboard(request):
    user = request.user
    context = {'user': user}
    
    if user.is_superadmin():
        return redirect('accounts:superadmin_dashboard')

def register_property_owner(request):
    if request.method == 'POST':
        user_form = CustomUserCreationForm(request.POST, request.FILES)
        owner_form = PropertyOwnerRegistrationForm(request.POST)
        if user_form.is_valid() and owner_form.is_valid():
            try:
                user = user_form.save(commit=False)
                user.user_type = 'property_owner'
                user.save()
                owner = owner_form.save(commit=False)
                owner.user = user
                owner.save()
                login(request, user)  # Log the user in
                messages.success(request, 'Registration successful! Please select a subscription plan.')
                return redirect('/payment')
            except Exception as e:
                messages.error(request, f'Registration failed: {str(e)}')
        else:
            for field, errors in user_form.errors.items():
                for error in errors:
                    messages.error(request, f'{field}: {error}')
            for field, errors in owner_form.errors.items():
                for error in errors:
                    messages.error(request, f'{field}: {error}')
    else:
        user_form = CustomUserCreationForm(initial={'user_type': 'property_owner'})
        owner_form = PropertyOwnerRegistrationForm()
    
    return render(request, 'accounts/register_property_owner.html', {
        'user_form': user_form,
        'owner_form': owner_form
    })

def register_tenant(request, property_id):
    # Get the property and verify ownership
    property = get_object_or_404(Property, id=property_id)
    
    # Only allow property owners who own this property
    if not request.user.is_authenticated or not request.user.is_property_owner():
        messages.error(request, 'Only property owners can register tenants.')
        return redirect('accounts:login')
        
    if property.owner.user != request.user:
        messages.error(request, 'You can only register tenants for your own properties.')
        return redirect('properties:property_list')
    
    if request.method == 'POST':
        user_form = CustomUserCreationForm(request.POST, request.FILES)
        tenant_form = TenantRegistrationForm(request.POST, request.FILES)
        
        if user_form.is_valid() and tenant_form.is_valid():
            try:
                with transaction.atomic():
                    # Create user account
                    user = user_form.save(commit=False)
                    user.user_type = 'tenant'
                    user.save()
                    
                    # Create tenant profile
                    tenant = tenant_form.save(commit=False)
                    tenant.user = user
                    tenant.save()
                    
                    # Create tenant-property relationship
                    TenantProperty.objects.create(
                        tenant=tenant,
                        property=property,
                        status='active',  # Automatically active since property owner is creating it
                        start_date=timezone.now()
                    )
                    
                    # Send email to tenant with their credentials
                    # TODO: Implement email notification
                    
                    messages.success(
                        request, 
                        f'Tenant {user.email} has been registered successfully for {property.title}.'
                    )
                    return redirect('properties:property_detail', pk=property_id)
                    
            except Exception as e:
                messages.error(request, f'Error creating tenant account: {str(e)}')
                
        else:
            for field, errors in user_form.errors.items():
                for error in errors:
                    messages.error(request, f'{field}: {error}')
            for field, errors in tenant_form.errors.items():
                for error in errors:
                    messages.error(request, f'{field}: {error}')
    else:
        # Initialize forms with default tenant type
        user_form = CustomUserCreationForm(initial={
            'user_type': 'tenant',
        })
        tenant_form = TenantRegistrationForm()
    
    context = {
        'user_form': user_form,
        'tenant_form': tenant_form,
        'property': property,
        'is_owner_registration': True,
        'page_title': f'Register New Tenant for {property.title}'
    }
    
    return render(request, 'accounts/register_tenant.html', context)

def user_login(request):
    if request.user.is_authenticated:
        return redirect('accounts:dashboard')

    if request.method == 'POST':
        username = request.POST.get('username')
        password = request.POST.get('password')
        user = authenticate(username=username, password=password)
        
        if user is not None:
            login(request, user)
            messages.success(request, 'Login successful!')
            
            # Check if user is a property owner and redirect to subscription
            if hasattr(user, 'Property_owner'):
                return redirect('accounts:payment')
            
            return redirect('accounts:dashboard')
        else:
            messages.error(request, 'Invalid username or password.')
    else:
        form = UserLoginForm()
    
    return render(request, 'accounts/login.html', {'form': form})

@login_required
def user_logout(request):
    logout(request)
    messages.success(request, 'You have been logged out.')
    return redirect('/')

@login_required
def dashboard(request):
    user = request.user
    context = {
        'user': user,
    }
    
    if user.is_superadmin():
        # Superadmin: Show property owners list and system stats
        context['property_owners'] = PropertyOwner.objects.all()
        context['total_tenants'] = Tenant.objects.count()
        context['total_lease_agreements'] = LeaseAgreement.objects.count()
        return render(request, 'accounts/superadmin_dashboard.html', context)
    
    elif user.is_property_owner():
        try:
            owner = PropertyOwner.objects.get(user=user)
            context['owner'] = owner
            context['properties'] = owner.property_set.all()
            context['lease_agreements'] = LeaseAgreement.objects.filter(
                property__owner=owner
            )
            context['total_tenants'] = Tenant.objects.filter(
                leaseagreement__property__owner=owner
            ).distinct().count()
            context['total_payments'] = Payment.objects.filter(
                lease_agreement__property__owner=owner
            ).count()
            context['recent_payments'] = Payment.objects.filter(
                lease_agreement__property__owner=owner
            ).order_by('-created_at')[:5]
        except PropertyOwner.DoesNotExist:
            messages.warning(request, 'Please complete your property owner profile.')
            return redirect('accounts:complete_profile')
        
        return render(request, 'accounts/property_owner_dashboard.html', context)
    
    elif user.is_tenant():
        try:
            tenant = Tenant.objects.get(user=user)
            context['tenant'] = tenant
            context['lease_agreements'] = LeaseAgreement.objects.filter(tenant=tenant)
            context['payments'] = Payment.objects.filter(
                lease_agreement__tenant=tenant
            ).order_by('-due_date')
            context['pending_payments'] = Payment.objects.filter(
                lease_agreement__tenant=tenant,
                status='PENDING'
            ).count()
            context['recent_payments'] = Payment.objects.filter(
                lease_agreement__tenant=tenant
            ).order_by('-created_at')[:5]
        except Tenant.DoesNotExist:
            messages.warning(request, 'Please complete your tenant profile.')
            return redirect('accounts:complete_profile')
        
        return render(request, 'accounts/tenant_dashboard.html', context)
    
    # If user type is not set
    messages.warning(request, 'Please select your user type and complete your profile.')
    return redirect('accounts:select_user_type')


@login_required
def profile(request):
    user = request.user
    if user.is_property_owner():
        owner = PropertyOwner.objects.get(user=user)
        if request.method == 'POST':
            form = PropertyOwnerUpdateForm(request.POST, instance=owner)
            if form.is_valid():
                form.save()
                user.email = form.cleaned_data['email']
                user.first_name = form.cleaned_data['first_name']
                user.last_name = form.cleaned_data['last_name']
                user.save()
                messages.success(request, 'Profile updated successfully!')
                return redirect('profile')
        else:
            form = PropertyOwnerUpdateForm(instance=owner)
        return render(request, 'accounts/profile.html', {'form': form})
    else:
        tenant = Tenant.objects.get(user=user)
        if request.method == 'POST':
            form = TenantUpdateForm(request.POST, instance=tenant)
            if form.is_valid():
                form.save()
                user.email = form.cleaned_data['email']
                user.first_name = form.cleaned_data['first_name']
                user.last_name = form.cleaned_data['last_name']
                user.save()
                messages.success(request, 'Profile updated successfully!')
                return redirect('profile')
        else:
            form = TenantUpdateForm(instance=tenant)
        return render(request, 'accounts/profile.html', {'form': form})

@login_required
def tenant_list(request):
    tenants = Tenant.objects.select_related('user').prefetch_related(
        'leaseagreement_set__property_unit',
        'leaseagreement_set__property'
    ).all()
    return render(request, 'accounts/tenant_list.html', {'tenants': tenants})

def stripe_onfig(request):
    if request.method == 'GET':
        stripe_config = {'publicKey': STRIPE_PUBLISHABLE_KEY}
        return JsonResponse(stripe_config, safe=False)

@login_required
def subscription_view(request):
    if request.method == 'POST':
        price_id = request.POST.get('price_id')
        print(f"Received price_id: {price_id}")  # Debug log
        
        # Create subscription plans if they don't exist
        subscription_plans = {
            'price_1R2FcQKoXpRZrhi2uM1HIlCi': {
                'name': 'Basic',
                'type': 'basic',
                'price': 399.00,
                'price_id': 'price_1R2FcQKoXpRZrhi2uM1HIlCi',
                'max_properties': 1,
                'max_units': 5,
                'description': 'For Individual',
                'features': {'properties': 1, 'units': 5},
            },
            'price_1R2CslKoXpRZrhi2qRVsk82R': {
                'name': 'Standard',
                'type': 'premium',
                'price': 699.00,
                'price_id': 'price_1R2CslKoXpRZrhi2qRVsk82R',
                'max_properties': 5,
                'max_units': 15,
                'description': 'For small businesses',
                'features': {'properties': 5, 'units': 15},
            },
            'price_1R2CtLKoXpRZrhi2vakKxMtM': {
                'name': 'Premium',
                'type': 'enterprise',
                'price': 999.00,
                'price_id': 'price_1R2CtLKoXpRZrhi2vakKxMtM',
                'max_properties': 30,
                'max_units': 999999,
                'description': 'For businesses and teams',
                'features': {'properties': 30, 'units': 'unlimited'},
            }
        }
        
        print(f"Available plans: {list(subscription_plans.keys())}")  # Debug log
        
        # Get or create subscription
        try:
            subscription = Subscription.objects.get(stripe_price_id=price_id)
            print(f"Found existing subscription: {subscription}")  # Debug log
        except Subscription.DoesNotExist:
            print(f"No subscription found for price_id: {price_id}")  # Debug log
            if price_id in subscription_plans:
                plan = subscription_plans[price_id]
                print(f"Creating new subscription with plan: {plan}")  # Debug log
                subscription = Subscription.objects.create(
                    name=plan['name'],
                    type=plan['type'],
                    price=plan['price'],
                    stripe_price_id=price_id,
                    max_properties=plan['max_properties'],
                    max_units=plan['max_units'],
                    description=plan['description'],
                    features=plan['features'],
                    is_active=True
                )
            else:
                print(f"Price ID {price_id} not found in subscription_plans")  # Debug log
                messages.error(request, 'Invalid subscription plan')
                return redirect('accounts:payment')
        
        # Store subscription details in session for later use
        request.session['subscription_id'] = subscription.id
        request.session['subscription_duration'] = 30  # 30 days for monthly plan
        
        try:
            checkout_session = stripe.checkout.Session.create(
                payment_method_types=['card'],
                line_items=[{
                    'price': price_id,
                    'quantity': 1,
                }],
                mode='subscription',
                success_url=request.build_absolute_uri(reverse('accounts:dashboard')) + 
                          f'?session_id={{CHECKOUT_SESSION_ID}}&subscription_id={subscription.id}',
                cancel_url=request.build_absolute_uri(reverse('accounts:payment')),
                client_reference_id=request.user.id,
            )
            return redirect(checkout_session.url)
        except Exception as e:
            print(f"Stripe error: {str(e)}")  # Debug log
            messages.error(request, f'Error: {str(e)}')
            return redirect('accounts:payment')
    
    subscriptions = Subscription.objects.filter(is_active=True)
    if not subscriptions.exists():
        print("Creating default subscriptions")  # Debug log
        # Create default subscriptions if none exist
        Subscription.objects.create(
            name='Basic',
            type='basic',
            price=399.00,
            stripe_price_id='price_1R2FcQKoXpRZrhi2uM1HIlCi',
            max_properties=1,
            max_units=5,
            description='For Individual',
            features={'properties': 1, 'units': 5},
            is_active=True
        )
        Subscription.objects.create(
            name='Standard',
            type='premium',
            price=699.00,
            stripe_price_id='price_1R2CslKoXpRZrhi2qRVsk82R',
            max_properties=5,
            max_units=15,
            description='For small businesses',
            features={'properties': 5, 'units': 15},
            is_active=True
        )
        Subscription.objects.create(
            name='Premium',
            type='enterprise',
            price=999.00,
            stripe_price_id='price_1R2CtLKoXpRZrhi2vakKxMtM',
            max_properties=30,
            max_units=999999,
            description='For businesses and teams',
            features={'properties': 30, 'units': 'unlimited'},
            is_active=True
        )
        subscriptions = Subscription.objects.filter(is_active=True)
        print(f"Created subscriptions: {list(subscriptions)}")  # Debug log
    
    return render(request, 'accounts/subscription.html', {'subscriptions': subscriptions})

@login_required
def payment_successful(request):
    session_id = request.GET.get('session_id')
    subscription_id = request.GET.get('subscription_id')
    print(f"Payment successful - Session ID: {session_id}, Subscription ID: {subscription_id}")  # Debug log
    
    try:
        # Verify the payment session
        session = stripe.checkout.Session.retrieve(session_id)
        print(f"Stripe session status: {session.payment_status}")  # Debug log
        
        if session.payment_status == 'paid':
            # Get the subscription details
            subscription = Subscription.objects.get(id=subscription_id)
            property_owner = PropertyOwner.objects.get(user=request.user)
            print(f"Found subscription: {subscription.name} for property owner: {property_owner}")  # Debug log
            
            # Calculate end date (30 days from now for monthly plan)
            end_date = timezone.now() + timezone.timedelta(days=30)
            
            try:
                # Create or update subscription record
                owner_subscription, created = PropertyOwnerSubscription.objects.update_or_create(
                    property_owner=property_owner,
                    defaults={
                        'subscription': subscription,
                        'status': 'active',
                        'end_date': end_date,
                        'payment_id': session.payment_intent,
                        'auto_renew': True
                    }
                )
                print(f"{'Created' if created else 'Updated'} subscription: {owner_subscription}")  # Debug log
                
                messages.success(request, 'Payment successful! Your subscription is now active.')
                return redirect('accounts:dashboard')
            except Exception as e:
                print(f"Error creating subscription record: {str(e)}")  # Debug log
                raise
        else:
            print(f"Payment not successful: {session.payment_status}")  # Debug log
            messages.error(request, 'Payment was not successful. Please try again.')
            return redirect('accounts:payment')
    except stripe.error.StripeError as e:
        print(f"Stripe error: {str(e)}")  # Debug log
        messages.error(request, f'Error processing payment: {str(e)}')
        return redirect('accounts:payment')
    except (Subscription.DoesNotExist, PropertyOwner.DoesNotExist) as e:
        print(f"Database error: {str(e)}")  # Debug log
        messages.error(request, 'Invalid subscription or property owner.')
        return redirect('accounts:payment')
    except Exception as e:
        print(f"Unexpected error: {str(e)}")  # Debug log
        messages.error(request, f'An error occurred: {str(e)}')
        return redirect('accounts:payment')

@csrf_exempt
def stripe_webhook(request):
    payload = request.body
    sig_header = request.META['HTTP_STRIPE_SIGNATURE']
    endpoint_secret = STRIPE_ENDPOINT_SECRET
    try:
        event = stripe.Webhook.construct_event(payload,sig_header,endpoint_secret)
    except:
        return HttpResponse(status=400)
    
    if event['type'] == 'checkout_session.completed':
        print(event)
        print('payment ws succesful')
    return HttpResponse(status=200 )

def create_subscription(request):
    checkout_session_id = request.GET.get('session_id', None)
    return redirect('my_sub')




def payment_cancelled(request):
    return render(request, 'accounts/cancel.html')

@login_required
def create_notification(request, message):
    notification = Notification(user=request.user, message=message)
    notification.save()
    return redirect('notifications_list')

@login_required
def notifications_list(request):
    notifications = Notification.objects.filter(user=request.user).order_by('-timestamp')
    notifications_data = [
        {
            'id': notification.id,
            'message': notification.message,
            'is_read': notification.is_read,
            'timestamp': notification.timestamp.strftime('%Y-%m-%d %H:%M:%S')
        }
        for notification in notifications
    ]
    return JsonResponse({'notifications': notifications_data})

@login_required
def mark_as_read(request, notification_id):
    notification = Notification.objects.get(id=notification_id, user=request.user)
    notification.is_read = True
    notification.save()
    return redirect('notifications_list')