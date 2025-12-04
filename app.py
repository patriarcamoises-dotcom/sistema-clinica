import streamlit as st
import pandas as pd
import gspread
from oauth2client.service_account import ServiceAccountCredentials
from datetime import date, datetime, time
import os
import base64
import urllib.parse
import time as t

# --- 1. CONFIGURAÇÃO ---
st.set_page_config(page_title="Sistema Clínica", layout="wide", page_icon="🏥")

st.markdown("""
    <meta name="google" content="notranslate">
    <style>
    #MainMenu {visibility: hidden;}
    footer {visibility: hidden;}
    
    @media print {
        body * { visibility: hidden; }
        .folha-impressao, .folha-impressao * { visibility: visible; }
        .folha-impressao { position: absolute; left: 0; top: 0; width: 100%; }
        [data-testid="stSidebar"] { display: none !important; }
    }
    .folha-impressao { 
        background-color: white; padding: 40px; border: 1px solid #ddd; 
        font-family: 'Arial', sans-serif; color: black; margin-top: 20px;
    }
    .aviso-ok { background-color: #d4edda; color: #155724; padding: 10px; border-radius: 5px; margin-bottom: 10px; }
    </style>
""", unsafe_allow_html=True)

# --- 2. CONEXÃO HÍBRIDA (FUNCIONA NO PC E NA NUVEM) ---
def conectar():
    # TENTATIVA 1: NUVEM (Streamlit Secrets)
    try:
        if "gcp_service_account" in st.secrets:
            scope = ["https://spreadsheets.google.com/feeds", "https://www.googleapis.com/auth/drive"]
            creds = ServiceAccountCredentials.from_json_keyfile_dict(dict(st.secrets["gcp_service_account"]), scope)
            client = gspread.authorize(creds)
            return client.open("sistema_clinica")
    except:
        pass # Se falhar, tenta o modo local

    # TENTATIVA 2: LOCAL (Arquivo no PC)
    try:
        pasta = os.path.dirname(os.path.abspath(__file__))
        caminho = os.path.join(pasta, "credentials.json")
        scope = ["https://spreadsheets.google.com/feeds", "https://www.googleapis.com/auth/drive"]
        creds = ServiceAccountCredentials.from_json_keyfile_name(caminho, scope)
        client = gspread.authorize(creds)
        return client.open("sistema_clinica")
    except Exception as e:
        st.error(f"❌ Erro de Conexão: {e}")
        return None

def carregar_dados(planilha, aba):
    try:
        ws = planilha.worksheet(aba)
        dados = ws.get_all_values()
        if len(dados) < 2: return pd.DataFrame()
        cabecalho = dados[0]
        indices = [i for i, nome in enumerate(cabecalho) if nome.strip() != ""]
        cab_limpo = [cabecalho[i] for i in indices]
        linhas = [[linha[i] if i < len(linha) else "" for i in indices] for linha in dados[1:]]
        return pd.DataFrame(linhas, columns=cab_limpo)
    except: return pd.DataFrame()

def carregar_logo_html():
    # Tenta achar logo local (PC)
    pasta = os.path.dirname(os.path.abspath(__file__))
    # Tenta vários nomes comuns
    for nome in ["LOGO.png", "logo.png", "Logo.png"]:
        caminho = os.path.join(pasta, nome)
        if os.path.exists(caminho):
            with open(caminho, "rb") as f:
                b64 = base64.b64encode(f.read()).decode()
            return f'<img src="data:image/png;base64,{b64}" style="max-height:80px; display:block; margin:0 auto;">'
    return ""

def processar_checks(dicionario):
    return ", ".join([k for k, v in dicionario.items() if v])

def get_valor(linha, chaves):
    for k in linha.index:
        for c in chaves:
            if c.lower() in k.lower(): return str(linha[k])
    return ""

# --- 3. PROGRAMA PRINCIPAL ---
def main():
    st.sidebar.title("🏥 Menu")
    menu = st.sidebar.radio("Ir para:", ["📅 Agenda", "📝 Ficha Completa", "🖨️ Impressão", "📊 Financeiro", "💸 Despesas"])
    
    # Logo na barra lateral (se existir)
    logo_html = carregar_logo_html()
    
    if st.sidebar.button("🔄 Recarregar"): st.rerun()

    planilha = conectar()
    if not planilha: 
        st.warning("⚠️ Não consegui conectar na planilha. Verifique as credenciais.")
        st.stop()

    # === AGENDA ===
    if menu == "📅 Agenda":
        st.title("📅 Agenda")
        df = carregar_dados(planilha, "agendamentos")
        
        if not df.empty:
            busca = st.text_input("🔎 Pesquisar:")
            if busca:
                st.dataframe(df[df.astype(str).apply(lambda x: x.str.contains(busca, case=False)).any(axis=1)], use_container_width=True)
            else:
                st.dataframe(df, use_container_width=True)
        
        st.divider()
        st.subheader("Novo Agendamento")
        with st.form("agenda"):
            c1, c2 = st.columns(2)
            nome = c1.text_input("Nome")
            zap = c2.text_input("WhatsApp")
            c3, c4 = st.columns(2)
            dia = c3.date_input("Data", value=date.today())
            hora = c4.time_input("Hora", value=time(9,0))
            if st.form_submit_button("Salvar"):
                planilha.worksheet("agendamentos").append_row([
                    dia.strftime("%d/%m/%Y"), str(hora), nome, zap, 
                    "-", "-", "-", "-", "-", "-", "Agendado"
                ])
                st.success("Salvo!")
                t.sleep(1)
                st.rerun()

    # === FICHA COMPLETA ===
    elif menu == "📝 Ficha Completa":
        st.title("📝 Avaliação Detalhada")
        df = carregar_dados(planilha, "agendamentos")
        
        v_nome, v_tel, v_anam, v_saude, v_corp, v_facial = "", "", "", "", "", ""

        st.markdown("##### 🔍 1. Selecione o Cliente")
        lista_nomes = []
        col_nome_real = ""
        if not df.empty:
            for c in df.columns:
                if "nome" in c.lower():
                    lista_nomes = df[c].unique().tolist()
                    col_nome_real = c
                    break
        
        if not lista_nomes:
            sel = st.selectbox("Cliente:", ["..."])
        else:
            sel = st.selectbox("Digite ou selecione:", ["..."] + lista_nomes)

        if sel != "..." and col_nome_real:
            d_cli = df[df[col_nome_real] == sel]
            ultimo = d_cli.iloc[-1]
            v_nome = str(ultimo[col_nome_real])
            v_tel = get_valor(ultimo, ["contato", "tel", "zap"])
            
            for i in range(len(d_cli)-1, -1, -1):
                linha = d_cli.iloc[i]
                if not v_anam: v_anam = get_valor(linha, ["anamnese"])
                if not v_saude: v_saude = get_valor(linha, ["saude", "mulher"])
                if not v_corp: v_corp = get_valor(linha, ["medidas", "corporal"])
                if not v_facial: v_facial = get_valor(linha, ["facial", "analise"])
            
            if v_anam or v_saude:
                st.markdown(f'<div class="aviso-ok">✅ Histórico carregado!</div>', unsafe_allow_html=True)

        with st.form("ficha"):
            t1, t2, t3, t4, t5 = st.tabs(["Pessoais", "Saúde/Laser", "Corporal", "Facial", "Orçamento"])
            with t1:
                c1, c2 = st.columns(2)
                nome = c1.text_input("Nome", value=v_nome)
                tel = c2.text_input("Telefone", value=v_tel)
                c3, c4 = st.columns(2)
                nasc = c3.text_input("Data Nascimento")
                prof = c4.text_input("Profissão / CPF")
            with t2:
                st.markdown("**Histórico Clínico:**")
                ca, cb, cc = st.columns(3)
                check_saude = {
                    "Alergia": ca.checkbox("Alergias"), "Medicamentos": cb.checkbox("Usa Medicamentos"), "Trat. Médico": cc.checkbox("Tratamento Médico"),
                    "Oncológico": ca.checkbox("Hist. Oncológico"), "Cardíaco": cb.checkbox("Cardíaco/Marcapasso"), "Gestante": cc.checkbox("Gestante"),
                    "DIU": ca.checkbox("Usa DIU"), "Hormonal": cb.checkbox("Alteração Hormonal"), "Sol": cc.checkbox("Sol Recente")
                }
                obs_saude = st.text_area("Obs. Saúde / Queixas", value=v_anam, height=100)
            with t3:
                st.markdown("**Medidas Corporais:**")
                m1, m2, m3 = st.columns(3)
                peso = m1.number_input("Peso (kg)", step=0.1)
                alt = m2.number_input("Altura (m)", step=0.01)
                busto = m3.number_input("Busto (cm)", step=1.0)
                m4, m5, m6 = st.columns(3)
                cint = m4.number_input("Cintura (cm)", step=1.0)
                abd = m5.number_input("Abdômen (cm)", step=1.0)
                quad = m6.number_input("Quadril (cm)", step=1.0)
                m7, m8, m9 = st.columns(3)
                coxa = m7.number_input("Coxas (cm)", step=1.0)
                culote = m8.number_input("Culote (cm)", step=1.0)
                braco = m9.number_input("Braços (cm)", step=1.0)
                obs_corp = st.text_input("Obs Corporal", value=v_corp)
            with t4:
                st.markdown("**Facial:**")
                f1, f2 = st.columns(2)
                fototipo = f1.select_slider("Fototipo", ["I", "II", "III", "IV", "V"])
                pele = f2.selectbox("Pele", ["Normal", "Seca", "Mista", "Oleosa", "Acneica"])
                check_face = {
                    "Manchas": st.checkbox("Manchas/Melasma"), "Acne": st.checkbox("Acne Ativa"), "Rugas": st.checkbox("Rugas"),
                    "Cicatriz": st.checkbox("Cicatrizes"), "Flacidez": st.checkbox("Flacidez Facial")
                }
                obs_facial = st.text_area("Avaliação Facial", value=v_facial)
            with t5:
                c1, c2 = st.columns(2)
                trat = c1.text_input("Tratamento")
                val = c2.number_input("Valor R$", step=10.0)
                pag = st.selectbox("Pagamento", ["PIX", "Cartão", "Dinheiro"])

            if st.form_submit_button("💾 SALVAR TUDO"):
                pessoal_txt = f"Nasc:{nasc} Prof:{prof}"
                checks_txt = processar_checks(check_saude)
                anamnese_fin = f"Checks:{checks_txt} | Queixa:{obs_saude}"
                saude_fin = f"Detalhes:{obs_saude}" 
                medidas_fin = f"Peso:{peso} Alt:{alt} Busto:{busto} Cint:{cint} Abd:{abd} Quad:{quad} | Obs:{obs_corp}"
                face_checks = processar_checks(check_face)
                face_fin = f"Foto:{fototipo} Pele:{pele} | {face_checks} | {obs_facial}"
                orc_fin = f"Trat:{trat} Pag:{pag} Val:{val}"
                
                planilha.worksheet("agendamentos").append_row([
                    date.today().strftime("%d/%m/%Y"), datetime.now().strftime("%H:%M"),
                    nome, tel, pessoal_txt, anamnese_fin, saude_fin, 
                    medidas_fin, face_fin, orc_fin, "Completo"
                ])
                st.success("Salvo com sucesso!")
                t.sleep(1)
                st.rerun()

    # === IMPRESSÃO ===
    elif menu == "🖨️ Impressão":
        st.title("🖨️ Gerar PDF")
        df = carregar_dados(planilha, "agendamentos")
        
        st.markdown("##### Selecione o Cliente:")
        lista = []
        col_nome = ""
        if not df.empty:
            for c in df.columns:
                if "nome" in c.lower():
                    lista = df[c].unique().tolist()
                    col_nome = c
                    break
        
        sel = st.selectbox("Cliente:", ["..."] + lista)
        
        if sel != "..." and col_nome:
            d = df[df[col_nome] == sel].iloc[-1]
            img_tag = carregar_logo_html()
            
            html = f"""
            <div class="folha-impressao">
                <div style="text-align:center;">
                    {img_tag}
                    <div class="titulo-imp">FICHA DE AVALIAÇÃO</div>
                    <small>Data: {d.get('Data', '')}</small>
                </div>
                
                <div class="secao-imp">1. Dados Pessoais</div>
                <div class="texto-imp">
                    <b>Cliente:</b> {d.get(col_nome, '')} | <b>Contato:</b> {get_valor(d, ['contato', 'tel'])} <br>
                    <b>Info:</b> {get_valor(d, ['dados', 'pessoais'])}
                </div>

                <div class="secao-imp">2. Anamnese e Saúde</div>
                <div class="texto-imp">
                    {get_valor(d, ['anamnese'])} <br>
                    {get_valor(d, ['saude', 'mulher'])}
                </div>

                <div class="secao-imp">3. Corporal e Facial</div>
                <div class="texto-imp">
                    <b>Corporal:</b> {get_valor(d, ['medidas', 'corporal'])} <br>
                    <b>Facial:</b> {get_valor(d, ['facial', 'analise'])}
                </div>

                <div class="secao-imp">4. Orçamento</div>
                <div class="texto-imp">{get_valor(d, ['orcamento'])}</div>

                <br><br><br><br>
                <div style="display:flex; justify-content:space-between;">
                    <div style="border-top:1px solid #000; width:40%; text-align:center;">Assinatura Cliente</div>
                    <div style="border-top:1px solid #000; width:40%; text-align:center;">Profissional</div>
                </div>
            </div>
            """
            st.markdown(html, unsafe_allow_html=True)
            st.info("Pressione Ctrl + P para salvar como PDF")

    # === DESPESAS ===
    elif menu == "💸 Despesas":
        st.title("Despesas")
        with st.form("desp"):
            v = st.number_input("Valor")
            d = st.text_input("Descrição")
            if st.form_submit_button("Salvar"):
                planilha.worksheet("despesas").append_row([date.today().strftime("%d/%m/%Y"), d, "Geral", str(v)])
                st.success("Ok!")
        st.dataframe(carregar_dados(planilha, "despesas"), use_container_width=True)

if __name__ == "__main__":
    main()
