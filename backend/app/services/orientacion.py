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
    "sim_swapping": "SIM swapping (robo de tu línea)",
    "estafa_whatsapp": "Estafa por WhatsApp (suplantan a un conocido)",
    "suplantacion_entidad": "Suplantación de entidad",
    "premio_falso": "Premio, subsidio o sorteo falso",
    "compra_falsa": "Venta o compra falsa",
    "extorsion": "Extorsión o amenaza",
    "empleo_falso": "Oferta de empleo o inversión falsa",
    "otro": "Otro fraude",
    "legitimo": "Sin indicios de fraude",
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
