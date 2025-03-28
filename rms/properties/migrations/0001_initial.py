# Generated by Django 4.2.7 on 2025-03-14 11:34

from django.conf import settings
from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):

    initial = True

    dependencies = [
        ('accounts', '0001_initial'),
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
    ]

    operations = [
        migrations.CreateModel(
            name='Property',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('title', models.CharField(max_length=200)),
                ('property_type', models.CharField(choices=[('apartment', 'Apartment'), ('house', 'House'), ('commercial', 'Commercial'), ('office', 'Office Space')], max_length=20)),
                ('address', models.TextField()),
                ('city', models.CharField(max_length=100)),
                ('state', models.CharField(max_length=100)),
                ('postal_code', models.CharField(max_length=10)),
                ('monthly_rent', models.DecimalField(decimal_places=2, max_digits=10)),
                ('bedrooms', models.IntegerField(default=1)),
                ('bathrooms', models.DecimalField(decimal_places=1, default=1, max_digits=3)),
                ('square_feet', models.IntegerField()),
                ('description', models.TextField()),
                ('is_available', models.BooleanField(default=True)),
                ('created_at', models.DateTimeField(auto_now_add=True)),
                ('updated_at', models.DateTimeField(auto_now=True)),
                ('owner', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, to='accounts.propertyowner')),
            ],
        ),
        migrations.CreateModel(
            name='PropertyMaintenance',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('title', models.CharField(max_length=200)),
                ('description', models.TextField()),
                ('status', models.CharField(choices=[('pending', 'Pending'), ('in_progress', 'In Progress'), ('completed', 'Completed'), ('cancelled', 'Cancelled')], default='pending', max_length=20)),
                ('priority', models.CharField(choices=[('low', 'Low'), ('medium', 'Medium'), ('high', 'High')], max_length=20)),
                ('reported_date', models.DateTimeField(auto_now_add=True)),
                ('resolved_date', models.DateTimeField(blank=True, null=True)),
                ('property', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, to='properties.property')),
                ('reported_by', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, to=settings.AUTH_USER_MODEL)),
            ],
        ),
        migrations.CreateModel(
            name='PropertyImage',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('image', models.ImageField(upload_to='property_images/')),
                ('caption', models.CharField(blank=True, max_length=200)),
                ('property', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name='images', to='properties.property')),
            ],
        ),
        migrations.CreateModel(
            name='LeaseAgreement',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('start_date', models.DateField()),
                ('end_date', models.DateField()),
                ('monthly_rent', models.DecimalField(decimal_places=2, max_digits=10)),
                ('security_deposit', models.DecimalField(decimal_places=2, max_digits=10)),
                ('status', models.CharField(choices=[('pending', 'Pending'), ('active', 'Active'), ('terminated', 'Terminated'), ('expired', 'Expired')], default='pending', max_length=20)),
                ('terms_and_conditions', models.TextField()),
                ('signed_by_tenant', models.BooleanField(default=False)),
                ('signed_by_owner', models.BooleanField(default=False)),
                ('document', models.FileField(blank=True, null=True, upload_to='lease_documents/')),
                ('created_at', models.DateTimeField(auto_now_add=True)),
                ('property', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, to='properties.property')),
                ('tenant', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, to='accounts.tenant')),
            ],
        ),
    ]
