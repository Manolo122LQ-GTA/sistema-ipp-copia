from django.db import migrations


EXAMENES = [
    ("PYLORISET", 2.50),
    ("FACTOR RH", 2.00),
    ("PRUEBA DE EMBARAZO", 2.50),
    ("TP", 2.50),
    ("TPT", 2.50),
    ("PROTEINA: TOTAL Y FRACCIONADA. ALBUMINA", 6.00),
    ("FOSFATASA", 5.00),
    ("FOSFORO SERICO", 4.00),
    ("CALCIO SERICO", 4.00),
    ("ORINA OCASIONAL", 4.50),
    ("BILIRRUBINA TOTAL Y FRACCIONADA", 7.00),
    ("ELECTROLITOS SERICO (SODICO, CLORO Y POTASIO)", 15.00),
    ("GLICEMIA", 2.00),
    ("COLESTEROL TOTAL", 2.00),
    ("ORINA", 2.00),
    ("HECES", 2.00),
    ("HECES SERIADOS", 6.00),
    ("HEMATOLOGIA COMPLETA", 2.50),
    ("CREATININA", 2.50),
    ("UREA", 2.50),
    ("ACIDO URICO", 2.50),
    ("TRIGLICERIDOS", 2.50),
    ("LDH", 2.50),
    ("TGO", 2.50),
    ("TGP", 2.50),
    ("GLICEMIA POSTPRANDIAL", 3.50),
    ("PERFIL LIPIDICO", 6.00),
    ("VSG", 1.50),
    ("PCR", 5.00),
    ("VDRL", 2.50),
    ("VIH", 3.00),
]


def forwards(apps, schema_editor):
    ExamenLaboratorio = apps.get_model('pacientes', 'ExamenLaboratorio')
    for nombre, costo in EXAMENES:
        ExamenLaboratorio.objects.get_or_create(
            nombre=nombre,
            defaults={'costo': costo, 'activo': True},
        )


def backwards(apps, schema_editor):
    ExamenLaboratorio = apps.get_model('pacientes', 'ExamenLaboratorio')
    nombres_seed = [nombre for nombre, _ in EXAMENES]
    ExamenLaboratorio.objects.filter(nombre__in=nombres_seed).delete()


class Migration(migrations.Migration):

    dependencies = [
        ('pacientes', '0029_examen_laboratorio'),
    ]

    operations = [
        migrations.RunPython(forwards, backwards),
    ]
