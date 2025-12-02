import streamlit as st
import pandas as pd
import gspread
from oauth2client.service_account import ServiceAccountCredentials
from datetime import date, datetime, time
import os
import base64

# --- 1. CONFIGURAÇÃO VISUAL & CSS "NUCLEAR" PARA IMPRESSÃO ---
st.set_page_config(page_title="Gestão Clínica Total", layout="wide", page_icon="logo.png")

st.markdown("""
    <style>
    /* Estilos normais para a tela do computador */
    .ficha-papel {
        border: 1px solid #ccc;
        padding: 30px;
        background-color: white;
        margin-top: 20px;
        box-shadow: 0 4px 8px rgba(0,0,0,0.1);
    }

    /* --- A MÁGICA DA IMPRESSÃO ACONTECE AQUI --- */
    @media print {
        /* 1. Ocultar TUDO que existe na página */
        body * {
            visibility: hidden;
        }

        /* 2. Forçar a visualização APENAS da nossa ficha */
        .ficha-papel, .ficha-papel * {
            visibility: visible;
        }

        /* 3. Posicionar a ficha no topo absoluto da folha */
        .ficha-papel {
            position: absolute;
            left: 0;
            top: 0;
            width: 100%;
            margin: 0;
            padding: 2cm; /* Margem de segurança para a folha A4 */
            border: none; /* Remove a borda cinza na impressão */
            box-shadow: none;
        }
        
        /* Configura a folha para A4 sem cabeçalhos do navegador */
        @page { size: auto; margin: 0mm; }
    }
    
    /* Estilos bonitos para o documento */
    .cabecalho { text-align: center; border-bottom: 2px solid #333; padding-bottom: 10px; margin-bottom: 20px; }
    .titulo-doc { font-size: 26px; font-weight: bold; text-transform: uppercase; margin-top: 10px; }
    .secao { margin-bottom: 15px; border-bottom: 1px solid #eee; padding-bottom: 10px; }
    .secao-titulo { font-weight: bold; font-size: 16px; color: #333; text-transform: uppercase; margin-bottom: 5px; border-left: 5px solid #333; padding-left: 10px; }
    .conteudo { font-size: 14px; line-height: 1.5; color: #000; }
    .assinaturas { margin-top: 60px; display: flex; justify-content: space-between; }
    .campo-ass { border-top: 1px solid #000; width: 45%; text-align: center; padding-top: 5px; font-size: 12px; }
    </style>
""", unsafe_allow_html=True)

# --- 2. CONEXÃO ---
def conectar_google_sheets():
    scope = ["https://spreadsheets.google.com/feeds", "https://www.googleapis.com/auth/drive"]
    try:
        if "gcp_service_account" in st.secrets:
            creds = ServiceAccountCredentials.from_json_keyfile_dict(dict(st.secrets["gcp_service_account"]), scope)
        else:
            creds = ServiceAccountCredentials.from_json_keyfile_name("credentials.json", scope)
        client = gspread.authorize(creds)
        return client.open("sistema_clinica")
    except: return None

def carregar_aba(planilha, nome_aba):
    try:
        sheet = planilha.worksheet(nome_aba)
        df = pd.DataFrame(sheet.get_all_records())
        if nome_aba == "agendamentos" and (df.empty or 'Data' not in df.columns):
            cols = ["Data", "Hora", "Nome_Cliente", "Contato", "Dados_Pessoais",
                    "Anamnese_Geral", "Saude_Mulher", "Medidas_Corporais", 
                    "Analise_Facial", "Orcamento", "Status"]
            return pd.DataFrame(columns=cols)
        if nome_aba == "despesas" and (df.empty or 'Valor' not in df.columns):
            return pd.DataFrame(columns=["Data", "Descricao", "Categoria", "Valor"])
        return df
    except: return pd.DataFrame()

# --- 3. LÓGICA ---
def verificar_conflito(df, dia, hora):
    if df.empty or 'Data' not in df.columns: return False
    dia_str = dia.strftime("%d/%m/%Y")
    hora_str = hora.strftime("%H:%M")
    conflito = df[
        (df['Data'].astype(str).str.contains(dia_str, regex=False)) & 
        (df['Hora'].astype(str).str.contains(hora_str, regex=False))
    ]
    return not conflito.empty

def limpar_valor(v):
    try:
        if isinstance(v, (int, float)): return float(v)
        txt = str(v)
        if "Valor: R$" in txt: txt = txt.split("Valor: R$")[1].strip()
        return float(txt.replace("R$", "").replace(".", "").replace(",", "."))
    except: return 0.0

def processar_checkboxes(dicionario):
    itens = [k for k, v in dicionario.items() if v]
    return ", ".join(itens) if itens else "Nada"

# --- 4. SISTEMA ---
def main():
    with st.sidebar:
        if os.path.exists("logo.png"): st.image("logo.png", width=200)
        st.title("Menu Clínica")
        menu = st.radio("Navegação:", [
            "📊 Painel Financeiro",
            "📅 Agendamento Rápido", 
            "📝 Ficha Completa (PDF Clone)", 
            "🖨️ Impressão Profissional",
            "💸 Registrar Despesa"
        ])
        st.success("V6.6 - Impressão Limpa")

    planilha = conectar_google_sheets()
    if not planilha: return

    # === FINANCEIRO ===
    if menu == "📊 Painel Financeiro":
        st.header("📊 Fluxo de Caixa")
        df_ag = carregar_aba(planilha, "agendamentos")
        df_dp = carregar_aba(planilha, "despesas")
        c1, c2 = st.columns(2)
        mes = c1.selectbox("Mês", range(1,13), index=datetime.now().month-1)
        ano = c2.number_input("Ano", value=datetime.now().year)
        
        rec = 0.0
        if not df_ag.empty and 'Orcamento' in df_ag.columns:
            df_ag['Dt'] = pd.to_datetime(df_ag['Data'], dayfirst=True, errors='coerce')
            f = df_ag[(df_ag['Dt'].dt.month == mes) & (df_ag['Dt'].dt.year == ano)]
            for item in f['Orcamento']: rec += limpar_valor(item)
        desp = 0.0
        if not df_dp.empty:
            df_dp['Dt'] = pd.to_datetime(df_dp['Data'], dayfirst=True, errors='coerce')
            f2 = df_dp[(df_dp['Dt'].dt.month == mes) & (df_dp['Dt'].dt.year == ano)]
            desp = f2['Valor'].apply(lambda x: limpar_valor(str(x))).sum()
        k1, k2, k3 = st.columns(3)
        k1.metric("Entradas", f"R$ {rec:,.2f}")
        k2.metric("Saídas", f"R$ {desp:,.2f}")
        k3.metric("Lucro", f"R$ {rec-desp:,.2f}")

    # === AGENDAMENTO ===
    elif menu == "📅 Agendamento Rápido":
        st.header("📅 Agenda Expressa")
        df = carregar_aba(planilha, "agendamentos")
        with st.form("rapido"):
            c1, c2 = st.columns(2)
            nome = c1.text_input("Nome")
            zap = c2.text_input("WhatsApp")
            c3, c4 = st.columns(2)
            dia = c3.date_input("Data", min_value=date.today())
            hora = c4.time_input("Hora", value=time(9,0))
            obs = st.text_input("Motivo")
            if st.form_submit_button("Agendar"):
                if verificar_conflito(df, dia, hora): st.error("Ocupado!")
                elif not nome: st.warning("Nome obrigatório")
                else:
                    planilha.worksheet("agendamentos").append_row([
                        dia.strftime("%d/%m/%Y"), str(hora), nome, zap, 
                        "-", "-", "-", "-", "-", obs, "Agendado"
                    ])
                    st.success("Agendado!")

    # === FICHA COMPLETA ===
    elif menu == "📝 Ficha Completa (PDF Clone)":
        st.header("📝 Avaliação Detalhada")
        t1, t2, t3, t4, t5 = st.tabs(["👤 Pessoais", "❤️ Saúde/Laser", "📏 Corporal", "✨ Facial/Pele", "💰 Orçamento"])
        
        with st.form("ficha_full"):
            with t1:
                st.subheader("1. Identificação")
                c1, c2 = st.columns(2)
                nome = c1.text_input("Nome Completo")
                nasc = c2.text_input("Data Nascimento")
                c3, c4 = st.columns(2)
                cpf = c3.text_input("CPF")
                prof = c4.text_input("Profissão")
                end = st.text_input("Endereço Completo")
                tel = st.text_input("Telefone")
                captacao = st.selectbox("Indicação/Origem", ["Instagram", "Facebook", "Indicação", "Outro"])
            with t2:
                st.subheader("2. Anamnese")
                colA, colB, colC = st.columns(3)
                with colA:
                    st.markdown("**Clínico:**")
                    saude_check = {
                        "Alergia": st.checkbox("Alergias?"),
                        "Medicamentos": st.checkbox("Usa Medicamentos?"),
                        "Trat_Medico": st.checkbox("Tratamento médico?"),
                        "Oncologico": st.checkbox("Hist. Oncológicos?"),
                        "Cardiaco": st.checkbox("Cardíaco/Marcapasso?"),
                        "Hepatite": st.checkbox("Hepatite/Renal?"),
                        "Epilepsia": st.checkbox("Epilepsia?")
                    }
                with colB:
                    st.markdown("**Pele:**")
                    pele_check = {
                        "Queloides": st.checkbox("Quelóides?"),
                        "Foliculite": st.checkbox("Foliculite?"),
                        "Manchas": st.checkbox("Manchas?"),
                        "Psoriase": st.checkbox("Psoríase?"),
                        "Varizes": st.checkbox("Varizes/Trombose?")
                    }
                with colC:
                    st.markdown("**Laser:**")
                    laser_check = {
                        "Depilacao_Ant": st.checkbox("Já fez depilação?"),
                        "Sol": st.checkbox("Sol Recente?"),
                        "Acidos": st.checkbox("Usa Ácidos?"),
                        "Roacutan": st.checkbox("Roacutan?")
                    }
                st.markdown("**Mulher:**")
                cm1, cm2, cm3 = st.columns(3)
                gestante = cm1.checkbox("Gestante/Amamentando?")
                diu = cm2.checkbox("Usa DIU?")
                hormonal = cm3.checkbox("Hormonal?")
                obs_saude = st.text_area("Observações")
            with t3:
                st.subheader("3. Corporal")
                ch1, ch2, ch3 = st.columns(3)
                intestino = ch1.selectbox("Intestino", ["Regular", "Preso", "Irregular"])
                sono = ch2.selectbox("Sono", ["Boa", "Regular", "Ruim"])
                agua = ch3.selectbox("Água", ["Sim (+2L)", "Pouco", "Não"])
                ativ = st.checkbox("Ativ. Física / Fumante / Álcool?")
                
                m1, m2, m3 = st.columns(3)
                with m1:
                    peso = st.number_input("Peso", step=0.1)
                    busto = st.number_input("Busto", step=0.5)
                    braco = st.number_input("Braços", step=0.5)
                with m2:
                    altura = st.number_input("Altura", step=0.01)
                    abd = st.number_input("Abdômen (Sup/Inf)", step=0.5)
                    cintura = st.number_input("Cintura", step=0.5)
                with m3:
                    quadril = st.number_input("Quadril", step=0.5)
                    coxa = st.number_input("Coxas", step=0.5)
                    culote = st.number_input("Culote/Panturrilha", step=0.5)
                biotipo = st.text_input("Biotipo / Queixa")
            with t4:
                st.subheader("4. Facial")
                f1, f2 = st.columns(2)
                lentes = f1.checkbox("Lentes/Cremes?")
                filtro = f2.radio("Filtro Solar?", ["Sim", "Não"], horizontal=True)
                fototipo = st.select_slider("Fototipo", options=["I", "II", "III", "IV", "V", "VI"])
                pele = st.selectbox("Pele", ["Normal", "Seca", "Oleosa", "Mista", "Seborréica", "Acneica"])
                lesoes = st.multiselect("Lesões:", ["Cravos", "Espinhas", "Manchas", "Melasma", "Rugas", "Flacidez", "Olheiras", "Cicatriz", "Vasinhos", "Verrugas"])
                plano_facial = st.text_area("Plano Facial")
            with t5:
                st.subheader("5. Fechamento")
                co1, co2 = st.columns(2)
                dia_orc = co1.date_input("Data", min_value=date.today())
                hora_orc = co2.time_input("Hora", value=time(9,0))
                tratamento = st.text_area("Tratamento")
                v1, v2 = st.columns(2)
                valor = v1.number_input("Total (R$)", min_value=0.0)
                pag = v2.selectbox("Pagamento", ["PIX", "Cartão", "Dinheiro"])
            
            if st.form_submit_button("💾 SALVAR"):
                df_check = carregar_aba(planilha, "agendamentos")
                if verificar_conflito(df_check, dia_orc, hora_orc): st.error("Ocupado!")
                elif not nome: st.warning("Nome!")
                else:
                    pessoais = f"Nasc:{nasc} | CPF:{cpf} | Prof:{prof} | End:{end}"
                    saude_txt = processar_checkboxes({**saude_check, **pele_check, **laser_check})
                    saude_txt += f" | Gest:{gestante}, DIU:{diu}, Horm:{hormonal} | Obs:{obs_saude}"
                    medidas_txt = (f"Peso:{peso} Alt:{altura} Busto:{busto} Braços:{braco} Cint:{cintura} Abd:{abd} Quad:{quadril} Coxas:{coxa} Culote:{culote} | Hab:{intestino},{sono},{agua} | Ativ:{ativ}")
                    facial_txt = (f"Foto:{fototipo} Pele:{pele} | Filtro:{filtro} Lentes:{lentes} | Lesões:{', '.join(lesoes)} | Plano:{plano_facial}")
                    orcamento_txt = f"Trat:{tratamento} | Pag:{pag} | Valor: R$ {valor}"
                    try:
                        planilha.worksheet("agendamentos").append_row([
                            dia_orc.strftime("%d/%m/%Y"), str(hora_orc), nome, tel,
                            pessoais, saude_txt, "Ver Geral", medidas_txt,
                            facial_txt, orcamento_txt, "Completo"
                        ])
                        st.success("Salvo!")
                    except Exception as e: st.error(f"Erro: {e}")

    # === IMPRESSÃO PROFISSIONAL (HTML PURO) ===
    elif menu == "🖨️ Impressão Profissional":
        st.header("🖨️ Seleção de Documento")
        
        # CONTROLES (Não aparecem na impressão graças ao CSS)
        df = carregar_aba(planilha, "agendamentos")
        if df.empty:
            st.info("Nenhuma ficha encontrada.")
            return
        
        st.caption("Selecione o cliente abaixo e pressione Ctrl + P. Tudo isto sumirá e ficará apenas o papel.")
        cli = st.selectbox("Cliente:", df['Nome_Cliente'].unique())
        
        if cli:
            d = df[df['Nome_Cliente'] == cli].iloc[-1]
            
            # Preparar Logo em Base64 para imprimir
            logo_html = ""
            if os.path.exists("logo.png"):
                with open("logo.png", "rb") as f:
                    data = base64.b64encode(f.read()).decode("utf-8")
                    logo_html = f'<img src="data:image/png;base64,{data}" style="max-width:180px; margin-bottom:10px;">'
            
            # --- O DOCUMENTO DE PAPEL (HTML) ---
            html_ficha = f"""
            <div class="ficha-papel">
                <div class="cabecalho">
                    {logo_html}
                    <div class="titulo-doc">Ficha de Avaliação Estética</div>
                    <div style="font-size: 12px; color: #555;">Data do Atendimento: {d['Data']} às {d['Hora']}</div>
                </div>

                <div class="secao">
                    <div class="secao-titulo">1. DADOS CADASTRAIS</div>
                    <div class="conteudo">
                        <b>Nome Completo:</b> {d['Nome_Cliente']} <br>
                        <b>Contato:</b> {d['Contato']} <br>
                        <b>Detalhes:</b> {d['Dados_Pessoais']}
                    </div>
                </div>

                <div class="secao">
                    <div class="secao-titulo">2. HISTÓRICO DE SAÚDE (ANAMNESE)</div>
                    <div class="conteudo">
                        {d['Anamnese_Geral']} <br>
                        <b>Saúde da Mulher / Obs:</b> {d['Saude_Mulher']}
                    </div>
                </div>

                <div class="secao">
                    <div class="secao-titulo">3. AVALIAÇÃO CORPORAL</div>
                    <div class="conteudo">
                        {d['Medidas_Corporais']}
                    </div>
                </div>

                <div class="secao">
                    <div class="secao-titulo">4. AVALIAÇÃO FACIAL</div>
                    <div class="conteudo">
                        {d['Analise_Facial']}
                    </div>
                </div>

                <div class="secao">
                    <div class="secao-titulo">5. PROPOSTA E ORÇAMENTO</div>
                    <div class="conteudo">
                        {d['Orcamento']}
                    </div>
                </div>

                <div class="assinaturas">
                    <div class="campo-ass">Assinatura do(a) Cliente</div>
                    <div class="campo-ass">Assinatura do(a) Profissional</div>
                </div>
                
                <div style="text-align:center; margin-top:20px; font-size:10px; color:#aaa;">
                    Documento gerado eletronicamente pelo Sistema Clínica Andreza Andrade
                </div>
            </div>
            """
            
            # Renderiza o HTML
            st.markdown(html_ficha, unsafe_allow_html=True)

    # === DESPESAS ===
    elif menu == "💸 Registrar Despesa":
        st.header("💸 Saída de Caixa")
        with st.form("despesa"):
            d1, d2 = st.columns(2)
            dt = d1.date_input("Data")
            val = d2.number_input("Valor R$", min_value=0.0)
            desc = st.text_input("Descrição")
            cat = st.selectbox("Categoria", ["Aluguel", "Luz/Água", "Produtos", "Pessoal", "Outros"])
            if st.form_submit_button("Lançar"):
                planilha.worksheet("despesas").append_row([
                    dt.strftime("%d/%m/%Y"), desc, cat, str(val).replace(".", ",")
                ])
                st.success("Lançado!")
        st.dataframe(carregar_aba(planilha, "despesas"))

if __name__ == "__main__":
    main()