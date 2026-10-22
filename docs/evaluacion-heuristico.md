# Evaluación del detector · 2026-10-22

- Motor: `heuristico` · fuentes en red: no (reproducible) · lista de demostración: desactivada
- Umbral de alerta: riesgo ≥ 40 %
- Mensajes sintéticos, escritos a partir de modalidades frecuentes en Colombia (phishing, malware, SIM swapping, estafas por WhatsApp, extorsión…) y legítimos difíciles (alertas reales de bancos, códigos OTP, familiares pidiendo plata de verdad).

- Conjunto de **desarrollo** (`tests/datos/evaluacion.jsonl`): 169 mensajes (76 fraudes, 93 legítimos), con estos mensajes a la vista se diseñaron las reglas del análisis local: sus cifras son optimistas.
- Conjunto de **prueba** (`tests/datos/evaluacion_prueba.jsonl`): 62 mensajes (32 fraudes, 30 legítimos), escritos aparte y nunca usados para ajustar nada: **la cifra honesta**.

## Conjunto de desarrollo

Motor usado en la práctica: heuristico (169)

| Métrica | Valor |
|---|---|
| Exactitud | **100.0 %** |
| Precisión (de lo que alertó, cuánto era fraude) | 100.0 % |
| Sensibilidad (de los fraudes, cuántos detectó) | 100.0 % |
| F1 | 100.0 % |
| Falsos positivos (legítimos marcados como fraude) | 0.0 % |
| Tipo de amenaza correcto (en fraudes detectados) | 84.2 % |
| Error de calibración de la confianza (ECE) | 65.0 puntos |
| Tiempo promedio por mensaje | 0.0 s |

**Matriz de confusión**

| | Predijo fraude | Predijo legítimo |
|---|---|---|
| Es fraude | 76 | 0 |
| Es legítimo | 0 | 93 |

**Calibración de la confianza**

| Rango de confianza | Casos | Confianza media | Acierto real |
|---|---|---|---|
| 0–50 % | 169 | 35.0 % | 100.0 % |

**Tipo de amenaza distinto al esperado (12)**

| Id | Esperado | Detectado |
|---|---|---|
| f014 | SIM swapping (robo de tu línea) | Phishing (robo de claves o datos) |
| f017 | Extorsión o amenaza | Suplantación de entidad |
| f025 | Oferta de empleo o inversión falsa | Extorsión o amenaza |
| f033 | Premio, subsidio o sorteo falso | Estafa por WhatsApp (suplantan a un conocido) |
| f038 | Otro fraude | Phishing (robo de claves o datos) |
| f040 | Phishing (robo de claves o datos) | Estafa por WhatsApp (suplantan a un conocido) |
| f042 | Extorsión o amenaza | Estafa por WhatsApp (suplantan a un conocido) |
| f048 | Phishing (robo de claves o datos) | Estafa por WhatsApp (suplantan a un conocido) |
| f052 | Phishing (robo de claves o datos) | Premio, subsidio o sorteo falso |
| f055 | Suplantación de entidad | Premio, subsidio o sorteo falso |
| f060 | Otro fraude | Estafa por WhatsApp (suplantan a un conocido) |
| f064 | Phishing (robo de claves o datos) | Premio, subsidio o sorteo falso |

## Conjunto de prueba

Motor usado en la práctica: heuristico (62)

| Métrica | Valor |
|---|---|
| Exactitud | **95.2 %** |
| Precisión (de lo que alertó, cuánto era fraude) | 100.0 % |
| Sensibilidad (de los fraudes, cuántos detectó) | 90.6 % |
| F1 | 95.1 % |
| Falsos positivos (legítimos marcados como fraude) | 0.0 % |
| Tipo de amenaza correcto (en fraudes detectados) | 79.3 % |
| Error de calibración de la confianza (ECE) | 60.9 puntos |
| Tiempo promedio por mensaje | 0.0 s |

**Matriz de confusión**

| | Predijo fraude | Predijo legítimo |
|---|---|---|
| Es fraude | 29 | 3 |
| Es legítimo | 0 | 30 |

**Calibración de la confianza**

| Rango de confianza | Casos | Confianza media | Acierto real |
|---|---|---|---|
| 0–50 % | 62 | 34.3 % | 95.2 % |

**Errores (3)**

| Id | Esperado | Riesgo | Mensaje |
|---|---|---|---|
| pf15 | fraude (Estafa por WhatsApp (suplantan a un conocido)) | 35 % | Hola! Te agregué a un grupo por error y me llegó un código de 6 dígitos a tu número, ¿me l… |
| pf21 | fraude (Premio, subsidio o sorteo falso) | 25 % | Ingreso Solidario 2026: usted fue preseleccionado para recibir $1.000.000. Inscríbase y pa… |
| pf24 | fraude (Extorsión o amenaza) | 35 % | Ya sabemos que usted tiene la tienda en Bosa Recreo. Si no colabora con 300 mil semanales … |

**Tipo de amenaza distinto al esperado (6)**

| Id | Esperado | Detectado |
|---|---|---|
| pf04 | Phishing (robo de claves o datos) | Suplantación de entidad |
| pf05 | Phishing (robo de claves o datos) | Suplantación de entidad |
| pf17 | Suplantación de entidad | Estafa por WhatsApp (suplantan a un conocido) |
| pf19 | Suplantación de entidad | Premio, subsidio o sorteo falso |
| pf29 | Oferta de empleo o inversión falsa | Premio, subsidio o sorteo falso |
| pf32 | Otro fraude | Premio, subsidio o sorteo falso |
