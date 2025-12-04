import streamlit as st
import pandas as pd
import gspread
from oauth2client.service_account import ServiceAccountCredentials
from datetime import date, datetime, time
import os
import base64
import time as t

# --- 1. CONFIGURAÇÃO (AQUI ESTÁ A MUDANÇA DO ÍCONE) ---
# Se o nome do arquivo na sua pasta for diferente de LOGO.png, ajuste aqui.
st.set_page_config(page_title="Sistema Clínica", layout="wide", page_icon="LOGO.png")

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
    .aviso-ok { background-color: #d4edda; color: #155724; padding: 10px; border-radius: 5px; }
    </style>
""", unsafe_allow_html=True)

# --- 2. CONEXÃO ---
def conectar():
    try:
        # Tenta conectar via Secrets (Nuvem)
        if "gcp_service_account" in st.secrets:
            scope = ["https://spreadsheets.google.com/feeds", "https://www.googleapis.com/auth/drive"]
            creds = ServiceAccountCredentials.from_json_keyfile_dict(dict(st.secrets["gcp_service_account"]), scope)
            client = gspread.authorize(creds)
            return client.open("sistema_clinica")
    except: pass

    try:
        # Tenta conectar via Arquivo Local (PC)
        pasta = os.path.dirname(os.path.abspath(__file__))
        caminho = os.path.join(pasta, "credentials.json")
        scope = ["https://spreadsheets.google.com/feeds", "https://www.googleapis.com/auth/drive"]
        creds = ServiceAccountCredentials.from_json_keyfile_name(caminho, scope)
        client = gspread.authorize(creds)
        return client.open("sistema_clinica")
    except Exception as e:
        return None

def carregar_dados(planilha, aba):
    try:
        ws = planilha.worksheet(aba)
        dados = ws.get_all_values()
        if len(dados) < 2: return pd.DataFrame()
        
        # Limpeza de Colunas
        cabecalho = dados[0]
        idx_validos = [i for i, nome in enumerate(cabecalho) if nome.strip() != ""]
        cols_limpas = [cabecalho[i] for i in idx_validos]
        
        linhas_limpas = []
        for linha in dados[1:]:
            linha += [""] * (len(cabecalho) - len(linha))
            linhas_limpas.append([linha[i] for i in idx_validos])
            
        return pd.DataFrame(linhas_limpas, columns=cols_limpas)
    except: return pd.DataFrame()

def get_logo():
    pasta = os.path.dirname(os.path.abspath(__file__))
    for n in ["LOGO.png", "logo.png"]:
        path = os.path.join(pasta, n)
        if os.path.exists(path):
            with open(path, "rb") as f:
                b64 = base64.b64encode(f.read()).decode()
            return f'<img src="data:image/png;base64,{b64}" style="max-height:80px; display:block; margin:0 auto;">'
    return ""

def get_val(linha, chaves):
    for k in linha.index:
        for c in chaves:
            if c.lower() in k.lower(): return str(linha[k])
    return ""

def lista_checks(dic):
    return ", ".join([k for k, v in dic.items() if v])

# --- 3. APP ---
def main():
    st.sidebar.title("🏥 Menu")
    menu = st.sidebar.radio("Ir para:", ["📅 Agenda", "📝 Ficha Completa", "🖨️ Impressão", "📊 Financeiro", "💸 Despesas"])
    logo = get_logo()
    
    planilha = conectar()
    if not planilha:
        st.error("Erro de conexão. Verifique a chave.")
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
        with st.form("age"):
            c1, c2 = st.columns(2)
            n = c1.text_input("Nome")
            z = c2.text_input("WhatsApp")
            c3, c4 = st.columns(2)
            d = c3.date_input("Data", value=date.today())
            h = c4.time_input("Hora", value=time(9,0))
            if st.form_submit_button("Agendar"):
                planilha.worksheet("agendamentos").append_row([d.strftime("%d/%m/%Y"), str(h), n, z, "", "", "", "", "", "", "Agendado"])
                st.success("Salvo!")
                t.sleep(1)
                st.rerun()

    # === FICHA ===
    elif menu == "📝 Ficha Completa":
        st.title("📝 Ficha")
        df = carregar_dados(planilha, "agendamentos")
        
        vn, vt, van, vsa, vco, vfa = "", "", "", "", "", ""
        
        st.markdown("##### 🔍 Selecione o Cliente")
        lst = []
        col_nome = ""
        if not df.empty:
            for c in df.columns:
                if "nome" in c.lower():
                    lst = df[c].unique().tolist()
                    col_nome = c
                    break
        
        sel = st.selectbox("Cliente:", ["..."] + lst)
        
        if sel != "..." and col_nome:
            dcli = df[df[col_nome] == sel]
            ult = dcli.iloc[-1]
            vn = str(ult[col_nome])
            vt = get_val(ult, ["contato", "tel"])
            
            for i in range(len(dcli)-1, -1, -1):
                row = dcli.iloc[i]
                if not van: van = get_val(row, ["anamnese"])
                if not vsa: vsa = get_val(row, ["saude", "mulher"])
                if not vco: vco = get_val(row, ["medidas", "corporal"])
                if not vfa: vfa = get_val(row, ["facial"])
            
            if van or vsa: st.markdown('<div class="aviso-ok">✅ Histórico carregado!</div>', unsafe_allow_html=True)

        with st.form("ficha"):
            t1, t2, t3, t4, t5 = st.tabs(["Pessoais", "Saúde", "Corporal", "Facial", "Orçamento"])
            with t1:
                c1, c2 = st.columns(2)
                nm = c1.text_input("Nome", value=vn)
                tl = c2.text_input("Tel", value=vt)
                c3, c4 = st.columns(2)
                dt = c3.text_input("Nascimento")
                pf = c4.text_input("Profissão")
            with t2:
                c1, c2 = st.columns(2)
                ck = {"Alergia": c1.checkbox("Alergia"), "Remédios": c2.checkbox("Remédios"), "Gestante": c1.checkbox("Gestante"), "Sol": c2.checkbox("Sol")}
                osa = st.text_area("Obs Saúde", value=van)
            with t3:
                oco = st.text_input("Obs Corporal", value=vco)
                m1, m2 = st.columns(2)
                pes = m1.number_input("Peso", step=0.1)
                alt = m2.number_input("Altura", step=0.01)
            with t4:
                ofa = st.text_area("Facial", value=vfa)
            with t5:
                tr = st.text_input("Tratamento")
                pg = st.selectbox("Pagamento", ["PIX", "Cartão", "Dinheiro"])
                vl = st.number_input("Valor", step=10.0)
            
            if st.form_submit_button("Salvar"):
                pess = f"Nasc:{dt} Prof:{pf}"
                chk_txt = lista_checks(ck)
                ana_fin = f"Checks:{chk_txt} | {osa}"
                med_fin = f"Peso:{pes} Alt:{alt} | {oco}"
                orc_fin = f"Trat:{tr} Pag:{pg} Val:{vl}"
                
                planilha.worksheet("agendamentos").append_row([
                    date.today().strftime("%d/%m/%Y"), datetime.now().strftime("%H:%M"),
                    nm, tl, pess, ana_fin, osa, med_fin, ofa, orc_fin, "Completo"
                ])
                st.success("Salvo!")
                t.sleep(1)
                st.rerun()

    # === IMPRESSÃO ===
    elif menu == "🖨️ Impressão":
        st.title("🖨️ Imprimir")
        df = carregar_dados(planilha, "agendamentos")
        lst = []
        col_n = ""
        if not df.empty:
            for c in df.columns:
                if "nome" in c.lower():
                    lst = df[c].unique().tolist()
                    col_n = c
                    break
        
        sel = st.selectbox("Cliente:", ["..."] + lst)
        
        if sel != "..." and col_n:
            d = df[df[col_n] == sel].iloc[-1]
            
            html = f"""
            <div class="folha-impressao">
                <div style="text-align:center;">
                    {logo}
                    <h3>FICHA DE AVALIAÇÃO</h3>
                    <small>{d.get('Data', '')}</small>
                </div>
                <br>
                <div style="border-bottom:1px solid #ccc; padding:5px;"><b>1. DADOS:</b> {d.get(col_n)} | {get_val(d, ['contato'])} <br> {get_val(d, ['dados'])}</div>
                <div style="border-bottom:1px solid #ccc; padding:5px;"><b>2. SAÚDE:</b> {get_val(d, ['anamnese'])} <br> {get_val(d, ['saude'])}</div>
                <div style="border-bottom:1px solid #ccc; padding:5px;"><b>3. CORPO/FACE:</b> {get_val(d, ['medidas'])} <br> {get_val(d, ['facial'])}</div>
                <div style="border-bottom:1px solid #ccc; padding:5px;"><b>4. ORÇAMENTO:</b> {get_val(d, ['orcamento'])}</div>
                <br><br><br>
                <center>__________________________<br>Assinatura</center>
            </div>
            """
            st.markdown(html, unsafe_allow_html=True)
            st.info("Aperte Ctrl + P. Na janela que abrir, mude 'Destino' para sua Impressora.")

    # === FINANCEIRO ===
    elif menu == "📊 Financeiro":
        st.header("📊 Fluxo de Caixa")
        df_ag = carregar_dados(planilha, "agendamentos")
        df_dp = carregar_dados(planilha, "despesas")
        
        ent = 0.0
        sai = 0.0
        
        # Calcula Entradas
        if not df_ag.empty:
            for col in df_ag.columns:
                if "orcamento" in col.lower():
                    for item in df_ag[col].astype(str):
                        if "Val:" in item:
                            try:
                                v = item.split("Val:")[1].strip()
                                ent += float(v.replace(",", "."))
                            except: pass
                        elif "Valor:" in item:
                             try:
                                v = item.split("R$")[1].strip()
                                ent += float(v.replace(",", "."))
                             except: pass

        # Calcula Saídas
        if not df_dp.empty:
            for col in df_dp.columns:
                if "valor" in col.lower():
                    for item in df_dp[col].astype(str):
                        try:
                            sai += float(item.replace(",", "."))
                        except: pass

        c1, c2, c3 = st.columns(3)
        c1.metric("💰 Entradas", f"R$ {ent:,.2f}")
        c2.metric("💸 Saídas", f"R$ {sai:,.2f}")
        c3.metric("📈 Lucro", f"R$ {ent - sai:,.2f}")

    # === DESPESAS ===
    elif menu == "💸 Despesas":
        st.title("Despesas")
        with st.form("dp"):
            v = st.number_input("Valor", min_value=0.0)
            d = st.text_input("Desc")
            if st.form_submit_button("Salvar"):
                planilha.worksheet("despesas").append_row([date.today().strftime("%d/%m/%Y"), d, "Geral", str(v)])
                st.success("Salvo!")
        st.dataframe(carregar_dados(planilha, "despesas"))

if __name__ == "__main__":
    main()