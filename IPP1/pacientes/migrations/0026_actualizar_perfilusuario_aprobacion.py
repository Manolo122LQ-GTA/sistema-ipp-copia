import django.db.models.deletion
import django.utils.timezone
from django.conf import settings
from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('pacientes', '0025_perfilusuario'),
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
    ]

    operations = [
        migrations.RemoveField(
            model_name='perfilusuario',
            name='telefono',
        ),
        migrations.RemoveField(
            model_name='perfilusuario',
            name='direccion',
        ),
        migrations.AddField(
            model_name='perfilusuario',
            name='aprobado',
            field=models.BooleanField(default=False),
        ),
        migrations.AddField(
            model_name='perfilusuario',
            name='fecha_registro',
            field=models.DateTimeField(auto_now_add=True, default=django.utils.timezone.now),
            preserve_default=False,
        ),
        migrations.AddField(
            model_name='perfilusuario',
            name='fecha_aprobacion',
            field=models.DateTimeField(blank=True, null=True),
        ),
        migrations.AddField(
            model_name='perfilusuario',
            name='aprobado_por',
            field=models.ForeignKey(
                blank=True,
                null=True,
                on_delete=django.db.models.deletion.SET_NULL,
                related_name='aprobaciones',
                to=settings.AUTH_USER_MODEL,
            ),
        ),
    ]
