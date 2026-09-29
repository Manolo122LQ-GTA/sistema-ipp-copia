from django.db import migrations


def sembrar_datos(apps, schema_editor):
    PlanSalud = apps.get_model('pacientes', 'PlanSalud')
    ExamenLaboratorio = apps.get_model('pacientes', 'ExamenLaboratorio')
    if not PlanSalud.objects.exists():
        PlanSalud.objects.create(
            nombre='Plan Básico',
            descripcion='Cobertura básica de consultas.',
            costo_mensual='25.00',
            cobertura='Consultas generales',
            consultas_maximas_anuales=4,
        )
    if not ExamenLaboratorio.objects.exists():
        ExamenLaboratorio.objects.create(
            nombre='Hemograma',
            descripcion='Análisis de sangre completo.',
            costo='15.00',
            activo=True,
        )


def retroceder(apps, schema_editor):
    pass


class Migration(migrations.Migration):

    dependencies = [
        ('pacientes', '0003_alter_solicitudsecretaria_unique_together_and_more'),
    ]

    operations = [
        migrations.RunPython(sembrar_datos, retroceder),
    ]