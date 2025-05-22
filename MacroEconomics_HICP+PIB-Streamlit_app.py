import streamlit as st
import requests
import pandas as pd
import matplotlib.pyplot as plt
from datetime import datetime
from openai import OpenAI

# Inicializa OpenAI
client = OpenAI(api_key=st.secrets["OPENAI_API_KEY"])

# --- Función para detectar país desde dirección ---
def obtener_codigo_pais(direccion):
    url = "https://nominatim.openstreetmap.org/search"
    params = {"q": direccion, "format": "json", "limit": 1, "addressdetails": 1}
    headers = {"User-Agent": "macro-app/1.0"}
    try:
        r = requests.get(url, params=params, headers=headers)
        data = r.json()
        if data:
            return data[0]["address"].get("country_code", "").upper()
    except Exception as e:
        st.error(f"Error detectando país: {e}")
    return None

# --- Interfaz de usuario ---
st.title("📊 Macroeconomic Summary Generator (HICP + GDP)")
direccion = st.text_input("Enter a European address:")
longitud = st.slider("Number of words in the summary:", 100, 300, 150, step=25)

if st.button("Generate Summary") and direccion:
    codigo_pais = obtener_codigo_pais(direccion)
    if not codigo_pais:
        st.error("❌ Could not detect the country from the address.")
    else:
        nombre_pais = {
            "NL": "Países Bajos", "ES": "España", "FR": "Francia",
            "IT": "Italia", "DE": "Alemania", "BE": "Bélgica",
            "PT": "Portugal", "AT": "Austria"
        }.get(codigo_pais, f"País ({codigo_pais})")

        anio_corte = datetime.today().year - 5

        # --- Función para obtener datos desde Eurostat ---
        def obtener_df(dataset, extra_params):
            url = f"https://ec.europa.eu/eurostat/api/dissemination/statistics/1.0/data/{dataset}"
            params = {"format": "JSON", "lang": "EN", "geo": codigo_pais}
            params.update(extra_params)
            r = requests.get(url, params=params)
            r.raise_for_status()
            data = r.json()
            idx = data["dimension"]["time"]["category"]["index"]
            lbl = data["dimension"]["time"]["category"]["label"]
            ix_map = {str(v): lbl[k] for k, v in idx.items()}
            valores = [{"Periodo": ix_map[k], "Valor": v} for k, v in data["value"].items()]
            df = pd.DataFrame(valores)
            df = df[df["Periodo"].str[:4].astype(int) >= anio_corte]
            df["Periodo"] = pd.PeriodIndex(df["Periodo"], freq='Q').astype(str)
            return df

        try:
            # --- Datos HICP ---
            df_hicp = obtener_df("prc_hicp_midx", {"coicop": "CP00", "unit": "I15"})

            st.subheader("📈 HICP – Harmonized Inflation Index")
            fig1, ax1 = plt.subplots(figsize=(10, 3))
            ax1.plot(df_hicp["Periodo"], df_hicp["Valor"], color="#DAA520", linewidth=2)
            ax1.set_facecolor("#F5F5F5")
            ax1.tick_params(axis="x", rotation=45)
            ax1.set_ylabel("HICP Index")
            ax1.grid(True, linestyle="--", alpha=0.4)
            st.pyplot(fig1)

            # --- Datos PIB ---
            df_pib = obtener_df("namq_10_gdp", {
                "na_item": "B1GQ",
                "unit": "CLV10_MNAC",
                "s_adj": "NSA"
            })

            st.subheader("📉 GDP – Quarterly Volume (chain-linked)")
            fig2, ax2 = plt.subplots(figsize=(10, 3))
            ax2.plot(df_pib["Periodo"], df_pib["Valor"], color="#4682B4", linewidth=2)
            ax2.set_facecolor("#F5F5F5")
            ax2.tick_params(axis="x", rotation=45)
            ax2.set_ylabel("GDP (national unit)")
            ax2.grid(True, linestyle="--", alpha=0.4)
            st.pyplot(fig2)

            # --- Preparar texto para el resumen ---
            texto_hicp = df_hicp.to_string(index=False)
            texto_pib = df_pib.to_string(index=False)

            prompt_es = f"""
Eres un economista que debe redactar un resumen macroeconómico profesional de aproximadamente {longitud} palabras.

Los siguientes datos reales pertenecen a {nombre_pais}, extraídos directamente de Eurostat:

📌 Inflación armonizada (HICP):
{texto_hicp}

📌 PIB trimestral (volumen encadenado):
{texto_pib}

Redacta un análisis técnico y claro que describa las tendencias económicas más relevantes de los últimos 5 años, incluyendo fases de aceleración o ralentización. Termina con una frase que sitúe al lector en el contexto actual. El texto debe estar en español.
"""

            prompt_en = f"""
You are an economist writing a professional macroeconomic summary of approximately {longitud} words.

The following are real economic indicators for {nombre_pais}, sourced directly from Eurostat:

📌 Harmonized Inflation Index (HICP):
{texto_hicp}

📌 Quarterly GDP (chain-linked volumes):
{texto_pib}

Write a clear, technical summary of the main economic trends over the past 5 years, including any acceleration or slowdown phases. Conclude with a sentence that situates the reader in the current moment. The text must be written in English.
"""

            # --- Llamadas a GPT ---
            respuesta_es = client.chat.completions.create(
                model="gpt-4o",
                messages=[{"role": "user", "content": prompt_es}],
                temperature=0.6
            )

            respuesta_en = client.chat.completions.create(
                model="gpt-4o",
                messages=[{"role": "user", "content": prompt_en}],
                temperature=0.6
            )

            st.subheader("🧠 Resumen en español")
            st.write(respuesta_es.choices[0].message.content.strip())

            st.subheader("🧠 Summary in English")
            st.write(respuesta_en.choices[0].message.content.strip())

        except Exception as e:
            st.error(f"❌ Error al obtener datos o generar el resumen: {e}")

