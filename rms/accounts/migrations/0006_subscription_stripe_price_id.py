# Generated by Django 4.2.7 on 2025-03-26 05:05

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('accounts', '0005_alter_propertyownersubscription_payment_id'),
    ]

    operations = [
        migrations.AddField(
            model_name='subscription',
            name='stripe_price_id',
            field=models.CharField(blank=True, max_length=100, null=True, unique=True),
        ),
    ]
