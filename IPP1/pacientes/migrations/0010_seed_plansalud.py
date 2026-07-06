from django.db import migrations


class Migration(migrations.Migration):

    dependencies = [
        ('pacientes', '0009_plansalud_poliza_gastopaciente_familiar'),
    ]

    operations = [
        migrations.RunPython(migrations.RunPython.noop),
    ]
