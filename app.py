import streamlit as st
import pandas as pd
import gspread
from oauth2client.service_account import ServiceAccountCredentials
from datetime import date, datetime, time
import os
import base64
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
    .aviso-ok { background-color: #d4edda; color: #155724; padding: 10px; border-radius: 5px; margin-bottom: 15px;}
    </style>
""", unsafe_allow_html=True)

# --- 2. CONEXÃO ---
def conectar():
    try:
        if "gcp_service_account" in st.secrets:
            scope = ["https://spreadsheets.google.com/feeds", "https://www.googleapis.com/auth/drive"]
            creds = ServiceAccountCredentials.from_json_keyfile_dict(dict(st.secrets["gcp_service_account"]), scope)
            client = gspread.authorize(creds)
            return client.open("sistema_clinica")
    except: pass

    try:
        pasta = os.path.dirname(os.path.abspath(__file__))
        caminho = os.path.join(pasta, "credentials.json")
        scope = ["https://spreadsheets.google.com/feeds", "https://www.googleapis.com/auth/drive"]
        creds = ServiceAccountCredentials.from_json_keyfile_name(caminho, scope)
        client = gspread.authorize(creds)
        return client.open("sistema_clinica")
    except Exception as e: return None

def carregar_dados(planilha, aba):
    try:
        ws = planilha.worksheet(aba)
        dados = ws.get_all_values()
        if len(dados) < 2: return pd.DataFrame()
        cabecalho = dados[0]
        idx_validos = [i for i, nome in enumerate(cabecalho) if nome.strip() != ""]
        cols_limpas = [cabecalho[i] for i in idx_validos]
        linhas_limpas = []
        for linha in dados[1:]:
            linha += [""] * (len(cabecalho) - len(linha))
            linhas_limpas.append([linha[i] for i in idx_validos])
        return pd.DataFrame(linhas_limpas, columns=cols_limpas)
    except: return pd.DataFrame()

# Função para encontrar o arquivo da logo (caminho)
def get_logo_path():
    pasta = os.path.dirname(os.path.abspath(__file__))
    for n in ["LOGO.png", "logo.png", "Logo.png"]:
        path = os.path.join(pasta, n)
        if os.path.exists(path): return path
    return None

# Função para converter a logo em HTML para impressão
def get_logo_html(path):
    if path and os.path.exists(path):
        with open(path, "rb") as f:
            b64 = base64.b64encode(f.read()).decode()
        return f'<img src="data:image/png;base64,{b64}" style="max-height:100px; display:block; margin:0 auto;">'
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
    # --- BARRA LATERAL (MENU) ---
    logo_path = get_logo_path()
    
    with st.sidebar:
        # 1. MOSTRA A LOGO NO TOPO DO MENU
        if logo_path:
            st.image(logo_path, use_container_width=True)
        else:
            st.title("🏥 Clínica")
            
        st.header("Menu Principal")
        menu = st.radio("Ir para:", ["📅 Agenda", "📝 Ficha Completa", "🖨️ Impressão", "📊 Financeiro", "💸 Despesas"])
        st.divider()
        if st.button("🔄 Recarregar Sistema"): st.rerun()

    planilha = conectar()
    if not planilha: st.error("Erro Conexão"); st.stop()

    # === AGENDA ===
    if menu == "📅 Agenda":
        st.title("📅 Agenda")
        df = carregar_dados(planilha, "agendamentos")
        if not df.empty:
            busca = st.text_input("🔎 Pesquisar:")
            if busca: st.dataframe(df[df.astype(str).apply(lambda x: x.str.contains(busca, case=False)).any(axis=1)], use_container_width=True)
            else: st.dataframe(df, use_container_width=True)
        st.divider()
        with st.form("age"):
            c1,c2=st.columns(2)
            n=c1.text_input("Nome"); z=c2.text_input("WhatsApp")
            c3,c4=st.columns(2)
            d=c3.date_input("Data", value=date.today()); h=c4.time_input("Hora", value=time(9,0))
            if st.form_submit_button("Agendar"):
                planilha.worksheet("agendamentos").append_row([d.strftime("%d/%m/%Y"), str(h), n, z, "", "", "", "", "", "", "Agendado"])
                st.success("Salvo!"); t.sleep(1); st.rerun()

    # === FICHA ===
    elif menu == "📝 Ficha Completa":
        st.title("📝 Ficha Detalhada")
        df = carregar_dados(planilha, "agendamentos")
        vn, vt, van, vsa, vco, vfa = "", "", "", "", "", ""
        
        st.markdown("##### 🔍 Selecione o Cliente")
        lst = []
        col_nome = ""
        if not df.empty:
            for c in df.columns:
                if "nome" in c.lower(): lst=df[c].unique().tolist(); col_nome=c; break
        
        sel = st.selectbox("Cliente:", ["..."]+lst)
        if sel != "..." and col_nome:
            dcli = df[df[col_nome] == sel]
            ult = dcli.iloc[-1]
            vn = str(ult[col_nome]); vt = get_val(ult, ["contato", "tel"])
            for i in range(len(dcli)-1, -1, -1):
                row = dcli.iloc[i]
                if not van: van=get_val(row, ["anamnese"])
                if not vsa: vsa=get_val(row, ["saude", "mulher"])
                if not vco: vco=get_val(row, ["medidas", "corporal"])
                if not vfa: vfa=get_val(row, ["facial"])
            if van or vsa: st.markdown('<div class="aviso-ok">✅ Histórico carregado!</div>', unsafe_allow_html=True)

        with st.form("ficha"):
            t1, t2, t3, t4, t5 = st.tabs(["Pessoais", "Saúde/Laser", "Corporal", "Facial", "Orçamento"])
            
            with t1:
                c1,c2=st.columns(2)
                nm=c1.text_input("Nome", value=vn); tl=c2.text_input("Tel", value=vt)
                c3,c4=st.columns(2)
                dt=c3.text_input("Nascimento"); pf=c4.text_input("Profissão/CPF")
            
            with t2:
                st.markdown("**Histórico Clínico:**")
                ca,cb,cc = st.columns(3)
                ck = {
                    "Alergia": ca.checkbox("Alergias"), "Remédios": cb.checkbox("Usa Medicamentos"), "Trat. Médico": cc.checkbox("Trat. Médico"),
                    "Oncológico": ca.checkbox("Hist. Oncológico"), "Cardíaco": cb.checkbox("Cardíaco/Marcapasso"), "Gestante": cc.checkbox("Gestante"),
                    "DIU": ca.checkbox("Usa DIU"), "Hormonal": cb.checkbox("Alt. Hormonal"), "Sol": cc.checkbox("Sol Recente")
                }
                st.markdown("**Observações:**")
                osa = st.text_area("Anamnese Geral", value=van, height=80)
                osmulher = st.text_area("Saúde da Mulher / Detalhes", value=vsa, height=80)

            with t3:
                st.markdown("**Medidas Corporais:**")
                m1,m2,m3 = st.columns(3)
                pes = m1.number_input("Peso (kg)", step=0.1)
                alt = m2.number_input("Altura (m)", step=0.01)
                busto = m3.number_input("Busto (cm)", step=1.0)
                
                m4,m5,m6 = st.columns(3)
                cint = m4.number_input("Cintura (cm)", step=1.0)
                abd = m5.number_input("Abdômen (cm)", step=1.0)
                quad = m6.number_input("Quadril (cm)", step=1.0)
                
                m7,m8,m9 = st.columns(3)
                coxa = m7.number_input("Coxas (cm)", step=1.0)
                culote = m8.number_input("Culote (cm)", step=1.0)
                braco = m9.number_input("Braços (cm)", step=1.0)
                
                oco = st.text_input("Obs Corporal (Celulite, Flacidez)", value=vco)

            with t4:
                st.markdown("**Análise Facial:**")
                f1,f2 = st.columns(2)
                foto = f1.select_slider("Fototipo", ["I", "II", "III", "IV", "V", "VI"])
                pele = f2.selectbox("Pele", ["Normal", "Seca", "Mista", "Oleosa", "Acneica"])
                ck_face = {
                    "Manchas": st.checkbox("Manchas"), "Acne": st.checkbox("Acne"), 
                    "Rugas": st.checkbox("Rugas"), "Cicatriz": st.checkbox("Cicatriz")
                }
                ofa = st.text_area("Obs Facial / Plano", value=vfa)

            with t5:
                tr = st.text_input("Tratamento")
                pg = st.selectbox("Pagamento", ["PIX", "Cartão", "Dinheiro"])
                vl = st.number_input("Valor", step=10.0)
            
            if st.form_submit_button("💾 SALVAR TUDO"):
                pess = f"Nasc:{dt} Prof:{pf}"
                chk_txt = lista_checks(ck)
                ana_fin = f"Checks:{chk_txt} | {osa}" 
                saude_fin = f"Detalhes:{osmulher}"
                med_fin = f"Peso:{pes} Alt:{alt} Busto:{busto} Cint:{cint} Abd:{abd} Quad:{quad} Coxa:{coxa} Culote:{culote} Braço:{braco} | Obs:{oco}"
                face_checks = lista_checks(ck_face)
                face_fin = f"Foto:{foto} Pele:{pele} | {face_checks} | {ofa}"
                orc_fin = f"Trat:{tr} Pag:{pg} Val:{vl}"
                
                planilha.worksheet("agendamentos").append_row([
                    date.today().strftime("%d/%m/%Y"), datetime.now().strftime("%H:%M"),
                    nm, tl, pess, ana_fin, saude_fin, med_fin, face_fin, orc_fin, "Completo"
                ])
                st.success("Salvo!"); t.sleep(1); st.rerun()

    # === IMPRESSÃO ===
    elif menu == "🖨️ Impressão":
        st.title("🖨️ Imprimir")
        df = carregar_dados(planilha, "agendamentos")
        lst = []; col_n = ""
        if not df.empty:
            for c in df.columns:
                if "nome" in c.lower(): lst=df[c].unique().tolist(); col_n=c; break
        
        sel = st.selectbox("Cliente:", ["..."]+lst)
        if sel != "..." and col_n:
            d = df[df[col_n] == sel].iloc[-1]
            # LOGO PARA PDF
            logo_html = get_logo_html(logo_path)
            
            html = f"""
            <div class="folha-impressao">
                <div style="text-align:center;">{logo_html}<h3>FICHA DE AVALIAÇÃO</h3><small>{d.get('Data','')}</small></div><br>
                <div style="border-bottom:1px solid #ccc; padding:5px;"><b>1. DADOS:</b> {d.get(col_n)} | {get_val(d,['contato'])}<br>{get_val(d,['dados'])}</div>
                <div style="border-bottom:1px solid #ccc; padding:5px;"><b>2. SAÚDE:</b> {get_val(d,['anamnese'])}<br>{get_val(d,['saude'])}</div>
                <div style="border-bottom:1px solid #ccc; padding:5px;"><b>3. CORPO/FACE:</b> {get_val(d,['medidas'])}<br>{get_val(d,['facial'])}</div>
                <div style="border-bottom:1px solid #ccc; padding:5px;"><b>4. ORÇAMENTO:</b> {get_val(d,['orcamento'])}</div>
                <br><br><br><center>__________________________<br>Assinatura</center>
            </div>
            """
            st.markdown(html, unsafe_allow_html=True)
            st.info("Aperte Ctrl + P")

    # === FINANCEIRO ===
    elif menu == "📊 Financeiro":
        st.header("📊 Fluxo de Caixa")
        df_ag = carregar_dados(planilha, "agendamentos"); df_dp = carregar_dados(planilha, "despesas")
        ent = 0.0; sai = 0.0
        if not df_ag.empty:
            for col in df_ag.columns:
                if "orcamento" in col.lower():
                    for item in df_ag[col].astype(str):
                        try:
                            if "Val:" in item: v=item.split("Val:")[1].strip(); ent+=float(v.replace(",", "."))
                            elif "Valor:" in item: v=item.split("R$")[1].strip(); ent+=float(v.replace(",", "."))
                        except: pass
        if not df_dp.empty:
            for col in df_dp.columns:
                if "valor" in col.lower():
                    for item in df_dp[col].astype(str):
                        try: sai+=float(item.replace(",", "."))
                        except: pass
        c1,c2,c3 = st.columns(3)
        c1.metric("Entradas", f"R$ {ent:,.2f}"); c2.metric("Saídas", f"R$ {sai:,.2f}"); c3.metric("Lucro", f"R$ {ent-sai:,.2f}")

    # === DESPESAS ===
    elif menu == "💸 Despesas":
        st.title("Despesas")
        with st.form("dp"):
            v=st.number_input("Valor"); d=st.text_input("Desc")
            if st.form_submit_button("Salvar"):
                planilha.worksheet("despesas").append_row([date.today().strftime("%d/%m/%Y"), d, "Geral", str(v)])
                st.success("Ok!")
        st.dataframe(carregar_dados(planilha, "despesas"))

if __name__ == "__main__":
    main()