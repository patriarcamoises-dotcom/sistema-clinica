import streamlit as st
import pandas as pd
import gspread
from oauth2client.service_account import ServiceAccountCredentials
from datetime import date, datetime, time
import os
import base64
import time as t
from PIL import Image
import io

# --- 1. CONFIGURAÇÃO ---
st.set_page_config(page_title="Sistema Clínica", layout="wide", page_icon="🏥")

st.markdown("""
    <style>
    #MainMenu {visibility: hidden;}
    footer {visibility: hidden;}
    .aviso-zap {
        background-color: #d1e7dd; color: #0f5132; padding: 10px;
        border-radius: 5px; border: 1px solid #badbcc; margin: 5px 0;
        text-align: center; font-weight: bold; text-decoration: none; display: block;
    }
    .folha-impressao { 
        background-color: white; padding: 40px; border: 1px solid #ddd; 
        font-family: 'Arial', sans-serif; color: black; margin-top: 20px;
    }
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
    except: return None

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

# --- FUNÇÕES ÚTEIS ---
def get_logo_html():
    return ""

def processar_foto(uploaded_file):
    if uploaded_file is None: return ""
    try:
        image = Image.open(uploaded_file)
        image.thumbnail((400, 400)) # Reduz tamanho
        img_byte_arr = io.BytesIO()
        image.save(img_byte_arr, format='JPEG', quality=70)
        return base64.b64encode(img_byte_arr.getvalue()).decode()
    except: return ""

def get_val(linha, chaves):
    for k in linha.index:
        for c in chaves:
            if c.lower() in k.lower(): return str(linha[k])
    return ""

def lista_checks(dic):
    return ", ".join([k for k, v in dic.items() if v])

def verificar_conflito(df, data_str, hora_obj):
    if df.empty: return False
    hora_str_simples = hora_obj.strftime("%H:%M")
    df_dia = df[df['Data'] == data_str].copy()
    if df_dia.empty: return False
    for h in df_dia['Hora']:
        if str(h).strip().startswith(hora_str_simples): return True
    return False

def radar_lembretes(df):
    if df.empty: return []
    agora = datetime.now()
    hoje_str = agora.strftime("%d/%m/%Y")
    df_hoje = df[df['Data'] == hoje_str].copy()
    avisos = []
    for idx, row in df_hoje.iterrows():
        try:
            hora_str = str(row['Hora'])
            dt_agend = datetime.strptime(f"{hoje_str} {hora_str}", "%d/%m/%Y %H:%M:%S" if len(hora_str)>5 else "%d/%m/%Y %H:%M")
            diferenca = dt_agend - agora
            minutos = diferenca.total_seconds() / 60
            if 0 < minutos <= 130:
                avisos.append((row['Nome_Cliente'], hora_str, get_val(row, ['contato', 'tel', 'zap'])))
        except: pass
    return avisos

# --- 3. APLICAÇÃO ---
def main():
    with st.sidebar:
        st.title("🏥 Clínica")
        st.header("Menu")
        menu = st.radio("Ir para:", ["📅 Agenda", "📝 Ficha Completa", "🖨️ Impressão", "📊 Financeiro", "💸 Despesas"])
        
        planilha = conectar()
        if not planilha: st.error("Erro Conexão Google Sheets"); st.stop()
        df_global = carregar_dados(planilha, "agendamentos")

        lembretes = radar_lembretes(df_global)
        if lembretes:
            st.divider()
            st.error(f"⏰ {len(lembretes)} Clientes em breve!")
            for nome, hora, zap in lembretes:
                st.write(f"**{nome}** às **{hora}**")
        
        if st.button("🔄 Recarregar"): st.rerun()

    # === AGENDA ===
    if menu == "📅 Agenda":
        st.title("📅 Agenda")
        if not df_global.empty:
            busca = st.text_input("🔎 Pesquisar:")
            if busca: st.dataframe(df_global[df_global.astype(str).apply(lambda x: x.str.contains(busca, case=False)).any(axis=1)], use_container_width=True)
            else: st.dataframe(df_global, use_container_width=True)
        else: st.info("Agenda vazia.")
        
        st.divider()
        st.subheader("➕ Novo Agendamento")
        with st.form("age"):
            c1,c2=st.columns(2)
            n=c1.text_input("Nome"); z=c2.text_input("WhatsApp")
            c3,c4=st.columns(2)
            d=c3.date_input("Data", value=date.today()); h=c4.time_input("Hora", value=time(9,0))
            if st.form_submit_button("Agendar"):
                d_fmt = d.strftime("%d/%m/%Y")
                # Verifica duplicidade simples na agenda
                duplicado = False
                if not df_global.empty:
                    filtro = df_global[(df_global['Data'] == d_fmt) & (df_global['Nome_Cliente'].str.lower() == n.strip().lower())]
                    if not filtro.empty: duplicado = True

                if verificar_conflito(df_global, d_fmt, h) and not duplicado:
                    st.error(f"❌ Horário {h} ocupado!")
                elif duplicado:
                    st.warning("⚠️ Cliente já agendado hoje! Use a Ficha Completa para editar.")
                else:
                    planilha.worksheet("agendamentos").append_row([d_fmt, str(h), n, z, "", "", "", "", "", "", "Agendado", ""])
                    st.success("Agendado!"); t.sleep(2); st.rerun()

    # === FICHA ===
    elif menu == "📝 Ficha Completa":
        st.title("📝 Ficha Detalhada")
        vn, vt, van, vsa, vco, vfa, vfoto = "", "", "", "", "", "", ""
        
        st.markdown("##### 🔍 Buscar Cliente")
        lst = []; col_nome = ""
        if not df_global.empty:
            for c in df_global.columns:
                if "nome" in c.lower(): lst=df_global[c].unique().tolist(); col_nome=c; break
        
        filtro = st.text_input("Filtrar nome:", key="bf")
        if filtro: lst = [x for x in lst if filtro.lower() in str(x).lower()]
        sel = st.selectbox("Selecione:", ["..."]+lst)
        
        if sel != "..." and col_nome:
            dcli = df_global[df_global[col_nome] == sel]
            ult = dcli.iloc[-1]
            vn = str(ult[col_nome]); vt = get_val(ult, ["contato", "tel"])
            # Histórico
            for i in range(len(dcli)-1, -1, -1):
                row = dcli.iloc[i]
                if not van: van=get_val(row, ["anamnese"])
                if not vsa: vsa=get_val(row, ["saude"])
                if not vco: vco=get_val(row, ["medidas"])
                if not vfa: vfa=get_val(row, ["facial"])
            
            # Busca foto na aba Historico_Fotos (Seguro)
            try:
                ws_foto = planilha.worksheet("Historico_Fotos")
                fotos = ws_foto.get_all_values()
                for f in reversed(fotos):
                    if len(f) > 2 and f[1].lower() == sel.lower():
                        vfoto = f[2]; break
            except: pass

        with st.form("ficha"):
            c_img, c_form = st.columns([1,3])
            with c_img:
                st.write("📸 **Foto**")
                if vfoto: 
                    try: st.image(base64.b64decode(vfoto), width=150)
                    except: st.write("Sem foto")
                nova_foto = st.file_uploader("Adicionar Foto", type=['jpg','png'])
            
            with c_form:
                c1,c2=st.columns(2)
                nm=c1.text_input("Nome", value=vn); tl=c2.text_input("Tel", value=vt)
                c3,c4=st.columns(2)
                dt=c3.text_input("Nascimento"); pf=c4.text_input("Profissão/CPF")
            
            t2, t3, t4 = st.tabs(["Saúde", "Corporal/Facial", "Orçamento"])
            with t2:
                osa = st.text_area("Anamnese Geral", value=van, height=70)
                osmulher = st.text_area("Saúde da Mulher", value=vsa, height=70)
            with t3:
                c1, c2 = st.columns(2)
                oco=c1.text_area("Corporal", value=vco)
                ofa=c2.text_area("Facial", value=vfa)
            with t4:
                orc_fin=st.text_input("Tratamento / Valor")

            if st.form_submit_button("💾 SALVAR COM SEGURANÇA"):
                pess = f"Nasc:{dt} Prof:{pf}"
                ana_fin = osa; saude_fin = osmulher
                med_fin = oco; face_fin = ofa
                
                # --- ANTI-DUPLICIDADE ---
                ws = planilha.worksheet("agendamentos")
                data_hoje = date.today().strftime("%d/%m/%Y")
                hora_agora = datetime.now().strftime("%H:%M")
                
                cell_encontrada = None
                try:
                    records = ws.get_all_records()
                    for i, row in enumerate(records):
                        # i começa em 0, planilha começa em 2 (1 é header)
                        r_nome = str(row.get('Nome_Cliente', '')).lower().strip()
                        r_data = str(row.get('Data', ''))
                        if r_nome == nm.lower().strip() and r_data == data_hoje:
                            cell_encontrada = i + 2
                            break
                except: pass

                # Salvar Foto Separada
                if nova_foto:
                    b64 = processar_foto(nova_foto)
                    try:
                        ws_f = planilha.worksheet("Historico_Fotos")
                    except:
                        ws_f = planilha.add_worksheet("Historico_Fotos", 1000, 5)
                        ws_f.append_row(["Data","Nome","Foto","Obs"])
                    ws_f.append_row([data_hoje, nm, b64, "Salvo via App"])
                    st.info("Foto salva no histórico!")

                if cell_encontrada:
                    # ATUALIZA LINHA (D até K)
                    range_update = f"D{cell_encontrada}:K{cell_encontrada}"
                    ws.update(range_update, [[tl, pess, ana_fin, saude_fin, med_fin, face_fin, orc_fin, "Completo"]])
                    # LIMPA COLUNA L (Para não travar)
                    ws.update_cell(cell_encontrada, 12, "Ver Historico")
                    st.success(f"✅ Ficha de {nm} atualizada na linha {cell_encontrada}!")
                else:
                    # CRIA NOVA
                    ws.append_row([data_hoje, hora_agora, nm, tl, pess, ana_fin, saude_fin, med_fin, face_fin, orc_fin, "Completo", "Ver Historico"])
                    st.success("✨ Novo cadastro criado!")
                
                t.sleep(2); st.rerun()

    # === IMPRESSÃO ===
    elif menu == "🖨️ Impressão":
        st.title("🖨️ Imprimir")
        lst=[]; col_n=""
        if not df_global.empty:
            for c in df_global.columns:
                if "nome" in c.lower(): lst=df_global[c].unique().tolist(); col_n=c; break
        
        sel = st.selectbox("Cliente:", ["..."]+lst)
        if sel != "..." and col_n:
            d = df_global[df_global[col_n] == sel].iloc[-1]
            
            # Busca foto segura
            fb64 = ""
            try:
                ws_foto = planilha.worksheet("Historico_Fotos")
                fotos = ws_foto.get_all_values()
                for f in reversed(fotos):
                    if len(f) > 2 and f[1].lower() == sel.lower():
                        fb64 = f[2]; break
            except: pass

            foto_html = ""
            if fb64: foto_html = f'<img src="data:image/png;base64,{fb64}" style="width:120px; border:1px solid #ccc;">'

            html = f"""
            <div class="folha-impressao">
                <div style="display:flex; justify-content:space-between;">
                    <div><h3>FICHA</h3><small>{d.get('Data','')}</small></div>
                    <div>{foto_html}</div>
                </div>
                <hr>
                <b>Cliente:</b> {d.get(col_n)}<br>
                <b>Saúde:</b> {get_val(d,['anamnese'])}<br>
                <b>Obs:</b> {get_val(d,['saude'])}
                <br><br><br><center>Assinatura</center>
            </div>
            """
            st.markdown(html, unsafe_allow_html=True)

    # === FINANCEIRO ===
    elif menu == "📊 Financeiro":
        st.header("Fluxo")
        st.info("Em desenvolvimento...")

if __name__ == "__main__":
    main()
