# Generated by Django 3.0.4 on 2020-03-08 16:52

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('chat', '0004_auto_20200307_2231'),
    ]

    operations = [
        migrations.AddField(
            model_name='chatuser',
            name='name',
            field=models.TextField(default='', max_length=50),
        ),
    ]