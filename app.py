import streamlit as st
import pandas as pd
import gspread
from oauth2client.service_account import ServiceAccountCredentials
from datetime import date, datetime, time, timedelta
import os
import base64
import time as t
import urllib.parse
from PIL import Image
import io

# --- 1. CONFIGURAÇÃO ---
st.set_page_config(page_title="Sistema Clínica", layout="wide", page_icon="🏥")

st.markdown("""
    <meta name="google" content="notranslate">
    <style>
    #MainMenu {visibility: hidden;}
    footer {visibility: hidden;}
    .aviso-proximo {
        background-color: #fff3cd; color: #856404; padding: 15px; border-radius: 10px;
        border-left: 6px solid #ffeeba; font-size: 18px; font-weight: bold; margin-bottom: 20px;
    }
    .aviso-zap {
        background-color: #d1e7dd; color: #0f5132; padding: 10px;
        border-radius: 5px; border: 1px solid #badbcc; margin: 5px 0;
        text-align: center; font-weight: bold; text-decoration: none; display: block;
    }
    .folha-impressao { 
        background-color: white; padding: 40px; border: 1px solid #ddd; 
        font-family: 'Arial', sans-serif; color: black; margin-top: 20px;
    }
    .historico-box { 
        background-color: #e2e3e5; padding: 15px; border-radius: 5px; 
        border-left: 6px solid #333; margin-bottom: 20px; color: #333;
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
        # Pega índices das colunas válidas (com nome)
        idx_validos = [i for i, nome in enumerate(cabecalho) if nome.strip() != ""]
        cols_limpas = [cabecalho[i] for i in idx_validos]
        linhas_limpas = []
        for linha in dados[1:]:
            linha += [""] * (len(cabecalho) - len(linha))
            linhas_limpas.append([linha[i] for i in idx_validos])
        return pd.DataFrame(linhas_limpas, columns=cols_limpas)
    except: return pd.DataFrame()

# --- FUNÇÕES DE LOGO E FOTO ---
def get_logo_path():
    pasta = os.path.dirname(os.path.abspath(__file__))
    for n in ["LOGO.png", "logo.png", "Logo.png"]:
        path = os.path.join(pasta, n)
        if os.path.exists(path): return path
    return None

def get_logo_html():
    path = get_logo_path()
    if path:
        with open(path, "rb") as f:
            b64 = base64.b64encode(f.read()).decode()
        return f'<img src="data:image/png;base64,{b64}" style="max-height:100px; display:block; margin:0 auto;">'
    return ""

def processar_foto(uploaded_file):
    if uploaded_file is None: return ""
    try:
        image = Image.open(uploaded_file)
        image.thumbnail((300, 300)) # Reduz tamanho para não travar
        img_byte_arr = io.BytesIO()
        image.save(img_byte_arr, format='JPEG', quality=70) # Comprime
        return base64.b64encode(img_byte_arr.getvalue()).decode()
    except: return ""

def get_val(linha, chaves):
    for k in linha.index:
        for c in chaves:
            if c.lower() in k.lower(): return str(linha[k])
    return ""

def lista_checks(dic):
    return ", ".join([k for k, v in dic.items() if v])

# --- FUNÇÕES INTELIGENTES (Radar e Conflito) ---
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

# --- 3. APP ---
def main():
    # BARRA LATERAL
    with st.sidebar:
        logo_path = get_logo_path()
        if logo_path: st.image(logo_path, use_container_width=True)
        else: st.title("🏥 Clínica")
            
        st.header("Menu")
        menu = st.radio("Ir para:", ["📅 Agenda", "📝 Ficha Completa", "🖨️ Impressão", "📊 Financeiro", "💸 Despesas"])
        
        planilha = conectar()
        if not planilha: st.error("Erro Conexão"); st.stop()
        df_global = carregar_dados(planilha, "agendamentos")

        # RADAR
        lembretes = radar_lembretes(df_global)
        if lembretes:
            st.divider()
            st.error(f"⏰ {len(lembretes)} Clientes em breve!")
            for nome, hora, zap in lembretes:
                st.markdown(f"**{nome}** às **{hora}**")
                if zap:
                    num = "".join(filter(str.isdigit, str(zap)))
                    link = f"https://wa.me/55{num}?text=Ola%20{nome},%20lembrete%20do%20seu%20horario%20as%20{hora}!"
                    st.markdown(f"[📲 Avisar Agora]({link})")
                st.divider()
        
        if st.button("🔄 Recarregar"): st.rerun()

    # === AGENDA ===
    if menu == "📅 Agenda":
        st.title("📅 Agenda")
        
        if not df_global.empty:
            busca = st.text_input("🔎 Pesquisar na Agenda:")
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
                
                # VERIFICAR DUPLICIDADE NO AGENDAMENTO TAMBÉM
                duplicado = False
                if not df_global.empty:
                    filtro = df_global[(df_global['Data'] == d_fmt) & (df_global['Nome_Cliente'].str.lower() == n.strip().lower())]
                    if not filtro.empty: duplicado = True

                if verificar_conflito(df_global, d_fmt, h) and not duplicado:
                    st.error(f"❌ Horário {h} ocupado em {d_fmt}!")
                elif duplicado:
                     st.warning("⚠️ Esse cliente já está agendado para hoje. Use a Ficha Completa para editar.")
                else:
                    planilha.worksheet("agendamentos").append_row([d_fmt, str(h), n, z, "", "", "", "", "", "", "Agendado", ""])
                    st.success("Agendado!")
                    if z:
                        link = f"https://wa.me/55{''.join(filter(str.isdigit, z))}?text=Ola%20{n},%20agendamento%20confirmado%20dia%20{d_fmt}%20as%20{h}"
                        st.markdown(f'<a href="{link}" target="_blank" class="aviso-zap">📲 ENVIAR MENSAGEM WHATSAPP</a>', unsafe_allow_html=True)
                    t.sleep(3); st.rerun()

    # === FICHA ===
    elif menu == "📝 Ficha Completa":
        st.title("📝 Ficha Detalhada")
        vn, vt, van, vsa, vco, vfa, vfoto = "", "", "", "", "", "", ""
        
        st.markdown("##### 🔍 Buscar Cliente")
        lst = []; col_nome = ""
        if not df_global.empty:
            for c in df_global.columns:
                if "nome" in c.lower(): lst=df_global[c].unique().tolist(); col_nome=c; break
        
        filtro = st.text_input("Filtrar nome:", key="busca_f")
        if filtro: lst = [x for x in lst if filtro.lower() in str(x).lower()]
            
        sel = st.selectbox("Selecione:", ["..."]+lst)
        
        if sel != "..." and col_nome:
            dcli = df_global[df_global[col_nome] == sel]
            ult = dcli.iloc[-1]
            vn = str(ult[col_nome]); vt = get_val(ult, ["contato", "tel"])
            
            # Recupera dados anteriores
            for i in range(len(dcli)-1, -1, -1):
                row = dcli.iloc[i]
                if not van: van=get_val(row, ["anamnese"])
                if not vsa: vsa=get_val(row, ["saude", "mulher"])
                if not vco: vco=get_val(row, ["medidas", "corporal"])
                if not vfa: vfa=get_val(row, ["facial"])
            
            # TENTA BUSCAR A FOTO NA ABA HISTORICO (Para não pesar a principal)
            try:
                ws_foto = planilha.worksheet("Historico_Fotos")
                fotos = ws_foto.get_all_values()
                # Procura foto do cliente (de baixo pra cima)
                for f in reversed(fotos):
                    if len(f) > 2 and f[1].lower() == sel.lower() and "http" not in f[2]:
                        vfoto = f[2] # Pega o base64
                        break
            except: pass
            
            if van or vsa: 
                st.info("✅ Histórico carregado!")

        with st.form("ficha"):
            col_img, col_form = st.columns([1, 3])
            
            with col_img:
                st.write("**Foto do Cliente**")
                if vfoto:
                    try: st.image(base64.b64decode(vfoto), width=150, caption="Foto Salva")
                    except: st.error("Erro ao carregar foto")
                
                nova_foto = st.file_uploader("Trocar/Adicionar", type=['jpg','png','jpeg'])

            with col_form:
                c1,c2=st.columns(2)
                nm=c1.text_input("Nome", value=vn); tl=c2.text_input("Tel", value=vt)
                c3,c4=st.columns(2)
                dt=c3.text_input("Nascimento"); pf=c4.text_input("Profissão/CPF")

            t2, t3, t4, t5 = st.tabs(["Saúde", "Corporal", "Facial", "Orçamento"])
            
            with t2:
                c1,c2,c3 = st.columns(3)
                ck = {
                    "Alergia": c1.checkbox("Alergias"), "Remédios": c2.checkbox("Usa Medicamentos"), "Trat. Médico": c3.checkbox("Médico"),
                    "Oncológico": c1.checkbox("Hist. Oncológico"), "Cardíaco": c2.checkbox("Cardíaco"), "Gestante": c3.checkbox("Gestante"),
                    "DIU": c1.checkbox("DIU"), "Hormonal": c2.checkbox("Hormonal"), "Sol": c3.checkbox("Sol")
                }
                osa = st.text_area("Anamnese Geral", value=van, height=70)
                osmulher = st.text_area("Saúde da Mulher", value=vsa, height=70)
            with t3:
                m1,m2,m3=st.columns(3)
                pes=m1.number_input("Peso",step=0.1); alt=m2.number_input("Altura",step=0.01); bus=m3.number_input("Busto",step=1.0)
                cin=m1.number_input("Cintura",step=1.0); abd=m2.number_input("Abdômen",step=1.0); qua=m3.number_input("Quadril",step=1.0)
                cox=m1.number_input("Coxa",step=1.0); cul=m2.number_input("Culote",step=1.0); bra=m3.number_input("Braço",step=1.0)
                oco=st.text_input("Obs Corporal", value=vco)
            with t4:
                ck_face = {"Manchas":st.checkbox("Manchas"), "Acne":st.checkbox("Acne"), "Rugas":st.checkbox("Rugas")}
                ofa=st.text_area("Obs Facial", value=vfa)
            with t5:
                tr=st.text_input("Tratamento"); pg=st.selectbox("Pagamento", ["PIX", "Cartão", "Dinheiro"]); vl=st.number_input("Valor", step=10.0)
            
            if st.form_submit_button("💾 SALVAR TUDO"):
                pess = f"Nasc:{dt} Prof:{pf}"
                chk_txt = lista_checks(ck)
                ana_fin = f"Checks:{chk_txt} | {osa}" 
                saude_fin = f"Detalhes:{osmulher}"
                med_fin = f"Peso:{pes} Alt:{alt} Busto:{bus} Cint:{cin} Abd:{abd} Quad:{qua} Coxa:{cox} Culote:{cul} Braço:{bra} | Obs:{oco}"
                face_checks = lista_checks(ck_face)
                face_fin = f"{face_checks} | {ofa}"
                orc_fin = f"Trat:{tr} Pag:{pg} Val:{vl}"
                
                # --- LÓGICA INTELIGENTE (ANTI-DUPLICIDADE) ---
                ws = planilha.worksheet("agendamentos")
                data_hoje = date.today().strftime("%d/%m/%Y")
                hora_agora = datetime.now().strftime("%H:%M")
                
                # 1. Procura se já existe (Nome + Data de Hoje)
                cell_encontrada = None
                try:
                    records = ws.get_all_records()
                    for i, row in enumerate(records):
                        # Gspread começa linha 2 (1 é header) -> i começa em 0
                        # Logo: Linha Real = i + 2
                        r_nome = str(row.get('Nome_Cliente', '')).lower().strip()
                        r_data = str(row.get('Data', ''))
                        
                        if r_nome == nm.lower().strip() and r_data == data_hoje:
                            cell_encontrada = i + 2
                            break
                except: pass

                # 2. Prepara os dados (SEM A FOTO GIGANTE)
                # Colunas: Data, Hora, Nome, Contato, Dados, Anamnese, Saude, Medidas, Facial, Orcamento, Status, Foto
                
                if cell_encontrada:
                    # >> ATUALIZAR LINHA EXISTENTE
                    # Atualiza colunas 4 (Contato) até 11 (Status)
                    # Range: D{linha}:K{linha}
                    ws.update(f"D{cell_encontrada}:K{cell_encontrada}", [[tl, pess, ana_fin, saude_fin, med_fin, face_fin, orc_fin, "Completo"]])
                    
                    # Limpa a coluna L (Foto) para não travar
                    ws.update_cell(cell_encontrada, 12, "Ver Historico")
                    st.success(f"✅ Ficha de {nm} atualizada na linha {cell_encontrada}!")
                
                else:
                    # >> CRIAR LINHA NOVA
                    ws.append_row([
                        data_hoje, hora_agora,
                        nm, tl, pess, ana_fin, saude_fin, med_fin, face_fin, orc_fin, "Completo", "Ver Historico"
                    ])
                    st.success(f"✨ Novo cadastro criado para {nm}!")

                # --- 3. SALVAR FOTO SEPARADAMENTE ---
                if nova_foto:
                    foto_b64 = processar_foto(nova_foto)
                    try:
                        ws_fotos = planilha.worksheet("Historico_Fotos")
                    except:
                        ws_fotos = planilha.add_worksheet("Historico_Fotos", 1000, 5)
                        ws_fotos.append_row(["Data", "Nome", "Foto_Base64", "Obs"])
                    
                    # Salva na aba separada
                    ws_fotos.append_row([data_hoje, nm, foto_b64, "Salvo via Sistema"])
                    st.info("📸 Foto salva no histórico com segurança.")
                
                t.sleep(2); st.rerun()

    # === IMPRESSÃO ===
    elif menu == "🖨️ Impressão":
        st.title("🖨️ Imprimir")
        lst=[]; col_n=""
        if not df_global.empty:
            for c in df_global.columns:
                if "nome" in c.lower(): lst=df_global[c].unique().tolist(); col_n=c; break
        
        filtro_print = st.text_input("Filtrar nome:")
        if filtro_print: lst = [x for x in lst if filtro_print.lower() in str(x).lower()]
            
        sel = st.selectbox("Cliente:", ["..."]+lst)
        if sel != "..." and col_n:
            d = df_global[df_global[col_n] == sel].iloc[-1]
            logo_html = get_logo_html()
            
            # Tenta pegar foto do Historico_Fotos se não tiver na principal
            fb64 = get_val(d, ["foto", "imagem"])
            if not fb64 or len(fb64) < 50:
                 try:
                    ws_foto = planilha.worksheet