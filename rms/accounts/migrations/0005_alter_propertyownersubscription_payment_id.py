# Generated by Django 4.2.7 on 2025-03-25 15:50

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('accounts', '0004_subscription_alter_tenant_employment_info_and_more'),
    ]

    operations = [
        migrations.AlterField(
            model_name='propertyownersubscription',
            name='payment_id',
            field=models.CharField(blank=True, max_length=100),
        ),
    ]
