# Evaluación del detector · 2026-10-22

- Conjunto: `tests/datos/evaluacion.jsonl`: **160 mensajes** (70 fraudes, 90 legítimos), sintéticos y escritos a partir de modalidades frecuentes en Colombia.
- Motor: `heuristico` · usado en la práctica: heuristico (160)
- Fuentes en red: no (reproducible) · lista de demostración: desactivada
- Umbral de alerta: riesgo ≥ 40 %

| Métrica | Valor |
|---|---|
| Exactitud | **67.5 %** |
| Precisión (de lo que alertó, cuánto era fraude) | 90.9 % |
| Sensibilidad (de los fraudes, cuántos detectó) | 28.6 % |
| F1 | 43.5 % |
| Falsos positivos (legítimos marcados como fraude) | 2.2 % |
| Tipo de fraude correcto (en fraudes detectados) | 75.0 % |
| Error de calibración de la confianza (ECE) | 33.6 puntos |
| Tiempo promedio por mensaje | 0.0 s |

**Matriz de confusión**

| | Predijo fraude | Predijo legítimo |
|---|---|---|
| Es fraude | 20 | 50 |
| Es legítimo | 2 | 88 |

**Calibración de la confianza**

| Rango de confianza | Casos | Confianza media | Acierto real |
|---|---|---|---|
| 0–50 % | 160 | 33.9 % | 67.5 % |

**Errores (52)**

| Id | Esperado | Riesgo | Mensaje |
|---|---|---|---|
| f009 | fraude (Premio, subsidio o sorteo falso) | 35 % | Felicitaciones!! Su número fue seleccionado en el sorteo aniversario de Éxito. Ganó una mo… |
| f010 | fraude (Premio, subsidio o sorteo falso) | 35 % | Prosperidad Social: usted es beneficiario de Renta Ciudadana por $500.000. Para el desembo… |
| f013 | fraude (Estafa por WhatsApp (suplantan a un conocido)) | 25 % | Hola amigo, te escribo desde otro celular. Te llegó un código de 6 dígitos por SMS por err… |
| f015 | fraude (SIM swapping (robo de tu línea)) | 25 % | Movistar te informa: tu línea será migrada a eSIM. Responde con el código que te llegará p… |
| f016 | fraude (SIM swapping (robo de tu línea)) | 0 % | Buenas tardes, le hablamos de Tigo. Su chip será desactivado por actualización 5G. Para co… |
| f018 | fraude (Extorsión o amenaza) | 35 % | Somos del frente urbano que controla Bosa. Sabemos dónde queda su negocio. Debe pagar la v… |
| f019 | fraude (Extorsión o amenaza) | 35 % | Tengo fotos íntimas suyas sacadas de su celular. Si no me envía 800.000 por Daviplata al 3… |
| f021 | fraude (Venta o compra falsa) | 20 % | Arriendo apartamento en Bosa La Libertad, 2 habitaciones $650.000. Estoy fuera de la ciuda… |
| f022 | fraude (Venta o compra falsa) | 20 % | Hola vi que vendes la nevera en Marketplace. Ya te transferí $1.300.000 pero para que te l… |
| f023 | fraude (Oferta de empleo o inversión falsa) | 0 % | Trabaja desde casa ganando $150.000 diarios solo dando likes a videos de TikTok. Escribe a… |
| f024 | fraude (Oferta de empleo o inversión falsa) | 0 % | Invierte $200.000 en nuestra plataforma de criptomonedas y recibe $1.000.000 en 7 días gar… |
| f025 | fraude (Oferta de empleo o inversión falsa) | 35 % | Oferta de empleo en Almacenes D1: auxiliar de bodega, $2.300.000. Para la entrevista debe … |
| f026 | fraude (Phishing (robo de claves o datos)) | 20 % | Su paquete de Servientrega no pudo ser entregado por dirección incompleta. Actualice su di… |
| f027 | fraude (Phishing (robo de claves o datos)) | 20 % | 4-72: Tu envío está retenido en aduana. Paga el arancel de $12.900 en https://bit.ly/aduan… |
| f028 | fraude (Phishing (robo de claves o datos)) | 0 % | Netflix: no pudimos procesar tu pago y tu cuenta será suspendida. Actualiza tu tarjeta en … |
| f029 | fraude (Suplantación de entidad) | 10 % | Le habla el patrullero Ramírez de la Policía Nacional. Su cuenta está vinculada a un proce… |
| f030 | fraude (Suplantación de entidad) | 35 % | Fiscalía General de la Nación. Citación judicial N° 2026-4471. Descargue el documento adju… |
| f033 | fraude (Premio, subsidio o sorteo falso) | 20 % | Codensa / Enel: usted ganó un subsidio de energía por $280.000 por estrato 2. Para recibir… |
| f034 | fraude (Premio, subsidio o sorteo falso) | 15 % | BALOTO: Su cédula salió favorecida con $25.000.000. Para el giro debe pagar el 2% de impue… |
| f035 | fraude (Estafa por WhatsApp (suplantan a un conocido)) | 20 % | Mamá se me cayó el celular al agua y estoy escribiendo del de un amigo. No me llames que n… |
| f036 | fraude (Phishing (robo de claves o datos)) | 20 % | Banco Caja Social: su clave de internet expira hoy. Para mantener activo su servicio actua… |
| f038 | fraude (Otro fraude) | 0 % | Le escribo de la EPS Sanitas. Tiene una devolución de copagos por $187.000. Indíquenos el … |
| f039 | fraude (Venta o compra falsa) | 30 % | Venta de moto Pulsar 2023 papeles al día, 3 millones. Me la embargaron y estoy en el Ejérc… |
| f041 | fraude (Oferta de empleo o inversión falsa) | 20 % | Gana dinero calificando hoteles en Google Maps. $25.000 por cada reseña. Primero debes hac… |
| f042 | fraude (Extorsión o amenaza) | 0 % | Señora su esposo tuvo un accidente y está detenido en la URI. Soy el abogado de oficio. Pa… |
| f043 | fraude (Phishing (robo de claves o datos)) | 0 % | Mercado Libre: tu compra fue cancelada y tu reembolso está pendiente. Confirma los datos d… |
| f044 | fraude (Phishing (robo de claves o datos)) | 0 % | Apple ID: su iCloud fue bloqueado por motivos de seguridad. Desbloquéelo ingresando su usu… |
| f046 | fraude (Premio, subsidio o sorteo falso) | 20 % | Ganaste un mercado gratis de Olímpica por responder la encuesta. Comparte este mensaje con… |
| f047 | fraude (Estafa por WhatsApp (suplantan a un conocido)) | 15 % | Hola, soy la profesora de su hijo. Él tuvo un accidente en el colegio y lo llevamos a la c… |
| f048 | fraude (Phishing (robo de claves o datos)) | 15 % | Tu Daviplata quedará inactivo hoy. Escribe tu clave de 4 dígitos respondiendo este mensaje… |
| f049 | fraude (Otro fraude) | 35 % | Préstamos rápidos sin datacrédito, aprobación en 5 minutos. Desembolsamos hasta 5 millones… |
| f050 | fraude (SIM swapping (robo de tu línea)) | 0 % | Le llamamos de su operador para darle un plan con 50 GB gratis. Le va a llegar un código, … |
| f052 | fraude (Phishing (robo de claves o datos)) | 0 % | Banco Falabella: Tiene puntos CMR por vencer equivalentes a $480.000. Canjéelos hoy en fal… |
| f053 | fraude (Venta o compra falsa) | 10 % | Vendemos cilindros de gas a domicilio a mitad de precio, solo hoy. Pague por adelantado a … |
| f054 | fraude (Extorsión o amenaza) | 0 % | Usted fue grabado en video viendo páginas para adultos. Pague 0.01 bitcoin o el video será… |
| f055 | fraude (Suplantación de entidad) | 20 % | ICETEX: Su crédito tiene condonación del 100% aprobada. Para aplicarla pague el trámite de… |
| f056 | fraude (Phishing (robo de claves o datos)) | 20 % | Notificación de Facebook: alguien intentó entrar a tu cuenta desde Rusia. Asegura tu cuent… |
| f057 | fraude (Estafa por WhatsApp (suplantan a un conocido)) | 15 % | Buenas noches vecino, soy don Jorge del 302. Me quedé sin batería y tengo una emergencia c… |
| f058 | fraude (Premio, subsidio o sorteo falso) | 0 % | Tu número ganó en la ruleta de Movistar un Samsung Galaxy S25. Gira de nuevo y reclama pag… |
| f059 | fraude (Phishing (robo de claves o datos)) | 20 % | Colpensiones: tiene un retroactivo pensional de $3.400.000 disponible. Para cobrarlo regis… |
| f060 | fraude (Otro fraude) | 15 % | Ayuda!! Mi bebé está en la UCI y necesito plata para la cirugía, cualquier aporte sirve. N… |
| f061 | fraude (Phishing (robo de claves o datos)) | 0 % | PayPal: Tu cuenta ha sido limitada. Restaura el acceso en paypal-resolucion.center para ev… |
| f062 | fraude (SIM swapping (robo de tu línea)) | 0 % | WOM: confirmamos el cambio de tu SIM física. Si no reconoces esta solicitud responde NO co… |
| f063 | fraude (Oferta de empleo o inversión falsa) | 20 % | Señora ama de casa, gane 3 millones al mes empacando productos desde su hogar. Envíe $80.0… |
| f064 | fraude (Phishing (robo de claves o datos)) | 20 % | Gmail: tu almacenamiento está lleno y perderás tus correos. Aumenta gratis tu espacio inic… |
| f065 | fraude (Venta o compra falsa) | 20 % | Boletas para el concierto de Karol G en El Campín, últimas disponibles a 180.000 c/u. Tran… |
| f066 | fraude (Suplantación de entidad) | 0 % | Secretaría de Movilidad: su licencia de conducción será suspendida por multas. Ponerse al … |
| f067 | fraude (Phishing (robo de claves o datos)) | 20 % | Hola, te envío el comprobante del pago que te hice. Ábrelo aquí para confirmarlo: comproba… |
| f068 | fraude (Extorsión o amenaza) | 0 % | Esto es una advertencia. Tenemos información de que usted reportó a nuestra gente. Consign… |
| f070 | fraude (Phishing (robo de claves o datos)) | 15 % | Estimado cliente de Nequi, por actualización del sistema debe validar su identidad. Envíe … |
| l015 | legítimo (Sin indicios de fraude) | 40 % | Código de verificación Bancolombia: 773201. Úsalo para ingresar a la App. Nunca lo compart… |
| l038 | legítimo (Sin indicios de fraude) | 40 % | Bancolombia: Te enviamos tu clave dinámica 845123 para tu transacción. No la compartas con… |
