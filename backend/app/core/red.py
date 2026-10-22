"""Contexto TLS compartido: cargar los certificados raíz cuesta ~0,5 s, así que se hace una sola vez."""
import ssl

import certifi

SSL = ssl.create_default_context(cafile=certifi.where())
