from datetime import datetimefrom datetime import datetime
from decimal import Decimal
import io
import base64
from reportlab.lib import colors
from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import ParagraphStyle, getSampleStyleSheet
from reportlab.platypus import Paragraph, SimpleDocTemplate, Spacer, Table, TableStyle
import streamlit as st
from supabase import Client, create_client

st.set_page_config(
    page_title="Contabilità Scontrini Bancomat", page_icon="💳", layout="centered"
)


def check_password():
  """Restituisce True se l'utente ha inserito la password corretta."""

  def password_entered():
    if (
        "APP_PASSWORD" in st.secrets
        and st.session_state["password_input"] == st.secrets["APP_PASSWORD"]
    ):
      st.session_state["password_correct"] = True
      del st.session_state["password_input"]
    else:
      st.session_state["password_correct"] = False

  if "password_correct" not in st.session_state:
    st.title("🔒 Autenticazione Richiesta")
    st.text_input(
        "Inserisci la password di accesso",
        type="password",
        on_change=password_entered,
        key="password_input",
    )
    return False
  elif not st.session_state["password_correct"]:
    st.title("🔒 Autenticazione Richiesta")
    st.text_input(
        "Inserisci la password di accesso",
        type="password",
        on_change=password_entered,
        key="password_input",
    )
    st.error("😕 Password errata. Riprova.")
    return False
  else:
    return True


if not check_password():
  st.stop()


@st.cache_resource
def init_supabase():
  url = st.secrets["SUPABASE_URL"]
  key = st.secrets["SUPABASE_KEY"]
  return create_client(url, key)


supabase: Client = init_supabase()


def aggiungi_transazione(
    data, tipo, importo, esercente, categoria, scontrino_conservato, base64_scontrino=None
):
  valore = float(Decimal(str(importo)).quantize(Decimal("0.01")))
  dati_inserimento = {
      "data": data,
      "tipo": tipo.upper(),
      "importo": valore,
      "esercente": esercente,
      "categoria": categoria,
      "scontrino_conservato": 1 if scontrino_conservato else 0,
      "url_scontrino": base64_scontrino,
  }
  response = supabase.table("transazioni").insert(dati_inserimento).execute()
  return response


def aggiorna_scontrino_transazione(id_transazione, base64_scontrino):
  response = (
      supabase.table("transazioni")
      .update({
          "scontrino_conservato": 1,
          "url_scontrino": base64_scontrino,
      })
      .eq("id", id_transazione)
      .execute()
  )
  return response


def elimina_transazione(id_transazione):
  response = (
      supabase.table("transazioni").delete().eq("id", id_transazione).execute()
  )
  return response


def ottieni_transazioni():
  response = (
      supabase.table("transazioni")
      .select("*")
      .order("data", desc=True)
      .execute()
  )
  return response.data


def genera_pdf_transazioni(
    prefisso_filtro, totale_entrate, totale_uscite, saldo, dati_tabella
):
  buffer = io.BytesIO()
  doc = SimpleDocTemplate(
      buffer,
      pagesize=A4,
      rightMargin=30,
      leftMargin=30,
      topMargin=30,
      bottomMargin=30,
  )
  elementi = []

  styles = getSampleStyleSheet()
  title_style = ParagraphStyle(
      "TitleStyle",
      parent=styles["Heading1"],
      fontSize=18,
      textColor=colors.HexColor("#1E3A8A"),
      spaceAfter=15,
  )

  subtitle_style = ParagraphStyle(
      "SubTitleStyle",
      parent=styles["Heading2"],
      fontSize=12,
      textColor=colors.HexColor("#4B5563"),
      spaceAfter=15,
  )

  elementi.append(Paragraph("Riepilogo Contabilità Bancomat", title_style))
  elementi.append(Paragraph(f"Periodo: {prefisso_filtro}", subtitle_style))

  riepilogo_data = [
      ["Totale Entrate", f"€ {totale_entrate:.2f}"],
      ["Totale Uscite", f"€ {totale_uscite:.2f}"],
      ["Saldo Netto", f"€ {saldo:.2f}"],
  ]
  t_riepilogo = Table(riepilogo_data, colWidths=[150, 100])
  t_riepilogo.setStyle(
      TableStyle([
          ("BACKGROUND", (0, 0), (-1, -1), colors.HexColor("#F3F4F6")),
          ("TEXTCOLOR", (0, 0), (-1, -1), colors.HexColor("#1F2937")),
          ("FONTNAME", (0, 0), (-1, -1), "Helvetica-Bold"),
          ("BOTTOMPADDING", (0, 0), (-1, -1), 6),
          ("TOPPADDING", (0, 0), (-1, -1), 6),
          ("GRID", (0, 0), (-1, -1), 0.5, colors.HexColor("#D1D5DB")),
      ])
  )
  elementi.append(t_riepilogo)
  elementi.append(Spacer(1, 20))

  elementi.append(Paragraph("Dettaglio Transazioni", subtitle_style))

  table_data = [
      ["Data", "Tipo", "Importo (€)", "Esercente", "Categoria", "Scontrino"]
  ]
  for row in dati_tabella:
    table_data.append([
        row["Data"],
        row["Tipo"],
        row["Importo (€)"],
        row["Esercente"],
        row["Categoria"],
        row["Scontrino"],
    ])

  t_dettaglio = Table(table_data, colWidths=[75, 65, 80, 110, 100, 70])
  t_dettaglio.setStyle(
      TableStyle([
          ("BACKGROUND", (0, 0), (-1, 0), colors.HexColor("#1E3A8A")),
          ("TEXTCOLOR", (0, 0), (-1, 0), colors.white),
          ("FONTNAME", (0, 0), (-1, 0), "Helvetica-Bold"),
          ("FONTSIZE", (0, 0), (-1, 0), 10),
          ("BOTTOMPADDING", (0, 0), (-1, -1), 5),
          ("TOPPADDING", (0, 0), (-1, -1), 5),
          (
              "ROWBACKGROUNDS",
              (0, 1),
              (-1, -1),
              [colors.white, colors.HexColor("#F9FAFB")],
          ),
          ("GRID", (0, 0), (-1, -1), 0.5, colors.HexColor("#E5E7EB")),
          ("FONTNAME", (0, 1), (-1, -1), "Helvetica"),
          ("FONTSIZE", (0, 1), (-1, -1), 9),
      ])
  )

  elementi.append(t_dettaglio)
  doc.build(elementi)
  buffer.seek(0)
  return buffer.getvalue()


st.title("💳 Contabilità e Riconciliazione Scontrini")

menu = st.sidebar.selectbox(
    "Seleziona Sezione", ["Aggiungi Transazione", "Visualizza e Riconcilia"]
)

if menu == "Aggiungi Transazione":
  st.subheader("Registra Nuova Transazione")

  with st.form("form_transazione", clear_on_submit=True):
    data = st.date_input("Data Transazione")
    tipo = st.selectbox("Tipo", ["Uscita", "Entrata"])
    importo = st.number_input(
        "Importo (€)", min_value=0.01, format="%.2f", step=1.00
    )
    esercente = st.text_input("Esercente / Beneficiario")
    categoria = st.text_input("Categoria (es. Spesa, Ristorante, Stipendio)")
    scontrino_checkbox = st.checkbox(
        "Scontrino conservato?", value=True if tipo == "Uscita" else False
    )

    submit = st.form_submit_button("Salva Transazione")

  st.markdown("---")
  st.subheader("📷 Acquisizione Fotografica Scontrino (Opzionale)")
  attiva_camera = st.toggle("Attiva fotocamera per scattare lo scontrino")
  foto_scontrino = None

  if attiva_camera:
    foto_scontrino = st.camera_input("Inquadra lo scontrino")
    if foto_scontrino is not None:
      st.image(foto_scontrino, caption="Anteprima Scontrino", width=300)

  if submit:
    if esercente.strip() == "":
      st.warning("Inserisci il nome dell'esercente.")
    else:
      try:
        stringa_base64 = None
        if foto_scontrino is not None:
          bytes_immagine = foto_scontrino.getvalue()
          stringa_base64 = base64.b64encode(bytes_immagine).decode("utf-8")

        aggiungi_transazione(
            str(data),
            tipo.upper(),
            importo,
            esercente,
            categoria,
            1 if (scontrino_checkbox or foto_scontrino is not None) else 0,
            stringa_base64,
        )
        st.success(
            "Transazione e scontrino salvati con successo su Supabase!"
        )
      except Exception as e:
        st.error(f"Errore durante il salvataggio: {e}")

elif menu == "Visualizza e Riconcilia":
  st.subheader("Elenco Transazioni e Riconciliazione Mensile")

  try:
    transazioni = ottieni_transazioni()
  except Exception as e:
    st.error(f"Errore nel recupero dati da Supabase: {e}")
    transazioni = []

  if not transazioni:
    st.info(
        "Nessuna transazione registrata nel database. Utilizza il menu a"
        " sinistra per aggiungerne una."
    )
  else:
    anni_disponibili = sorted(
        list(set([str(t["data"])[:4] for t in transazioni])), reverse=True
    )

    anno_corrente = str(datetime.now().year)
    mese_corrente = datetime.now().month

    default_anno_idx = (
        anni_disponibili.index(anno_corrente)
        if anno_corrente in anni_disponibili
        else 0
    )

    col1, col2 = st.columns(2)
    with col1:
      anno_sel = st.selectbox(
          "Seleziona Anno", anni_disponibili, index=default_anno_idx
      )
    with col2:
      mese_sel = st.selectbox(
          "Seleziona Mese",
          range(1, 13),
          index=mese_corrente - 1,
          format_func=lambda x: f"{x:02d}",
      )

    prefisso_filtro = f"{anno_sel}-{mese_sel:02d}"

    totale_entrate = Decimal("0.00")
    totale_uscite = Decimal("0.00")
    mancanti = []
    dati_tabella = []
    transazioni_filtrate = []

    for t in transazioni:
      data_t = str(t["data"])
      if data_t.startswith(prefisso_filtro):
        transazioni_filtrate.append(t)
        val = Decimal(str(t["importo"]))
        tipo_t = t["tipo"]
        esc_t = t["esercente"]
        cat_t = t["categoria"]
        scontrino_t = t["scontrino_conservato"]

        if tipo_t == "ENTRATA":
          totale_entrate += val
        else:
          totale_uscite += val
          if scontrino_t == 0:
            mancanti.append((esc_t, val, data_t))

        dati_tabella.append({
            "Data": data_t,
            "Tipo": tipo_t,
            "Importo (€)": f"{val:.2f}",
            "Esercente": esc_t,
            "Categoria": cat_t,
            "Scontrino": "Sì" if scontrino_t == 1 else "No",
        })

    st.markdown(f"### RIEPILOGO MESE: {prefisso_filtro}")
    m1, m2, m3 = st.columns(3)
    m1.metric("Entrate", f"€ {totale_entrate:.2f}")
    m2.metric("Uscite", f"€ {totale_uscite:.2f}")
    saldo_netto = totale_entrate - totale_uscite
    m3.metric("Saldo Netto", f"€ {saldo_netto:.2f}")

    if mancanti:
      st.warning(
          f"⚠️ Attenzione: Ci sono {len(mancanti)} uscite senza scontrino nel"
          " periodo selezionato!"
      )
      for esc, imp, dt in mancanti:
        st.write(f"- **{dt}** | {esc}: **€ {imp:.2f}**")
    elif dati_tabella:
      st.success("Tutte le uscite di questo mese hanno uno scontrino abbinato!")

    st.markdown("### Dettaglio Transazioni e Scontrini del Mese")
    if dati_tabella:
      st.dataframe(dati_tabella, use_container_width=True)

      st.markdown("#### 🔍 Gestione Scontrino e Transazione")
      opzioni_gestione = {
          f"ID {t['id']} - {t['data']} - {t['tipo']} - € {t['importo']} - {t['esercente']}": t
          for t in transazioni_filtrate
      }

      if opzioni_gestione:
        voce_selezionata = st.selectbox(
            "Seleziona la transazione da esaminare",
            options=list(opzioni_gestione.keys()),
        )
        transazione_selezionata = opzioni_gestione[voce_selezionata]

        # Decodifica ed esposizione dello scontrino salvato in base64
        dati_b64 = transazione_selezionata.get("url_scontrino")
        if dati_b64:
          st.success("📄 Scontrino fotografico disponibile per questa transazione:")
          try:
            binario_immagine = base64.b64decode(dati_b64)
            st.image(binario_immagine, caption=f"Scontrino - {transazione_selezionata['esercente']}", width=400)
          except Exception:
            st.error("Impossibile decodificare l'immagine salvata.")
        else:
          st.info("ℹ️ Nessuna foto scontrino associata a questa transazione.")

        # Integrazione del bottone / fotocamera per acquisire e associare lo scontrino
        st.markdown("##### 📷 Aggiungi o Aggiorna Foto Scontrino")
        attiva_camera_rec = st.toggle("Attiva fotocamera per questo scontrino", key=f"cam_{transazione_selezionata['id']}")
        foto_scontrino_rec = None

        if attiva_camera_rec:
          foto_scontrino_rec = st.camera_input("Inquadra lo scontrino da associare", key=f"cam_input_{transazione_selezionata['id']}")
          if foto_scontrino_rec is not None:
            st.image(foto_scontrino_rec, caption="Nuova Anteprima Scontrino", width=300)
            if st.button("Salva Foto per questa Transazione", key=f"save_photo_{transazione_selezionata['id']}"):
              try:
                bytes_img = foto_scontrino_rec.getvalue()
                str_b64 = base64.b64encode(bytes_img).decode("utf-8")
                aggiorna_scontrino_transazione(transazione_selezionata["id"], str_b64)
                st.success("Scontrino associato e salvato con successo!")
                st.rerun()
              except Exception as e:
                st.error(f"Errore durante l'aggiornamento dello scontrino: {e}")

        if st.button("Elimina Transazione Selezionata", type="primary"):
          id_da_eliminare = transazione_selezionata["id"]
          try:
            elimina_transazione(id_da_eliminare)
            st.success("Transazione eliminata con successo!")
            st.rerun()
          except Exception as e:
            st.error(f"Errore durante l'eliminazione: {e}")

      pdf_bytes = genera_pdf_transazioni(
          prefisso_filtro,
          totale_entrate,
          totale_uscite,
          saldo_netto,
          dati_tabella,
      )
      st.download_button(
          label="📄 Stampa in PDF",
          data=pdf_bytes,
          file_name=f"contabilita_{prefisso_filtro}.pdf",
          mime="application/pdf",
      )
    else:
      st.info(
          "Nessuna transazione trovata per il mese selezionato. Cambia mese o"
          " aggiungi una nuova transazione."
      )
