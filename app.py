import calendar
from datetime import datetime
import gspread
from google.oauth2.service_account import Credentials
import streamlit as st

# Configuração da página do Streamlit
st.set_page_config(
    page_title="Reserva de Salas - DMA", page_icon="🏫", layout="centered"
)


# 1. Autenticação no Google Sheets via Conta de Serviço
@st.cache_resource
def conectar_google_sheets():
  scope = [
      "https://www.googleapis.com/auth/spreadsheets",
      "https://www.googleapis.com/auth/drive",
  ]
  # Busca as credenciais salvas nos Secrets do Streamlit
  creds_dict = st.secrets["gcp_service_account"]
  creds = Credentials.from_service_account_info(creds_dict, scopes=scope)
  client = gspread.authorize(creds)
  return client


# Conectar à planilha criada no Google Drive
try:
  gc = conectar_google_sheets()
  sh = gc.open("Reserva_de_Salas_DMA_2026_Online")
except Exception as e:
  st.error(
      "Erro ao conectar com a planilha do Google Sheets. Verifique o compartilhamento."
  )
  st.stop()

months_map = {
    8: "Agosto 2026",
    9: "Setembro 2026",
    10: "Outubro 2026",
    11: "Novembro 2026",
    12: "Dezembro 2026",
}

# 2. Interface do Usuário (Streamlit)
st.title("🏫 Reserva de Salas - DMA 2026")
st.write(
    "Preencha o formulário abaixo para solicitar o agendamento das salas 307,"
    " 309 ou 312."
)

with st.form("form_reserva", clear_on_submit=True):
  nome = st.text_input("Seu Nome Completo", placeholder="Ex: Prof. Carlos Silva")

  col1, col2 = st.columns(2)
  with col1:
    data_reserva = st.date_input(
        "Data da Reserva", min_value=datetime(2026, 8, 1)
    )
  with col2:
    sala = st.selectbox("Selecione a Sala", ["307", "309", "312"])

  horarios_opcoes = [f"{h:02d}:00" for h in range(8, 23)]
  col3, col4 = st.columns(2)
  with col3:
    h_inicio = st.selectbox("Horário de Início", horarios_opcoes, index=0)
  with col4:
    h_fim = st.selectbox("Horário de Término", horarios_opcoes, index=2)

  finalidade = st.text_input(
      "Finalidade / Atividade", placeholder="Ex: Aula de Monitoria / Reunião"
  )

  submetido = st.form_submit_button("📅 Confirmar Solicitação")

if submetido:
  if not nome.strip():
    st.error("Por favor, informe seu nome completo.")
  else:
    mes_num = data_reserva.month
    if mes_num not in months_map:
      st.error(
          "As reservas estão disponíveis apenas entre Agosto e Dezembro de"
          " 2026."
      )
    else:
      data_str = data_reserva.strftime("%d/%m/%Y")
      sala_nome = f"Sala {sala}"
      nome_aba = months_map[mes_num]

      ws = sh.worksheet(nome_aba)
      dados = ws.get_all_records(head=4)

      # Checar Conflito
      conflito = False
      pessoa_conflito = ""
      for r in dados:
        if (
            str(r.get("Data")).strip() == data_str
            and str(r.get("Horário Início")).strip() == h_inicio
            and str(r.get("Sala")).strip() == sala_nome
            and str(r.get("Status")).strip() in ["Confirmado", "Pendente"]
        ):
          conflito = True
          pessoa_conflito = str(r.get("Solicitante / Responsável")).strip()
          break

      if conflito:
        st.warning(
            f"⚠️ CONFLITO DE RESERVA: A {sala_nome} já foi solicitada por"
            f" '{pessoa_conflito}' em {data_str} às {h_inicio}."
        )
      else:
        proxima_linha = len(dados) + 5
        novo_id = f"RES-{mes_num:02d}-{len(dados)+1:03d}"
        nova_linha = [
            novo_id,
            data_str,
            h_inicio,
            h_fim,
            sala_nome,
            nome,
            finalidade,
            "Pendente",
            "Solicitado via Web App",
        ]

        ws.update(
            range_name=f"A{proxima_linha}:I{proxima_linha}", values=[nova_linha]
        )
        st.success(
            f"✅ Solicitação (ID: {novo_id}) enviada com sucesso! Status:"
            " Pendente."
        )