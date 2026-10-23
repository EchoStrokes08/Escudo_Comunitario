import { useEffect, useState } from 'react'
import { Link, useSearchParams } from 'react-router-dom'
import Icono from '../components/Icono.jsx'
import { consultarNumero, fuentesNumeros } from '../services/api.js'
import { nivelRiesgo } from '../utils/riesgo.js'

const ICONO_FACTOR = { sube: 'alerta', baja: 'check', info: 'mira', alerta: 'alerta' }

function Resultado({ r, fuentes }) {
  const nivel = nivelRiesgo(r.nivel_riesgo)
  return (
    <section className={`resultado-numero ${nivel.clase}`} aria-live="polite">
      <div className="resultado-numero-cabecera">
        <div>
          <span className="eyebrow"><Icono nombre="llamar" tamano={14} /> Número consultado</span>
          <h2>{r.visible}</h2>
          <p className="texto-suave">{r.tipo_linea} · {r.pais}</p>
        </div>
        <div className={`medidor-numero ${nivel.clase}`}>
          <strong>{r.nivel_riesgo}</strong>
          <span>Riesgo {nivel.etiqueta.toLowerCase()}</span>
        </div>
      </div>

      <div className="barra-riesgo" role="img" aria-label={`Nivel de riesgo ${r.nivel_riesgo} de 100`}>
        <span style={{ width: `${Math.max(2, r.nivel_riesgo)}%`, background: nivel.tono }} />
      </div>

      <div className="resultado-numero-resumen">
        <span className={`chip chip-${nivel.id}`}>
          {r.confiable ? 'Línea oficial registrada' : (r.reportado ? 'Número reportado' : 'Sin reportes conocidos')}
        </span>
        {r.reportes_comunidad > 0 && (
          <span className="chip chip-neutro">
            <Icono nombre="usuarios" tamano={14} /> {r.reportes_comunidad} reporte{r.reportes_comunidad === 1 ? '' : 's'} de vecinos
          </span>
        )}
        {r.confiable && <span className="chip chip-bajo">Línea oficial: {r.confiable.entidad}</span>}
        <span className="chip chip-neutro">Confianza {r.confianza}%</span>
      </div>

      {r.confiable && (
        <div className="aviso aviso-info">
          <Icono nombre="candado" tamano={16} />
          <span>
            {r.confiable.nota} <a href={r.confiable.url} target="_blank" rel="noreferrer">Ver en el sitio oficial <Icono nombre="externo" tamano={12} /></a>
          </span>
        </div>
      )}

      {r.factores.length > 0 && (
        <div className="bloque-detalle">
          <h3><Icono nombre="pulso" tamano={16} /> Por qué este nivel</h3>
          <ul className="lista-factores">
            {r.factores.map((f, i) => (
              <li key={i} className={`factor factor-${f.tipo}`}>
                <Icono nombre={ICONO_FACTOR[f.tipo] || 'mira'} tamano={15} />
                <span>{f.texto}</span>
              </li>
            ))}
          </ul>
        </div>
      )}

      {r.causas.length > 0 && (
        <div className="bloque-detalle">
          <h3><Icono nombre="cadena" tamano={16} /> Señales del número</h3>
          <ul className="lista-causas">
            {r.causas.map((c, i) => <li key={i}>{c}</li>)}
          </ul>
        </div>
      )}

      {r.coincidencias.length > 0 && (
        <div className="bloque-detalle">
          <h3><Icono nombre="archivo" tamano={16} /> Reportes con fuente verificable</h3>
          <div className="tabla-scroll">
            <table className="tabla-numeros">
              <thead>
                <tr><th>Categoría</th><th>Fuente</th><th>Fecha</th><th>Detalle</th></tr>
              </thead>
              <tbody>
                {r.coincidencias.map((c, i) => (
                  <tr key={i}>
                    <td><strong>{c.categoria_nombre}</strong>{c.demo && <span className="chip chip-neutro">demo</span>}</td>
                    <td>
                      {c.url
                        ? <a href={c.url} target="_blank" rel="noreferrer">{c.fuente} <Icono nombre="externo" tamano={12} /></a>
                        : c.fuente}
                    </td>
                    <td>{c.fecha || '—'}</td>
                    <td>{c.descripcion || '—'}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        </div>
      )}

      <div className={`recomendacion recomendacion-${nivel.id}`}>
        <Icono nombre={nivel.id === 'alto' ? 'alerta' : 'escudo'} tamano={20} />
        <div>
          <strong>{nivel.id === 'alto' ? 'No sigas la conversación' : 'Cómo actuar'}</strong>
          <p>{r.recomendacion}</p>
        </div>
      </div>

      <p className="aviso aviso-medio"><Icono nombre="alerta" tamano={15} /> {r.aviso}</p>

      <div className="resultado-numero-acciones">
        <Link className="boton boton-primario" to={`/reportar?contexto=llamada&numero=${encodeURIComponent(r.numero)}`}>
          <Icono nombre="bandera" tamano={16} /> Reportar esta llamada
        </Link>
        <Link className="boton boton-secundario" to="/reportar">
          <Icono nombre="mensaje" tamano={16} /> Reportar un mensaje
        </Link>
      </div>

      {fuentes && (
        <p className="fuentes-numero texto-suave">
          Registro actualizado al {fuentes.actualizado || '—'} · {fuentes.confiables} líneas oficiales y{' '}
          {fuentes.reportados} números reportados por autoridades o entidades. Fuentes:{' '}
          {fuentes.fuentes.map((f, i) => (
            <span key={f.id}>
              {i > 0 && ' · '}
              <a href={f.url} target="_blank" rel="noreferrer">{f.nombre}</a>
            </span>
          ))}
        </p>
      )}
    </section>
  )
}

export default function ConsultarNumero() {
  const [params] = useSearchParams()
  const [numero, setNumero] = useState(params.get('numero') || '')
  const [resultado, setResultado] = useState(null)
  const [fuentes, setFuentes] = useState(null)
  const [error, setError] = useState(null)
  const [cargando, setCargando] = useState(false)

  useEffect(() => {
    fuentesNumeros().then(setFuentes).catch(() => null)
  }, [])

  useEffect(() => {
    const inicial = params.get('numero')
    if (inicial) consultar(inicial)
    // solo al montar: la URL puede venir del botón "Reportar esta llamada"
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [])

  const consultar = async (valor) => {
    const limpio = (valor ?? numero).trim()
    if (!limpio) {
      setError('Escribe el número que te llamó (o escribe "oculto" si no lo mostró).')
      return
    }
    setCargando(true)
    setError(null)
    setResultado(null)
    try {
      setResultado(await consultarNumero(limpio))
    } catch (e) {
      setError(e.message)
    } finally {
      setCargando(false)
    }
  }

  const enviar = (e) => {
    e.preventDefault()
    consultar()
  }

  return (
    <div className="pagina-numero">
      <section className="hero hero-compacto">
        <div className="hero-texto">
          <span className="eyebrow"><Icono nombre="llamar" tamano={14} /> Consulta de números · vishing</span>
          <h1>¿Te llamó un número desconocido?</h1>
          <p>
            Escríbelo y te decimos si ya fue <strong>reportado por autoridades, entidades o vecinos</strong>,
            qué nivel de riesgo tiene y qué hacer. Si te pidieron un código, una clave o instalar una app,
            es una estafa por llamada (<em>vishing</em>).
          </p>
        </div>
      </section>

      <form className="formulario formulario-numero" onSubmit={enviar}>
        <label className="campo-numero">
          <span>Número que llamó</span>
          <div className="campo-numero-fila">
            <Icono nombre="llamar" tamano={18} />
            <input
              type="tel"
              inputMode="tel"
              autoComplete="tel"
              placeholder="Ej.: 300 123 4567 · +57 601 592 0400"
              value={numero}
              onChange={(e) => setNumero(e.target.value)}
              maxLength={40}
            />
            <button type="submit" className="boton boton-primario" disabled={cargando}>
              {cargando ? <><span className="spinner" /> Consultando…</> : <><Icono nombre="buscar" tamano={16} /> Consultar</>}
            </button>
          </div>
        </label>
        <div className="campo-numero-ayuda">
          <button type="button" className="boton-texto" onClick={() => { setNumero('oculto'); consultar('oculto') }}>
            No mostró número
          </button>
          <span className="texto-suave">También puedes pegar el número con espacios, guiones o +57.</span>
        </div>
      </form>

      {error && <p className="aviso aviso-error"><Icono nombre="alerta" tamano={16} /> {error}</p>}

      {resultado && <Resultado r={resultado} fuentes={fuentes} />}

      {!resultado && !error && (
        <section className="panel panel-numero">
          <div className="panel-cabecera">
            <h2><Icono nombre="escudo" tamano={18} /> Un número no es toda la historia</h2>
          </div>
          <p className="texto-suave">
            Los estafadores cambian de línea y pueden falsificar el número que aparece en pantalla
            (<em>spoofing</em>). Que un número no esté reportado no significa que sea seguro: si la llamada pide
            dinero, códigos, claves o instalar una app de control remoto, es fraude.
          </p>
          <ul className="lista-causas">
            <li>Ninguna entidad pide por teléfono el código que llega por SMS ni tu clave dinámica.</li>
            <li>Los bancos no tienen “cuentas seguras” para mover tu plata.</li>
            <li>Si ya diste datos o dinero, llama a tu banco y al 123; guarda el certificado del reporte.</li>
          </ul>
        </section>
      )}
    </div>
  )
}
