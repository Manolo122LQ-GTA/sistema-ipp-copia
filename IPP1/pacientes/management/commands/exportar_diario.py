import os
from datetime import date
from django.core.management.base import BaseCommand
from django.conf import settings
from openpyxl import Workbook
from pacientes.models import Paciente, SolicitudSecretaria, SolicitudLaboratorio, Poliza


class Command(BaseCommand):
    help = "Exporta gastos y reportes del día a un Excel en /exports/"

    def handle(self, *args, **options):
        export_dir = settings.BASE_DIR / 'exports'
        os.makedirs(export_dir, exist_ok=True)
        hoy = date.today()
        filename = f"reporte_diario_{hoy.strftime('%Y%m%d')}.xlsx"
        filepath = export_dir / filename

        wb = Workbook()

        # Hoja 1: Gastos por Paciente
        ws1 = wb.active
        ws1.title = "Gastos por Paciente"
        ws1.append(["Paciente", "Cédula", "Status", "Categoría", "Saldo Plan Salud"])
        for p in Paciente.objects.all():
            ws1.append([f"{p.nombre} {p.apellido}", p.cedula, p.status_afiliado, p.categoria_afiliado, float(p.saldo_plan_salud)])

        # Hoja 2: Citas Atendidas
        ws2 = wb.create_sheet("Citas Atendidas")
        ws2.append(["Paciente", "Especialista", "Fecha", "Costo", "Cubierto Póliza"])
        for c in SolicitudSecretaria.objects.filter(estado='Atendido').select_related('paciente', 'especialista'):
            esp = c.especialista.get_full_name() or c.especialista.username if c.especialista else ""
            ws2.append([f"{c.paciente.nombre} {c.paciente.apellido}", esp, c.fecha_cita.isoformat(), float(c.costo_consulta), "Sí" if c.cubierto_por_poliza else "No"])

        # Hoja 3: Pólizas activas
        ws3 = wb.create_sheet("Pólizas Activas")
        ws3.append(["Paciente", "Plan", "Inicio", "Vencimiento", "Saldo Restante"])
        for pol in Poliza.objects.filter(estado='Activo').select_related('paciente', 'plan'):
            plan_nombre = pol.plan.nombre if pol.plan else ""
            ws3.append([f"{pol.paciente.nombre} {pol.paciente.apellido}", plan_nombre, pol.fecha_inicio.isoformat(), pol.fecha_vencimiento.isoformat() if pol.fecha_vencimiento else "", float(pol.saldo_restante)])

        wb.save(filepath)
        self.stdout.write(self.style.SUCCESS(f"Reporte exportado: {filepath}"))