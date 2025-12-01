import streamlit as st
import pandas as pd
import gspread
from oauth2client.service_account import ServiceAccountCredentials
from datetime import date, datetime, time
import os

# --- 1. CONFIGURAÇÃO VISUAL & ESTILO DE IMPRESSÃO ---
st.set_page_config(page_title="Gestão Clínica Total", layout="wide", page_icon="💎")

def estilo_impressao():
    # ESSE CÓDIGO FAZ A MÁGICA DE ESCONDER O MENU NA HORA DE IMPRIMIR
    st.markdown("""
        <style>
        @media print {
            /* Esconde o menu lateral, cabeçalho e botões ao imprimir */
            [data-testid="stSidebar"] { display: none !important; }
            [data-testid="stHeader"] { display: none !important; }
            .stApp { margin-top: -80px; } /* Sobe a folha para o topo */
            button { display: none !important; } /* Esconde botões de clique */
            footer { display: none !important; }
            
            /* Garante que o fundo fique branco e texto preto */
            body { color: black; background-color: white; }
            .block-container { padding: 0 !important; }
        }
        </style>
    """, unsafe_allow_html=True)

estilo_impressao()

# --- 2. CONEXÃO GOOGLE SHEETS ---
def conectar_google_sheets():
    scope = ["https://spreadsheets.google.com/feeds", "https://www.googleapis.com/auth/drive"]
    try:
        # Tenta conexão Híbrida (PC ou Nuvem)
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

# --- 3. LÓGICA AUXILIAR ---
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

# --- 4. SISTEMA PRINCIPAL ---
def main():
    with st.sidebar:
        if os.path.exists("logo.png"): st.image("logo.png", width=200)
        elif os.path.exists("logo.jpg"): st.image("logo.jpg", width=200)
        
        st.title("Menu Clínica")
        menu = st.radio("Navegação:", [
            "📊 Painel Financeiro",
            "📅 Agendamento Rápido", 
            "📝 Ficha Completa (PDF Clone)", 
            "🖨️ Central de Impressão",
            "💸 Registrar Despesa"
        ])
        st.success("Sistema V6.3 - Pronta p/ Impressão")

    planilha = conectar_google_sheets()
    if not planilha:
        st.error("Erro de conexão. Verifique 'credentials.json'.")
        return

    # === TELA 1: FINANCEIRO ===
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

    # === TELA 2: AGENDAMENTO ===
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

    # === TELA 3: FICHA COMPLETA ===
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
                st.subheader("2. Anamnese Geral & Laser")
                colA, colB, colC = st.columns(3)
                with colA:
                    st.markdown("**Clínico:**")
                    saude_check = {
                        "Alergia": st.checkbox("Alergias?"),
                        "Medicamentos": st.checkbox("Usa Medicamentos?"),
                        "Trat_Medico": st.checkbox("Em tratamento médico?"),
                        "Oncologico": st.checkbox("Antecedentes Oncológicos?"),
                        "Cardiaco": st.checkbox("Alterações Cardíacas?"),
                        "Marcapasso": st.checkbox("Usa Marcapasso?"),
                        "Hepatite": st.checkbox("Teve Hepatite?"),
                        "Renal": st.checkbox("Problema Renal?"),
                        "Epilepsia": st.checkbox("Epilepsia/Convulsão?")
                    }
                with colB:
                    st.markdown("**Pele & Circulação:**")
                    pele_check = {
                        "Queloides": st.checkbox("Quelóides?"),
                        "Foliculite": st.checkbox("Foliculite?"),
                        "Manchas": st.checkbox("Manchas?"),
                        "Psoriase": st.checkbox("Psoríase/Prob. Pele?"),
                        "Varizes": st.checkbox("Vasos/Varizes?"),
                        "Trombose": st.checkbox("Distúrbio Circulatório?"),
                        "Cicatriza": st.checkbox("Má Cicatrização?")
                    }
                with colC:
                    st.markdown("**Laser & Hábitos:**")
                    laser_check = {
                        "Depilacao_Ant": st.checkbox("Já fez depilação antes?"),
                        "Sol": st.checkbox("Exposição Solar Recente?"),
                        "Bronzeamento": st.checkbox("Usa Bronzeador?"),
                        "Acidos": st.checkbox("Usa Ácidos na pele?"),
                        "Roacutan": st.checkbox("Usou Roacutan (6 meses)?")
                    }
                st.markdown("**Saúde da Mulher:**")
                cm1, cm2, cm3, cm4 = st.columns(4)
                gestante = cm1.checkbox("Gestante?")
                semanas = cm1.text_input("Semanas", "")
                amamentando = cm2.checkbox("Amamentando?")
                diu = cm3.checkbox("Usa DIU?")
                hormonal = cm4.checkbox("Hormonal?")
                obs_saude = st.text_area("Observações")

            with t3:
                st.subheader("3. Medidas & Hábitos")
                ch1, ch2, ch3 = st.columns(3)
                intestino = ch1.selectbox("Intestino", ["Regular", "Preso", "Irregular"])
                sono = ch2.selectbox("Qualidade Sono", ["Boa", "Regular", "Ruim"])
                agua = ch3.selectbox("Ingere Água?", ["Sim (+2L)", "Pouco", "Não"])
                ativ = st.checkbox("Atividade Física?")
                fumante = st.checkbox("Tabagismo?")
                alcool = st.checkbox("Ingere Álcool?")
                
                m1, m2, m3 = st.columns(3)
                with m1:
                    peso = st.number_input("Peso (kg)", step=0.1)
                    busto = st.number_input("Busto", step=0.5)
                    braco_d = st.number_input("Braço Dir", step=0.5)
                    braco_e = st.number_input("Braço Esq", step=0.5)
                with m2:
                    altura = st.number_input("Altura (m)", step=0.01)
                    abd_sup = st.number_input("Abdômen Sup", step=0.5)
                    cintura = st.number_input("Cintura/Umbigo", step=0.5)
                    abd_inf = st.number_input("Abdômen Inf", step=0.5)
                with m3:
                    quadril = st.number_input("Quadril", step=0.5)
                    coxa_d = st.number_input("Coxa Dir", step=0.5)
                    coxa_e = st.number_input("Coxa Esq", step=0.5)
                    culote = st.number_input("Culote", step=0.5)
                biotipo = st.radio("Biotipo", ["Ginóide", "Andróide", "Normolíneo"], horizontal=True)
                queixa_corp = st.text_area("Queixa Corporal")

            with t4:
                st.subheader("4. Facial")
                f1, f2 = st.columns(2)
                lentes = f1.checkbox("Lentes de Contato?")
                cremes = f2.checkbox("Usa Cremes?")
                filtro = st.radio("Filtro Solar?", ["Sim", "Às vezes", "Não"], horizontal=True)
                
                col_pele1, col_pele2 = st.columns(2)
                with col_pele1:
                    fototipo = st.select_slider("Fototipo", options=["I", "II", "III", "IV", "V", "VI"])
                    tipo_pele = st.selectbox("Pele", ["Eudérmica", "Alípica", "Lipídica", "Mista", "Seborréica"])
                    hidratacao = st.selectbox("Hidratação", ["Hidratada", "Desidratada"])
                with col_pele2:
                    espessura = st.selectbox("Espessura", ["Fina", "Muito Fina", "Espessa"])
                    ostios = st.selectbox("Óstios", ["Contraídos", "Dilatados"])
                    acne_grau = st.selectbox("Acne", ["Não tem", "Grau I", "Grau II", "Grau III", "Grau IV"])

                lesoes = st.multiselect("Lesões:", [
                    "Comedões (Cravos)", "Millium", "Pápulas", "Pústulas", "Cistos", 
                    "Manchas Hiper", "Manchas Hipo", "Melasma", "Efélides",
                    "Rugas", "Flacidez", "Olheiras", "Cicatriz Acne", "Telangiectasias",
                    "Nevos", "Verrugas", "Xantelasma", "Hirsutismo", "Queratose", "Vibices", "Ptose"
                ])
                plano_facial = st.text_area("Plano Facial")

            with t5:
                st.subheader("5. Fechamento")
                co1, co2 = st.columns(2)
                dia_orc = co1.date_input("Data", min_value=date.today())
                hora_orc = co2.time_input("Hora", value=time(9,0))
                tratamento = st.text_area("Tratamento")
                v1, v2 = st.columns(2)
                valor = v1.number_input("Total (R$)", min_value=0.0)
                pag = v2.selectbox("Pagamento", ["PIX", "Cartão Crédito", "Cartão Débito", "Dinheiro", "Parcelado"])

            if st.form_submit_button("💾 SALVAR"):
                df_check = carregar_aba(planilha, "agendamentos")
                if verificar_conflito(df_check, dia_orc, hora_orc): st.error("Horário Ocupado!")
                elif not nome: st.warning("Preencha Nome!")
                else:
                    pessoais = f"Nasc:{nasc} | CPF:{cpf} | Prof:{prof} | End:{end} | Origem:{captacao}"
                    saude_txt = processar_checkboxes({**saude_check, **pele_check, **laser_check})
                    saude_txt += f" | Gest:{gestante}({semanas}), DIU:{diu}, Horm:{hormonal} | Obs:{obs_saude}"
                    habitos_txt = f"Intest:{intestino}, Sono:{sono}, Água:{agua}, Ativ:{ativ}, Fum:{fumante}"
                    medidas_txt = (f"Peso:{peso} Alt:{altura} Busto:{busto} Braços:{braco_d}/{braco_e} "
                                   f"Cint:{cintura} Abd:{abd_sup}/{abd_inf} Quad:{quadril} Culote:{culote} "
                                   f"Coxas:{coxa_d}/{coxa_e} | Bio:{biotipo} | Hábitos: {habitos_txt}")
                    facial_txt = (f"Foto:{fototipo} Pele:{tipo_pele} Hidra:{hidratacao} Esp:{espessura} "
                                  f"Acne:{acne_grau} Poros:{ostios} | Filtro:{filtro} Lentes:{lentes} | "
                                  f"Lesões: {', '.join(lesoes)} | Plano: {plano_facial}")
                    orcamento_txt = f"Trat:{tratamento} | Pag:{pag} | Valor: R$ {valor}"

                    try:
                        planilha.worksheet("agendamentos").append_row([
                            dia_orc.strftime("%d/%m/%Y"), str(hora_orc), nome, tel,
                            pessoais, saude_txt, "Ver Geral", medidas_txt,
                            facial_txt, orcamento_txt, "Completo"
                        ])
                        st.balloons()
                        st.success("Salvo!")
                    except Exception as e: st.error(f"Erro: {e}")

    # === TELA 4: IMPRESSÃO ===
    elif menu == "🖨️ Central de Impressão":
        st.header("🖨️ Fichas para Imprimir")
        df = carregar_aba(planilha, "agendamentos")
        if not df.empty:
            st.dataframe(df)
            cli = st.selectbox("Selecione Cliente:", df['Nome_Cliente'].unique())
            if cli:
                d = df[df['Nome_Cliente'] == cli].iloc[-1]
                with st.container(border=True):
                    c_img, c_tit = st.columns([1, 4])
                    with c_img:
                        if os.path.exists("logo.png"): st.image("logo.png", width=100)
                    with c_tit:
                        st.markdown("## FICHA DE AVALIAÇÃO ESTÉTICA")
                    
                    st.markdown("---")
                    st.markdown(f"**Data:** {d.get('Data')} | **Cliente:** {d.get('Nome_Cliente')}")
                    st.markdown(f"**Dados:** {d.get('Dados_Pessoais')}")
                    
                    st.markdown("### 🏥 SAÚDE & HISTÓRICO")
                    st.info(d.get('Anamnese_Geral'))
                    
                    st.markdown("### 📏 CORPORAL & HÁBITOS")
                    st.warning(d.get('Medidas_Corporais'))
                    
                    st.markdown("### ✨ FACIAL & PELE")
                    st.success(d.get('Analise_Facial'))
                    
                    st.markdown("### 💰 ORÇAMENTO")
                    st.markdown(f"**{d.get('Orcamento')}**")
                    st.markdown("\n\n______________________\nAssinatura")
                st.info("Pressione Ctrl + P (O menu lateral irá sumir na impressão!)")

    # === TELA 5: DESPESAS ===
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