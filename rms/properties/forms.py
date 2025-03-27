from django import forms
from django.contrib.auth.models import AbstractUser
from django.contrib.auth.forms import UserCreationForm, UserChangeForm
from crispy_forms.helper import FormHelper
from crispy_forms.layout import Layout, Row, Column
from .models import *

class PropertyForm(forms.ModelForm):
    class Meta:
        model = Property
        fields = ['title', 'property_type', 'address', 'city', 'is_available',
                'state', 'postal_code', 'description']
        widgets = {
            'description': forms.Textarea(attrs={'rows': 3}),
            'address': forms.Textarea(attrs={'rows': 2}),
            'monthly_rent': forms.NumberInput(attrs={'min': 0, 'step': '0.01'}),
            'square_feet': forms.NumberInput(attrs={'min': 0}),
            'bedrooms': forms.NumberInput(attrs={'min': 0}),
            'bathrooms': forms.NumberInput(attrs={'min': 0, 'step': '0.5'}),
            'is_available': forms.CheckboxInput(attrs={'class': 'form-check-input'})
        }
        
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.helper = FormHelper()
        self.helper.form_tag = False
        self.helper.layout = Layout(
            Row(
                Column('title', css_class='col-md-8'),
                Column('property_type', css_class='col-md-4'),
            ),
            Row(
                Column('address', css_class='col-md-12'),
                
                Column('is_available,')
            ),
            Row(
                Column('city', css_class='col-md-4'),
                Column('state', css_class='col-md-4'),
                Column('postal_code', css_class='col-md-4'),
            ),
            
            
            'description',
        )
        
        for field in self.fields.values():
            field.widget.attrs['class'] = 'form-control'
            
        # Add help text
        
class PropertyImageForm(forms.ModelForm):
    image = forms.ImageField(
        widget=forms.ClearableFileInput(attrs={'multiple': False}),
        required=False,
        help_text='You can upload multiple images. Supported formats: JPG, PNG'
    )
    
    class Meta:
        model = PropertyImage
        fields = ['image']
        
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.helper = FormHelper()
        self.helper.form_tag = False
        for field in self.fields.values():
            field.widget.attrs['class'] = 'form-control'

class PropertyUnitForm(forms.ModelForm):
    class Meta:
        model = PropertyUnit
        fields = ['unit_number', 'monthly_rent', 
                 'bedrooms', 'bathrooms', 'square_feet', 'is_available']
        widgets = {
            'bathrooms': forms.NumberInput(attrs={'min': 0, 'step': '0.5'}),
            'monthly_rent': forms.NumberInput(attrs={'min': 0}),
        }

class LeaseAgreementForm(forms.ModelForm):
    bank_account = forms.ModelChoiceField(
        queryset=BankAccount.objects.none(),
        required=True,
        widget=forms.Select(attrs={'class': 'form-control'})
    )

    class Meta:
        model = LeaseAgreement
        fields = ['tenant', 'start_date', 'end_date', 'monthly_rent', 'property_unit','rent_due_day',
                 'security_deposit', 'bank_account']

    def __init__(self, *args, **kwargs):
        # Extract property from kwargs before calling super()
        self.property = kwargs.pop('property', None)
        super().__init__(*args, **kwargs)
        
        # Filter bank accounts based on property
        if self.property:
            self.fields['bank_account'].queryset = self.property.bank_accounts.filter(status='Active')
        
        # Set default form field classes
        for field in self.fields.values():
            if not isinstance(field.widget, forms.DateInput):
                field.widget.attrs['class'] = 'form-control'
    
    def clean(self):
        cleaned_data = super().clean()
        property = getattr(self, 'property', None)
        
        if property and not cleaned_data.get('bank_account'):
            if property.bank_accounts.filter(status='Active').exists():
                raise forms.ValidationError(
                    "Please select a payment account for this lease."
                )
            else:
                raise forms.ValidationError(
                    "No active payment accounts available. Please create one first."
                )
        return cleaned_data
            


class PropertyMaintenanceForm(forms.ModelForm):
    class Meta:
        model = PropertyMaintenance
        fields = ['title', 'description', 'priority']
        widgets = {
            'description': forms.Textarea(attrs={'rows': 3}),
        }
        
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        for field in self.fields.values():
            field.widget.attrs['class'] = 'form-control'

class PropertySearchForm(forms.Form):
    PRICE_CHOICES = [
        ('', 'Any Price'),
        ('0-1000', 'Under $1,000'),
        ('1000-2000', '$1,000 - $2,000'),
        ('2000-3000', '$2,000 - $3,000'),
        ('3000-4000', '$3,000 - $4,000'),
        ('4000-5000', '$4,000 - $5,000'),
        ('5000+', '$5,000+')
    ]
    
    keyword = forms.CharField(required=False, widget=forms.TextInput(
        attrs={'class': 'form-control', 'placeholder': 'Search by keyword...'}
    ))
    property_type = forms.ChoiceField(
        choices=[('', 'All Types')] + list(Property.PROPERTY_TYPE_CHOICES),
        required=False,
        widget=forms.Select(attrs={'class': 'form-control'})
    )
    city = forms.CharField(required=False, widget=forms.TextInput(
        attrs={'class': 'form-control', 'placeholder': 'City'}
    ))
    price_range = forms.ChoiceField(
        choices=PRICE_CHOICES,
        required=False,
        widget=forms.Select(attrs={'class': 'form-control'})
    )
    bedrooms = forms.ChoiceField(
        choices=[('', 'Any')] + [(i, i) for i in range(1, 6)] + [(6, '6+')],
        required=False,
        widget=forms.Select(attrs={'class': 'form-control'})
    )


class BankAccountForm(forms.ModelForm):
    class Meta:
        model = BankAccount
        fields = ['title', 'account_type', 'status', 'account_mode', 'client_id', 'secret_key']
        widgets = {
            'title': forms.TextInput(attrs={
                'class': 'form-control',
                'placeholder': 'Enter title'
            }),
            'account_type': forms.Select(attrs={
                'class': 'form-control'
            }),
            'status': forms.Select(attrs={
                'class': 'form-control'
            }),
            'account_mode': forms.RadioSelect(),
            'client_id': forms.TextInput(attrs={
                'class': 'form-control',
                'placeholder': 'Enter client id'
            }),
            'secret_key': forms.PasswordInput(attrs={
                'class': 'form-control',
                'placeholder': 'Enter secret key'
            }, render_value=True),
        }

    def __init__(self, *args, **kwargs):
        self.property = kwargs.pop('property', None)
        super().__init__(*args, **kwargs)
        
        # Set default form field classes
        for field in self.fields.values():
            if not isinstance(field.widget, forms.RadioSelect):
                field.widget.attrs['class'] = 'form-control'
        
        # Set choices for account type based on property settings
        if self.property:
            self.fields['account_type'].choices = [
                ('stripe', 'Stripe'),
                ('paypal', 'PayPal'),
                ('razorpay', 'Razorpay')
            ]
