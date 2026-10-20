import hashlib
from datetime import datetime

def evaluar_fraude(texto: str):
    texto_lower = texto.lower()
    score = 0
    
    if "premio" in texto_lower or "ganador" in texto_lower: score += 40
    if "http" in texto_lower or "link" in texto_lower: score += 30
    if "nequi" in texto_lower or "consign" in texto_lower: score += 20
    
    riesgo = min(score, 100)
    
    # Generar el certificado inmanipulable
    raw_data = f"{texto}{datetime.now().isoformat()}"
    certificado = hashlib.sha256(raw_data.encode()).hexdigest()[:16]
    
    return riesgo, certificado