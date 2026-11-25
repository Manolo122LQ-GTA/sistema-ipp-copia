from django.contrib.auth.models import User
from django.db import models
from django.contrib.auth.hashers import make_password, check_password


# ── Catálogo de preguntas de seguridad ──────────────────────────────────────

class PreguntaSeguridad(models.Model):
    """Catálogo canonical de preguntas de seguridad (único por texto)."""
    texto = models.CharField("Texto de la pregunta", max_length=200, unique=True)
    activa = models.BooleanField("Activa", default=True)
    orden = models.IntegerField("Orden de presentación", default=0)

    class Meta:
        verbose_name = "Pregunta de seguridad"
        verbose_name_plural = "Preguntas de seguridad"
        ordering = ['orden', 'texto']

    def __str__(self):
        return self.texto


# ── Respuestas de seguridad por usuario ─────────────────────────────────────

class RespuestaSeguridad(models.Model):
    """Respuesta hashgeada a una pregunta de seguridad, por usuario."""
    usuario = models.ForeignKey(
        User,
        on_delete=models.CASCADE,
        related_name="respuestas_seguridad",
        verbose_name="Usuario",
    )
    pregunta = models.ForeignKey(
        PreguntaSeguridad,
        on_delete=models.PROTECT,
        verbose_name="Pregunta",
    )
    respuesta_hash = models.CharField("Respuesta (hash)", max_length=128)
    creado_en = models.DateTimeField("Creado en", auto_now_add=True)
    actualizado_en = models.DateTimeField("Actualizado en", auto_now=True)

    class Meta:
        verbose_name = "Respuesta de seguridad"
        verbose_name_plural = "Respuestas de seguridad"
        unique_together = ("usuario", "pregunta")
        ordering = ["pregunta__orden"]

    def __str__(self):
        return f"{self.usuario.username} - {self.pregunta.texto}"

    def verificar_respuesta(self, respuesta_texto: str) -> bool:
        """Verifica la respuesta normalizada (strip + casefold)."""
        return check_password(
            respuesta_texto.strip().casefold(),
            self.respuesta_hash,
        )

    @classmethod
    def crear_o_actualizar(cls, usuario, pregunta, respuesta_texto):
        """
        Guarda la respuesta hasheada. Normaliza a strip().casefold() antes de hashear.
        Usa get_or_create para evitar duplicados por usuario+pregunta.
        """
        normalized = respuesta_texto.strip().casefold()
        hash_val = make_password(normalized)
        obj, created = cls.objects.get_or_create(
            usuario=usuario,
            pregunta=pregunta,
            defaults={"respuesta_hash": hash_val},
        )
        if not created:
            # Actualizar si cambió el hash (por si el usuario vuelve a responder)
            obj.respuesta_hash = hash_val
            obj.save(update_fields=["respuesta_hash", "actualizado_en"])
        return obj, created