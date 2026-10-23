"""
Orientación a la víctima: tipos de fraude y plan de acción por tipo.

El agente no solo dice "es fraude": le dice a la persona qué hacer ahora, en
orden, con canales oficiales. Los contactos son nacionales y estables (123,
122, CAI Virtual); para bancos y operadores se indica usar la línea oficial
impresa en la tarjeta o en la app, nunca un número que llegue en el mensaje.
"""

CAI_VIRTUAL = "https://caivirtual.policia.gov.co"
FISCALIA = "https://www.fiscalia.gov.co"

TIPOS_FRAUDE: dict[str, str] = {
    "phishing": "Phishing (robo de claves o datos)",
    "malware": "Malware (app o archivo que infecta tu celular)",
    "sim_swapping": "SIM swapping (robo de tu línea)",
    "vishing": "Vishing (estafa por llamada)",
    "estafa_whatsapp": "Estafa por WhatsApp (suplantan a un conocido)",
    "suplantacion_entidad": "Suplantación de entidad",
    "premio_falso": "Premio, subsidio o sorteo falso",
    "compra_falsa": "Venta o compra falsa",
    "extorsion": "Extorsión o amenaza",
    "empleo_falso": "Oferta de empleo o inversión falsa",
    "otro": "Otro fraude",
    "legitimo": "Sin indicios de fraude",
}

# Cómo funciona cada amenaza y qué buscan: para que la persona entienda el engaño, no solo el veredicto
COMO_FUNCIONA: dict[str, str] = {
    "phishing": "Te llevan a una página o formulario falso, idéntico al de tu banco o una entidad, para que "
                "escribas tu usuario, clave o datos de tarjeta. Con eso entran a tu cuenta y sacan la plata.",
    "malware": "Te piden instalar una app o abrir un archivo (.apk, .exe, .zip) que no viene de la tienda oficial, "
               "o una app de control remoto (AnyDesk, TeamViewer). Una vez instalado, pueden ver lo que escribes, "
               "leer tus SMS y códigos y manejar tu celular y tus apps del banco.",
    "sim_swapping": "Buscan que les des un código o tus datos para pasar tu número a otra SIM. Con tu línea "
                    "reciben tus códigos por SMS y recuperan tus cuentas de banco y WhatsApp.",
    "vishing": "Te llaman haciéndose pasar por tu banco, la Policía, la Fiscalía, la DIAN o un familiar. "
               "Usan prisa y miedo ('no cuelgue', 'su cuenta será bloqueada', 'hay un proceso en su contra') "
               "para que dictes un código, entregues claves, instales una app de control remoto o transfieras "
               "a una 'cuenta segura'. La llamada parece urgente y real, pero la entidad nunca pide eso.",
    "estafa_whatsapp": "Se hacen pasar por un familiar o conocido con 'número nuevo' para pedirte plata con "
                       "urgencia, o te piden el código de 6 dígitos para robarte tu WhatsApp.",
    "suplantacion_entidad": "Usan el nombre de un banco, la Policía, la Fiscalía, la DIAN u otra entidad para "
                            "asustarte o ilusionarte y que pagues o entregues datos sin verificar.",
    "premio_falso": "Te anuncian un premio, subsidio o devolución que no existe y te cobran un 'impuesto', "
                    "'envío' o 'trámite' para entregarlo. El premio nunca llega.",
    "compra_falsa": "Ofrecen algo muy barato o fingen ser compradores para que pagues por adelantado o "
                    "entregues códigos. Después desaparecen.",
    "extorsion": "Usan amenazas o miedo (secuestro falso, 'vacuna', fotos íntimas) para que pagues rápido sin "
                 "pensar ni consultar a nadie.",
    "empleo_falso": "Prometen ganancias fáciles o un empleo bien pagado, pero primero te cobran exámenes, "
                    "'recargas' o una inversión que nunca recuperas.",
    "otro": "El mensaje tiene señales típicas de engaño: urgencia, dinero o datos personales de por medio.",
    "legitimo": "No encontramos señales de engaño en el mensaje.",
}

_DENUNCIAR = {
    "titulo": "Denuncia y guarda tu certificado",
    "detalle": "Denuncia en el CAI Virtual de la Policía o en la Fiscalía (línea 122). "
               "Lleva el certificado de este reporte: prueba qué recibiste y cuándo.",
    "enlace": CAI_VIRTUAL,
}
_NO_RESPONDER = {
    "titulo": "No respondas ni abras enlaces",
    "detalle": "No contestes, no llames al número del mensaje y no abras los enlaces. "
               "Bloquea el contacto después de hacer el reporte.",
}
_NO_CODIGOS = {
    "titulo": "Nunca compartas códigos",
    "detalle": "Ninguna entidad te pide claves, el código que llega por SMS ni la clave dinámica. "
               "Si alguien lo pide, es fraude.",
}
_BANCO = {
    "titulo": "Si diste datos o dinero: llama a tu banco ya",
    "detalle": "Usa la línea oficial que aparece al respaldo de tu tarjeta o en la app oficial "
               "(no la del mensaje). Pide bloquear productos y cambia tus claves.",
    "urgente": True,
}
_EMERGENCIA = {
    "titulo": "Si hay amenaza, llama al 123",
    "detalle": "La línea 123 de la Policía atiende extorsión y amenazas las 24 horas. "
               "También está el GAULA (línea 165) para extorsión.",
    "telefono": "123",
    "urgente": True,
}

PLANES: dict[str, list[dict]] = {
    "phishing": [
        _NO_RESPONDER,
        {"titulo": "Si ya ingresaste datos, cambia tus claves",
         "detalle": "Cambia de inmediato la clave del banco, del correo y de las apps donde uses la misma.",
         "urgente": True},
        _BANCO,
        _DENUNCIAR,
    ],
    "malware": [
        {"titulo": "No instales nada ni abras el archivo",
         "detalle": "Las apps de bancos y entidades solo se descargan de Play Store o App Store. Nadie de soporte "
                    "te pide instalar AnyDesk ni TeamViewer, ni dictar el código que aparece.",
         "urgente": True},
        {"titulo": "Si ya lo instalaste: desconecta y desinstala",
         "detalle": "Pon el celular en modo avión, desinstala la app sospechosa (Ajustes > Aplicaciones) y revisa "
                    "en Ajustes > Accesibilidad que ninguna app desconocida tenga permisos.",
         "urgente": True},
        {"titulo": "Cambia tus claves desde otro dispositivo",
         "detalle": "Desde un celular o computador de confianza cambia las claves del banco y del correo. "
                    "Llama a tu banco por la línea oficial y pide revisar movimientos."},
        _DENUNCIAR,
    ],
    "sim_swapping": [
        {"titulo": "Si tu celular se quedó sin señal de repente, actúa ya",
         "detalle": "Desde otro teléfono llama a la línea oficial de tu operador y pide bloquear la SIM "
                    "y cualquier duplicado o portabilidad que no pediste.",
         "urgente": True},
        _BANCO,
        {"titulo": "Activa la clave de la SIM (PIN)",
         "detalle": "Configura el PIN de tu SIM y pide a tu operador que no hagan cambios de SIM sin presencia física.",
         },
        _NO_CODIGOS,
        _DENUNCIAR,
    ],
    "vishing": [
        {"titulo": "Cuelga y no devuelvas la llamada",
         "detalle": "No sigas la conversación ni marques de vuelta al número que te llamó. Si dice ser tu banco "
                    "o una entidad, cuelga y llama tú al número que aparece en la tarjeta, en la app oficial "
                    "o en la página de la entidad.",
         "urgente": True},
        _NO_CODIGOS,
        {"titulo": "No instales apps de control remoto",
         "detalle": "Nadie de soporte, del banco ni de la Policía te pide instalar AnyDesk, TeamViewer ni "
                    "compartir la pantalla. Si ya lo hiciste, activa el modo avión, desinstala la app y "
                    "cambia tus claves desde otro dispositivo.",
         "urgente": True},
        {"titulo": "No transfieras a una 'cuenta segura'",
         "detalle": "Los bancos no tienen cuentas seguras para 'proteger' tu plata ni te piden mover tus "
                    "ahorros por teléfono. Si ya transferiste, llama a tu banco de inmediato y pide el "
                    "bloqueo y la reversión."},
        _BANCO,
        {"titulo": "Reporta el número y guarda el certificado",
         "detalle": "Consulta el número en el panel comunitario y repórtalo aquí. Lleva el certificado a la "
                    "denuncia en el CAI Virtual o en la Fiscalía (línea 122): prueba qué número llamó y qué te dijo.",
         "enlace": CAI_VIRTUAL},
    ],
    "estafa_whatsapp": [
        {"titulo": "Verifica por otro medio",
         "detalle": "Si dice ser un familiar o conocido con número nuevo, llámalo a su número de siempre "
                    "o haz una pregunta que solo esa persona sepa.",
         "urgente": True},
        {"titulo": "No envíes dinero ni códigos",
         "detalle": "Si te piden el código de 6 dígitos de WhatsApp, quieren robar tu cuenta. Activa la "
                    "verificación en dos pasos en WhatsApp > Ajustes > Cuenta."},
        {"titulo": "Avisa a tus contactos",
         "detalle": "Si suplantan a alguien que conoces, avísale para que alerte a su familia."},
        _DENUNCIAR,
    ],
    "suplantacion_entidad": [
        _NO_RESPONDER,
        {"titulo": "Contacta a la entidad por su canal oficial",
         "detalle": "Busca tú mismo la página o línea oficial de la entidad. Las entidades no cobran por "
                    "WhatsApp ni piden consignar a cuentas Nequi o Daviplata personales."},
        _BANCO,
        _DENUNCIAR,
    ],
    "premio_falso": [
        {"titulo": "No pagues para recibir un premio",
         "detalle": "Si te piden un pago por 'impuestos', 'envío' o 'trámite' para entregar un premio o "
                    "subsidio, es fraude. Los subsidios reales no cobran."},
        _NO_RESPONDER,
        _NO_CODIGOS,
        _DENUNCIAR,
    ],
    "compra_falsa": [
        {"titulo": "No pagues por adelantado a desconocidos",
         "detalle": "Prefiere pago contra entrega o plataformas con protección al comprador. "
                    "Desconfía de precios muy por debajo del mercado."},
        {"titulo": "Revisa si la cuenta ya fue reportada",
         "detalle": "Consulta el número de cuenta en el panel comunitario antes de transferir."},
        _BANCO,
        _DENUNCIAR,
    ],
    "extorsion": [
        _EMERGENCIA,
        {"titulo": "No pagues ni negocies",
         "detalle": "Verifica que tu familiar esté bien llamándolo directamente. Los secuestros "
                    "'virtuales' buscan que pagues rápido con miedo."},
        {"titulo": "Guarda todo",
         "detalle": "No borres los mensajes ni las llamadas: son evidencia. Este certificado queda como prueba."},
        _DENUNCIAR,
    ],
    "empleo_falso": [
        {"titulo": "Un empleo real no te cobra",
         "detalle": "Si piden pagar exámenes, uniformes o 'inversión inicial' con ganancias seguras, es fraude."},
        _NO_CODIGOS,
        _DENUNCIAR,
    ],
    "otro": [
        _NO_RESPONDER,
        _NO_CODIGOS,
        _BANCO,
        _DENUNCIAR,
    ],
    "legitimo": [
        {"titulo": "Aun así, verifica antes de actuar",
         "detalle": "No vemos señales graves, pero si te piden dinero o datos, confirma por el canal "
                    "oficial de la entidad o de la persona."},
        _NO_CODIGOS,
    ],
}


def normalizar_tipo(tipo: str | None) -> str:
    tipo = (tipo or "").strip().lower().replace(" ", "_").replace("-", "_")
    return tipo if tipo in TIPOS_FRAUDE else "otro"


def plan_accion(tipo: str, riesgo: int) -> list[dict]:
    """Plan por tipo; si el riesgo es bajo se usa la recomendación preventiva."""
    if riesgo < 40:
        return [dict(p) for p in PLANES["legitimo"]]
    return [dict(p) for p in PLANES.get(normalizar_tipo(tipo), PLANES["otro"])]


def nombre_tipo(tipo: str) -> str:
    return TIPOS_FRAUDE.get(normalizar_tipo(tipo), TIPOS_FRAUDE["otro"])


def como_funciona(tipo: str) -> str:
    return COMO_FUNCIONA.get(normalizar_tipo(tipo), COMO_FUNCIONA["otro"])
