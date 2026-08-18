import calendar
from datetime import datetime
import email.mime.multipart
import email.mime.text
import smtplib
from dateutil.relativedelta import relativedelta
import gspread
from google.oauth2.service_account import Credentials
import streamlit as st

# -----------------------------------------------------------------------------
# CONFIGURAÇÃO DA PÁGINA
# -----------------------------------------------------------------------------
st.set_page_config(
    page_title="Reserva de Salas - DMA", page_icon="🏫", layout="centered"
)


# -----------------------------------------------------------------------------
# 1. AUTENTICAÇÃO NO GOOGLE SHEETS
# -----------------------------------------------------------------------------
@st.cache_resource
def conectar_google_sheets():
  scope = [
      "https://www.googleapis.com/auth/spreadsheets",
      "https://www.googleapis.com/auth/drive",
  ]
  creds_dict = st.secrets["gcp_service_account"]
  creds = Credentials.from_service_account_info(creds_dict, scopes=scope)
  return gspread.authorize(creds)


try:
  gc = conectar_google_sheets()
  sh = gc.open("Reserva_de_Salas_DMA_2026_Online")
except Exception as e:
  st.error(
      "Erro ao conectar com a planilha do Google Sheets. Verifique a chave de"
      " acesso e o compartilhamento."
  )
  st.stop()

months_map = {
    8: "Agosto 2026",
    9: "Setembro 2026",
    10: "Outubro 2026",
    11: "Novembro 2026",
    12: "Dezembro 2026",
}


# -----------------------------------------------------------------------------
# 2. FUNÇÃO AUXILIAR PARA ENVIAR E-MAIL (ADMIN)
# -----------------------------------------------------------------------------
def enviar_email_notificacao(
    nome, email_solicitante, sala_nome, datas_list, h_inicio, h_fim, finalidade
):
  """Envia e-mail de alerta para o Admin sobre novas solicitações pendentes."""
  try:
    email_admin = st.secrets.get("EMAIL_ADMIN", "")
    email_remetente = st.secrets.get("EMAIL_REMETENTE", "")
    senha_app = st.secrets.get("GMAIL_APP_PASSWORD", "")

    if not email_admin or not email_remetente or not senha_app:
      print("Credenciais de e-mail não configuradas nos Secrets.")
      return

    msg = email.mime.multipart.MIMEMultipart()
    msg["From"] = email_remetente
    msg["To"] = email_admin
    msg["Subject"] = f"📌 Nova Reserva Pendente - {sala_nome} ({nome})"

    datas_str = ", ".join([d.strftime("%d/%m/%Y") for d in datas_list])

    corpo_html = f"""
        <h3>Nova Solicitação de Reserva de Sala - DMA</h3>
        <p><b>Solicitante:</b> {nome}</p>
        <p><b>E-mail do Solicitante:</b> {email_solicitante}</p>
        <p><b>Espaço Solicitado:</b> {sala_nome}</p>
        <p><b>Data(s):</b> {datas_str}</p>
        <p><b>Horário:</b> {h_inicio} às {h_fim}</p>
        <p><b>Finalidade:</b> {finalidade}</p>
        <hr>
        <p>Acesse a planilha do Google Sheets para confirmar ou alterar o status da reserva.</p>
        """

    msg.attach(email.mime.text.MIMEText(corpo_html, "html"))

    server = smtplib.SMTP("smtp.gmail.com", 587)
    server.starttls()
    server.login(email_remetente, senha_app)
    server.sendmail(email_remetente, email_admin, msg.as_string())
    server.quit()
  except Exception as err:
    print(f"Erro ao enviar e-mail de notificação: {err}")


# -----------------------------------------------------------------------------
# 3. INTERFACE DO USUÁRIO (FORMULÁRIO)
# -----------------------------------------------------------------------------
st.title("🏫 Reserva de Salas - DMA 2026")
st.write(
    "Preencha o formulário abaixo para solicitar o agendamento das salas 307,"
    " 309 ou 312."
)

with st.form("form_reserva", clear_on_submit=False):
  col_nome, col_email = st.columns(2)
  with col_nome:
    nome = st.text_input("Seu Nome Completo", placeholder="Ex: Prof. Carlos Silva")
  with col_email:
    email_solicitante = st.text_input(
        "Seu E-mail (para confirmação)", placeholder="exemplo@ufv.br"
    )

  col1, col2 = st.columns(2)
  with col1:
    data_inicio = st.date_input(
        "Data Início / Única", min_value=datetime(2026, 8, 1)
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

  # --- OPÇÕES DE RECORRÊNCIA ---
  st.markdown("---")
  st.subheader("🔁 Repetição / Recorrência")

  tipo_recorrencia = st.selectbox(
      "Repetir reserva",
      [
          "Não se repete (Apenas na data selecionada)",
          "Semanalmente (A cada semana)",
          "Mensalmente (A cada mês no mesmo dia)",
          "Personalizado (A cada X semanas)",
      ],
  )

  qtd_repeticoes = 1
  intervalo_semanas = 1

  if tipo_recorrencia == "Semanalmente (A cada semana)":
    qtd_repeticoes = st.number_input(
        "Número de semanas seguidas:", min_value=2, max_value=20, value=4
    )

  elif tipo_recorrencia == "Mensalmente (A cada mês no mesmo dia)":
    qtd_repeticoes = st.number_input(
        "Número de meses seguidos:", min_value=2, max_value=5, value=3
    )

  elif tipo_recorrencia == "Personalizado (A cada X semanas)":
    col_rec1, col_rec2 = st.columns(2)
    with col_rec1:
      intervalo_semanas = st.number_input(
          "Repetir a cada quantos intervalos (semanas):",
          min_value=1,
          max_value=4,
          value=2,
      )
    with col_rec2:
      qtd_repeticoes = st.number_input(
          "Total de ocorrências:", min_value=2, max_value=10, value=4
      )

  submetido = st.form_submit_button("📅 Confirmar Solicitação")


# -----------------------------------------------------------------------------
# 4. PROCESSAMENTO E VALIDAÇÃO DA RESERVA
# -----------------------------------------------------------------------------
if submetido:
  if not nome.strip():
    st.error("Por favor, informe seu nome completo.")
  elif not email_solicitante.strip() or "@" not in email_solicitante:
    st.error("Por favor, informe um e-mail válido para receber a confirmação.")
  else:
    # Gerar a lista de datas com base no tipo de recorrência
    datas_agendamento = []
    data_atual = data_inicio

    for _ in range(qtd_repeticoes):
      if data_atual.month in months_map:
        datas_agendamento.append(data_atual)

      if "Semanalmente" in tipo_recorrencia:
        data_atual += relativedelta(weeks=1)
      elif "Mensalmente" in tipo_recorrencia:
        data_atual += relativedelta(months=1)
      elif "Personalizado" in tipo_recorrencia:
        data_atual += relativedelta(weeks=intervalo_semanas)

    if not datas_agendamento:
      st.error(
          "Nenhuma das datas da repetição está dentro do período letivo de"
          " Agosto a Dezembro de 2026."
      )
      st.stop()

    sala_nome = f"Sala {sala}"
    conflitos_encontrados = []

    # Checar conflito de horários em todas as datas geradas
    for d in datas_agendamento:
      mes_num = d.month
      data_str = d.strftime("%d/%m/%Y")
      nome_aba = months_map[mes_num]

      ws = sh.worksheet(nome_aba)
      dados = ws.get_all_records(head=4)

      for r in dados:
        if (
            str(r.get("Data")).strip() == data_str
            and str(r.get("Horário Início")).strip() == h_inicio
            and str(r.get("Sala")).strip() == sala_nome
            and str(r.get("Status")).strip() in ["Confirmado", "Pendente"]
        ):
          pessoa = str(r.get("Solicitante / Responsável")).strip()
          conflitos_encontrados.append(f"{data_str} (Reservado por: {pessoa})")
          break

    if conflitos_encontrados:
      st.error(
          f"⚠️ A reserva não pôde ser concluída devido a conflito de horários"
          f" em {len(conflitos_encontrados)} data(s):"
      )
      for c in conflitos_encontrados:
        st.write(f"- {c}")
    else:
      agendamentos_sucesso = []

      # Registrar agendamentos na planilha
      for d in datas_agendamento:
        mes_num = d.month
        data_str = d.strftime("%d/%m/%Y")
        nome_aba = months_map[mes_num]

        ws = sh.worksheet(nome_aba)
        dados = ws.get_all_records(head=4)

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
            f"Solicitado via Web App | Contato: {email_solicitante}",
        ]

        ws.update(
            range_name=f"A{proxima_linha}:I{proxima_linha}", values=[nova_linha]
        )
        agendamentos_sucesso.append(f"{data_str} (ID: {novo_id})")

      # Enviar notificação por e-mail para o Admin
      enviar_email_notificacao(
          nome,
          email_solicitante,
          sala_nome,
          datas_agendamento,
          h_inicio,
          h_fim,
          finalidade,
      )

      st.success(
          f"✅ Todas as {len(agendamentos_sucesso)} solicitações foram"
          " registradas com sucesso! O status atual é 'Pendente'."
      )
      with st.expander("Ver lista das datas agendadas"):
        for item in agendamentos_sucesso:
          st.write(f"- {item}")
