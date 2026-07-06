from django.db import migrations


def replace_plans(apps, schema_editor):
    PlanSalud = apps.get_model('pacientes', 'PlanSalud')
    PlanSalud.objects.all().delete()
    PlanSalud.objects.create(
        nombre='Plan de Salud',
        descripcion='Cobertura general de salud para afiliados.',
        costo_mensual=50.00,
    )


class Migration(migrations.Migration):

    dependencies = [
        ('pacientes', '0010_seed_plansalud'),
    ]

    operations = [
        migrations.RunPython(replace_plans),
    ]