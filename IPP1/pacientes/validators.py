import re
from django.core.exceptions import ValidationError
from django.utils.translation import gettext_lazy as _

class ValidarContrasenaFuerte:
    def validate(self, password, user=None):
        # VALIDAR LA CONTRASEÑA DE MÍNIMO 16 CARACTERES (SIN MÁXIMO)
        if len(password) < 16:
            raise ValidationError(
                _("La contraseña debe tener al menos 16 caracteres."),
                code='password_too_short',
            )

        # VALIDAR QUE TENGA AL MENOS UNA LETRA MINUSCULA
        if not re.search(r'[a-z]', password):
            raise ValidationError(
                _("La contraseña debe contener al menos una letra minúscula."),
                code='no_lowercase',
            )

        # VALIDAR QUE TENGA AL MENOS UNA LETRA MAYÚSCULA
        if not re.search(r'[A-Z]', password):
            raise ValidationError(
                _("La contraseña debe contener al menos una letra mayúscula."),
                code='no_uppercase',
            )

        # VALIDAR QUE TENGA AL MENOS UN NÚMERO
        if not re.search(r'[0-9]', password):
            raise ValidationError(
                _("La contraseña debe contener al menos un número."),
                code='password_no_number',
            )

        # VALIDAR QUE TENGA AL MENOS UN CARÁCTER ESPECIAL
        if not re.search(r'[!@#$%^&*(),.?":{}|<>]', password):
            raise ValidationError(
                _("La contraseña debe contener al menos un carácter especial."),
                code='password_no_special',
            )
        
        # AQUI LA CONTRASEÑA DEBE DE TENER 8 CARACTERES, LETRAS MINUSCULAS, MAYUSCULAS, NUMEROS Y CARACTERES ESPECIAL
    def get_help_text(self):
        return _(
            "La contraseña debe tener al menos 16 caracteres, una letra minúscula, "
            "una letra mayúscula, un número y un carácter especial."
        )