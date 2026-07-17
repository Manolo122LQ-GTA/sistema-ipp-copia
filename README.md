# SISTEMA INTEGRADO DE REGISTRO DE PACIENTES IPP-IUTAG
* Un sistema intregado de registro de paciente que ayuda a la comunidad del IPP-IUTAG a optimizar su area de trabajo.
* Version Actual: 1.6_3

# CAMBIOS/ACTUALIZACIONES AL "SIDRP_IPP_IUTAG"
* Se añadio en "Secretaria General" la posibilidad de ver la Poliza y diseversa.
* Se corrigio un error de seguridad que permitia cualquier usuario a ingresar al sistema sin permiso previo del administrador.
* Cambio de gestor de base de datos "Paso de usar PostgreSQL a MYSQL".
* Ahora los registros de los pacientes no se borran sino que se desactivan.
* Se añadio 3 intentos de inicio se sesion antes de un bloqueo de contraseñas, obligando al usuario a recuperar el acceso a traves de la funcion recuperacion.
* Ahora los correos se verifican.
