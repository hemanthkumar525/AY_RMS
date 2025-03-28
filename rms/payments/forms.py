from django import forms
from .models import Payment, Invoice
from properties.models import Property, LeaseAgreement, PropertyUnit, Tenant, BankAccount
from crispy_forms.helper import FormHelper
from crispy_forms.layout import Layout, Row, Column, Submit, Button, Div, HTML


class PaymentForm(forms.ModelForm):
    class Meta:
        model = Payment
        fields = ['lease_agreement', 'payment_type', 'amount', 'due_date', 'payment_method']
        widgets = {
            'due_date': forms.DateInput(attrs={'type': 'date', 'class': 'datepicker'}),
        }

    def __init__(self, *args, **kwargs):
        user = kwargs.pop('user', None)
        super().__init__(*args, **kwargs)
        
        # Filter lease agreements based on user role
        if user and user.is_property_owner:
            self.fields['lease_agreement'].queryset = LeaseAgreement.objects.filter(
                property__owner=user.propertyowner
            )
        
        self.helper = FormHelper()
        self.helper.layout = Layout(
            Row(
                Column('lease_agreement', css_class='form-group col-md-6'),
                Column('payment_type', css_class='form-group col-md-6'),
            ),
            Row(
                Column('amount', css_class='form-group col-md-6'),
                Column('due_date', css_class='form-group col-md-6'),
            ),
            Row(
                Column('payment_method', css_class='form-group col-md-12'),
            ),
            Submit('submit', 'Save Payment', css_class='btn btn-primary'),
            Button('cancel', 'Cancel', css_class='btn btn-secondary', onclick='window.history.back()')
        )

class PaymentFilterForm(forms.Form):
    status = forms.ChoiceField(
        choices=[('', 'All Status')] + list(Payment.PAYMENT_STATUS_CHOICES),
        required=False
    )
    payment_method = forms.ChoiceField(
        choices=[
            ('', 'All Methods'),
            ('CARD', 'Credit/Debit Card'),
            ('BANK', 'Bank Transfer'),
            ('CASH', 'Cash'),
            ('CHECK', 'Check'),
        ],
        required=False
    )
    property = forms.ModelChoiceField(
        queryset=Property.objects.all(),
        required=False,
        empty_label="All Properties"
    )
    start_date = forms.DateField(
        required=False,
        widget=forms.DateInput(attrs={'type': 'date', 'class': 'datepicker'})
    )
    end_date = forms.DateField(
        required=False,
        widget=forms.DateInput(attrs={'type': 'date', 'class': 'datepicker'})
    )
    sort = forms.ChoiceField(
        choices=[
            ('-payment_date', 'Latest First'),
            ('payment_date', 'Oldest First'),
            ('amount', 'Amount (Low to High)'),
            ('-amount', 'Amount (High to Low)'),
        ],
        required=False,
        initial='-payment_date'
    )

    def __init__(self, *args, **kwargs):
        user = kwargs.pop('user', None)
        super().__init__(*args, **kwargs)
        
        # Filter properties based on user role
        if user:
            if user.is_property_owner:
                self.fields['property'].queryset = Property.objects.filter(owner=user.propertyowner)
            elif user.is_tenant:
                self.fields['property'].queryset = Property.objects.filter(
                    leaseagreement__tenant=user.tenant
                )

        self.helper = FormHelper()
        self.helper.form_method = 'get'
        self.helper.layout = Layout(
            Row(
                Column('status', css_class='form-group col-md-4'),
                Column('payment_method', css_class='form-group col-md-4'),
                Column('property', css_class='form-group col-md-4'),
            ),
            Row(
                Column('start_date', css_class='form-group col-md-4'),
                Column('end_date', css_class='form-group col-md-4'),
                Column('sort', css_class='form-group col-md-4'),
            ),
        )

    def clean(self):
        cleaned_data = super().clean()
        start_date = cleaned_data.get('start_date')
        end_date = cleaned_data.get('end_date')
        
        if start_date and end_date and start_date > end_date:
            raise forms.ValidationError("End date must be after start date")
        
        return cleaned_data

class MakePaymentForm(forms.Form):
    payment_method = forms.ChoiceField(
        choices=[
            ('CARD', 'Credit/Debit Card'),
            ('BANK', 'Bank Transfer'),
            ('CASH', 'Cash'),
            ('CHECK', 'Check'),
        ],
        widget=forms.RadioSelect
    )
    reference_number = forms.CharField(
        max_length=100,
        required=False,
        help_text="Reference number for bank transfers or check number"
    )
    documents = forms.FileField(
        required=False,
        widget=forms.ClearableFileInput(attrs={'multiple': False}),
        help_text="Upload payment proof (receipts, screenshots, etc.)"
    )

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.helper = FormHelper()
        self.helper.layout = Layout(
            'payment_method',
            'reference_number',
            'documents',
            Submit('submit', 'Submit Payment', css_class='btn btn-primary'),
            Button('cancel', 'Cancel', css_class='btn btn-secondary', onclick='window.history.back()')
        )

class PaymentConfirmationForm(forms.Form):
    confirm = forms.BooleanField(
        required=True,
        label="I confirm that I have received and verified this payment"
    )
    notes = forms.CharField(
        widget=forms.Textarea,
        required=False,
        label="Additional Notes"
    )

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.helper = FormHelper()
        self.helper.layout = Layout(
            'confirm',
            'notes',
            Submit('submit', 'Confirm Payment', css_class='btn btn-success'),
            Button('cancel', 'Cancel', css_class='btn btn-secondary', onclick='window.history.back()')
        )

class BulkUploadForm(forms.Form):
    property = forms.ModelChoiceField(
        queryset=Property.objects.all(),
        help_text="Select the property for which you want to upload payments"
    )
    file = forms.FileField(
        help_text="Upload a CSV file with columns: tenant_email, amount, payment_date, payment_method"
    )

    def __init__(self, *args, **kwargs):
        user = kwargs.pop('user', None)
        super().__init__(*args, **kwargs)
        
        # Filter properties based on user role
        if user and user.is_property_owner:
            self.fields['property'].queryset = Property.objects.filter(owner=user.propertyowner)

        self.helper = FormHelper()
        self.helper.layout = Layout(
            'property',
            'file',
            Submit('submit', 'Upload Payments', css_class='btn btn-primary'),
            Button('cancel', 'Cancel', css_class='btn btn-secondary', onclick='window.history.back()')
        )

    def clean_file(self):
        file = self.cleaned_data['file']
        if not file.name.endswith('.csv'):
            raise forms.ValidationError("Only CSV files are allowed")
        return file

class InvoiceForm(forms.ModelForm):
    class Meta:
        model = Invoice
        fields = [
            'lease_agreement', 'property_unit', 'tenant','invoice_number',
            'amount', 'payment_type', 'description', 
            'due_date', 'late_fee', 'bank_account'
        ]
        widgets = {
            'due_date': forms.DateInput(attrs={'type': 'date', 'class': 'datepicker'}),
            'description': forms.Textarea(attrs={'rows': 3}),
        }

    def __init__(self, *args, **kwargs):
        user = kwargs.pop('user', None)
        super().__init__(*args, **kwargs)
        
        # Filter querysets based on user role
        if user and user.is_property_owner:
            # Get all lease agreements for this property owner
            lease_agreements = LeaseAgreement.objects.filter(
                property__owner=user.propertyowner
            )
            self.fields['lease_agreement'].queryset = lease_agreements
            
            # Get all property units for this property owner
            self.fields['property_unit'].queryset = PropertyUnit.objects.filter(
                property__owner=user.propertyowner
            )
            
            # Get all tenants who have lease agreements with this property owner
            self.fields['tenant'].queryset = Tenant.objects.filter(
                leaseagreement__property__owner=user.propertyowner
            ).distinct()

            # Filter bank accounts
            self.fields['bank_account'].queryset = BankAccount.objects.filter(
                property__owner=user.propertyowner
            )
            
        # Add select2 classes for better dropdown UI
        self.fields['lease_agreement'].widget.attrs['class'] = 'select2'
        self.fields['property_unit'].widget.attrs['class'] = 'select2'
        self.fields['tenant'].widget.attrs['class'] = 'select2'
        self.fields['bank_account'].widget.attrs['class'] = 'select2'
        
        # Add crispy form layout
        self.helper = FormHelper()
        self.helper.layout = Layout(
            Row(
                Column('lease_agreement', css_class='form-group col-md-12'),
            ),
            Row(
                Column('property_unit', css_class='form-group col-md-6'),
                Column('tenant', css_class='form-group col-md-6'),
            ),
            Row(
                Column('amount', css_class='form-group col-md-4'),
                Column('payment_type', css_class='form-group col-md-4'),
                Column('due_date', css_class='form-group col-md-4'),
            ),
            Row(
                Column('late_fee', css_class='form-group col-md-6'),
                Column('bank_account', css_class='form-group col-md-6'),
            ),
            'description',
            Submit('submit', 'Save Invoice', css_class='btn btn-primary'),
            Button('cancel', 'Cancel', css_class='btn btn-secondary', onclick='window.history.back()')
        )

    def clean(self):
        cleaned_data = super().clean()
        lease_agreement = cleaned_data.get('lease_agreement')
        property_unit = cleaned_data.get('property_unit')
        tenant = cleaned_data.get('tenant')

        if lease_agreement:
            # Ensure property unit and tenant match lease agreement
            if property_unit and property_unit != lease_agreement.property_unit:
                raise forms.ValidationError('Property unit must match the lease agreement.')
            if tenant and tenant != lease_agreement.tenant:
                raise forms.ValidationError('Tenant must match the lease agreement.')

        return cleaned_data

class InvoiceFilterForm(forms.Form):
    status = forms.ChoiceField(
        choices=[('', 'All Status')] + list(Invoice.STATUS_CHOICES),
        required=False
    )
    payment_type = forms.ChoiceField(
        choices=[('', 'All Types')] + list(Invoice.PAYMENT_TYPE_CHOICES),
        required=False
    )
    date_from = forms.DateField(
        required=False,
        widget=forms.DateInput(attrs={'type': 'date'})
    )
    date_to = forms.DateField(
        required=False,
        widget=forms.DateInput(attrs={'type': 'date'})
    )
    property = forms.ModelChoiceField(
        queryset=Property.objects.all(),
        required=False,
        empty_label="All Properties"
    )
    tenant = forms.CharField(
        required=False,
        widget=forms.TextInput(attrs={'placeholder': 'Search by tenant name'})
    )

    def __init__(self, *args, **kwargs):
        user = kwargs.pop('user', None)
        super().__init__(*args, **kwargs)
        
        if user and user.is_property_owner:
            self.fields['property'].queryset = Property.objects.filter(owner=user.propertyowner)
        
        self.helper = FormHelper()
        self.helper.form_method = 'get'
        self.helper.layout = Layout(
            Row(
                Column('status', css_class='form-group col-md-6'),
                Column('payment_type', css_class='form-group col-md-6'),
            ),
            Row(
                Column('date_from', css_class='form-group col-md-6'),
                Column('date_to', css_class='form-group col-md-6'),
            ),
            Row(
                Column('property', css_class='form-group col-md-6'),
                Column('tenant', css_class='form-group col-md-6'),
            ),
            Submit('submit', 'Filter', css_class='btn btn-primary'),
            Button('reset', 'Reset', css_class='btn btn-secondary', onclick='window.location.href=window.location.pathname')
        )
