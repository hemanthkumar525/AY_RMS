# Generated by Django 4.2.7 on 2025-03-25 15:44

from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):

    dependencies = [
        ('accounts', '0003_notification'),
    ]

    operations = [
        migrations.CreateModel(
            name='Subscription',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('name', models.CharField(max_length=50)),
                ('type', models.CharField(choices=[('basic', 'Basic'), ('premium', 'Premium'), ('enterprise', 'Enterprise')], max_length=20)),
                ('price', models.DecimalField(decimal_places=2, max_digits=10)),
                ('max_properties', models.IntegerField()),
                ('max_units', models.IntegerField()),
                ('description', models.TextField()),
                ('features', models.JSONField()),
                ('is_active', models.BooleanField(default=True)),
                ('created_at', models.DateTimeField(auto_now_add=True)),
                ('updated_at', models.DateTimeField(auto_now=True)),
            ],
        ),
        migrations.AlterField(
            model_name='tenant',
            name='employment_info',
            field=models.TextField(blank=True),
        ),
        migrations.AlterField(
            model_name='tenant',
            name='id_proof',
            field=models.FileField(null=True, upload_to='tenant_docs/'),
        ),
        migrations.CreateModel(
            name='PropertyOwnerSubscription',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('status', models.CharField(choices=[('active', 'Active'), ('expired', 'Expired'), ('cancelled', 'Cancelled')], default='active', max_length=20)),
                ('start_date', models.DateTimeField(auto_now_add=True)),
                ('end_date', models.DateTimeField()),
                ('payment_id', models.CharField(max_length=100)),
                ('auto_renew', models.BooleanField(default=True)),
                ('created_at', models.DateTimeField(auto_now_add=True)),
                ('updated_at', models.DateTimeField(auto_now=True)),
                ('property_owner', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, to='accounts.propertyowner')),
                ('subscription', models.ForeignKey(on_delete=django.db.models.deletion.PROTECT, to='accounts.subscription')),
            ],
            options={
                'ordering': ['-created_at'],
            },
        ),
    ]
